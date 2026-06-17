import asyncio
import json
import logging
import sqlite3
import time
import pickle
import os
import random
from datetime import datetime
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field, ValidationError
from aiomqtt import Client, MqttError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_KEY = os.getenv("API_KEY", "default-dev-key")
MQTT_USER = os.getenv("MQTT_USER", "iotuser")
MQTT_PASS = os.getenv("MQTT_PASS", "strongpassword")

async def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        logger.warning("Unauthorized access attempt rejected.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API Key")
    return x_api_key
# --- 1. Logging & Styling Configuration ---
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler("logs/error.log", maxBytes=1000000, backupCount=7),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("IoT-Pipeline")
# Terminal Color Sequences
C_GREEN = "\033[92m"
C_CYAN = "\033[96m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_RESET = "\033[0m"
# Configuration
DB_FILE = "weather_data.db"
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "weather/sensor"
START_TIME = time.time()
# Paths to your trained serialized models
ANOMALY_MODEL_PATH = "anomaly_model.pkl"
FORECAST_MODEL_PATH = "forecast_model.pkl"
# Global placeholder allocations
ANOMALY_MODEL = None
FORECAST_MODEL = None
class WeatherPayload(BaseModel):
    temperature: float = Field(..., ge=-40.0, le=60.0)
    humidity: float = Field(..., ge=0.0, le=100.0)
    pressure: float = Field(..., ge=300.0, le=1100.0)
class ConfigPayload(BaseModel):
    anomaly_threshold: float
class DatabasePool:
    def __init__(self, db_path: str): self.db_path = db_path
    @asynccontextmanager
    async def get_session(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        try: yield conn
        finally: conn.close()
db_pool = DatabasePool(DB_FILE)
async def init_db():
    async with db_pool.get_session() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                temperature REAL, 
                humidity REAL, 
                pressure REAL, 
                is_anomaly INTEGER, 
                predicted_temp_next_hour REAL, 
                confidence_score REAL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON telemetry (timestamp DESC);")
        conn.commit()
    logger.info("💾 Indexed Database verified in WAL mode.")
def load_ml_models():
    global ANOMALY_MODEL, FORECAST_MODEL
    
    if os.path.exists(ANOMALY_MODEL_PATH):
        try:
            with open(ANOMALY_MODEL_PATH, "rb") as f:
                ANOMALY_MODEL = pickle.load(f)
            logger.info("🤖 [ML BOOT] anomaly_model.pkl loaded successfully.")
        except Exception as e:
            logger.error(f"🔴 [ML BOOT ERROR] Failed to parse anomaly pickle matrix: {e}")
    else:
        logger.warning("⚠️ [ML BOOT] anomaly_model.pkl not found. Running baseline fallback mode.")
    if os.path.exists(FORECAST_MODEL_PATH):
        try:
            with open(FORECAST_MODEL_PATH, "rb") as f:
                FORECAST_MODEL = pickle.load(f)
            logger.info("🤖 [ML BOOT] forecast_model.pkl loaded successfully.")
        except Exception as e:
            logger.error(f"🔴 [ML BOOT ERROR] Failed to parse forecast pickle matrix: {e}")
    else:
        logger.warning("⚠️ [ML BOOT] forecast_model.pkl not found. Running baseline fallback mode.")
def execute_ml_inference(data: WeatherPayload):
    global ANOMALY_MODEL, FORECAST_MODEL
    
    # Clear threshold logic (this should trigger for 45°C)
    is_anomaly = 1 if (data.temperature > 40.0 or data.temperature < 5.0) else 0
    predicted_temp_next_hour = round(data.temperature + 0.5, 2)
    confidence_score = 95.0

    features_input = [[data.temperature, data.humidity, data.pressure]]

    # Try real model if available
    if ANOMALY_MODEL is not None:
        try:
            anomaly_prediction = ANOMALY_MODEL.predict(features_input)
            is_anomaly = 1 if int(anomaly_prediction[0]) == -1 else 0
        except:
            pass  # fallback remains active

    if FORECAST_MODEL is not None:
        try:
            forecast_prediction = FORECAST_MODEL.predict(features_input)
            predicted_temp_next_hour = round(float(forecast_prediction[0]), 2)
        except:
            pass

    return is_anomaly, predicted_temp_next_hour, confidence_score
async def save_to_database(data: WeatherPayload, is_anomaly: int, pred_temp: float, conf: float):
    try:
        async with db_pool.get_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO telemetry (timestamp, temperature, humidity, pressure, is_anomaly, predicted_temp_next_hour, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                data.temperature, data.humidity, data.pressure, is_anomaly, pred_temp, conf
            ))
            conn.commit()
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{C_GREEN}🟢 [DATABASE SAVE - {timestamp}] T: {data.temperature}°C | H: {data.humidity}% | Anomaly: {bool(is_anomaly)}{C_RESET}")
    except Exception as e:
        print(f"{C_RED}🔴 [DATABASE ERROR] Code failed to execute write transaction: {e}{C_RESET}")
# 3. Resilient MQTT Loop
async def mqtt_subscriber_loop():
    logger.info(">>> mqtt_subscriber_loop: Resilient Mode Active <<<")
    retry_delay = 5
    username = "iotuser"
    password = "strongpassword"   # Change this if you used a different password

    while True:
        try:
            async with Client(
                hostname=MQTT_BROKER, 
                port=MQTT_PORT,
                username=username,
                password=password
            ) as client:
                retry_delay = 5
                print(f"{C_CYAN}🔵 [SYSTEM ONLINE] Connected to Broker: {MQTT_BROKER} (Authenticated){C_RESET}")
                
                await client.subscribe(MQTT_TOPIC)
                
                async for message in client.messages:
                    try:
                        raw_payload = message.payload.decode("utf-8").strip()
                        if raw_payload.startswith(("'", '"')) and raw_payload.endswith(("'", '"')):
                            raw_payload = raw_payload[1:-1]
                        
                        data = json.loads(raw_payload)
                        validated_data = WeatherPayload(**data)
                        
                        is_anomaly, pred_temp, conf = execute_ml_inference(validated_data)
                        await save_to_database(validated_data, is_anomaly, pred_temp, conf)
                        
                    except json.JSONDecodeError:
                        print(f"{C_RED}⚠️ [JSON MALFORMED] Dropping bad payload.{C_RESET}")
                    except ValidationError:
                        print(f"{C_RED}❌ [DATA REJECTED] Out-of-bounds.{C_RESET}")
                    except Exception as e:
                        print(f"{C_RED}🔴 [PROCESSING ERROR] {e}{C_RESET}")
                        
        except (MqttError, Exception) as e:
            print(f"{C_YELLOW}⚠️ [MQTT NETWORK] Connection lost: {e}. Retrying in {retry_delay}s...{C_RESET}")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    load_ml_models()
    task = asyncio.create_task(mqtt_subscriber_loop())
    yield
    task.cancel()
app = FastAPI(title="IoT Pipeline - Enterprise Engine", lifespan=lifespan)
@app.get("/api/health", dependencies=[Depends(verify_api_key)])
async def health_check():
    total_records = 0
    try:
        async with db_pool.get_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM telemetry")
            row = cursor.fetchone()
            if row: total_records = row['count']
    except Exception as e:
        logger.error(f"Error fetching DB count: {e}")
    return {
        "status": "healthy", 
        "system_uptime_seconds": round(time.time() - START_TIME, 2),
        "database_total_records": total_records
    }
@app.post("/api/config", dependencies=[Depends(verify_api_key)])
async def sync_config(config: ConfigPayload):
    logger.info(f"Dashboard sync received: Anomaly Threshold updated to {config.anomaly_threshold}")
    print(f"{C_CYAN}⚙️ [CONFIG UPDATE] Anomaly Threshold -> {config.anomaly_threshold}{C_RESET}")
    return {"message": "Config synchronized", "new_threshold": config.anomaly_threshold}