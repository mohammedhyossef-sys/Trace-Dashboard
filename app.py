import pandas as pd
import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import st_folium
import numpy as np

# ---------------------------
# CONFIG
# ---------------------------
plot_template = "plotly_dark"

st.set_page_config(layout="wide", page_title="Trace Dashboard")
st.title("📡 Trace Dashboard")

# ---------------------------
# UPLOAD
# ---------------------------
st.sidebar.header("📁 Upload Files")

trace_file = st.sidebar.file_uploader("Upload Trace File", type=["xlsx"])
onair_file = st.sidebar.file_uploader("Upload On-Air File", type=["xlsx"])
down_file = st.sidebar.file_uploader("Upload Down Sites File (Optional)", type=["xlsx"])
planned_file = st.sidebar.file_uploader("Upload Planned Sites File (Optional)", type=["xlsx"])
if trace_file is None or onair_file is None:
    st.warning("📌 Upload BOTH files")
    st.stop()

# ---------------------------
# READ MSISDN FROM USER PLAN (C8)
# ---------------------------
try:
    user_plan_df = pd.read_excel(trace_file, sheet_name=0, header=None)
    msisdn_value = user_plan_df.iloc[7, 2]
except:
    msisdn_value = "N/A"

# ---------------------------
# READ DATA
# ---------------------------
trace_df = pd.read_excel(trace_file, sheet_name=1)
on_air_df = pd.read_excel(onair_file)

trace_df.columns = trace_df.columns.str.strip()
on_air_df.columns = on_air_df.columns.str.strip()

# ---------------------------
# SITE COLUMN
# ---------------------------
cols = ["BSC/RNC/eNodeB/gNodeB Name", "eNodeB Name", "gNodeB Name"]
trace_col = next((c for c in cols if c in trace_df.columns), None)

if trace_col is None:
    st.error("❌ No Site Column Found")
    st.stop()

# ---------------------------
# CLEAN
# ---------------------------
def clean(x):
    return str(x).upper().replace(" ", "").replace("-", "")

trace_df[trace_col] = trace_df[trace_col].apply(clean)
on_air_df["Site ID"] = on_air_df["Site ID"].apply(clean)

# ---------------------------
# TIME
# ---------------------------
trace_df["Start Time"] = pd.to_datetime(
    trace_df["Start Time"].astype(str).str.replace(r"\(.*\)", "", regex=True),
    errors="coerce"
)

