"""
tests/test_disease_service.py — Unit tests for DiseaseService.

Run with:
    pytest -q tests/test_disease_service.py

The tests use a tiny in-memory Keras model so TensorFlow does not need to
load the full EfficientNet weights during CI.
"""
import io
import json
import os
import sys
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# ── Add project root to sys.path ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.disease_service import parse_class_name, DiseaseService, _DiseaseModel


# ═══════════════════════════════════════════════════════════════════════════════
# parse_class_name
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseClassName:
    def test_basic(self):
        crop, disease = parse_class_name('Tomato___Early_Blight')
        assert crop == 'Tomato'
        assert disease == 'Early Blight'

    def test_healthy(self):
        crop, disease = parse_class_name('Potato___Healthy')
        assert crop == 'Potato'
        assert disease == 'Healthy'

    def test_no_separator(self):
        crop, disease = parse_class_name('SomeClass')
        assert crop == 'SomeClass'
        assert disease == 'Unknown'

    def test_underscores_in_names(self):
        crop, disease = parse_class_name('Bell_Pepper___Late_Blight')
        assert crop == 'Bell Pepper'
        assert disease == 'Late Blight'


# ═══════════════════════════════════════════════════════════════════════════════
# _DiseaseModel (singleton inference)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def tiny_model_fixture(tmp_path):
    """
    Build a tiny in-memory Keras model that matches EfficientNetB0's I/O shape.
    Saves it to tmp_path and returns (model_path, metadata_path, class_names).
    """
    import tensorflow as tf

    class_names = [
        'Potato___Early_Blight', 'Potato___Healthy', 'Potato___Late_Blight',
        'Tomato___Early_Blight', 'Tomato___Healthy', 'Tomato___Late_Blight',
    ]
    num_classes = len(class_names)

    inputs = tf.keras.Input(shape=(224, 224, 3))
    x = tf.keras.layers.GlobalAveragePooling2D()(inputs)
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    model = tf.keras.Model(inputs, outputs)

    model_path = str(tmp_path / 'disease_model.keras')
    model.save(model_path)

    meta = {
        'model_name': 'Test',
        'version': '0.0.1',
        'architecture': 'Tiny',
        'image_size': [224, 224],
        'confidence_threshold': 0.70,
        'classes': class_names,
    }
    meta_path = str(tmp_path / 'disease_metadata.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f)

    return model_path, meta_path, class_names


class TestDiseaseModelSingleton:
    def _fresh_model(self):
        """Return a new (unlocked) _DiseaseModel for testing."""
        m = _DiseaseModel.__new__(_DiseaseModel)
        m._loaded = False
        m._instance = m
        return m

    def test_load_and_predict(self, tiny_model_fixture):
        model_path, meta_path, class_names = tiny_model_fixture
        m = self._fresh_model()
        m.load(model_path, meta_path, threshold=0.70)
        assert m._loaded
        assert m.class_names == class_names

        from PIL import Image
        pil = Image.new('RGB', (224, 224), color=(100, 150, 80))
        result = m.predict(pil, top_k=3)
        assert 'status' in result
        assert len(result['top_predictions']) == 3

    def test_prediction_shape(self, tiny_model_fixture):
        model_path, meta_path, class_names = tiny_model_fixture
        m = self._fresh_model()
        m.load(model_path, meta_path, threshold=0.0)  # always "success"
        from PIL import Image
        pil = Image.new('RGB', (100, 100))
        result = m.predict(pil, top_k=3)
        assert result['status'] == 'success'
        assert result['crop'] is not None
        assert result['disease'] is not None
        assert isinstance(result['confidence'], float)

    def test_confidence_threshold_uncertain(self, tiny_model_fixture):
        model_path, meta_path, class_names = tiny_model_fixture
        m = self._fresh_model()
        m.load(model_path, meta_path, threshold=0.99)  # impossible to reach → uncertain
        from PIL import Image
        pil = Image.new('RGB', (224, 224))
        result = m.predict(pil)
        assert result['status'] == 'uncertain'
        assert result['crop'] is None
        assert result['disease'] is None

    def test_top_k_predictions(self, tiny_model_fixture):
        model_path, meta_path, class_names = tiny_model_fixture
        m = self._fresh_model()
        m.load(model_path, meta_path, threshold=0.0)
        from PIL import Image
        pil = Image.new('RGB', (224, 224))
        result = m.predict(pil, top_k=2)
        assert len(result['top_predictions']) == 2

    def test_severity_is_null(self, tiny_model_fixture):
        model_path, meta_path, class_names = tiny_model_fixture
        m = self._fresh_model()
        m.load(model_path, meta_path, threshold=0.0)
        from PIL import Image
        pil = Image.new('RGB', (224, 224))
        result = m.predict(pil)
        assert result['severity'] is None


# ═══════════════════════════════════════════════════════════════════════════════
# DiseaseService (Flask-level)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_fake_file(content_type='image/jpeg', filename='leaf.jpg'):
    f = MagicMock()
    f.filename = filename
    f.content_type = content_type
    f.read.return_value = open(
        Path(__file__).parent / '_sample_leaf.jpg', 'rb'
    ).read() if (Path(__file__).parent / '_sample_leaf.jpg').exists() else b''
    return f


class TestDiseaseServiceValidation:
    def test_no_file_returns_error(self):
        err = DiseaseService._validate_file(None)
        assert err is not None
        assert not err['success']

    def test_empty_filename_returns_error(self):
        f = MagicMock()
        f.filename = ''
        err = DiseaseService._validate_file(f)
        assert err is not None

    def test_non_image_mime_returns_error(self):
        f = MagicMock()
        f.filename = 'doc.pdf'
        f.content_type = 'application/pdf'
        err = DiseaseService._validate_file(f)
        assert err is not None

    def test_valid_file_passes_validation(self):
        f = MagicMock()
        f.filename = 'leaf.jpg'
        f.content_type = 'image/jpeg'
        err = DiseaseService._validate_file(f)
        assert err is None


class TestDiseaseServiceQuality:
    def test_tiny_image_rejected(self):
        from PIL import Image
        tiny = Image.new('RGB', (32, 32))
        err = DiseaseService._check_quality(tiny)
        assert err is not None

    def test_normal_image_passes(self):
        from PIL import Image
        ok = Image.new('RGB', (224, 224))
        err = DiseaseService._check_quality(ok)
        assert err is None
