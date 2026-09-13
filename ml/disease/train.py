"""
train.py — EfficientNetB0 transfer-learning + fine-tuning for crop disease detection.

Usage
-----
    python train.py [--epochs 15] [--fine-tune-epochs 10]

Output
------
    ml/disease/outputs/best_model.keras      – best checkpoint during training
    ml/disease/outputs/disease_model.keras   – final fine-tuned model
    ml/disease/outputs/training_history.png  – accuracy/loss plot
    ml/disease/outputs/history.json          – training metrics per epoch
    ml/disease/outputs/training_metadata.json
    models/disease_model.keras               – exported model for Flask
    models/disease_classes.json
    models/disease_metadata.json
"""
import os
import sys
import json
import shutil
import random
import argparse
import logging
from pathlib import Path
from datetime import datetime

# ── Reproducibility ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from config import SEED

os.environ['PYTHONHASHSEED'] = str(SEED)
random.seed(SEED)

import numpy as np
np.random.seed(SEED)

import tensorflow as tf
tf.random.set_seed(SEED)

# ── Training config ──────────────────────────────────────────────────────────
from config import (
    IMAGE_SIZE, BATCH_SIZE,
    INITIAL_EPOCHS, FINE_TUNE_EPOCHS,
    INITIAL_LR, FINE_TUNE_LR,
    EARLY_STOPPING_PATIENCE, LR_REDUCTION_PATIENCE, LR_REDUCTION_FACTOR,
    FINE_TUNE_LAYERS, DROPOUT_RATE,
    TRAIN_DIR, VAL_DIR, TEST_DIR,
    OUTPUTS_DIR, BEST_MODEL_PATH, FINAL_MODEL_PATH,
    CLASSES_JSON, METADATA_JSON, FLASK_MODEL_PATH,
    MODEL_NAME, MODEL_VERSION, ARCHITECTURE, CONFIDENCE_THRESHOLD,
    MIN_IMAGES_PER_CLASS,
)
from utils import (
    discover_classes, count_images_per_class,
    validate_dataset, print_validation_report,
    compute_class_weights, save_json,
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)

os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(FLASK_MODEL_PATH), exist_ok=True)


# ── Dataset loading ──────────────────────────────────────────────────────────

def build_datasets(image_size, batch_size, seed):
    """Load train / val / test as tf.data.Dataset pipelines."""
    train_ds = tf.keras.utils.image_dataset_from_directory(
        TRAIN_DIR,
        image_size=image_size,
        batch_size=batch_size,
        seed=seed,
        shuffle=True,
        label_mode='int',
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        VAL_DIR,
        image_size=image_size,
        batch_size=batch_size,
        seed=seed,
        shuffle=False,
        label_mode='int',
    )
    test_ds = tf.keras.utils.image_dataset_from_directory(
        TEST_DIR,
        image_size=image_size,
        batch_size=batch_size,
        seed=seed,
        shuffle=False,
        label_mode='int',
    )
    class_names = train_ds.class_names
    autotune = tf.data.AUTOTUNE

    # ── Data augmentation (training only) ────────────────────────────────────
    augmentation = tf.keras.Sequential([
        tf.keras.layers.RandomFlip('horizontal'),
        tf.keras.layers.RandomRotation(0.10),
        tf.keras.layers.RandomZoom(0.10),
        tf.keras.layers.RandomContrast(0.15),
    ], name='augmentation')

    def augment(x, y):
        return augmentation(x, training=True), y

    train_ds = (
        train_ds
        .map(augment, num_parallel_calls=autotune)
        .prefetch(autotune)
    )
    val_ds  = val_ds.prefetch(autotune)
    test_ds = test_ds.prefetch(autotune)

    return train_ds, val_ds, test_ds, class_names


# ── Model construction ───────────────────────────────────────────────────────

