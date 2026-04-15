"""
services/analysis.py
Unified analyze_tank_data() function.
"""

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

from services.stl import compute_stl, resample_for_stl
from services.roc import compute_roc
from services.anomaly import fit_anomaly_params, AnomalyDetector
from services.forecast import train_prophet, get_hourly_summary

TANK_HEIGHT_MM = 240  # 24 cm


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
    water_level_pct  = max(0.0, min(100.0, (1 - current_distance / TANK_HEIGHT_MM) * 100))

    # ── 2. ROC ────────────────────────────────────────────────────────────────
    window = min(30, len(values))
    roc_result = compute_roc(values[-window:])

    # ── 3. STL decomposition ──────────────────────────────────────────────────
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
            scores = anomaly_detector.batch_score(stl_result["resid"])
            anomalies_historical = [
                {"index": i, "date": stl_result["dates"][i], "value": stl_result["original"][i]}
                for i, s in enumerate(scores)
                if s["is_anomaly"]
            ]
            # Reset CUSUM for live use
            anomaly_detector.reset_cusum()

    # ── 4. Prophet forecast ───────────────────────────────────────────────────
    prophet_df = df.rename(columns={"timestamp": "ds", "distance": "y"})
    forecast_result = None
    insights = []
    try:
        forecast_result = train_prophet(prophet_df, horizon_hours=24)
        insights = forecast_result.pop("model", None) and forecast_result.get("insights", [])
        insights = forecast_result.get("insights", [])
    except Exception as e:
        insights = [f"Forecast unavailable: {str(e)[:60]}"]

    # ── 5. Hourly summary ─────────────────────────────────────────────────────
    hourly_summary = get_hourly_summary(df)

    # ── 6. Additional insights ────────────────────────────────────────────────
    if len(anomalies_historical) > 3:
        insights.append(f"⚠ {len(anomalies_historical)} anomalous periods detected in dataset")
    if roc_result["state"] == "Emptying" and abs(roc_result["roc"]) > roc_result["noise_floor"] * 3:
        insights.append("⚠ Rapid level drop — possible leak or heavy usage")
    if water_level_pct < 15:
        insights.append("🔴 Critical: tank below 15% capacity")
    elif water_level_pct < 30:
        insights.append("🟡 Warning: tank below 30% capacity")

    return {
        "current_level": {
            "distance_mm":   round(current_distance, 2),
            "water_level_pct": round(water_level_pct, 1),
            "timestamp":     df["timestamp"].iloc[-1].isoformat(),
        },
        "roc_state":  roc_result,
        "stl":        stl_result,
        "anomalies":  anomalies_historical,
        "forecast":   forecast_result,
        "hourly_summary": hourly_summary,
        "insights":   insights,
        "_detector":  anomaly_detector,   # live use — not serialised
    }
