# IoT Tank Monitor Anomaly Detection Pipeline

This repository hosts a robust, production-ready IoT Tank Monitoring Dashboard and Anomaly Detection backend designed for precision water level telemetry. 

## 🏗 System Architecture

The architecture spans a modular Flask (Python) backend for mathematical analysis and a Vite (React) front-end built natively with CSS glassmorphism aesthetics.

### Key Dimensions (Configurable)
- **Tank Full Capacity (100%)**: `35.0 mm` distance from the sensor
- **Tank Empty Capacity (0%)**: `395.0 mm` distance from the sensor

---

## 🧠 Diagnostic Pipeline

We utilize an academically grounded, deterministic statistical model optimized for IoT sensor dynamics (specifically addressing characteristic HC-SR04 ultrasonic sensor glitches), completely eliminating the need for circular, high-latency libraries like Prophet.

### Step 1: STL Decomposition
Raw data is processed using **Seasonal-Trend Decomposition using Loess (STL)**. 
- Prevents false-anomalies caused by cyclic daily usage.
- Detection algorithms execute exclusively on the **residual signal** (de-trended and de-seasonalized).

### Step 2: Hybrid Detection (3-Method Voting)
We employ three distinct mathematical bounds, covering all physical failure geometries. 

1. **MAD (Median Absolute Deviation)**
    - *Purpose*: Point anomalies.
    - *Mechanism*: Extracts the median of variations and applies an adaptive 99.5th-percentile threshold. Highly robust against infinite sensor spikes (unlike MA+SD which suffers from anomaly masking).
2. **Rate-of-Change (RoC)**
    - *Purpose*: Contextual anomalies.
    - *Mechanism*: Catches aggressive, sudden draining outside the physical constraints of baseline plumbing (Draining > 2.0 mm/sample).
3. **Adaptive CUSUM**
    - *Purpose*: Collective anomalies.
    - *Mechanism*: Accumulates progressive, minute deviations over time to catch gradual drifts and slow-leaks entirely undetectable to MAD or typical thresholds.

### Step 3: Formal Classification Taxonomy
Anomalies trigger a voting consensus (n_agree / 3) and map directly to formal topologies defined by **Chandola et al. (2009)**:

- `sensor_spike`: Immediate isolated reading failure.
- `sensor_freeze`: Output stagnates artificially.
- `overflow`: Proximity encroaches dangerous boundary.
- `sudden_drain_theft`: Accelerated unexpected drainage.
- `slow_leak`: Gradual progressive liquid depletion.
- *Note:* Intentional refills are dynamically parsed (via negative RoC) and downgraded to "Log" priority, suppressing them from triggering UI alerts since they reflect expected operations.

---

## 🚀 Running The Application

### Backend (Flask)
```bash
cd backend
pip install -r requirements.txt
python app.py
```
*(Runs on localhost:5001. The simulator script `simulator/replay.py` streams dataset rows actively to `/collect`)*

### Frontend (React)
```bash
cd frontend
npm install
npm run dev
```
*(Runs on localhost:5173. Dynamically polls the backend for sub-second visual updates)*