trace_df["End Time"] = pd.to_datetime(
    trace_df["End Time"].astype(str).str.replace(r"\(.*\)", "", regex=True),
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
    if "downlink" in col.lower():
        traffic_col = col
        break

if traffic_col is None:
    st.error("❌ No Traffic Column Found")
    st.stop()

# ---------------------------
# CONVERT TRAFFIC TO MB
# ---------------------------
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

trace_df["Traffic_MB"] = trace_df[traffic_col].apply(convert_to_mb)

# ---------------------------
# THROUGHPUT
# ---------------------------
trace_df["Throughput"] = (trace_df["Traffic_MB"] * 8) / trace_df["Duration"]

# ---------------------------
# FILTERS
# ---------------------------
st.sidebar.header("🔎 Filters")

if "IMSI" in trace_df.columns:
    imsi_list = trace_df["IMSI"].dropna().astype(str).unique()
    selected_imsi = st.sidebar.multiselect("👤 Select Users (IMSI)", imsi_list, default=[])
else:
    selected_imsi = []

if "Service Type" in trace_df.columns:
    service_types = sorted(trace_df["Service Type"].dropna().astype(str).unique())
    selected_service = st.sidebar.multiselect("📶 Service Type", service_types, default=[])
else:
    selected_service = []

sites = trace_df[trace_col].unique()
selected_site = st.sidebar.selectbox("📡 Site", ["All"] + list(sites))

extra_filters = {}
filter_cols = ["App Name", "Radio Access Type", "Roaming Status"]

for col in filter_cols:
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

# ---------------------------
# USER LOCATION INPUT (NEW)
# ---------------------------
st.sidebar.header("📍 User Location (Optional)")

user_lat = st.sidebar.text_input("Latitude")
user_lon = st.sidebar.text_input("Longitude")

user_location = None

try:
    if user_lat and user_lon:
        user_location = (float(user_lat), float(user_lon))
except:
    user_location = None

# ---------------------------
# APPLY FILTERS
# ---------------------------
df = trace_df.copy()

if selected_site != "All":
    df = df[df[trace_col] == selected_site]

if selected_imsi:
    df = df[df["IMSI"].astype(str).isin(selected_imsi)]

if selected_service:
    df = df[df["Service Type"].astype(str).isin(selected_service)]

for col, val in extra_filters.items():
    if val != "All":
        df = df[df[col].astype(str) == val]

df = df[
    (df["Start Time"] >= time_range[0]) &
    (df["Start Time"] <= time_range[1])
]

if df.empty:
    st.warning("⚠️ No data after filters → showing all data")
    df = trace_df.copy()

# ---------------------------
# DEVICE INFO (RESTORED)
# ---------------------------
device_info = "N/A"

if "Device Brand" in df.columns and "Device Model" in df.columns:
    devices = (
        df["Device Brand"].astype(str).fillna("") + " " +
        df["Device Model"].astype(str).fillna("")
    )
    device_info = ", ".join(devices.dropna().unique()[:5])

# ---------------------------
# KPI
# ---------------------------
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("📡 Sites", df[trace_col].nunique())
c2.metric("⚡ Avg Throughput (Mbps)", round(df["Throughput"].mean(), 2))
c3.metric("👤 Users", df["IMSI"].nunique() if "IMSI" in df.columns else 0, delta=f"MSISDN: {msisdn_value}")
c4.metric("📱 Devices", device_info)
c5.metric("📊 Records", len(df))

# ---------------------------
# TIME SERIES
# ---------------------------
df["Time"] = df["Start Time"].dt.floor("min")
time_data = df.groupby("Time")["Throughput"].mean().reset_index()

st.plotly_chart(
    px.line(time_data, x="Time", y="Throughput", title="Throughput Over Time"),
    use_container_width=True
)

# ---------------------------
# HOURLY
# ---------------------------
st.subheader("📈 Hourly Average Throughput")

df["Time_Hour"] = df["Start Time"].dt.floor("h")
hourly_data = df.groupby("Time_Hour")["Throughput"].mean().reset_index()

st.plotly_chart(
    px.line(hourly_data, x="Time_Hour", y="Throughput"),
    use_container_width=True
)

# ---------------------------
# NETWORK COMPARISON (FIXED)
# ---------------------------
st.subheader("📊 Network Performance Comparison")

net_col = next((c for c in ["Roaming Status", "Network Type", "Service Provider"] if c in df.columns), None)

if net_col:
    df["Network"] = df[net_col].astype(str).str.upper()

    dl_col = "Downlink Throughput (Kbps)"
    ul_col = "Uplink Throughput (Kbps)"

    df[dl_col] = pd.to_numeric(df[dl_col], errors="coerce") / 1000
    df[ul_col] = pd.to_numeric(df[ul_col], errors="coerce") / 1000

    comparison = df.groupby("Network").agg(
        Avg_DL=(dl_col, "mean"),
        Median_DL=(dl_col, "median"),
        Avg_UL=(ul_col, "mean"),
        Median_UL=(ul_col, "median"),
        Records=("Throughput", "count")
    ).reset_index()

    st.dataframe(comparison)

    fig2 = px.bar(comparison, x="Network", y="Avg_DL", template=plot_template)
    st.plotly_chart(fig2, use_container_width=True)

    best = comparison.sort_values("Avg_DL", ascending=False).iloc[0]
    st.success(f"🏆 Best Network = {best['Network']}")
else:
    st.warning("⚠️ No network column found")

# ---------------------------
# PLANNED SITES (SAFE ADDITION - NO BREAKING)
# ---------------------------
planned_df = None

if planned_file is not None:
    try:
        planned_df = pd.read_excel(planned_file)
        planned_df.columns = planned_df.columns.str.strip()

        def clean(x):
            return str(x).upper().replace(" ", "").replace("-", "")

        # Clean Site ID if exists
        if "Site ID" in planned_df.columns:
            planned_df["Site ID"] = planned_df["Site ID"].apply(clean)

        # 🔴 SAFE detection (no KeyError)
        lat_col = next((c for c in planned_df.columns if "lat" in c.lower()), None)
        lon_col = next((c for c in planned_df.columns if "lon" in c.lower()), None)

        if lat_col is not None and lon_col is not None:
            planned_df["Latitude"] = pd.to_numeric(planned_df[lat_col], errors="coerce")
            planned_df["Longitude"] = pd.to_numeric(planned_df[lon_col], errors="coerce")

            planned_df = planned_df.dropna(subset=["Latitude", "Longitude"])
        else:
            planned_df = None

    except:
        planned_df = None


# ---------------------------
# MAP
# ---------------------------
st.subheader("🗺️ Sites Map")

site_perf = df.groupby(trace_col)["Throughput"].mean().reset_index()

map_df = pd.merge(site_perf, on_air_df, left_on=trace_col, right_on="Site ID", how="left")

map_df["Latitude"] = pd.to_numeric(map_df["Latitude"], errors="coerce")
map_df["Longitude"] = pd.to_numeric(map_df["Longitude"], errors="coerce")
map_df = map_df.dropna()

m = folium.Map(location=[30.05, 31.3], zoom_start=10)

for _, row in map_df.iterrows():
    color = "red" if row["Throughput"] < 1 else "green"

    folium.Marker(
        [row["Latitude"], row["Longitude"]],
        popup=row["Site ID"],
        icon=folium.Icon(color=color)
    ).add_to(m)
# ---------------------------
# USER LOCATION ON MAP
# ---------------------------
if user_location is not None:
    folium.Marker(
        user_location,
        popup="👤 User Location",
        icon=folium.Icon(color="purple", icon="user")
    ).add_to(m)

    # optional circle around user
    folium.Circle(
        location=user_location,
        radius=500,  # بالمتر
        color="purple",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)
# Planned Sites layer (blue circles) - ONLY NEAR ACTIVE SITES
if planned_df is not None:

    def distance(lat1, lon1, lat2, lon2):
        return np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

    for _, p in planned_df.iterrows():

        for _, a in map_df.iterrows():

            if pd.isna(a["Latitude"]) or pd.isna(a["Longitude"]):
                continue

            dist = distance(
                p["Latitude"], p["Longitude"],
                a["Latitude"], a["Longitude"]
            )

            # 👇 threshold بسيط للقرب
            if dist < 0.05:

                folium.CircleMarker(
                    [p["Latitude"], p["Longitude"]],
                    radius=6,
                    color="blue",
                    fill=True,
                    fill_opacity=0.6,
                    popup=f"PLANNED: {p['Site ID']}"
                ).add_to(m)

                break
# ---------------------------
# NEARBY ALERT
# ---------------------------
st.subheader("🚨 Nearby Impact Alert")

def distance(lat1, lon1, lat2, lon2):
    return np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

down_sites = site_perf[site_perf["Throughput"] < 1].merge(
    on_air_df, left_on=trace_col, right_on="Site ID", how="left"
)

down_sites["Latitude"] = pd.to_numeric(down_sites["Latitude"], errors="coerce")
down_sites["Longitude"] = pd.to_numeric(down_sites["Longitude"], errors="coerce")
down_sites = down_sites.dropna()

alerts = []

for _, d in down_sites.iterrows():
    for _, s in on_air_df.iterrows():

        if d["Site ID"] == s["Site ID"]:
            continue

        if pd.isna(s["Latitude"]) or pd.isna(s["Longitude"]):
            continue

        dist = distance(d["Latitude"], d["Longitude"], s["Latitude"], s["Longitude"])

        if dist < 0.02:
            alerts.append({
                "Down Site": d["Site ID"],
                "Nearby Site": s["Site ID"],
                "Distance": round(dist, 4)
            })

if alerts:
    st.dataframe(pd.DataFrame(alerts))
else:
    st.success("No nearby impacted sites")

st_folium(m, width=800, height=500)

# ---------------------------
# ISSUES
# ---------------------------
st.subheader("🚨 Issues")

df["Issue"] = "Good"
df.loc[df["Throughput"] < 1, "Issue"] = "Low Throughput"
df.loc[df["Throughput"] == 0, "Issue"] = "Zero Traffic"

st.dataframe(df.groupby([trace_col, "Issue"]).size().reset_index(name="Count"))

# ---------------------------
# SAMPLE
# ---------------------------
st.subheader("📋 Sample Data")
st.dataframe(df.head(100))
