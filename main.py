import os
import json
import sqlite3
import time
import pickle
import threading
from collections import deque, defaultdict
from datetime import datetime
from contextlib import contextmanager
from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError
import paho.mqtt.client as mqtt
import pandas as pd
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "weather_data.db")
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASS")
DEAD_LETTER_LOG = os.path.join(BASE_DIR, "rejected_payloads.log")

C_GREEN, C_CYAN, C_YELLOW, C_RED, C_RESET = "\033[92m", "\033[96m", "\033[93m", "\033[91m", "\033[0m"

# --- GLOBAL STATE ---
start_time = time.time()
system_state = {
    "mqtt_connected": False,
    "esp32_online": False,
}
ANOMALY_MODEL = None
FORECAST_MODEL = None
ANOMALY_MODEL_PATH = os.path.join(BASE_DIR, "anomaly_model.pkl")
FORECAST_MODEL_PATH = os.path.join(BASE_DIR, "forecast_model.pkl")

mqtt_client = None

# Per-sensor historical buffer for ML (keeps last 5 readings)
historical_buffers = defaultdict(lambda: deque(maxlen=5))

# --- MODELS ---
class WeatherPayload(BaseModel):
    sensor_id: str = Field(..., min_length=1, description="Unique identifier for the sensor")
    temperature: float = Field(..., ge=-40.0, le=60.0)
    humidity: float = Field(..., ge=0.0, le=100.0)
    pressure: float = Field(..., ge=300.0, le=1100.0)

# --- DATABASE ---
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                temperature REAL,
                humidity REAL,
                pressure REAL,
                is_anomaly INTEGER,
                predicted_temp_next_hour REAL,
                confidence_score REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sensor_time ON telemetry(sensor_id, timestamp);")
        conn.commit()
        conn.close()
        print(f"{C_GREEN}✅ [DATABASE] SQLite ready.{C_RESET}")
    except Exception as e:
        print(f"{C_RED}🔴 [DB ERROR] Initialization failed: {e}{C_RESET}")

