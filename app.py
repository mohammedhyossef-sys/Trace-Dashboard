import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
import traceback
import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import numpy as np
import math

from plotly.subplots import make_subplots
import plotly.graph_objects as go

# ---------------------------
# CONFIG
# ---------------------------
plot_template = "plotly_white"

st.set_page_config(
    layout="wide",
    page_title="WE Trace Dashboard",
    page_icon="📡",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
#MainMenu, footer, header { visibility: hidden; }
.stApp { background: #f4f6fb; }
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 {
    color: #1e293b !important; font-size: 13px !important; font-weight: 600 !important;
    text-transform: uppercase; letter-spacing: .06em; margin-top: 1.2rem !important;
}
[data-testid="stFileUploader"] {
    background: #f8fafc; border: 1.5px dashed #cbd5e1;
    border-radius: 10px; padding: 6px 10px; margin-bottom: 4px;
}
[data-testid="stFileUploader"]:hover { border-color: #6366f1; }
[data-testid="stSlider"] > div > div > div > div { background: #6366f1 !important; }
.we-header {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border-radius: 16px; padding: 22px 32px; margin-bottom: 20px;
    display: flex; align-items: center; gap: 18px;
    box-shadow: 0 4px 24px rgba(99,102,241,.25);
}
.we-header-icon { font-size: 44px; line-height:1; }
.we-header h1 {
    color: white !important; font-size: 28px !important;
    font-weight: 700 !important; margin: 0 !important; padding: 0 !important;
}
.we-header p { color: rgba(255,255,255,.75) !important; font-size: 13px !important; margin: 4px 0 0 !important; }
[data-testid="stMetric"] {
    background: #ffffff; border-radius: 14px;
    padding: 16px 20px !important; box-shadow: 0 2px 12px rgba(0,0,0,.06);
}
[data-testid="stMetricLabel"] { font-size:12px !important; color:#64748b !important; font-weight:600 !important; }
[data-testid="stMetricValue"] { font-size:26px !important; color:#1e293b !important; font-weight:700 !important; }
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: #ffffff; border-radius: 10px; padding: 4px; gap: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 8px !important; font-weight: 600 !important;
    font-size: 13px !important; color: #64748b !important;
}
[data-testid="stTabs"] [aria-selected="true"] { background: #6366f1 !important; color: white !important; }
[data-testid="stButton"] > button {
    background: linear-gradient(135deg,#6366f1,#8b5cf6) !important;
    color: white !important; border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; padding: 8px 20px !important;
    box-shadow: 0 2px 8px rgba(99,102,241,.3) !important;
}
[data-testid="stAlert"] { border-radius: 10px !important; }
hr { border-color: #e2e8f0 !important; }
div[data-testid="stPlotlyChart"] {
    background: #ffffff; border-radius: 14px;
    padding: 16px; box-shadow: 0 2px 12px rgba(0,0,0,.06); margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="we-header">
  <div class="we-header-icon">📡</div>
  <div>
    <h1>WE Trace Dashboard</h1>
    <p>Network performance analysis &amp; customer trace visualization</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------
# FUNCTIONS
# ---------------------------
def clean(x):
    return str(x).upper().replace(" ", "").replace("-", "")

def extract_site_id(sector_name):
    """
    Extract Site ID from Sector Name by removing trailing _N suffix.
    e.g. LDELM28621_5 → LDELM28621
         LDELM28621_11 → LDELM28621
         LDELM28621 → LDELM28621 (unchanged)
    """
    s = str(sector_name).strip()
    import re
    return re.sub(r'_\d+$', '', s)

def clean_coord(x):
    return str(x).replace(",", ".").replace("N", "").replace("E", "").strip()

def convert_to_mb(val):
    val = str(val).upper().replace(",", "").strip()
    if "KB" in val:
        return float(val.replace("KB", "")) / 1024
    elif "MB" in val:
        return float(val.replace("MB", ""))
    else:
        try:
            return float(val) / 1024
        except:
            return 0

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))

LAYER_COLORS = {
    "L700":  "#e74c3c",
    "L800":  "#e67e22",
    "L900":  "#f39c12",
    "L1800": "#2ecc71",
    "L2100": "#3498db",
    "L2600": "#9b59b6",
    "L3500": "#1abc9c",
    "NR":    "#e91e63",
    "5G":    "#ff5722",
}

def get_layer_color(layer_str):
    layer_str = str(layer_str).upper()
    for key, color in LAYER_COLORS.items():
        if key in layer_str:
            return color
    return "#95a5a6"

def parse_layers(layer_str):
    if not layer_str or str(layer_str).strip() in ["", "nan", "None"]:
        return ["L1800"]
    parts = str(layer_str).replace(",", "+").replace("/", "+").upper().split("+")
    return [p.strip() for p in parts if p.strip()]

def build_sector_popup(sector_row, layer_name, layer_color, throughput=None):
    rows_html = f"""
    <div style='font-family:Arial; font-size:12px; min-width:220px; max-width:320px'>
      <div style='background:{layer_color};color:white;padding:4px 8px;
                  border-radius:4px 4px 0 0;font-weight:bold;font-size:13px'>
        ▌ {layer_name}
      </div>
      <table style='width:100%;border-collapse:collapse;margin-top:4px'>
    """
    skip_cols = {"Latitude", "Longitude", "Folder Path"}
    for col, val in sector_row.items():
        if col in skip_cols or pd.isna(val) if not isinstance(val, str) else False:
            continue
        val_str = str(val).strip().replace("\\", " / ").replace("\xa0", " ")
        if val_str in ("", "nan", "None"):
            continue
        rows_html += f"""
        <tr style='border-bottom:1px solid #eee'>
          <td style='padding:2px 6px;color:#666;white-space:nowrap'><b>{col}</b></td>
          <td style='padding:2px 6px'>{val_str}</td>
        </tr>"""
    if throughput is not None:
        rows_html += f"""
        <tr style='border-bottom:1px solid #eee;background:#f0fff0'>
          <td style='padding:2px 6px;color:#666'><b>Throughput</b></td>
          <td style='padding:2px 6px;font-weight:bold'>{round(throughput,2)} Mbps</td>
        </tr>"""
    rows_html += "</table></div>"
    return rows_html


def draw_sector_cone(m, lat, lon, azimuth, radius_km=0.5, beamwidth=65,
                     color="blue", sector_row=None, layers=None, throughput=None):
    if layers is None or len(layers) == 0:
        layers = ["L1800"]

    n_layers = len(layers)
    half_beam = beamwidth / 2
    start_angle = azimuth - half_beam
    end_angle   = azimuth + half_beam
    steps = 12

    r_lat = radius_km / 111.0
    r_lon = radius_km / (111.0 * math.cos(math.radians(lat)))

    def arc_points(r_frac, from_deg, to_deg):
        pts = []
        for i in range(steps + 1):
            a = math.radians(from_deg + (to_deg - from_deg) * i / steps)
            pts.append((lat + r_lat * r_frac * math.cos(a),
                         lon + r_lon * r_frac * math.sin(a)))
        return pts

    for idx, layer in enumerate(layers):
        frac_inner = idx / n_layers
        frac_outer = (idx + 1) / n_layers
        layer_color = LAYER_COLORS.get(layer, color)

        if frac_inner == 0:
            outer_arc = arc_points(frac_outer, start_angle, end_angle)
            polygon_pts = [(lat, lon)] + outer_arc + [(lat, lon)]
        else:
            outer_arc = arc_points(frac_outer, start_angle, end_angle)
            inner_arc = arc_points(frac_inner, end_angle, start_angle)
            polygon_pts = outer_arc + inner_arc + [outer_arc[0]]

        popup_html = build_sector_popup(
            sector_row if sector_row is not None else {},
            layer_name=layer,
            layer_color=layer_color,
            throughput=throughput
        )

        folium.Polygon(
            locations=polygon_pts,
            color=layer_color,
            fill=True,
            fill_color=layer_color,
            fill_opacity=0.30,
            weight=2,
            popup=folium.Popup(popup_html, max_width=340)
        ).add_to(m)

    full_arc = arc_points(1.0, start_angle, end_angle)
    outline_pts = [(lat, lon)] + full_arc + [(lat, lon)]
    folium.PolyLine(
        locations=outline_pts,
        color=color,
        weight=2,
        opacity=0.8
    ).add_to(m)


# ---------------------------
# MSISDN NORMALIZATION
# ---------------------------
def norm_msisdn(s):
    """
    Normalize MSISDN for matching:
    - Remove spaces, dashes, +
    - Remove leading country code (20 for Egypt, or 002)
    - Return last 10 digits
    """
    s = str(s).strip().replace(" ", "").replace("-", "").replace("+", "")
    # Remove leading 00 + country code
    if s.startswith("002"):
        s = s[3:]
    elif s.startswith("20") and len(s) > 10:
        s = s[2:]
    # Remove leading zero
    if s.startswith("0") and len(s) > 9:
        s = s[1:]
    # Return last 10 digits as the canonical form
    return s[-10:] if len(s) >= 10 else s

def is_masked(msisdn_str):
    """Returns True if the MSISDN contains masking characters like * or X"""
    return "*" in str(msisdn_str) or "x" in str(msisdn_str).lower()


# ---------------------------
# UPLOAD
# ---------------------------
st.sidebar.markdown("""
<div style="text-align:center;padding:16px 8px 20px;border-bottom:1px solid #e2e8f0;margin-bottom:8px">
  <div style="font-size:36px">📡</div>
  <div style="font-size:16px;font-weight:700;color:#1e293b;margin-top:6px">WE Trace</div>
  <div style="font-size:11px;color:#6366f1;font-weight:600;letter-spacing:.08em;text-transform:uppercase">Dashboard</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin:16px 0 6px;padding-bottom:4px;border-bottom:1px solid #e2e8f0">📁 Upload Files</div>', unsafe_allow_html=True)

trace_files = st.sidebar.file_uploader("Upload Trace sheet(s)", type=["xlsx"], accept_multiple_files=True)
sectors_file = st.sidebar.file_uploader("Upload On-Air sheet", type=["xlsx"])
down_file = st.sidebar.file_uploader("Upload Down Sites sheet", type=["xlsx"])
planned_file = st.sidebar.file_uploader("Upload Planned Sites sheet (Optional)", type=["xlsx"])
customers_file = st.sidebar.file_uploader("Upload Customers data (Optional)", type=["xlsx"])

if not trace_files or sectors_file is None:
    st.warning("📌 Upload BOTH Trace File(s) and Sectors File")
    st.stop()

# ---------------------------
# CACHED READ FUNCTIONS (prevent re-reading on every interaction)
# ---------------------------
@st.cache_data(show_spinner="📂 Loading trace file…")
def load_trace_file(file_bytes):
    import io
    buf = io.BytesIO(file_bytes)
    try:
        cond_df = pd.read_excel(buf, sheet_name=0, header=None)
        msisdn = str(cond_df.iloc[7, 2]).strip()
    except:
        msisdn = "N/A"
    buf.seek(0)
    tdf = pd.read_excel(buf, sheet_name=1)
    tdf.columns = tdf.columns.str.strip()
    return msisdn, tdf

@st.cache_data(show_spinner="📂 Loading sectors file…")
def load_sectors_file(file_bytes):
    import io
    buf = io.BytesIO(file_bytes)
    try:
        xl = pd.ExcelFile(buf)
        sheet = "Sectors" if "Sectors" in xl.sheet_names else 0
        df = pd.read_excel(buf, sheet_name=sheet)
    except:
        buf.seek(0)
        df = pd.read_excel(buf)
    df.columns = df.columns.str.strip()
    return df

@st.cache_data(show_spinner="📂 Loading optional file…")
def load_optional_file(file_bytes):
    import io
    buf = io.BytesIO(file_bytes)
    df = pd.read_excel(buf)
    df.columns = df.columns.str.strip()
    return df

# Read all trace files and combine
on_air_df = load_sectors_file(sectors_file.getvalue()).copy()

# Read customers file early to get Customer Name for MSISDN selector
_cust_name_map = {}  # msisdn_normalized -> Customer Name
if customers_file is not None:
    try:
        _cdf_early = load_optional_file(customers_file.getvalue())
        _msisdn_col_early = next(
            (c for c in _cdf_early.columns if "problematic msisdn" in c.lower()), None
        ) or next(
            (c for c in _cdf_early.columns if any(x in c.lower() for x in ["msisdn", "mobile", "phone", "number"])),
            None
        )
        _name_col_early = next(
            (c for c in _cdf_early.columns if "customer name" in c.lower()), None
        )
        if _msisdn_col_early and _name_col_early:
            for _, _row in _cdf_early.dropna(subset=[_msisdn_col_early]).iterrows():
                _norm = norm_msisdn(str(_row[_msisdn_col_early]))
                _name = str(_row[_name_col_early]).strip()
                if _name and _name not in ("nan", ""):
                    _cust_name_map[_norm] = _name
    except:
        pass

all_traces = []
msisdn_map = {}  # msisdn_normalized -> display label

for tf in trace_files:
    _msisdn_raw, _tdf = load_trace_file(tf.getvalue())
    _msisdn_norm = norm_msisdn(_msisdn_raw) if _msisdn_raw != "N/A" else tf.name
    _tdf["_msisdn_file"] = _msisdn_norm
    all_traces.append(_tdf)
    # Label = "CustomerName — MSISDN" Use name if available, else MSISDN only
    _cust_name = _cust_name_map.get(_msisdn_norm, "")
    msisdn_map[_msisdn_norm] = f"{_cust_name} — {_msisdn_raw}" if _cust_name else _msisdn_raw

trace_df_all = pd.concat(all_traces, ignore_index=True) if all_traces else pd.DataFrame()


# MSISDN selector — Select the number you want to view
msisdn_options = list(msisdn_map.keys())
if len(msisdn_options) > 1:
    selected_msisdn = st.sidebar.selectbox(
        "📱 Select MSISDN",
        msisdn_options,
        format_func=lambda x: msisdn_map.get(x, x)
    )
else:
    selected_msisdn = msisdn_options[0] if msisdn_options else None

# Filter trace for selected MSISDN
if selected_msisdn:
    trace_df = trace_df_all[trace_df_all["_msisdn_file"] == selected_msisdn].copy()
    msisdn_value = msisdn_map.get(selected_msisdn, selected_msisdn)
    msisdn_normalized = selected_msisdn
else:
    trace_df = trace_df_all.copy()
    msisdn_value = "N/A"
    msisdn_normalized = None

# ---------------------------
# SAFE LAT/LON FIX
# ---------------------------
lat_col = next((c for c in on_air_df.columns if "lat" in c.lower()), None)
lon_col = next((c for c in on_air_df.columns if "lon" in c.lower()), None)

if lat_col and lon_col:
    on_air_df["Latitude"] = pd.to_numeric(
        on_air_df[lat_col].astype(str).apply(clean_coord), errors="coerce"
    )
    on_air_df["Longitude"] = pd.to_numeric(
        on_air_df[lon_col].astype(str).apply(clean_coord), errors="coerce"
    )
    on_air_df = on_air_df.dropna(subset=["Latitude", "Longitude"])
else:
    st.error("❌ Latitude/Longitude not found in Sectors file")
    st.stop()

# ---------------------------
# AZIMUTH
# ---------------------------
azimuth_col = next((c for c in on_air_df.columns if "azimuth" in c.lower()), None)
if azimuth_col:
    on_air_df["Azimuth"] = pd.to_numeric(on_air_df[azimuth_col], errors="coerce")
else:
    on_air_df["Azimuth"] = 0

# ---------------------------
# SECTOR STATUS COLOR
# ---------------------------
def get_sector_color(status):
    if status is None:
        return "gray"
    s = str(status).upper()
    if "ON AIR" in s or "SIGNED" in s or "ACTIVE" in s:
        return "green"
    elif "DOWN" in s or "OFF" in s:
        return "red"
    elif "PLANNED" in s or "PH" in s:
        return "blue"
    else:
        return "orange"

status_col = next((c for c in on_air_df.columns if "status" in c.lower()), None)

# ---------------------------
# CLEAN SITE IDS
# ---------------------------
on_air_df["Site ID"] = on_air_df["Site ID"].apply(clean)

# ---------------------------
# DOWN FILE
# ---------------------------
down_df = None
if down_file is not None:
    down_df = load_optional_file(down_file.getvalue()).copy()
    if "Site ID" in down_df.columns:
        down_df["Site ID"] = down_df["Site ID"].apply(clean)
    # Get coordinates from on_air_df if available, but do not drop unmatched rows
    down_geo = on_air_df[["Site ID", "Latitude", "Longitude"]].drop_duplicates("Site ID")
    if "Site ID" in down_df.columns:
        down_df = down_df.merge(down_geo, on="Site ID", how="left")
    # If there is lat/lon in the file itself, use as fallback
    _d_lat = next((c for c in down_df.columns if "lat" in c.lower() and c not in ["Latitude"]), None)
    _d_lon = next((c for c in down_df.columns if "lon" in c.lower() and c not in ["Longitude"]), None)
    if _d_lat and "Latitude" not in down_df.columns:
        down_df["Latitude"]  = pd.to_numeric(down_df[_d_lat], errors="coerce")
        down_df["Longitude"] = pd.to_numeric(down_df[_d_lon], errors="coerce")
    elif "Latitude" not in down_df.columns:
        down_df["Latitude"]  = float("nan")
        down_df["Longitude"] = float("nan")
    down_df["Latitude"]  = pd.to_numeric(down_df["Latitude"],  errors="coerce")
    down_df["Longitude"] = pd.to_numeric(down_df["Longitude"], errors="coerce")
    # Do not drop — JS will get coordinates from SECTORS

# ---------------------------
# PLANNED FILE
# ---------------------------
planned_df = None

if planned_file is not None:
    try:
        planned_df = load_optional_file(planned_file.getvalue()).copy()

        if "Site ID" in planned_df.columns:
            planned_df["Site ID"] = planned_df["Site ID"].apply(clean)

        p_lat_col = next((c for c in planned_df.columns if "lat" in c.lower()), None)
        p_lon_col = next((c for c in planned_df.columns if "lon" in c.lower()), None)

        if p_lat_col and p_lon_col:
            planned_df["Latitude"] = pd.to_numeric(planned_df[p_lat_col], errors="coerce")
            planned_df["Longitude"] = pd.to_numeric(planned_df[p_lon_col], errors="coerce")
            planned_df = planned_df.dropna(subset=["Latitude", "Longitude"])
        else:
            planned_df = None
    except:
        planned_df = None

# ---------------------------
# CUSTOMERS FILE
# ---------------------------
customers_df = None

if customers_file is not None:
    try:
        customers_df = load_optional_file(customers_file.getvalue()).copy()
        
        if customers_df is not None and not customers_df.empty:
            c_lat = next((c for c in customers_df.columns if "lat" in c.lower()), None)
            c_lon = next((c for c in customers_df.columns if "lon" in c.lower()), None)

            if c_lat and c_lon:
                try:
                    # Safe conversion: handle both string and numeric formats
                    customers_df[c_lat] = customers_df[c_lat].astype(str).str.strip()
                    customers_df[c_lon] = customers_df[c_lon].astype(str).str.strip()
                    
                    customers_df["Latitude"]  = pd.to_numeric(customers_df[c_lat], errors="coerce")
                    customers_df["Longitude"] = pd.to_numeric(customers_df[c_lon], errors="coerce")
                    
                    # Only drop NaN if we have enough data left
                    customers_df = customers_df.dropna(subset=["Latitude", "Longitude"])
                    
                    if customers_df.empty:
                        st.warning("⚠️ No valid coordinates in customer file")
                        customers_df = None
                except Exception as e:
                    st.warning(f"⚠️ Error processing customer coordinates: {str(e)}")
                    customers_df = None
            else:
                st.warning("⚠️ No Latitude/Longitude columns found in customer file")
                customers_df = None
    except Exception as e:
        st.warning(f"⚠️ Error loading customer file: {str(e)}")
        customers_df = None

# ---------------------------
# SITE COLUMN IN TRACE
# ---------------------------
cols = ["BSC/RNC/eNodeB/gNodeB Name", "eNodeB Name", "gNodeB Name"]
trace_col = next((c for c in cols if c in trace_df.columns), None)

# If no Site column found, create one from Complaint ID or MSISDN
if trace_col is None:
    if "Complaint" in trace_df.columns:
        trace_col = "Complaint"
        st.info("ℹ️ Using Complaint ID as Site identifier (No Site column in trace file)")
    elif "Problematic MSISDN" in trace_df.columns:
        trace_col = "Problematic MSISDN"
        st.info("ℹ️ Using Problematic MSISDN as Site identifier (No Site column in trace file)")
    else:
        # Create a generic site identifier
        trace_df["_generated_site"] = "Site_" + trace_df.index.astype(str)
        trace_col = "_generated_site"
        st.info("ℹ️ Generated Site IDs for visualization")
else:
    trace_df[trace_col] = trace_df[trace_col].apply(clean)

# ── Fallback: If Name column is empty (all values -- or blank)
# Use IP address as site identifier
if trace_col and trace_col in trace_df.columns:
    _name_filled = trace_df[trace_col].astype(str).replace("", pd.NA).dropna()
    _name_filled = _name_filled[~_name_filled.isin(["--", "NAN", "NONE"])]
    if len(_name_filled) == 0:
        _ip_col = next((c for c in [
            "BSC/RNC/eNodeB/gNodeB User-Plane IP Address",
            "BSC/RNC/eNodeB/gNodeB IP",
            "eNodeB IP",
        ] if c in trace_df.columns), None)
        if _ip_col:
            trace_df[trace_col] = trace_df[_ip_col].astype(str).str.replace(".", "_", regex=False)
            if not trace_df_all.empty and trace_col in trace_df_all.columns and _ip_col in trace_df_all.columns:
                trace_df_all[trace_col] = trace_df_all[_ip_col].astype(str).str.replace(".", "_", regex=False)
            st.info(f"ℹ️ Site Name column is empty — using IP address ({_ip_col}) as site identifier.")
        else:
            st.warning("⚠️ Site Name column is empty and no IP fallback found. Showing all data as one site.")
            trace_df[trace_col] = "UNKNOWN_SITE"
            if not trace_df_all.empty and trace_col in trace_df_all.columns:
                trace_df_all[trace_col] = "UNKNOWN_SITE"
    else:
        if not trace_df_all.empty and trace_col in trace_df_all.columns:
            trace_df_all[trace_col] = trace_df_all[trace_col].astype(str).apply(lambda x: clean(x) if x else x)

# Build extracted Site ID column from sector name (removes _N suffix)
trace_df["_site_id_clean"] = trace_df[trace_col].apply(extract_site_id)
_bad_mask = trace_df["_site_id_clean"].isin(["", "--", "NAN", "NONE"])

# Only filter if there are good rows, otherwise keep all
if not _bad_mask.all() and len(trace_df) > 0:
    trace_df = trace_df[~_bad_mask].reset_index(drop=True)

# Add _site_id_clean to trace_df_all using the same logic
if not trace_df_all.empty and trace_col in trace_df_all.columns:
    if trace_col not in trace_df_all.columns:
        trace_df_all[trace_col] = "UNKNOWN"
    else:
        trace_df_all[trace_col] = trace_df_all[trace_col].astype(str).apply(lambda x: clean(x) if x else x)
    trace_df_all["_site_id_clean"] = trace_df_all[trace_col].apply(extract_site_id)
    _bad_all = trace_df_all["_site_id_clean"].isin(["", "--", "NAN", "NONE"])
    if not _bad_all.all() and len(trace_df_all) > 0:
        trace_df_all = trace_df_all[~_bad_all].reset_index(drop=True)

# ---------------------------
# TIME
# ---------------------------
trace_df["Start Time"] = pd.to_datetime(
    trace_df["Start Time"].astype(str).str.replace(r"\s*\(.*?\)\s*$", "", regex=True).str.strip(),
    format="%Y-%m-%d %H:%M:%S.%f",
    errors="coerce"
)
# fallback for rows without milliseconds
_mask_st = trace_df["Start Time"].isna()
if _mask_st.any():
    trace_df.loc[_mask_st, "Start Time"] = pd.to_datetime(
        trace_df.loc[_mask_st, "Start Time"].astype(str)
               .str.replace(r"\s*\(.*?\)\s*$", "", regex=True).str.strip(),
        errors="coerce"
    )

trace_df["End Time"] = pd.to_datetime(
    trace_df["End Time"].astype(str).str.replace(r"\s*\(.*?\)\s*$", "", regex=True).str.strip(),
    format="%Y-%m-%d %H:%M:%S.%f",
    errors="coerce"
)
# fallback for rows without milliseconds
_mask_et = trace_df["End Time"].isna()
if _mask_et.any():
    trace_df.loc[_mask_et, "End Time"] = pd.to_datetime(
        trace_df.loc[_mask_et, "End Time"].astype(str)
               .str.replace(r"\s*\(.*?\)\s*$", "", regex=True).str.strip(),
        errors="coerce"
    )
trace_df = trace_df.dropna(subset=["Start Time", "End Time"])

if trace_df.empty:
    st.error("❌ No valid time data")
    st.stop()

# ---------------------------
# DURATION
# ---------------------------
trace_df["Duration"] = (trace_df["End Time"] - trace_df["Start Time"]).dt.total_seconds()
trace_df = trace_df[trace_df["Duration"] > 0]

# ---------------------------
# TRAFFIC COLUMN
# ---------------------------
traffic_col = None
for col in trace_df.columns:
    if "downlink" in col.lower() and "traffic" in col.lower():
        traffic_col = col
        break
if traffic_col is None:
    for col in trace_df.columns:
        if "downlink" in col.lower():
            traffic_col = col
            break

if traffic_col is None:
    st.error("❌ No Traffic Column Found")
    st.stop()

# ---------------------------
# THROUGHPUT
# ---------------------------
trace_df["Traffic_MB"] = trace_df[traffic_col].apply(convert_to_mb)
trace_df["Throughput"] = (trace_df["Traffic_MB"] * 8) / trace_df["Duration"]

# Add DL/UL Mbps to trace_df for export
_dl_col = next((c for c in trace_df.columns if "downlink throughput" in c.lower()), None)
_ul_col = next((c for c in trace_df.columns if "uplink throughput" in c.lower()), None)
if _dl_col:
    trace_df["DL_Mbps"] = pd.to_numeric(trace_df[_dl_col], errors="coerce") / 1000
if _ul_col:
    trace_df["UL_Mbps"] = pd.to_numeric(trace_df[_ul_col], errors="coerce") / 1000

# ---------------------------
# FILTERS
# ---------------------------
st.sidebar.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin:16px 0 6px;padding-bottom:4px;border-bottom:1px solid #e2e8f0">🔎 Filters</div>', unsafe_allow_html=True)

# MSISDN selector already shown above — no IMSI multiselect needed
selected_imsi = []

if "Service Type" in trace_df.columns:
    service_types = sorted(trace_df["Service Type"].dropna().astype(str).unique())
    selected_service = st.sidebar.selectbox("📶 Service Type", ["All"] + service_types)
else:
    selected_service = "All"

sites = trace_df[trace_col].unique()
selected_site = st.sidebar.selectbox("📡 Site", ["All"] + list(sites))

extra_filters = {}
for col in ["App Name", "Radio Access Type", "Roaming Status"]:
    if col in trace_df.columns:
        values = trace_df[col].dropna().astype(str).unique()
        extra_filters[col] = st.sidebar.selectbox(col, ["All"] + list(values))

min_time = trace_df["Start Time"].min()
max_time = trace_df["Start Time"].max()
time_range = st.sidebar.slider(
    "Time Range",
    min_value=min_time.to_pydatetime(),
    max_value=max_time.to_pydatetime(),
    value=(min_time.to_pydatetime(), max_time.to_pydatetime())
)

st.sidebar.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin:16px 0 6px;padding-bottom:4px;border-bottom:1px solid #e2e8f0">📍 User Location (Optional)</div>', unsafe_allow_html=True)
user_lat = st.sidebar.text_input("Latitude")
user_lon = st.sidebar.text_input("Longitude")
user_location = None
try:
    if user_lat and user_lon:
        user_location = (float(user_lat), float(user_lon))
except:
    user_location = None

# ---------------------------
# SECTOR MAP SETTINGS
# ---------------------------
st.sidebar.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin:16px 0 6px;padding-bottom:4px;border-bottom:1px solid #e2e8f0">⚙️ Sector Display Settings</div>', unsafe_allow_html=True)
sector_radius = st.sidebar.slider("Sector Radius (km)", 0.1, 2.0, 0.5, 0.1)
sector_beamwidth = st.sidebar.slider("Sector Beamwidth (degrees)", 30, 120, 65, 5)
show_all_sectors = st.sidebar.checkbox("Show ALL Sectors on Map", value=False)

# ---------------------------
# APPLY FILTERS
# ---------------------------
df = trace_df.copy()

if selected_site != "All":
    df = df[df[trace_col] == selected_site]
# IMSI filter removed — filtering is done by MSISDN file selection above
if selected_service and selected_service != "All":
    df = df[df["Service Type"].astype(str) == selected_service]
for col, val in extra_filters.items():
    if val != "All":
        df = df[df[col].astype(str) == val]
df = df[(df["Start Time"] >= time_range[0]) & (df["Start Time"] <= time_range[1])]

if df.empty:
    st.warning("⚠️ No data after filters")
    df = trace_df.copy()

# ---------------------------
# DEVICE INFO
# ---------------------------
device_info = "N/A"
if "Device Brand" in df.columns and "Device Model" in df.columns:
    devices = df["Device Brand"].astype(str).fillna("") + " " + df["Device Model"].astype(str).fillna("")
    device_info = ", ".join(devices.dropna().unique()[:5])

# ---------------------------
# KPI
# ---------------------------
st.markdown('<div style="margin:8px 0 4px"><span style="font-size:14px;font-weight:700;color:#1e293b">📊 Key Performance Indicators</span></div>', unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.markdown(f"""<div style="background:#fff;border-radius:14px;padding:18px 20px;box-shadow:0 2px 12px rgba(0,0,0,.06);border-top:4px solid #6366f1">
        <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em">📡 Sites</div>
        <div style="font-size:28px;font-weight:700;color:#1e293b;line-height:1.2">{df["_site_id_clean"].nunique()}</div>
        <div style="font-size:11px;color:#94a3b8">Active Sites</div></div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div style="background:#fff;border-radius:14px;padding:18px 20px;box-shadow:0 2px 12px rgba(0,0,0,.06);border-top:4px solid #22c55e">
        <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em">⚡ Avg Throughput</div>
        <div style="font-size:28px;font-weight:700;color:#1e293b;line-height:1.2">{round(df["DL_Mbps"].mean(), 2) if "DL_Mbps" in df.columns and df["DL_Mbps"].notna().any() else round(df["Throughput"].mean(), 2)}</div>
        <div style="font-size:11px;color:#94a3b8">Mbps</div></div>""", unsafe_allow_html=True)
with c3:
    users_count = df["IMSI"].nunique() if "IMSI" in df.columns else 0
    st.markdown(f"""<div style="background:#fff;border-radius:14px;padding:18px 20px;box-shadow:0 2px 12px rgba(0,0,0,.06);border-top:4px solid #3b82f6">
        <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em">👤 Users</div>
        <div style="font-size:28px;font-weight:700;color:#1e293b;line-height:1.2">{users_count}</div>
        <div style="font-size:11px;color:#94a3b8">MSISDN: {msisdn_value}</div></div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div style="background:#fff;border-radius:14px;padding:18px 20px;box-shadow:0 2px 12px rgba(0,0,0,.06);border-top:4px solid #f59e0b">
        <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em">📱 Device</div>
        <div style="font-size:13px;font-weight:700;color:#1e293b;line-height:1.4;margin-top:4px">{device_info[:30] + "…" if len(str(device_info)) > 30 else device_info}</div>
        <div style="font-size:11px;color:#94a3b8">Model Info</div></div>""", unsafe_allow_html=True)
with c5:
    st.markdown(f"""<div style="background:#fff;border-radius:14px;padding:18px 20px;box-shadow:0 2px 12px rgba(0,0,0,.06);border-top:4px solid #8b5cf6">
        <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em">📊 Records</div>
        <div style="font-size:28px;font-weight:700;color:#1e293b;line-height:1.2">{len(df):,}</div>
        <div style="font-size:11px;color:#94a3b8">Total Rows</div></div>""", unsafe_allow_html=True)
with c6:
    if "App Name" in df.columns:
        _apps = df["App Name"].dropna().astype(str)
        _apps = _apps[~_apps.str.strip().str.upper().isin(["NAN","NONE",""])]
        _top3 = _apps.value_counts().head(3).index.tolist()
        _medals = ["🥇","🥈","🥉"]
        _apps_html = "".join(
            f'<div style="font-size:11px;font-weight:600;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_medals[i]} {a}</div>'
            for i, a in enumerate(_top3)
        ) if _top3 else '<div style="font-size:11px;color:#94a3b8">No data</div>'
    else:
        _apps_html = '<div style="font-size:11px;color:#94a3b8">No App column</div>'
    st.markdown(f"""<div style="background:#fff;border-radius:14px;padding:18px 20px;box-shadow:0 2px 12px rgba(0,0,0,.06);border-top:4px solid #06b6d4">
        <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em">📲 Top 3 Apps</div>
        <div style="margin-top:8px;display:flex;flex-direction:column;gap:4px">{_apps_html}</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:4px">Most Used</div></div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------
# DL & UL OVER TIME
# ---------------------------
st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">📈 DL & UL Throughput Over Time</div>''', unsafe_allow_html=True)

df["Time"] = df["Start Time"].dt.floor("min")

dl_col_name = next((c for c in df.columns if "downlink throughput" in c.lower()), None)
ul_col_name = next((c for c in df.columns if "uplink throughput" in c.lower()), None)

if dl_col_name and ul_col_name:
    df["DL_Mbps"] = pd.to_numeric(df[dl_col_name], errors="coerce") / 1000
    df["UL_Mbps"] = pd.to_numeric(df[ul_col_name], errors="coerce") / 1000

    time_df = df.groupby("Time")[["DL_Mbps", "UL_Mbps"]].mean().reset_index()

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=time_df["Time"], y=time_df["DL_Mbps"],
                              mode="lines", name="DL Throughput (Mbps)",
                              line=dict(color="purple", width=3), yaxis="y1"))
    fig1.add_trace(go.Scatter(x=time_df["Time"], y=time_df["UL_Mbps"],
                              mode="lines", name="UL Throughput (Mbps)",
                              line=dict(color="orange", width=3), yaxis="y2"))
    fig1.update_layout(
        title=dict(text="📶 DL vs UL Throughput Over Time", font=dict(size=18)),
        template="plotly_dark",
        xaxis=dict(title="Time"),
        yaxis=dict(title="DL Throughput (Mbps)", tickfont=dict(color="purple")),
        yaxis2=dict(title="UL Throughput (Mbps)", tickfont=dict(color="orange"),
                    overlaying="y", side="right")
    )
    st.plotly_chart(fig1, use_container_width=True)

# ---------------------------
# HOURLY DL & UL
# ---------------------------
    st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">📊 Hourly DL & UL Throughput</div>''', unsafe_allow_html=True)
    df["Hour"] = df["Start Time"].dt.floor("h")
    hour_df = df.groupby("Hour")[["DL_Mbps", "UL_Mbps"]].mean().reset_index()

    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    fig2.add_trace(go.Scatter(x=hour_df["Hour"], y=hour_df["DL_Mbps"],
                              name="DL Throughput (Mbps)", mode="lines+markers",
                              line=dict(color="purple", width=3)), secondary_y=False)
    fig2.add_trace(go.Scatter(x=hour_df["Hour"], y=hour_df["UL_Mbps"],
                              name="UL Throughput (Mbps)", mode="lines+markers",
                              line=dict(color="orange", width=3)), secondary_y=True)
    fig2.update_layout(title="📊 Hourly DL & UL Throughput", template="plotly_dark")
    fig2.update_yaxes(title_text="DL Throughput (Mbps)", secondary_y=False)
    fig2.update_yaxes(title_text="UL Throughput (Mbps)", secondary_y=True)
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------
# HOURLY DL THROUGHPUT + DL TRAFFIC
# ---------------------------
st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">📊 Hourly Average DL Throughput & DL Traffic</div>''', unsafe_allow_html=True)
dl_col = next((c for c in df.columns if "downlink throughput" in c.lower()), None)

if dl_col:
    df["DL_Mbps"] = pd.to_numeric(df[dl_col], errors="coerce") / 1000
    df["Hour"] = df["Start Time"].dt.floor("h")

    hourly_dl = (
        df.groupby("Hour")
        .agg(Avg_DL_Throughput=("DL_Mbps", "mean"), Avg_DL_Traffic=("Traffic_MB", "mean"))
        .reset_index()
    )

    fig_dl = make_subplots(specs=[[{"secondary_y": True}]])
    fig_dl.add_trace(go.Scatter(x=hourly_dl["Hour"], y=hourly_dl["Avg_DL_Throughput"],
                                name="DL Throughput (Mbps)", mode="lines+markers"),
                     secondary_y=False)
    fig_dl.add_trace(go.Bar(x=hourly_dl["Hour"], y=hourly_dl["Avg_DL_Traffic"],
                            name="DL Traffic (MB)", opacity=0.7),
                     secondary_y=True)
    fig_dl.update_layout(template=plot_template, title="Hourly Average DL Throughput & DL Traffic", height=500)
    fig_dl.update_yaxes(title_text="DL Throughput (Mbps)", secondary_y=False)
    fig_dl.update_yaxes(title_text="DL Traffic (MB)", secondary_y=True)
    st.plotly_chart(fig_dl, use_container_width=True)
    st.markdown('<div style="background:#fff;border-radius:12px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.05);margin-top:8px">', unsafe_allow_html=True)
    st.dataframe(hourly_dl, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.warning("⚠️ Downlink Throughput column not found")

# ---------------------------
# NETWORK COMPARISON
# ---------------------------
st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">📊 Network Performance Comparison</div>''', unsafe_allow_html=True)

net_col = next((c for c in ["Roaming Status", "Network Type", "Service Provider"] if c in df.columns), None)

if net_col:
    df["Network"] = df[net_col].astype(str).str.upper()
    dl_kbps = next((c for c in df.columns if "downlink throughput" in c.lower()), None)
    ul_kbps = next((c for c in df.columns if "uplink throughput" in c.lower()), None)

    if dl_kbps and ul_kbps:
        # Use temp columns to avoid overwriting the original kbps columns (prevents double division)
        _dl_mbps_tmp = pd.to_numeric(df[dl_kbps], errors="coerce") / 1000
        _ul_mbps_tmp = pd.to_numeric(df[ul_kbps], errors="coerce") / 1000

        _net_tmp_df = df[["Network", "Throughput"]].copy()
        _net_tmp_df["_dl_mbps"] = _dl_mbps_tmp
        _net_tmp_df["_ul_mbps"] = _ul_mbps_tmp

        comparison = (
            _net_tmp_df.groupby("Network")
            .agg(Avg_DL=("_dl_mbps", "mean"), Median_DL=("_dl_mbps", "median"),
                 Avg_UL=("_ul_mbps", "mean"), Median_UL=("_ul_mbps", "median"),
                 Records=("Throughput", "count"))
            .reset_index()
        )

        def classify_network(val):
            return "ROAMING" if "ROAM" in str(val).upper() else "LOCAL"

        comparison["Category"] = comparison["Network"].apply(classify_network)
        color_map = {"LOCAL": "purple", "ROAMING": "orange"}

        fig3 = px.bar(comparison, x="Network", y="Avg_DL", text_auto=".2f",
                      template=plot_template, color="Category", color_discrete_map=color_map)
        fig3.update_layout(xaxis_title="Network Type", yaxis_title="Avg Downlink (Mbps)",
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           bargap=0.4, legend_title_text="Connection Type", font=dict(size=13))
        fig3.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig3, use_container_width=True)
        st.markdown('<div style="background:#fff;border-radius:12px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.05);margin-top:8px">', unsafe_allow_html=True)
        st.dataframe(comparison, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        best = comparison.sort_values("Avg_DL", ascending=False).iloc[0]
        st.success(f"🏆 Best Network = {best['Network']}")
else:
    st.warning("⚠️ No network column found")

# ---------------------------
# MAP WITH SECTORS
# ---------------------------
st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">🗺️ Sites Map with Sectors</div>''', unsafe_allow_html=True)

site_perf = df.groupby("_site_id_clean")["Throughput"].mean().reset_index()
serving_sites = set(site_perf["_site_id_clean"].unique())

# ------------------------------------------------------------------
# MATCHING:
# Trace column contains Sector Name (e.g. LDELM28621_5)
# Extract real Site ID (without _N suffix) to match with on_air_df
# ------------------------------------------------------------------

# Step 1: exact match — extracted Site ID → on_air Site ID
sites_unique = on_air_df.drop_duplicates("Site ID")[["Site ID", "Latitude", "Longitude"]].copy()
map_df = pd.merge(site_perf, sites_unique, left_on="_site_id_clean", right_on="Site ID", how="left")

# Step 2: For unmatched — try exact match after clean only (no fuzzy)
unmatched_mask = map_df["Latitude"].isna()
if unmatched_mask.any():
    unmatched_ids = map_df.loc[unmatched_mask, "_site_id_clean"].tolist()
    fallback_rows = []
    for tid in unmatched_ids:
        site_rows = on_air_df[on_air_df["Site ID"] == tid]
        if not site_rows.empty:
            sec_row = site_rows.iloc[0]
            tp_val = site_perf[site_perf["_site_id_clean"] == tid]["Throughput"].values[0]
            fallback_rows.append({
                "_site_id_clean": tid, "Throughput": tp_val,
                "Site ID": sec_row["Site ID"],
                "Latitude": sec_row["Latitude"],
                "Longitude": sec_row["Longitude"]
            })
    if fallback_rows:
        map_df = pd.concat([map_df[~unmatched_mask], pd.DataFrame(fallback_rows)], ignore_index=True)

map_df = map_df.dropna(subset=["Latitude", "Longitude"])

matched_count = len(map_df)
total_trace_sites = len(site_perf)
unmatched_count = total_trace_sites - matched_count
st.info(f"🗺️ Matched **{matched_count}** out of **{total_trace_sites}** trace sites to map coordinates")
if unmatched_count > 0:
    unmatched_ids_set = set(site_perf["_site_id_clean"].unique()) - set(map_df["_site_id_clean"].unique())
    st.warning(f"⚠️ **{unmatched_count}** site(s) not found in On-Air file: `{', '.join(sorted(unmatched_ids_set))}`")

if not map_df.empty:
    center_lat = map_df["Latitude"].mean()
    center_lon = map_df["Longitude"].mean()
else:
    center_lat, center_lon = 30.05, 31.3

m = folium.Map(location=[center_lat, center_lon], zoom_start=10)

legend_html = """
<div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
            background: white; padding: 10px 15px; border-radius: 8px;
            border: 2px solid #ccc; font-size: 12px; max-width:200px">
  <b>🗺️ Map Legend</b><br><br>
  <b>Sites:</b><br>
  <span style="color:green">●</span> Good Throughput<br>
  <span style="color:red">●</span> Low Throughput<br>
  <span style="color:blue">●</span> On-Air (no trace)<br>
  <span style="color:red">◼</span> Down Site<br>
  <span style="color:#3498db">◼</span> Planned Site<br>
  <span style="color:purple">★</span> User Location<br><br>
  <b>Sector Layers:</b><br>
  <span style="color:#e74c3c">◼</span> L700<br>
  <span style="color:#2ecc71">◼</span> L1800<br>
  <span style="color:#9b59b6">◼</span> L2600<br>
  <span style="color:#e91e63">◼</span> NR/5G<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

if show_all_sectors:
    sectors_to_draw = on_air_df.copy()
else:
    # Draw all sectors whose Site ID exists in the trace — exactly like before
    matched_site_ids = set(map_df["Site ID"].dropna().unique())
    sectors_to_draw = on_air_df[on_air_df["Site ID"].isin(matched_site_ids)].copy()

# Draw sector cone for each row (each row = sector with different azimuth)
for _, sector in sectors_to_draw.iterrows():
    try:
        az = float(sector["Azimuth"]) if not pd.isna(sector["Azimuth"]) else 0
        lat = float(sector["Latitude"])
        lon = float(sector["Longitude"])
        site_id = sector["Site ID"]

        site_tp = map_df[map_df["Site ID"] == site_id]["Throughput"]
        if not site_tp.empty:
            tp_val = site_tp.values[0]
            color = "red" if tp_val < 1 else "green"
        elif status_col and status_col in sector.index:
            color = get_sector_color(sector[status_col])
            tp_val = None
        else:
            color = "blue"
            tp_val = None

        layer_raw = sector.get("Layer", "")
        layers_list = parse_layers(layer_raw)

        draw_sector_cone(
            m, lat, lon, az,
            radius_km=sector_radius,
            beamwidth=sector_beamwidth,
            color=color,
            sector_row=sector,
            layers=layers_list,
            throughput=tp_val
        )
    except Exception:
        continue

# Central point for each Site (once only)
drawn_sites = set()
for _, sector in sectors_to_draw.iterrows():
    site_id = sector["Site ID"]
    if site_id in drawn_sites:
        continue
    try:
        lat = float(sector["Latitude"])
        lon = float(sector["Longitude"])
        site_tp = map_df[map_df["Site ID"] == site_id]["Throughput"]
        if not site_tp.empty:
            tp_val = float(site_tp.values[0])
            marker_color = "red" if tp_val < 1 else "green"
            folium.CircleMarker(
                [lat, lon], radius=5,
                color=marker_color, fill=True, fill_opacity=0.9,
                popup=f"{site_id} | TP: {round(tp_val, 2)} Mbps"
            ).add_to(m)
        else:
            folium.CircleMarker(
                [lat, lon], radius=4,
                color="blue", fill=True, fill_opacity=0.7,
                popup=site_id
            ).add_to(m)
        drawn_sites.add(site_id)
    except:
        continue

if planned_df is not None:
    shown_planned = set()
    for _, p in planned_df.iterrows():
        if p["Site ID"] in shown_planned:
            continue
        for _, a in map_df.iterrows():
            dist = haversine(p["Latitude"], p["Longitude"],
                             a["Latitude"], a["Longitude"])
            if dist <= 2:
                folium.CircleMarker(
                    [p["Latitude"], p["Longitude"]],
                    radius=6,
                    color="blue",
                    fill=True,
                    fill_opacity=0.6,
                    popup=f"PLANNED: {p['Site ID']}"
                ).add_to(m)
                shown_planned.add(p["Site ID"])
                break

# ---------------------------
# CUSTOMERS ON MAP — FIXED MSISDN MATCHING
# ---------------------------
if customers_df is not None:
    try:
        # Find MSISDN column in customers file
        msisdn_col_cust = next(
            (c for c in customers_df.columns if "problematic msisdn" in c.lower()), None
        ) or next(
            (c for c in customers_df.columns
             if any(x in c.lower() for x in ["msisdn", "mobile", "phone", "number"])),
            None
        )



        matched_customers = pd.DataFrame()

        if msisdn_col_cust and msisdn_normalized:
            # ✅ FIX: work on a COPY to avoid mutating the @st.cache_data DataFrame
            # Mutating the cached object directly causes Streamlit to throw an exception
            # OUTSIDE any try/except, which stops execution before st_folium() is called
            # and makes the map disappear entirely.
            _cdf = customers_df.copy()
            _cdf["_norm_msisdn"] = _cdf[msisdn_col_cust].astype(str).apply(norm_msisdn)

            # Strategy 1: exact match on normalized number
            matched_customers = _cdf[
                _cdf["_norm_msisdn"] == msisdn_normalized
            ].copy()

            # Strategy 2: partial/suffix match — last 8 digits
            if matched_customers.empty:
                suffix_8 = msisdn_normalized[-8:] if len(msisdn_normalized) >= 8 else msisdn_normalized
                matched_customers = _cdf[
                    _cdf["_norm_msisdn"].str.endswith(suffix_8)
                ].copy()

            # Strategy 3: contains the raw msisdn_value anywhere
            if matched_customers.empty:
                matched_customers = _cdf[
                    _cdf[msisdn_col_cust].astype(str).str.contains(
                        msisdn_normalized[-8:], na=False
                    )
                ].copy()



        elif msisdn_col_cust is None:
            st.sidebar.warning("⚠️ No MSISDN column found in Customers file")

        cust_feature_group = folium.FeatureGroup(name=f"👤 Customers ({len(matched_customers)})", show=True)

        if matched_customers.empty:
            st.info(f"ℹ️ No customers matched MSISDN: {msisdn_value}")
        else:
            st.success(f"✅ Found {len(matched_customers)} customer record(s) matching MSISDN: {msisdn_value}")

        # Compute occurrence count per site
        loc_counts = {}
        for _, cust in matched_customers.iterrows():
            try:
                lat_val = cust.get("Latitude")
                lon_val = cust.get("Longitude")
            
                if lat_val is None or lon_val is None:
                    continue
            
                try:
                    lat = float(lat_val)
                    lon = float(lon_val)
                    if pd.isna(lat) or pd.isna(lon):
                        continue
                    key = (round(lat, 6), round(lon, 6))
                    loc_counts[key] = loc_counts.get(key, 0) + 1
                except (ValueError, TypeError):
                    continue
            except:
                continue

        loc_seen = {}
        for _, cust in matched_customers.iterrows():
            try:
                # Safe coordinate extraction
                lat_val = cust.get("Latitude")
                lon_val = cust.get("Longitude")
            
                # Convert to float safely
                if lat_val is None or lon_val is None:
                    continue
            
                try:
                    c_lat = float(lat_val)
                    c_lon = float(lon_val)
                except (ValueError, TypeError):
                    continue
            
                # Skip if coordinates are invalid
                if pd.isna(c_lat) or pd.isna(c_lon):
                    continue
            
                key = (round(c_lat, 6), round(c_lon, 6))
                idx = loc_seen.get(key, 0)
                loc_seen[key] = idx + 1
                total = loc_counts.get(key, 1)  # Safer dict access

                # offset Small so repeated markers do not overlap
                c_lat += 0.0001 * idx
                c_lon += 0.0001 * idx

                status_val = str(cust.get("Status", "")).upper()
                if "CLOSED" in status_val or "RESOLVED" in status_val:
                    header_color = "#27ae60"; marker_color = "green"; status_icon = "✅"
                elif "QUEUED" in status_val or "OPEN" in status_val or "PROGRESS" in status_val:
                    header_color = "#c0392b"; marker_color = "red"; status_icon = "🔴"
                else:
                    header_color = "#8e44ad"; marker_color = "purple"; status_icon = "👤"

                msisdn_val = str(cust.get(msisdn_col_cust, "Customer")) if msisdn_col_cust else "Customer"
                tooltip_text = f"{status_icon} {msisdn_val}"
                if total > 1:
                    tooltip_text += f" ({idx+1}/{total} repeated)"

                # Build full Customer data table
                popup_rows = ""
                skip_cols = {"Latitude", "Longitude", "MSISDN_clean", "_norm_msisdn"}
                for col, val in cust.items():
                    if col in skip_cols:
                        continue
                    val_str = str(val).strip().replace("\xa0", " ").replace("\\", " / ").replace("\r", " ").replace("\n", " ")
                    if val_str in ("", "nan", "None", "NaT"):
                        continue
                    popup_rows += (f"<tr style='border-bottom:1px solid #f0f0f0'>"
                                   f"<td style='padding:3px 8px;color:#666;white-space:nowrap;font-weight:bold'>{col}</td>"
                                   f"<td style='padding:3px 8px'>{val_str}</td></tr>")

                repeat_banner = ""
                if total > 1:
                    repeat_banner = (f"<div style='background:#fff3cd;color:#856404;padding:5px 10px;"
                                     f"font-size:11px;font-weight:bold'>"
                                     f"⚠️ Repeated {total}x at same location (showing {idx+1}/{total})</div>")

                popup_html = f"""
                <div style='font-family:Arial;font-size:12px;min-width:260px;max-width:360px;
                            box-shadow:0 2px 8px rgba(0,0,0,0.2);border-radius:6px;overflow:hidden'>
                  <div style='background:{header_color};color:white;padding:6px 10px;font-weight:bold;font-size:13px'>
                    {status_icon} {msisdn_val}
                  </div>
                  <div style='max-height:300px;overflow-y:auto'>
                    <table style='width:100%;border-collapse:collapse'>
                      {popup_rows}
                    </table>
                  </div>
                  {repeat_banner}
                </div>"""

                folium.Marker(
                    [c_lat, c_lon],
                    popup=folium.Popup(popup_html, max_width=380),
                    icon=folium.Icon(color=marker_color, icon="user", prefix="fa"),
                    tooltip=tooltip_text
                ).add_to(cust_feature_group)

            except:
                continue

        cust_feature_group.add_to(m)

    except Exception as _cust_map_err:
        import traceback
        st.warning(f"⚠️ Customer layer skipped — {_cust_map_err}")

# ---------------------------
# USER LOCATION
# ---------------------------
if user_location is not None:
    folium.Marker(
        user_location,
        popup="👤 User Location",
        icon=folium.Icon(color="purple", icon="user")
    ).add_to(m)
    folium.Circle(
        location=user_location, radius=500,
        color="purple", fill=True, fill_opacity=0.1
    ).add_to(m)

# ---------------------------
# DOWN SITES IMPACT
# ---------------------------
st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">🚨 Down Sites Impact Analysis</div>''', unsafe_allow_html=True)
alerts = []

if down_df is not None:
    shown_down = set()
    for _, down in down_df.iterrows():
        if down["Site ID"] in shown_down:
            continue
        for _, serving in map_df.iterrows():
            if down["Site ID"] == serving["Site ID"]:
                continue
            dist = haversine(down["Latitude"], down["Longitude"],
                             serving["Latitude"], serving["Longitude"])
            if dist <= 2:
                alerts.append({
                    "Down Site": down["Site ID"],
                    "Serving Site": serving["Site ID"],
                    "Distance (KM)": round(dist, 2)
                })
                folium.CircleMarker(
                    [down["Latitude"], down["Longitude"]],
                    radius=9, color="red", fill=True,
                    fill_color="red", fill_opacity=0.7,
                    popup=f"DOWN SITE: {down['Site ID']}"
                ).add_to(m)
                shown_down.add(down["Site ID"])
                break

if alerts:
    df_alerts = pd.DataFrame(alerts).drop_duplicates().sort_values("Distance (KM)")
    st.markdown('<div style="background:#fff;border-radius:12px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.05);margin-top:8px">', unsafe_allow_html=True)
    st.dataframe(df_alerts, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.success("✅ No impacted serving sites near down sites")

# ---------------------------
# LAYER CONTROL + SHOW MAP
# ---------------------------
folium.LayerControl(collapsed=False).add_to(m)
st_folium(m, use_container_width=True, height=580)




def build_export_html():
    import plotly.io as pio
    import json as _json

    export_date = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")

    # ── Plotly JS — CDN only (much faster build, loads in browser) ──
    plotly_js_tag = '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>'

    # ── Add all computed columns to trace_df_all so the HTML works correctly ──
    _dl_raw_all = next((c for c in trace_df_all.columns if "downlink throughput" in c.lower()), None)
    _ul_raw_all = next((c for c in trace_df_all.columns if "uplink throughput"   in c.lower()), None)
    _traffic_col_all = None
    for _c in trace_df_all.columns:
        if "downlink" in _c.lower() and "traffic" in _c.lower():
            _traffic_col_all = _c; break
    if _traffic_col_all is None:
        for _c in trace_df_all.columns:
            if "downlink" in _c.lower():
                _traffic_col_all = _c; break

    if _dl_raw_all and "DL_Mbps" not in trace_df_all.columns:
        trace_df_all["DL_Mbps"] = pd.to_numeric(trace_df_all[_dl_raw_all], errors="coerce") / 1000
    if _ul_raw_all and "UL_Mbps" not in trace_df_all.columns:
        trace_df_all["UL_Mbps"] = pd.to_numeric(trace_df_all[_ul_raw_all], errors="coerce") / 1000
    if _traffic_col_all and "Traffic_MB" not in trace_df_all.columns:
        trace_df_all["Traffic_MB"] = trace_df_all[_traffic_col_all].apply(convert_to_mb)
    if "Traffic_MB" in trace_df_all.columns and "Duration" in trace_df_all.columns and "Throughput" not in trace_df_all.columns:
        trace_df_all["Throughput"] = (trace_df_all["Traffic_MB"] * 8) / trace_df_all["Duration"].replace(0, float("nan"))

    # Add _site_id_clean to trace_df_all (important for merge)
    if "_site_id_clean" not in trace_df_all.columns:
        trace_df_all["_site_id_clean"] = trace_df_all[trace_col].apply(extract_site_id)

    # ── Export trace data as JSON — All traces so the MSISDN selector in HTML works ──
    export_df = trace_df_all.copy()
    export_df["Start Time"] = export_df["Start Time"].astype(str)
    export_df["End Time"]   = export_df["End Time"].astype(str)

    # ── Build site→coords mapping (extracted Site ID match) ──
    _site_perf_exp = export_df.groupby("_site_id_clean")["Throughput"].mean().reset_index() if "Throughput" in export_df.columns else pd.DataFrame(columns=["_site_id_clean", "Throughput"])
    _sites_unique_exp = on_air_df.drop_duplicates("Site ID")[["Site ID", "Latitude", "Longitude"]].copy()
    _map_exp = pd.merge(_site_perf_exp, _sites_unique_exp, left_on="_site_id_clean", right_on="Site ID", how="left")
    _map_exp = _map_exp.dropna(subset=["Latitude", "Longitude"])
    matched_site_ids_export = set(_map_exp["Site ID"].dropna().unique())

    # Keep only columns needed for charts + filters
    _essential = set([trace_col, "_site_id_clean", "Start Time", "End Time", "IMSI", "_msisdn_file", "Service Type",
        "App Name", "Radio Access Type", "Roaming Status",
        "Throughput", "Traffic_MB", "DL_Mbps", "UL_Mbps", "Duration", "Network"])
    for _c in export_df.columns:
        if "downlink" in _c.lower() or "uplink" in _c.lower():
            _essential.add(_c)
        if "device" in _c.lower() or "brand" in _c.lower() or "model" in _c.lower():
            _essential.add(_c)

    slim_cols = [c for c in export_df.columns if c in _essential]
    export_df = export_df[slim_cols].fillna("")

    # Collect unique values for filter dropdowns
    all_sites    = sorted(export_df[trace_col].dropna().unique().tolist())
    all_imsi     = sorted(export_df["IMSI"].dropna().astype(str).unique().tolist()) if "IMSI" in export_df.columns else []
    # MSISDN options for the HTML selector — same labels as Streamlit (includes Customer Name)
    all_msisdn_norm = list(msisdn_map.keys())
    all_msisdn_display = [msisdn_map.get(x, x) for x in all_msisdn_norm]
    all_service  = sorted(export_df["Service Type"].dropna().astype(str).unique().tolist()) if "Service Type" in export_df.columns else []
    all_appname  = sorted(export_df["App Name"].dropna().astype(str).unique().tolist()) if "App Name" in export_df.columns else []
    all_rat      = sorted(export_df["Radio Access Type"].dropna().astype(str).unique().tolist()) if "Radio Access Type" in export_df.columns else []
    all_roaming  = sorted(export_df["Roaming Status"].dropna().astype(str).unique().tolist()) if "Roaming Status" in export_df.columns else []

    min_time_str = str(export_df["Start Time"].min())[:16]
    max_time_str = str(export_df["Start Time"].max())[:16]

    # Round floats to reduce JSON size
    for _c in ["Throughput", "Traffic_MB", "DL_Mbps", "UL_Mbps", "Duration"]:
        if _c in export_df.columns:
            export_df[_c] = pd.to_numeric(export_df[_c], errors="coerce").round(3).fillna(0)

    data_json = _json.dumps(export_df.to_dict(orient="records"), ensure_ascii=False, default=str)

    # ── Sectors — slim for map ──
    _sec_cols = ["Site ID", "Latitude", "Longitude", "Azimuth"]
    if status_col:
        _sec_cols.append(status_col)
    if "Layer" in on_air_df.columns:
        _sec_cols.append("Layer")

    # Get all site IDs from trace_df_all directly (safer than merge)
    _all_trace_site_ids = set(
        trace_df_all["_site_id_clean"].dropna().unique()
    ) - {"", "--", "NAN", "NONE"}

    sectors_export = on_air_df[
        on_air_df["Site ID"].isin(_all_trace_site_ids)
    ][_sec_cols].copy().fillna("")
    sectors_json = _json.dumps(sectors_export.to_dict(orient="records"), ensure_ascii=False, default=str)

    # ── Per-MSISDN: avg DL throughput + display label + sectors ──
    _dl_raw_col = next((c for c in trace_df_all.columns if "downlink throughput" in c.lower()), None)
    _msisdn_kpis = {}   # norm → {avg_tp, label, site_ids}
    _sec_cols_set = set(_sec_cols)
    for _mn, _ml in msisdn_map.items():
        _sub = trace_df_all[trace_df_all["_msisdn_file"] == _mn]
        if _dl_raw_col:
            _dl_vals = pd.to_numeric(_sub[_dl_raw_col], errors="coerce").dropna()
            _avg = round(float(_dl_vals.mean()) / 1000, 2) if len(_dl_vals) else 0
        else:
            _avg = round(float(_sub["Throughput"].mean()), 2) if "Throughput" in _sub.columns and len(_sub) else 0
        _site_ids = set(_sub["_site_id_clean"].dropna().unique())
        _msisdn_kpis[_mn] = {"avg_tp": _avg, "label": _ml, "site_ids": list(_site_ids)}

    # ── Sectors per MSISDN — exact + prefix fuzzy match ──
    _sectors_by_msisdn = {}
    for _mn, _info in _msisdn_kpis.items():
        _sids = set(_info["site_ids"]) - {"", "--", "NAN", "NONE"}
        # exact match — fast isin lookup
        _matched = on_air_df[on_air_df["Site ID"].isin(_sids)][_sec_cols].copy()
        _sectors_by_msisdn[_mn] = _matched.fillna("").to_dict(orient="records")

    msisdn_kpis_json     = _json.dumps(_msisdn_kpis,       ensure_ascii=False, default=str)
    sectors_by_msisdn_json = _json.dumps(_sectors_by_msisdn, ensure_ascii=False, default=str)

    # ── Build all_map_df including all sites from all MSISDNs (not just selected) ──
    _all_site_perf = trace_df_all.groupby("_site_id_clean")["Throughput"].mean().reset_index() if "Throughput" in trace_df_all.columns else pd.DataFrame(columns=["_site_id_clean", "Throughput"])
    _all_sites_unique = on_air_df.drop_duplicates("Site ID")[["Site ID", "Latitude", "Longitude"]].copy()
    _all_map_df = pd.merge(_all_site_perf, _all_sites_unique, left_on="_site_id_clean", right_on="Site ID", how="left")
    _all_map_df = _all_map_df.dropna(subset=["Latitude", "Longitude"])

    # ── Build per-MSISDN map_df for each MSISDN ──
    def _build_map_df_for_msisdn(mn):
        _sub = trace_df_all[trace_df_all["_msisdn_file"] == mn]
        _sp  = _sub.groupby("_site_id_clean")["Throughput"].mean().reset_index() if "Throughput" in _sub.columns else pd.DataFrame(columns=["_site_id_clean", "Throughput"])
        _mdf = pd.merge(_sp, _all_sites_unique, left_on="_site_id_clean", right_on="Site ID", how="left")
        return _mdf.dropna(subset=["Latitude", "Longitude"])

    # ── export All down records (JS will fetch lat/lon from SECTORS and filter by proximity) ──
    def _export_down():
        if down_df is None or down_df.empty:
            return []
        return [{k: str(v) for k, v in r.items() if k not in ["_norm_msisdn"]}
                for _, r in down_df.iterrows()]

    # ── export Planned exactly (has lat/lon) ──
    def _export_planned():
        if planned_df is None or planned_df.empty:
            return []
        return [{k: str(v) for k, v in r.items() if k not in ["_norm_msisdn"]}
                for _, r in planned_df.iterrows()]

    down_export_records    = _export_down()
    planned_export_records = _export_planned()
    down_json    = _json.dumps(down_export_records,    ensure_ascii=False, default=str)
    planned_json = _json.dumps(planned_export_records, ensure_ascii=False, default=str)

    # per-MSISDN: Same data — JS will filter by each MSISDN serving sites
    _down_by_msisdn    = {_mn: down_export_records    for _mn in all_msisdn_norm}
    _planned_by_msisdn = {_mn: planned_export_records for _mn in all_msisdn_norm}
    down_by_msisdn_json    = _json.dumps(_down_by_msisdn,    ensure_ascii=False, default=str)
    planned_by_msisdn_json = _json.dumps(_planned_by_msisdn, ensure_ascii=False, default=str)

    # ── Customers For each MSISDN (same 3 strategies exactly) ──
    customers_by_msisdn = {}
    if customers_df is not None:
        _msisdn_col_exp = next(
            (c for c in customers_df.columns if "problematic msisdn" in c.lower()), None
        ) or next(
            (c for c in customers_df.columns
             if any(x in c.lower() for x in ["msisdn", "mobile", "phone", "number"])),
            None
        )
        if _msisdn_col_exp and "_norm_msisdn" not in customers_df.columns:
            customers_df["_norm_msisdn"] = customers_df[_msisdn_col_exp].astype(str).apply(norm_msisdn)

        for _mn in all_msisdn_norm:
            _matched = pd.DataFrame()
            if _msisdn_col_exp:
                # Strategy 1: exact
                _matched = customers_df[customers_df["_norm_msisdn"] == _mn].copy()
                # Strategy 2: suffix 8
                if _matched.empty:
                    _sfx = _mn[-8:] if len(_mn) >= 8 else _mn
                    _matched = customers_df[customers_df["_norm_msisdn"].str.endswith(_sfx)].copy()
                # Strategy 3: contains
                if _matched.empty:
                    _matched = customers_df[
                        customers_df[_msisdn_col_exp].astype(str).str.contains(_mn[-8:], na=False)
                    ].copy()
            if not _matched.empty:
                _exp = _matched.drop(columns=["_norm_msisdn"], errors="ignore").fillna("")
                customers_by_msisdn[_mn] = [{k: str(v) for k, v in r.items()}
                                             for r in _exp.to_dict(orient="records")]
            else:
                customers_by_msisdn[_mn] = []

    customers_json = _json.dumps(customers_by_msisdn, ensure_ascii=False, default=str)

    # ── Map center based on matched sites only ──
    map_center_lat = float(_map_exp["Latitude"].mean()) if not _map_exp.empty else 30.05
    map_center_lon = float(_map_exp["Longitude"].mean()) if not _map_exp.empty else 31.3

    # ── Down sites table ──
    down_table = ""
    if alerts:
        df_al = pd.DataFrame(alerts).drop_duplicates().sort_values("Distance (KM)")
        al_rows = "".join(
            f"<tr><td>{r['Down Site']}</td><td>{r['Serving Site']}</td><td>{r['Distance (KM)']}</td></tr>"
            for _, r in df_al.iterrows()
        )
        down_table = f"""
        <div class="sec-title">🔴 Down Sites Impact</div>
        <div class="tbl-wrap">
          <table><thead><tr><th>Down Site</th><th>Serving Site</th><th>Distance (KM)</th></tr></thead>
          <tbody>{al_rows}</tbody></table>
        </div>"""

    # ── Build filter option HTML helpers ──
    def opts(lst):
        return "".join(f'<option value="{v}">{v}</option>' for v in lst)

    def multi_opts(lst):
        return "".join(f'<option value="{v}">{v}</option>' for v in lst)

    TRACE_COL_JS = trace_col.replace("'", "\'")

    # DL_Mbps and UL_Mbps always exist in export_df after conversion above
    _dl_js  = "DL_Mbps"
    _ul_js  = "UL_Mbps"
    _net_js = next((c for c in ["Roaming Status","Network Type","Service Provider"] if c in export_df.columns), "")

    # ── Q&A section variables ────────────────────────────────────
    def _qmean(col):
        s = pd.to_numeric(df[col], errors="coerce").dropna() if col in df.columns else pd.Series(dtype=float)
        return round(float(s.mean()), 2) if len(s) else 0.0
    def _qpct(part, total):
        return round(100 * part / total, 1) if total else 0.0

    _q_dl_col = next((c for c in df.columns if "downlink throughput" in c.lower()), None)
    _q_ul_col = next((c for c in df.columns if "uplink throughput"   in c.lower()), None)
    q_dl_avg    = round(float(pd.to_numeric(df[_q_dl_col], errors="coerce").dropna().mean()) / 1000, 2) if _q_dl_col else 0
    q_dl_max    = round(float(pd.to_numeric(df[_q_dl_col], errors="coerce").dropna().max())  / 1000, 2) if _q_dl_col else 0
    q_dl_min    = round(float(pd.to_numeric(df[_q_dl_col], errors="coerce").dropna().min())  / 1000, 2) if _q_dl_col else 0
    q_dl_median = round(float(pd.to_numeric(df[_q_dl_col], errors="coerce").dropna().median())/ 1000, 2) if _q_dl_col else 0
    q_ul_avg    = round(float(pd.to_numeric(df[_q_ul_col], errors="coerce").dropna().mean()) / 1000, 2) if _q_ul_col else 0

    q_N     = len(df)
    q_total_dl_mb = df["Traffic_MB"].sum() if "Traffic_MB" in df.columns else 0
    q_total_dl_gb = round(q_total_dl_mb / 1024, 2)
    q_avg_per_rec = round(q_total_dl_mb / q_N, 2) if q_N else 0

    q_sites_all   = sorted(df["_site_id_clean"].dropna().unique().tolist())
    q_n_sites     = len(q_sites_all)
    q_sites_list  = ", ".join(q_sites_all) if q_sites_all else "N/A"

    # Use DL_Mbps for site throughput (correct Mbps), fallback to kbps/1000, then Throughput
    if "DL_Mbps" in df.columns:
        _q_site_tp = (pd.to_numeric(df["DL_Mbps"], errors="coerce")
                        .groupby(df["_site_id_clean"]).mean().dropna().round(2))
    elif _q_dl_col:
        _q_site_tp = ((pd.to_numeric(df[_q_dl_col], errors="coerce") / 1000)
                        .groupby(df["_site_id_clean"]).mean().dropna().round(2))
    else:
        _q_site_tp = (df.groupby("_site_id_clean")["Throughput"].mean().dropna()
                      if "Throughput" in df.columns else pd.Series(dtype=float))
    q_best_site  = _q_site_tp.idxmax()  if len(_q_site_tp) else "N/A"
    q_worst_site = _q_site_tp.idxmin()  if len(_q_site_tp) else "N/A"
    q_best_tp    = round(float(_q_site_tp.max()), 2) if len(_q_site_tp) else 0
    q_worst_tp   = round(float(_q_site_tp.min()), 2) if len(_q_site_tp) else 0

    # Classify rows using Mbps (not raw Throughput which has different units)
    if "DL_Mbps" in df.columns:
        _q_dl_mbps_s = pd.to_numeric(df["DL_Mbps"], errors="coerce").fillna(0)
    elif _q_dl_col:
        _q_dl_mbps_s = pd.to_numeric(df[_q_dl_col], errors="coerce").fillna(0) / 1000
    else:
        _q_dl_mbps_s = pd.to_numeric(df["Throughput"], errors="coerce").fillna(0) if "Throughput" in df.columns else pd.Series([0]*q_N)
    q_good_rows  = int((_q_dl_mbps_s > 1).sum())
    q_low_rows   = int(((_q_dl_mbps_s > 0) & (_q_dl_mbps_s <= 1)).sum())
    q_zero_rows  = int((_q_dl_mbps_s == 0).sum())
    q_good_pct   = _qpct(q_good_rows, q_N)
    q_low_pct    = _qpct(q_low_rows,  q_N)
    q_zero_pct   = _qpct(q_zero_rows, q_N)

    _q_rat_col = next((c for c in ["Radio Access Type"] if c in df.columns), None)
    if _q_rat_col:
        _q_rat_counts = df[_q_rat_col].dropna().astype(str).value_counts()
        q_rat_html = "<br>".join(f"<b>{k}:</b> {v:,} ({_qpct(v, q_N)}%)" for k, v in _q_rat_counts.items())
    else:
        q_rat_html = "N/A"

    _q_roam_col = next((c for c in ["Roaming Status"] if c in df.columns), None)
    if _q_roam_col:
        _q_roam_vals = df[_q_roam_col].astype(str).str.upper()
        q_local_cnt = int((_q_roam_vals.str.contains("LOCAL|HOME", na=False)).sum())
        q_roam_cnt  = q_N - q_local_cnt
    else:
        q_local_cnt = q_N; q_roam_cnt = 0
    q_local_pct = _qpct(q_local_cnt, q_N)
    q_roam_pct  = _qpct(q_roam_cnt,  q_N)

    _q_hourly = df.copy()
    _q_hourly["_hr"] = pd.to_datetime(_q_hourly["Start Time"], errors="coerce").dt.hour
    if _q_dl_col:
        _q_hourly["_dl"] = pd.to_numeric(_q_hourly[_q_dl_col], errors="coerce") / 1000
        _q_h = _q_hourly.groupby("_hr")["_dl"].mean().dropna()
    else:
        _q_h = pd.Series(dtype=float)
    q_best_hour  = int(_q_h.idxmax())  if len(_q_h) else None
    q_worst_hour = int(_q_h.idxmin()) if len(_q_h) else None
    q_best_hour_str  = f"{q_best_hour:02d}:00 — {round(float(_q_h[q_best_hour]),2)} Mbps"   if q_best_hour  is not None else "N/A"
    q_worst_hour_str = f"{q_worst_hour:02d}:00 — {round(float(_q_h[q_worst_hour]),2)} Mbps" if q_worst_hour is not None else "N/A"

    _q_loss_col  = next((c for c in df.columns if "packet loss" in c.lower() and "dl" in c.lower()), None)
    _q_delay_col = next((c for c in df.columns if "delay" in c.lower() and "dl" in c.lower()), None)
    _q_retx_col  = next((c for c in df.columns if "retransmission" in c.lower() and "dl" in c.lower()), None)
    _q_rtt_col   = next((c for c in df.columns if "rtt" in c.lower() and "dl" in c.lower()), None)
    q_dl_loss_avg  = round(float(pd.to_numeric(df[_q_loss_col],  errors="coerce").mean()), 2) if _q_loss_col  else None
    q_dl_delay_avg = round(float(pd.to_numeric(df[_q_delay_col], errors="coerce").mean()), 2) if _q_delay_col else None
    q_dl_retx_avg  = round(float(pd.to_numeric(df[_q_retx_col],  errors="coerce").mean()), 2) if _q_retx_col  else None
    q_dl_rtt_avg   = round(float(pd.to_numeric(df[_q_rtt_col],   errors="coerce").mean()), 2) if _q_rtt_col   else None
    q_dl_loss_str  = f"{q_dl_loss_avg}%"  if q_dl_loss_avg  is not None else "N/A"
    q_dl_delay_str = f"{q_dl_delay_avg} ms" if q_dl_delay_avg is not None else "N/A"

    q_score = 100
    if q_dl_loss_avg  and q_dl_loss_avg  > 1: q_score -= 15
    if q_dl_loss_avg  and q_dl_loss_avg  > 3: q_score -= 15
    if q_dl_retx_avg  and q_dl_retx_avg  > 1: q_score -= 10
    if q_dl_retx_avg  and q_dl_retx_avg  > 3: q_score -= 10
    if q_dl_delay_avg and q_dl_delay_avg > 50: q_score -= 10
    if q_dl_delay_avg and q_dl_delay_avg > 100: q_score -= 10
    if q_dl_avg < 2: q_score -= 15
    if q_dl_avg < 1: q_score -= 15
    q_score = max(q_score, 0)
    q_sq_color = "#22c55e" if q_score >= 70 else ("#f59e0b" if q_score >= 40 else "#e74c3c")
    q_sq_label = "Excellent 🟢" if q_score >= 70 else ("Average 🟡" if q_score >= 40 else "Poor 🔴")

    _q_app_col = next((c for c in df.columns if c == "App Name"), None)
    if _q_app_col:
        _q_apps = df[_q_app_col].dropna().astype(str)
        _q_apps = _q_apps[~_q_apps.str.strip().str.upper().isin(["NAN","NONE",""])]
        _q_top  = _q_apps.value_counts().head(5)
        medals  = ["🥇","🥈","🥉","4️⃣","5️⃣"]
        q_top_apps_html = "<br>".join(f"{medals[i]} <b>{a}:</b> {c:,} ({_qpct(c, q_N)}%)" for i,(a,c) in enumerate(_q_top.items()))
    else:
        q_top_apps_html = "N/A"

    q_time_start_str = df["Start Time"].min().strftime("%Y-%m-%d %H:%M") if "Start Time" in df.columns else "N/A"
    q_time_end_str   = df["Start Time"].max().strftime("%Y-%m-%d %H:%M") if "Start Time" in df.columns else "N/A"
    q_duration_h     = round((df["Start Time"].max() - df["Start Time"].min()).total_seconds() / 3600, 1) if "Start Time" in df.columns else 0
    # ── end Q&A variables ────────────────────────────────────────

    # ── Extra Q&A variables for full tab parity ──────────────────
    import json as _json2

    # helper: find column safely and compute mean/max/quantile with optional /1000 normalization
    def _qcol(keywords, df=df):
        """Return first column whose lowercase name contains ALL keywords."""
        kws = keywords if isinstance(keywords, list) else [keywords]
        return next((c for c in df.columns if all(k in c.lower() for k in kws)), None)

    def _qnum(col, op="mean", div=1):
        """Safe numeric aggregation on a column; returns None if col missing or all-NaN."""
        if col is None or col not in df.columns:
            return None
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(s) == 0:
            return None
        val = {"mean": s.mean, "max": s.max, "min": s.min,
               "median": s.median, "p10": lambda: s.quantile(0.10),
               "p90": lambda: s.quantile(0.90)}[op]()
        return round(float(val) / div, 2)

    # ── normalizer: are DL values in kbps (mean > 500) or already Mbps? ──
    _q_dl_div = 1000 if (_q_dl_col and pd.to_numeric(df[_q_dl_col], errors="coerce").mean() > 500) else 1
    _q_ul_div = 1000 if (_q_ul_col and pd.to_numeric(df[_q_ul_col], errors="coerce").mean() > 500) else 1

    # ── recompute core DL/UL with correct divisor ──
    q_dl_avg    = _qnum(_q_dl_col, "mean",   _q_dl_div) or 0
    q_dl_max    = _qnum(_q_dl_col, "max",    _q_dl_div) or 0
    q_dl_min    = _qnum(_q_dl_col, "min",    _q_dl_div) or 0
    q_dl_median = _qnum(_q_dl_col, "median", _q_dl_div) or 0
    q_ul_avg    = _qnum(_q_ul_col, "mean",   _q_ul_div) or 0

    # ── recompute best/worst site using correct Mbps ──
    if _q_dl_col and "_site_id_clean" in df.columns:
        _q_site_tp_s = (pd.to_numeric(df[_q_dl_col], errors="coerce")
                          .div(_q_dl_div)
                          .groupby(df["_site_id_clean"]).mean()
                          .dropna()
                          .round(2))
        q_best_site  = _q_site_tp_s.idxmax() if len(_q_site_tp_s) else "N/A"
        q_worst_site = _q_site_tp_s.idxmin() if len(_q_site_tp_s) else "N/A"
        q_best_tp    = round(float(_q_site_tp_s.max()), 2) if len(_q_site_tp_s) else 0
        q_worst_tp   = round(float(_q_site_tp_s.min()), 2) if len(_q_site_tp_s) else 0
    elif "Throughput" in df.columns and "_site_id_clean" in df.columns:
        _q_site_tp_s = (pd.to_numeric(df["Throughput"], errors="coerce")
                          .groupby(df["_site_id_clean"]).mean().dropna().round(2))
        q_best_site  = _q_site_tp_s.idxmax() if len(_q_site_tp_s) else "N/A"
        q_worst_site = _q_site_tp_s.idxmin() if len(_q_site_tp_s) else "N/A"
        q_best_tp    = round(float(_q_site_tp_s.max()), 2) if len(_q_site_tp_s) else 0
        q_worst_tp   = round(float(_q_site_tp_s.min()), 2) if len(_q_site_tp_s) else 0
    else:
        _q_site_tp_s = pd.Series(dtype=float)
        q_best_site = q_worst_site = "N/A"
        q_best_tp   = q_worst_tp   = 0

    # ── recompute performance rows using correct Mbps threshold ──
    if _q_dl_col:
        _q_dl_mbps = pd.to_numeric(df[_q_dl_col], errors="coerce").fillna(0) / _q_dl_div
    elif "Throughput" in df.columns:
        _q_dl_mbps = pd.to_numeric(df["Throughput"], errors="coerce").fillna(0)
    else:
        _q_dl_mbps = pd.Series([0] * q_N)
    q_good_rows = int((_q_dl_mbps > 1).sum())
    q_low_rows  = int(((_q_dl_mbps > 0) & (_q_dl_mbps <= 1)).sum())
    q_zero_rows = int((_q_dl_mbps == 0).sum())
    q_good_pct  = _qpct(q_good_rows, q_N)
    q_low_pct   = _qpct(q_low_rows,  q_N)
    q_zero_pct  = _qpct(q_zero_rows, q_N)

    # ── recompute hourly with correct Mbps ──
    _q_hourly_tmp = df.copy()
    _q_hourly_tmp["_qhr"] = pd.to_datetime(_q_hourly_tmp["Start Time"], errors="coerce").dt.hour
    if _q_dl_col:
        _q_hourly_tmp["_qdl"] = pd.to_numeric(_q_hourly_tmp[_q_dl_col], errors="coerce") / _q_dl_div
        _q_h = _q_hourly_tmp.groupby("_qhr")["_qdl"].mean().dropna().round(2)
    elif "Throughput" in df.columns:
        _q_hourly_tmp["_qdl"] = pd.to_numeric(_q_hourly_tmp["Throughput"], errors="coerce")
        _q_h = _q_hourly_tmp.groupby("_qhr")["_qdl"].mean().dropna().round(2)
    else:
        _q_h = pd.Series(dtype=float)
    q_best_hour  = int(_q_h.idxmax()) if len(_q_h) else None
    q_worst_hour = int(_q_h.idxmin()) if len(_q_h) else None
    q_best_hour_str  = f"{q_best_hour:02d}:00 — {round(float(_q_h[q_best_hour]),2)} Mbps" if q_best_hour  is not None else "N/A"
    q_worst_hour_str = f"{q_worst_hour:02d}:00 — {round(float(_q_h[q_worst_hour]),2)} Mbps" if q_worst_hour is not None else "N/A"

    # ── recompute quality KPI columns ──
    _q_loss_col   = _qcol(["packet loss",  "downlink"])  or _qcol(["downlink", "loss"])
    _q_ul_loss    = _qcol(["packet loss",  "uplink"])    or _qcol(["uplink",   "loss"])
    _q_delay_col  = _qcol(["delay",        "downlink"])  or _qcol(["downlink", "delay"])
    _q_ul_delay   = _qcol(["delay",        "uplink"])    or _qcol(["uplink",   "delay"])
    _q_retx_col   = _qcol(["retransmission","downlink"]) or _qcol(["downlink", "retransmission"])
    _q_ul_retx    = _qcol(["retransmission","uplink"])   or _qcol(["uplink",   "retransmission"])
    _q_rtt_col    = _qcol(["rtt",           "downlink"]) or _qcol(["downlink", "rtt"])
    _q_ul_rtt_col = _qcol(["rtt",           "uplink"])   or _qcol(["uplink",   "rtt"])

    q_dl_loss_avg   = _qnum(_q_loss_col,  "mean")
    q_ul_loss_avg2  = _qnum(_q_ul_loss,   "mean")
    q_dl_loss_max   = _qnum(_q_loss_col,  "max")
    q_dl_delay_avg  = _qnum(_q_delay_col, "mean")
    q_ul_delay_avg2 = _qnum(_q_ul_delay,  "mean")
    q_dl_retx_avg   = _qnum(_q_retx_col,  "mean")
    q_ul_retx_avg2  = _qnum(_q_ul_retx,   "mean")
    q_dl_retx_max   = _qnum(_q_retx_col,  "max")
    _q_rtt_raw      = _qnum(_q_rtt_col,   "mean")
    _q_ul_rtt_raw   = _qnum(_q_ul_rtt_col,"mean")
    q_dl_rtt_avg    = _q_rtt_raw    # kept as-is (ms or µs — divide by 1000 for display if > 1000)
    q_ul_rtt_avg2   = _q_ul_rtt_raw

    q_dl_loss_str  = f"{q_dl_loss_avg}%"    if q_dl_loss_avg  is not None else "N/A"
    q_dl_delay_str = f"{q_dl_delay_avg} ms" if q_dl_delay_avg is not None else "N/A"
    q_dl_retx_str  = f"{q_dl_retx_avg}%"   if q_dl_retx_avg  is not None else "N/A"
    _q_dl_rtt_ms   = round(q_dl_rtt_avg/1000, 1)  if q_dl_rtt_avg  and q_dl_rtt_avg > 100 else q_dl_rtt_avg
    _q_ul_rtt_ms   = round(q_ul_rtt_avg2/1000, 1) if q_ul_rtt_avg2 and q_ul_rtt_avg2 > 100 else q_ul_rtt_avg2
    q_dl_rtt_str   = f"{_q_dl_rtt_ms} ms"  if _q_dl_rtt_ms is not None else "N/A"

    # ── recompute quality score ──
    q_score = 100
    if q_dl_loss_avg  and q_dl_loss_avg  > 1:  q_score -= 15
    if q_dl_loss_avg  and q_dl_loss_avg  > 3:  q_score -= 15
    if q_dl_retx_avg  and q_dl_retx_avg  > 1:  q_score -= 10
    if q_dl_retx_avg  and q_dl_retx_avg  > 3:  q_score -= 10
    if q_dl_delay_avg and q_dl_delay_avg > 50:  q_score -= 10
    if q_dl_delay_avg and q_dl_delay_avg > 100: q_score -= 10
    if q_dl_avg < 2:  q_score -= 15
    if q_dl_avg < 1:  q_score -= 15
    q_score    = max(q_score, 0)
    q_sq_color = "#22c55e" if q_score >= 70 else ("#f59e0b" if q_score >= 40 else "#e74c3c")
    q_sq_label = "Excellent 🟢" if q_score >= 70 else ("Average 🟡" if q_score >= 40 else "Poor 🔴")

    def _q_loss_icon(v):
        return "⚪" if v is None else ("🟢" if v < 1 else ("🟡" if v < 3 else "🔴"))
    def _q_delay_icon(v):
        return "⚪" if v is None else ("🟢" if v < 50 else ("🟡" if v < 100 else "🔴"))
    def _q_retx_icon(v):
        return "⚪" if v is None else ("🟢" if v < 1 else ("🟡" if v < 3 else "🔴"))
    def _q_rtt_icon(v):
        return "⚪" if v is None else ("🟢" if v < 50 else ("🟡" if v < 100 else "🔴"))

    # TAB 0 – Service Type
    _q_svc_col = next((c for c in df.columns if c == "Service Type"), None)
    if _q_svc_col:
        _q_svc_counts = df[_q_svc_col].dropna().astype(str).value_counts()
        q_svc_html = "<br>".join(
            f"• <b>{k}:</b> {v:,} rows ({_qpct(v, q_N)}%)"
            for k, v in _q_svc_counts.items()
        ) or "No data available"
    else:
        q_svc_html = "No data available"

    # TAB 1 – P10/P90, UL max, ratio, per-site throughput
    q_dl_p10      = _qnum(_q_dl_col, "p10", _q_dl_div) or 0
    q_dl_p90      = _qnum(_q_dl_col, "p90", _q_dl_div) or 0
    q_ul_max      = _qnum(_q_ul_col, "max", _q_ul_div) or 0
    q_dl_ul_ratio = round(q_dl_avg / q_ul_avg, 1) if q_ul_avg else "N/A"
    q_site_tp_html = "<br>".join(
        f"{'🟢' if v>=5 else ('🟡' if v>=2 else '🔴')} <b>{s}:</b> {v} Mbps"
        for s, v in _q_site_tp_s.items()
    ) if len(_q_site_tp_s) else "No data"

    # TAB 2 – Site detail table
    _q_site_traffic = {}
    if "Traffic_MB" in df.columns:
        _q_site_traffic = df.groupby("_site_id_clean")["Traffic_MB"].sum().round(1).to_dict()
    _q_rat_per_site = {}
    if "Radio Access Type" in df.columns:
        for _sid, _grp in df.groupby("_site_id_clean"):
            _rv = _grp["Radio Access Type"].dropna().astype(str).value_counts()
            _q_rat_per_site[_sid] = ", ".join(f"{k}={v}" for k, v in _rv.items())
    _q_app_per_site = {}
    if "App Name" in df.columns:
        for _sid, _grp in df.groupby("_site_id_clean"):
            _tp = _grp["App Name"].dropna().astype(str).value_counts()
            _q_app_per_site[_sid] = _tp.index[0] if len(_tp) else "—"

    site_comparison_rows = ""
    for _sid, _avg_dl in _q_site_tp_s.items():
        _icon = "🟢" if _avg_dl >= 5 else ("🟡" if _avg_dl >= 2 else "🔴")
        _tr   = _q_site_traffic.get(_sid, "—")
        _rat  = _q_rat_per_site.get(_sid, "—")
        _app  = _q_app_per_site.get(_sid, "—")
        site_comparison_rows += (
            f"<tr><td style='padding:6px 10px;font-weight:700'>{_sid}</td>"
            f"<td style='padding:6px 10px'>{_icon} {_avg_dl} Mbps</td>"
            f"<td style='padding:6px 10px'>{_tr} MB</td>"
            f"<td style='padding:6px 10px'>{_rat}</td>"
            f"<td style='padding:6px 10px'>{_app}</td></tr>"
        )

    # TAB 3 – Apps
    _q_app_col2 = next((c for c in df.columns if c == "App Name"), None)
    _q_app_vc = pd.Series(dtype=int)
    if _q_app_col2:
        _qa = df[_q_app_col2].dropna().astype(str)
        _qa = _qa[~_qa.str.strip().str.upper().isin(["NAN","NONE",""])]
        _q_app_vc = _qa.value_counts()
        medals = ["🥇","🥈","🥉"] + ["•"]*20
        q_top10_usage_html = "<br>".join(
            f"{medals[i]} <b>{k}:</b> {v:,} rows ({_qpct(v, q_N)}%)"
            for i,(k,v) in enumerate(_q_app_vc.head(10).items())
        ) or "No data"
        if _q_dl_col:
            _app_dl_s = (pd.to_numeric(df[_q_dl_col], errors="coerce") / _q_dl_div)
            _app_dl = (_app_dl_s[_app_dl_s > 0]
                        .groupby(df[_q_app_col2]).mean()
                        .sort_values(ascending=False).head(10).round(2))
            q_top10_dl_html = "<br>".join(f"• <b>{k}:</b> {v} Mbps" for k,v in _app_dl.items()) or "No data"
        else:
            q_top10_dl_html = "No DL column"
        if "Traffic_MB" in df.columns:
            _app_tr = (df.groupby(_q_app_col2)["Traffic_MB"].sum()
                         .sort_values(ascending=False).round(1).head(10))
            q_top10_traffic_html = "<br>".join(f"• <b>{k}:</b> {v} MB" for k,v in _app_tr.items()) or "No data"
        else:
            q_top10_traffic_html = "No traffic data"
        if _q_svc_col:
            _brows = (df[df[_q_svc_col].astype(str).str.contains("Brows", case=False, na=False)]
                        [_q_app_col2].dropna().astype(str).value_counts().head(5))
            q_browsing_html = "<br>".join(f"• <b>{k}:</b> {v}" for k,v in _brows.items()) or "No browsing data"
            _vid = (df[df[_q_svc_col].astype(str).str.contains("Video|Stream", case=False, na=False)]
                      [_q_app_col2].dropna().astype(str).value_counts().head(5))
            q_video_html = "<br>".join(f"• <b>{k}:</b> {v}" for k,v in _vid.items()) or "No video data"
        else:
            q_browsing_html = "No service type data"
            q_video_html    = "No service type data"
    else:
        q_top10_usage_html = q_top10_dl_html = q_top10_traffic_html = q_browsing_html = q_video_html = "No App Name column"

    # TAB 4 – Network
    _q_rat_col2 = next((c for c in df.columns if c == "Radio Access Type"), None)
    _q_rat_vc   = pd.Series(dtype=int)
    if _q_rat_col2:
        _q_rat_vc  = df[_q_rat_col2].dropna().astype(str).value_counts()
        _q_nr  = int(_q_rat_vc.get("NR",  0))
        _q_lte = int(_q_rat_vc.get("EUTRAN", _q_rat_vc.get("LTE", 0)))
        q_rat_full_html = (
            f"• <b>NR (5G):</b> {_q_nr:,} rows ({_qpct(_q_nr, q_N)}%)<br>"
            f"• <b>EUTRAN (LTE):</b> {_q_lte:,} rows ({_qpct(_q_lte, q_N)}%)<br>"
            + "<br>".join(f"• <b>{k}:</b> {v:,}" for k,v in _q_rat_vc.items() if k not in ("NR","EUTRAN","LTE"))
        )
        if _q_dl_col:
            _rdl_s  = pd.to_numeric(df[_q_dl_col], errors="coerce") / _q_dl_div
            _rat_dl = (_rdl_s[_rdl_s > 0]
                        .groupby(df[_q_rat_col2]).mean()
                        .sort_values(ascending=False).round(2))
            q_rat_dl_html = "<br>".join(f"• <b>{k}:</b> {v} Mbps" for k,v in _rat_dl.items()) or "No data"
        else:
            q_rat_dl_html = "No DL data"
    else:
        q_rat_full_html = "No RAT column"
        q_rat_dl_html   = "No data"

    _q_roam_col2 = next((c for c in df.columns if c == "Roaming Status"), None)
    if _q_roam_col2 and _q_dl_col:
        _rdl_s2   = pd.to_numeric(df[_q_dl_col], errors="coerce") / _q_dl_div
        _roam_dl  = (_rdl_s2[_rdl_s2 > 0]
                      .groupby(df[_q_roam_col2]).mean()
                      .sort_values(ascending=False).round(2))
        q_roam_dl_html = "<br>".join(f"• <b>{k}:</b> {v} Mbps" for k,v in _roam_dl.items()) or "No data"
    else:
        q_roam_dl_html = "No data"

    _q_enc_col = _qcol(["encrypted"])
    if _q_enc_col:
        _enc_cnt = df[_q_enc_col].astype(str).str.contains("Encrypt|Yes|True|1", case=False, na=False).sum()
        q_enc_html = f"<b>{_qpct(int(_enc_cnt), q_N)}%</b> of sessions are encrypted"
    else:
        q_enc_html = "No encryption data"

    _q_mbr_dl = _qcol(["allowed", "downlink", "maximum"]) or _qcol(["mbr", "dl"]) or _qcol(["max bit rate", "downlink"])
    _q_mbr_ul = _qcol(["allowed", "uplink",   "maximum"]) or _qcol(["mbr", "ul"]) or _qcol(["max bit rate", "uplink"])
    if _q_mbr_dl:
        _mbr_dv = pd.to_numeric(df[_q_mbr_dl], errors="coerce").dropna()
        _mbr_dv = _mbr_dv[_mbr_dv > 0]
        _mbr_dl_avg = round(float(_mbr_dv.mean())/1000, 1) if len(_mbr_dv) else None
        _mbr_ul_avg = round(float(pd.to_numeric(df[_q_mbr_ul], errors="coerce").mean())/1000, 1) if _q_mbr_ul else None
        q_mbr_html = (f"• <b>Avg DL MBR:</b> {_mbr_dl_avg if _mbr_dl_avg else 'N/A'} Mbps<br>"
                      f"• <b>Avg UL MBR:</b> {_mbr_ul_avg if _mbr_ul_avg else 'N/A'} Mbps")
    else:
        q_mbr_html = "No MBR data"

    # TAB 5 – Issues detail table
    df["_q_issue"] = "Good"
    df.loc[_q_dl_mbps < 1,  "_q_issue"] = "Low Throughput"
    df.loc[_q_dl_mbps == 0, "_q_issue"] = "Zero Traffic"
    _q_issues_detail = df.groupby(["_site_id_clean","_q_issue"]).size().reset_index(name="Count")
    _q_prob_sites    = (df[df["_q_issue"] != "Good"]
                          .groupby("_site_id_clean").size().sort_values(ascending=False))
    issues_detail_rows = ""
    for _, _row in _q_issues_detail.iterrows():
        _iss = _row["_q_issue"]
        _bg  = "#dcfce7" if _iss == "Good" else ("#fef3c7" if _iss == "Low Throughput" else "#fee2e2")
        _fg  = "#166534" if _iss == "Good" else ("#92400e" if _iss == "Low Throughput" else "#991b1b")
        _ico = "✅"       if _iss == "Good" else ("⚠️"      if _iss == "Low Throughput" else "🔴")
        issues_detail_rows += (
            f"<tr><td style='padding:6px 10px'>{_row['_site_id_clean']}</td>"
            f"<td style='padding:6px 10px'>{_iss}</td>"
            f"<td style='padding:6px 10px'>{_row['Count']:,}</td>"
            f"<td style='padding:6px 10px'><span style='background:{_bg};color:{_fg};"
            f"padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700'>{_ico} {_iss}</span></td></tr>"
        )
    prob_sites_html = "<br>".join(f"🔴 <b>{s}:</b> {v:,} problem rows" for s,v in _q_prob_sites.items()) or "No issues found ✅"

    def _q_loss_icon(v):
        return "⚪" if v is None else ("🟢" if v < 1 else ("🟡" if v < 3 else "🔴"))
    def _q_delay_icon(v):
        return "⚪" if v is None else ("🟢" if v < 50 else ("🟡" if v < 100 else "🔴"))
    def _q_retx_icon(v):
        return "⚪" if v is None else ("🟢" if v < 1 else ("🟡" if v < 3 else "🔴"))

    # TAB 6 – Timing
    _q_hourly_by_records = _q_hourly_tmp.groupby("_qhr").size()
    q_busiest_hour_val = int(_q_hourly_by_records.idxmax()) if len(_q_hourly_by_records) else 0
    q_busiest_hour_cnt = int(_q_hourly_by_records.max())    if len(_q_hourly_by_records) else 0
    if len(_q_h) >= 3:
        _q_peak3 = _q_h.sort_values(ascending=False).head(3)
        _q_off3  = _q_h.sort_values().head(3)
        q_peak3_html = "<br>".join(f"• {int(h):02d}:00 — {v} Mbps" for h,v in _q_peak3.items())
        q_off3_html  = "<br>".join(f"• {int(h):02d}:00 — {v} Mbps" for h,v in _q_off3.items())
    else:
        q_peak3_html = q_off3_html = "Not enough data"

    _q_hourly_tmp["_qdate"] = pd.to_datetime(_q_hourly_tmp["Start Time"], errors="coerce").dt.date
    if _q_dl_col:
        _q_daily = (_q_hourly_tmp.groupby("_qdate")["_qdl"].mean().dropna().round(2))
    elif "Throughput" in df.columns:
        _q_daily = (pd.to_numeric(df["Throughput"], errors="coerce")
                      .groupby(_q_hourly_tmp["_qdate"]).mean().dropna().round(2))
    else:
        _q_daily = pd.Series(dtype=float)

    if len(_q_daily):
        q_best_day_str  = f"{_q_daily.idxmax()} — {float(_q_daily.max())} Mbps"
        q_worst_day_str = f"{_q_daily.idxmin()} — {float(_q_daily.min())} Mbps"
    else:
        q_best_day_str = q_worst_day_str = "No data"

    _q_hourly_labels = [f"{int(h):02d}:00" for h in _q_h.index] if len(_q_h) else []
    _q_hourly_values = [float(v) for v in _q_h.values]           if len(_q_h) else []
    if _q_hourly_values:
        _mx = max(_q_hourly_values); _mn = min(_q_hourly_values)
        _q_hourly_colors = ["#22c55e" if v==_mx else ("#e74c3c" if v==_mn else "#6366f1") for v in _q_hourly_values]
    else:
        _q_hourly_colors = []
    q_hourly_labels_json = _json2.dumps(_q_hourly_labels)
    q_hourly_values_json = _json2.dumps(_q_hourly_values)
    q_hourly_colors_json = _json2.dumps(_q_hourly_colors)
    q_daily_labels_json  = _json2.dumps([str(d) for d in _q_daily.index]  if len(_q_daily) else [])
    q_daily_values_json  = _json2.dumps([float(v) for v in _q_daily.values] if len(_q_daily) else [])

    # TAB 7 – Connection Quality
    def _q_qbar(label, val, unit, good, warn):
        if val is None: return f"<b>{label}:</b> No data<br>"
        icon = "🟢" if val <= good else ("🟡" if val <= warn else "🔴")
        return f"{icon} <b>{label}:</b> {val} {unit}<br>"

    q_quality_kpi_html = (_q_qbar("DL Packet Loss",  q_dl_loss_avg,   "%",  1,  3)
                        +  _q_qbar("UL Packet Loss",  q_ul_loss_avg2, "%",  1,  3)
                        +  _q_qbar("DL Delay",        q_dl_delay_avg, "ms", 30, 80)
                        +  _q_qbar("UL Delay",        q_ul_delay_avg2,"ms", 30, 80))
    q_retx_html2       = (_q_qbar("DL TCP Retransmission", q_dl_retx_avg,  "%", 1, 3)
                        +  _q_qbar("UL TCP Retransmission", q_ul_retx_avg2, "%", 1, 3))
    q_rtt_html2        = (_q_qbar("DL RTT", _q_dl_rtt_ms, "ms", 30, 80)
                        +  _q_qbar("UL RTT", _q_ul_rtt_ms, "ms", 30, 80))

    _q_eff_dl  = _qcol(["downlink", "effective", "traffic"])
    _q_eff_ul  = _qcol(["uplink",   "effective", "traffic"])
    _q_eff_dur = _qcol(["downlink", "effective", "duration"])
    eff_parts  = []
    if _q_eff_dl:  eff_parts.append(f"<b>DL Effective Traffic Avg:</b> {_qnum(_q_eff_dl)} KB")
    if _q_eff_ul:  eff_parts.append(f"<b>UL Effective Traffic Avg:</b> {_qnum(_q_eff_ul)} KB")
    if _q_eff_dur: eff_parts.append(f"<b>DL Effective Duration Avg:</b> {_qnum(_q_eff_dur)} ms")
    q_eff_html = "<br>".join(eff_parts) if eff_parts else "No data available"

    # TAB 8 – Summary
    q_rat_summary  = " | ".join(f"{k}: {v}" for k,v in _q_rat_vc.items()) if len(_q_rat_vc) else "N/A"
    q_top_app_str  = (_q_app_vc.index[0] if len(_q_app_vc) else "N/A")
    # ── end extra Q&A variables ──────────────────────────────────

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>WE Trace Report — {export_date}</title>
{plotly_js_tag}
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Arial,sans-serif;background:#f4f6fb;color:#1e293b}}
.layout{{display:flex;min-height:100vh}}

/* ── Sidebar ── */
.sidebar{{width:270px;min-width:220px;background:#fff;border-right:1px solid #e2e8f0;
          padding:0;display:flex;flex-direction:column;position:sticky;top:0;height:100vh;overflow-y:auto}}
.sb-header{{background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:18px 16px;text-align:center}}
.sb-header h2{{color:#fff;font-size:16px;font-weight:700;margin:0}}
.sb-header p{{color:rgba(255,255,255,.75);font-size:11px;margin-top:4px}}
.sb-section{{padding:12px 14px;border-bottom:1px solid #f1f5f9}}
.sb-label{{font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;
           letter-spacing:.07em;margin-bottom:6px;display:block}}
select,input[type=text],input[type=datetime-local]{{
  width:100%;padding:6px 8px;border:1px solid #e2e8f0;border-radius:7px;
  font-size:12px;color:#334155;background:#f8fafc;outline:none;margin-bottom:4px}}
select:focus,input:focus{{border-color:#6366f1}}
select[multiple]{{height:90px}}
.btn-apply{{width:100%;padding:9px;background:linear-gradient(135deg,#6366f1,#8b5cf6);
            color:#fff;border:none;border-radius:8px;font-weight:700;font-size:13px;
            cursor:pointer;margin-top:6px;letter-spacing:.03em}}
.btn-apply:hover{{opacity:.9}}
.btn-reset{{width:100%;padding:7px;background:#f1f5f9;color:#64748b;border:1px solid #e2e8f0;
            border-radius:8px;font-weight:600;font-size:12px;cursor:pointer;margin-top:4px}}

/* ── Main content ── */
.main{{flex:1;padding:20px;overflow-x:hidden}}
.hdr{{background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:14px;
      padding:18px 24px;display:flex;align-items:center;gap:14px;margin-bottom:16px;
      box-shadow:0 4px 20px rgba(99,102,241,.3)}}
.hdr h1{{color:#fff;font-size:20px;font-weight:700;margin:0}}
.hdr p{{color:rgba(255,255,255,.8);font-size:11px;margin-top:3px}}
.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:16px}}
@media(max-width:900px){{.kpis{{grid-template-columns:repeat(2,1fr)}}
  .sidebar{{width:200px}}.layout{{flex-direction:column}}
  .sidebar{{height:auto;position:relative}}}}
.kpi{{background:#fff;border-radius:12px;padding:14px 16px;border-top:4px solid #6366f1;
      box-shadow:0 2px 10px rgba(0,0,0,.06)}}
.kl{{font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.05em}}
.kv{{font-size:22px;font-weight:700;color:#1e293b;line-height:1.2;margin:4px 0 2px}}
.ks{{font-size:11px;color:#94a3b8}}
.sec-title{{font-size:15px;font-weight:700;color:#1e293b;margin:20px 0 8px;
           padding-bottom:7px;border-bottom:2px solid #e2e8f0}}
.chart-wrap{{background:#fff;border-radius:12px;padding:14px;
            box-shadow:0 2px 10px rgba(0,0,0,.05);margin-bottom:14px}}
.map-wrap{{background:#fff;border-radius:12px;padding:10px;
          box-shadow:0 2px 10px rgba(0,0,0,.05);margin-bottom:14px}}
.tbl-wrap{{background:#fff;border-radius:12px;padding:12px;
          box-shadow:0 2px 10px rgba(0,0,0,.05);margin-bottom:14px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{background:#f8fafc;font-size:10px;font-weight:700;color:#64748b;text-align:left;
   padding:7px 9px;border-bottom:1px solid #e2e8f0;white-space:nowrap;position:sticky;top:0;z-index:1}}
td{{padding:6px 9px;border-bottom:1px solid #f1f5f9;color:#334155;white-space:nowrap}}
tr:hover td{{background:#f8fafc}}
.footer{{text-align:center;font-size:11px;color:#94a3b8;margin-top:24px;
        padding-top:12px;border-top:1px solid #e2e8f0}}
.badge{{padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700}}
/* ── QA Cards ── */
.qgrid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}}
.qcard{{background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;padding:9px 12px;margin-bottom:8px}}
.qcard-lbl{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#64748b;margin-bottom:4px}}
.qcard-body{{font-size:12px;color:#1e293b;line-height:1.55}}
.qa-panel{{display:none}}.qa-panel.qa-show{{display:block}}
</style>
</head>
<body>
<div class="layout">

<!-- ══════════════ SIDEBAR FILTERS ══════════════ -->
<div class="sidebar">
  <div class="sb-header">
    <div style="font-size:30px">📡</div>
    <h2>WE Trace</h2>
    <p>Interactive Filters</p>
  </div>

  <div class="sb-section">
    <span class="sb-label">📡 Site</span>
    <select id="f_site" onchange="applyFilters()">
      <option value="All">All Sites</option>
      {opts(all_sites)}
    </select>
  </div>

  <div class="sb-section">
    <span class="sb-label">📱 MSISDN</span>
    <select id="f_msisdn" onchange="applyFilters()">
      <option value="All">All</option>
      {''.join(f'<option value="{n}">{d}</option>' for n,d in zip(all_msisdn_norm, all_msisdn_display))}
    </select>
  </div>

  <div class="sb-section">
    <span class="sb-label">📶 Service Type</span>
    <select id="f_service" onchange="applyFilters()">
      <option value="All">All</option>
      {opts(all_service)}
    </select>
  </div>

  {'<div class="sb-section"><span class="sb-label">📱 App Name</span><select id="f_app" onchange="applyFilters()"><option value="All">All</option>' + opts(all_appname) + '</select></div>' if all_appname else '<div style="display:none"><select id="f_app"><option value="All">All</option></select></div>'}

  {'<div class="sb-section"><span class="sb-label">📡 Radio Access Type</span><select id="f_rat" onchange="applyFilters()"><option value="All">All</option>' + opts(all_rat) + '</select></div>' if all_rat else '<div style="display:none"><select id="f_rat"><option value="All">All</option></select></div>'}

  {'<div class="sb-section"><span class="sb-label">🌍 Roaming Status</span><select id="f_roam" onchange="applyFilters()"><option value="All">All</option>' + opts(all_roaming) + '</select></div>' if all_roaming else '<div style="display:none"><select id="f_roam"><option value="All">All</option></select></div>'}

  <div class="sb-section">
    <span class="sb-label">🕐 Time Range — From</span>
    <input type="datetime-local" id="f_tstart" value="{min_time_str}">
    <span class="sb-label" style="margin-top:6px">To</span>
    <input type="datetime-local" id="f_tend"   value="{max_time_str}">
  </div>

  <div class="sb-section">
    <button class="btn-apply" onclick="applyFilters()">✅ Apply Filters</button>
    <button class="btn-reset" onclick="resetFilters()">🔄 Reset All</button>
    <div id="filter_status" style="font-size:11px;color:#6366f1;margin-top:6px;text-align:center"></div>
  </div>
</div>

<!-- ══════════════ MAIN CONTENT ══════════════ -->
<div class="main">

<div class="hdr">
  <div style="font-size:36px">📡</div>
  <div>
    <h1>WE Trace Dashboard — Full Report</h1>
    <p id="hdr_sub">MSISDN: <span id="hdr_msisdn">{msisdn_value}</span> &nbsp;·&nbsp; {export_date}</p>
  </div>
</div>

<!-- KPIs -->
<div class="kpis">
  <div class="kpi" style="border-color:#6366f1">
    <div class="kl">📡 Sites</div><div class="kv" id="kpi_sites">—</div>
    <div class="ks">Serving Sites</div></div>
  <div class="kpi" style="border-color:#22c55e">
    <div class="kl">⚡ Avg Throughput</div><div class="kv" id="kpi_tp">—</div>
    <div class="ks">Mbps</div></div>
  <div class="kpi" style="border-color:#3b82f6">
    <div class="kl">👤 Unique Users</div><div class="kv" id="kpi_users">—</div>
    <div class="ks">MSISDN: <span id="kpi_msisdn_lbl">{msisdn_value}</span></div></div>
  <div class="kpi" style="border-color:#f59e0b">
    <div class="kl">📱 Device</div>
    <div class="kv" style="font-size:12px;margin-top:4px" id="kpi_device">{str(device_info)[:30]}</div>
    <div class="ks">Model Info</div></div>
  <div class="kpi" style="border-color:#8b5cf6">
    <div class="kl">📊 Records</div><div class="kv" id="kpi_records">—</div>
    <div class="ks">Total Rows</div></div>
  <div class="kpi" style="border-color:#06b6d4">
    <div class="kl">📲 Top 3 Apps</div>
    <div id="kpi_top3apps" style="margin-top:8px;display:flex;flex-direction:column;gap:4px;font-size:11px;font-weight:600;color:#1e293b">—</div>
    <div class="ks">Most Used</div></div>
</div>

<!-- Charts -->
<div class="sec-title">📈 DL &amp; UL Throughput Over Time</div>
<div class="chart-wrap"><div id="chart_dl_time"></div></div>

<div class="sec-title">📊 Hourly DL &amp; UL Throughput</div>
<div class="chart-wrap"><div id="chart_hourly"></div></div>

<div class="sec-title">📊 Hourly Average DL Throughput &amp; DL Traffic</div>
<div class="chart-wrap"><div id="chart_dl_traffic"></div></div>

<div class="sec-title">📊 Network Performance Comparison</div>
<div class="chart-wrap"><div id="chart_network"></div></div>

<!-- Map -->
<div class="sec-title">🗺️ Sites Map with Sectors</div>
<div class="map-wrap"><div id="leaflet_map" style="height:560px;border-radius:10px"></div></div>

{down_table}

<!-- Issues table -->
<div class="sec-title">🚨 Issues Summary</div>
<div class="tbl-wrap"><table id="tbl_issues">
  <thead><tr><th>Site</th><th>Issue</th><th>Count</th><th>Status</th></tr></thead>
  <tbody id="tbody_issues"></tbody>
</table></div>

<!-- Full data table -->
<div class="sec-title">
  📋 Full Data — <span id="rec_count">0</span> Rows
  <input id="srch" onkeyup="filterTable()" placeholder="🔍 Search..."
         style="float:right;padding:5px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:12px;outline:none;width:200px">
</div>
<div class="tbl-wrap" style="max-height:480px;overflow:auto">
  <table id="dtbl"><thead id="thead_data"></thead><tbody id="tbody_data"></tbody></table>
</div>

<div class="footer">
  WE Trace Dashboard &nbsp;·&nbsp; Generated {export_date} &nbsp;·&nbsp; Confidential
</div>
</div><!-- /main -->
</div><!-- /layout -->

<script>
// ═══════════════════════════════════════════
//  RAW DATA
// ═══════════════════════════════════════════
const RAW_DATA  = {data_json};
const TRACE_COL = '{TRACE_COL_JS}';
const DL_COL    = '{_dl_js}';
const UL_COL    = '{_ul_js}';
const NET_COL   = '{_net_js}';
const MSISDN_KPIS       = {msisdn_kpis_json};
const SECTORS_BY_MSISDN = {sectors_by_msisdn_json};

// ═══════════════════════════════════════════
//  FILTER LOGIC
// ═══════════════════════════════════════════

// ── Update Site dropdown based on selected MSISDN ──
function updateSiteDropdown() {{
  const msisdn_sel = document.getElementById('f_msisdn') ? document.getElementById('f_msisdn').value : 'All';
  const siteEl = document.getElementById('f_site');
  const currentSite = siteEl.value;

  // Filter RAW_DATA for selected MSISDN
  const relevantData = msisdn_sel === 'All' ? RAW_DATA
    : RAW_DATA.filter(r => r['_msisdn_file'] === msisdn_sel);

  // Get unique sites
  const sites = [...new Set(relevantData.map(r => r[TRACE_COL]).filter(Boolean))].sort();

  // Rebuild options
  siteEl.innerHTML = '<option value="All">All Sites</option>';
  sites.forEach(s => {{
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s;
    if (s === currentSite) opt.selected = true;
    siteEl.appendChild(opt);
  }});

  // If selected site not in new MSISDN, reset to All
  if (currentSite !== 'All' && !sites.includes(currentSite)) {{
    siteEl.value = 'All';
  }}
}}

function applyFilters() {{
  updateSiteDropdown();
  const site    = document.getElementById('f_site').value;
  const msisdn_sel = document.getElementById('f_msisdn') ? document.getElementById('f_msisdn').value : 'All';
  const service = document.getElementById('f_service') ? document.getElementById('f_service').value : 'All';
  const app     = document.getElementById('f_app')  ? document.getElementById('f_app').value  : 'All';
  const rat     = document.getElementById('f_rat')  ? document.getElementById('f_rat').value  : 'All';
  const roam    = document.getElementById('f_roam') ? document.getElementById('f_roam').value : 'All';
  const tstart  = document.getElementById('f_tstart').value;
  const tend    = document.getElementById('f_tend').value;

  let filtered = RAW_DATA.filter(r => {{
    if (site !== 'All' && r[TRACE_COL] !== site) return false;
    if (msisdn_sel !== 'All' && r['_msisdn_file'] !== msisdn_sel)   return false;
    if (service !== 'All' && String(r['Service Type']) !== service) return false;
    if (app  !== 'All' && r['App Name']        !== app)  return false;
    if (rat  !== 'All' && r['Radio Access Type'] !== rat) return false;
    if (roam !== 'All' && String(r['Roaming Status']||r[NET_COL]||'') !== roam) return false;
    if (tstart && r['Start Time'] < tstart) return false;
    if (tend   && r['Start Time'] > tend)   return false;
    return true;
  }});

  if (filtered.length === 0) {{
    document.getElementById('filter_status').textContent = '⚠️ No matching data';
  }} else {{
    document.getElementById('filter_status').textContent = `✅ ${{filtered.length.toLocaleString()}} rows`;
  }}

  renderAll(filtered);
}}

function resetFilters() {{
  document.getElementById('f_site').value = 'All';
  document.getElementById('f_app') && (document.getElementById('f_app').value = 'All');
  document.getElementById('f_rat') && (document.getElementById('f_rat').value = 'All');
  document.getElementById('f_roam') && (document.getElementById('f_roam').value = 'All');
  if (document.getElementById('f_msisdn')) document.getElementById('f_msisdn').value = 'All';
  if (document.getElementById('f_service')) document.getElementById('f_service').value = 'All';
  updateSiteDropdown();  // Restore all sites on reset
  document.getElementById('filter_status').textContent = '';
  renderAll(RAW_DATA);
}}

// ═══════════════════════════════════════════
//  RENDER ALL
// ═══════════════════════════════════════════
function renderAll(data) {{
  updateKPIs(data);
  renderChartDLTime(data);
  renderChartHourly(data);
  renderChartDLTraffic(data);
  renderChartNetwork(data);
  renderIssuesTable(data);
  renderDataTable(data);
  renderLeafletMap(data);
}}

// ── KPIs ──
function renderKPI(id, val) {{ document.getElementById(id).textContent = val; }}
function updateKPIs(data) {{
  const sites  = new Set(data.map(r => r['_site_id_clean'] || String(r[TRACE_COL]).replace(/_\\d+$/, ''))).size;
  const users  = new Set(data.map(r => r['IMSI'])).size;

  // Avg TP — always computed from filtered data to reflect all filters
  const selEl    = document.getElementById('f_msisdn');
  const msisdnSel = selEl ? selEl.value : 'All';
  let avgTp = '—', msisdnLabel = msisdnSel !== 'All' && MSISDN_KPIS[msisdnSel] ? MSISDN_KPIS[msisdnSel].label : (msisdnSel === 'All' ? 'All' : msisdnSel);
  const dlVals = data.map(r => parseFloat(r[DL_COL])).filter(v => !isNaN(v) && v > 0);
  avgTp = dlVals.length ? (dlVals.reduce((a,b)=>a+b,0)/dlVals.length).toFixed(2) : '—';

  // Update label in header and KPI
  const hdr = document.getElementById('hdr_msisdn');     if (hdr) hdr.textContent = msisdnLabel;
  const kl  = document.getElementById('kpi_msisdn_lbl'); if (kl)  kl.textContent  = msisdnLabel;

  renderKPI('kpi_sites',   sites);
  renderKPI('kpi_tp',      avgTp);
  renderKPI('kpi_users',   users);
  renderKPI('kpi_records', data.length.toLocaleString());
  document.getElementById('rec_count').textContent = data.length.toLocaleString();

  // Top 3 Apps
  const appCount = {{}};
  data.forEach(r => {{
    const a = String(r['App Name'] || '').trim();
    if (a && a.toUpperCase() !== 'NAN' && a !== '') appCount[a] = (appCount[a]||0) + 1;
  }});
  const top3 = Object.entries(appCount).sort((x,y)=>y[1]-x[1]).slice(0,3);
  const medals = ['🥇','🥈','🥉'];
  const appsEl = document.getElementById('kpi_top3apps');
  if (appsEl) {{
    appsEl.innerHTML = top3.length
      ? top3.map((([a],i) => `<div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{medals[i]}} ${{a}}</div>`)).join('')
      : '<div style="color:#94a3b8">No data</div>';
  }}
}}

// ── Helper: group by key, aggregate values ──
function groupBy(data, keyFn, valFn, aggFn) {{
  const map = {{}};
  data.forEach(r => {{
    const k = keyFn(r);
    if (!map[k]) map[k] = [];
    const v = valFn(r);
    if (!isNaN(v)) map[k].push(v);
  }});
  return Object.entries(map).map(([k,vs]) => ({{key:k, val: aggFn(vs)}}));
}}
const avg = vs => vs.length ? vs.reduce((a,b)=>a+b,0)/vs.length : 0;
const sum = vs => vs.reduce((a,b)=>a+b,0);

function floorMin(dtStr) {{
  // slice string directly to avoid UTC timezone shift
  if (!dtStr || dtStr === '') return '';
  return String(dtStr).slice(0, 16); // "YYYY-MM-DD HH:MM"
}}
function floorHour(dtStr) {{
  if (!dtStr || dtStr === '') return '';
  return String(dtStr).slice(0, 13) + ':00'; // "YYYY-MM-DD HH:00"
}}

// ── Chart 1: DL & UL over time (per minute) ──
function renderChartDLTime(data) {{
  const byMin = {{}};
  data.forEach(r => {{
    const k = floorMin(r['Start Time']);
    if (!byMin[k]) byMin[k] = {{dl:[],ul:[]}};
    const dl = parseFloat(r[DL_COL] || 0);
    const ul = parseFloat(r[UL_COL] || 0);
    if (!isNaN(dl)) byMin[k].dl.push(dl);
    if (!isNaN(ul)) byMin[k].ul.push(ul);
  }});
  const keys = Object.keys(byMin).sort();
  const dlVals = keys.map(k => avg(byMin[k].dl));
  const ulVals = keys.map(k => avg(byMin[k].ul));
  Plotly.newPlot('chart_dl_time', [
    {{x:keys, y:dlVals, name:'DL Throughput (Mbps)', mode:'lines', line:{{color:'purple',width:2}}}},
    {{x:keys, y:ulVals, name:'UL Throughput (Mbps)', mode:'lines', line:{{color:'orange',width:2}}, yaxis:'y2'}}
  ], {{
    template:'plotly_dark', height:360,
    xaxis:{{title:'Time'}},
    yaxis:{{title:'DL (Mbps)', tickfont:{{color:'purple'}}}},
    yaxis2:{{title:'UL (Mbps)', tickfont:{{color:'orange'}}, overlaying:'y', side:'right'}},
    legend:{{orientation:'h', y:1.1}}, margin:{{t:20,b:50}}
  }}, {{responsive:true}});
}}

// ── Chart 2: Hourly DL & UL ──
function renderChartHourly(data) {{
  const byH = {{}};
  data.forEach(r => {{
    const k = floorHour(r['Start Time']);
    if (!byH[k]) byH[k] = {{dl:[],ul:[]}};
    const dl = parseFloat(r[DL_COL] || 0);
    const ul = parseFloat(r[UL_COL] || 0);
    if (!isNaN(dl)) byH[k].dl.push(dl);
    if (!isNaN(ul)) byH[k].ul.push(ul);
  }});
  const keys = Object.keys(byH).sort();
  Plotly.newPlot('chart_hourly', [
    {{x:keys, y:keys.map(k=>avg(byH[k].dl)), name:'DL Mbps', mode:'lines+markers', line:{{color:'purple',width:2}}}},
    {{x:keys, y:keys.map(k=>avg(byH[k].ul)), name:'UL Mbps', mode:'lines+markers', line:{{color:'orange',width:2}}, yaxis:'y2'}}
  ], {{
    template:'plotly_dark', height:360,
    yaxis:{{title:'DL (Mbps)'}}, yaxis2:{{title:'UL (Mbps)', overlaying:'y', side:'right'}},
    legend:{{orientation:'h', y:1.1}}, margin:{{t:20,b:50}}
  }}, {{responsive:true}});
}}

// ── Chart 3: Hourly DL Throughput + Traffic ──
function renderChartDLTraffic(data) {{
  const byH = {{}};
  data.forEach(r => {{
    const k = floorHour(r['Start Time']);
    if (!byH[k]) byH[k] = {{dl:[],tr:[]}};
    const dl = parseFloat(r[DL_COL] || 0);
    const tr = parseFloat(r['Traffic_MB'] || 0);
    if (!isNaN(dl)) byH[k].dl.push(dl);
    if (!isNaN(tr)) byH[k].tr.push(tr);
  }});
  const keys = Object.keys(byH).sort();
  Plotly.newPlot('chart_dl_traffic', [
    {{x:keys, y:keys.map(k=>avg(byH[k].dl)), name:'DL Throughput (Mbps)', mode:'lines+markers', line:{{color:'#6366f1',width:2}}}},
    {{x:keys, y:keys.map(k=>avg(byH[k].tr)), name:'DL Traffic (MB)', type:'bar', opacity:0.6, yaxis:'y2', marker:{{color:'#22c55e'}}}}
  ], {{
    template:'plotly_white', height:380,
    yaxis:{{title:'DL Throughput (Mbps)'}},
    yaxis2:{{title:'DL Traffic (MB)', overlaying:'y', side:'right'}},
    legend:{{orientation:'h', y:1.1}}, margin:{{t:20,b:50}}
  }}, {{responsive:true}});
}}

// ── Chart 4: Network Comparison ──
function renderChartNetwork(data) {{
  const netField = NET_COL || ['Roaming Status','Network Type','Service Provider'].find(f => data.length && data[0][f] !== undefined);
  if (!netField) {{ document.getElementById('chart_network').innerHTML='<p style="color:#94a3b8;padding:20px">No network column</p>'; return; }}
  const byNet = {{}};
  data.forEach(r => {{
    const k = String(r[netField]).toUpperCase();
    if (!byNet[k]) byNet[k] = [];
    const dl = parseFloat(r[DL_COL]);
    if (!isNaN(dl) && dl > 0) byNet[k].push(dl);  // same logic as updateKPIs
  }});
  const nets = Object.keys(byNet);
  const vals = nets.map(k => avg(byNet[k]));
  const colors = nets.map(k => k.includes('ROAM') ? 'orange' : 'purple');
  Plotly.newPlot('chart_network', [
    {{x:nets, y:vals, type:'bar', text:vals.map(v=>v.toFixed(2)), textposition:'outside',
      marker:{{color:colors}}, name:'Avg DL (Mbps)'}}
  ], {{
    template:'plotly_white', height:320,
    yaxis:{{title:'Avg DL (Mbps)'}},
    xaxis:{{title:'Network'}},
    bargap:0.4, margin:{{t:20,b:50}}
  }}, {{responsive:true}});
}}

// ── Issues Table ──
function renderIssuesTable(data) {{
  const counts = {{}};
  data.forEach(r => {{
    const site = r[TRACE_COL];
    // Use DL_Mbps or Throughput — whichever is available and valid
    const dl = parseFloat(r[DL_COL]);
    const tp = !isNaN(dl) && dl > 0 ? dl : parseFloat(r['Throughput']);
    const issue = isNaN(tp) || tp === 0 ? 'Zero Traffic' : tp < 1 ? 'Low Throughput' : 'Good';
    const key = site + '|' + issue;
    counts[key] = (counts[key]||0) + 1;
  }});
  const pillMap = {{
    'Good':           ['dcfce7','166534','✅'],
    'Low Throughput': ['fef3c7','92400e','⚠️'],
    'Zero Traffic':   ['fee2e2','991b1b','🔴'],
    'Unknown':        ['e2e8f0','334155','❓']
  }};
  let html = '';
  Object.entries(counts).sort().forEach(([k,cnt]) => {{
    const [site,issue] = k.split('|');
    const [bg,fg,ic] = pillMap[issue] || pillMap['Unknown'];
    html += `<tr>
      <td>${{site}}</td><td>${{issue}}</td><td>${{cnt}}</td>
      <td><span class="badge" style="background:#${{bg}};color:#${{fg}}">${{ic}} ${{issue}}</span></td>
    </tr>`;
  }});
  document.getElementById('tbody_issues').innerHTML = html;
}}

// ── Full Data Table ──
let _currentData = [];
function renderDataTable(data) {{
  _currentData = data;
  if (!data.length) {{ document.getElementById('tbody_data').innerHTML='<tr><td>No data</td></tr>'; return; }}
  const cols = Object.keys(data[0]).filter(c => c !== 'geometry');
  const thead = document.getElementById('thead_data');
  thead.innerHTML = '<tr>' + cols.map(c=>`<th>${{c}}</th>`).join('') + '</tr>';
  const rows = data.slice(0,2000).map(r =>
    '<tr>' + cols.map(c=>`<td>${{String(r[c]||'').slice(0,60)}}</td>`).join('') + '</tr>'
  ).join('');
  document.getElementById('tbody_data').innerHTML = rows;
  document.getElementById('rec_count').textContent = data.length.toLocaleString() + (data.length>2000?' (showing first 2000)':'');
}}

function filterTable() {{
  const q = document.getElementById('srch').value.toLowerCase();
  const rows = document.getElementById('dtbl').getElementsByTagName('tr');
  for (let i=1;i<rows.length;i++) {{
    rows[i].style.display = rows[i].innerText.toLowerCase().includes(q) ? '' : 'none';
  }}
}}

// ── Init on load ──
window.addEventListener('load', () => {{
  // If only one MSISDN, auto-select it
  const msEl = document.getElementById('f_msisdn');
  if (msEl) {{
    const opts = Array.from(msEl.options).map(o => o.value).filter(v => v !== 'All');
    if (opts.length === 1) {{ msEl.value = opts[0]; }}
  }}
  applyFilters();
  initLeafletMap();
}});

// ═══════════════════════════════════════════
//  LEAFLET MAP
// ═══════════════════════════════════════════
const SECTORS   = {sectors_json};
const DOWN_SITES = {down_json};
const PLANNED_SITES = {planned_json};
const DOWN_BY_MSISDN     = {down_by_msisdn_json};
const PLANNED_BY_MSISDN  = {planned_by_msisdn_json};
const CUSTOMERS = {customers_json};
const MAP_LAT  = {map_center_lat};
const MAP_LON  = {map_center_lon};

const LAYER_COLORS_JS = {{
  L700:'#e74c3c', L800:'#e67e22', L900:'#f39c12', L1800:'#2ecc71',
  L2100:'#3498db', L2600:'#9b59b6', L3500:'#1abc9c', NR:'#e91e63', '5G':'#ff5722'
}};

function getLayerColor(layer) {{
  for (const [k,v] of Object.entries(LAYER_COLORS_JS)) {{
    if (layer.toUpperCase().includes(k)) return v;
  }}
  return '#95a5a6';
}}

function sectorPolygon(lat, lon, azimuth, radiusKm, beamwidth) {{
  const pts = [];
  const halfBeam = beamwidth / 2;
  const steps = 12;
  const rLat = radiusKm / 111.0;
  const rLon = radiusKm / (111.0 * Math.cos(lat * Math.PI / 180));
  const start = azimuth - halfBeam;
  const end   = azimuth + halfBeam;
  pts.push([lat, lon]);
  for (let i = 0; i <= steps; i++) {{
    const a = (start + (end - start) * i / steps) * Math.PI / 180;
    pts.push([lat + rLat * Math.cos(a), lon + rLon * Math.sin(a)]);
  }}
  pts.push([lat, lon]);
  return pts;
}}

let leafletMap = null;
let allMapLayers = [];

function buildSiteStats(data) {{
  const stats = {{}};
  data.forEach(r => {{
    // Use _site_id_clean (without _N suffix) for matching with Site ID
    const s = r['_site_id_clean'] || String(r[TRACE_COL]).replace(/_\\d+$/, '');
    if (!stats[s]) stats[s] = {{ tps:[], minTP:Infinity, maxTP:-Infinity, rows:[] }};
    // Use DL_Mbps (actual) — fallback to Throughput
    const tp = parseFloat(r[DL_COL] || r['Throughput']);
    if (!isNaN(tp) && tp > 0) {{
      stats[s].tps.push(tp);
      if (tp < stats[s].minTP) stats[s].minTP = tp;
      if (tp > stats[s].maxTP) stats[s].maxTP = tp;
    }}
    stats[s].rows.push(r);
  }});
  return stats;
}}

function buildSectorPopup(siteId, sec, tp, stats) {{
  const tpStr = tp !== null ? tp.toFixed(2) + ' Mbps' : 'N/A';
  const tpColor = tp === null ? '#94a3b8' : tp < 1 ? '#e74c3c' : '#16a34a';
  const rows = stats ? stats.rows : [];
  const cnt  = stats ? stats.tps.length : 0;
  // Use incremental aggregation instead of spread to avoid stack overflow
  const minTP = stats && stats.tps.length ? stats.minTP.toFixed(2) : 'N/A';
  const maxTP = stats && stats.tps.length ? stats.maxTP.toFixed(2) : 'N/A';

  // Sector metadata rows (from on-air sectors file)
  let secRows = '';
  const skipSec = new Set(['Latitude','Longitude']);
  for (const [k,v] of Object.entries(sec)) {{
    if (skipSec.has(k) || v === '' || v === null) continue;
    secRows += `<tr><td style="padding:3px 8px;color:#64748b;white-space:nowrap;font-weight:600">${{k}}</td>
                    <td style="padding:3px 8px">${{v}}</td></tr>`;
  }}

  // Last 5 trace rows for this site
  let traceRows = '';
  if (rows.length > 0) {{
    const cols = Object.keys(rows[0]).filter(c => !['geometry'].includes(c));
    traceRows = `<div style="margin-top:8px;font-size:11px;font-weight:700;color:#1e293b;border-top:2px solid #e2e8f0;padding-top:6px">
      📋 All Trace Records (${{rows.length}} rows)</div>
      <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:10px;margin-top:4px">
      <thead><tr>${{cols.map(c=>`<th style="background:#f8fafc;padding:3px 6px;white-space:nowrap;border-bottom:1px solid #e2e8f0">${{c}}</th>`).join('')}}</tr></thead>
      <tbody>`;
    rows.forEach(r => {{
      traceRows += '<tr>' + cols.map(c=>`<td style="padding:3px 6px;border-bottom:1px solid #f1f5f9;white-space:nowrap">${{String(r[c]||'').slice(0,40)}}</td>`).join('') + '</tr>';
    }});
    traceRows += '</tbody></table></div>';
  }}

  return `<div style="font-family:Arial;font-size:12px;min-width:300px;max-width:480px;max-height:500px;overflow-y:auto;border-radius:6px;overflow:hidden">
    <div style="background:#6366f1;color:white;padding:8px 12px;font-weight:700;font-size:13px">
      📡 ${{siteId}}
    </div>
    <div style="padding:8px 12px">
      <div style="display:flex;gap:12px;margin-bottom:8px;flex-wrap:wrap">
        <div style="background:#f8fafc;border-radius:8px;padding:6px 12px;border-left:3px solid ${{tpColor}}">
          <div style="font-size:10px;color:#64748b;font-weight:700">⚡ AVG THROUGHPUT</div>
          <div style="font-size:18px;font-weight:700;color:${{tpColor}}">${{tpStr}}</div>
        </div>
        <div style="background:#f8fafc;border-radius:8px;padding:6px 12px;border-left:3px solid #6366f1">
          <div style="font-size:10px;color:#64748b;font-weight:700">📊 RECORDS</div>
          <div style="font-size:18px;font-weight:700;color:#1e293b">${{cnt}}</div>
        </div>
        <div style="background:#f8fafc;border-radius:8px;padding:6px 12px;border-left:3px solid #f59e0b">
          <div style="font-size:10px;color:#64748b;font-weight:700">📉 MIN / MAX</div>
          <div style="font-size:14px;font-weight:700;color:#1e293b">${{minTP}} / ${{maxTP}}</div>
        </div>
      </div>
      <div style="font-size:11px;font-weight:700;color:#1e293b;margin-bottom:4px">🔧 Sector Info</div>
      <table style="width:100%;border-collapse:collapse;font-size:11px">${{secRows}}</table>
      ${{traceRows}}
    </div>
  </div>`;
}}

function initLeafletMap() {{
  const mapEl = document.getElementById('leaflet_map');
  if (!mapEl || !window.L) return;
  leafletMap = L.map('leaflet_map').setView([MAP_LAT, MAP_LON], 11);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '© OpenStreetMap'
  }}).addTo(leafletMap);
  renderLeafletMap(RAW_DATA);
}}

function renderLeafletMap(data) {{
  if (!leafletMap) return;

  // Remove old layers
  allMapLayers.forEach(l => leafletMap.removeLayer(l));
  allMapLayers = [];

  // Build per-site stats from filtered data
  const siteStats  = buildSiteStats(data);
  const activeSites = new Set(Object.keys(siteStats));

  // Select sectors for chosen MSISDN only
  const selEl     = document.getElementById('f_msisdn');
  const msisdnSel = selEl ? selEl.value : 'All';
  const sectors   = (msisdnSel !== 'All' && SECTORS_BY_MSISDN[msisdnSel])
                    ? SECTORS_BY_MSISDN[msisdnSel]
                    : SECTORS;

  function fuzzyMatchSite(sectorId, traceIds) {{
    if (traceIds.has(sectorId)) return sectorId;
    for (const tid of traceIds) {{
      const minLen = Math.min(sectorId.length, tid.length);
      if (minLen >= 6 && (tid.startsWith(sectorId) || sectorId.startsWith(tid))) return tid;
    }}
    return null;
  }}

  const drawn = new Set();
  sectors.forEach(sec => {{
    try {{
      const siteId = sec['Site ID'];
      const matchedId = fuzzyMatchSite(siteId, activeSites);
      if (!matchedId) return;
      const stats = siteStats[matchedId];

      const lat = parseFloat(sec['Latitude']);
      const lon = parseFloat(sec['Longitude']);
      if (isNaN(lat) || isNaN(lon)) return;
      const az  = parseFloat(sec['Azimuth']) || 0;
      const layer = String(sec['Layer'] || 'L1800');
      const layers = layer.split(',').join('+').split('/').join('+').toUpperCase().split('+').filter(Boolean);
      const tp = stats && stats.tps.length ? stats.tps.reduce((a,b)=>a+b,0)/stats.tps.length : null;
      const markerColor = tp === null ? '#3b82f6' : tp < 1 ? '#e74c3c' : '#16a34a';
      const popupHtml = buildSectorPopup(siteId, sec, tp, stats);
      const popupOpts = {{ maxWidth: 500, maxHeight: 520 }};

      layers.forEach((lyr, i) => {{
        const rOuter = 0.5 * (i + 1) / layers.length;
        const pts = sectorPolygon(lat, lon, az, rOuter, 65);
        const color = getLayerColor(lyr);
        const poly = L.polygon(pts, {{color, fillColor:color, fillOpacity:0.30, weight:1.5}})
          .bindPopup(popupHtml, popupOpts);
        poly.addTo(leafletMap);
        allMapLayers.push(poly);
      }});

      const markerKey = siteId + '|' + lat.toFixed(5) + '|' + lon.toFixed(5);
      if (!drawn.has(markerKey)) {{
        const marker = L.circleMarker([lat, lon], {{
          radius: 6, color: markerColor, fillColor: markerColor, fillOpacity: 0.95, weight: 2
        }}).bindPopup(popupHtml, popupOpts);
        marker.addTo(leafletMap);
        allMapLayers.push(marker);
        drawn.add(markerKey);
      }}
      // Track matched IDs to know which got a sector drawn
      drawn.add('__traced__' + matchedId);
    }} catch(e) {{ console.warn('Sector render error:', e); }}
  }});

  // ── Fallback: sites in trace but not in sectors — draw simple marker ──
  activeSites.forEach(siteId => {{
    if (drawn.has('__traced__' + siteId)) return; // already drew a sector for this site
    const stats = siteStats[siteId];
    if (!stats || !stats.rows.length) return;

    // Try to get coordinates from first row with lat/lon
    let lat = null, lon = null;
    for (const row of stats.rows) {{
      const rlat = parseFloat(row['Latitude'] || row['latitude'] || '');
      const rlon = parseFloat(row['Longitude'] || row['longitude'] || '');
      if (!isNaN(rlat) && !isNaN(rlon) && rlat !== 0 && rlon !== 0) {{
        lat = rlat; lon = rlon; break;
      }}
    }}
    if (lat === null) return;

    const tp = stats.tps.length ? stats.tps.reduce((a,b)=>a+b,0)/stats.tps.length : null;
    const tpColor = tp === null ? '#3b82f6' : tp < 1 ? '#e74c3c' : '#16a34a';
    const popupHtml = buildSectorPopup(siteId, {{
      'Site ID': siteId, 'Note': '⚠️ Not found in sectors file'
    }}, tp, stats);

    // Draw 3 default sectors (0/120/240) instead of a circle
    [0, 120, 240].forEach(az => {{
      const pts = sectorPolygon(lat, lon, az, 0.4, 65);
      const poly = L.polygon(pts, {{
        color: tpColor, fillColor: tpColor, fillOpacity: 0.25, weight: 1.5, dashArray: '4,4'
      }}).bindPopup(popupHtml, {{ maxWidth: 500, maxHeight: 520 }});
      poly.addTo(leafletMap); allMapLayers.push(poly);
    }});
    // Center dot
    const dot = L.circleMarker([lat, lon], {{
      radius: 5, color: tpColor, fillColor: tpColor, fillOpacity: 1, weight: 2
    }}).bindPopup(popupHtml, {{ maxWidth: 500, maxHeight: 520 }});
    dot.addTo(leafletMap); allMapLayers.push(dot);
    console.log(`⚠️ Fallback sector for: ${{siteId}} at [${{lat}}, ${{lon}}]`);
  }});

  // ── build lookup: siteId → {{lat,lon}} from ALL sectors ──
  const sectorCoords = {{}};
  (SECTORS || []).forEach(s => {{
    const sid = String(s['Site ID'] || '').toUpperCase().replace(/[\s-]/g,'');
    const la = parseFloat(s['Latitude']), lo = parseFloat(s['Longitude']);
    if (sid && !isNaN(la) && !isNaN(lo)) sectorCoords[sid] = {{lat:la, lon:lo}};
  }});

  // ── helper: distance in km between two lat/lon points ──
  function distKm(la1,lo1,la2,lo2) {{
    const R=6371, dLat=(la2-la1)*Math.PI/180, dLon=(lo2-lo1)*Math.PI/180;
    const a=Math.sin(dLat/2)**2+Math.cos(la1*Math.PI/180)*Math.cos(la2*Math.PI/180)*Math.sin(dLon/2)**2;
    return R*2*Math.asin(Math.sqrt(a));
  }}

  // ── serving site coords for proximity check ──
  const servingCoords = [];
  activeSites.forEach(sid => {{
    const c = sectorCoords[sid.toUpperCase().replace(/[\s-]/g,'')];
    if (c) servingCoords.push(c);
  }});

  // ── Down Sites (red) — only near serving sites ──
  const downAll = (msisdnSel !== 'All' && DOWN_BY_MSISDN[msisdnSel])
                  ? DOWN_BY_MSISDN[msisdnSel] : DOWN_SITES;
  downAll.forEach(d => {{
    try {{
      const sid = String(d['Site ID'] || '').toUpperCase().replace(/[\s-]/g,'');
      // Get coordinates from record itself or from sectorCoords
      let lat = parseFloat(d['Latitude']), lon = parseFloat(d['Longitude']);
      if (isNaN(lat) || isNaN(lon)) {{
        const c = sectorCoords[sid];
        if (!c) return;  // not found in on_air — skip
        lat = c.lat; lon = c.lon;
      }}
      // Filter by proximity to serving sites (2km)
      const near = servingCoords.length === 0 ||
                   servingCoords.some(c => distKm(lat,lon,c.lat,c.lon) <= 2);
      if (!near) return;
      let rows = '';
      for (const [k,v] of Object.entries(d)) {{
        if (k==='Latitude'||k==='Longitude'||v===''||v==='nan') continue;
        rows += `<tr><td style="padding:3px 8px;color:#64748b;font-weight:600;white-space:nowrap">${{k}}</td><td style="padding:3px 8px">${{v}}</td></tr>`;
      }}
      const popup = `<div style="font-family:Arial;font-size:12px;min-width:220px">
        <div style="background:#e74c3c;color:white;padding:6px 10px;font-weight:700">🔴 DOWN: ${{sid}}</div>
        <table style="width:100%;border-collapse:collapse">${{rows}}</table></div>`;
      const mk = L.circleMarker([lat,lon],{{radius:9,color:'#c0392b',fillColor:'#e74c3c',fillOpacity:0.9,weight:2}})
        .bindPopup(popup,{{maxWidth:360}});
      mk.addTo(leafletMap); allMapLayers.push(mk);
    }} catch(e) {{}}
  }});

  // ── Planned Sites (blue) — only near serving sites ──
  const plannedAll = (msisdnSel !== 'All' && PLANNED_BY_MSISDN[msisdnSel])
                     ? PLANNED_BY_MSISDN[msisdnSel] : PLANNED_SITES;
  plannedAll.forEach(p => {{
    try {{
      let lat = parseFloat(p['Latitude']), lon = parseFloat(p['Longitude']);
      if (isNaN(lat) || isNaN(lon)) return;
      // Filter by proximity to serving sites (2km)
      const near = servingCoords.length === 0 ||
                   servingCoords.some(c => distKm(lat,lon,c.lat,c.lon) <= 2);
      if (!near) return;
      const sid = p['Site ID'] || 'Planned Site';
      let rows = '';
      for (const [k,v] of Object.entries(p)) {{
        if (k==='Latitude'||k==='Longitude'||v==='') continue;
        rows += `<tr><td style="padding:3px 8px;color:#64748b;font-weight:600;white-space:nowrap">${{k}}</td><td style="padding:3px 8px">${{v}}</td></tr>`;
      }}
      const popup = `<div style="font-family:Arial;font-size:12px;min-width:220px">
        <div style="background:#3498db;color:white;padding:6px 10px;font-weight:700">🔵 PLANNED: ${{sid}}</div>
        <table style="width:100%;border-collapse:collapse">${{rows}}</table></div>`;
      const mk = L.circleMarker([lat,lon],{{radius:7,color:'#2980b9',fillColor:'#3498db',fillOpacity:0.85,weight:2}})
        .bindPopup(popup,{{maxWidth:360}});
      mk.addTo(leafletMap); allMapLayers.push(mk);
    }} catch(e) {{}}
  }});

  // ── Customers — show only for selected MSISDN ──
  const custList = (msisdnSel !== 'All' && CUSTOMERS[msisdnSel]) ? CUSTOMERS[msisdnSel] : [];
  custList.forEach(c => {{
    try {{
      const lat = parseFloat(c['Latitude']), lon = parseFloat(c['Longitude']);
      if (isNaN(lat) || isNaN(lon)) return;
      let rows = '';
      for (const [k,v] of Object.entries(c)) {{
        if (k==='Latitude'||k==='Longitude'||v==='') continue;
        rows += `<tr><td style="padding:3px 8px;color:#64748b;font-weight:600;white-space:nowrap">${{k}}</td><td style="padding:3px 8px">${{v}}</td></tr>`;
      }}
      const popup = `<div style="font-family:Arial;font-size:12px;min-width:220px">
        <div style="background:#f59e0b;color:#1a1a1a;padding:6px 10px;font-weight:700">⭐ Customer Location</div>
        <table style="width:100%;border-collapse:collapse">${{rows}}</table></div>`;
      const icon = L.divIcon({{
        className: '',
        html: `<div style="
          width:28px;height:28px;
          background:#f59e0b;
          border:3px solid #b45309;
          border-radius:50% 50% 50% 0;
          transform:rotate(-45deg);
          box-shadow:0 2px 6px rgba(0,0,0,0.4);
          display:flex;align-items:center;justify-content:center;
        "><span style="transform:rotate(45deg);font-size:13px;line-height:1">👤</span></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 28],
        popupAnchor: [0, -30]
      }});
      const mk = L.marker([lat,lon], {{icon}}).bindPopup(popup, {{maxWidth:360}});
      mk.addTo(leafletMap); allMapLayers.push(mk);
    }} catch(e) {{}}
  }});
}}

// ── Init on page load ──
window.addEventListener('DOMContentLoaded', function() {{
  updateSiteDropdown();
  renderAll(RAW_DATA);
}});
</script>


<!-- ══ HIDDEN QA DATA PANELS (used by floating chat) ══ -->
<div style="display:none">
<!-- ══ TAB 1 – Throughput ══ -->
<div id="qa1" class="qa-panel qa-show">
  <div class="qgrid">
    <div class="qcard" style="border-left:5px solid #6366f1">
      <div class="qcard-lbl" style="color:#6366f1">⬇️ Avg DL Throughput</div>
      <div class="qcard-body">
        <span style="font-size:14px;font-weight:700">{'🟢' if q_dl_avg>=5 else ('🟡' if q_dl_avg>=2 else '🔴')} {q_dl_avg} Mbps</span><br>
        • Median: {q_dl_median} Mbps<br>
        • P10: {q_dl_p10} Mbps &nbsp;|&nbsp; P90: {q_dl_p90} Mbps<br>
        • Min: {q_dl_min} Mbps &nbsp;|&nbsp; Max: {q_dl_max} Mbps
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #22c55e">
      <div class="qcard-lbl" style="color:#22c55e">⬆️ Avg UL Throughput</div>
      <div class="qcard-body">
        <span style="font-size:14px;font-weight:700">{q_ul_avg} Mbps</span><br>
        • Max: {q_ul_max} Mbps
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #f59e0b">
      <div class="qcard-lbl" style="color:#f59e0b">↕️ DL/UL Ratio</div>
      <div class="qcard-body">
        <b>DL/UL Ratio:</b> {q_dl_ul_ratio}x<br>
        Downlink is {q_dl_ul_ratio} times faster than Uplink
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #22c55e">
      <div class="qcard-lbl" style="color:#22c55e">🏆 Best Site Throughput</div>
      <div class="qcard-body">🥇 <b>{q_best_site}</b> — {q_best_tp} Mbps</div>
    </div>
    <div class="qcard" style="border-left:5px solid #e74c3c">
      <div class="qcard-lbl" style="color:#e74c3c">📉 Worst Site Throughput</div>
      <div class="qcard-body">
        ⚠️ <b>{q_worst_site}</b> — {q_worst_tp} Mbps<br>
        Gap from best: {round(q_best_tp - q_worst_tp, 2)} Mbps
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #8b5cf6">
      <div class="qcard-lbl" style="color:#8b5cf6">📊 Throughput per Site</div>
      <div class="qcard-body">{q_site_tp_html}</div>
    </div>
  </div>
  <div style="background:#fff;border-radius:14px;padding:14px;box-shadow:0 2px 12px rgba(0,0,0,.06)">
    <div style="font-size:13px;font-weight:700;color:#1e293b;margin-bottom:8px">📈 DL Throughput Distribution (Histogram)</div>
    <div id="qa_hist_chart"></div>
  </div>
</div>

<!-- ══ TAB 2 – Sites ══ -->
<div id="qa2" class="qa-panel">
  <div class="qgrid">
    <div class="qcard" style="border-left:5px solid #6366f1;grid-column:1/-1">
      <div class="qcard-lbl" style="color:#6366f1">📡 Site Comparison</div>
      <div class="qcard-body">{q_site_tp_html}</div>
    </div>
  </div>
  <div style="background:#fff;border-radius:14px;padding:14px;box-shadow:0 2px 12px rgba(0,0,0,.06);margin-bottom:12px;overflow-x:auto">
    <div style="font-size:13px;font-weight:700;margin-bottom:8px">📋 Detailed Table per Site</div>
    <table class="qtable">
      <thead><tr><th>Site</th><th>Avg DL (Mbps)</th><th>Total Traffic (MB)</th><th>RAT</th><th>Top App</th></tr></thead>
      <tbody>{site_comparison_rows}</tbody>
    </table>
  </div>
  <div class="qgrid">
    <div class="qcard" style="border-left:5px solid #8b5cf6">
      <div class="qcard-lbl" style="color:#8b5cf6">📱 Top App per Site</div>
      <div class="qcard-body">{"<br>".join(f"• <b>{s}:</b> {a}" for s,a in _q_app_per_site.items()) or "No app data"}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #06b6d4">
      <div class="qcard-lbl" style="color:#06b6d4">📶 RAT per Site</div>
      <div class="qcard-body">{"<br>".join(f"• <b>{s}:</b> {r}" for s,r in _q_rat_per_site.items()) or "No RAT data"}</div>
    </div>
  </div>
  <div style="background:#fff;border-radius:14px;padding:14px;box-shadow:0 2px 12px rgba(0,0,0,.06)">
    <div style="font-size:13px;font-weight:700;margin-bottom:8px">📦 Traffic per Site (MB)</div>
    <div id="qa_site_traffic_chart"></div>
  </div>
</div>

<!-- ══ TAB 3 – Apps ══ -->
<div id="qa3" class="qa-panel">
  <div class="qgrid">
    <div class="qcard" style="border-left:5px solid #6366f1">
      <div class="qcard-lbl" style="color:#6366f1">📱 Top 10 Most Used Apps</div>
      <div class="qcard-body">{q_top10_usage_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #22c55e">
      <div class="qcard-lbl" style="color:#22c55e">⚡ Top 10 Apps by DL Throughput</div>
      <div class="qcard-body">{q_top10_dl_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #f59e0b">
      <div class="qcard-lbl" style="color:#f59e0b">📦 Top 10 Apps by Traffic</div>
      <div class="qcard-body">{q_top10_traffic_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #3b82f6">
      <div class="qcard-lbl" style="color:#3b82f6">🌐 Top Browsing Apps</div>
      <div class="qcard-body">{q_browsing_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #8b5cf6">
      <div class="qcard-lbl" style="color:#8b5cf6">🎬 Top Video Streaming Apps</div>
      <div class="qcard-body">{q_video_html}</div>
    </div>
  </div>
  <div style="background:#fff;border-radius:14px;padding:14px;box-shadow:0 2px 12px rgba(0,0,0,.06)">
    <div style="font-size:13px;font-weight:700;margin-bottom:8px">📊 App Distribution (Top 8)</div>
    <div id="qa_app_pie_chart"></div>
  </div>
</div>

<!-- ══ TAB 4 – Network ══ -->
<div id="qa4" class="qa-panel">
  <div class="qgrid">
    <div class="qcard" style="border-left:5px solid #6366f1">
      <div class="qcard-lbl" style="color:#6366f1">📶 Radio Access Type</div>
      <div class="qcard-body">{q_rat_full_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #22c55e">
      <div class="qcard-lbl" style="color:#22c55e">⚡ Avg DL per RAT</div>
      <div class="qcard-body">{q_rat_dl_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #f59e0b">
      <div class="qcard-lbl" style="color:#f59e0b">🌍 Roaming Analysis</div>
      <div class="qcard-body">
        • <b>Local:</b> {q_local_cnt:,} ({q_local_pct}%)<br>
        • <b>Roaming:</b> {q_roam_cnt:,} ({q_roam_pct}%)
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #8b5cf6">
      <div class="qcard-lbl" style="color:#8b5cf6">📊 Avg DL: Local vs Roaming</div>
      <div class="qcard-body">{q_roam_dl_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #06b6d4">
      <div class="qcard-lbl" style="color:#06b6d4">🔐 Encrypted Sessions</div>
      <div class="qcard-body">{q_enc_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #e74c3c">
      <div class="qcard-lbl" style="color:#e74c3c">🚦 Max Bit Rate (MBR)</div>
      <div class="qcard-body">{q_mbr_html}</div>
    </div>
  </div>
</div>

<!-- ══ TAB 5 – Issues ══ -->
<div id="qa5" class="qa-panel">
  <div class="qgrid">
    <div class="qcard" style="border-left:5px solid #6366f1">
      <div class="qcard-lbl" style="color:#6366f1">📊 Performance Classification</div>
      <div class="qcard-body">
        🟢 <b>Good (&gt;1 Mbps):</b> {q_good_rows:,} rows ({q_good_pct}%)<br>
        🟡 <b>Low (0–1 Mbps):</b> {q_low_rows:,} rows ({q_low_pct}%)<br>
        🔴 <b>Zero Traffic:</b> {q_zero_rows:,} rows ({q_zero_pct}%)
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #e74c3c">
      <div class="qcard-lbl" style="color:#e74c3c">📉 Packet Loss</div>
      <div class="qcard-body">
        {_q_loss_icon(q_dl_loss_avg)} <b>DL Avg:</b> {q_dl_loss_str}<br>
        <b>UL Avg:</b> {f"{q_ul_loss_avg2}%" if q_ul_loss_avg2 is not None else "N/A"}<br>
        <b>DL Max:</b> {f"{q_dl_loss_max}%" if q_dl_loss_max is not None else "N/A"}
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #f59e0b">
      <div class="qcard-lbl" style="color:#f59e0b">⏱️ Transmission Delay</div>
      <div class="qcard-body">
        {_q_delay_icon(q_dl_delay_avg)} <b>DL Avg:</b> {q_dl_delay_str}<br>
        <b>UL Avg:</b> {f"{q_ul_delay_avg2} ms" if q_ul_delay_avg2 is not None else "N/A"}
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #8b5cf6">
      <div class="qcard-lbl" style="color:#8b5cf6">🔁 TCP Retransmission Rate</div>
      <div class="qcard-body">
        {_q_retx_icon(q_dl_retx_avg)} <b>DL Avg:</b> {f"{q_dl_retx_avg}%" if q_dl_retx_avg is not None else "N/A"}<br>
        <b>UL Avg:</b> {f"{q_ul_retx_avg2}%" if q_ul_retx_avg2 is not None else "N/A"}<br>
        <b>DL Max:</b> {f"{q_dl_retx_max}%" if q_dl_retx_max is not None else "N/A"}
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #06b6d4">
      <div class="qcard-lbl" style="color:#06b6d4">🔄 RTT (Round Trip Time)</div>
      <div class="qcard-body">
        {_q_rtt_icon(q_dl_rtt_avg)} <b>DL Avg:</b> {f"{round(q_dl_rtt_avg/1000,1)} ms" if q_dl_rtt_avg is not None else "N/A"}<br>
        <b>UL Avg:</b> {f"{round(q_ul_rtt_avg2/1000,1)} ms" if q_ul_rtt_avg2 is not None else "N/A"}
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #e74c3c">
      <div class="qcard-lbl" style="color:#e74c3c">⚠️ Most Problematic Sites</div>
      <div class="qcard-body">{prob_sites_html}</div>
    </div>
  </div>
  <div style="background:#fff;border-radius:14px;padding:14px;box-shadow:0 2px 12px rgba(0,0,0,.06);overflow-x:auto">
    <div style="font-size:13px;font-weight:700;margin-bottom:8px">📋 Issue Details per Site</div>
    <table class="qtable">
      <thead><tr><th>Site</th><th>Issue</th><th>Count</th><th>Status</th></tr></thead>
      <tbody>{issues_detail_rows}</tbody>
    </table>
  </div>
</div>

<!-- ══ TAB 6 – Timing ══ -->
<div id="qa6" class="qa-panel">
  <div class="qgrid">
    <div class="qcard" style="border-left:5px solid #6366f1">
      <div class="qcard-lbl" style="color:#6366f1">⏰ Best &amp; Worst Hour</div>
      <div class="qcard-body">
        🟢 <b>Best Hour:</b> {q_best_hour_str}<br>
        🔴 <b>Worst Hour:</b> {q_worst_hour_str}
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #8b5cf6">
      <div class="qcard-lbl" style="color:#8b5cf6">📅 Best &amp; Worst Day</div>
      <div class="qcard-body">
        🟢 <b>Best Day:</b> {q_best_day_str}<br>
        🔴 <b>Worst Day:</b> {q_worst_day_str}
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #22c55e">
      <div class="qcard-lbl" style="color:#22c55e">⏱️ Peak Hours</div>
      <div class="qcard-body">
        🔝 <b>Top Hours:</b><br>{q_peak3_html}<br><br>
        📉 <b>Weakest Hours:</b><br>{q_off3_html}
      </div>
    </div>
    <div class="qcard" style="border-left:5px solid #f59e0b">
      <div class="qcard-lbl" style="color:#f59e0b">📊 Busiest Hour</div>
      <div class="qcard-body">📈 <b>{q_busiest_hour_val:02d}:00</b> — {q_busiest_hour_cnt:,} records</div>
    </div>
  </div>
  <div style="background:#fff;border-radius:14px;padding:14px;box-shadow:0 2px 12px rgba(0,0,0,.06);margin-bottom:12px">
    <div style="font-size:13px;font-weight:700;margin-bottom:8px">⏰ Avg DL Throughput by Hour</div>
    <div id="qa_hourly_bar"></div>
  </div>
  <div style="background:#fff;border-radius:14px;padding:14px;box-shadow:0 2px 12px rgba(0,0,0,.06)">
    <div style="font-size:13px;font-weight:700;margin-bottom:8px">📅 Daily Avg DL Throughput</div>
    <div id="qa_daily_line"></div>
  </div>
</div>

<!-- ══ TAB 7 – Connection Quality ══ -->
<div id="qa7" class="qa-panel">
  <div class="qgrid">
    <div class="qcard" style="border-left:5px solid #6366f1">
      <div class="qcard-lbl" style="color:#6366f1">📊 Connection Quality KPIs</div>
      <div class="qcard-body">{q_quality_kpi_html}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #e74c3c">
      <div class="qcard-lbl" style="color:#e74c3c">🔁 TCP Retransmission</div>
      <div class="qcard-body">{q_retx_html2}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #f59e0b">
      <div class="qcard-lbl" style="color:#f59e0b">🔄 RTT / Latency</div>
      <div class="qcard-body">{q_rtt_html2}</div>
    </div>
    <div class="qcard" style="border-left:5px solid #22c55e">
      <div class="qcard-lbl" style="color:#22c55e">📦 Effective Traffic &amp; Duration</div>
      <div class="qcard-body">{q_eff_html}</div>
    </div>
  </div>
  <div class="qcard" style="border-left:5px solid {q_sq_color};text-align:center;padding:24px">
    <div class="qcard-lbl" style="color:{q_sq_color};text-align:center">🏅 Overall Network Quality Score</div>
    <div style="font-size:48px;font-weight:800;color:{q_sq_color}">{q_score}/100</div>
    <div style="font-size:18px;font-weight:700;color:#1e293b">{q_sq_label}</div>
  </div>
</div>

<!-- ══ TAB 8 – Full Summary ══ -->
<div id="qa8" class="qa-panel">
  <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:14px;
              padding:20px 24px;color:#fff;margin-bottom:14px">
    <div style="font-size:20px;font-weight:800;margin-bottom:4px">📋 Executive Summary</div>
    <div style="font-size:12px;opacity:.8">Full network performance report for {msisdn_value}</div>
  </div>
  <div style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.06)">
    {''.join(f"""<div style="display:flex;gap:12px;padding:9px 14px;border-bottom:1px solid #f1f5f9">
      <div style="min-width:210px;font-weight:700;color:#64748b;font-size:12px">{lbl}</div>
      <div style="color:#1e293b;font-size:13px">{val}</div></div>""" for lbl,val in [
        ("👤 Customer",       msisdn_value),
        ("📱 Device",         device_info),
        ("📅 Period",         f"{q_time_start_str} → {q_time_end_str} ({q_duration_h} hours)"),
        ("📊 Total Records",  f"{q_N:,}"),
        ("📦 Total Traffic",  f"{q_total_dl_gb} GB"),
        ("📡 Number of Sites",f"{q_n_sites} — {q_sites_list}"),
        ("⬇️ Avg DL",         f"{q_dl_avg} Mbps (Max: {q_dl_max}, Min: {q_dl_min}, Median: {q_dl_median})"),
        ("⬆️ Avg UL",         f"{q_ul_avg} Mbps"),
        ("🏆 Best Site",      f"{q_best_site} — {q_best_tp} Mbps"),
        ("📉 Worst Site",     f"{q_worst_site} — {q_worst_tp} Mbps"),
        ("📶 RAT",            q_rat_summary),
        ("🌍 Roaming",        f"Local: {q_local_cnt:,} ({q_local_pct}%) | Roaming: {q_roam_cnt:,} ({q_roam_pct}%)"),
        ("🟢 Good Records",   f"{q_good_rows:,} ({q_good_pct}%)"),
        ("🟡 Low Throughput", f"{q_low_rows:,} ({q_low_pct}%)"),
        ("🔴 Zero Traffic",   f"{q_zero_rows:,} ({q_zero_pct}%)"),
        ("📉 DL Packet Loss", q_dl_loss_str),
        ("⏱️ DL Delay",       q_dl_delay_str),
        ("🔁 DL TCP Retx",    q_dl_retx_str),
        ("🔄 DL RTT",         q_dl_rtt_str),
        ("📱 Top App",        q_top_app_str),
        ("⏰ Best Hour",      q_best_hour_str),
        ("⏰ Worst Hour",     q_worst_hour_str),
        ("🏅 Network Quality",f"{q_score}/100 — {q_sq_label}"),
    ])}
  </div>
</div>

<script>
function showQA(e, id) {{
  document.querySelectorAll('.qa-panel').forEach(p => p.classList.remove('qa-show'));
  document.querySelectorAll('.qa-tab').forEach(b => b.classList.remove('qa-active'));
  document.getElementById(id).classList.add('qa-show');
  e.currentTarget.classList.add('qa-active');
  if (id === 'qa1' && !window._qa1done) {{ window._qa1done=1; renderQAHist(); }}
  if (id === 'qa2' && !window._qa2done) {{ window._qa2done=1; renderQASiteTraffic(); }}
  if (id === 'qa3' && !window._qa3done) {{ window._qa3done=1; renderQAAppPie(); }}
  if (id === 'qa6' && !window._qa6done) {{ window._qa6done=1; renderQAHourlyBar(); renderQADailyLine(); }}
}}

// ── Throughput Histogram ──
function renderQAHist() {{ renderQAHistOn(document.getElementById('qa_hist_chart')); }}
function renderQAHistOn(div) {{
  if (!div) return;
  const dlVals = RAW_DATA.map(r => parseFloat(r[DL_COL])).filter(v => !isNaN(v) && v > 0);
  if (!dlVals.length) return;
  const min = Math.min(...dlVals), max = Math.max(...dlVals);
  const bins = 40, w = (max-min)/bins;
  const counts = new Array(bins).fill(0);
  dlVals.forEach(v => {{ const i = Math.min(Math.floor((v-min)/w), bins-1); counts[i]++; }});
  const xs = Array.from({{length:bins}}, (_,i) => +(min + i*w + w/2).toFixed(2));
  Plotly.newPlot(div, [{{
    x:xs, y:counts, type:'bar', marker:{{color:'#6366f1'}}, name:'Records'
  }}], {{
    template:'plotly_white', height:280, bargap:0.05,
    xaxis:{{title:'DL Mbps'}}, yaxis:{{title:'Records'}},
    margin:{{t:10,b:45}}, showlegend:false
  }}, {{responsive:true}});
}}

// ── Site Traffic Bar ──
function renderQASiteTraffic() {{ renderQASiteTrafficOn(document.getElementById('qa_site_traffic_chart')); }}
function renderQASiteTrafficOn(div) {{
  if (!div) return;
  const byS = {{}};
  RAW_DATA.forEach(r => {{
    const s = r['_site_id_clean'] || '';
    const t = parseFloat(r['Traffic_MB'] || 0);
    if (!isNaN(t)) byS[s] = (byS[s]||0) + t;
  }});
  const sites = Object.keys(byS).sort((a,b) => byS[b]-byS[a]);
  const vals  = sites.map(s => +byS[s].toFixed(1));
  Plotly.newPlot(div, [{{
    x:sites, y:vals, type:'bar', text:vals.map(v=>v.toFixed(0)), textposition:'outside',
    marker:{{color:vals.map((_,i) => i===0?'#6366f1':'#a5b4fc')}}, name:'Traffic'
  }}], {{
    template:'plotly_white', height:280,
    yaxis:{{title:'Traffic (MB)'}}, xaxis:{{title:'Site'}},
    bargap:0.3, margin:{{t:10,b:50}}, showlegend:false
  }}, {{responsive:true}});
}}

// ── App Pie ──
function renderQAAppPie() {{ renderQAAppPieOn(document.getElementById('qa_app_pie_chart')); }}
function renderQAAppPieOn(div) {{
  if (!div) return;
  const ac = {{}};
  RAW_DATA.forEach(r => {{
    const a = String(r['App Name']||'').trim();
    if (a && a.toUpperCase() !== 'NAN' && a !== '') ac[a] = (ac[a]||0)+1;
  }});
  const top8 = Object.entries(ac).sort((a,b)=>b[1]-a[1]).slice(0,8);
  Plotly.newPlot(div, [{{
    labels: top8.map(x=>x[0]), values: top8.map(x=>x[1]),
    type:'pie', hole:0.45,
    marker:{{colors:['#6366f1','#8b5cf6','#a78bfa','#c4b5fd','#22c55e','#3b82f6','#f59e0b','#e74c3c']}}
  }}], {{
    template:'plotly_white', height:340,
    margin:{{t:10,b:10,l:10,r:10}}, showlegend:true
  }}, {{responsive:true}});
}}

// ── Hourly Bar ──
const QA_HOURLY_LABELS = {q_hourly_labels_json};
const QA_HOURLY_VALUES = {q_hourly_values_json};
const QA_HOURLY_COLORS = {q_hourly_colors_json};
function renderQAHourlyBar() {{ renderQAHourlyBarOn(document.getElementById('qa_hourly_bar')); }}
function renderQAHourlyBarOn(div) {{
  if (!div || !QA_HOURLY_LABELS.length) return;
  Plotly.newPlot(div, [{{
    x: QA_HOURLY_LABELS, y: QA_HOURLY_VALUES, type:'bar',
    text: QA_HOURLY_VALUES.map(v=>v.toFixed(1)), textposition:'outside',
    marker:{{color: QA_HOURLY_COLORS}}, name:'Avg DL'
  }}], {{
    template:'plotly_white', height:300,
    yaxis:{{title:'Avg DL (Mbps)'}}, xaxis:{{title:'Hour'}},
    bargap:0.2, margin:{{t:10,b:45}}, showlegend:false, coloraxis_showscale:false
  }}, {{responsive:true}});
}}

// ── Daily Line ──
const QA_DAILY_LABELS = {q_daily_labels_json};
const QA_DAILY_VALUES = {q_daily_values_json};
function renderQADailyLine() {{ renderQADailyLineOn(document.getElementById('qa_daily_line')); }}
function renderQADailyLineOn(div) {{
  if (!div || QA_DAILY_LABELS.length < 2) return;
  Plotly.newPlot(div, [{{
    x: QA_DAILY_LABELS, y: QA_DAILY_VALUES,
    mode:'lines+markers', line:{{color:'#6366f1',width:2}},
    marker:{{size:6}}, name:'Avg DL'
  }}], {{
    template:'plotly_white', height:280,
    yaxis:{{title:'Avg DL (Mbps)'}}, xaxis:{{title:'Date'}},
    margin:{{t:10,b:50}}, showlegend:false
  }}, {{responsive:true}});
}}
</script>


</div>

<!-- ══ FLOATING CHAT PANEL for Export ══ -->
<style>
#exp-robot-btn {{
  position:fixed;bottom:28px;right:28px;
  width:66px;height:66px;border-radius:50%;
  background:linear-gradient(135deg,#6366f1,#8b5cf6);
  border:none;cursor:pointer;z-index:10000;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 20px rgba(99,102,241,.45);
  transition:transform .18s,box-shadow .18s;
}}
#exp-robot-btn:hover{{transform:scale(1.12);box-shadow:0 7px 28px rgba(99,102,241,.6)}}
#exp-robot-btn svg{{width:38px;height:38px}}
#exp-chat-panel {{
  position:fixed;bottom:106px;right:28px;
  width:480px;height:600px;
  background:#ffffff;border-radius:16px;
  border:1px solid #e2e8f0;
  box-shadow:0 12px 48px rgba(0,0,0,.18);
  display:none;flex-direction:column;
  overflow:hidden;z-index:9999;
  font-family:'Inter',sans-serif;
}}
#exp-chat-panel.ecopen{{display:flex}}
#exp-chat-hdr{{
  background:linear-gradient(135deg,#6366f1,#8b5cf6);
  padding:14px 18px;display:flex;
  align-items:center;justify-content:space-between;flex-shrink:0;
}}
#exp-chat-hdr span{{color:#fff;font-weight:700;font-size:15px}}
#exp-chat-close{{background:none;border:none;cursor:pointer;
  color:rgba(255,255,255,.85);font-size:22px;line-height:1;padding:0}}
#exp-chat-tabs{{
  display:flex;flex-wrap:wrap;gap:5px;
  padding:10px 12px;border-bottom:1px solid #e2e8f0;
  flex-shrink:0;background:#f8fafc;
}}
.ect-btn{{
  background:#fff;border:1px solid #e2e8f0;
  border-radius:8px;padding:5px 10px;
  font-size:11px;font-weight:600;color:#64748b;
  cursor:pointer;transition:all .15s;font-family:'Inter',sans-serif;
  white-space:nowrap;
}}
.ect-btn:hover,.ect-btn.ect-active{{background:#6366f1;color:#fff;border-color:#6366f1}}
#exp-chat-body{{
  overflow-y:auto;padding:14px;flex:1;
}}
.ec-panel{{display:none}}
.ec-panel.ec-show{{display:block}}
.ec-card{{background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;padding:13px 15px;margin-bottom:10px}}
.ec-lbl{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#64748b;margin-bottom:7px}}
.ec-val{{font-size:13px;color:#1e293b;line-height:1.8}}
.ec-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}}
.ec-kpi{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:11px 13px}}
.ec-kpi-lbl{{font-size:10px;color:#64748b;margin-bottom:3px}}
.ec-kpi-val{{font-size:20px;font-weight:700;color:#1e293b}}
.ec-row{{display:flex;align-items:center;justify-content:space-between;padding:7px 10px;border-radius:8px;background:#f1f5f9;margin-bottom:5px}}
.ec-row-k{{font-size:12px;font-weight:600;color:#334155}}
.ec-row-v{{font-size:13px;font-weight:700;color:#1e293b}}
</style>

<button id="exp-robot-btn" title="Analytics Q&A" onclick="document.getElementById('exp-chat-panel').classList.toggle('ecopen')">
<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="12" y="20" width="40" height="30" rx="6" fill="white" opacity="0.95"/>
  <line x1="32" y1="20" x2="32" y2="10" stroke="white" stroke-width="3" stroke-linecap="round"/>
  <circle cx="32" cy="8" r="4" fill="white"/>
  <circle cx="22" cy="32" r="5" fill="#6366f1"/>
  <circle cx="42" cy="32" r="5" fill="#6366f1"/>
  <circle cx="23" cy="31" r="2" fill="white"/>
  <circle cx="43" cy="31" r="2" fill="white"/>
  <rect x="20" y="41" width="24" height="4" rx="2" fill="#6366f1" opacity="0.7"/>
  <rect x="22" y="41" width="4" height="4" rx="1" fill="white" opacity="0.9"/>
  <rect x="30" y="41" width="4" height="4" rx="1" fill="white" opacity="0.9"/>
  <rect x="38" y="41" width="4" height="4" rx="1" fill="white" opacity="0.9"/>
  <rect x="6" y="26" width="6" height="12" rx="3" fill="white" opacity="0.8"/>
  <rect x="52" y="26" width="6" height="12" rx="3" fill="white" opacity="0.8"/>
</svg>
</button>

<div id="exp-chat-panel">
  <div id="exp-chat-hdr">
    <span>📊 Analytics Q&amp;A</span>
    <button id="exp-chat-close" onclick="document.getElementById('exp-chat-panel').classList.remove('ecopen')">✕</button>
  </div>
  <div id="exp-chat-tabs">
    <button class="ect-btn ect-active" onclick="ecShow(this,'ec1')">⚡ Throughput</button>
    <button class="ect-btn" onclick="ecShow(this,'ec2')">📡 Sites</button>
    <button class="ect-btn" onclick="ecShow(this,'ec3')">📱 Apps</button>
    <button class="ect-btn" onclick="ecShow(this,'ec4')">🌐 Network</button>
    <button class="ect-btn" onclick="ecShow(this,'ec5')">⚠️ Issues</button>
    <button class="ect-btn" onclick="ecShow(this,'ec6')">⏰ Timing</button>
    <button class="ect-btn" onclick="ecShow(this,'ec7')">🔒 Quality</button>
    <button class="ect-btn" onclick="ecShow(this,'ec8')">📋 Summary</button>
  </div>
  <div id="exp-chat-body">

    <div id="ec1" class="ec-panel ec-show"></div>
    <div id="ec2" class="ec-panel"></div>
    <div id="ec3" class="ec-panel"></div>
    <div id="ec4" class="ec-panel"></div>
    <div id="ec5" class="ec-panel"></div>
    <div id="ec6" class="ec-panel"></div>
    <div id="ec7" class="ec-panel"></div>
    <div id="ec8" class="ec-panel"></div>

  </div>
</div>

<script>
(function(){{
  const PANEL_MAP = [
    ['ec1','qa1'],['ec2','qa2'],['ec3','qa3'],
    ['ec4','qa4'],['ec5','qa5'],['ec6','qa6'],['ec7','qa7'],['ec8','qa8']
  ];
  PANEL_MAP.forEach(([ecId, qaId]) => {{
    const src = document.getElementById(qaId);
    const dst = document.getElementById(ecId);
    if (src && dst) {{
      dst.innerHTML = src.innerHTML;
      dst.querySelectorAll('[id]').forEach(el => {{ el.id = 'ec_' + el.id; }});
    }}
  }});

  function ecShow(btn, id) {{
    document.querySelectorAll('.ect-btn').forEach(b => b.classList.remove('ect-active'));
    document.querySelectorAll('.ec-panel').forEach(p => p.classList.remove('ec-show'));
    btn.classList.add('ect-active');
    document.getElementById(id).classList.add('ec-show');
    setTimeout(() => {{
      const p = document.getElementById(id);
      if (!p || p._chartsRendered) return;
      p._chartsRendered = true;
      const h = (divId) => p.querySelector('#ec_' + divId);
      if (id==='ec1') {{ renderQAHistOn(h('qa_hist_chart')); }}
      if (id==='ec2') {{ renderQASiteTrafficOn(h('qa_site_traffic_chart')); }}
      if (id==='ec3') {{ renderQAAppPieOn(h('qa_app_pie_chart')); }}
      if (id==='ec6') {{ renderQAHourlyBarOn(h('qa_hourly_bar')); renderQADailyLineOn(h('qa_daily_line')); }}
    }}, 80);
  }}
  window.ecShow = ecShow;

  document.getElementById('exp-robot-btn').addEventListener('click', function() {{
    setTimeout(() => {{
      const ec1 = document.getElementById('ec1');
      if (ec1 && !ec1._chartsRendered) {{
        ec1._chartsRendered = true;
        const h = (divId) => ec1.querySelector('#ec_' + divId);
        renderQAHistOn(h('qa_hist_chart'));
      }}
    }}, 150);
  }});
}})();
</script>

</body>
</html>"""
    return full_html

# ---------------------------
# ISSUES
# ---------------------------
st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">🚨 Issues</div>''', unsafe_allow_html=True)
df["Issue"] = "Good"
df.loc[df["Throughput"] < 1, "Issue"] = "Low Throughput"
df.loc[df["Throughput"] == 0, "Issue"] = "Zero Traffic"

issues_df = df.groupby([trace_col, "Issue"]).size().reset_index(name="Count")
st.markdown('<div style="background:#fff;border-radius:12px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.05);margin-top:8px">', unsafe_allow_html=True)
st.dataframe(issues_df, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------
# SAMPLE DATA
# ---------------------------
st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">📋 Sample Data</div>''', unsafe_allow_html=True)
st.markdown('<div style="background:#fff;border-radius:12px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.05);margin-top:8px">', unsafe_allow_html=True)
st.dataframe(df.head(100), use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# ── helpers ──────────────────────────────────────────────────
def _safe_mean(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return round(float(s.mean()), 2) if len(s) else 0.0

def _safe_sum(series):
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    return round(float(s.sum()), 2)

def _pct(part, total):
    return round(100 * part / total, 1) if total else 0.0

def _status_icon(val, good=5, warn=2):
    if val >= good:   return "🟢"
    if val >= warn:   return "🟡"
    return "🔴"

def _render_card(title, answer, icon="📌", color="#6366f1"):
    st.markdown(f"""
    <div style="background:#fff;border-radius:14px;padding:16px 20px;
                box-shadow:0 2px 12px rgba(0,0,0,.06);margin-bottom:12px;
                border-left:5px solid {color}">
      <div style="font-size:12px;font-weight:700;color:{color};text-transform:uppercase;
                  letter-spacing:.06em;margin-bottom:6px">{icon} {title}</div>
      <div style="font-size:13px;color:#1e293b;line-height:1.7">{answer}</div>
    </div>""", unsafe_allow_html=True)

# ── Compute all numbers once ────────────────────────────────
_dl  = "DL_Mbps"  if "DL_Mbps"  in df.columns else None
_ul  = "UL_Mbps"  if "UL_Mbps"  in df.columns else None
_tp  = "Throughput"

_dl_col_raw = next((c for c in df.columns if "downlink throughput" in c.lower()), None)
_ul_col_raw = next((c for c in df.columns if "uplink throughput"   in c.lower()), None)
_dl_loss_col = next((c for c in df.columns if "downlink packet loss" in c.lower()), None)
_ul_loss_col = next((c for c in df.columns if "uplink packet loss"   in c.lower()), None)
_dl_delay_col = next((c for c in df.columns if "downlink transmission delay" in c.lower()), None)
_ul_delay_col = next((c for c in df.columns if "uplink transmission delay"   in c.lower()), None)
_dl_rtt_col  = next((c for c in df.columns if "downlink rtt" in c.lower()), None)
_ul_rtt_col  = next((c for c in df.columns if "uplink rtt"   in c.lower()), None)
_dl_retx_col = next((c for c in df.columns if "downlink tcp retransmission" in c.lower()), None)
_ul_retx_col = next((c for c in df.columns if "uplink tcp retransmission"   in c.lower()), None)
_dl_eff_col  = next((c for c in df.columns if "downlink effective traffic"  in c.lower()), None)
_ul_eff_col  = next((c for c in df.columns if "uplink effective traffic"    in c.lower()), None)
_dl_eff_dur  = next((c for c in df.columns if "downlink effective duration" in c.lower()), None)
_ul_eff_dur  = next((c for c in df.columns if "uplink effective duration"   in c.lower()), None)
_enc_col     = next((c for c in df.columns if "encrypted" in c.lower()), None)
_mbr_dl_col  = next((c for c in df.columns if "allowed downlink maximum" in c.lower()), None)
_mbr_ul_col  = next((c for c in df.columns if "allowed uplink maximum"   in c.lower()), None)

N = len(df)
sites_all   = df["_site_id_clean"].dropna().unique().tolist()
n_sites     = len(sites_all)
time_start  = df["Start Time"].min()
time_end    = df["Start Time"].max()
duration_h  = round((time_end - time_start).total_seconds() / 3600, 1)

dl_avg      = _safe_mean(df[_dl]) if _dl else _safe_mean(df[_tp])
ul_avg      = _safe_mean(df[_ul]) if _ul else 0.0
dl_max      = round(float(pd.to_numeric(df[_dl], errors="coerce").max()), 2) if _dl else 0.0
ul_max      = round(float(pd.to_numeric(df[_ul], errors="coerce").max()), 2) if _ul else 0.0
dl_min      = round(float(pd.to_numeric(df[_dl], errors="coerce").replace(0, np.nan).min()), 2) if _dl else 0.0
dl_median   = round(float(pd.to_numeric(df[_dl], errors="coerce").median()), 2) if _dl else 0.0
dl_p10      = round(float(pd.to_numeric(df[_dl], errors="coerce").quantile(0.10)), 2) if _dl else 0.0
dl_p90      = round(float(pd.to_numeric(df[_dl], errors="coerce").quantile(0.90)), 2) if _dl else 0.0

total_dl_gb = round(_safe_sum(df["Traffic_MB"]) / 1024, 3) if "Traffic_MB" in df.columns else 0.0
total_dl_mb = round(_safe_sum(df["Traffic_MB"]), 1) if "Traffic_MB" in df.columns else 0.0

# per-site throughput
site_tp = (df.groupby("_site_id_clean")[_dl if _dl else _tp]
             .apply(lambda s: round(float(pd.to_numeric(s, errors="coerce").mean()), 2))
             .sort_values(ascending=False))
best_site  = site_tp.index[0]  if len(site_tp) else "N/A"
worst_site = site_tp.index[-1] if len(site_tp) else "N/A"
best_tp    = site_tp.iloc[0]   if len(site_tp) else 0
worst_tp   = site_tp.iloc[-1]  if len(site_tp) else 0

# per-site traffic
site_traffic = pd.Series(dtype=float)
if "Traffic_MB" in df.columns:
    site_traffic = df.groupby("_site_id_clean")["Traffic_MB"].sum().sort_values(ascending=False).round(1)

# issues
zero_rows  = int((pd.to_numeric(df[_dl if _dl else _tp], errors="coerce").fillna(0) == 0).sum())
low_rows   = int((pd.to_numeric(df[_dl if _dl else _tp], errors="coerce").fillna(0).between(0.001, 1)).sum())
good_rows  = N - zero_rows - low_rows

# RAT
rat_counts = df["Radio Access Type"].dropna().astype(str).value_counts() if "Radio Access Type" in df.columns else pd.Series(dtype=int)
nr_cnt   = int(rat_counts.get("NR", 0))
lte_cnt  = int(rat_counts.get("EUTRAN", rat_counts.get("LTE", 0)))

# Service type
svc_counts = df["Service Type"].dropna().astype(str).value_counts() if "Service Type" in df.columns else pd.Series(dtype=int)

# App
app_counts = df["App Name"].dropna().astype(str).value_counts() if "App Name" in df.columns else pd.Series(dtype=int)
top_apps   = app_counts.head(10)

# Roaming
roam_counts = df["Roaming Status"].dropna().astype(str).value_counts() if "Roaming Status" in df.columns else pd.Series(dtype=int)
local_cnt   = int(roam_counts.get("Local", roam_counts.get("LOCAL", 0)))
roam_cnt    = int(roam_counts.get("Roaming", roam_counts.get("ROAMING", 0)))

# Packet loss
dl_loss_avg = _safe_mean(df[_dl_loss_col]) if _dl_loss_col else None
ul_loss_avg = _safe_mean(df[_ul_loss_col]) if _ul_loss_col else None
dl_loss_max = round(float(pd.to_numeric(df[_dl_loss_col], errors="coerce").max()), 2) if _dl_loss_col else None

# Delay
dl_delay_avg = _safe_mean(df[_dl_delay_col]) if _dl_delay_col else None
ul_delay_avg = _safe_mean(df[_ul_delay_col]) if _ul_delay_col else None

# RTT
dl_rtt_avg = _safe_mean(df[_dl_rtt_col]) if _dl_rtt_col else None
ul_rtt_avg = _safe_mean(df[_ul_rtt_col]) if _ul_rtt_col else None

# Retransmission
dl_retx_avg = _safe_mean(df[_dl_retx_col]) if _dl_retx_col else None
ul_retx_avg = _safe_mean(df[_ul_retx_col]) if _ul_retx_col else None
dl_retx_max = round(float(pd.to_numeric(df[_dl_retx_col], errors="coerce").max()), 2) if _dl_retx_col else None

# Encryption
enc_pct = None
if _enc_col:
    enc_pct = _pct(int(df[_enc_col].astype(str).str.contains("Encrypt", case=False, na=False).sum()), N)

# MBR
mbr_dl_avg = _safe_mean(df[_mbr_dl_col]) if _mbr_dl_col else None
mbr_ul_avg = _safe_mean(df[_mbr_ul_col]) if _mbr_ul_col else None

# Hourly breakdown
df["_hour"] = df["Start Time"].dt.hour
hourly_dl = df.groupby("_hour")[_dl if _dl else _tp].apply(
    lambda s: round(float(pd.to_numeric(s, errors="coerce").mean()), 2)) if _dl or _tp in df.columns else pd.Series(dtype=float)
best_hour  = int(hourly_dl.idxmax()) if len(hourly_dl) else None
worst_hour = int(hourly_dl.idxmin()) if len(hourly_dl) else None

# Daily breakdown
df["_date"] = df["Start Time"].dt.date
daily_dl = df.groupby("_date")[_dl if _dl else _tp].apply(
    lambda s: round(float(pd.to_numeric(s, errors="coerce").mean()), 2))

# Device
device_info = "N/A"
if "Device Brand" in df.columns and "Device Model" in df.columns:
    devs = (df["Device Brand"].astype(str).str.strip() + " " + df["Device Model"].astype(str).str.strip()).unique()
    device_info = ", ".join(d for d in devs if d.strip() not in ("", "nan nan"))

# per-site stats for table
site_stats_df = pd.DataFrame({"Avg DL (Mbps)": site_tp})
if len(site_traffic):
    site_stats_df["Total Traffic (MB)"] = site_traffic
if "Radio Access Type" in df.columns:
    site_stats_df["RAT"] = df.groupby("_site_id_clean")["Radio Access Type"].agg(
        lambda s: s.dropna().astype(str).mode()[0] if len(s.dropna()) else "N/A")
if "Issue" in df.columns:
    site_stats_df["Issues"] = df.groupby("_site_id_clean")["Issue"].apply(
        lambda s: ", ".join(s.value_counts().index.tolist()))
site_stats_df = site_stats_df.reset_index().rename(columns={"_site_id_clean": "Site"})

# app per-site top app
app_per_site = {}
if "App Name" in df.columns:
    for sid, grp in df.groupby("_site_id_clean"):
        top = grp["App Name"].dropna().astype(str).value_counts()
        app_per_site[sid] = top.index[0] if len(top) else "N/A"


# ── Compute quality score ──
score = 100
if dl_loss_avg and dl_loss_avg > 1:     score -= 15
if dl_loss_avg and dl_loss_avg > 3:     score -= 15
if dl_retx_avg and dl_retx_avg > 1:    score -= 10
if dl_retx_avg and dl_retx_avg > 3:    score -= 10
if dl_delay_avg and dl_delay_avg > 50:  score -= 10
if dl_delay_avg and dl_delay_avg > 100: score -= 10
if dl_avg < 2:  score -= 15
if dl_avg < 1:  score -= 15
score = max(score, 0)
sq_label = "Excellent 🟢" if score >= 70 else ("Average 🟡" if score >= 40 else "Poor 🔴")

# ANALYTICS CHAT BUTTON — Analytics Chat Button
# ════════════════════════════════════════════════════════════════

# ── Compute required values for chat button ──
_cb_hourly_labels = [f"{int(h):02d}:00" for h in hourly_dl.index] if len(hourly_dl) else []
_cb_hourly_vals   = [float(v) for v in hourly_dl.values] if len(hourly_dl) else []

_cb_daily_labels  = [str(d) for d in daily_dl.index] if len(daily_dl) else []
_cb_daily_vals    = [float(v) for v in daily_dl.values] if len(daily_dl) else []

_cb_site_labels   = [str(s) for s in site_tp.index.tolist()] if len(site_tp) else []
_cb_site_vals     = [float(v) for v in site_tp.values.tolist()] if len(site_tp) else []

_cb_app_labels    = [str(k) for k in app_counts.head(8).index.tolist()] if len(app_counts) else []
_cb_app_vals      = [int(v) for v in app_counts.head(8).values.tolist()] if len(app_counts) else []

_cb_rat_labels    = [str(k) for k in rat_counts.index.tolist()] if len(rat_counts) else []
_cb_rat_vals      = [int(v) for v in rat_counts.values.tolist()] if len(rat_counts) else []

_cb_site_traffic_labels = [str(s) for s in site_traffic.index.tolist()] if len(site_traffic) else []
_cb_site_traffic_vals   = [float(v) for v in site_traffic.values.tolist()] if len(site_traffic) else []

_cb_score = score   # from tab 7 the quality score
_cb_sq_label = sq_label

import json as _json

_cb_data = _json.dumps({
    "msisdn":        msisdn_value,
    "device":        device_info,
    "N":             N,
    "time_start":    time_start.strftime("%Y-%m-%d %H:%M"),
    "time_end":      time_end.strftime("%Y-%m-%d %H:%M"),
    "duration_h":    duration_h,
    "total_dl_gb":   total_dl_gb,
    "total_dl_mb":   total_dl_mb,
    "n_sites":       n_sites,
    "sites_all":     sites_all,
    "dl_avg":        dl_avg,
    "dl_max":        dl_max,
    "dl_min":        dl_min,
    "dl_median":     dl_median,
    "dl_p10":        dl_p10,
    "dl_p90":        dl_p90,
    "ul_avg":        ul_avg,
    "ul_max":        ul_max,
    "best_site":     best_site,
    "worst_site":    worst_site,
    "best_tp":       best_tp,
    "worst_tp":      worst_tp,
    "good_rows":     good_rows,
    "low_rows":      low_rows,
    "zero_rows":     zero_rows,
    "local_cnt":     local_cnt,
    "roam_cnt":      roam_cnt,
    "dl_loss_avg":   dl_loss_avg,
    "ul_loss_avg":   ul_loss_avg,
    "dl_loss_max":   dl_loss_max,
    "dl_delay_avg":  dl_delay_avg,
    "ul_delay_avg":  ul_delay_avg,
    "dl_rtt_avg":    dl_rtt_avg,
    "dl_retx_avg":   dl_retx_avg,
    "ul_retx_avg":   ul_retx_avg,
    "dl_retx_max":   dl_retx_max,
    "best_hour":     best_hour,
    "worst_hour":    worst_hour,
    "score":         _cb_score,
    "sq_label":      _cb_sq_label,
    "hourly_labels": _cb_hourly_labels,
    "hourly_vals":   _cb_hourly_vals,
    "daily_labels":  _cb_daily_labels,
    "daily_vals":    _cb_daily_vals,
    "site_labels":   _cb_site_labels,
    "site_vals":     _cb_site_vals,
    "site_traffic_labels": _cb_site_traffic_labels,
    "site_traffic_vals":   _cb_site_traffic_vals,
    "app_labels":    _cb_app_labels,
    "app_vals":      _cb_app_vals,
    "rat_labels":    _cb_rat_labels,
    "rat_vals":      _cb_rat_vals,
    "enc_pct":       enc_pct,
    "mbr_dl_avg":    mbr_dl_avg,
    "mbr_ul_avg":    mbr_ul_avg,
})

import streamlit.components.v1 as _stc

# Neutralize Streamlit iframe wrapper: zero height, no layout space, no scroll block
st.markdown("""
<style>
div[data-testid="stIFrame"] {
  overflow: visible !important;
  pointer-events: auto !important;
  margin: 0 !important;
  padding: 0 !important;
}
div[data-testid="stIFrame"] > div {
  overflow: visible !important;
  pointer-events: auto !important;
}
div[data-testid="stIFrame"] iframe {
  overflow: visible !important;
}
</style>
""", unsafe_allow_html=True)

_chat_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{font-family:'Inter',sans-serif;background:transparent;overflow:hidden;width:100%;height:100%;pointer-events:none;}}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
/* Allow pointer events only on interactive elements */
#we-chat-btn, #we-chat-panel, #we-chat-panel * {{
  pointer-events: auto !important;
}}
#we-chat-btn {{
  position:fixed;bottom:18px;right:18px;
  width:60px;height:60px;border-radius:50%;
  background:linear-gradient(135deg,#6366f1,#8b5cf6);
  border:none;cursor:pointer;z-index:10000;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 20px rgba(99,102,241,.45);
  transition:transform .18s,box-shadow .18s;
}}
#we-chat-btn:hover{{transform:scale(1.12);box-shadow:0 7px 28px rgba(99,102,241,.6)}}
#we-chat-btn svg{{width:34px;height:34px;filter:drop-shadow(0 1px 3px rgba(0,0,0,.3))}}
#we-chat-panel {{
  position:fixed;bottom:88px;right:18px;
  width:460px;max-height:78vh;
  background:#ffffff;border-radius:16px;
  border:1px solid #e2e8f0;
  box-shadow:0 12px 48px rgba(0,0,0,.14);
  display:none;flex-direction:column;
  overflow:hidden;z-index:9999;
  font-family:'Inter',sans-serif;
}}
#we-chat-panel.wcopen{{display:flex}}
#wcp-header{{
  background:linear-gradient(135deg,#6366f1,#8b5cf6);
  padding:14px 18px;display:flex;
  align-items:center;justify-content:space-between;flex-shrink:0;
}}
#wcp-header span{{color:#fff;font-weight:700;font-size:15px}}
#wcp-close{{background:none;border:none;cursor:pointer;
  color:rgba(255,255,255,.85);font-size:22px;line-height:1;padding:0}}
#wcp-qlist{{
  overflow-y:auto;padding:12px;
  flex:1;display:flex;flex-direction:column;gap:7px;
}}
.wcq-btn{{
  background:#f8fafc;border:1px solid #e2e8f0;
  border-radius:10px;padding:10px 14px;
  text-align:left;font-size:13px;
  color:#1e293b;cursor:pointer;
  display:flex;align-items:center;gap:10px;
  transition:background .15s,border-color .15s;font-family:'Inter',sans-serif;
}}
.wcq-btn:hover{{background:#f1f5f9;border-color:#c7d2fe}}
.wcq-icon{{font-size:18px;flex-shrink:0}}
#wcp-answer{{display:none;flex-direction:column;overflow:hidden;height:100%}}
#wcp-answer.wcashow{{display:flex}}
#wcp-ans-hdr{{
  padding:11px 16px;border-bottom:1px solid #e2e8f0;
  display:flex;align-items:center;gap:10px;flex-shrink:0;
}}
#wcp-back{{background:none;border:none;cursor:pointer;
  color:#6366f1;font-size:13px;font-weight:600;
  display:flex;align-items:center;gap:4px;padding:0;font-family:'Inter',sans-serif;}}
