"""
services/analysis.py
Unified analyze_tank_data() function.
Pipeline: STL decomposition → MAD + RoC + Adaptive CUSUM → classification → tier.
"""

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

from services.stl import compute_stl, resample_for_stl
from services.roc import compute_roc
from services.anomaly import fit_anomaly_params, AnomalyDetector, classify_anomaly, ROC_THRESHOLD
from services.flow import compute_flow_rate, compute_flow_summary

TANK_EMPTY_MM = 395  # Tank empty distance (0%)
TANK_FULL_MM  = 35   # Tank full distance (100%)


def get_hourly_summary(df: pd.DataFrame) -> list[dict]:
    """Return last 24 hours of hourly-averaged readings."""
    df = df.copy()
    df["hour_bucket"] = df["timestamp"].dt.floor("1h")
    summary = (
        df.groupby("hour_bucket")["distance"]
        .agg(["mean", "min", "max", "count"])
        .reset_index()
        .tail(24)
    )
    return [
        {
            "hour":  row["hour_bucket"].strftime("%H:%M"),
            "mean":  round(row["mean"], 2),
            "min":   round(row["min"],  2),
            "max":   round(row["max"],  2),
            "count": int(row["count"]),
        }
        for _, row in summary.iterrows()
    ]


def analyze_tank_data(df: pd.DataFrame) -> dict:
    """
    Full pipeline analysis on a DataFrame with columns:
        timestamp (datetime), distance (float, mm from sensor to surface)

    Returns comprehensive analysis dict.
    """
    df = df.copy().sort_values("timestamp").reset_index(drop=True)
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
    df = df.dropna(subset=["distance"])

    if len(df) < 10:
        return {"error": "Insufficient data"}

    values = df["distance"].tolist()

    # ── 1. Current level ──────────────────────────────────────────────────────
    current_distance = float(values[-1])
    water_level_pct  = max(0.0, min(100.0, ((TANK_EMPTY_MM - current_distance) / (TANK_EMPTY_MM - TANK_FULL_MM)) * 100))

    # ── 2. ROC ────────────────────────────────────────────────────────────────
    window = min(30, len(values))
    roc_result = compute_roc(values[-window:])

    # ── 3. Flow analysis ──────────────────────────────────────────────────────
    flow_result = compute_flow_summary(values[-60:], TANK_EMPTY_MM, TANK_FULL_MM)

    # ── 4. STL decomposition ──────────────────────────────────────────────────
    ts_hourly = resample_for_stl(df)
    stl_result = None
    anomaly_detector = None
    anomalies_historical = []

    if ts_hourly is not None and len(ts_hourly) >= 48:
        period = min(24, len(ts_hourly) // 2)
        stl_result = compute_stl(ts_hourly, period=period)

        if stl_result:
            params = fit_anomaly_params(stl_result["resid"])
            anomaly_detector = AnomalyDetector(params)

            # Compute recent std for classification context
            recent_std = float(np.std(values[-20:])) if len(values) >= 20 else 0.0

            # Compute per-point RoC on residuals for the RoC detector
            resid_arr = np.array(stl_result["resid"])
            roc_per_point = np.gradient(resid_arr)

            scores = []
            for i, resid_val in enumerate(stl_result["resid"]):
                roc_val = float(roc_per_point[i])
                s = anomaly_detector.update(
                    resid_val,
                    distance_mm=stl_result["original"][i],
                    roc=roc_val,
                    recent_std=recent_std,
                    tank_full_mm=TANK_FULL_MM,
                    tank_empty_mm=TANK_EMPTY_MM,
                )
                scores.append(s)

            # Collect anomalies
            for i, s in enumerate(scores):
                if s["is_anomaly"]:
                    anomalies_historical.append({
                        "index":         i,
                        "date":          stl_result["dates"][i],
                        "value":         stl_result["original"][i],
                        "anomaly_class": s["anomaly_class"],
                        "conf_score":    s["conf_score"],
                        "conf_tier":     s["conf_tier"],
                        "mad_z":         s["mad_z"],
                        "n_agree":       s["n_agree"],
                        "roc_anomaly":   s["roc_anomaly"],
                        "cusum_anomaly": s["cusum_anomaly"],
                        "mad_anomaly":   s["mad_anomaly"],
                    })

            # Reset for live use
            anomaly_detector.reset_cusum()
            anomaly_detector.reset_suppression()

    # ── 5. Hourly summary ─────────────────────────────────────────────────────
    hourly_summary = get_hourly_summary(df)

    # ── 6. Insights ───────────────────────────────────────────────────────────
    insights = []
    if len(anomalies_historical) > 0:
        insights.append(f"{len(anomalies_historical)} anomalous periods detected in historical data")
    if roc_result["state"] == "Emptying" and abs(roc_result["roc"]) > roc_result["noise_floor"] * 3:
        insights.append("Rapid level drop detected — possible leak or heavy usage")
    if water_level_pct < 15:
        insights.append("Critical: tank below 15% capacity")
    elif water_level_pct < 30:
        insights.append("Warning: tank below 30% capacity")

    # Flow-based insights
    if flow_result.get("flow_direction") == "draining" and flow_result.get("trend") == "accelerating":
        insights.append("Drain rate is accelerating — monitor closely")
    if flow_result.get("est_time_to_empty"):
        insights.append(f"Estimated time to empty: {flow_result['est_time_to_empty']}")

    # Anomaly class breakdown
    class_counts = {}
    for a in anomalies_historical:
        cls = a.get("anomaly_class", "unclassified")
        class_counts[cls] = class_counts.get(cls, 0) + 1
    if class_counts:
        top_class = max(class_counts, key=class_counts.get)
        insights.append(f"Most common anomaly type: {top_class} ({class_counts[top_class]} events)")

    return {
        "current_level": {
            "distance_mm":     round(current_distance, 2),
            "water_level_pct": round(water_level_pct, 1),
            "timestamp":       df["timestamp"].iloc[-1].isoformat(),
        },
        "roc_state":       roc_result,
        "flow":            flow_result,
        "stl":             stl_result,
        "anomalies":       anomalies_historical,
        "hourly_summary":  hourly_summary,
        "insights":        insights,
        "_detector":       anomaly_detector,   # live use — not serialised
    }
