# PikDrishti AI — Disease Dataset

## Source
The model is designed to work with the **PlantVillage** dataset, which provides
labelled plant leaf images across 38 disease/healthy classes.

**Download:**
- Kaggle: https://www.kaggle.com/datasets/emmarex/plantdisease
- Or directly from: https://github.com/spMohanty/PlantVillage-Dataset

The initial training configuration targets the following 6 classes:

| Class Directory              | Crop   | Condition     |
|------------------------------|--------|---------------|
| `Tomato___Healthy`           | Tomato | Healthy       |
| `Tomato___Early_Blight`      | Tomato | Early Blight  |
| `Tomato___Late_Blight`       | Tomato | Late Blight   |
| `Potato___Healthy`           | Potato | Healthy       |
| `Potato___Early_Blight`      | Potato | Early Blight  |
| `Potato___Late_Blight`       | Potato | Late Blight   |

---

## Expected Folder Structure

After downloading, place images under:

```
ml/disease/dataset/raw/
├── Tomato___Healthy/
│   ├── image_001.jpg
│   └── ...
├── Tomato___Early_Blight/
├── Tomato___Late_Blight/
├── Potato___Healthy/
├── Potato___Early_Blight/
└── Potato___Late_Blight/
```

The `split_dataset.py` script will automatically generate `train/`, `validation/`
and `test/` directories from `raw/`.

---

## Split Ratios
| Split      | Percentage |
|------------|------------|
| Train      | 70%        |
| Validation | 15%        |
| Test       | 15%        |

---

## License / Usage
PlantVillage data is released under the **CC0: Public Domain** license.
See: https://creativecommons.org/publicdomain/zero/1.0/

---

## Known Limitations
1. PlantVillage images are captured in laboratory/controlled conditions.
2. Real farmer images may differ in lighting, background, camera angle, and disease stage.
3. Benchmark accuracy does **not** equal real-world accuracy.
4. The confidence threshold (default 0.70) should be calibrated on real field images.
5. Additional crops and diseases require retraining or fine-tuning the model.

---

## Adding New Classes
1. Create a new subdirectory under `ml/disease/dataset/raw/` using the naming convention:
   `CropName___DiseaseName` (three underscores as separator).
2. Add at least 50–100 images per class.
3. Re-run `split_dataset.py`, `train.py`, and `evaluate.py`.
4. Copy the new `disease_model.keras` to `models/` and restart Flask.