#wcp-atitle{{font-size:13px;color:#64748b;font-weight:500}}
#wcp-abody{{overflow-y:auto;padding:10px 10px 10px 10px;flex:1}}
.wc-card{{background:#f8fafc;border-radius:10px;
  border:1px solid #e2e8f0;padding:9px 12px;margin-bottom:8px}}
.wc-lbl{{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.07em;color:#64748b;margin-bottom:4px}}
.wc-val{{font-size:12px;color:#1e293b;line-height:1.5}}
.wc-grid{{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px}}
.wc-kpi{{background:#f8fafc;border:1px solid #e2e8f0;
  border-radius:8px;padding:8px 10px}}
.wc-kpi-lbl{{font-size:10px;color:#64748b;margin-bottom:3px}}
.wc-kpi-val{{font-size:15px;font-weight:700;color:#1e293b}}
.wc-bar-row{{display:flex;align-items:center;gap:7px;margin-bottom:5px}}
.wc-bar-lbl{{font-size:11px;color:#64748b;min-width:90px;max-width:90px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.wc-bar-track{{flex:1;height:7px;background:#e2e8f0;border-radius:4px;overflow:hidden}}
.wc-bar-fill{{height:100%;border-radius:4px;transition:width .5s ease}}
.wc-bar-num{{font-size:11px;color:#64748b;min-width:46px;text-align:right}}
.wc-good{{color:#16a34a}}.wc-warn{{color:#d97706}}.wc-bad{{color:#dc2626}}
.wc-score-big{{font-size:28px;font-weight:800;text-align:center;padding:4px 0}}
</style>
</head>
<body>
<button id="we-chat-btn" title="Analytics Q&A">
<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="12" y="20" width="40" height="30" rx="6" fill="white" opacity="0.95"/>
  <line x1="32" y1="20" x2="32" y2="10" stroke="white" stroke-width="3" stroke-linecap="round"/>
  <circle cx="32" cy="8" r="4" fill="white"/>
  <circle cx="22" cy="32" r="5" fill="#6366f1"/>
  <circle cx="42" cy="32" r="5" fill="#6366f1"/>
  <circle cx="23" cy="31" r="2" fill="white"/>
  <circle cx="43" cy="31" r="2" fill="white"/>
  <rect x="20" y="41" width="24" height="4" rx="2" fill="#6366f1" opacity="0.7"/>
  <rect x="22" y="41" width="4" height="4" rx="1" fill="white" opacity="0.9"/>
  <rect x="30" y="41" width="4" height="4" rx="1" fill="white" opacity="0.9"/>
  <rect x="38" y="41" width="4" height="4" rx="1" fill="white" opacity="0.9"/>
  <rect x="6" y="26" width="6" height="12" rx="3" fill="white" opacity="0.8"/>
  <rect x="52" y="26" width="6" height="12" rx="3" fill="white" opacity="0.8"/>
</svg>
</button>

<div id="we-chat-panel">
  <div id="wcp-header">
    <span>📊 Analytics Q&amp;A</span>
    <button id="wcp-close" title="Close">✕</button>
  </div>
  <div id="wcp-qlist">
    <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:.07em;padding:2px 4px 6px">Select a question</div>
    <button class="wcq-btn" data-q="overview"><span class="wcq-icon">👤</span> General Customer Info</button>
    <button class="wcq-btn" data-q="throughput"><span class="wcq-icon">⚡</span> Speed Analysis (DL / UL)</button>
    <button class="wcq-btn" data-q="sites"><span class="wcq-icon">📡</span> Site & Sector Performance</button>
    <button class="wcq-btn" data-q="apps"><span class="wcq-icon">📱</span> Most Used Applications</button>
    <button class="wcq-btn" data-q="network"><span class="wcq-icon">🌐</span> Network Type & Technology</button>
    <button class="wcq-btn" data-q="issues"><span class="wcq-icon">⚠️</span> Issues & Performance Classification</button>
    <button class="wcq-btn" data-q="timing"><span class="wcq-icon">⏰</span> Timing & Best / Worst Hours</button>
    <button class="wcq-btn" data-q="quality"><span class="wcq-icon">🔒</span> Connection Quality (Packet Loss / RTT)</button>
    <button class="wcq-btn" data-q="summary"><span class="wcq-icon">📋</span> Full Summary</button>
  </div>
  <div id="wcp-answer">
    <div id="wcp-ans-hdr">
      <button id="wcp-back">◀ Back</button>
      <span id="wcp-atitle"></span>
    </div>
    <div id="wcp-abody"></div>
  </div>
</div>

<script>
(function(){{
  const D = {_cb_data};
  const COLORS = ['#6366f1','#22c55e','#f59e0b','#ef4444','#3b82f6','#8b5cf6','#06b6d4','#ec4899','#14b8a6','#f97316'];

  // ── helpers ──
  function pct(a,b){{ return b?Math.round(a/b*100):0; }}
  function fmt(v){{ return v==null?'N/A':(typeof v==='number'?v.toFixed(2):v); }}
  function statusIcon(v){{ return v>=5?'🟢':v>=2?'🟡':'🔴'; }}
  function lossIcon(v){{  return v==null?'⚪':v<=1?'🟢':v<=3?'🟡':'🔴'; }}
  function delayIcon(v){{ return v==null?'⚪':v<=30?'🟢':v<=80?'🟡':'🔴'; }}
  function rttIcon(v){{   return v==null?'⚪':v<=30?'🟢':v<=80?'🟡':'🔴'; }}
  function retxIcon(v){{  return v==null?'⚪':v<=1?'🟢':v<=3?'🟡':'🔴'; }}

  function barChart(labels, vals, colors){{
    if(!labels||!labels.length) return '<div style="color:#94a3b8;font-size:12px">No data available</div>';
    const mx = Math.max(...vals)||1;
    return labels.map((l,i)=>{{
      const col = colors? colors[i%colors.length] : COLORS[i%COLORS.length];
      const pct2 = Math.round(vals[i]/mx*100);
      return `<div class="wc-bar-row">
        <div class="wc-bar-lbl" title="${{l}}">${{l}}</div>
        <div class="wc-bar-track"><div class="wc-bar-fill" style="width:${{pct2}}%;background:${{col}}"></div></div>
        <div class="wc-bar-num">${{typeof vals[i]==='number'?vals[i].toFixed(1):vals[i]}}</div>
      </div>`;
    }}).join('');
  }}

  function pieChart(labels, vals){{
    if(!labels||!labels.length) return '<div style="color:#94a3b8;font-size:12px">No data available</div>';
    const total = vals.reduce((s,v)=>s+v,0)||1;
    let offset=0, paths='';
    const r=52, cx=65, cy=65;
    labels.forEach((l,i)=>{{
      const frac=vals[i]/total, angle=frac*2*Math.PI;
      const x1=cx+r*Math.sin(offset), y1=cy-r*Math.cos(offset);
      offset+=angle;
      const x2=cx+r*Math.sin(offset), y2=cy-r*Math.cos(offset);
      const large=frac>.5?1:0;
      paths+=`<path d="M${{cx}},${{cy}} L${{x1.toFixed(1)}},${{y1.toFixed(1)}} A${{r}},${{r}} 0 ${{large}} 1 ${{x2.toFixed(1)}},${{y2.toFixed(1)}} Z" fill="${{COLORS[i%COLORS.length]}}"/>`;
    }});
    const legend = labels.map((l,i)=>`<div style="display:flex;align-items:center;gap:5px;font-size:11px;color:#64748b"><div style="width:9px;height:9px;border-radius:50%;background:${{COLORS[i%COLORS.length]}};flex-shrink:0"></div>${{l}} (${{Math.round(vals[i]/total*100)}}%)</div>`).join('');
    return `<div style="display:flex;flex-direction:column;align-items:center">
      <svg viewBox="0 0 130 130" style="width:130px;height:130px">
        ${{paths}}<circle cx="${{cx}}" cy="${{cy}}" r="26" fill="#ffffff"/>
      </svg>
      <div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:6px">${{legend}}</div>
    </div>`;
  }}

  function sparkLine(labels, vals, color){{
    if(!vals||!vals.length) return '';
    const W=420,H=80, mx=Math.max(...vals)||1, mn=Math.min(...vals);
    const pts=vals.map((v,i)=>{{
      const x=i/(vals.length-1||1)*W;
      const y=H-(mx===mn?H/2:(v-mn)/(mx-mn)*H);
      return x.toFixed(1)+','+y.toFixed(1);
    }}).join(' ');
    const area='M0,'+H+' '+vals.map((v,i)=>{{
      const x=i/(vals.length-1||1)*W;
      const y=H-(mx===mn?H/2:(v-mn)/(mx-mn)*H);
      return 'L'+x.toFixed(1)+','+y.toFixed(1);
    }}).join(' ')+' L'+W+','+H+' Z';
    const lbl0=labels[0]||'', lblN=labels[labels.length-1]||'';
    return `<svg viewBox="0 0 ${{W}} ${{H}}" style="width:100%;height:80px;overflow:visible">
      <path d="${{area}}" fill="${{color||'#6366f1'}}" opacity=".12"/>
      <polyline points="${{pts}}" fill="none" stroke="${{color||'#6366f1'}}" stroke-width="2" stroke-linejoin="round"/>
    </svg>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;margin-top:2px">
      <span>${{lbl0}}</span><span>${{lblN}}</span></div>`;
  }}

  function hourBar(labels, vals){{
    if(!vals||!vals.length) return '<div style="color:#94a3b8;font-size:12px">No data available</div>';
    const mx=Math.max(...vals)||1;
    const bw=Math.floor(420/vals.length)-1;
    const bars=vals.map((v,i)=>{{
      const x=i*(bw+1), h=Math.max(3,Math.round(v/mx*72)), y=76-h;
      const col=v===mx?'#22c55e':(v===Math.min(...vals)?'#ef4444':'#6366f1');
      return `<rect x="${{x}}" y="${{y}}" width="${{bw}}" height="${{h}}" fill="${{col}}" rx="2"/>`;
    }}).join('');
    const lbl0=labels[0]||'00:00', lblN=labels[labels.length-1]||'23:00';
    return `<svg viewBox="0 0 420 80" style="width:100%;height:80px">
      ${{bars}}
    </svg>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;margin-top:2px">
      <span>${{lbl0}}</span><span>${{lblN}}</span></div>
    <div style="display:flex;gap:10px;font-size:10px;margin-top:4px">
      <span style="color:#22c55e">■ Best Hour</span>
      <span style="color:#ef4444">■ Worst Hour</span>
      <span style="color:#6366f1">■ Normal</span></div>`;
  }}

  // ── answers ──
  const ANSWERS = {{
    overview: {{
      title: 'General Customer Info',
      html(){{
        const roamTotal = D.local_cnt + D.roam_cnt || 1;
        return `
        <div class="wc-grid">
          <div class="wc-kpi"><div class="wc-kpi-lbl">MSISDN</div><div class="wc-kpi-val" style="font-size:13px">${{D.msisdn}}</div></div>
          <div class="wc-kpi"><div class="wc-kpi-lbl">Total Records</div><div class="wc-kpi-val">${{D.N.toLocaleString()}}</div></div>
          <div class="wc-kpi"><div class="wc-kpi-lbl">Start Period</div><div class="wc-kpi-val" style="font-size:12px">${{D.time_start}}</div></div>
          <div class="wc-kpi"><div class="wc-kpi-lbl">End Period</div><div class="wc-kpi-val" style="font-size:12px">${{D.time_end}}</div></div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Device & Duration</div>
          <div class="wc-val">📱 <b>Device:</b> ${{D.device}}<br>⏱️ <b>Duration:</b> ${{D.duration_h}} hr</div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Total Traffic</div>
          <div class="wc-val">📦 <b>${{D.total_dl_gb}} GB</b> (${{D.total_dl_mb}} MB)<br>
          Average per record: ${{D.N?((D.total_dl_mb/D.N).toFixed(2)):0}} MB/record</div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Active Sites (${{D.n_sites}} sites)</div>
          <div class="wc-val">${{D.sites_all.map(s=>`• ${{s}}`).join('<br>')||'No sites found'}}</div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Roaming Status</div>
          <div style="display:flex;gap:10px;margin-top:6px">
            <div style="flex:1;text-align:center;padding:10px;border-radius:10px;background:#dcfce7">
              <div style="font-size:11px;color:#166534;font-weight:600">Local</div>
              <div style="font-size:15px;font-weight:700;color:#15803d">${{D.local_cnt.toLocaleString()}}</div>
              <div style="font-size:10px;color:#16a34a">${{pct(D.local_cnt,roamTotal)}}%</div>
            </div>
            <div style="flex:1;text-align:center;padding:10px;border-radius:10px;background:#fef9c3">
              <div style="font-size:11px;color:#854d0e;font-weight:600">Roaming</div>
              <div style="font-size:15px;font-weight:700;color:#d97706">${{D.roam_cnt.toLocaleString()}}</div>
              <div style="font-size:10px;color:#b45309">${{pct(D.roam_cnt,roamTotal)}}%</div>
            </div>
          </div>
        </div>`;
      }}
    }},
    throughput: {{
      title: 'Speed Analysis (DL / UL)',
      html(){{
        const dlItems=[['P10',D.dl_p10],['Min',D.dl_min],['Median',D.dl_median],['Avg',D.dl_avg],['P90',D.dl_p90],['Max',D.dl_max]];
        return `
        <div class="wc-card">
          <div class="wc-lbl">Avg DL Throughput</div>
          <div style="text-align:center;padding:8px 0">
            <div style="font-size:22px;font-weight:700;color:#6366f1">${{D.dl_avg}} <span style="font-size:12px;font-weight:500">Mbps</span></div>
            <div style="font-size:12px;color:#64748b">${{statusIcon(D.dl_avg)}} ${{D.dl_avg>=5?'Excellent':D.dl_avg>=2?'Average':'Poor'}}</div>
          </div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">DL Distribution (Mbps)</div>
          ${{barChart(dlItems.map(([l])=>l), dlItems.map(([,v])=>v))}}
        </div>
        <div class="wc-card">
          <div class="wc-lbl">UL Throughput</div>
          <div class="wc-val">⬆️ <b>Average:</b> ${{D.ul_avg}} Mbps &nbsp;|&nbsp; <b>Max:</b> ${{D.ul_max}} Mbps<br>
          ↕️ <b>DL/UL Ratio:</b> ${{D.ul_avg?(D.dl_avg/D.ul_avg).toFixed(1):'N/A'}}x</div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Best & Worst Site</div>
          <div style="display:flex;gap:8px">
            <div style="flex:1;padding:10px;border-radius:10px;background:#dcfce7;text-align:center">
              <div style="font-size:10px;color:#166534;font-weight:600">Best Site</div>
              <div style="font-size:12px;font-weight:700;color:#15803d">${{D.best_site}}</div>
              <div style="font-size:11px;color:#16a34a">${{D.best_tp}} Mbps</div>
            </div>
            <div style="flex:1;padding:10px;border-radius:10px;background:#fee2e2;text-align:center">
              <div style="font-size:10px;color:#991b1b;font-weight:600">Worst Site</div>
              <div style="font-size:12px;font-weight:700;color:#b91c1c">${{D.worst_site}}</div>
              <div style="font-size:11px;color:#dc2626">${{D.worst_tp}} Mbps</div>
            </div>
          </div>
        </div>
        ${{D.hourly_vals.length?`<div class="wc-card"><div class="wc-lbl">DL Throughout the Day (by Hour)</div>${{sparkLine(D.hourly_labels,D.hourly_vals,'#6366f1')}}</div>`:''}}
        ${{D.daily_vals.length>1?`<div class="wc-card"><div class="wc-lbl">DL Daily</div>${{sparkLine(D.daily_labels,D.daily_vals,'#8b5cf6')}}</div>`:''}}`;
      }}
    }},
    sites: {{
      title: 'Site & Sector Performance',
      html(){{
        return `
        <div class="wc-card">
          <div class="wc-lbl">Avg DL per Site (Mbps)</div>
          ${{barChart(D.site_labels, D.site_vals)}}
        </div>
        ${{D.site_traffic_labels.length?`
        <div class="wc-card">
          <div class="wc-lbl">Traffic per Site (MB)</div>
          ${{barChart(D.site_traffic_labels, D.site_traffic_vals, ['#f59e0b'])}}
        </div>`:''}}`
        + `<div class="wc-card">
          <div class="wc-lbl">Number of Sites</div>
          <div style="text-align:center;padding:8px 0">
            <div style="font-size:22px;font-weight:700;color:#6366f1">${{D.n_sites}}</div>
            <div style="font-size:12px;color:#64748b">Active site in selected period</div>
          </div>
        </div>`;
      }}
    }},
    apps: {{
      title: 'Most Used Applications',
      html(){{
        return `
        <div class="wc-card">
          <div class="wc-lbl">Usage Distribution</div>
          ${{pieChart(D.app_labels, D.app_vals)}}
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Top Applications (Session Count)</div>
          ${{barChart(D.app_labels, D.app_vals)}}
        </div>`;
      }}
    }},
    network: {{
      title: 'Network Type & Technology',
      html(){{
        const roamTotal=D.local_cnt+D.roam_cnt||1;
        return `
        <div class="wc-card">
          <div class="wc-lbl">Radio Access Type (RAT) Distribution</div>
          ${{pieChart(D.rat_labels, D.rat_vals)}}
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Local vs Roaming</div>
          ${{pieChart(['Local','Roaming'],[D.local_cnt,D.roam_cnt])}}
        </div>
        ${{D.enc_pct!=null?`<div class="wc-card"><div class="wc-lbl">Encrypted Sessions</div><div class="wc-val">🔐 ${{D.enc_pct}}% of records encrypted</div></div>`:''}}
        ${{D.mbr_dl_avg!=null?`<div class="wc-card"><div class="wc-lbl">Max Bit Rate (MBR)</div><div class="wc-val">⬇️ DL MBR Avg: ${{fmt(D.mbr_dl_avg)}} Kbps<br>⬆️ UL MBR Avg: ${{fmt(D.mbr_ul_avg)}} Kbps</div></div>`:''}}`;
      }}
    }},
    issues: {{
      title: 'Issues & Performance Classification',
      html(){{
        return `
        <div class="wc-card">
          <div class="wc-lbl">Performance Classification</div>
          ${{pieChart(
            ['Good (>1 Mbps)','Low (0-1)','Zero'],
            [D.good_rows, D.low_rows, D.zero_rows]
          )}}
        </div>
        <div class="wc-grid">
          <div class="wc-kpi" style="background:#dcfce7">
            <div class="wc-kpi-lbl">🟢 Good</div>
            <div class="wc-kpi-val" style="color:#15803d">${{D.good_rows.toLocaleString()}}</div>
            <div style="font-size:10px;color:#16a34a">${{pct(D.good_rows,D.N)}}%</div>
          </div>
          <div class="wc-kpi" style="background:#fef9c3">
            <div class="wc-kpi-lbl">🟡 Low</div>
            <div class="wc-kpi-val" style="color:#d97706">${{D.low_rows.toLocaleString()}}</div>
            <div style="font-size:10px;color:#b45309">${{pct(D.low_rows,D.N)}}%</div>
          </div>
          <div class="wc-kpi" style="background:#fee2e2">
            <div class="wc-kpi-lbl">🔴 Zero</div>
            <div class="wc-kpi-val" style="color:#dc2626">${{D.zero_rows.toLocaleString()}}</div>
            <div style="font-size:10px;color:#b91c1c">${{pct(D.zero_rows,D.N)}}%</div>
          </div>
          <div class="wc-kpi">
            <div class="wc-kpi-lbl">Total</div>
            <div class="wc-kpi-val">${{D.N.toLocaleString()}}</div>
          </div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Packet Loss</div>
          <div class="wc-val">
            ${{lossIcon(D.dl_loss_avg)}} <b>DL Avg:</b> ${{D.dl_loss_avg!=null?D.dl_loss_avg+'%':'N/A'}}<br>
            ${{lossIcon(D.ul_loss_avg)}} <b>UL Avg:</b> ${{D.ul_loss_avg!=null?D.ul_loss_avg+'%':'N/A'}}<br>
            <b>DL Max:</b> ${{D.dl_loss_max!=null?D.dl_loss_max+'%':'N/A'}}
          </div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">TCP Retransmission</div>
          <div class="wc-val">
            ${{retxIcon(D.dl_retx_avg)}} <b>DL Avg:</b> ${{D.dl_retx_avg!=null?D.dl_retx_avg+'%':'N/A'}}<br>
            ${{retxIcon(D.ul_retx_avg)}} <b>UL Avg:</b> ${{D.ul_retx_avg!=null?D.ul_retx_avg+'%':'N/A'}}<br>
            <b>DL Max:</b> ${{D.dl_retx_max!=null?D.dl_retx_max+'%':'N/A'}}
          </div>
        </div>`;
      }}
    }},
    timing: {{
      title: 'Timing & Best / Worst Hours',
      html(){{
        return `
        <div class="wc-grid">
          <div class="wc-kpi" style="background:#dcfce7">
            <div class="wc-kpi-lbl">🟢 Best Hour</div>
            <div class="wc-kpi-val" style="color:#15803d">${{D.best_hour!=null?String(D.best_hour).padStart(2,'0')+':00':'N/A'}}</div>
            <div style="font-size:10px;color:#16a34a">${{D.best_hour!=null&&D.hourly_vals.length?D.hourly_vals[D.hourly_labels.indexOf(String(D.best_hour).padStart(2,'0')+':00')]?.toFixed(1)+' Mbps':''}}</div>
          </div>
          <div class="wc-kpi" style="background:#fee2e2">
            <div class="wc-kpi-lbl">🔴 Worst Hour</div>
            <div class="wc-kpi-val" style="color:#dc2626">${{D.worst_hour!=null?String(D.worst_hour).padStart(2,'0')+':00':'N/A'}}</div>
          </div>
        </div>
        ${{D.hourly_vals.length?`
        <div class="wc-card">
          <div class="wc-lbl">⏰ DL Hourly (Bar)</div>
          ${{hourBar(D.hourly_labels, D.hourly_vals)}}
        </div>`:''}}
        ${{D.daily_vals.length>1?`
        <div class="wc-card">
          <div class="wc-lbl">📅 DL Daily</div>
          ${{sparkLine(D.daily_labels, D.daily_vals, '#8b5cf6')}}
        </div>`:''}}`;
      }}
    }},
    quality: {{
      title: 'Connection Quality (Packet Loss / RTT)',
      html(){{
        const sq = D.score;
        const sqColor = sq>=70?'#16a34a':sq>=40?'#d97706':'#dc2626';
        return `
        <div class="wc-card">
          <div class="wc-lbl">Overall Quality Score</div>
          <div style="text-align:center;padding:8px 0">
            <div class="wc-score-big" style="color:${{sqColor}}">${{sq}}<span style="font-size:18px">/100</span></div>
            <div style="font-size:14px;font-weight:600;color:${{sqColor}}">${{D.sq_label}}</div>
            <div style="height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden;margin:10px 0 4px">
              <div style="height:100%;width:${{sq}}%;background:${{sqColor}};border-radius:4px;transition:width .6s"></div>
            </div>
          </div>
        </div>
        <div class="wc-card">
          <div class="wc-lbl">Quality Indicators</div>
          ${{[
            ['DL Packet Loss', D.dl_loss_avg, '%', lossIcon(D.dl_loss_avg)],
            ['UL Packet Loss', D.ul_loss_avg, '%', lossIcon(D.ul_loss_avg)],
            ['DL Delay', D.dl_delay_avg, 'ms', delayIcon(D.dl_delay_avg)],
            ['UL Delay', D.ul_delay_avg, 'ms', delayIcon(D.ul_delay_avg)],
            ['DL RTT', D.dl_rtt_avg!=null?+(D.dl_rtt_avg/1000).toFixed(1):null, 'ms', rttIcon(D.dl_rtt_avg!=null?D.dl_rtt_avg/1000:null)],
            ['DL TCP Retx', D.dl_retx_avg, '%', retxIcon(D.dl_retx_avg)],
            ['UL TCP Retx', D.ul_retx_avg, '%', retxIcon(D.ul_retx_avg)],
          ].map(([k,v,u,ic])=>`
            <div style="display:flex;align-items:center;justify-content:space-between;padding:7px 10px;border-radius:8px;background:#f1f5f9;margin-bottom:5px">
              <span style="font-size:12px;font-weight:600;color:#334155">${{ic}} ${{k}}</span>
              <span style="font-size:13px;font-weight:700;color:#1e293b">${{v!=null?v+' '+u:'N/A'}}</span>
            </div>`).join('')}}
        </div>`;
      }}
    }},
    summary: {{
      title: 'Full Summary',
      html(){{
        const rows=[
          ['Customer', D.msisdn],
          ['Device', D.device],
          ['Period', D.time_start+' ← '+D.time_end+' ('+D.duration_h+' hr)'],
          ['Total Records', D.N.toLocaleString()],
          ['Total Traffic', D.total_dl_gb+' GB'],
          ['Number of Sites', D.n_sites],
          ['Avg DL', D.dl_avg+' Mbps (Max: '+D.dl_max+', Min: '+D.dl_min+')'],
          ['Avg UL', D.ul_avg+' Mbps'],
          ['Best Site', D.best_site+' — '+D.best_tp+' Mbps'],
          ['Worst Site', D.worst_site+' — '+D.worst_tp+' Mbps'],
          ['Good Records', D.good_rows.toLocaleString()+' ('+pct(D.good_rows,D.N)+'%)'],
          ['Low Records', D.low_rows.toLocaleString()+' ('+pct(D.low_rows,D.N)+'%)'],
          ['Zero Records', D.zero_rows.toLocaleString()+' ('+pct(D.zero_rows,D.N)+'%)'],
          ['DL Packet Loss', D.dl_loss_avg!=null?D.dl_loss_avg+'%':'N/A'],
          ['DL Delay', D.dl_delay_avg!=null?D.dl_delay_avg+' ms':'N/A'],
          ['DL RTT', D.dl_rtt_avg!=null?+(D.dl_rtt_avg/1000).toFixed(1)+' ms':'N/A'],
          ['DL TCP Retx', D.dl_retx_avg!=null?D.dl_retx_avg+'%':'N/A'],
          ['Best Hour', D.best_hour!=null?String(D.best_hour).padStart(2,'0')+':00':'N/A'],
          ['Network Quality', D.score+'/100 — '+D.sq_label],
        ];
        return `<div style="background:#f8fafc;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0">
          ${{rows.map(([l,v],i)=>`
          <div style="display:flex;gap:8px;padding:8px 12px;${{i%2===0?'':'background:#ffffff'}}">
            <div style="min-width:130px;font-size:11px;font-weight:600;color:#64748b">${{l}}</div>
            <div style="font-size:12px;color:#1e293b">${{v}}</div>
          </div>`).join('')}}
        </div>`;
      }}
    }},
  }};

  // ── DOM logic ──
  const chatBtn   = document.getElementById('we-chat-btn');
  const chatPanel = document.getElementById('we-chat-panel');
  const qList     = document.getElementById('wcp-qlist');
  const aPanel    = document.getElementById('wcp-answer');
  const aBody     = document.getElementById('wcp-abody');
  const aTitle    = document.getElementById('wcp-atitle');

  // ── Resize iframe based on panel open/closed state ──
  function resizeIframe(open) {{
    try {{
      const f = window.frameElement;
      if(!f) return;
      f.style.position      = 'fixed';
      f.style.bottom        = '0';
      f.style.right         = '0';
      f.style.border        = 'none';
      f.style.background    = 'transparent';
      f.style.zIndex        = '99999';
      f.style.pointerEvents = 'auto';
      if(open) {{
        f.style.width  = '500px';
        f.style.height = '620px';
      }} else {{
        f.style.width  = '100px';
        f.style.height = '100px';
      }}
    }} catch(e){{}}
  }}

  // Initial size — closed (just the button)
  resizeIframe(false);

  chatBtn.onclick = ()=>{{
    const isOpen = chatPanel.classList.toggle('wcopen');
    resizeIframe(isOpen);
  }};

  document.getElementById('wcp-close').onclick = ()=>{{
    chatPanel.classList.remove('wcopen');
    resizeIframe(false);
  }};

  document.getElementById('wcp-back').onclick  = ()=>{{
    aPanel.classList.remove('wcashow');
    qList.style.display='flex';
  }};

  document.querySelectorAll('.wcq-btn').forEach(btn=>{{
    btn.onclick = ()=>{{
      const key = btn.dataset.q;
      const ans = ANSWERS[key];
      if(!ans) return;
      aTitle.textContent = ans.title;
      aBody.innerHTML = ans.html();
      qList.style.display = 'none';
      aPanel.classList.add('wcashow');
    }};
  }});
}})();
</script>
</body>
</html>
"""

_stc.html(_chat_html, height=100, scrolling=False)

# ---------------------------
# EXPORT INTERACTIVE REPORT
# ---------------------------
st.markdown(f'''<div style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 12px;padding-bottom:10px;border-bottom:2px solid #e2e8f0">📤 Export Interactive Report</div>''', unsafe_allow_html=True)

if "export_html" not in st.session_state:
    st.session_state["export_html"] = None
    st.session_state["export_fname"] = None

if st.button("📤 Generate Interactive Report (HTML)", use_container_width=True):
    with st.spinner("⏳ Building report..."):
        try:
            html_content = build_export_html()
            st.session_state["export_html"] = html_content.encode("utf-8")
            st.session_state["export_fname"] = f"WE_Trace_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.html"
            st.success("✅ Report ready! Click Download below.")
        except Exception as e:
            st.session_state["export_html"] = None
            st.error(f"❌ Error: {e}")
            import traceback
            st.code(traceback.format_exc())

if st.session_state.get("export_html"):
    st.download_button(
        label="⬇️ Download Report.html",
        data=st.session_state["export_html"],
        file_name=st.session_state["export_fname"] or "WE_Trace_Report.html",
        mime="text/html",
        use_container_width=True,
        key="dl_report_btn",
    )
