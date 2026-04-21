"""
services/flow.py
Flow rate analysis — direction, smoothed rate, time estimates.
Ported from tank_monitor_complete's flow logic, adapted for the modular architecture.
"""

import numpy as np

FLOW_STABLE_THRESHOLD = 0.3   # mm/min — below this = 'stable'
FLOW_SMOOTH_WINDOW    = 5     # readings to smooth flow rate


def compute_flow_rate(values: list[float], window: int = FLOW_SMOOTH_WINDOW) -> dict:
    """
    Compute smoothed flow rate and direction from recent distance readings.

    Returns
    -------
    dict:
        flow_rate      - smoothed rate (mm/sample); positive = draining, negative = filling
        flow_direction - 'draining' | 'filling' | 'stable'
        raw_rate       - instantaneous (last diff)
    """
    if len(values) < 2:
        return {"flow_rate": 0.0, "flow_direction": "stable", "raw_rate": 0.0}

    arr = np.array(values, dtype=float)
    diffs = np.diff(arr)
    raw_rate = float(diffs[-1])

    # Smoothed rate: mean of last `window` diffs
    tail = diffs[-window:] if len(diffs) >= window else diffs
    flow_rate = float(np.mean(tail))

    if flow_rate > FLOW_STABLE_THRESHOLD:
        direction = "draining"
    elif flow_rate < -FLOW_STABLE_THRESHOLD:
        direction = "filling"
    else:
        direction = "stable"

    return {
        "flow_rate":      round(flow_rate, 4),
        "flow_direction": direction,
        "raw_rate":       round(raw_rate, 4),
    }


def compute_flow_summary(
    values: list[float],
    tank_empty_mm: float = 395.0,
    tank_full_mm: float = 35.0,
) -> dict:
    """
    Full flow snapshot: rate, direction, time-to-empty/full, trend.

    Parameters
    ----------
    values : recent distance readings (most recent last)
    tank_empty_mm : distance at 0%
    tank_full_mm  : distance at 100%
    """
    flow = compute_flow_rate(values)
    fr = flow["flow_rate"]
    direction = flow["flow_direction"]

    # Current distance is last reading
    dist = values[-1] if values else tank_empty_mm
    level_pct = max(0, min(100, ((tank_empty_mm - dist) / (tank_empty_mm - tank_full_mm)) * 100))

    # Time estimates
    est_empty = None
    est_full = None
    if fr > 0.01:
        remaining_mm = tank_empty_mm - dist  # mm of water left before empty
        if remaining_mm > 0:
            mins = remaining_mm / fr
            est_empty = f"{int(mins // 60)}h {int(mins % 60)}m"
    elif fr < -0.01:
        max_rise_mm = dist - tank_full_mm  # airspace before hitting sensor limit
        if max_rise_mm > 0:
            mins = abs(max_rise_mm / fr)
            est_full = f"{int(mins // 60)}h {int(mins % 60)}m"

    # Trend: accelerating or decelerating? (compare first vs second half of last 10)
    trend = "stable"
    if len(values) >= 10:
        arr = np.array(values[-10:], dtype=float)
        diffs = np.diff(arr)
        first_half = float(np.mean(diffs[:5]))
        second_half = float(np.mean(diffs[4:]))
        if second_half > first_half + 0.1:
            trend = "accelerating"
        elif second_half < first_half - 0.1:
            trend = "decelerating"

    return {
        "current_flow_rate":   flow["flow_rate"],
        "flow_direction":      direction,
        "est_time_to_empty":   est_empty,
        "est_time_to_full":    est_full,
        "trend":               trend,
        "level_pct":           round(level_pct, 1),
    }
