"""
app.py  —  Water Tank Monitor Backend
Detection: STL → MAD + RoC + Adaptive CUSUM → Classification → Tier
No Prophet. All thresholds adaptive except RoC (±2.0 per taxonomy).

Run: python app.py
"""

import os, sys, json, threading, warnings
from datetime import datetime, timedelta
from collections import deque

import numpy as np
import pandas as pd
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
warnings.filterwarnings("ignore")

# ── Path setup ──────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from services.analysis import analyze_tank_data, get_hourly_summary, TANK_EMPTY_MM, TANK_FULL_MM
from services.roc import compute_roc
from services.anomaly import fit_anomaly_params, AnomalyDetector, ROC_THRESHOLD
from services.flow import compute_flow_rate, compute_flow_summary
from services.report import generate_report_html

app = Flask(__name__)
CORS(app, origins="*")

DB_PATH = os.path.join(BASE, "data", "live_sensor.db")

def init_live_db():
    """Create database for live readings."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS live_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            distance REAL,
            flow_rate REAL DEFAULT 0,
            flow_direction TEXT DEFAULT 'stable',
            anomaly_class TEXT DEFAULT 'normal',
            conf_score REAL DEFAULT 0,
            conf_tier TEXT DEFAULT 'log',
            suppressed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# ── In-memory state ──────────────────────────────────────────────────────────
BUFFER_SIZE = 300
_buffer = deque(maxlen=BUFFER_SIZE)
_lock = threading.Lock()

_cache = {
    "analysis":     None,    # serialised analysis dict (from CSV on startup)
    "hourly":       None,
    "last_update":  None,
    "detector":     None,    # live AnomalyDetector instance
    "last_anomaly": None,
    "trained":      False,   # whether initial training from CSV is done
}


def _serialise(obj):
    """Recursively make a dict JSON-safe."""
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items() if not k.startswith("_")}
    elif isinstance(obj, list):
        return [_serialise(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return round(float(obj), 6)
    elif isinstance(obj, (np.ndarray,)):
        return [_serialise(v) for v in obj.tolist()]
    elif isinstance(obj, (int, str, bool, type(None))):
        return obj
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    else:
        return str(obj)


def _load_and_train():
    """Load historical CSV, run full analysis, cache results."""
    csv_path = os.path.join(BASE, "data", "Thursday_Tuesday.csv")
    if not os.path.exists(csv_path):
        print("[app] WARNING: dataset not found, starting cold.")
        return

    print("[app] Loading dataset and training models...")
    df = pd.read_csv(csv_path)
    # Support both old Prophet format (ds, y) and new raw format (timestamp, distance_mm)
    df = df.rename(columns={"ds": "timestamp", "y": "distance", "distance_mm": "distance"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df[["timestamp", "distance"]].dropna().sort_values("timestamp")

    # Fill buffer with tail of historical data
    tail = df.tail(BUFFER_SIZE)
    with _lock:
        _buffer.clear()
        for _, row in tail.iterrows():
            _buffer.append({"timestamp": row["timestamp"].isoformat(),
                            "distance": float(row["distance"])})

    # Run full analysis on the COMPLETE dataset
    result = analyze_tank_data(df)

    with _lock:
        _cache["analysis"]    = _serialise(result)
        _cache["hourly"]      = result.get("hourly_summary")
        _cache["last_update"] = datetime.now().isoformat()
        _cache["detector"]    = result.get("_detector")
        _cache["trained"]     = True

    n_anomalies = len(result.get("anomalies", []))
    has_stl = result.get("stl") is not None
    print(f"[app] Training done. {len(df)} rows. STL: {has_stl}. Anomalies: {n_anomalies}")


def _hourly_refresh():
    with _lock:
        buf_copy = list(_buffer)
    if not buf_copy: return
    df = pd.DataFrame(buf_copy)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    hourly = get_hourly_summary(df)
    with _lock:
        _cache["hourly"] = hourly


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

    with _lock:
        _buffer.append({"timestamp": ts, "distance": distance})
        buf_copy = list(_buffer)
        detector = _cache.get("detector")

    # Live ROC
    recent_vals = [p["distance"] for p in buf_copy[-30:]]
    roc = compute_roc(recent_vals)

    # Live flow
    flow_vals = [p["distance"] for p in buf_copy[-60:]]
    flow = compute_flow_rate(flow_vals)

    # Live anomaly detection (3-method: MAD + RoC + CUSUM)
    anomaly_result = None
    if detector and len(buf_copy) >= 10:
        ma = float(np.median([p["distance"] for p in buf_copy[-20:]]))
        residual = distance - ma
        recent_std = float(np.std([p["distance"] for p in buf_copy[-20:]]))
        anomaly_result = detector.update(
            residual,
            distance_mm=distance,
            roc=roc.get("roc", 0),
            recent_std=recent_std,
            tank_full_mm=TANK_FULL_MM,
            tank_empty_mm=TANK_EMPTY_MM,
        )
        if anomaly_result["is_anomaly"]:
            with _lock:
                _cache["last_anomaly"] = {
                    "timestamp":     ts,
                    "distance":      distance,
                    "mad_z":         anomaly_result["mad_z"],
                    "n_agree":       anomaly_result["n_agree"],
                    "anomaly_class": anomaly_result["anomaly_class"],
                    "conf_tier":     anomaly_result["conf_tier"],
                    "conf_score":    anomaly_result["conf_score"],
                }

    # Save to DB
    anom_class = anomaly_result["anomaly_class"] if anomaly_result else "normal"
    conf_score = anomaly_result["conf_score"] if anomaly_result else 0
    conf_tier  = anomaly_result["conf_tier"] if anomaly_result else "log"
    suppressed = int(anomaly_result.get("suppressed", False)) if anomaly_result else 0

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO live_readings
           (timestamp, distance, flow_rate, flow_direction,
            anomaly_class, conf_score, conf_tier, suppressed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts, distance, flow["flow_rate"], flow["flow_direction"],
         anom_class, conf_score, conf_tier, suppressed)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "received":        True,
        "distance":        distance,
        "water_level_pct": round(max(0, min(100, ((TANK_EMPTY_MM - distance)/(TANK_EMPTY_MM - TANK_FULL_MM))*100)), 1),
        "roc_state":       roc["state"],
        "flow":            flow,
        "anomaly":         anomaly_result,
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
    flow = compute_flow_summary([p["distance"] for p in buf[-60:]], TANK_EMPTY_MM, TANK_FULL_MM)

    return jsonify({
        "timestamp":       last["timestamp"],
        "distance_mm":     distance,
        "water_level_pct": round(max(0, min(100, ((TANK_EMPTY_MM - distance)/(TANK_EMPTY_MM - TANK_FULL_MM))*100)), 1),
        "roc":             roc,
        "flow":            flow,
        "last_anomaly":    anomaly,
        "buffer_size":     len(buf),
        "readings":        [{"timestamp": p["timestamp"], "distance": p["distance"]} for p in buf[-15:]],
    })


@app.route("/analysis")
def analysis():
    """
    Return full analysis.
    On startup, this returns the cached CSV-trained result (with STL + anomalies).
    Force re-analysis with ?refresh=true.
    """
    force = request.args.get("refresh", "").lower() == "true"

    with _lock:
        cached = _cache["analysis"]
        trained = _cache["trained"]

    if cached and not force:
        return jsonify(cached)

    # Only re-run from DB if explicitly forced AND we have enough data
    if force:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT timestamp, distance FROM live_readings", conn)
        conn.close()
        if len(df) >= 50:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            result = analyze_tank_data(df)
            with _lock:
                _cache["analysis"]    = _serialise(result)
                _cache["last_update"] = datetime.now().isoformat()
                if result.get("_detector"):
                    _cache["detector"] = result["_detector"]
            return jsonify(_cache["analysis"])

    return jsonify(cached or {"error": "No analysis available yet. Waiting for data."})


@app.route("/anomalies")
def anomalies():
    """Recent anomaly log from the live database."""
    limit = int(request.args.get("limit", 50))
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT timestamp, distance, anomaly_class, conf_score, conf_tier, suppressed
        FROM live_readings
        WHERE anomaly_class != 'normal'
        ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    return jsonify([
        {
            "timestamp":     r[0],
            "distance_mm":   r[1],
            "anomaly_class": r[2],
            "conf_score":    r[3],
            "conf_tier":     r[4],
            "suppressed":    bool(r[5]),
        }
        for r in rows
    ])


@app.route("/flow_summary")
def flow_summary():
    with _lock:
        buf = list(_buffer)
    if not buf:
        return jsonify({"error": "no data"}), 404
    vals = [p["distance"] for p in buf[-60:]]
    result = compute_flow_summary(vals, TANK_EMPTY_MM, TANK_FULL_MM)
    return jsonify(result)


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
    return jsonify({"status": "ok", "buffer": len(_buffer), "trained": _cache["trained"]})


@app.route("/report")
def report():
    """Dynamic HTML report from current analysis data."""
    with _lock:
        cached = _cache["analysis"]

    db_stats = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM live_readings").fetchone()[0]
        anomaly_count = conn.execute(
            "SELECT COUNT(*) FROM live_readings WHERE anomaly_class != 'normal'"
        ).fetchone()[0]
        conn.close()
        db_stats = {"total_readings": total, "total_anomalies": anomaly_count}
    except Exception:
        pass

    html = generate_report_html(cached or {}, db_stats)
    return Response(html, content_type="text/html; charset=utf-8")


if __name__ == "__main__":
    init_live_db()
    _load_and_train()
    print("[app] Flask server starting on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)