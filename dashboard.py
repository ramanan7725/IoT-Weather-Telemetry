import sqlite3
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, date, timedelta
from fpdf import FPDF

# --- CONFIG ---
DB_FILE = "weather_data.db"
BACKEND_HEALTH_URL = "http://localhost:8000/api/health"

st.set_page_config(page_title="IoT Environmental Station", layout="wide", page_icon="🌤️")

st.markdown("<h1>🌤️ IoT Environmental Station</h1>", unsafe_allow_html=True)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* Main Background */
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    
    /* Remove default Streamlit top padding to push title up */
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    
    /* Metrics */
    div[data-testid="stMetricValue"] { 
        font-size: 2.5rem !important; 
        color: #00F0FF !important; 
        font-weight: 700 !important;
        text-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
    }
    div[data-testid="stMetricLabel"] { 
        font-size: 1.1rem !important; 
        color: #A0AEC0 !important; 
        font-weight: 600 !important;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 1rem !important;
    }
    
    /* Headers */
    h1 { font-size: 3rem !important; color: #FFFFFF !important; font-weight: 800; text-align: left; margin-top: -40px; margin-bottom: 30px; }
    h2, h3 { color: #E2E8F0 !important; }
    
    /* Sidebar Status Box */
    .sidebar-status-box {
        background-color: #1E293B;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        margin-bottom: 5px;
        border: 1px solid #334155;
    }
    
    /* Sidebar Spacing Optimization */
    section[data-testid="stSidebar"] hr { margin: 10px 0 !important; padding: 0 !important; }
    section[data-testid="stSidebar"] h2 { padding-top: 0 !important; margin-bottom: 5px !important; }
    section[data-testid="stSidebar"] .stDateInput { padding-bottom: 0 !important; margin-bottom: -10px !important; }
    .sidebar-status-box h3 {
        margin: 5px 0 !important;
        font-size: 1.2rem !important;
    }
    
    /* Tabs styling */
    button[data-baseweb="tab"] p {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }
    
    /* Status Badge */
    .status-badge { 
        padding: 8px 12px; 
        border-radius: 8px; 
        font-weight: bold; 
        text-align: center; 
        font-size: 1rem; 
        margin-top: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .status-stable { background: linear-gradient(135deg, #00b09b, #96c93d); color: white; }
    .status-anomaly { background: linear-gradient(135deg, #ff416c, #ff4b2b); color: white; animation: pulse 1.5s infinite; }
    
    @keyframes pulse {
        0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 65, 108, 0.7); }
        70% { transform: scale(1.05); box-shadow: 0 0 0 10px rgba(255, 65, 108, 0); }
        100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 65, 108, 0); }
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIC ---
@st.cache_data(ttl=5) # Reduced TTL for more "live" feel
def fetch_live():
    try:
        # Use read-only connection (?mode=ro) to avoid locking backend
        conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True, timeout=20)
        # Fetch last 2 records to calculate delta
        df = pd.read_sql("SELECT * FROM telemetry ORDER BY id DESC LIMIT 2", conn)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_hist(start, end):
    try:
        # Use read-only connection (?mode=ro) to avoid locking backend
        conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True, timeout=20)
        # Fast indexed query: String range comparison instead of full-table date() scan
        end_inclusive = (end + timedelta(days=1)).strftime("%Y-%m-%d")
        start_str = start.strftime("%Y-%m-%d")
        df = pd.read_sql("SELECT * FROM telemetry WHERE timestamp >= ? AND timestamp < ? ORDER BY id DESC", conn, params=(start_str, end_inclusive))
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

def generate_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "IoT Environmental Telemetry Report", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, f"Total Records: {len(df)}", ln=True)
    if not df.empty:
        pdf.cell(200, 10, f"Avg Temp: {df['temperature'].mean():.2f} °C", ln=True)
        pdf.cell(200, 10, f"Avg Humidity: {df['humidity'].mean():.2f} %", ln=True)
        if 'is_anomaly' in df.columns:
            pdf.cell(200, 10, f"Anomalies Detected: {df['is_anomaly'].sum()}", ln=True)
    return pdf.output(dest='S').encode('latin-1', 'replace')

def create_gauge(value, title, min_val, max_val, suffix, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        title = {'text': title, 'font': {'size': 20, 'color': '#E2E8F0'}},
        number = {'suffix': suffix, 'font': {'size': 30, 'color': color}},
        gauge = {
            'axis': {'range': [min_val, max_val], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': color},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "#2D3748",
            'steps': [
                {'range': [min_val, (max_val-min_val)*0.5 + min_val], 'color': 'rgba(255,255,255,0.05)'},
                {'range': [(max_val-min_val)*0.5 + min_val, max_val], 'color': 'rgba(255,255,255,0.1)'}
            ]
        }
    ))
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)", font={'color': "#E2E8F0"})
    return fig

