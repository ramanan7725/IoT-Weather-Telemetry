# 🌤️ IoT Weather Monitoring System

> **A real-time IoT weather monitoring platform built with ESP32, MQTT, FastAPI, Machine Learning, and Streamlit.**

Collect environmental data from IoT devices, analyze it using machine learning, and visualize everything through an interactive live dashboard.

---

## 🚀 Highlights

✨ Real-time weather monitoring

📡 MQTT-based IoT communication

⚡ FastAPI backend with data validation

🤖 AI-powered anomaly detection

📈 Temperature forecasting

📊 Interactive dashboard with Plotly

🗄️ SQLite data storage (WAL Mode)

📥 CSV data export

📶 Multi-device support

🔍 Live backend & device health monitoring

---

## 🏗️ Architecture

```text
        ESP32 Sensor
             │
             ▼
     MQTT Broker (Mosquitto)
             │
             ▼
       FastAPI Backend
      ├── Data Validation
      ├── ML Inference
      ├── SQLite Storage
      └── Health Monitoring
             │
             ▼
       SQLite Database
             │
             ▼
    Streamlit Live Dashboard
```

---

## 🛠️ Tech Stack

| Category            | Technologies              |
| ------------------- | ------------------------- |
| 💻 Backend          | FastAPI, Paho MQTT        |
| 🤖 Machine Learning | Isolation Forest, XGBoost |
| 🗄️ Database        | SQLite                    |
| 📊 Dashboard        | Streamlit, Plotly         |
| 🌐 Networking       | Mosquitto MQTT, Tailscale |
| 🔧 Hardware         | ESP32, BME690             |

---

## 📂 Project Structure

```text
IoT_Weather_Project/
│
├── main.py                  # FastAPI Backend
├── dashboard.py             # Streamlit Dashboard
├── weather_data.db          # SQLite Database
├── anomaly_model.pkl
├── temperature_model.pkl
├── requirements.txt
└── README.md
```

---

## ✨ Dashboard Features

* 🌡️ Live Temperature, Humidity & Pressure
* 📈 Historical Trends
* 🚨 AI Anomaly Alerts
* 🤖 Temperature Prediction
* 📊 Model Confidence Score
* 📉 Mean Absolute Error (MAE)
* 📡 Device Status Monitoring
* 🔄 Auto Refresh
* 📥 CSV Export

---

## ⚙️ Getting Started

### 1️⃣ Clone the repository

```bash
git clone https://github.com/yourusername/IoT_Weather_Project.git
cd IoT_Weather_Project
```

### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Start the backend

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4️⃣ Launch the dashboard

```bash
streamlit run dashboard.py
```

---

## 📸 Dashboard Preview

> *Add screenshots or GIFs here.*

```
docs/
├── dashboard.png
├── trends.png
└── anomaly_detection.png
```

---

## 🎯 What's Next?

* 🥧 Raspberry Pi Edge Deployment
* 🔐 HTTPS & JWT Authentication
* 🐳 Docker Support
* ☁️ Cloud Deployment
* 🌦️ Weather API Integration
* 📡 Multi-node IoT Network
* 📈 Enhanced ML Models

---

## ⭐ Why This Project?

This project demonstrates practical experience with:

* Embedded Systems
* IoT Communication (MQTT)
* Backend Development
* REST APIs
* Machine Learning Integration
* Data Visualization
* Database Design
* Distributed System Architecture

It is designed as a complete end-to-end IoT application, combining hardware, software, networking, and machine learning into a single system.