def build_model(num_classes: int, image_size) -> tf.keras.Model:
    """Build EfficientNetB0 transfer-learning model."""
    inputs = tf.keras.Input(shape=(*image_size, 3), name='input_image')

    # EfficientNetB0 includes its own preprocessing when include_preprocessing=True (default)
    # So we pass raw [0, 255] float images directly.
    base = tf.keras.applications.EfficientNetB0(
        include_top=False,
        weights='imagenet',
        input_tensor=inputs,
    )
    base.trainable = False  # freeze during initial phase

    x = base.output
    x = tf.keras.layers.GlobalAveragePooling2D(name='gap')(x)
    x = tf.keras.layers.Dropout(DROPOUT_RATE, name='dropout')(x)
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax', name='predictions')(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name='AgriVision_Disease_Classifier')
    return model, base


# ── Callbacks ────────────────────────────────────────────────────────────────

def get_callbacks(monitor: str = 'val_accuracy'):
    return [
        tf.keras.callbacks.EarlyStopping(
            monitor=monitor,
            patience=EARLY_STOPPING_PATIENCE,
            restore_best_weights=True,
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor=monitor,
            factor=LR_REDUCTION_FACTOR,
            patience=LR_REDUCTION_PATIENCE,
            min_lr=1e-7,
            verbose=1,
        ),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=BEST_MODEL_PATH,
            monitor=monitor,
            save_best_only=True,
            verbose=1,
        ),
    ]


# ── Training ─────────────────────────────────────────────────────────────────

def main(initial_epochs: int = INITIAL_EPOCHS, fine_tune_epochs: int = FINE_TUNE_EPOCHS):
    start_time = datetime.now()

    # ── Validate dataset ─────────────────────────────────────────────────────
    print("\n── Validating training dataset ──")
    report = validate_dataset(TRAIN_DIR, min_images=MIN_IMAGES_PER_CLASS)
    print_validation_report(report)
    if not report['valid']:
        logger.error("Dataset validation failed. Fix the issues above before training.")
        sys.exit(1)

    # ── Discover classes ─────────────────────────────────────────────────────
    class_names = discover_classes(TRAIN_DIR)
    num_classes = len(class_names)
    print(f"Discovered {num_classes} classes: {class_names}\n")

    # ── Load datasets ────────────────────────────────────────────────────────
    train_ds, val_ds, test_ds, tf_class_names = build_datasets(IMAGE_SIZE, BATCH_SIZE, SEED)
    # Prefer tf_class_names (from TF, alphabetically sorted) as canonical order
    class_names = tf_class_names
    num_classes = len(class_names)

    # ── Class weights ─────────────────────────────────────────────────────────
    train_counts = count_images_per_class(TRAIN_DIR)
    class_weight_dict = compute_class_weights(train_counts)

    # ── Build model ──────────────────────────────────────────────────────────
    model, base_model = build_model(num_classes, IMAGE_SIZE)
    model.summary(line_length=100)

    # ── Phase 1: initial training (frozen base) ──────────────────────────────
    print(f"\n── Phase 1: Transfer Learning (frozen backbone, LR={INITIAL_LR}) ──")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=INITIAL_LR),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy'],
    )

    history1 = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=initial_epochs,
        callbacks=get_callbacks(),
        class_weight=class_weight_dict,
        verbose=1,
    )

    # ── Phase 2: fine-tuning (unfreeze last N layers) ────────────────────────
    print(f"\n── Phase 2: Fine-Tuning (last {FINE_TUNE_LAYERS} layers, LR={FINE_TUNE_LR}) ──")
    base_model.trainable = True
    for layer in base_model.layers[:-FINE_TUNE_LAYERS]:
        layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=FINE_TUNE_LR),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy'],
    )

    history2 = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=initial_epochs + fine_tune_epochs,
        initial_epoch=len(history1.history['loss']),
        callbacks=get_callbacks(),
        class_weight=class_weight_dict,
        verbose=1,
    )

    # ── Merge history ─────────────────────────────────────────────────────────
    def merge(h1, h2):
        combined = {}
        for k in h1.history:
            combined[k] = h1.history[k] + h2.history.get(k, [])
        return combined

    history_data = merge(history1, history2)

    # ── Save final model ──────────────────────────────────────────────────────
    model.save(FINAL_MODEL_PATH)
    print(f"Saved final model → {FINAL_MODEL_PATH}")

    # Copy to Flask models directory
    shutil.copy2(FINAL_MODEL_PATH, FLASK_MODEL_PATH)
    print(f"Exported to Flask → {FLASK_MODEL_PATH}")

    # ── Save class metadata ───────────────────────────────────────────────────
    save_json(class_names, CLASSES_JSON)

    metadata = {
        'model_name': MODEL_NAME,
        'version': MODEL_VERSION,
        'architecture': ARCHITECTURE,
        'image_size': list(IMAGE_SIZE),
        'confidence_threshold': CONFIDENCE_THRESHOLD,
        'classes': class_names,
        'num_classes': num_classes,
        'train_counts': train_counts,
        'class_weights': {str(k): v for k, v in class_weight_dict.items()} if class_weight_dict else None,
        'training': {
            'initial_epochs': initial_epochs,
            'fine_tune_epochs': fine_tune_epochs,
            'batch_size': BATCH_SIZE,
            'initial_lr': INITIAL_LR,
            'fine_tune_lr': FINE_TUNE_LR,
            'fine_tune_layers': FINE_TUNE_LAYERS,
            'dropout': DROPOUT_RATE,
            'seed': SEED,
        },
        'trained_at': start_time.isoformat(),
    }
    save_json(metadata, METADATA_JSON)

    # ── Save history JSON ─────────────────────────────────────────────────────
    history_json_path = os.path.join(OUTPUTS_DIR, 'history.json')
    save_json(history_data, history_json_path)

    # ── Training curves ───────────────────────────────────────────────────────
    _plot_history(history_data, initial_epochs)

    duration = (datetime.now() - start_time).total_seconds()
    print(f"\n✓ Training complete in {duration/60:.1f} minutes.")
    print(f"  Model : {FLASK_MODEL_PATH}")
    print(f"  Classes: {CLASSES_JSON}")


