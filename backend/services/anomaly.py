"""
services/anomaly.py
Hybrid adaptive anomaly detection on STL residuals:
  1. MAD  (Median Absolute Deviation) — point anomalies
  2. RoC  (Rate of Change threshold)  — contextual anomalies
  3. Adaptive CUSUM                   — collective anomalies

STL decomposition removes trend + seasonality first.
All thresholds data-derived. Zero hardcoded parameters for MAD/CUSUM.
RoC uses fixed ±2.0 mm/sample per Chandola taxonomy.

Enhanced with:
  - 7-class anomaly classification (Chandola et al. 2009)
  - Confidence tiering (log → dashboard → alert → critical)
  - Alert suppression (5-hit cooldown)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ── Anomaly classification labels ────────────────────────────────────────────
ANOMALY_CLASSES = [
    "normal",
    "sensor_freeze",
    "sensor_spike",
    "overflow",
    "sudden_drain_theft",
    "refill_event",
    "slow_leak",
    "unclassified_anomaly",
]

# ── Detection thresholds ─────────────────────────────────────────────────────
ROC_THRESHOLD = 2.0   # mm/sample — per Chandola taxonomy

# ── Confidence tiers ─────────────────────────────────────────────────────────
def confidence_tier(score: float) -> str:
    """Map a 0-1 confidence score to a human-readable tier."""
    if score < 0.30:
        return "log"
    elif score < 0.50:
        return "dashboard"
    elif score < 0.70:
        return "alert"
    else:
        return "critical"


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


def classify_anomaly(
    is_anomaly: bool,
    mad_anomaly: bool,
    roc_anomaly: bool,
    cusum_anomaly: bool,
    distance_mm: float = 0.0,
    roc: float = 0.0,
    recent_std: float = 0.0,
    tank_full_mm: float = 35.0,
    tank_empty_mm: float = 395.0,
) -> str:
    """
    Classify an anomaly into one of 7 categories based on Chandola et al. (2009)
    anomaly taxonomy for IoT liquid tank monitoring.

    Three detector flags + contextual features → classification.

    Categories:
      POINT ANOMALY
        sensor_spike        — Isolated outlier from HC-SR04 echo noise
        sensor_freeze       — Sensor stuck (collective, but rule-based)
      CONTEXTUAL ANOMALY
        sudden_drain_theft  — Rapid unexpected level drop (theft/valve failure)
        overflow            — Tank near capacity (distance < 30mm)
        refill_event        — Rapid intentional filling
      COLLECTIVE ANOMALY
        slow_leak           — Gradual persistent drift via CUSUM
    """
    if not is_anomaly:
        return "normal"

    # ── COLLECTIVE: sensor_freeze ─────────────────────────────────────────
    # std(last 20 readings) < 0.2mm → hardware malfunction / stuck sensor
    if recent_std < 0.2:
        return "sensor_freeze"

    # ── POINT: sensor_spike ───────────────────────────────────────────────
    # MAD fires alone (isolated outlier), neither RoC nor CUSUM triggered
    if mad_anomaly and not cusum_anomaly and not roc_anomaly:
        return "sensor_spike"

    # ── CONTEXTUAL: overflow ──────────────────────────────────────────────
    # Distance < TANK_FULL_MM → liquid surface hitting the sensor boundary
    if distance_mm < tank_full_mm:
        return "overflow"

    # ── CONTEXTUAL: sudden_drain_theft ────────────────────────────────────
    # Distance increasing rapidly (RoC > +2.0 mm/sample) → water dropping
    if roc > ROC_THRESHOLD:
        return "sudden_drain_theft"

    # ── CONTEXTUAL: refill_event ──────────────────────────────────────────
    # Distance decreasing rapidly (RoC < -2.0 mm/sample) → water rising
    if roc < -ROC_THRESHOLD:
        return "refill_event"

    # ── COLLECTIVE: slow_leak ─────────────────────────────────────────────
    # CUSUM accumulates deviations but individual RoC < 1.5 mm/sample
    if cusum_anomaly and abs(roc) < 1.5:
        return "slow_leak"

    return "unclassified_anomaly"


class AnomalyDetector:
    """
    Stateful hybrid anomaly detector with 3-method voting + alert suppression.

    Detection pipeline (applied to STL residuals):
      1. MAD   — |residual - center| > adaptive threshold (99.5th %ile)
      2. RoC   — |rate of change| > 2.0 mm/sample (Chandola taxonomy)
      3. CUSUM — cumulative sum exceeds adaptive h (99th %ile of cumdev)

    is_anomaly = MAD OR RoC OR CUSUM
    confidence = n_agree / 3  (voting)

    Alert suppression:
      After SUPPRESSION_LIMIT consecutive alerts of the SAME class,
      that class is suppressed until RECOVERY_COUNT normal readings.
    """

    SUPPRESSION_LIMIT = 5
    RECOVERY_COUNT    = 3

    def __init__(self, params: dict):
        self.center        = params["center"]
        self.mad           = params["mad"]
        self.mad_threshold = params["mad_threshold"]
        self.cusum_k       = params["cusum_k"]
        self.cusum_h       = params["cusum_h"]

        # CUSUM state
        self._cs_pos = 0.0
        self._cs_neg = 0.0

        # Alert suppression state
        self._last_class       = "normal"
        self._consecutive      = 0
        self._suppressed_class = None
        self._normal_streak    = 0

    def update(
        self,
        residual: float,
        distance_mm: float = 0.0,
        roc: float = 0.0,
        recent_std: float = 0.0,
        tank_full_mm: float = 35.0,
        tank_empty_mm: float = 395.0,
    ) -> dict:
        """
        Process a single new residual value.
        Returns full anomaly assessment with classification, tier,
        3-detector voting, and suppression status.
        """
        dev = residual - self.center
        abs_dev = abs(dev)

        # ── Detector 1: MAD ──────────────────────────────────────────────────
        if self.mad > 1e-9:
            mad_z = abs_dev / (self.mad * 1.4826)
        else:
            mad_z = 0.0
        mad_anomaly = abs_dev > self.mad_threshold

        # ── Detector 2: RoC threshold ────────────────────────────────────────
        roc_anomaly = abs(roc) > ROC_THRESHOLD

        # ── Detector 3: Adaptive CUSUM ───────────────────────────────────────
        self._cs_pos = max(0.0, self._cs_pos + dev - self.cusum_k)
        self._cs_neg = min(0.0, self._cs_neg + dev + self.cusum_k)
        cusum_anomaly = (self._cs_pos > self.cusum_h or abs(self._cs_neg) > self.cusum_h)

        if cusum_anomaly:
            self._cs_pos = 0.0   # reset after detection
            self._cs_neg = 0.0

        # ── 3-method voting ──────────────────────────────────────────────────
        n_agree = sum([mad_anomaly, roc_anomaly, cusum_anomaly])
        is_anomaly = n_agree >= 1   # ANY detector fires

        # ── Confidence score (voting-based, 0-1) ─────────────────────────────
        conf_score = round(n_agree / 3.0, 3) if is_anomaly else 0.0

        # ── Classification ───────────────────────────────────────────────────
        raw_class = classify_anomaly(
            is_anomaly=is_anomaly,
            mad_anomaly=mad_anomaly,
            roc_anomaly=roc_anomaly,
            cusum_anomaly=cusum_anomaly,
            distance_mm=distance_mm,
            roc=roc,
            recent_std=recent_std,
            tank_full_mm=tank_full_mm,
            tank_empty_mm=tank_empty_mm,
        )

        # ── Alert suppression ────────────────────────────────────────────────
        suppressed = False

        if raw_class == "normal":
            self._normal_streak += 1
            if self._normal_streak >= self.RECOVERY_COUNT and self._suppressed_class:
                self._suppressed_class = None
            self._consecutive = 0
            self._last_class = "normal"
        else:
            self._normal_streak = 0

            if raw_class == self._last_class:
                self._consecutive += 1
            else:
                self._consecutive = 1
                self._last_class = raw_class

            # Refill events are expected operations, so we suppress them very aggressively
            # (after 2 hits) compared to real anomalies like theft or leakage.
            dynamic_limit = 2 if raw_class == "refill_event" else self.SUPPRESSION_LIMIT

            if self._consecutive >= dynamic_limit:
                self._suppressed_class = raw_class

            if self._suppressed_class and raw_class == self._suppressed_class:
                suppressed = True
                is_anomaly = False
                conf_score = 0.0
                raw_class = "normal"

        # ── Tier ─────────────────────────────────────────────────────────────
        if raw_class == "refill_event":
            # Force refill events to the lowest tier ("log") so they don't trigger critical UI alerts
            conf_score = min(conf_score, 0.25)
            
        conf_tier = confidence_tier(conf_score)

        return {
            "is_anomaly":     is_anomaly,
            "mad_z":          round(mad_z, 3),
            "mad_anomaly":    mad_anomaly,
            "roc_anomaly":    roc_anomaly,
            "cusum_anomaly":  cusum_anomaly,
            "n_agree":        n_agree,
            "cusum_pos":      round(self._cs_pos, 4),
            "cusum_neg":      round(self._cs_neg, 4),
            "conf_score":     conf_score,
            "conf_tier":      conf_tier,
            "anomaly_class":  raw_class,
            "suppressed":     suppressed,
        }

    def batch_score(self, residuals: list[float]) -> list[dict]:
        """Score a list of historical residuals in order."""
        return [self.update(r) for r in residuals]

    def reset_cusum(self):
        self._cs_pos = 0.0
        self._cs_neg = 0.0

    def reset_suppression(self):
        """Fully reset the alert suppression state."""
        self._last_class       = "normal"
        self._consecutive      = 0
        self._suppressed_class = None
        self._normal_streak    = 0