# --- AUTO REFRESH ---
# Refresh every 10 seconds for a more live experience
count = st_autorefresh(interval=30000, key="refresher")

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## ⚙️ System Status")
    
    try:
        h = requests.get(BACKEND_HEALTH_URL, timeout=2).json()
    except:
        h = {}
        
    engine_status = h.get('status','offline').upper()
    esp32_status = h.get('esp32_status','offline').upper()
    
    st.markdown(f"""
    <div class="sidebar-status-box">
        <h3><b>Engine:</b> {'🟢' if engine_status == 'ONLINE' else '🔴'} {engine_status}</h3>
        <h3><b>ESP32:</b> {'🟢' if esp32_status == 'ONLINE' else '🔴'} {esp32_status}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("## 📅 Data Range")
    start = st.date_input("Start Date", date.today()-timedelta(days=7))
    end = st.date_input("End Date", date.today())
    
    st.markdown("---")
    if st.button("🔄 Force Refresh Data", use_container_width=True): 
        st.cache_data.clear()
        st.rerun()

# --- MAIN UI ---

live = fetch_live()
hist = fetch_hist(start, end)

# Create Tabs for better organization
tab1, tab2, tab3 = st.tabs(["🚀 Live Dashboard", "📈 Historical Analysis", "📄 Data & Reports"])

with tab1:
    if not live.empty:
        l = live.iloc[0]
        prev = live.iloc[1] if len(live) > 1 else l
        
        # Threat Status Badge
        if l.get('is_anomaly', 0):
            st.markdown('<div class="status-badge status-anomaly">⚠️ CRITICAL: ANOMALY DETECTED</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge status-stable">✅ SYSTEM STABLE: NO ANOMALIES</div>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Top Metrics with Deltas & Forecast
        c1, c2, c3, c4 = st.columns(4)
        
        temp_delta = float(l['temperature']) - float(prev['temperature'])
        hum_delta = float(l['humidity']) - float(prev['humidity'])
        press_delta = float(l['pressure']) - float(prev['pressure'])
        
        c1.metric("Temperature", f"{l['temperature']} °C", f"{temp_delta:.1f} °C")
        c2.metric("Humidity", f"{l['humidity']} %", f"{hum_delta:.1f} %")
        c3.metric("Pressure", f"{l['pressure']} hPa", f"{press_delta:.1f} hPa")
        
        if 'predicted_temp_next_hour' in l and pd.notna(l['predicted_temp_next_hour']):
            pred_temp = float(l['predicted_temp_next_hour'])
            pred_delta = pred_temp - float(l['temperature'])
            c4.metric("AI Temp Forecast (1h)", f"{pred_temp} °C", f"{pred_delta:+.1f} °C expected", delta_color="off")
        else:
            c4.metric("AI Temp Forecast (1h)", "Awaiting Data", "-")
        
        st.markdown("<hr style='border-color: #2D3748;'>", unsafe_allow_html=True)
        
        # Gauges
        g1, g2, g3 = st.columns(3)
        with g1:
            st.plotly_chart(create_gauge(l['temperature'], "Temperature", -10, 50, "°C", "#FF5722"), use_container_width=True)
        with g2:
            st.plotly_chart(create_gauge(l['humidity'], "Humidity", 0, 100, "%", "#00BCD4"), use_container_width=True)
        with g3:
            st.plotly_chart(create_gauge(l['pressure'], "Pressure", 900, 1100, "hPa", "#8BC34A"), use_container_width=True)
    else:
        st.warning("No live data available. Check database connection.")

with tab2:
    if not hist.empty:
        st.markdown("### 📊 Interactive Trends")
        
        # Advanced Graph with Range Slider and Hover Effects
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.08,
                            subplot_titles=("Temperature (°C)", "Humidity (%)", "Pressure (hPa)"))
        
        fig.add_trace(go.Scatter(x=hist['timestamp'], y=hist['temperature'], name="Temp", line=dict(color="#FF5722", width=2), fill='tozeroy', fillcolor="rgba(255, 87, 34, 0.1)"), 1, 1)
        fig.add_trace(go.Scatter(x=hist['timestamp'], y=hist['humidity'], name="Hum", line=dict(color="#00BCD4", width=2), fill='tozeroy', fillcolor="rgba(0, 188, 212, 0.1)"), 2, 1)
        fig.add_trace(go.Scatter(x=hist['timestamp'], y=hist['pressure'], name="Press", line=dict(color="#8BC34A", width=2), fill='tozeroy', fillcolor="rgba(139, 195, 74, 0.1)"), 3, 1)
        
        if 'is_anomaly' in hist.columns:
            anom = hist[hist['is_anomaly']==1]
            if not anom.empty:
                for i, col in enumerate(['temperature', 'humidity', 'pressure'], 1):
                    # Render solid 'X' for anomalies
                    fig.add_trace(go.Scatter(x=anom['timestamp'], y=anom[col], mode='markers', name=f'Anomaly', 
                                           marker=dict(color='#FF0000', size=12, symbol='x', line=dict(width=2, color='white'))), i, 1)
        
        fig.update_layout(
            height=700, 
            template="plotly_dark", 
            showlegend=False, 
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode="x unified",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        
        fig.update_xaxes(rangeslider_visible=True, row=3, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No historical data found for the selected date range.")

with tab3:
    st.markdown("### 🗃️ Raw Data & Export")
    if not hist.empty:
        search = st.text_input("🔍 Filter records (e.g., specific date/time)")
        filtered_df = hist[hist.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)] if search else hist
        
        st.dataframe(filtered_df, use_container_width=True, height=400)
        
        # Limit to 5000 rows for PDF to prevent UI freeze
        export_df = filtered_df.head(5000)
        if len(filtered_df) > 5000:
            st.warning("⚠️ For performance reasons, the PDF export is limited to the first 5,000 records.")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            st.download_button(
                label="📥 Download PDF Report", 
                data=generate_pdf(export_df), 
                file_name=f"iot_report_{date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col2:
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"iot_data_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.info("No data available to display or export.")