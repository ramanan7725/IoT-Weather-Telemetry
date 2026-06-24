# IoT Weather Monitoring Pipeline

A robust, resilient IoT telemetry pipeline designed for real-time environmental monitoring. This system features a decoupled architecture using MQTT for ingestion, FastAPI for high-performance processing, and Streamlit for real-time data visualization and predictive ML forecasting.

## Architecture Overview


- **Ingestion**: MQTT Protocol (Mosquitto Broker) with secure authentication.
- **Backend**: FastAPI (Python) implementing Pydantic validation and resilient asynchronous loops.
- **Persistence**: SQLite in Write-Ahead Logging (WAL) mode for high-concurrency read/writes.
- **Intelligence**: Integrated Linear Regression model for real-time temperature trend forecasting and anomaly detection.
- **Connectivity**: Zero-trust networking via Tailscale.

## Features
- **Data Integrity**: Strict Pydantic schema validation for incoming telemetry packets.
- **Resilience**: Automatic reconnection logic for broker stability.
- **Predictive Analytics**: Live forecasting of temperature trends using `scikit-learn`.
- **Anomalies**: Real-time outlier detection and UI visualization.

## Getting Started
1. **Clone the repo**: `git clone <your-repo-url>`
2. **Setup Environment**: Install dependencies using `pip install -r requirements.txt`.
3. **Configure**: Update your `.env` file with MQTT broker credentials.
4. **Run**: 
   - `mosquitto -c mosquitto.conf`
   - `python main.py`
   - `streamlit run dashboard.py`

## Project Status
Currently in **Tier 1A (Prototype)** stage:
- [x] Ingestion Engine
- [x] Backend Processing & Validation
- [x] Database Persistence
- [x] UI Dashboard
- [ ] Physical Hardware Integration (Awaiting BME280 sensor)
