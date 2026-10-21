<div align="center">

# 🌊 Anomaly Detection in Liquid Tanking Using Time-Series Analysis

**Real-time IoT water tank monitoring system with adaptive anomaly detection, STL decomposition, and Prophet-based forecasting**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

</div>

---

## 📌 Overview

This project implements a **full-stack anomaly detection pipeline** for liquid tank monitoring, combining an IoT sensor data ingestion backend with a real-time analytics dashboard. It uses **Time-Series Analysis (TSA)** techniques — STL decomposition, adaptive CUSUM, MAD-based scoring, and Facebook Prophet forecasting — to detect anomalies such as leaks, overflow events, or irregular consumption patterns in real-time.

### Key Capabilities

| Feature | Description |
|---|---|
| **Hybrid Anomaly Detection** | Combines STL-Residual MAD scoring + Adaptive CUSUM — zero hardcoded thresholds, all parameters derived from data quantiles |
| **STL Decomposition** | Decomposes sensor signal into Trend, Seasonal, and Residual components for interpretable analysis |
| **Prophet Forecasting** | 24-hour ahead forecast with 95% confidence intervals, daily/weekly seasonality modeling |
| **Real-Time Ingestion** | Flask REST API ingests ultrasonic sensor readings from ESP32 at configurable intervals |
| **Adaptive Rate-of-Change** | Rolling noise-floor estimation to classify tank state as Filling / Emptying / Stable |
| **Live Dashboard** | React + Recharts UI with real-time charts, animated tank visualizer, anomaly alerts |

---

## 🏗️ Architecture

```
┌──────────────┐      POST /collect       ┌─────────────────────────────────────┐
│  ESP32 +     │ ──────────────────────▶  │         Flask Backend (5001)        │
│  HC-SR04     │                          │                                     │
│  Sensor      │     GET /latest          │  ┌─────────┐  ┌──────────────────┐  │
└──────────────┘  ◀──────────────────────  │  │ SQLite  │  │   ML Pipeline    │  │
                                          │  │ (live   │  │                  │  │
┌──────────────┐      GET /analysis       │  │  data)  │  │ • STL Decomp     │  │
│  React       │ ──────────────────────▶  │  └─────────┘  │ • MAD + CUSUM    │  │
│  Dashboard   │                          │               │ • Prophet        │  │
│  (Vite)      │     GET /forecast        │               │ • Adaptive ROC   │  │
│  Port: 5173  │ ──────────────────────▶  │               └──────────────────┘  │
└──────────────┘                          └─────────────────────────────────────┘
```

---

## 📂 Project Structure

```
tank_monitor/
├── backend/
│   ├── app.py                  # Flask server — REST endpoints, scheduler
│   ├── requirements.txt        # Python dependencies
│   ├── data/
│   │   └── CleanedFinalDataset.csv   # 34K+ sensor readings for training
│   ├── services/
│   │   ├── analysis.py         # Unified analysis pipeline
│   │   ├── anomaly.py          # Hybrid anomaly detector (MAD + CUSUM)
│   │   ├── forecast.py         # Prophet forecasting + hourly summaries
│   │   ├── roc.py              # Adaptive rate-of-change classifier
│   │   └── stl.py              # STL decomposition service
│   └── simulator/
│       └── replay.py           # CSV replay tool for testing
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── .env.example
│   └── src/
│       ├── App.jsx             # Root — tab navigation
│       ├── main.jsx            # React entry point
│       ├── index.css           # Design system (dark theme)
│       ├── components/
│       │   └── ui.jsx          # Shared UI primitives
│       ├── pages/
│       │   ├── Dashboard.jsx   # Live telemetry dashboard
│       │   └── Analytics.jsx   # Deep analysis — STL, Prophet, Anomalies
│       └── services/
│           └── api.jsx         # Axios API client
├── .gitignore
├── LICENSE
└── README.md
```

---

## ⚙️ Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** & npm
- (Optional) ESP32 with HC-SR04 ultrasonic sensor for live data

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Start the server (loads dataset & trains models on startup)
python app.py
```

The backend starts on `http://localhost:5001` and:
- Loads ~34K sensor readings from `CleanedFinalDataset.csv`
- Trains STL decomposition + Prophet models
- Initializes the adaptive anomaly detector
- Runs an hourly background scheduler for summary refresh

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# (Optional) Configure API URL
cp .env.example .env

# Start dev server
npm run dev
```

The dashboard opens at `http://localhost:5173`.

### 3. Simulate Live Sensor Data

If you don't have a physical ESP32 sensor, use the built-in replay simulator:

```bash
cd backend
python -m simulator.replay --speed 10      # 10× speed replay
python -m simulator.replay --delay 0.2     # Custom interval
python -m simulator.replay --loop          # Continuous loop
```

---

## 🔬 Algorithm Details

### Anomaly Detection Pipeline

1. **STL Decomposition** — Separates sensor signal into trend (long-term drift), seasonal (daily patterns), and residual (noise + anomalies)
2. **MAD Scoring** — Computes Median Absolute Deviation Z-scores on STL residuals; threshold derived from the 99.5th percentile of historical deviations (no manual tuning)
3. **Adaptive CUSUM** — Cumulative Sum control chart detects sustained mean shifts; allowance `k = MAD`, threshold `h = 99th percentile` of cumulative deviations
4. **Hybrid Decision** — An anomaly is flagged if **either** MAD exceeds threshold **or** CUSUM triggers — high recall without excessive false positives

### Forecasting

- **Facebook Prophet** with daily + weekly seasonality, 5-minute resolution resampling
- 24-hour forecast horizon with 95% confidence intervals
- Automated insight generation (peak usage hour, trend direction, variance classification)

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/collect` | Ingest a sensor reading (`{ "distance_mm": 120.5 }`) |
| `GET` | `/latest` | Latest reading + ROC state + anomaly status |
| `GET` | `/analysis` | Full ML analysis (STL + anomalies + forecast + insights) |
| `GET` | `/forecast` | Prophet forecast with confidence intervals |
| `GET` | `/hourly` | Hourly usage summary (last 24h) |
| `GET` | `/buffer` | Raw in-memory buffer (last 300 readings) |
| `GET` | `/health` | Health check |

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Sensor** | ESP32, HC-SR04 Ultrasonic Sensor |
| **Backend** | Python, Flask, SQLite, APScheduler |
| **ML/TSA** | statsmodels (STL), Prophet, NumPy, Pandas, scikit-learn |
| **Frontend** | React 19, Vite 8, Recharts, Framer Motion, Axios |
| **Anomaly Detection** | MAD Z-score, Adaptive CUSUM, STL Residual Analysis |

---

## 📊 Dataset

- **34,082 readings** collected from an ultrasonic distance sensor
- **~20-second sampling interval** over multiple days
- Columns: `ds` (timestamp), `y` (distance in mm from sensor to water surface)
- Distance is inversely proportional to water level: higher distance = lower water level

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](./LICENSE) file for details.

---

<div align="center">

**Built with 🔬 Time-Series Analysis & IoT**

</div>
