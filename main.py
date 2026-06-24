import os
import json
import sqlite3
import paho.mqtt.client as mqtt
from datetime import datetime
from dotenv import load_dotenv
import time

# --- CONFIG ---
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "weather_data.db")
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASS")
TOPIC = "weather/telemetry"

C_GREEN, C_RED, C_RESET = "\033[92m", "\033[91m", "\033[0m"

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            timestamp TEXT, 
            temperature REAL, 
            humidity REAL, 
            pressure REAL
        )
    """)
    conn.commit()
    conn.close()
    print(f"{C_GREEN}✅ [DATABASE] Table 'telemetry' is ready.{C_RESET}")

def save_to_database(temp, hum, press):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.execute(
            "INSERT INTO telemetry (timestamp, temperature, humidity, pressure) VALUES (?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), temp, hum, press)
        )
        conn.commit()
        conn.close()
        print(f"{C_GREEN}🟢 [SAVE] T: {temp}°C | H: {hum}% | P: {press}hPa{C_RESET}")
    except Exception as e:
        print(f"{C_RED}🔴 [DB ERROR] {e}{C_RESET}")

# --- MQTT CALLBACKS ---
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"🔵 Connected to MQTT Broker! Subscribing to {TOPIC}...")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    try:
        raw = msg.payload.decode().strip()
        data = json.loads(raw)
        
        # Strict data parsing - drop incomplete payloads
        if "temperature" not in data or "humidity" not in data or "pressure" not in data:
            print(f"{C_RED}⚠️ [DATA REJECTED] Missing keys in payload: {raw}{C_RESET}")
            return
            
        temp = float(data["temperature"])
        hum = float(data["humidity"])
        press = float(data["pressure"])
        
        save_to_database(temp, hum, press)
    except Exception as e:
        print(f"{C_RED}❌ [ERROR] Failed to parse message: {e}{C_RESET}")

# --- MAIN ENGINE ---
def start_engine():
    init_db()
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
    client.on_connect = on_connect
    client.on_message = on_message
    
    print("🚀 Starting Minimal Engine...")
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            print(f"{C_RED}🔴 Connection failed: {e}. Retrying in 5s...{C_RESET}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        start_engine()
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}🛑 Engine stopped by user.{C_RESET}")