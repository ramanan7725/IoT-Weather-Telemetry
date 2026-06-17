import sqlite3
from datetime import datetime, timedelta
import random

DB_FILE = "weather_data.db"

def backfill_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Ensure table exists
    cursor.execute("""CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL NOT NULL,
        humidity REAL NOT NULL,
        pressure REAL NOT NULL,
        is_anomaly INTEGER DEFAULT 0,
        predicted_temp_next_hour REAL DEFAULT 0.0,
        confidence_score REAL DEFAULT 95.0
    )""")
    
    start_date = datetime(2026, 6, 8, 0, 0, 0)
    end_date = datetime(2026, 6, 15, 23, 59, 59)
    
    current = start_date
    inserted = 0
    
    while current <= end_date:
        # 24 points per day (hourly)
        for hour in range(24):
            ts = current + timedelta(hours=hour)
            
            # Realistic variations (base + daily cycle + noise)
            base_temp = 22 + 8 * (hour - 12) / 12  # diurnal cycle
            temp = round(base_temp + random.uniform(-3, 3), 2)
            hum = round(45 + random.uniform(-15, 15), 1)
            pres = round(1010 + random.uniform(-8, 8), 1)
            
            # Occasional anomalies
            is_anomaly = 1 if random.random() < 0.08 or temp > 38 or temp < 8 else 0
            
            pred_temp = round(temp + random.uniform(-1.5, 2.0), 2)
            conf = round(random.uniform(82, 99), 1)
            
            cursor.execute("""INSERT INTO telemetry 
                (timestamp, temperature, humidity, pressure, is_anomaly, predicted_temp_next_hour, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                (ts.strftime("%Y-%m-%d %H:%M:%S"), temp, hum, pres, is_anomaly, pred_temp, conf))
            
            inserted += 1
            if inserted % 100 == 0:
                print(f"Inserted {inserted} records...")
        
        current += timedelta(days=1)
    
    conn.commit()
    conn.close()
    print(f"✅ Backfill complete. Inserted {inserted} records from June 8 to June 15, 2026.")

if __name__ == "__main__":
    backfill_data()