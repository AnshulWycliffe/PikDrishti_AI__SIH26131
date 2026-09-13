"""
disease_service.py — PikDrishti AI crop disease detection service.

Modes
-----
DEMO_MODE = true (default)
    Returns deterministic Hindi mock results for development / hackathon demos.

DEMO_MODE = false
    Loads a real EfficientNetB0 Keras model from DISEASE_MODEL_PATH,
    performs actual inference, and returns structured results.

The model is loaded **once** at module import time (or first use) — never
per request.  This is enforced by the _DiseaseModel singleton below.
"""
from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Utility: class name parser (no external dependencies)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_class_name(class_str: str) -> tuple[str, str]:
    """
    Convert a directory-style class string into (crop, disease).

    Handles both:
      - 'Tomato___Early_Blight'  (triple-underscore separator)
      - 'Tomato_Early_blight'    (single-underscore, real PlantVillage naming)
      - 'Pepper__bell___healthy' (double-underscore variety + disease)

    Examples
    --------
    >>> parse_class_name('Tomato___Early_Blight')
    ('Tomato', 'Early Blight')
    >>> parse_class_name('Tomato_Early_blight')
    ('Tomato', 'Early Blight')
    >>> parse_class_name('Pepper__bell___Bacterial_spot')
    ('Pepper Bell', 'Bacterial Spot')
    """
    # Prefer triple-underscore split first
    if '___' in class_str:
        parts = class_str.split('___', 1)
        crop    = parts[0].strip().replace('_', ' ').title()
        disease = parts[1].strip().replace('_', ' ').title() if len(parts) > 1 else 'Unknown'
        return crop, disease

    # Known crop prefixes to detect single-underscore names (order matters — longest first)
    CROP_PREFIXES = [
        'Pepper__bell',
        'Tomato',
        'Potato',
        'Apple',
        'Cherry',
        'Corn',
        'Grape',
        'Orange',
        'Peach',
        'Squash',
        'Strawberry',
    ]
    class_lower = class_str.lower()
    for prefix in CROP_PREFIXES:
        if class_lower.startswith(prefix.lower()):
            crop    = prefix.replace('_', ' ').replace('  ', ' ').title()
            rest    = class_str[len(prefix):].lstrip('_')
            disease = rest.replace('_', ' ').title() if rest else 'Healthy'
            return crop, disease

    # Fallback: preserve the original class name when there is no separator.
    # This keeps names like 'SomeClass' as crop='SomeClass', disease='Unknown'
    # instead of incorrectly title-casing them to 'Someclass'.
    if '_' not in class_str:
        return class_str, 'Unknown'

    parts   = class_str.split('_', 1)
    crop    = parts[0]
    disease = parts[1].replace('_', ' ').title() if len(parts) > 1 else 'Unknown'
    return crop, disease


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton model loader
# ═══════════════════════════════════════════════════════════════════════════════

