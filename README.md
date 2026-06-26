# IoT Weather Monitoring System

A distributed, real-time weather monitoring system. ESP32 sensor → MQTT → Machine Learning → Live Dashboard.

**Status:** 6.5/10 (Functional MVP, awaiting hardware validation)

## Architecture


- **Sensor:** ESP32 (BME690) publishing MQTT data.
- **Broker:** Mosquitto (Windows native).
- **Backend:** FastAPI (Python) for ingestion, validation, and SQLite persistence.
- **Persistence:** SQLite with Write-Ahead Logging (WAL) for concurrent access.
- **Dashboard:** Streamlit with Plotly charts and auto-refresh.

## Project Phases

| Phase | Host | Tech Stack |
| :--- | :--- | :--- |
| **1A: Prototype** | Laptop | MQTT + FastAPI + Kaggle ML models |
| **1: Edge** | Pi 4 or 5 | MQTT + FastAPI + Real Sensor Data |
| **1 Pro: Scaled** | Pi 4 or 5 | Real-time Fusion + Advanced ML Monitoring |

## Machine Learning Strategy
- **Models:** XGBRegressor (Forecasting) + IsolationForest (Anomaly Detection).
- **Current State:** Models are trained on synthetic Kaggle data (placeholder).
- **Real Data Pipeline:** 1. Collect 500+ readings using BME690.
    2. Implement cumulative retraining (retrain on *all* data when MAE > 1.5°C).
    3. Monitor degradation via `/api/ml/performance`.

## Setup & Usage

### 1. Prerequisites
- Python 3.10+
- Mosquitto Broker (Installed to `D:\Program Files\mosquitto\`)

### 2. Configuration
Create a `.env` file in the root directory:
```env
MQTT_BROKER=100.110.195.55
MQTT_PORT=1883
MQTT_USER=your_user
MQTT_PASS=your_pass
