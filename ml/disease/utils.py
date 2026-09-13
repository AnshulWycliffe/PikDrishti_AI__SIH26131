"""
utils.py — shared helper functions for the AgriVision disease detection pipeline.
Covers: class discovery, dataset validation, class-name parsing, image quality
checks, and preprocessing consistent with EfficientNetB0 training.
"""
import os
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import numpy as np
from PIL import Image, ImageStat, UnidentifiedImageError

logger = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


# ── Class discovery ──────────────────────────────────────────────────────────

def discover_classes(dataset_dir: str) -> List[str]:
    """Return sorted list of class names (sub-directory names) in *dataset_dir*."""
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    classes = sorted([
        d.name for d in dataset_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ])
    if not classes:
        raise ValueError(f"No class directories found in {dataset_dir}")
    return classes


def count_images_per_class(dataset_dir: str) -> Dict[str, int]:
    """Return {class_name: image_count} for every class in *dataset_dir*."""
    classes = discover_classes(dataset_dir)
    counts = {}
    for cls in classes:
        cls_dir = Path(dataset_dir) / cls
        counts[cls] = sum(
            1 for f in cls_dir.iterdir()
            if f.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    return counts


# ── Class name parsing ───────────────────────────────────────────────────────

def parse_class_name(class_str: str) -> Tuple[str, str]:
    """
    Convert a directory-style class name into (crop, disease).

    Examples
    --------
    >>> parse_class_name('Tomato___Early_Blight')
    ('Tomato', 'Early Blight')
    >>> parse_class_name('Potato___Healthy')
    ('Potato', 'Healthy')
    """
    parts = class_str.split('___', 1)
    crop = parts[0].strip().replace('_', ' ')
    disease = parts[1].strip().replace('_', ' ') if len(parts) > 1 else 'Unknown'
    return crop, disease


# ── Dataset validation ───────────────────────────────────────────────────────

def validate_dataset(dataset_dir: str, min_images: int = 10) -> Dict:
    """
    Validate a dataset directory.

    Checks
    ------
    - Each class directory exists.
    - Each image is readable by Pillow (not corrupted, not zero-byte).
    - No unsupported file extensions (warnings only).
    - Minimum image count per class.

    Returns
    -------
    dict with keys:
        'valid': bool
        'classes': List[str]
        'counts': Dict[str, int]
        'corrupted': List[str]
        'skipped': List[str]
        'warnings': List[str]
    """
    result = {
        'valid': True,
        'classes': [],
        'counts': {},
        'corrupted': [],
        'skipped': [],
        'warnings': [],
    }

    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_dir():
        result['valid'] = False
        result['warnings'].append(f"Dataset directory does not exist: {dataset_dir}")
        return result

    classes = discover_classes(str(dataset_dir))
    result['classes'] = classes

    for cls in classes:
        cls_dir = dataset_dir / cls
        valid_count = 0
        for fpath in sorted(cls_dir.iterdir()):
            if fpath.is_dir():
                continue
            if fpath.suffix.lower() not in SUPPORTED_EXTENSIONS:
                result['skipped'].append(str(fpath))
                result['warnings'].append(f"Unsupported extension: {fpath.name}")
                continue
            if fpath.stat().st_size == 0:
                result['corrupted'].append(str(fpath))
                logger.warning("Zero-byte file skipped: %s", fpath)
                continue
            try:
                img = Image.open(fpath)
                img.verify()  # catches truncated / corrupted images
                valid_count += 1
            except (UnidentifiedImageError, Exception) as exc:
                result['corrupted'].append(str(fpath))
                logger.warning("Corrupted image skipped (%s): %s", fpath.name, exc)

        result['counts'][cls] = valid_count
        if valid_count < min_images:
            msg = (
                f"Class '{cls}' has only {valid_count} valid images "
                f"(minimum required: {min_images})."
            )
            result['warnings'].append(msg)
            if valid_count == 0:
                result['valid'] = False

    return result


def print_validation_report(report: Dict) -> None:
    """Pretty-print the output of validate_dataset()."""
    print("\n── Dataset Validation Report ──")
    print(f"Status : {'✓ VALID' if report['valid'] else '✗ INVALID'}")
    print(f"Classes: {len(report['classes'])}\n")
    for cls, count in report['counts'].items():
        print(f"  {cls:<40} {count:>6} images")
    if report['corrupted']:
        print(f"\n  ⚠  Corrupted / unreadable files: {len(report['corrupted'])}")
        for p in report['corrupted'][:10]:
            print(f"     {p}")
    if report['skipped']:
        print(f"\n  ⚠  Skipped (unsupported extension): {len(report['skipped'])}")
    if report['warnings']:
        print("\n  Warnings:")
        for w in report['warnings']:
            print(f"    - {w}")
    print()


# ── Image quality checks ─────────────────────────────────────────────────────

def check_image_quality(
    pil_image: Image.Image,
    min_size: int = 64,
    min_brightness: float = 10.0,
    max_brightness: float = 245.0,
    blur_threshold: float = 80.0,
    enabled: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Perform basic quality checks on a PIL image before inference.

    Returns (True, None) if the image passes all checks,
    or (False, reason_string) if it fails.

    Parameters
    ----------
    pil_image       : PIL.Image.Image  — image to check
    min_size        : int              — minimum width/height in pixels
    min_brightness  : float            — mean pixel value considered too dark
    max_brightness  : float            — mean pixel value considered overexposed
    blur_threshold  : float            — Laplacian variance below this → blurry
    enabled         : bool             — set False to bypass all checks
    """
    if not enabled:
        return True, None

    w, h = pil_image.size
    if w < min_size or h < min_size:
        return False, f"Image too small ({w}×{h}). Please capture a clearer photo."

    gray = pil_image.convert('L')
    stat = ImageStat.Stat(gray)
    mean_brightness = stat.mean[0]

    if mean_brightness < min_brightness:
        return False, "Image is too dark. Please use better lighting."
    if mean_brightness > max_brightness:
        return False, "Image is overexposed. Please avoid direct sunlight on the lens."

    # Blur detection: variance of the Laplacian (approximated via numpy)
    arr = np.array(gray, dtype=np.float32)
    laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
    from scipy.ndimage import convolve  # type: ignore
    filtered = convolve(arr, laplacian)
    var = float(np.var(filtered))
    if var < blur_threshold:
        return False, "Image appears blurry. Please capture a clearer image of the affected leaf."

    return True, None


# ── Preprocessing (must match training pipeline exactly) ─────────────────────

def preprocess_pil_image(pil_image: Image.Image, image_size: Tuple[int, int]) -> np.ndarray:
    """
    Preprocess a PIL image for EfficientNetB0 inference.

    Steps
    -----
    1. Convert to RGB (handles RGBA, grayscale, etc.)
    2. Resize to image_size
    3. Convert to float32
    4. Apply EfficientNetB0-specific scaling via
       tf.keras.applications.efficientnet.preprocess_input
       (scales pixels to [-1, 1]).
    5. Add batch dimension → shape (1, H, W, 3)

    The same scaling is applied during training via the Rescaling layer
    embedded in EfficientNetB0 when include_preprocessing=True (default).
    When using include_preprocessing=True, DO NOT apply external
    preprocess_input — just scale to [0, 255] uint8.  This function
    keeps images as uint8 because EfficientNetB0 includes its own
    preprocessing.
    """
    img = pil_image.convert('RGB')
    img = img.resize(image_size, Image.BILINEAR)
    arr = np.array(img, dtype=np.float32)          # shape (H, W, 3), range 0-255
    arr = np.expand_dims(arr, axis=0)               # shape (1, H, W, 3)
    return arr


# ── Class weights ────────────────────────────────────────────────────────────

def compute_class_weights(class_counts: Dict[str, int]) -> Optional[Dict[int, float]]:
    """
    Compute per-class weights to mitigate class imbalance.

    Returns None if the maximum imbalance ratio is <= 1.2 (considered balanced).
    Otherwise returns {class_index: weight} using sklearn.
    """
    from sklearn.utils.class_weight import compute_class_weight  # type: ignore

    class_names = sorted(class_counts.keys())
    labels = []
    for idx, cls in enumerate(class_names):
        labels.extend([idx] * class_counts[cls])

    labels = np.array(labels, dtype=int)
    counts = np.array([class_counts[c] for c in class_names], dtype=float)
    max_ratio = counts.max() / (counts.min() + 1e-9)

    if max_ratio <= 1.2:
        print("Class distribution is balanced (ratio ≤ 1.2). Skipping class weights.")
        return None

    weights = compute_class_weight(
        class_weight='balanced',
        classes=np.arange(len(class_names)),
        y=labels,
    )
    weight_dict = {idx: float(w) for idx, w in enumerate(weights)}
    print("Class Weights:")
    for idx, cls in enumerate(class_names):
        print(f"  {cls:<40} {weight_dict[idx]:.4f}")
    return weight_dict


# ── File hash (for duplicate detection) ─────────────────────────────────────

def file_md5(filepath: str) -> str:
    """Return the MD5 hex digest of a file (for duplicate detection)."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


# ── JSON helpers ─────────────────────────────────────────────────────────────

def save_json(data: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved → {path}")


def load_json(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
