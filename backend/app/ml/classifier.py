"""CICIDS2017 attack classifier with model registry and explainability."""
from __future__ import annotations

import logging
import os
import pickle
from typing import Optional

import numpy as np

from app.config import settings
from app.ml.features import CICIDS2017_FEATURES, ATTACK_CLASSES, SEVERITY_MAP

logger = logging.getLogger(__name__)


class AttackClassifier:
    """Loads a pre-trained sklearn pipeline and classifies network flows."""

    def __init__(self):
        self._model = None
        self._scaler = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if os.path.exists(settings.ML_MODEL_PATH):
                with open(settings.ML_MODEL_PATH, "rb") as f:
                    self._model = pickle.load(f)
                logger.info("ML model loaded from %s", settings.ML_MODEL_PATH)
            else:
                logger.warning("ML model not found at %s — using heuristic fallback", settings.ML_MODEL_PATH)
        except Exception as exc:
            logger.error("Failed to load ML model: %s", exc)
        self._loaded = True

    def _features_to_vector(self, features: dict) -> np.ndarray:
        vec = [float(features.get(f) or 0.0) for f in CICIDS2017_FEATURES]
        return np.array(vec, dtype=np.float32).reshape(1, -1)

    def predict(self, features: dict) -> dict:
        """
        Returns:
            {
                "attack_category": str,
                "confidence": float,
                "severity": str,
                "needs_review": bool,
                "probabilities": dict[str, float],
                "top_features": list[dict],
            }
        """
        self._load()

        if self._model is not None:
            return self._predict_model(features)
        return self._heuristic_predict(features)

    def _predict_model(self, features: dict) -> dict:
        vec = self._features_to_vector(features)
        try:
            probas = self._model.predict_proba(vec)[0]
            class_idx = int(np.argmax(probas))
            confidence = float(probas[class_idx])
            attack_category = ATTACK_CLASSES[class_idx] if class_idx < len(ATTACK_CLASSES) else "Unknown"
            proba_map = {
                ATTACK_CLASSES[i]: float(probas[i])
                for i in range(min(len(ATTACK_CLASSES), len(probas)))
            }
        except Exception as exc:
            logger.error("Model prediction failed: %s", exc)
            return self._heuristic_predict(features)

        top_features = self._compute_top_features(vec[0], features)

        return {
            "attack_category": attack_category,
            "confidence": confidence,
            "severity": SEVERITY_MAP.get(attack_category, "medium"),
            "needs_review": confidence < settings.ML_CONFIDENCE_THRESHOLD,
            "probabilities": proba_map,
            "top_features": top_features,
            "model_version": settings.ML_MODEL_VERSION,
        }

    def _heuristic_predict(self, features: dict) -> dict:
        """Simple rule-based fallback when model is unavailable."""
        dst_port = features.get("destination_port", 0) or 0
        syn_flags = features.get("syn_flag_count", 0) or 0
        flow_duration = features.get("flow_duration", 0) or 0
        pkt_rate = features.get("flow_packets_per_sec", 0) or 0

        if pkt_rate > 10000:
            category = "DDoS"
        elif syn_flags > 1000:
            category = "DoS Hulk"
        elif dst_port == 21:
            category = "FTP-Patator"
        elif dst_port == 22:
            category = "SSH-Patator"
        elif dst_port in (80, 443, 8080):
            category = "Web Attack - Brute Force"
        else:
            category = "BENIGN"

        confidence = 0.65  # Heuristic confidence always below threshold
        return {
            "attack_category": category,
            "confidence": confidence,
            "severity": SEVERITY_MAP.get(category, "medium"),
            "needs_review": True,
            "probabilities": {category: confidence, "BENIGN": 1 - confidence},
            "top_features": [
                {"feature": "destination_port", "value": dst_port, "importance": 0.3},
                {"feature": "syn_flag_count", "value": syn_flags, "importance": 0.25},
                {"feature": "flow_packets_per_sec", "value": pkt_rate, "importance": 0.2},
            ],
            "model_version": "heuristic-fallback",
        }

    def _compute_top_features(self, vec: np.ndarray, features: dict, top_n: int = 10) -> list[dict]:
        """Return top contributing features by absolute value (simple explainability)."""
        sorted_idx = np.argsort(np.abs(vec))[::-1][:top_n]
        return [
            {
                "feature": CICIDS2017_FEATURES[i],
                "value": float(vec[i]),
                "importance": float(np.abs(vec[i]) / (np.sum(np.abs(vec)) + 1e-9)),
            }
            for i in sorted_idx
            if i < len(CICIDS2017_FEATURES)
        ]


classifier = AttackClassifier()
