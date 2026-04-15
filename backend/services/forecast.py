"""
services/forecast.py
Prophet-based forecasting + STL trend extraction.
"""

import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def train_prophet(df: pd.DataFrame, horizon_hours: int = 24) -> dict:
    """
    Train Prophet on cleaned data and return forecast.

    df must have columns: ds (datetime), y (float distance_mm).
    Returns dict with forecast data and insight flags.
    """
    from prophet import Prophet

    # Resample to 5-minute resolution to keep training fast
    df_r = df.set_index("ds")["y"].resample("5min").median().ffill().reset_index()
    df_r.columns = ["ds", "y"]

    m = Prophet(
        interval_width=0.95,
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10,
    )
    m.fit(df_r)

    future = m.make_future_dataframe(
        periods=horizon_hours * 12,  # 5-min slots
        freq="5min",
        include_history=True,
    )
    fc = m.predict(future)

    # Keep a compact slice: last 48 h history + forecast horizon
    cutoff = df_r["ds"].max()
    hist   = fc[fc["ds"] <= cutoff].tail(576)   # ~2 days history
    fcast  = fc[fc["ds"] >  cutoff]

    # ── Insights ──────────────────────────────────────────────────────────────
    insights = _generate_insights(df_r, fc, cutoff)

    return {
        "history": {
            "ds":          hist["ds"].astype(str).tolist(),
            "yhat":        hist["yhat"].round(2).tolist(),
            "yhat_lower":  hist["yhat_lower"].round(2).tolist(),
            "yhat_upper":  hist["yhat_upper"].round(2).tolist(),
        },
        "forecast": {
            "ds":          fcast["ds"].astype(str).tolist(),
            "yhat":        fcast["yhat"].round(2).tolist(),
            "yhat_lower":  fcast["yhat_lower"].round(2).tolist(),
            "yhat_upper":  fcast["yhat_upper"].round(2).tolist(),
        },
        "trend": {
            "ds":    fc["ds"].astype(str).tolist(),
            "trend": fc["trend"].round(2).tolist(),
        },
        "insights": insights,
        "model": m,   # kept in memory, not serialised to JSON
    }


def _generate_insights(df_r: pd.DataFrame, fc: pd.DataFrame, cutoff) -> list[str]:
    """Generate natural-language insights from usage patterns."""
    insights = []

    # ── Peak usage hour ───────────────────────────────────────────────────────
    df_r["hour"] = df_r["ds"].dt.hour
    hourly = df_r.groupby("hour")["y"].mean()
    peak_hour = int(hourly.idxmax())
    insights.append(f"Peak usage typically around {peak_hour:02d}:00")

    # ── Rising vs falling trend ───────────────────────────────────────────────
    hist_fc = fc[fc["ds"] <= cutoff]
    if len(hist_fc) >= 2:
        recent_trend = hist_fc["trend"].iloc[-1] - hist_fc["trend"].iloc[0]
        if recent_trend > 5:
            insights.append("Usage higher than baseline — possible slow drain")
        elif recent_trend < -5:
            insights.append("Usage lower than baseline — good conservation")

    # ── Forecast direction ────────────────────────────────────────────────────
    fcast = fc[fc["ds"] > cutoff]
    if len(fcast) >= 12:
        fcast_delta = fcast["yhat"].iloc[11] - fcast["yhat"].iloc[0]
        if fcast_delta > 10:
            insights.append("Forecast: level expected to rise (emptying) over next hour")
        elif fcast_delta < -10:
            insights.append("Forecast: level expected to drop (filling) over next hour")
        else:
            insights.append("Forecast: stable level expected over next hour")

    # ── Variance insight ──────────────────────────────────────────────────────
    resid_std = float(df_r["y"].std())
    if resid_std > 30:
        insights.append("High reading variance — intermittent usage pattern detected")

    return insights


def get_hourly_summary(df: pd.DataFrame) -> list[dict]:
    """
    Return last 24 hours of hourly-averaged readings.
    df has: timestamp (datetime), distance (float).
    """
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
