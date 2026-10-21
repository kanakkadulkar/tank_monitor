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
import sqlite3
warnings.filterwarnings("ignore")

# ── Path setup ──────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from services.analysis import analyze_tank_data, TANK_HEIGHT_MM
from services.roc import compute_roc
from services.anomaly import fit_anomaly_params, AnomalyDetector

app = Flask(__name__)
CORS(app, origins="*")


DB_PATH = os.path.join(BASE, "data", "live_sensor.db")

def init_live_db():
    """Create a fresh database for live readings only."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # This table stores every reading received from the ESP32
    conn.execute("""
        CREATE TABLE IF NOT EXISTS live_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            distance REAL
        )
    """)
    conn.commit()
    conn.close()

# ── In-memory buffer ─────────────────────────────────────────────────────────
BUFFER_SIZE = 300
_buffer = deque(maxlen=BUFFER_SIZE)
_lock = threading.Lock()

# ── Cached analysis results ───────────────────────────────────────────────────
_cache = {
    "analysis":     None,
    "forecast":     None,
    "hourly":       None,
    "last_update": None,
    "detector":     None,        # live AnomalyDetector instance
    "last_anomaly": None,
}

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

    tail = df.tail(BUFFER_SIZE)
    with _lock:
        _buffer.clear()
        for _, row in tail.iterrows():
            _buffer.append({"timestamp": row["timestamp"].isoformat(),
                            "distance": float(row["distance"])})

    result = analyze_tank_data(df)

    with _lock:
        _cache["analysis"]    = _serialise(result)
        _cache["forecast"]    = result.get("forecast")
        _cache["hourly"]      = result.get("hourly_summary")
        _cache["last_update"] = datetime.now().isoformat()
        _cache["detector"]    = result.get("_detector")

    print(f"[app] Training done. {len(df)} rows loaded.")

def _serialise(result: dict) -> dict:
    out = {}
    for k, v in result.items():
        if k.startswith("_"): continue
        if isinstance(v, dict): out[k] = _serialise(v)
        elif isinstance(v, list): out[k] = v
        elif isinstance(v, (int, float, str, bool, type(None))): out[k] = v
        elif hasattr(v, "isoformat"): out[k] = v.isoformat()
        else: out[k] = str(v)
    return out

def _hourly_refresh():
    with _lock:
        buf_copy = list(_buffer)
    if not buf_copy: return
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

# ── Endpoints ──────────────────────────────────────────────────────────────

@app.route("/collect", methods=["POST"])
def collect():
    data = request.get_json(silent=True) or {}
    try:
        distance = float(data.get("distance_mm") or data.get("distance") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid distance"}), 400

    ts = datetime.now().isoformat()

    # Thread-safe snapshot of buffer + detector
    with _lock:
        _buffer.append({"timestamp": ts, "distance": distance})
        buf_copy = list(_buffer)
        detector = _cache["detector"]

    # Save every live reading to the SQLite database
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO live_readings (timestamp, distance) VALUES (?, ?)", (ts, distance))
    conn.commit()
    conn.close()

    # Live ROC calculation
    recent_vals = [p["distance"] for p in buf_copy[-30:]]
    roc = compute_roc(recent_vals)

    # Live anomaly detection
    anomaly_result = None
    if detector and len(buf_copy) >= 10:
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
    with _lock:
        buf = list(_buffer)
        anomaly = _cache["last_anomaly"]
    if not buf: return jsonify({"error": "no data yet"}), 404

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
        "readings":        [{"timestamp": p["timestamp"], "distance": p["distance"]} for p in buf[-15:]],
    })

@app.route("/analysis")
def analysis():
    """Return full ML analysis based on LIVE SQLite data."""
    with _lock:
        cached = _cache["analysis"]
        last   = _cache["last_update"]

    # Re-run if cache is stale (>5 min) or empty
    stale = (last is None) or \
            (datetime.now() - datetime.fromisoformat(last) > timedelta(minutes=5))

    if stale:
        # 1. Connect to your NEW live database
        conn = sqlite3.connect(DB_PATH) 
        # 2. Pull all readings received from the ESP32
        df = pd.read_sql_query("SELECT timestamp, distance FROM live_readings", conn)
        conn.close()

        if len(df) >= 20:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            # 3. Run the advanced pipeline on ONLY your live data
            result = analyze_tank_data(df) 
            
            with _lock:
                _cache["analysis"]    = _serialise(result)
                _cache["last_update"] = datetime.now().isoformat()
                if result.get("_detector"):
                    _cache["detector"] = result["_detector"]
            return jsonify(_cache["analysis"])

    return jsonify(cached or {"error": "Insufficient live data for AI analysis (need 20+ readings)"})


@app.route("/forecast")
def forecast():
    with _lock: fc = _cache["forecast"]
    if fc is None: return jsonify({"error": "forecast not ready yet"}), 404
    return jsonify({
        "history": fc.get("history"),
        "forecast": fc.get("forecast"),
        "trend": fc.get("trend"),
        "insights": fc.get("insights", []),
    })

@app.route("/hourly")
def hourly():
    with _lock: h = _cache["hourly"]
    return jsonify(h or [])

@app.route("/buffer")
def buffer_data():
    with _lock: buf = list(_buffer)
    return jsonify([{"timestamp": p["timestamp"], "distance": p["distance"]} for p in buf])

@app.route("/health")
def health():
    return jsonify({"status": "ok", "buffer": len(_buffer)})

if __name__ == "__main__":
    _load_and_train()
    print("[app] Flask server starting on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)