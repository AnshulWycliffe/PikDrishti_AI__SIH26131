"""
evaluate.py — Post-training evaluation of the AgriVision disease classifier.

Usage
-----
    python evaluate.py [--model PATH] [--test-dir PATH]

Outputs
-------
    ml/disease/outputs/classification_report.txt
    ml/disease/outputs/confusion_matrix.png
    ml/disease/outputs/real_world_report.txt
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import tensorflow as tf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    IMAGE_SIZE, BATCH_SIZE, SEED, OUTPUTS_DIR,
    FLASK_MODEL_PATH, METADATA_JSON, CLASSES_JSON,
    TEST_DIR, REAL_WORLD_DIR,
)
from utils import discover_classes, load_json


def load_model_and_meta(model_path: str, metadata_path: str):
    print(f"Loading model from {model_path} …")
    model = tf.keras.models.load_model(model_path)
    meta = load_json(metadata_path)
    class_names = meta['classes']
    return model, class_names, meta


def get_predictions(model, dataset) -> tuple:
    """Run inference over a tf.data.Dataset; return (y_true, y_pred)."""
    y_true, y_pred_probs = [], []
    for images, labels in dataset:
        preds = model.predict(images, verbose=0)
        y_pred_probs.extend(preds)
        y_true.extend(labels.numpy())
    y_true = np.array(y_true, dtype=int)
    y_pred = np.argmax(np.array(y_pred_probs), axis=1)
    return y_true, y_pred


def evaluate_on_directory(model, class_names: list, data_dir: str, label: str) -> dict:
    """Load a dataset directory, run predictions, return metrics dict."""
    ds = tf.keras.utils.image_dataset_from_directory(
        data_dir,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        seed=SEED,
        shuffle=False,
        label_mode='int',
    ).prefetch(tf.data.AUTOTUNE)

    loss_fn = tf.keras.losses.SparseCategoricalCrossentropy()
    all_images, all_labels, all_preds_probs = [], [], []

    for imgs, lbls in ds:
        probs = model.predict(imgs, verbose=0)
        all_images.append(imgs.numpy())
        all_labels.extend(lbls.numpy())
        all_preds_probs.extend(probs)

    y_true = np.array(all_labels, dtype=int)
    probs_arr = np.array(all_preds_probs)
    y_pred = np.argmax(probs_arr, axis=1)

    # Compute loss
    all_imgs_flat = np.concatenate(all_images, axis=0)
    tf_loss = float(loss_fn(y_true, probs_arr).numpy())
    accuracy = float(np.mean(y_true == y_pred))

    report_str = classification_report(
        y_true, y_pred,
        target_names=class_names,
        zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred)

    print(f"\n── {label} ──")
    print(f"  Loss     : {tf_loss:.4f}")
    print(f"  Accuracy : {accuracy:.4f}")
    print(f"\n{report_str}")

    return {
        'label': label,
        'accuracy': accuracy,
        'loss': tf_loss,
        'report': report_str,
        'confusion_matrix': cm.tolist(),
        'y_true': y_true.tolist(),
        'y_pred': y_pred.tolist(),
    }


def save_confusion_matrix(cm: list, class_names: list, filepath: str, title: str) -> None:
    cm_arr = np.array(cm)
    # Normalize
    row_sums = cm_arr.sum(axis=1, keepdims=True)
    cm_norm = cm_arr / np.where(row_sums == 0, 1, row_sums)

    fig_size = max(8, len(class_names))
    fig, ax = plt.subplots(figsize=(fig_size, fig_size - 1))
    sns.heatmap(
        cm_norm,
        annot=True,
        fmt='.2f',
        cmap='Greens',
        xticklabels=class_names,
        yticklabels=class_names,
        linewidths=0.5,
        ax=ax,
    )
    ax.set_title(title, fontsize=13, pad=14)
    ax.set_ylabel('True Label')
    ax.set_xlabel('Predicted Label')
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.yticks(rotation=0, fontsize=8)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    plt.close()
    print(f"Confusion matrix → {filepath}")


def main(model_path: str, test_dir: str) -> None:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    model, class_names, meta = load_model_and_meta(model_path, METADATA_JSON)

    # ── Standard benchmark evaluation ───────────────────────────────────────
    metrics = evaluate_on_directory(model, class_names, test_dir, label='Test Set Evaluation')

    # Save classification report
    report_path = os.path.join(OUTPUTS_DIR, 'classification_report.txt')
    with open(report_path, 'w') as f:
        f.write(f"AgriVision Disease Classifier — Evaluation Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Model    : {model_path}\n")
        f.write(f"Test dir : {test_dir}\n\n")
        f.write(f"Loss     : {metrics['loss']:.4f}\n")
        f.write(f"Accuracy : {metrics['accuracy']:.4f}\n\n")
        f.write(metrics['report'])
        f.write("\n\nNote: These are benchmark results on held-out test data.\n")
        f.write("Real-world field performance may differ due to lighting,\n")
        f.write("camera quality, occlusion, and other environmental factors.\n")
    print(f"Classification report → {report_path}")

    # Save confusion matrix
    cm_path = os.path.join(OUTPUTS_DIR, 'confusion_matrix.png')
    save_confusion_matrix(
        metrics['confusion_matrix'], class_names, cm_path,
        title='Test Set — Normalised Confusion Matrix',
    )

    # ── Real-world evaluation ────────────────────────────────────────────────
    rw_report_path = os.path.join(OUTPUTS_DIR, 'real_world_report.txt')
    rw_dir = Path(REAL_WORLD_DIR)

    if not rw_dir.is_dir() or not any(rw_dir.iterdir()):
        with open(rw_report_path, 'w') as f:
            f.write("Real-World Evaluation Report\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write("No real-world evaluation images provided.\n")
            f.write(f"To run real-world evaluation, place labelled images in:\n  {REAL_WORLD_DIR}\n")
        print(f"Real-world report → {rw_report_path} (no images found)")
    else:
        try:
            rw_metrics = evaluate_on_directory(
                model, class_names, str(rw_dir), label='Real-World Evaluation',
            )
            rw_cm_path = os.path.join(OUTPUTS_DIR, 'confusion_matrix_real_world.png')
            save_confusion_matrix(
                rw_metrics['confusion_matrix'], class_names, rw_cm_path,
                title='Real-World — Normalised Confusion Matrix',
            )
            with open(rw_report_path, 'w') as f:
                f.write("Real-World Evaluation Report\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n\n")
                f.write(f"Loss     : {rw_metrics['loss']:.4f}\n")
                f.write(f"Accuracy : {rw_metrics['accuracy']:.4f}\n\n")
                f.write(rw_metrics['report'])
                f.write("\nIMPORTANT: Real-world accuracy may be lower than benchmark accuracy.\n")
        except Exception as e:
            with open(rw_report_path, 'w') as f:
                f.write(f"Real-world evaluation failed: {e}\n")
            print(f"Real-world evaluation error: {e}")

    print("\n✓ Evaluation complete.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluate the AgriVision disease model.')
    parser.add_argument('--model',    default=FLASK_MODEL_PATH, help='Path to .keras model file')
    parser.add_argument('--test-dir', default=TEST_DIR,         help='Path to test dataset directory')
    args = parser.parse_args()
    main(args.model, args.test_dir)
