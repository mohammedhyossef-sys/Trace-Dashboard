import pandas as pd
import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import st_folium

# ---------------------------
# PAGE
# ---------------------------
st.set_page_config(layout="wide")
st.title("📡 Network Performance Dashboard (Mbps)")

# ---------------------------
# UPLOAD
# ---------------------------
st.sidebar.header("📁 Upload Files")

trace_file = st.sidebar.file_uploader("Upload Trace File", type=["xlsx"])
onair_file = st.sidebar.file_uploader("Upload On-Air File", type=["xlsx"])

if trace_file is None or onair_file is None:
    st.warning("📌 Upload BOTH files")
    st.stop()

# ---------------------------
# READ
# ---------------------------
trace_df = pd.read_excel(trace_file)
on_air_df = pd.read_excel(onair_file)

trace_df.columns = trace_df.columns.str.strip()
on_air_df.columns = on_air_df.columns.str.strip()

# ---------------------------
# SITE COLUMN
# ---------------------------
cols = ["BSC/RNC/eNodeB/gNodeB Name","eNodeB Name","gNodeB Name"]
trace_col = next((c for c in cols if c in trace_df.columns), None)

if trace_col is None:
    st.error("❌ No Site Column Found")
    st.write(trace_df.columns)
    st.stop()

# ---------------------------
# SERVICE COLUMN
# ---------------------------
service_cols = ["Service Type","Service","Application","QCI"]
service_col = next((c for c in service_cols if c in trace_df.columns), None)

# ---------------------------
# CLEAN
# ---------------------------
def clean(x):
    return str(x).upper().replace(" ","").replace("-","")

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

trace_df = trace_df.dropna(subset=["Start Time","End Time"])

if trace_df.empty:
    st.error("❌ No valid time data")
    st.stop()

# ---------------------------
# DURATION
# ---------------------------
trace_df["Duration"] = (trace_df["End Time"] - trace_df["Start Time"]).dt.total_seconds()
trace_df = trace_df[trace_df["Duration"] > 0]

# ---------------------------
# AUTO TRAFFIC DETECT
# ---------------------------
traffic_col = None

for col in trace_df.columns:
    c = col.lower()
    if "downlink" in c and ("total" in c or "volume" in c):
        traffic_col = col
        break

if traffic_col is None:
    for col in trace_df.columns:
        if "dl" in col.lower():
            traffic_col = col
            break

if traffic_col is None:
    st.error("❌ No Traffic Column Found")
    st.write(trace_df.columns)
    st.stop()

# ---------------------------
# CLEAN TRAFFIC
# ---------------------------
trace_df["Traffic"] = (
    trace_df[traffic_col]
    .astype(str)
    .str.replace(",", "")
    .str.replace("MB", "")
    .str.replace("KB", "")
)

trace_df["Traffic"] = pd.to_numeric(trace_df["Traffic"], errors="coerce").fillna(0)

# Mbps
trace_df["Throughput"] = (trace_df["Traffic"] * 8) / (trace_df["Duration"] * 1_000_000)

# ---------------------------
# FILTERS
# ---------------------------
st.sidebar.header("🔎 Filters")

sites = trace_df[trace_col].dropna().unique()
selected_site = st.sidebar.selectbox("Site", ["All"] + list(sites))

# EXTRA FILTERS
extra_filters = {}
filter_cols = ["App Name", "Radio Access Type", "Roaming Status"]

for col in filter_cols:
    if col in trace_df.columns:
        values = trace_df[col].dropna().astype(str).unique()
        selected = st.sidebar.selectbox(col, ["All"] + list(values))
        extra_filters[col] = selected

# TIME FILTER
min_time = trace_df["Start Time"].min()
max_time = trace_df["Start Time"].max()

if pd.isna(min_time) or pd.isna(max_time):
    st.error("❌ Invalid time range")
    st.stop()

time_range = st.sidebar.slider(
    "Time Range",
    min_value=min_time.to_pydatetime(),
    max_value=max_time.to_pydatetime(),
    value=(min_time.to_pydatetime(), max_time.to_pydatetime())
)

# ---------------------------
# APPLY FILTERS
# ---------------------------
df = trace_df.copy()

if selected_site != "All":
    df = df[df[trace_col] == selected_site]

# APPLY EXTRA
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
# KPIs
# ---------------------------
c1, c2, c3, c4 = st.columns(4)

c1.metric("📡 Sites", df[trace_col].nunique())
c2.metric("⚡ Avg Throughput (Mbps)", round(df["Throughput"].mean(), 2))

users_count = df["IMSI"].nunique() if "IMSI" in df.columns else 0
c3.metric("👤 Users", users_count)

c4.metric("📊 Records", len(df))

# ---------------------------
# TIME SERIES
# ---------------------------
df["Time"] = df["Start Time"].dt.floor("min")
time_data = df.groupby("Time")["Throughput"].mean().reset_index()

fig_time = px.line(
    time_data,
    x="Time",
    y="Throughput",
    title="Throughput Over Time (Mbps)"
)

st.plotly_chart(fig_time, use_container_width=True)

# ---------------------------
# MAP
# ---------------------------
site_perf = df.groupby(trace_col)["Throughput"].mean().reset_index()

map_df = pd.merge(
    site_perf,
    on_air_df,
    left_on=trace_col,
    right_on="Site ID",
    how="left"
)

map_df["Latitude"] = pd.to_numeric(map_df["Latitude"], errors="coerce")
map_df["Longitude"] = pd.to_numeric(map_df["Longitude"], errors="coerce")
map_df = map_df.dropna(subset=["Latitude","Longitude"])

st.subheader("🗺️ Sites Map")

m = folium.Map(location=[30.05,31.3], zoom_start=10)

for _,row in map_df.iterrows():
    tp = row["Throughput"]

    color = "green"
    if tp < 1:
        color = "red"
    elif tp < 5:
        color = "orange"

    folium.CircleMarker(
        location=[row["Latitude"],row["Longitude"]],
        radius=6,
        color=color,
        fill=True,
        popup=f"{row['Site ID']} | {round(tp,2)} Mbps"
    ).add_to(m)

st_folium(m, width=800, height=500)

# ---------------------------
# ISSUES
# ---------------------------
st.subheader("🚨 Issues")

df["Issue"] = "Good"
df.loc[df["Throughput"] < 1, "Issue"] = "Low Throughput"
df.loc[df["Throughput"] == 0, "Issue"] = "Zero Traffic"
df.loc[df["Duration"] < 3, "Issue"] = "Drop Session"

issues = df.groupby([trace_col,"Issue"]).size().reset_index(name="Count")
st.dataframe(issues)

# ---------------------------
# TABLE
# ---------------------------
st.subheader("📋 Data Sample")
st.dataframe(df.head(100))