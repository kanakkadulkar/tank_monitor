"""
app.py  —  Water Tank Monitor Backend
Run: python app.py
"""

import os, sys, json, threading, warnings
from datetime import datetime, timedelta
from collections import deque

import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

warnings.filterwarnings("ignore")

# ── Path setup ──────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from services.analysis import analyze_tank_data, TANK_HEIGHT_MM
from services.roc import compute_roc
from services.anomaly import fit_anomaly_params, AnomalyDetector

app = Flask(__name__)
CORS(app, origins="*")

# ── In-memory buffer ─────────────────────────────────────────────────────────
BUFFER_SIZE = 300
_buffer: deque = deque(maxlen=BUFFER_SIZE)
_lock = threading.Lock()

# ── Cached analysis results ───────────────────────────────────────────────────
_cache = {
    "analysis":    None,
    "forecast":    None,
    "hourly":      None,
    "last_update": None,
    "detector":    None,        # live AnomalyDetector instance
    "last_anomaly": None,
}


# ─────────────────────────────────────────────────────────────────────────────
# Startup: load dataset & train
# ─────────────────────────────────────────────────────────────────────────────

def _load_and_train():
    csv_path = os.path.join(BASE, "data", "CleanedFinalDataset.csv")
    if not os.path.exists(csv_path):
        print("[app] WARNING: dataset not found, starting cold.")
        return

    print("[app] Loading dataset and training models…")
    df = pd.read_csv(csv_path)
    df = df.rename(columns={"ds": "timestamp", "y": "distance"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df[["timestamp", "distance"]].dropna().sort_values("timestamp")

    # Pre-fill buffer with last BUFFER_SIZE rows
    tail = df.tail(BUFFER_SIZE)
    with _lock:
        _buffer.clear()
        for _, row in tail.iterrows():
            _buffer.append({"timestamp": row["timestamp"].isoformat(),
                            "distance": float(row["distance"])})

    # Full analysis on whole dataset
    result = analyze_tank_data(df)

    with _lock:
        _cache["analysis"]    = _serialise(result)
        _cache["forecast"]    = result.get("forecast")
        _cache["hourly"]      = result.get("hourly_summary")
        _cache["last_update"] = datetime.now().isoformat()
        _cache["detector"]    = result.get("_detector")

    print(f"[app] Training done. {len(df)} rows loaded.")


def _serialise(result: dict) -> dict:
    """Strip non-serialisable objects from analysis result."""
    out = {}
    for k, v in result.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            out[k] = _serialise(v)
        elif isinstance(v, list):
            out[k] = v
        elif isinstance(v, (int, float, str, bool, type(None))):
            out[k] = v
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = str(v)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled hourly summary refresh
# ─────────────────────────────────────────────────────────────────────────────

def _hourly_refresh():
    with _lock:
        buf_copy = list(_buffer)
    if not buf_copy:
        return
    df = pd.DataFrame(buf_copy)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    from services.forecast import get_hourly_summary
    hourly = get_hourly_summary(df)
    with _lock:
        _cache["hourly"] = hourly
    print(f"[app] Hourly summary refreshed ({len(buf_copy)} points)")


scheduler = BackgroundScheduler()
scheduler.add_job(_hourly_refresh, "interval", minutes=60)
scheduler.start()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/collect", methods=["POST"])
def collect():
    """Receive sensor reading from ESP32 or replay script."""
    data = request.get_json(silent=True) or {}
    try:
        distance = float(data.get("distance") or data.get("value") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid distance"}), 400

    ts = data.get("timestamp") or datetime.now().isoformat()
    point = {"timestamp": ts, "distance": distance}

    with _lock:
        _buffer.append(point)
        buf_copy = list(_buffer)
        detector = _cache["detector"]

    # ── Live ROC ──────────────────────────────────────────────────────────────
    recent_vals = [p["distance"] for p in buf_copy[-30:]]
    roc = compute_roc(recent_vals)

    # ── Live anomaly via buffered STL residual (approximation) ────────────────
    anomaly_result = None
    if detector and len(buf_copy) >= 10:
        # Estimate residual: deviation from trailing MA (fast proxy for STL resid)
        ma = float(np.median([p["distance"] for p in buf_copy[-20:]]))
        residual = distance - ma
        anomaly_result = detector.update(residual)
        if anomaly_result["is_anomaly"]:
            with _lock:
                _cache["last_anomaly"] = {
                    "timestamp":  ts,
                    "distance":   distance,
                    "mad_z":      anomaly_result["mad_z"],
                    "cusum_anomaly": anomaly_result["cusum_anomaly"],
                }

    return jsonify({
        "received": True,
        "distance": distance,
        "water_level_pct": round(max(0, min(100, (1 - distance/TANK_HEIGHT_MM)*100)), 1),
        "roc_state":  roc["state"],
        "anomaly":    anomaly_result,
    })


@app.route("/latest")
def latest():
    """Return last reading + current status."""
    with _lock:
        buf = list(_buffer)
        anomaly = _cache["last_anomaly"]

    if not buf:
        return jsonify({"error": "no data yet"}), 404

    last = buf[-1]
    distance = last["distance"]
    recent = [p["distance"] for p in buf[-30:]]
    roc = compute_roc(recent)

    return jsonify({
        "timestamp":       last["timestamp"],
        "distance_mm":     distance,
        "water_level_pct": round(max(0, min(100, (1-distance/TANK_HEIGHT_MM)*100)), 1),
        "roc":             roc,
        "last_anomaly":    anomaly,
        "buffer_size":     len(buf),
        "readings":        [{"timestamp": p["timestamp"], "distance": p["distance"]}
                            for p in buf[-15:]],
    })


@app.route("/analysis")
def analysis():
    """Return full ML analysis (cached, refreshed on demand)."""
    with _lock:
        cached = _cache["analysis"]
        last   = _cache["last_update"]
        buf    = list(_buffer)

    # Re-run if cache is stale (>5 min) or not yet populated
    stale = (last is None) or \
            (datetime.now() - datetime.fromisoformat(last) > timedelta(minutes=5))

    if stale and len(buf) >= 20:
        df = pd.DataFrame(buf)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        result = analyze_tank_data(df)
        with _lock:
            _cache["analysis"]    = _serialise(result)
            _cache["last_update"] = datetime.now().isoformat()
            if result.get("_detector"):
                _cache["detector"] = result["_detector"]
        return jsonify(_cache["analysis"])

    return jsonify(cached or {"error": "analysis not ready"})


@app.route("/forecast")
def forecast():
    """Return Prophet forecast data."""
    with _lock:
        fc = _cache["forecast"]
    if fc is None:
        return jsonify({"error": "forecast not ready yet"}), 404

    # Return serialisable subset
    return jsonify({
        "history":  fc.get("history"),
        "forecast": fc.get("forecast"),
        "trend":    fc.get("trend"),
        "insights": fc.get("insights", []),
    })


@app.route("/hourly")
def hourly():
    """Return hourly usage summary."""
    with _lock:
        h = _cache["hourly"]
    return jsonify(h or [])


@app.route("/buffer")
def buffer_data():
    """Return all buffered raw readings (for chart)."""
    with _lock:
        buf = list(_buffer)
    return jsonify([{"timestamp": p["timestamp"], "distance": p["distance"]} for p in buf])


@app.route("/health")
def health():
    return jsonify({"status": "ok", "buffer": len(_buffer)})


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _load_and_train()
    print("[app] Flask server starting on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
