import os

# Base directory of the repository (two levels up from ml/disease/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# ── Image / Training hyper-parameters ───────────────────────────────────────
IMAGE_SIZE = (224, 224)
BATCH_SIZE = int(os.getenv('DISEASE_BATCH_SIZE', '32'))
SEED       = int(os.getenv('DISEASE_SEED', '42'))

INITIAL_EPOCHS   = int(os.getenv('DISEASE_INITIAL_EPOCHS',   '15'))
FINE_TUNE_EPOCHS = int(os.getenv('DISEASE_FINE_TUNE_EPOCHS', '10'))
INITIAL_LR       = float(os.getenv('DISEASE_INITIAL_LR',   '1e-3'))
FINE_TUNE_LR     = float(os.getenv('DISEASE_FINE_TUNE_LR', '1e-5'))

EARLY_STOPPING_PATIENCE = int(os.getenv('DISEASE_ES_PATIENCE',  '5'))
LR_REDUCTION_PATIENCE   = int(os.getenv('DISEASE_LR_PATIENCE',  '3'))
LR_REDUCTION_FACTOR     = float(os.getenv('DISEASE_LR_FACTOR', '0.5'))

# Number of layers from the TOP of EfficientNetB0 to unfreeze during fine-tuning
FINE_TUNE_LAYERS = int(os.getenv('DISEASE_FINE_TUNE_LAYERS', '30'))

# Dropout rate in the classification head
DROPOUT_RATE = float(os.getenv('DISEASE_DROPOUT', '0.3'))

# ── Inference ────────────────────────────────────────────────────────────────
# NOTE: 0.70 is an operational threshold, NOT a scientifically derived value.
# Calibrate against your validation data before production deployment.
CONFIDENCE_THRESHOLD = float(os.getenv('DISEASE_CONFIDENCE_THRESHOLD', '0.70'))

# ── Dataset paths (relative to repository root) ──────────────────────────────
DATASET_DIR = os.path.join(BASE_DIR, 'ml', 'disease', 'dataset')
RAW_DIR     = os.path.join(DATASET_DIR, 'raw')
TRAIN_DIR   = os.path.join(DATASET_DIR, 'train')
VAL_DIR     = os.path.join(DATASET_DIR, 'validation')
TEST_DIR    = os.path.join(DATASET_DIR, 'test')

# ── Output / model paths ─────────────────────────────────────────────────────
OUTPUTS_DIR        = os.path.join(BASE_DIR, 'ml', 'disease', 'outputs')
BEST_MODEL_PATH    = os.path.join(OUTPUTS_DIR, 'best_model.keras')
FINAL_MODEL_PATH   = os.path.join(OUTPUTS_DIR, 'disease_model.keras')
CLASSES_JSON       = os.path.join(BASE_DIR, 'models', 'disease_classes.json')
METADATA_JSON      = os.path.join(BASE_DIR, 'models', 'disease_metadata.json')
FLASK_MODEL_PATH   = os.path.join(BASE_DIR, 'models', 'disease_model.keras')

REAL_WORLD_DIR     = os.path.join(BASE_DIR, 'ml', 'disease', 'real_world_test')

# ── Split ratios ─────────────────────────────────────────────────────────────
TRAIN_RATIO = 0.70
VAL_RATIO   = 0.15
TEST_RATIO  = 0.15

# Minimum images per class required before training
MIN_IMAGES_PER_CLASS = 10

# ── Model metadata ───────────────────────────────────────────────────────────
MODEL_NAME    = 'AgriVision Disease Classifier'
MODEL_VERSION = '1.0.0'
ARCHITECTURE  = 'EfficientNetB0'
