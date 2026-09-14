"""Structured integrated pest and disease management recommendations."""
from __future__ import annotations

import re
from typing import Any


class IPMService:
    """Build conservative, actionable IPM plans from a disease prediction."""

    _DISEASE_RULES = {
        "early blight": {
            "risk": "Fungal disease pressure can increase with leaf wetness and poor airflow.",
            "cultural": [
                "Improve airflow by spacing plants and removing dense lower foliage.",
                "Use drip irrigation or water at the soil line; avoid wetting leaves.",
                "Rotate away from solanaceous crops where practical.",
            ],
            "mechanical": [
                "Remove heavily affected leaves and place them in sealed waste; do not compost infected tissue.",
                "Disinfect cutting tools after working on affected plants.",
            ],
            "biological": [
                "Consider a locally approved Trichoderma or Bacillus-based product according to its label.",
            ],
            "chemical": [
                "If disease is spreading, consult the local agriculture officer for a crop-approved fungicide.",
                "Rotate fungicide groups and follow the product label, pre-harvest interval, and re-entry period.",
            ],
            "monitoring": [
                "Inspect lower leaves every 2 to 3 days and record new lesions.",
                "Repeat a clear scan after 5 to 7 days or sooner if symptoms spread rapidly.",
            ],
        },
        "late blight": {
            "risk": "Cool, wet conditions can cause rapid spread and require frequent scouting.",
            "cultural": [
                "Keep foliage dry, improve field drainage, and avoid dense canopy conditions.",
                "Remove volunteer potato or tomato plants that may carry infection.",
            ],
            "mechanical": [
                "Isolate and remove plants with rapidly expanding lesions; bag infected material before disposal.",
                "Clean tools, footwear, and harvest containers after entering an affected block.",
            ],
            "biological": [
                "Use only locally approved biological protectants as part of an extension-led program.",
            ],
            "chemical": [
                "Seek same-day extension guidance when lesions are expanding quickly or weather is persistently wet.",
                "Use only a crop-approved, label-directed product and rotate modes of action.",
            ],
            "monitoring": [
                "Scout the crop daily during wet or cool weather and record affected plants by block.",
                "Re-scan after intervention and escalate if new lesions appear within 48 hours.",
            ],
        },
        "bacterial spot": {
            "risk": "Splashing water and contaminated tools can move bacterial lesions between plants.",
            "cultural": [
                "Use clean planting material and avoid overhead irrigation.",
                "Improve drainage and remove volunteer plants and crop debris after harvest.",
            ],
            "mechanical": [
                "Remove the most affected leaves when practical and avoid handling plants while foliage is wet.",
                "Sanitize tools and hands between healthy and affected rows.",
            ],
            "biological": [
                "Ask an extension officer about registered biological or copper-compatible options for the crop.",
            ],
            "chemical": [
                "Do not apply an unverified antibiotic or pesticide; use only locally registered products on the label.",
                "Follow resistance-management guidance and observe the stated harvest interval.",
            ],
            "monitoring": [
                "Mark affected rows and check for new spots twice weekly.",
                "Capture a follow-up image if lesions move to new leaves or fruit.",
            ],
        },
        "leaf mold": {
            "risk": "High humidity and poor ventilation can favor leaf mold development.",
            "cultural": [
                "Increase ventilation, avoid overcrowding, and keep greenhouse or field foliage dry.",
                "Remove crop debris and manage irrigation timing to reduce overnight humidity.",
            ],
            "mechanical": [
                "Remove infected lower leaves and dispose of them away from the production area.",
                "Clean supports and tools before moving to another crop block.",
            ],
            "biological": [
                "Use a registered biological fungicide only when recommended for the crop and disease.",
            ],
            "chemical": [
                "Confirm the diagnosis with an extension worker before applying a fungicide.",
                "Use label-approved products and rotate modes of action to slow resistance.",
            ],
            "monitoring": [
                "Check leaf undersides and humidity-prone areas every 2 to 3 days.",
                "Repeat the scan after environmental conditions improve.",
            ],
        },
    }

    @staticmethod
    def _normalise(value: Any) -> str:
        value = str(value or "").lower().replace("_", " ")
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _rule_for(cls, disease: Any) -> tuple[str, dict]:
        normalised = cls._normalise(disease)
        for key, rule in cls._DISEASE_RULES.items():
            if key in normalised:
                return key, rule
        return "general", {
            "risk": "The diagnosis needs field confirmation before a crop-protection decision is made.",
            "cultural": [
                "Maintain field sanitation, balanced nutrition, and adequate drainage.",
                "Avoid routine pesticide application without confirming the cause of symptoms.",
            ],
            "mechanical": [
                "Remove only clearly affected plant material and dispose of it safely.",
                "Clean tools and avoid spreading plant material between blocks.",
            ],
            "biological": [
                "Ask an extension officer about crop-specific biological control options.",
            ],
            "chemical": [
                "Do not spray until the diagnosis and crop label are confirmed.",
                "If treatment is required, use only a locally registered product exactly as labelled.",
            ],
            "monitoring": [
                "Record the affected area and inspect again within 3 days.",
                "Request expert or laboratory confirmation if symptoms spread or remain unclear.",
            ],
        }

    @classmethod
    def build_plan(
        cls,
        crop: Any = None,
        disease: Any = None,
        confidence: Any = None,
        severity: Any = None,
    ) -> dict:
        """Return a structured IPM plan safe for API and template consumption."""
        disease_name, rule = cls._rule_for(disease)
        try:
            confidence_value = round(float(confidence), 3) if confidence is not None else None
        except (TypeError, ValueError):
            confidence_value = None

        uncertain = confidence_value is not None and confidence_value < 0.70
        healthy = "healthy" in cls._normalise(disease)
        needs_referral = uncertain or disease_name == "general" or not disease or healthy
        risk = rule["risk"]

        if healthy:
            risk = "Healthy scan; continue routine scouting and preventive crop care."
            referral = ["Seek expert review if visible symptoms continue despite a healthy scan."]
        elif needs_referral:
            referral = [
                "Request extension or laboratory confirmation before using a curative pesticide.",
                "Take a well-lit close-up and a whole-plant image if symptoms continue.",
            ]
        else:
            referral = [
                "Contact an extension officer if the affected area increases, fruit or tubers are affected, or treatment fails.",
            ]

        plan = {
            "version": "1.0",
            "crop": crop or "Unknown crop",
            "disease": disease or "Unconfirmed condition",
            "confidence": confidence_value,
            "severity": severity or "Unclassified",
            "risk_summary": risk,
            "cultural": rule["cultural"],
            "mechanical": rule["mechanical"],
            "biological": rule["biological"],
            "chemical": rule["chemical"],
            "monitoring": rule["monitoring"],
            "referral": referral,
            "safety": [
                "Read the registered product label and follow crop, dosage, re-entry, and pre-harvest instructions.",
                "Wear the label-required protective equipment and keep people and animals away during spraying.",
                "Never mix products unless the label or a qualified agriculture professional explicitly permits it.",
            ],
            "requires_confirmation": needs_referral,
        }

        if healthy:
            plan["chemical"] = [
                "Do not apply a pesticide for a healthy scan; investigate visible symptoms before spraying.",
            ]

        return plan
