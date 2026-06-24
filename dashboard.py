import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

import os

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "weather_data.db")

st.set_page_config(page_title="Weather Station", layout="wide", page_icon="🌤️")
st.title("🌤️ Weather Station Dashboard")

# --- DATA FETCHING ---
@st.cache_data(ttl=60)
def fetch_data(days=1):
    try:
        # Read-only connection to prevent locking the backend writes
        conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True, timeout=5)
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        df = pd.read_sql(f"SELECT * FROM telemetry WHERE timestamp >= '{cutoff_date}' ORDER BY timestamp DESC", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

# --- UI ---
status_placeholder = st.sidebar.empty()  # Placeholder to put status at the very top
st.sidebar.markdown("---")
st.sidebar.header("Controls")
if st.sidebar.button("🔄 Force Refresh"):
    st.cache_data.clear()
    st.rerun()

days_to_fetch = st.sidebar.slider("Days of Data", 1, 30, 1)
df = fetch_data(days_to_fetch)

if not df.empty:
    # Latest Data
    latest = df.iloc[0]
    
    # Check Backend Status based on last packet timestamp
    try:
        last_timestamp = datetime.strptime(latest['timestamp'], "%Y-%m-%d %H:%M:%S")
        time_since_last_packet = (datetime.now() - last_timestamp).total_seconds()
        
        if time_since_last_packet < 120:  # If we got a packet in the last 2 minutes
            status_placeholder.success("🟢 Backend & Sensor Online")
        else:
            status_placeholder.error(f"🔴 Offline (Last seen: {int(time_since_last_packet/60)} mins ago)")
    except Exception:
        status_placeholder.warning("⚠️ Status Unknown")
    
    st.subheader("Current Conditions")
    col1, col2, col3 = st.columns(3)
    col1.metric("Temperature", f"{latest['temperature']} °C")
    col2.metric("Humidity", f"{latest['humidity']} %")
    col3.metric("Pressure", f"{latest['pressure']} hPa")
    
    st.markdown("---")
    
    # Graphs
    st.subheader("Historical Trends")
    # Melt dataframe for easier subplotting in Plotly Express
    df_chart = df.melt(id_vars=["timestamp"], value_vars=["temperature", "humidity", "pressure"], 
                       var_name="Metric", value_name="Value")
    
    fig = px.line(df_chart, x="timestamp", y="Value", color="Metric", facet_row="Metric", height=600)
    fig.update_yaxes(matches=None) # Allow independent y-axes so pressure and temp don't squash each other
    st.plotly_chart(fig, use_container_width=True)
    
    # Data Table
    st.markdown("---")
    st.subheader("Raw Data")
    st.dataframe(df, use_container_width=True, height=300)
    
    # Download Button
    st.download_button(
        label="Download CSV",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name=f"weather_data.csv",
        mime="text/csv"
    )
else:
    st.info("No data found in the database. Ensure the backend engine and ESP32 are running.")