def save_to_database(data: WeatherPayload, is_anomaly: int, pred_temp: float, conf: float):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        conn.execute("""
            INSERT INTO telemetry (sensor_id, temperature, humidity, pressure, is_anomaly, predicted_temp_next_hour, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data.sensor_id, data.temperature, data.humidity, data.pressure, is_anomaly, pred_temp, conf))
        conn.commit()
        conn.close()
        
        timestamp_str = datetime.now().strftime("%H:%M:%S")
        print(f"{C_GREEN}🟢 [SAVE - {timestamp_str}] ID: {data.sensor_id} | T: {data.temperature}°C | H: {data.humidity}% | Anomaly: {bool(is_anomaly)}{C_RESET}")
    except Exception as e:
        print(f"{C_RED}🔴 [DB ERROR] Write failed: {e}{C_RESET}")

def log_dead_letter(reason: str, raw_payload: str):
    try:
        with open(DEAD_LETTER_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] REASON: {reason} | PAYLOAD: {raw_payload}\n")
    except Exception:
        pass

# --- MACHINE LEARNING ---
def load_ml_models():
    global ANOMALY_MODEL, FORECAST_MODEL
    
    if os.path.exists(ANOMALY_MODEL_PATH):
        try:
            with open(ANOMALY_MODEL_PATH, "rb") as f:
                ANOMALY_MODEL = pickle.load(f)
            print(f"{C_GREEN}🤖 [ML BOOT] anomaly_model.pkl loaded.{C_RESET}")
            if hasattr(ANOMALY_MODEL, "feature_names_in_"):
                print(f"{C_CYAN}📋 Anomaly model expects features: {list(ANOMALY_MODEL.feature_names_in_)}{C_RESET}")
        except Exception as e:
            print(f"{C_RED}🔴 [ML BOOT ERROR] Anomaly model failed: {e}{C_RESET}")
    else:
        print(f"{C_YELLOW}⚠️ [ML BOOT] anomaly_model.pkl not found. Using mathematical fallback.{C_RESET}")
        
    if os.path.exists(FORECAST_MODEL_PATH):
        try:
            with open(FORECAST_MODEL_PATH, "rb") as f:
                FORECAST_MODEL = pickle.load(f)
            print(f"{C_GREEN}🤖 [ML BOOT] forecast_model.pkl loaded.{C_RESET}")
            if hasattr(FORECAST_MODEL, "feature_names_in_"):
                print(f"{C_CYAN}📋 Forecast model expects features: {list(FORECAST_MODEL.feature_names_in_)}{C_RESET}")
        except Exception as e:
            print(f"{C_RED}🔴 [ML BOOT ERROR] Forecast model failed: {e}{C_RESET}")
    else:
        print(f"{C_YELLOW}⚠️ [ML BOOT] forecast_model.pkl not found. Using mathematical fallback.{C_RESET}")

def execute_ml_inference(data: WeatherPayload):
    buffer = historical_buffers[data.sensor_id]
    buffer.append({
        "temperature": data.temperature,
        "humidity": data.humidity,
        "pressure": data.pressure,
        "timestamp": datetime.now()
    })
    
    # Reliable fallback (always safe)
    is_anomaly = 1 if (data.temperature > 40 or data.temperature < -10 or 
                       data.humidity > 95 or data.humidity < 5 or 
                       data.pressure < 950 or data.pressure > 1050) else 0
    predicted_temp_next_hour = round(data.temperature * 1.02, 2)
    confidence_score = 60.0

    # Try ML only if models are loaded and we have enough history
    if len(buffer) >= 5 and (ANOMALY_MODEL is not None or FORECAST_MODEL is not None):
        try:
            df_hist = pd.DataFrame(list(buffer))
            df_hist['hour'] = pd.to_datetime(df_hist['timestamp']).dt.hour
            df_hist['temp_rolling_mean'] = df_hist['temperature'].rolling(3).mean().bfill()
            df_hist['hum_rolling_mean'] = df_hist['humidity'].rolling(3).mean().bfill()
            df_hist['temp_diff'] = df_hist['temperature'].diff().bfill()
            
            latest_features = df_hist.iloc[[-1]]   # Keep as DataFrame (important!)
            
            if ANOMALY_MODEL is not None:
                pred = ANOMALY_MODEL.predict(latest_features)
                is_anomaly = 1 if int(pred[0]) == -1 else 0
                
            if FORECAST_MODEL is not None:
                pred = FORECAST_MODEL.predict(latest_features)
                predicted_temp_next_hour = round(float(pred[0]), 2)
                
        except Exception as e:
            print(f"{C_YELLOW}⚠️ ML inference failed (using fallback): {e}{C_RESET}")
                
    return is_anomaly, predicted_temp_next_hour, confidence_score

# --- MQTT CLIENT (THREADED) ---
def on_connect(client, userdata, flags, reason_code, properties):
    system_state["mqtt_connected"] = True
    print(f"{C_CYAN}🔵 [MQTT] Connected to Broker. Subscribing to weather/#...{C_RESET}")
    client.subscribe("weather/#")

def on_disconnect(client, userdata, flags, reason_code, properties):
    system_state["mqtt_connected"] = False
    print(f"{C_YELLOW}⚠️ [MQTT] Disconnected. Reconnecting...{C_RESET}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        raw_payload = msg.payload.decode().strip()
        
        # Handle ESP32 Status Topic
        if topic == "weather/status":
            system_state["esp32_online"] = (raw_payload.lower() == "online")
            status_color = C_GREEN if system_state["esp32_online"] else C_YELLOW
            print(f"{status_color}📡 [ESP32 STATUS] {raw_payload.upper()}{C_RESET}")
            return
            
        # Parse Telemetry
        data_dict = json.loads(raw_payload)
        val = WeatherPayload(**data_dict)
        
        # Execute ML & Save
        anomaly_flag, predicted_t, conf_score = execute_ml_inference(val)
        save_to_database(val, anomaly_flag, predicted_t, conf_score)
        
    except json.JSONDecodeError as e:
        print(f"{C_YELLOW}⚠️ [JSON ERROR] {e}{C_RESET}")
        log_dead_letter(f"JSONDecodeError: {e}", msg.payload.decode(errors="ignore"))
    except ValidationError as ve:
        err_msg = ve.errors()[0]['msg']
        print(f"{C_RED}❌ [DATA REJECTED] {err_msg}{C_RESET}")
        log_dead_letter(f"ValidationError: {err_msg}", msg.payload.decode(errors="ignore"))
    except Exception as e:
        print(f"{C_RED}🔴 [ERROR] Processing failed: {e}{C_RESET}")

def mqtt_background_loop():
    global mqtt_client
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    
    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_forever()
        except Exception as e:
            print(f"{C_RED}🔴 [MQTT NETWORK] Connection failed: {e}. Retrying in 5s...{C_RESET}")
            time.sleep(5)

# --- FASTAPI APP ---
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    load_ml_models()
    mqtt_thread = threading.Thread(target=mqtt_background_loop, daemon=True, name="MQTT_Thread")
    mqtt_thread.start()
    yield
    # Shutdown
    print(f"\n{C_YELLOW}🛑 Shutting down engine.{C_RESET}")
    global mqtt_client
    if mqtt_client and mqtt_client.is_connected():
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

app = FastAPI(title="Synchronous IoT Engine", lifespan=lifespan)

@app.get("/api/health")
def health_check():
    # Verify the background thread is alive
    thread_alive = any(t.name == "MQTT_Thread" for t in threading.enumerate())
    engine_status = "online" if thread_alive else "offline"
    
    return {
        "status": "healthy",
        "engine_status": engine_status,
        "system_uptime_seconds": round(time.time() - start_time, 1)
    }

# Run via: uvicorn main:app --host 0.0.0.0 --port 8000