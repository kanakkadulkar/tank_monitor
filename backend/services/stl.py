"""
services/stl.py
Adaptive STL decomposition service.
All thresholds derived from data statistics — no fixed values.
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL


def compute_stl(series: pd.Series, period: int = 72) -> dict:
    """
    Run STL on a numeric Series indexed by time.
    period=72 → one full day at ~20-second intervals resampled to 5-min → 288/day,
    but we use hourly resampled: 24/day → period=24.
    Caller should pass the right period for their resampled data.

    Returns dict with:
        trend, seasonal, resid, dates, original,
        mad, mad_threshold (99.5th percentile of |resid|)
    """
    if len(series) < period * 2:
        return None

    stl = STL(series, period=period, robust=True)
    result = stl.fit()

    resid = result.resid
    mad = float(np.median(np.abs(resid - np.median(resid))))
    # Adaptive threshold: 99.5th quantile of absolute deviations
    mad_threshold = float(np.quantile(np.abs(resid - np.median(resid)), 0.995))

    return {
        "trend":         result.trend.tolist(),
        "seasonal":      result.seasonal.tolist(),
        "resid":         resid.tolist(),
        "original":      series.tolist(),
        "dates":         series.index.astype(str).tolist(),
        "mad":           mad,
        "mad_threshold": mad_threshold,
        "period":        period,
    }


def resample_for_stl(df: pd.DataFrame, freq: str = "1h") -> pd.Series:
    """
    Resample raw 20-second data to hourly median for STL.
    df must have columns: timestamp (datetime), distance (float).
    """
    ts = df.set_index("timestamp")["distance"].resample(freq).median().ffill()
    return ts
