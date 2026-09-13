"""
split_dataset.py — Stratified train/validation/test split.

Usage
-----
    python split_dataset.py [--raw-dir PATH] [--seed 42]

Reads images from:
    ml/disease/dataset/raw/<ClassName>/

Copies them (no duplication) into:
    ml/disease/dataset/train/<ClassName>/
    ml/disease/dataset/validation/<ClassName>/
    ml/disease/dataset/test/<ClassName>/

Split ratios (configurable in config.py):
    70% train / 15% validation / 15% test
"""
import os
import sys
import shutil
import random
import argparse
import logging
from pathlib import Path
from collections import defaultdict

# Allow running from any location
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    RAW_DIR, TRAIN_DIR, VAL_DIR, TEST_DIR,
    TRAIN_RATIO, VAL_RATIO, TEST_RATIO, SEED
)
from utils import discover_classes, count_images_per_class, file_md5

try:
    from config import SUPPORTED_EXTENSIONS
except ImportError:
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def split_class(
    class_dir: Path,
    train_dir: Path,
    val_dir: Path,
    test_dir: Path,
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> tuple:
    """
    Split files in *class_dir* into train/val/test sub-directories.
    Returns (n_train, n_val, n_test, n_skipped).
    """
    files = sorted([
        f for f in class_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ])
    if not files:
        logger.warning("No valid images found in %s – skipping class.", class_dir)
        return 0, 0, 0, 0

    # Shuffle deterministically
    rng = random.Random(seed)
    rng.shuffle(files)

    n = len(files)
    n_train = max(1, int(n * train_ratio))
    n_val   = max(1, int(n * val_ratio))
    n_test  = n - n_train - n_val
    if n_test < 1:
        # Safety: ensure at least 1 test image if class is tiny
        if n >= 3:
            n_train -= 1
            n_test = 1
        else:
            n_test = 0

    splits = {
        train_dir: files[:n_train],
        val_dir:   files[n_train:n_train + n_val],
        test_dir:  files[n_train + n_val:],
    }

    skipped = 0
    for dest_base, file_list in splits.items():
        dest_base.mkdir(parents=True, exist_ok=True)
        for src in file_list:
            dest = dest_base / src.name
            if dest.exists():
                skipped += 1
                continue
            shutil.copy2(src, dest)

    return n_train, n_val, len(splits[test_dir]), skipped


def run_split(raw_dir: str, seed: int) -> None:
    raw_path = Path(raw_dir)
    if not raw_path.is_dir():
        logger.error("Raw directory not found: %s", raw_dir)
        sys.exit(1)

    classes = discover_classes(str(raw_path))
    if not classes:
        logger.error("No class sub-directories found in %s", raw_dir)
        sys.exit(1)

    total_train = total_val = total_test = 0
    print("\n═══ Class Distribution ═══\n")

    for cls in classes:
        cls_raw = raw_path / cls
        train_out = Path(TRAIN_DIR) / cls
        val_out   = Path(VAL_DIR)   / cls
        test_out  = Path(TEST_DIR)  / cls

        n_train, n_val, n_test, n_skip = split_class(
            cls_raw, train_out, val_out, test_out,
            TRAIN_RATIO, VAL_RATIO, seed,
        )
        total_train += n_train
        total_val   += n_val
        total_test  += n_test

        print(f"  {cls}")
        print(f"    Train      : {n_train}")
        print(f"    Validation : {n_val}")
        print(f"    Test       : {n_test}")
        if n_skip:
            print(f"    Skipped    : {n_skip}  (already existed)")
        print()

    print("═══ Totals ═══")
    print(f"  Train      : {total_train}")
    print(f"  Validation : {total_val}")
    print(f"  Test       : {total_test}")
    print(f"  Grand Total: {total_train + total_val + total_test}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Stratified dataset split for AgriVision disease detection.')
    parser.add_argument('--raw-dir', default=RAW_DIR,
                        help=f'Directory with raw class images (default: {RAW_DIR})')
    parser.add_argument('--seed', type=int, default=SEED,
                        help=f'Random seed (default: {SEED})')
    args = parser.parse_args()
    run_split(args.raw_dir, args.seed)
