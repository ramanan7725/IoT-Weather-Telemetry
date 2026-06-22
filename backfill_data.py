import sqlite3
import random
from datetime import datetime, timedelta

DB_FILE = "weather_data.db"

def simulate_day():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Clear existing data to ensure a fresh, clean graph
    cursor.execute("DELETE FROM telemetry")
    
    start_time = datetime.now() - timedelta(days=1)
    print("📈 Generating correlated 24-hour telemetry...")
    
    # Generate 2880 records (1 record every 30 seconds for 24 hours)
    for i in range(2880):
        ts = start_time + timedelta(seconds=i * 30)
        hour = ts.hour + ts.minute / 60
        
        # 1. Temperature: Sine wave peak at 2:00 PM (14.0)
        base_temp = 22 + 8 * (-( (hour-14)**2 ) / 72 + 1)
        temp = round(base_temp + random.uniform(-0.5, 0.5), 2)
        
        # 2. Humidity: Inverse to temperature (General rule of thumb)
        humidity = round(65 - (temp - 20) * 1.2 + random.uniform(-2, 2), 2)
        humidity = max(20, min(95, humidity)) # Keep within 20-95%
        
        # 3. Pressure: Slowly changing atmospheric pressure
        pressure = round(1013 + 3 * (-( (hour-12)**2 ) / 144) + random.uniform(-0.5, 0.5), 2)
        
        # 4. Inject Spikes/Dips (Anomalies) - 2% chance
        is_anomaly = 0
        if random.random() < 0.02:
            temp += random.choice([12.0, -12.0])
            humidity += random.choice([20.0, -20.0])
            pressure += random.choice([15.0, -15.0])
            is_anomaly = 1
            
        cursor.execute("""
            INSERT INTO telemetry 
            (timestamp, temperature, humidity, pressure, is_anomaly)
            VALUES (?, ?, ?, ?, ?)
        """, (ts.strftime("%Y-%m-%d %H:%M:%S"), temp, humidity, pressure, is_anomaly))
        
    conn.commit()
    conn.close()
    print("✅ Data simulation complete.")

if __name__ == "__main__":
    simulate_day()