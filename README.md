# IoT Weather Telemetry System

A professional-grade IoT data pipeline that ingests sensor data via MQTT, validates it, stores it in a relational database, and visualizes it in real-time.

## 🏗️ Architecture
This system follows a modular IoT architecture, designed to be scalable and resilient.

```mermaid
graph LR
    A[ESP32 / Simulator] -->|MQTT| B(Mosquitto Broker)
    B -->|Subscribe| C[FastAPI Backend]
    C -->|Validate| D[(SQLite Database)]
    C -->|Inference| E[ML Fallback Engine]
    C -->|Dashboard Data| F[Streamlit Dashboard]