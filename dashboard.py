import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from streamlit_autorefresh import st_autorefresh
import logging
from datetime import datetime, timedelta, date, time
import io
import json
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY", "default-dev-key")
# Graceful imports for PDF reporting
try:
    from fpdf import FPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_FILE = "weather_data.db"
BACKEND_HEALTH_URL = "http://localhost:8000/api/health"
BACKEND_CONFIG_URL = "http://localhost:8000/api/config"

st.set_page_config(page_title="IoT Environmental Visual Station", page_icon="🌤️", layout="wide")

# --- 1. PREMIUM THEMING & UX ---
st.markdown("""
<style>
    /* Glassmorphism Metric Cards */
    div[data-testid="metric-container"] {
        background-color: rgba(28, 30, 38, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 5% 5% 5% 10%;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(10px);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=5)
def fetch_telemetry_batch(start_dt, end_dt):
    """Fetches telemetry data within a date range."""
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        query = "SELECT timestamp, temperature, humidity, pressure, is_anomaly, predicted_temp_next_hour, confidence_score FROM telemetry WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp DESC"
        df = pd.read_sql_query(query, conn, params=(start_dt.strftime('%Y-%m-%d %H:%M:%S'), end_dt.strftime('%Y-%m-%d %H:%M:%S')))
        conn.close()
        if not df.empty: 
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        logging.error(f"Database Read Failure: {e}")
        return pd.DataFrame()

def fetch_pipeline_health():
    try:
        response = requests.get(BACKEND_HEALTH_URL, headers={"X-API-Key": API_KEY}, timeout=1.5)
        if response.status_code == 200: 
            return response.json()
    except Exception as e: 
        logging.warning(f"Backend health check failed: {e}")
    return {"status": "offline", "system_uptime_seconds": 0.0, "database_total_records": "Unknown"}

def sync_config_to_backend(config_data):
    """Mocks sending a POST request to update backend thresholds."""
    try:
        # response = requests.post(BACKEND_CONFIG_URL, json=config_data, headers={"X-API-Key": API_KEY}, timeout=2.0)
        # if response.status_code == 200: return True
        # For now, we mock success
        logging.info(f"Mocked Backend Sync with config: {config_data}")
        return True
    except Exception as e:
        logging.error(f"Failed to sync config: {e}")
        return False

def generate_pdf_report(df, stats):
    """Generates a PDF report string/bytes using fpdf if available."""
    if not PDF_SUPPORT:
        return None
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="IoT Telemetry & Anomaly Report", ln=True, align='C')
    
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Summary KPIs", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Avg Temperature: {stats['temp_avg']} C", ln=True)
    pdf.cell(200, 10, txt=f"Avg Humidity: {stats['hum_avg']} %", ln=True)
    pdf.cell(200, 10, txt=f"Avg Pressure: {stats['press_avg']} hPa", ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Anomalies Found", ln=True)
    pdf.set_font("Arial", size=10)
    
    anomalies = df[df['is_anomaly'] == 1]
    if anomalies.empty:
        pdf.cell(200, 10, txt="No anomalies detected in this time range.", ln=True)
    else:
        for idx, row in anomalies.head(20).iterrows():
            pdf.cell(200, 8, txt=f"Time: {row['timestamp']} | Temp: {row['temperature']} | Hum: {row['humidity']}", ln=True)
            
    return pdf.output(dest='S').encode('latin-1', 'replace')

st.title("🌤️ IoT Environmental Telemetry & Predictive Analytics")
st.markdown("---")

health_metrics = fetch_pipeline_health()

with st.sidebar:
    st.markdown("### 🖥️ Ingestion Infrastructure")
    if health_metrics["status"] == "healthy":
        st.success("🟢 PIPELINE ENGINE: ONLINE")
        st.metric(label="Server Uptime", value=f"{health_metrics.get('system_uptime_seconds', 0.0)}s")
        st.metric(label="DB Records", value=f"{health_metrics.get('database_total_records', 'Unknown')}")
    else: 
        st.error("🔴 PIPELINE ENGINE: OFFLINE")

    st.markdown("### 📡 Hardware Telemetry")
    if health_metrics.get("esp32_status") == "online":
        st.success("📡 ESP32 Sensor: CONNECTED")
    else:
        st.error("🔌 ESP32 Sensor: DISCONNECTED")
    
    st.markdown("---")
    # --- 2. ADVANCED DATA QUERYING ---
    st.markdown("### 🎛️ Time-Range Filters")
    today = date.today()
    col_d1, col_d2 = st.columns(2)
    start_date = col_d1.date_input("Start Date", today - timedelta(days=1))
    end_date = col_d2.date_input("End Date", today)
    
    col_t1, col_t2 = st.columns(2)
    start_time = col_t1.time_input("Start Time", time(0, 0))
    end_time = col_t2.time_input("End Time", time(23, 59))
    
    dt_start = datetime.combine(start_date, start_time)
    dt_end = datetime.combine(end_date, end_time)
    
    # Pause toggle
    pause_feed = st.toggle("⏸️ Pause Live Feed", value=False, help="Stops auto-refresh so you can inspect data.")
    
    st.markdown("---")
    # --- 3. BIDIRECTIONAL CONTROL ---
    st.markdown("### 🎚️ Backend Configuration")
    anomaly_threshold = st.slider("Anomaly Sensitivity", min_value=0.5, max_value=0.99, value=0.85, step=0.01)
    if st.button("Sync to Engine"):
        success = sync_config_to_backend({"anomaly_threshold": anomaly_threshold})
        if success:
            st.success("Config Synced!")
        else:
            st.error("Sync Failed.")
            
    if st.button("🔄 Clear Cache & Sync Disk"):
        st.cache_data.clear()
        st.rerun()

@st.fragment
def live_analytics_fragment(start_dt, end_dt, pause):
    # Set interval extremely high if paused
    refresh_interval = 86400000 if pause else 10000 
    st_autorefresh(interval=refresh_interval, key="fragment_refresh_counter")
    
    df_data = fetch_telemetry_batch(start_dt, end_dt)
    
    if df_data.empty:
        st.warning("⚠️ No records found in the selected time range.")
        return

    latest = df_data.iloc[0]
    st.markdown("### 🤖 Live Predictive AI & Anomaly Insights")
    ml_space1, ml_space2, ml_space3 = st.columns(3)
    
    with ml_space1:
        if int(latest['is_anomaly']) == 1: 
            st.error("⚠️ Threat Matrix: ANOMALY DETECTED")
        else: 
            st.success("✅ Threat Matrix: CLIMATE STABLE")
    with ml_space2:
        st.metric(label="🔮 Projected Temp (Next Hour)", value=f"{latest['predicted_temp_next_hour']} °C")
    with ml_space3:
        st.metric(label="📊 Prediction Certainty Score", value=f"{latest['confidence_score']} %")
        
    st.markdown("### 🌡️ Environmental Conditions")
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Temperature", value=f"{latest['temperature']} °C")
    col2.metric(label="Relative Humidity", value=f"{latest['humidity']} %")
    col3.metric(label="Atmospheric Pressure", value=f"{latest['pressure']} hPa")
    
    # --- 4. ADVANCED VISUAL ANALYTICS (Plotly Subplots) ---
    st.markdown("### 📈 Synchronized Environmental Trends")
    df_chart = df_data.iloc[::-1].copy()
    
    # Subplots sharing X axis
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        subplot_titles=("Temperature (°C)", "Humidity (%)", "Pressure (hPa)"))
    
    # Traces
    fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['temperature'], mode='lines', name='Temp', line=dict(color='#ff7f0e')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['humidity'], mode='lines', name='Humidity', line=dict(color='#1f77b4')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['pressure'], mode='lines', name='Pressure', line=dict(color='#2ca02c')), row=3, col=1)
    
    # Anomaly Markers (Red Dots) on Temperature graph
    anomalies = df_chart[df_chart['is_anomaly'] == 1]
    if not anomalies.empty:
        fig.add_trace(go.Scatter(
            x=anomalies['timestamp'], 
            y=anomalies['temperature'], 
            mode='markers', 
            name='Anomaly', 
            marker=dict(color='red', size=8, symbol='x')
        ), row=1, col=1)
        
    fig.update_layout(height=600, showlegend=True, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    # --- 5. AUTOMATED REPORTING ---
    with st.expander("Raw Data & Reporting"):
        st.dataframe(df_data, use_container_width=True)
        
        col_csv, col_pdf = st.columns(2)
        with col_csv:
            csv_data = df_data.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", data=csv_data, file_name="telemetry.csv", mime="text/csv")
            
        with col_pdf:
            if PDF_SUPPORT:
                stats = {
                    'temp_avg': round(df_data['temperature'].mean(), 2),
                    'hum_avg': round(df_data['humidity'].mean(), 2),
                    'press_avg': round(df_data['pressure'].mean(), 2)
                }
                pdf_bytes = generate_pdf_report(df_data, stats)
                if pdf_bytes:
                    st.download_button(
                        label="Download PDF Report",
                        data=pdf_bytes,
                        file_name="anomaly_report.pdf",
                        mime="application/pdf"
                    )
            else:
                st.info("PDF reporting requires 'fpdf'. Run `pip install fpdf` to enable.")

# Render fragment
live_analytics_fragment(dt_start, dt_end, pause_feed)