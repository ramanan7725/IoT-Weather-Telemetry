# 🌤️ IoT Weather Monitoring System

> A distributed, real-time weather monitoring system built from the ground up. ESP32 sensors → MQTT → Machine Learning → Live Dashboard. Currently **Project 1A** (laptop local). Evolving toward **Project 1** (Raspberry Pi edge) and **Project 1 Pro** (multi-node fusion).

**Status:** 6.5/10 (MVP functional. ML models pending real hardware validation.)

---

## 📖 The Story

This project started with a simple question: *Can I build a real IoT system that's defensible in interviews?*

Not a toy project. Not a tutorial clone. Something where every architectural decision answers "why," and every line of code proves something.

**The journey:**
- Started with Flask → switched to FastAPI (type safety, built-in validation)
- Started with async MQTT → switched to sync threading (single sensor doesn't need async overhead)
- Trained ML models on Kaggle data → discovered they're broken on real sensor inputs (+320% error on edge cases)
- Built the whole system LOCAL before touching deployment (you need hardware working before cloud makes sense)

This README documents the what, why, and how of each decision.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     PROJECT 1A (Current)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ESP32 (WROOM-32)                                              │
│  ├─ BME690 Sensor (ordered, hardware blocker)                 │
│  ├─ BH1750 Light Sensor (planned)                             │
│  └─ Publishes MQTT every 5 minutes                            │
│           ↓ (WiFi + Tailscale VPN)                            │
│  Mosquitto Broker (Windows, Tailscale IP: 100.110.195.55)     │
│  └─ Binds on all interfaces (0.0.0.0:1883)                   │
│           ↓ (MQTT Subscribe)                                   │
│  FastAPI Backend (uvicorn, localhost:8000)                    │
│  ├─ paho-mqtt threaded client                                │
│  ├─ ML inference (IsolationForest + XGBoost)                 │
│  ├─ Exponential backoff MQTT reconnection                     │
│  ├─ /api/health (system status)                              │
│  ├─ /api/metrics/mae (accuracy tracking)                      │
│  └─ /api/ml/performance (degradation monitoring)              │
│           ↓ (SQLite WAL)                                       │
│  SQLite Database                                               │
│  └─ Read-only for dashboard (prevents lock contention)        │
│           ↓ (REST API)                                         │
│  Streamlit Dashboard (localhost:8501)                         │
│  ├─ Auto-refresh every 35 seconds (st_autorefresh)           │
│  ├─ Smart polling: 3-min full scan + 35s partial updates     │
│  ├─ Multi-sensor support (dropdown selector)                  │
│  ├─ Plotly real-time charts                                   │
│  ├─ Anomaly visualization                                      │
│  └─ CSV export for analysis                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Why | Trade-off |
|----------|-----|-----------|
| **FastAPI over Flask** | Type safety, Pydantic validation, async-ready | Slightly more boilerplate |
| **paho-mqtt over aiomqtt** | Single sensor = no async bottleneck; easier debugging | More verbose threading code |
| **Sync + daemon thread** | paho-mqtt is sync; wrapping in async defeats purpose | Mixing paradigms (acceptable at MVP) |
| **SQLite WAL mode** | Allows concurrent reads (dashboard) while backend writes | Slightly more disk I/O |
| **Streamlit dashboard** | Rapid prototyping, zero frontend complexity | Not ideal for scaling to 100s of dashboards |
| **Tailscale VPN** | Secure remote access; works on Project 1 (Pi phase) | Adds network dependency for 1A (local) |
| **Pickle models** | Quick, works; real risk is sklearn version mismatch | Switching to XGBoost JSON after retraining |

---

## 🛠️ Tech Stack

**Hardware:**
- ESP32-WROOM-32 (USB-C dev board, ~$5)
- BME690 (temperature, humidity, pressure; **on order**, BME280 failed)
- BH1750 light sensor (planned)

**Backend:**
- **FastAPI** – REST API, type hints, Pydantic validation
- **paho-mqtt** – MQTT client, synchronous, thread-safe
- **SQLite** – WAL mode for concurrent read/write
- **XGBoost** – Temperature forecasting (100 trees, depth 6)
- **scikit-learn** – IsolationForest anomaly detection, StandardScaler

**Frontend:**
- **Streamlit** – Dashboard, auto-refresh, Plotly charts
- **streamlit-autorefresh** – Smooth 35s refresh without blocking
- **Plotly** – Interactive subplots, anomaly markers

**Infrastructure:**
- **Mosquitto** – MQTT broker (Windows native)
- **Tailscale** – VPN (currently hardcoded, flexible for Project 1)
- **uvicorn** – ASGI server for FastAPI

**Development:**
- Python 3.10+ (Anaconda)
- Windows (D:\IoT_Weather_Project\)
- Versioned via retraining (model_version_history.json)

---

## 📊 Project Phases

### Phase 1A: Laptop Local (Current) ✅
- Single ESP32 sensor
- Laptop runs: Mosquitto + FastAPI + Streamlit
- No cloud, no Pi, no containerization
- **Goal:** Validate architecture with synthetic data, prepare for real sensor

**Status:** 6.5/10
- ✅ MQTT pub/sub working
- ✅ Backend + dashboard integrated
- ✅ ML inference pipeline built
- ❌ Hardware blocker (sensor broken, BME690 ordered)
- ⚠️ ML models weak (synthetic Kaggle data)

### Phase 1: Raspberry Pi Edge (Q3 2026)
- Mosquitto + FastAPI migrate to Pi Zero 2W
- ESP32 publishes to Pi (Tailscale or local network)
- Laptop runs dashboard only (connects to Pi remotely via Tailscale)
- Always-on edge processing

**Goal:** Always-on monitoring without laptop

### Phase 1 Pro: Multi-Node + Fusion (Q4 2026)
- Multiple ESP32 sensors (temp, humidity, light, CO2)
- Real-time data fusion with OpenWeatherMap API
- Advanced ML: spatial anomaly detection, weather pattern prediction
- Prometheus metrics, structured logging

**Goal:** Production-grade distributed IoT system

---

## 🤖 Machine Learning Strategy

### Current State (Synthetic Data - Not Production)
```
Models: XGBRegressor (temperature) + IsolationForest (anomaly)
Training Data: Kaggle weather dataset (synthetic, clean)
Problem: Completely breaks on real sensor data
  - Marks 35°C as anomaly (normal in Chennai June)
  - Predicts 21°C from 5°C input (+320% error)
  - Overfits to smooth, clean data
Result: 2.5/10 strength — placeholders only
```

### Real Data Strategy (Post-BME690 Arrival)

**Timeline:**
```
Day 2: Collect 500 real readings (41+ hours)
Week 1: Train models v1.0 on all data
        ├─ Anomaly: IsolationForest with StandardScaler
        ├─ Forecast: XGBRegressor (depth 6, L1/L2 reg)
        └─ Expected: MAE ±2°C

Week 2: Have 1,000 readings → Retrain v1.1
        └─ Expected: MAE ±1.2°C

Week 4: Have 2,000 readings → Retrain v1.2
        └─ Expected: MAE ±0.7°C

Month 2: Have 4,000 readings → Retrain v1.3
         └─ Expected: MAE ±0.5°C

Month 3+: Models plateau (diminishing returns)
          Weekly monitoring for degradation
```

### Why Cumulative Retraining (Not Weekly Window)

| Approach | Data Stability | Overfitting Risk | Generalization |
|----------|-----------------|-----------------|-----------------|
| Weekly window (last 7 days) | Volatile | HIGH | Poor |
| Cumulative (all time) | Stable | LOW | Excellent |

**Decision:** Retrain on ALL historical data whenever models degrade (MAE > 1.5°C). This:
- Averages sensor drift across time
- Captures multiple weather patterns
- Prevents overfitting to recent bias
- Models improve naturally as you collect more data

### Feature Engineering (Post-Retraining)

```python
# Raw features (3):
temperature, humidity, pressure

# Engineered features (7):
+ temp_lag1, temp_lag2, temp_lag3
+ temp_rolling_mean (3-reading window)
+ temp_rolling_std

# Result: 98.7% of model importance is temperature (as expected)
# Pressure and humidity are ~0.6% each (noise-dominated in synthetic data)
# Real data will likely show pressure/humidity mattering more
```

### Model Monitoring

```python
# Weekly check (manual, 5 minutes):
GET /api/ml/performance
→ {
    "mae": 0.65,
    "status": "healthy" | "degraded",
    "recommendation": "RETRAIN if mae > 2.0"
  }

# If MAE > 1.5°C AND have 1000+ samples: Trigger retraining
# If MAE < 1.0°C: Continue monitoring
```

---

## 🐛 Known Issues & Roadmap

### Fixed ✅
- ✅ Tailscale IP configured (100.110.195.55)
- ✅ Dashboard doesn't block on refresh (streamlit-autorefresh)
- ✅ Confidence score computed from prediction error
- ✅ MAE calculation correct (T[i+1] vs predicted[i])
- ✅ MQTT exponential backoff (prevents broker hammering)
- ✅ Sensor selection persists across refreshes
- ✅ Data freshness indicator (shows stale/offline status)

### Blocked on Hardware 🚧
- ⏳ Real ML model training (BME690 arrival)
- ⏳ Model retraining on cumulative data
- ⏳ Feature importance analysis (meaningful on real data only)

### Future (Not 1A) 📋
- [ ] Docker containerization (for Pi deployment)
- [ ] Prometheus metrics + Grafana
- [ ] Structured logging (JSON format, log rotation)
- [ ] XGBoost JSON format (instead of pickle)
- [ ] Multi-sensor support (code ready, needs hardware)
- [ ] OpenWeatherMap data fusion
- [ ] Tailscale integration (currently hardcoded IP)

---

## 📦 Setup & Usage

### Prerequisites
```powershell
# Python 3.10+
python --version

# Install dependencies
pip install fastapi uvicorn paho-mqtt pandas scikit-learn xgboost streamlit streamlit-autorefresh plotly python-dotenv

# Mosquitto (Windows)
# Download: https://mosquitto.org/download/
# Install to D:\Program Files\mosquitto\
```

### Configuration

Create `.env` in project root:
```env
MQTT_BROKER=100.110.195.55
MQTT_PORT=1883
MQTT_USER=
MQTT_PASS=
```

Or modify `main.py` directly (both work).

### Running

**Terminal 1: Mosquitto Broker**
```powershell
D:\Program Files\mosquitto\mosquitto.exe -c D:\Program Files\mosquitto\mosquitto.conf -v
# Output: "Listening on port 1883"
```

**Terminal 2: FastAPI Backend**
```powershell
cd D:\IoT_Weather_Project
uvicorn main:app --host 0.0.0.0 --port 8000
# Output: "Application startup complete"
```

**Terminal 3: Streamlit Dashboard**
```powershell
streamlit run dashboard.py
# Opens: http://localhost:8501
```

### Testing with Mock Data

```powershell
# Publish test MQTT message
mosquitto_pub -h 100.110.195.55 -t weather/telemetry -m '{
  "sensor_id": "sensor_01",
  "temperature": 25.5,
  "humidity": 60,
  "pressure": 1013
}'

# Or simulate ESP32 publishing every 5 mins
# Use a simple script in Arduino IDE → Serial Monitor
```

---

## 📈 Dashboard Features

- **Live Conditions:** Current temperature, humidity, pressure
- **AI Intelligence:** Forecast (next hour), anomaly status, confidence score, accuracy (MAE)
- **Historical Trends:** 3-panel chart (temp, humidity, pressure) with anomaly overlays
- **System Health:** API status, MQTT connection, ESP32 transmit status
- **Data Controls:**
  - Auto-refresh checkbox (35s interval)
  - Historical window slider (1-30 days)
  - Force refresh button
  - CSV download

---

## 🧠 Interview Talking Points

### What You Built
*"I designed a three-tier IoT system: ESP32 sensor → MQTT broker → FastAPI backend → SQLite database → Streamlit dashboard. Every architectural decision is justified. FastAPI for type safety; paho-mqtt because single-sensor MVPs don't need async overhead; SQLite WAL for concurrent read/write; Streamlit for rapid iteration."*

### Why These Choices
*"I deliberately chose synchronous patterns over pure async because the bottleneck isn't CPU—it's the 5-minute sensor interval. Adding async complexity would be premature optimization. The codebase is simple enough to debug when things break."*

### The ML Reality
*"ML models are currently trained on Kaggle synthetic data—they're placeholders. I validated this by testing edge cases: the model predicts 21°C from 5°C input (320% error). This proves synthetic data doesn't transfer. Once I collect real BME690 readings, I'll retrain on cumulative data. Expected improvement: MAE from ±2°C to ±0.5°C."*

### The Hardware Journey
*"BME280 failed (heat-damaged), replacement was defective (I2C returned 0x40 instead of 0x76). This taught me validation discipline: every new sensor gets three checks—I2C scanner, data stability test, MQTT integration. BME690 is on order; I have a strict validation protocol ready."*

### The Real Interview Win
*"This project shows I don't just code—I reason about systems. Every decision has a why. I'm comfortable with imperfection (weak ML models now) because the infrastructure is solid and improves with real data. That's production thinking."*

---

## 📁 Project Structure

```
D:\IoT_Weather_Project\
├── main.py                          # FastAPI backend + MQTT client
├── dashboard.py                     # Streamlit dashboard
├── weather_data.db                  # SQLite (WAL mode)
├── anomaly_model.pkl                # IsolationForest (Kaggle trained)
├── temperature_model.pkl            # XGBRegressor (Kaggle trained)
├── prepare_retraining_cumulative.py # Retraining script (ready to run)
├── ml_analysis.py                   # Model behavior analysis
├── .env                             # Config (MQTT broker, credentials)
├── model_version_history.json       # Retraining log
├── rejected_payloads.log            # Dead letter log (validation failures)
└── README.md                        # This file
```

---

## 🎯 What Makes This Portfolio-Ready

1. **Real Problem:** IoT is complex. Distributed systems matter.
2. **Real Decisions:** Not following a tutorial. Chose FastAPI, paho-mqtt, SQLite WAL—all justified.
3. **Real Constraints:** Hardware blocker is honest. Doesn't fake it.
4. **Real ML:** Knows that synthetic data is broken. Has a clear retraining strategy.
5. **Real Code:** No magic. Readable, commented, defensible.
6. **Real Project Management:** Has phases (1A → 1 → 1 Pro). Shows roadmap thinking.

---

## 🚀 Next Steps (Post-BME690 Arrival)

1. **Validate sensor:** I2C scanner must show 0x76 or 0x77
2. **Data stability test:** 10 consecutive reads, check for jitter
3. **MQTT integration:** Firmware loads sensor driver, publishes every 5 min
4. **Collect 500 readings:** ~41 hours on the desk (captures natural variation)
5. **Run retraining:** `python prepare_retraining_cumulative.py`
6. **Deploy models:** Update `anomaly_model.pkl` + `temperature_model.pkl`
7. **Validate on dashboard:** Check MAE, confidence scores, anomaly detection
8. **Document results:** Update README with real-data metrics
9. **Plan Phase 1:** Procure Raspberry Pi Zero 2W, Tailscale setup

---

## 📞 Questions for Interviewers

*"Ask me why I chose Streamlit over React. Or why SQLite WAL instead of PostgreSQL for an MVP. Or what I'd do differently if I had 10 sensors instead of 1. I have answers for all of it."*

---

## 📝 License

This project is part of a portfolio for ECE fresher interviews. Open source—feel free to fork, adapt, learn.

---

## 🙏 Acknowledgments

- **Espressif** (ESP32 documentation)
- **Mosquitto** (MQTT broker)
- **FastAPI** + **Streamlit** communities
- **scikit-learn** + **XGBoost** for ML frameworks
- **Ritchie Street, Chennai** (hardware sourcing)

---

**Built with discipline, not hype. Real IoT from the ground up.**

---

**Last Updated:** June 2026  
**Status:** 6.5/10 (Functional MVP, awaiting hardware validation)  
**Next Review:** Post-BME690 arrival
