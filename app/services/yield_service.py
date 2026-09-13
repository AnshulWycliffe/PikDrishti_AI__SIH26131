import os
from flask import current_app

class YieldPredictionService:
    @staticmethod
    def predict(farm_area, crop_name, disease_severity=None):
        """
        Predict crop yield based on farm and crop parameters.
        In DEMO_MODE, returns deterministic dummy results based on area and disease.
        """
        # Ensure area is a float
        try:
            area = float(farm_area)
        except (ValueError, TypeError):
            return {"success": False, "error": "Invalid farm area."}
            
        if not current_app.config.get('DEMO_MODE'):
            # Baseline expected yield per acre (in tonnes) for standard crops
            baselines = {
                'Tomato': 3.8,
                'Rice': 2.5,
                'Wheat': 1.8,
                'Maize': 4.0,
                'Potato': 8.0,
                'Pepper': 2.2
            }
            
            # Default to 3.0 if crop not in baselines
            base_yield = baselines.get(crop_name, 3.0)
            
            # Apply penalty if disease severity is given
            penalty = 0.0
            if disease_severity:
                sev = disease_severity.lower()
                if sev == 'mild' or sev == 'हल्का':
                    penalty = 0.10
                elif sev == 'moderate' or sev == 'मध्यम':
                    penalty = 0.30
                elif sev == 'severe' or sev == 'गंभीर':
                    penalty = 0.60
                    
            final_yield_per_acre = base_yield * (1.0 - penalty)
            total_yield = final_yield_per_acre * area
            potential_total = base_yield * area
            loss_tonnes = potential_total - total_yield
            
            return {
                "success": True,
                "yield_per_acre": round(final_yield_per_acre, 2),
                "total_yield": round(total_yield, 2),
                "base_yield_per_acre": round(base_yield, 2),
                "potential_total_yield": round(potential_total, 2),
                "penalty_percent": int(penalty * 100),
                "loss_tonnes": round(loss_tonnes, 2),
                "unit": "टन",
                "penalty_applied": penalty > 0
            }
            
        # Real ML inference would go here using scikit-learn / XGBoost
        return {"success": False, "error": "Production yield model not yet implemented. Enable DEMO_MODE."}