class _DiseaseModel:
    """
    Singleton wrapper that loads the Keras model once and provides predict().
    Thread-safety note: Flask development server is single-threaded; for
    production Gunicorn use, pre-load the model in a post-fork hook or
    accept that each worker loads the model once independently.
    """

    _instance: Optional['_DiseaseModel'] = None
    _loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, model_path: str, metadata_path: str, threshold: float) -> None:
        if self._loaded:
            return
        try:
            import tensorflow as tf  # lazy import — only needed in REAL mode
            tf.config.optimizer.set_jit(True)
            import numpy as np
            self._tf = tf
            self._np = np

            logger.info("Loading disease model from %s …", model_path)
            self.model = tf.keras.models.load_model(model_path)

            # Load class names from metadata
            with open(metadata_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            self.class_names: List[str] = meta['classes']
            self.image_size: tuple = tuple(meta.get('image_size', [224, 224]))
            self.threshold = threshold
            self._loaded = True
            logger.info(
                "Disease model loaded — %d classes, threshold=%.2f",
                len(self.class_names), self.threshold,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Disease model file not found: {e}\n"
                "Train the model first:\n"
                "  1. python ml/disease/split_dataset.py\n"
                "  2. python ml/disease/train.py\n"
                "Then restart the Flask server."
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to load disease model: {e}") from e

    def predict(self, pil_image, top_k: int = 3) -> dict:
        """
        Run inference on a PIL image.

        Returns a dict matching the API contract:
        {
            "status"          : "success" | "uncertain",
            "crop"            : str | None,
            "disease"         : str | None,
            "confidence"      : float,
            "severity"        : null,           # not modelled
            "top_predictions" : [...],
        }
        """
        tf, np = self._tf, self._np

        # Pre-process: RGB, resize, float32, batch dim
        img = pil_image.convert('RGB')
        img = img.resize(self.image_size, 1)        # BILINEAR = 1
        arr = np.array(img, dtype=np.float32)       # [0, 255] — EfficientNet handles scaling
        arr = np.expand_dims(arr, axis=0)           # (1, H, W, 3)

        probs = self.model.predict(arr, verbose=0)[0]   # (num_classes,)
        top_indices = np.argsort(probs)[::-1][:top_k]
        confidence  = float(probs[top_indices[0]])
        predicted   = self.class_names[top_indices[0]]

        top_predictions = [
            {
                'class':      self.class_names[i],
                'confidence': float(probs[i]),
            }
            for i in top_indices
        ]

        if confidence < self.threshold:
            return {
                'status':          'uncertain',
                'crop':            None,
                'disease':         None,
                'confidence':      confidence,
                'severity':        None,
                'top_predictions': top_predictions,
                'message':         'The image could not be classified reliably. Please capture a clearer leaf photo.',
            }

        crop, disease = parse_class_name(predicted)
        return {
            'status':          'success',
            'crop':            crop,
            'disease':         disease,
            'confidence':      confidence,
            'severity':        None,   # not yet modelled — Gemini may discuss it
            'top_predictions': top_predictions,
        }


_model_singleton = _DiseaseModel()


# ═══════════════════════════════════════════════════════════════════════════════
# Public service
# ═══════════════════════════════════════════════════════════════════════════════

class DiseaseService:
    """
    Stateless façade called by Flask routes.

    predict(image_file, farmer_observation=None) → dict
    """

    @staticmethod
    def _validate_file(image_file) -> Optional[dict]:
        """Return an error dict if the file is invalid, else None."""
        if not image_file or getattr(image_file, 'filename', '') == '':
            return {'success': False, 'error': 'No image provided.'}
        mime = getattr(image_file, 'content_type', '')
        if not mime or not mime.startswith('image/'):
            return {'success': False, 'error': 'Invalid file type. Please upload an image.'}
        return None

    @staticmethod
    def _check_quality(pil_image) -> Optional[dict]:
        """
        Lightweight quality check; returns an error dict or None.
        Blurriness detection requires scipy — if not installed, skip.
        """
        w, h = pil_image.size
        if w < 64 or h < 64:
            return {
                'success': False,
                'status': 'invalid_image',
                'error': 'Image is too small. Please capture a clearer photo of the leaf.',
            }
        return None

    @staticmethod
    def predict(image_file, farmer_observation=None) -> dict:
        """
        Main prediction entry point.

        Parameters
        ----------
        image_file          : Werkzeug FileStorage or any file-like with .read()
        farmer_observation  : Optional str  — forwarded to the caller for Gemini context

        Returns
        -------
        dict with at minimum:
            success, crop, disease, confidence, severity, top_predictions
        """
        from flask import current_app  # imported here to keep tests easy

        # ── 1. File validation ────────────────────────────────────────────────
        err = DiseaseService._validate_file(image_file)
        if err:
            return err

        # ── 2. Read image bytes ───────────────────────────────────────────────
        try:
            from PIL import Image
            image_bytes = image_file.read()
            pil_image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            logger.exception("Failed to open uploaded image.")
            return {'success': False, 'error': f'Could not read image: {e}'}

        # ── 3. Image quality check (optional) ────────────────────────────────
        quality_err = DiseaseService._check_quality(pil_image)
        if quality_err:
            return quality_err

        # ── 4. DEMO_MODE branch ───────────────────────────────────────────────
        if current_app.config.get('DEMO_MODE', True):
            return {
                'success': True,
                'status':  'success',
                'crop':    'टमाटर',
                'disease': 'अर्ली ब्लाइट (अगेती झुलसा)',
                'confidence': 0.943,
                'severity': None,
                'symptoms': [
                    'निचली पत्तियों पर भूरे रंग के धब्बे',
                    'पीले किनारे',
                    'धब्बों में गहरे संकेंद्रित वलय',
                ],
                'recommendations': [
                    'संक्रमित निचली पत्तियों को तुरंत हटा दें',
                    'तांबे-आधारित फफूंदनाशक (Fungicide) का प्रयोग करें',
                    'पौधों के चारों ओर हवा का संचार बढ़ाएं',
                ],
                'prevention': [
                    'हर साल फसल चक्र अपनाएं',
                    'ऊपर से सिंचाई करने से बचें',
                    'पत्तियों को जमीन से दूर रखने के लिए पौधों को सहारा दें',
                ],
                'top_predictions': [
                    {'class': 'Tomato___Early_Blight', 'confidence': 0.943},
                    {'class': 'Tomato___Late_Blight',  'confidence': 0.041},
                    {'class': 'Tomato___Healthy',      'confidence': 0.016},
                ],
            }

        # ── 5. REAL model inference ───────────────────────────────────────────
        model_path    = current_app.config['DISEASE_MODEL_PATH']
        metadata_path = str(Path(model_path).parent / 'disease_metadata.json')
        threshold     = current_app.config.get('DISEASE_CONFIDENCE_THRESHOLD', 0.70)

        try:
            _model_singleton.load(model_path, metadata_path, threshold)
        except RuntimeError as e:
            logger.error("Model load error: %s", e)
            return {'success': False, 'error': str(e)}

        try:
            result = _model_singleton.predict(pil_image, top_k=3)
            result['success'] = True

            # ── 6. Build Gemini-ready context string ──────────────────────────
            top_str = '\n'.join(
                f"  {i+1}. {p['class']} — {p['confidence']:.1%}"
                for i, p in enumerate(result.get('top_predictions', []))
            )
            result['gemini_context'] = (
                f"Disease Model Prediction:\n"
                f"  Crop      : {result.get('crop')}\n"
                f"  Disease   : {result.get('disease')}\n"
                f"  Confidence: {result.get('confidence', 0):.1%}\n\n"
                f"Top Predictions:\n{top_str}\n"
            )
            if farmer_observation:
                result['gemini_context'] += (
                    f"\nFarmer Observation:\n  \"{farmer_observation}\"\n"
                )

            return result

        except Exception as e:
            logger.exception("Inference failed.")
            return {'success': False, 'error': f'Inference error: {e}'}
