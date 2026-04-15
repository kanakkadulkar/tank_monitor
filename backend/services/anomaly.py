"""
services/anomaly.py
Hybrid adaptive anomaly detection: STL-Residual MAD + Adaptive CUSUM.
Zero fixed thresholds — everything derived from data quantiles / MAD.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CUSUMState:
    pos: float = 0.0
    neg: float = 0.0
    k:   float = 0.0      # allowance = MAD of training residuals
    h:   float = 0.0      # threshold = quantile of cumulative deviations
    hits: list = field(default_factory=list)


def mad_score(values: list[float], center: Optional[float] = None) -> np.ndarray:
    """Return MAD-normalised scores: |x - median| / MAD."""
    arr = np.array(values, dtype=float)
    if center is None:
        center = float(np.median(arr))
    mad = float(np.median(np.abs(arr - center)))
    if mad < 1e-9:
        return np.zeros_like(arr)
    return np.abs(arr - center) / (mad * 1.4826)   # 1.4826 → consistent estimator


def fit_anomaly_params(residuals: list[float]) -> dict:
    """
    Derive adaptive anomaly detection parameters from historical residuals.
    Called once after STL decomposition of training data.
    """
    arr = np.array(residuals, dtype=float)
    center = float(np.median(arr))
    mad = float(np.median(np.abs(arr - center)))

    # MAD threshold = 99.5th quantile of absolute deviations (adaptive)
    mad_threshold = float(np.quantile(np.abs(arr - center), 0.995))

    # CUSUM allowance k = MAD (sensitivity tuned to data noise)
    cusum_k = mad if mad > 0 else float(np.std(arr)) * 0.5

    # CUSUM threshold h = 99th quantile of cumulative absolute deviations
    cumdev = np.cumsum(np.abs(arr - center))
    cusum_h = float(np.quantile(cumdev, 0.99)) if len(cumdev) > 1 else cusum_k * 5

    return {
        "center":        center,
        "mad":           mad,
        "mad_threshold": mad_threshold,
        "cusum_k":       cusum_k,
        "cusum_h":       cusum_h,
    }


class AnomalyDetector:
    """
    Stateful hybrid anomaly detector.
    Initialise with fit_params from fit_anomaly_params().
    """

    def __init__(self, params: dict):
        self.center        = params["center"]
        self.mad           = params["mad"]
        self.mad_threshold = params["mad_threshold"]
        self.cusum_k       = params["cusum_k"]
        self.cusum_h       = params["cusum_h"]

        # CUSUM state
        self._cs_pos = 0.0
        self._cs_neg = 0.0

    def update(self, residual: float) -> dict:
        """
        Process a single new residual value.
        Returns anomaly assessment dict.
        """
        dev = residual - self.center
        abs_dev = abs(dev)

        # ── MAD score ────────────────────────────────────────────────────────
        if self.mad > 1e-9:
            mad_z = abs_dev / (self.mad * 1.4826)
        else:
            mad_z = 0.0
        mad_anomaly = abs_dev > self.mad_threshold

        # ── Adaptive CUSUM ───────────────────────────────────────────────────
        self._cs_pos = max(0.0, self._cs_pos + dev - self.cusum_k)
        self._cs_neg = min(0.0, self._cs_neg + dev + self.cusum_k)
        cusum_anomaly = (self._cs_pos > self.cusum_h or abs(self._cs_neg) > self.cusum_h)

        if cusum_anomaly:
            self._cs_pos = 0.0   # reset after detection
            self._cs_neg = 0.0

        # ── Hybrid decision ──────────────────────────────────────────────────
        is_anomaly = mad_anomaly or cusum_anomaly

        return {
            "is_anomaly":    is_anomaly,
            "mad_z":         round(mad_z, 3),
            "mad_anomaly":   mad_anomaly,
            "cusum_anomaly": cusum_anomaly,
            "cusum_pos":     round(self._cs_pos, 4),
            "cusum_neg":     round(self._cs_neg, 4),
        }

    def batch_score(self, residuals: list[float]) -> list[dict]:
        """Score a list of historical residuals in order."""
        return [self.update(r) for r in residuals]

    def reset_cusum(self):
        self._cs_pos = 0.0
        self._cs_neg = 0.0
