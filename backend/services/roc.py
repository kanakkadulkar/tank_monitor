"""
services/roc.py
Adaptive Rate-of-Change detection.
Noise threshold = rolling standard deviation — fully adaptive.
"""

import numpy as np
import pandas as pd
from collections import deque


def compute_roc(values: list[float], window: int = 10) -> dict:
    """
    Compute ROC and classify state using adaptive noise threshold.

    Parameters
    ----------
    values : list of recent distance readings (mm)
    window : rolling window for noise estimation

    Returns
    -------
    dict:
        roc         - instantaneous rate of change (mm per sample)
        noise_floor - rolling std of recent values
        state       - "Filling" | "Emptying" | "Stable"
        roc_series  - list of per-sample ROC values
    """
    if len(values) < 3:
        return {"roc": 0.0, "noise_floor": 0.0, "state": "Stable", "roc_series": []}

    arr = np.array(values, dtype=float)

    # Instantaneous ROC (central difference where possible)
    roc_series = np.gradient(arr).tolist()
    current_roc = roc_series[-1]

    # Adaptive noise floor = rolling std over last `window` diffs
    diffs = np.abs(np.diff(arr))
    if len(diffs) >= window:
        noise_floor = float(np.std(diffs[-window:]))
    else:
        noise_floor = float(np.std(diffs)) if len(diffs) > 0 else 0.0

    # Minimum noise guard: 1 MAD of the diffs
    mad_diffs = float(np.median(np.abs(diffs - np.median(diffs)))) if len(diffs) > 0 else 0.0
    noise_floor = max(noise_floor, mad_diffs * 0.5, 0.01)

    # Classification
    if current_roc > noise_floor:
        state = "Emptying"    # distance increasing → water dropping
    elif current_roc < -noise_floor:
        state = "Filling"     # distance decreasing → water rising
    else:
        state = "Stable"

    return {
        "roc":         round(current_roc, 4),
        "noise_floor": round(noise_floor, 4),
        "state":       state,
        "roc_series":  [round(r, 4) for r in roc_series],
    }
