# 🌤️ IoT Weather Monitoring System

A distributed IoT weather monitoring system built using **ESP32**, **MQTT**, **FastAPI**, **SQLite**, **Machine Learning**, and **Streamlit**.

The system collects environmental data from ESP32 sensors, performs real-time anomaly detection and temperature forecasting, stores telemetry in a database, and visualizes everything through a live dashboard.

---

## Features

* Real-time weather telemetry
* MQTT-based communication
* FastAPI backend
* SQLite database (WAL mode)
* Multi-sensor support
* Live Streamlit dashboard
* AI-based anomaly detection
* Temperature forecasting
* CSV data export
* System health monitoring
* Tailscale remote connectivity

---

## System Architecture

```text
ESP32
   │
   ▼
MQTT Broker (Mosquitto)
   │
   ▼
FastAPI Backend
   ├── Payload Validation
   ├── ML Inference
   ├── SQLite Storage
   └── Health API
   │
   ▼
SQLite Database
   │
   ▼
Streamlit Dashboard
```

---

## Tech Stack

### Hardware

* ESP32-WROOM-32
* BME690 Sensor

### Backend

* FastAPI
* Paho MQTT
* SQLite

### Machine Learning

* Isolation Forest
* XGBoost

### Dashboard

* Streamlit
* Plotly

### Networking

* Mosquitto MQTT
* Tailscale

---

## Project Structure

```text
IoT_Weather_Project/
│
├── main.py                 # FastAPI backend
├── dashboard.py            # Streamlit dashboard
├── weather_data.db         # SQLite database
├── anomaly_model.pkl
├── temperature_model.pkl
├── rejected_payloads.log
├── requirements.txt
└── README.md
```

---

## Current Status

### Completed

* MQTT communication
* FastAPI backend
* SQLite storage
* Multi-sensor support
* Live dashboard
* ML inference
* Health monitoring
* CSV export

### In Progress

* Real sensor data collection
* ML model retraining
* REST API expansion
* Documentation

### Planned

* Raspberry Pi deployment
* Docker support
* HTTPS/TLS
* JWT Authentication
* Automated testing
* Cloud deployment

---

## Running the Project

### 1. Clone the repository

```bash
git clone <repository-url>
cd IoT_Weather_Project
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the backend

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. Launch the dashboard

```bash
streamlit run dashboard.py
```

---

## Dashboard

The dashboard provides:

* Live sensor readings
* Historical trends
* AI anomaly alerts
* Temperature prediction
* Model confidence
* CSV export
* Device status monitoring

---

## Future Improvements

* Raspberry Pi edge deployment
* Multi-node sensor network
* OpenWeatherMap integration
* Docker containerization
* Prometheus & Grafana monitoring
* OTA firmware updates
* Enhanced ML models trained on real-world sensor data

---

## License

This project was developed as a portfolio project to demonstrate IoT system design, backend development, and applied machine learning.
