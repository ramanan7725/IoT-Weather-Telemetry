import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError
from aiomqtt import Client
import aiosqlite
from dotenv import load_dotenv

# --- CONFIG ---
load_dotenv()
DB_FILE = "weather_data.db"
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
C_GREEN, C_CYAN, C_YELLOW, C_RED, C_RESET = "\033[92m", "\033[96m", "\033[93m", "\033[91m", "\033[0m"
DEAD_LETTER_LOG = "rejected_payloads.log"

# --- STATE & CONCURRENCY ---
system_state = {
    "mqtt_connected": False,
    "esp32_online": False,
    "packet_counter": 0,
    "total_latency_ms": 0.0,
    "last_metrics": {"pps": 0, "avg_latency": 0.0}
}
state_lock = asyncio.Lock()
payload_queue = asyncio.Queue()

# --- MODELS ---
class WeatherPayload(BaseModel):
    temperature: float = Field(..., ge=-40.0, le=60.0)
    humidity: float = Field(..., ge=0.0, le=100.0)
    pressure: float = Field(..., ge=300.0, le=1100.0)

# --- DATABASE ---
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, 
                temperature REAL, humidity REAL, pressure REAL, is_anomaly INTEGER,
                predicted_temp_next_hour REAL, confidence_score REAL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON telemetry(timestamp);")
        await db.commit()
    print(f"{C_GREEN}✅ [DATABASE] Table 'telemetry' is ready (aiosqlite).{C_RESET}")

def detect_anomaly(data: WeatherPayload):
    # Dynamic anomaly detection logic (extreme bounds)
    if data.temperature > 40.0 or data.temperature < -10.0: return 1
    if data.humidity > 95.0 or data.humidity < 5.0: return 1
    if data.pressure < 950.0 or data.pressure > 1050.0: return 1
    return 0

def log_dead_letter(reason: str, raw_payload: str):
    with open(DEAD_LETTER_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] REASON: {reason} | PAYLOAD: {raw_payload}\n")

# --- BACKGROUND WORKER (Decoupled Logic) ---
async def processing_worker_loop():
    print(f"{C_CYAN}⚙️ [WORKER] Processing background task started.{C_RESET}")
    while True:
        item = await payload_queue.get()
        start_time, data = item
        
        try:
            val = WeatherPayload(**data)
            
            # Predictive Logic
            anomaly_flag = detect_anomaly(val)
            predicted_t = round(val.temperature + (val.temperature * 0.02), 2)
            
            # Non-blocking DB write
            async with aiosqlite.connect(DB_FILE, timeout=20) as db:
                await db.execute("""
                    INSERT INTO telemetry (timestamp, temperature, humidity, pressure, is_anomaly, predicted_temp_next_hour, confidence_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), val.temperature, val.humidity, val.pressure, anomaly_flag, predicted_t, 95.0))
                await db.commit()
            
            # Calculate processing latency
            latency_ms = (time.time() - start_time) * 1000.0
            
            async with state_lock:
                system_state["packet_counter"] += 1
                system_state["total_latency_ms"] += latency_ms
                
        except ValidationError as ve:
            err_msg = ve.errors()[0]['msg']
            print(f"{C_RED}❌ [DATA REJECTED] {err_msg}{C_RESET}")
            log_dead_letter(f"ValidationError: {err_msg}", json.dumps(data))
        except Exception as e:
            print(f"{C_YELLOW}⚠️ [WORKER ERROR] {e}{C_RESET}")
            log_dead_letter(f"WorkerError: {e}", json.dumps(data))
        finally:
            payload_queue.task_done()

# --- MQTT INGESTION ---
async def mqtt_subscriber_loop():
    reconnect_delay = 5
    while True:
        try:
            async with Client(hostname=MQTT_BROKER, port=MQTT_PORT) as client:
                async with state_lock:
                    system_state["mqtt_connected"] = True
                reconnect_delay = 5
                print(f"{C_CYAN}🔵 [SYSTEM ONLINE] Connected to MQTT Broker{C_RESET}")
                await client.subscribe("weather/#")
                async for message in client.messages:
                    try:
                        if message.topic.value == "weather/status":
                            status_msg = message.payload.decode().strip().lower()
                            async with state_lock:
                                system_state["esp32_online"] = (status_msg == "online")
                            continue
                        
                        # Just ingest and parse raw JSON quickly
                        raw_str = message.payload.decode().strip()
                        data = json.loads(raw_str)
                        
                        # Immediately queue it for the worker
                        await payload_queue.put((time.time(), data))
                        
                    except json.JSONDecodeError as e:
                        print(f"{C_YELLOW}⚠️ [JSON ERROR] {e}{C_RESET}")
                        log_dead_letter(f"JSONDecodeError: {e}", message.payload.decode(errors="ignore"))
                    except Exception as e: 
                        print(f"{C_YELLOW}⚠️ [MQTT LOOP WARN] {e}{C_RESET}")
        except Exception as e:
            async with state_lock:
                system_state["mqtt_connected"] = False
            print(f"{C_RED}🔴 [ERROR] MQTT Connection Lost: {e}. Retrying in {reconnect_delay}s...{C_RESET}")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60)

async def metrics_aggregator_loop():
    while True:
        await asyncio.sleep(1)
        async with state_lock:
            pps = system_state["packet_counter"]
            total_lat = system_state["total_latency_ms"]
            
            avg_lat = (total_lat / pps) if pps > 0 else system_state["last_metrics"]["avg_latency"]
            system_state["last_metrics"] = {"pps": pps, "avg_latency": round(avg_lat, 2)}
            
            system_state["packet_counter"] = 0
            system_state["total_latency_ms"] = 0.0

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task1 = asyncio.create_task(mqtt_subscriber_loop())
    task2 = asyncio.create_task(processing_worker_loop())
    task3 = asyncio.create_task(metrics_aggregator_loop())
    yield
    task1.cancel()
    task2.cancel()
    task3.cancel()

app = FastAPI(title="IoT Pipeline", lifespan=lifespan)

@app.get("/api/health")
async def health_check():
    async with state_lock:
        return {
            "status": "online" if system_state["mqtt_connected"] else "offline",
            "esp32_status": "online" if system_state["esp32_online"] else "offline"
        }

@app.get("/api/metrics")
async def get_metrics():
    async with state_lock:
        return system_state["last_metrics"]