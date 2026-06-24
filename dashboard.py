import os
import sqlite3
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "weather_data.db")
API_URL = "http://localhost:8000/api/health"

st.set_page_config(page_title="Weather Station", layout="wide", page_icon="🌤️")

# --- FETCH DATA ---
@st.cache_data(ttl=60)
def fetch_data(days=1):
    try:
        # Read-only connection to prevent locking the backend writes
        conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True, timeout=5)
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        
        # SECURE: Using parameterized queries to prevent SQL injection
        query = "SELECT * FROM telemetry WHERE timestamp >= ? ORDER BY timestamp DESC"
        df = pd.read_sql(query, conn, params=(cutoff_date,))
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

def check_backend_status():
    try:
        res = requests.get(API_URL, timeout=2).json()
        return res
    except:
        return {"engine_status": "offline", "mqtt_connected": False, "esp32_online": False}

# --- SIDEBAR UI ---
st.sidebar.title("🌤️ Weather Station")

# Status checking via FastAPI endpoint
status = check_backend_status()
if status["engine_status"] == "online":
    st.sidebar.success("🟢 API Engine: Online")
    if status["esp32_online"]:
        st.sidebar.success("🟢 Network: Transmitting")
    else:
        st.sidebar.warning("⚠️ Network: Idle")
else:
    st.sidebar.error("🔴 API Engine: Offline")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Force Refresh"):
    st.cache_data.clear()
    st.rerun()

days_to_fetch = st.sidebar.slider("Historical Window (Days)", 1, 30, 1)
df = fetch_data(days_to_fetch)

# --- MAIN DASHBOARD ---
if not df.empty:
    
    # 1. Multi-Sensor Selection
    if "sensor_id" in df.columns:
        sensors = df["sensor_id"].unique().tolist()
        selected_sensor = st.sidebar.selectbox("Select Sensor Device", sensors)
        df_sensor = df[df["sensor_id"] == selected_sensor]
        df_sensor = df_sensor.sort_values("timestamp").reset_index(drop=True)
    else:
        # Fallback if old schema
        df_sensor = df
        selected_sensor = "Legacy Sensor"
        
    st.title(f"Telemetry Dashboard: `{selected_sensor}`")
    
    if not df_sensor.empty:
        latest = df_sensor.iloc[0]
        
        # Detailed Per-Sensor Status
        try:
            last_timestamp = datetime.strptime(latest['timestamp'], "%Y-%m-%d %H:%M:%S")
            time_since_last = (datetime.now() - last_timestamp).total_seconds()
            if time_since_last < 300:
                st.caption(f"**Sensor Status**: 🟢 Online (Last seen {int(time_since_last)}s ago)")
            else:
                st.caption(f"**Sensor Status**: 🔴 Offline (Last seen {int(time_since_last/60)}m ago)")
        except:
            pass
        
        # 2. Key Metrics
        st.subheader("Live Conditions")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Temperature", f"{latest['temperature']} °C")
        col2.metric("Humidity", f"{latest['humidity']} %")
        col3.metric("Pressure", f"{latest['pressure']} hPa")
        
        # AI Forecast Metric
        if "predicted_temp_next_hour" in latest and pd.notna(latest["predicted_temp_next_hour"]):
            col4.metric("AI Forecast (Next Hr)", f"{latest['predicted_temp_next_hour']} °C")
            
        st.markdown("---")
        
        # 3. Interactive Charts (with Anomaly overlays)
        st.subheader("Historical Trends")
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                            subplot_titles=("Temperature (°C)", "Humidity (%)", "Pressure (hPa)"))
                            
        fig.add_trace(go.Scatter(x=df_sensor["timestamp"], y=df_sensor["temperature"], name="Temp", line=dict(color="#FF7F0E")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_sensor["timestamp"], y=df_sensor["humidity"], name="Humidity", line=dict(color="#1F77B4")), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_sensor["timestamp"], y=df_sensor["pressure"], name="Pressure", line=dict(color="#2CA02C")), row=3, col=1)
        
        # Highlight anomalies if column exists
        if "is_anomaly" in df_sensor.columns:
            anomalies = df_sensor[df_sensor["is_anomaly"] == 1]
            if not anomalies.empty:
                # Enhanced anomaly markers
                marker_style = dict(color="red", symbol="x", size=12, line=dict(color="white", width=2))
                fig.add_trace(go.Scatter(x=anomalies["timestamp"], y=anomalies["temperature"], mode="markers", marker=marker_style, name="Anomaly"), row=1, col=1)
                fig.add_trace(go.Scatter(x=anomalies["timestamp"], y=anomalies["humidity"], mode="markers", marker=marker_style, showlegend=False), row=2, col=1)
                fig.add_trace(go.Scatter(x=anomalies["timestamp"], y=anomalies["pressure"], mode="markers", marker=marker_style, showlegend=False), row=3, col=1)

        fig.update_layout(height=700, margin=dict(t=40, b=40))
        st.plotly_chart(fig, use_container_width=True)
        
        # 4. Raw Data Logs
        st.markdown("---")
        st.subheader("System Logs")
        st.dataframe(df_sensor, use_container_width=True, height=250)
        
        st.download_button("Download CSV", data=df_sensor.to_csv(index=False).encode('utf-8'), file_name=f"{selected_sensor}_data.csv", mime="text/csv")
        
    else:
        st.info("No data available for the selected sensor in this time range.")
else:
    st.info("No data found in the database. Please ensure the backend engine is running and hardware is transmitting.")