def _plot_history(history_data: dict, phase_split: int) -> None:
    import matplotlib.pyplot as plt
    epochs = range(1, len(history_data['accuracy']) + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(epochs, history_data['accuracy'],     'b-o', label='Train accuracy',  markersize=3)
    ax1.plot(epochs, history_data['val_accuracy'], 'r-o', label='Val accuracy',    markersize=3)
    ax1.axvline(x=phase_split, color='gray', linestyle='--', linewidth=1, label='Fine-tune start')
    ax1.set_title('Accuracy')
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('Accuracy')
    ax1.legend()
    ax1.grid(True, alpha=0.4)

    ax2.plot(epochs, history_data['loss'],     'b-o', label='Train loss',   markersize=3)
    ax2.plot(epochs, history_data['val_loss'], 'r-o', label='Val loss',     markersize=3)
    ax2.axvline(x=phase_split, color='gray', linestyle='--', linewidth=1, label='Fine-tune start')
    ax2.set_title('Loss')
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Loss')
    ax2.legend()
    ax2.grid(True, alpha=0.4)

    plt.suptitle('AgriVision Disease Classifier — Training History', fontsize=13)
    plt.tight_layout()
    out_path = os.path.join(OUTPUTS_DIR, 'training_history.png')
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Training history plot → {out_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train the AgriVision crop disease model.')
    parser.add_argument('--epochs',          type=int, default=INITIAL_EPOCHS,   help='Initial training epochs')
    parser.add_argument('--fine-tune-epochs', type=int, default=FINE_TUNE_EPOCHS, help='Fine-tuning epochs')
    args = parser.parse_args()
    main(args.epochs, args.fine_tune_epochs)
