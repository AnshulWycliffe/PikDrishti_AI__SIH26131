"""
predict.py — CLI inference tool for the AgriVision crop disease classifier.

Usage
-----
    python predict.py --image path/to/leaf.jpg
    python predict.py --image path/to/leaf.jpg --top-k 3
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    FLASK_MODEL_PATH, METADATA_JSON, IMAGE_SIZE, CONFIDENCE_THRESHOLD,
)
from utils import parse_class_name, load_json

import numpy as np
import tensorflow as tf
from PIL import Image


def load_resources(model_path: str, metadata_path: str):
    model = tf.keras.models.load_model(model_path)
    meta = load_json(metadata_path)
    return model, meta


def preprocess(image_path: str, image_size) -> np.ndarray:
    img = Image.open(image_path).convert('RGB')
    img = img.resize(image_size, Image.BILINEAR)
    arr = np.array(img, dtype=np.float32)   # [0, 255]
    arr = np.expand_dims(arr, axis=0)       # (1, H, W, 3)
    return arr


def infer(model, arr: np.ndarray, class_names: list, threshold: float, top_k: int) -> dict:
    probs = model.predict(arr, verbose=0)[0]           # shape (num_classes,)
    top_k_indices = np.argsort(probs)[::-1][:top_k]
    confidence = float(probs[top_k_indices[0]])
    predicted_class = class_names[top_k_indices[0]]

    top_predictions = [
        {
            'class': class_names[i],
            'confidence': float(probs[i]),
        }
        for i in top_k_indices
    ]

    if confidence < threshold:
        return {
            'status': 'uncertain',
            'class': None,
            'confidence': confidence,
            'message': 'The image could not be classified reliably.',
            'top_predictions': top_predictions,
        }

    crop, disease = parse_class_name(predicted_class)
    return {
        'status': 'success',
        'class': predicted_class,
        'crop': crop,
        'disease': disease,
        'confidence': confidence,
        'top_predictions': top_predictions,
    }


def pretty_print(result: dict, image_path: str) -> None:
    print(f"\n  Image      : {image_path}")
    print(f"  Status     : {result['status']}")
    if result['status'] == 'uncertain':
        print(f"  Message    : {result['message']}")
        print(f"  Confidence : {result['confidence']:.2%}")
    else:
        print(f"  Crop       : {result.get('crop')}")
        print(f"  Disease    : {result.get('disease')}")
        print(f"  Confidence : {result['confidence']:.2%}")

    if result.get('top_predictions'):
        print("\n  Top Predictions:")
        for i, p in enumerate(result['top_predictions'], 1):
            print(f"    {i}. {p['class']:40s} {p['confidence']:.2%}")
    print()


def main():
    parser = argparse.ArgumentParser(description='Run crop disease inference on a single image.')
    parser.add_argument('--image',  required=True, help='Path to the leaf image')
    parser.add_argument('--model',  default=FLASK_MODEL_PATH, help='Path to .keras model')
    parser.add_argument('--top-k', type=int, default=3, help='Number of top predictions to show')
    parser.add_argument('--threshold', type=float, default=CONFIDENCE_THRESHOLD,
                        help='Confidence threshold (default: 0.70)')
    parser.add_argument('--json', action='store_true', help='Output raw JSON instead of formatted text')
    args = parser.parse_args()

    image_path = args.image
    if not Path(image_path).is_file():
        print(f"Error: image not found: {image_path}")
        sys.exit(1)

    model, meta = load_resources(args.model, METADATA_JSON)
    class_names = meta['classes']

    arr = preprocess(image_path, IMAGE_SIZE)
    result = infer(model, arr, class_names, args.threshold, args.top_k)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        pretty_print(result, image_path)


if __name__ == '__main__':
    main()
