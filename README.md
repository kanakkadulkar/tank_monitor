# 🛢 IoT Liquid Tank Monitoring with Anomaly Detection

A comprehensive IoT-based anomaly detection framework for liquid tank monitoring using HC-SR04 ultrasonic sensor, ESP32 microcontroller, and a robust 3-detector ensemble pipeline acting on STL-decomposed residuals.

## 🏗 Architecture

```mermaid
graph TD
    subgraph "Tier 1: Sensing (Edge)"
        A["📶 HC-SR04 Sensor"] -->|"Distance (mm)"| B["⚡ ESP32"]
    end
  
    subgraph "Tier 2: Edge Server (Flask)"
        B -->|"HTTP POST /collect"| C["🌐 Flask API"]
        C --> D["🧠 3-Detector Ensemble"]
        D -->|"MAD | RoC | CUSUM"| D
        D --> E[("💽 SQLite Database (Live)")]
    end
  
    subgraph "Tier 3: UI (React/Vite)"
        E --> G["💻 Glassmorphism Web Dashboard"]
        E --> H["📊 Real-Time Report"]
    end
```

**Three-Tier System:**

- **Tier 1 (Sensing):** HC-SR04 + ESP32 emitting real-time proximity pings.
- **Tier 2 (Edge Server):** Flask backend evaluating residuals via median absolute deviations, contextual thresholds, and adaptive logic.
- **Tier 3 (Visualization):** React/Vite web application providing real-time flow summary, dynamic charting, and statistical reporting.

## 🔍 In-Depth System Architecture

```mermaid
graph LR
    %% Hardware Tier
    subgraph ESP32["Sensing Hardware"]
        direction TB
        HC["HC-SR04"] --> MCU["ESP32 Microcontroller"]
        MCU --> WiFi["WiFi / HTTP POST"]
    end

    %% Python Backend Tier
    subgraph Server["Backend Server (Python/Flask)"]
        direction TB
        Route["POST /collect"] --> Buffer["300-point Rolling Buffer"]
      
        %% Ensemble Engine
        subgraph Ensemble["Live Diagnosis Engine"]
            Buffer --> STL["STL Decomposition (Startup)"]
            STL -.-> Residual["Residual Signal"]
            Residual --> MAD["1. MAD (Spikes)"]
            Residual --> ROC["2. RoC (Rapid Drain/Refill)"]
            Residual --> CUSUM["3. Adaptive CUSUM (Leaks)"]
            MAD --> Voting["Consensus & Taxonomy Layer"]
            ROC --> Voting
            CUSUM --> Voting
        end
      
        Voting --> Flow["Flow/Usage Calculator"]
      
        %% Database
        subgraph DB["SQLite Database"]
            LiveDb[("live_sensor.db")]
        end
      
        Flow --> DB
    end

    %% Client Tier
    subgraph Client["React Dashboard (Vite)"]
        direction TB
        Fetch["Polling (GET /latest)"] --> DOM["Virtual DOM Elements"]
        DOM --> Charts["Recharts Renderers"]
        DOM --> Log["Anomaly Data Table & Badges"]
    end

    %% Connections
    WiFi == "JSON Payload" ==> Route
    Fetch == "JSON State" ==> DB
```

## 🔄 User Flow & Data Lifecycle

```mermaid
sequenceDiagram
    participant E as ESP32 Sensor
    participant F as Flask Backend
    participant D as SQLite DB
    participant U as React Dashboard
  
    loop Every ~20 seconds
        E->>F: POST /collect {"distance_mm": 42.5}
        F->>F: Extract Residual
        F->>F: Execute MAD, RoC (>2.0mm), CUSUM
        F->>F: Vote & Suppress (Classify Chandola Taxonomy)
        F->>D: INSERT INTO live_readings
        F-->>E: JSON 200 OK
    end
  
    loop Every 2 seconds
        U->>F: GET /latest
        F->>D: Fetch buffer and anomaly states
        F-->>U: JSON (water_level_pct, flow, last_anomaly)
        U->>U: Hot-reload React visual components
    end
```

## 🎯 Physical Calibration (Hardcoded Defaults)

- **Tank Full Capacity (100%)**: `35.0 mm` boundary from sensor.
- **Tank Empty Limit (0%)**: `395.0 mm` boundary from sensor.
- **Overflow Trigger**: `< 35.0 mm`

## 📊 Detection Methods

| Method                      | Target Anomaly   | Mechanism | Severity/Alert |
| --------------------------- | ---------------- | --------- | ------------- |
| MAD (Median Absolute Dev)   | Point Spikes     | Robust threshold against extreme math noise | Critical |
| RoC (Rate of Change)        | Drains / Theft   | Failsafe threshold bounds `±2.0mm/s` | Alert |
| RoC (Negative Limit)        | Refill Events    | Physical override mapping to Normal Op | Log |
| Adaptive CUSUM              | Slow Leaks       | Tracks progressive cumulative slip | Alert |
| **Hybrid (3-method)** | **Voting Consensus** | **n_agree / 3 determines tier** | **Dynamic** |

## 🚀 Quick Start

### 1. Start the Flask Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```
*Note: `app.py` runs on port `5001`. The `backend/simulator/replay.py` can be used to stream the included `Thursday_Tuesday.csv` directly into the `/collect` endpoint to visualize data locally.*

### 2. Start the React Frontend

```bash
cd frontend
npm install
npm run dev
```
*Note: Runs on port `5173`. Opens to a live dashboard rendering sensor streams mapped to the mathematical pipeline.*

## 📁 Project Structure

```text
tank_monitor_cloned/
├── backend/
│   ├── app.py                   # Main Flask API / Routing
│   ├── data/                    # Thursday_Tuesday.csv & SQLite local instance
│   ├── services/
│   │   ├── analysis.py          # Master aggregator + pipeline initialization
│   │   ├── anomaly.py           # MAD, CUSUM, Chandola Taxonomy Logic
│   │   ├── flow.py              # Time-to-Empty / Flow Rate logic
│   │   ├── roc.py               # Rate of change sliding window
│   │   └── stl.py               # Time-series decomposition
│   └── simulator/               # Synthetic event streaming
│       └── replay.py
├── frontend/
│   ├── src/
│   │   ├── components/          # Reusable Glassmorphism UI
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx    # Real-time operations window
│   │   │   ├── Analytics.jsx    # Historical chart views
│   │   │   └── Report.jsx       # Read-only live statistical review
│   │   └── services/            # Axios API config
│   ├── package.json
│   └── vite.config.js           # Native build tooling
└── README.md
```

## 📈 Methodology Notes

- **Refill Logic Handling:** Standard `refill_events` mapped to negative RoC bursts are parsed correctly but are specifically downgraded to the `Log` severity tier. They automatically trigger an accelerated suppression circuit (2 hits instead of 5), recognizing massive level shifts natively as "Normal Application Operation", protecting against alert fatigue.
- **STL Application:** Detection is exclusively measured on mathematical **Residuals** rather than raw values, naturally eliminating daily water usage cycles that trigger false-positives in simpler moving average/standard-deviation models.
