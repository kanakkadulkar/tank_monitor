"""
simulator/replay.py
Replays CleanedFinalDataset.csv row-by-row to the Flask /collect endpoint.

Usage:
    python replay.py                    # 1 reading/sec
    python replay.py --delay 0.5        # 2 readings/sec
    python replay.py --speed 10         # 10× faster (2s interval → 0.2s)
    python replay.py --host localhost --port 5001
"""

import argparse
import sys
import time
import os
import requests
import pandas as pd
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="Water Tank Data Replay")
    parser.add_argument("--host",  default="localhost")
    parser.add_argument("--port",  type=int, default=5001)
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between sends")
    parser.add_argument("--speed", type=float, default=1.0,  help="Speed multiplier")
    parser.add_argument("--loop",  action="store_true", help="Loop indefinitely")
    args = parser.parse_args()

    delay = args.delay / args.speed
    url   = f"http://{args.host}:{args.port}/collect"

    # Find CSV relative to this script or in parent data dir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_candidates = [
        os.path.join(script_dir, "..", "data", "CleanedFinalDataset.csv"),
        os.path.join(script_dir, "CleanedFinalDataset.csv"),
    ]
    csv_path = next((p for p in csv_candidates if os.path.exists(p)), None)
    if not csv_path:
        print("ERROR: CleanedFinalDataset.csv not found.")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df = df.rename(columns={"ds": "timestamp", "y": "distance"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df[["timestamp", "distance"]].dropna().sort_values("timestamp").reset_index(drop=True)

    print(f"[replay] Loaded {len(df)} rows from {csv_path}")
    print(f"[replay] Sending to {url} — delay={delay:.2f}s")
    print(f"[replay] Press Ctrl+C to stop\n")

    iteration = 0
    while True:
        iteration += 1
        sent = errors = 0
        for i, row in df.iterrows():
            payload = {
                "distance":  float(row["distance"]),
                "timestamp": datetime.now().isoformat(),   # use real-time ts
                "original_ts": str(row["timestamp"]),
            }
            try:
                resp = requests.post(url, json=payload, timeout=3)
                if resp.ok:
                    r = resp.json()
                    print(
                        f"\r[{datetime.now().strftime('%H:%M:%S')}] "
                        f"row {i+1:5d}/{len(df)} | "
                        f"dist={payload['distance']:6.1f}mm | "
                        f"level={r.get('water_level_pct',0):5.1f}% | "
                        f"state={r.get('roc_state','?'):8s} | "
                        f"anomaly={'YES' if r.get('anomaly') and r['anomaly'].get('is_anomaly') else 'no ':3s}",
                        end="", flush=True,
                    )
                    sent += 1
                else:
                    errors += 1
            except requests.ConnectionError:
                print(f"\n[replay] Cannot connect to {url} — is the backend running?")
                time.sleep(3)
                continue
            except Exception as e:
                errors += 1

            time.sleep(delay)

        print(f"\n[replay] Pass {iteration} complete. Sent={sent}, Errors={errors}")
        if not args.loop:
            break

    print("[replay] Done.")


if __name__ == "__main__":
    main()
