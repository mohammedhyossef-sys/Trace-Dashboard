import pandas as pd
import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import st_folium
import numpy as np
import math

# ---------------------------
# CONFIG
# ---------------------------
plot_template = "plotly_dark"

st.set_page_config(layout="wide", page_title="WE Trace Dashboard")
st.title("📡 WE Trace Dashboard")

# ---------------------------
# FUNCTIONS
# ---------------------------
def clean(x):
    return str(x).upper().replace(" ", "").replace("-", "")

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

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * R * math.asin(math.sqrt(a))

# ---------------------------
# UPLOAD
# ---------------------------
st.sidebar.header("📁 Upload Files")

trace_file = st.sidebar.file_uploader(
    "Upload Trace File",
    type=["xlsx"]
)

onair_file = st.sidebar.file_uploader(
    "Upload On-Air File",
    type=["xlsx"]
)

down_file = st.sidebar.file_uploader(
    "Upload Down Sites File",
    type=["xlsx"]
)

planned_file = st.sidebar.file_uploader(
    "Upload Planned Sites File (Optional)",
    type=["xlsx"]
)

if trace_file is None or onair_file is None:
    st.warning("📌 Upload BOTH files")
    st.stop()

# ---------------------------
# READ MSISDN
# ---------------------------
try:

    user_plan_df = pd.read_excel(
        trace_file,
        sheet_name=0,
        header=None
    )

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
# SAFE LAT/LON FIX
# ---------------------------
lat_col = next(
    (c for c in on_air_df.columns if "lat" in c.lower()),
    None
)

lon_col = next(
    (c for c in on_air_df.columns if "lon" in c.lower()),
    None
)

if lat_col and lon_col:

    on_air_df["Latitude"] = pd.to_numeric(
        on_air_df[lat_col].apply(clean_coord),
        errors="coerce"
    )

    on_air_df["Longitude"] = pd.to_numeric(
        on_air_df[lon_col].apply(clean_coord),
        errors="coerce"
    )

    on_air_df = on_air_df.dropna(
        subset=["Latitude", "Longitude"]
    )

else:
    st.error("❌ Latitude/Longitude not found")
    st.stop()

# ---------------------------
# CLEAN SITE IDS
# ---------------------------
on_air_df["Site ID"] = on_air_df["Site ID"].apply(clean)

# ---------------------------
# DOWN FILE
# ---------------------------
down_df = None

if down_file is not None:

    down_df = pd.read_excel(down_file)

    down_df.columns = down_df.columns.str.strip()

    if "Site ID" in down_df.columns:

        down_df["Site ID"] = down_df["Site ID"].apply(clean)

        # get geo from on air
        down_geo = on_air_df[
            ["Site ID", "Latitude", "Longitude"]
        ].copy()

        down_df = down_df.merge(
            down_geo,
            on="Site ID",
            how="left"
        )

        down_df = down_df.dropna(
            subset=["Latitude", "Longitude"]
        )

# ---------------------------
# PLANNED FILE
# ---------------------------
planned_df = None

if planned_file is not None:

    try:

        planned_df = pd.read_excel(planned_file)

        planned_df.columns = (
            planned_df.columns.str.strip()
        )

        if "Site ID" in planned_df.columns:

            planned_df["Site ID"] = planned_df[
                "Site ID"
            ].apply(clean)

        p_lat_col = next(
            (
                c for c in planned_df.columns
                if "lat" in c.lower()
            ),
            None
        )

        p_lon_col = next(
            (
                c for c in planned_df.columns
                if "lon" in c.lower()
            ),
            None
        )

        if p_lat_col and p_lon_col:

            planned_df["Latitude"] = pd.to_numeric(
                planned_df[p_lat_col],
                errors="coerce"
            )

            planned_df["Longitude"] = pd.to_numeric(
                planned_df[p_lon_col],
                errors="coerce"
            )

            planned_df = planned_df.dropna(
                subset=["Latitude", "Longitude"]
            )

        else:
            planned_df = None

    except:
        planned_df = None

# ---------------------------
# SITE COLUMN
# ---------------------------
cols = [
    "BSC/RNC/eNodeB/gNodeB Name",
    "eNodeB Name",
    "gNodeB Name"
]

trace_col = next(
    (c for c in cols if c in trace_df.columns),
    None
)

if trace_col is None:
    st.error("❌ No Site Column Found")
    st.stop()

# ---------------------------
# CLEAN TRACE
# ---------------------------
trace_df[trace_col] = trace_df[
    trace_col
].apply(clean)

# ---------------------------
# TIME
# ---------------------------
trace_df["Start Time"] = pd.to_datetime(
    trace_df["Start Time"]
    .astype(str)
    .str.replace(r"\(.*\)", "", regex=True),
    errors="coerce"
)

trace_df["End Time"] = pd.to_datetime(
    trace_df["End Time"]
    .astype(str)
    .str.replace(r"\(.*\)", "", regex=True),
    errors="coerce"
)

trace_df = trace_df.dropna(
    subset=["Start Time", "End Time"]
)

if trace_df.empty:
    st.error("❌ No valid time data")
    st.stop()

# ---------------------------
# DURATION
# ---------------------------
trace_df["Duration"] = (
    trace_df["End Time"]
    - trace_df["Start Time"]
).dt.total_seconds()

trace_df = trace_df[
    trace_df["Duration"] > 0
]

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
# THROUGHPUT
# ---------------------------
trace_df["Traffic_MB"] = trace_df[
    traffic_col
].apply(convert_to_mb)

trace_df["Throughput"] = (
    trace_df["Traffic_MB"] * 8
) / trace_df["Duration"]

# ---------------------------
# FILTERS
# ---------------------------
st.sidebar.header("🔎 Filters")

if "IMSI" in trace_df.columns:

    imsi_list = (
        trace_df["IMSI"]
        .dropna()
        .astype(str)
        .unique()
    )

    selected_imsi = st.sidebar.multiselect(
        "👤 Select Users (IMSI)",
        imsi_list,
        default=[]
    )

else:
    selected_imsi = []

if "Service Type" in trace_df.columns:

    service_types = sorted(
        trace_df["Service Type"]
        .dropna()
        .astype(str)
        .unique()
    )

    selected_service = st.sidebar.multiselect(
        "📶 Service Type",
        service_types,
        default=[]
    )

else:
    selected_service = []

sites = trace_df[trace_col].unique()

selected_site = st.sidebar.selectbox(
    "📡 Site",
    ["All"] + list(sites)
)

# ---------------------------
# EXTRA FILTERS
# ---------------------------
extra_filters = {}

filter_cols = [
    "App Name",
    "Radio Access Type",
    "Roaming Status"
]

for col in filter_cols:

    if col in trace_df.columns:

        values = (
            trace_df[col]
            .dropna()
            .astype(str)
            .unique()
        )

        extra_filters[col] = st.sidebar.selectbox(
            col,
            ["All"] + list(values)
        )

# ---------------------------
# TIME FILTER
# ---------------------------
min_time = trace_df["Start Time"].min()
max_time = trace_df["Start Time"].max()

time_range = st.sidebar.slider(
    "Time Range",
    min_value=min_time.to_pydatetime(),
    max_value=max_time.to_pydatetime(),
    value=(
        min_time.to_pydatetime(),
        max_time.to_pydatetime()
    )
)

# ---------------------------
# USER LOCATION
# ---------------------------
st.sidebar.header("📍 User Location (Optional)")

user_lat = st.sidebar.text_input("Latitude")
user_lon = st.sidebar.text_input("Longitude")

user_location = None

try:

    if user_lat and user_lon:
        user_location = (
            float(user_lat),
            float(user_lon)
        )

except:
    user_location = None

# ---------------------------
# APPLY FILTERS
# ---------------------------
df = trace_df.copy()

if selected_site != "All":
    df = df[df[trace_col] == selected_site]

if selected_imsi:
    df = df[
        df["IMSI"].astype(str).isin(selected_imsi)
    ]

if selected_service:
    df = df[
        df["Service Type"]
        .astype(str)
        .isin(selected_service)
    ]

for col, val in extra_filters.items():

    if val != "All":
        df = df[df[col].astype(str) == val]

df = df[
    (df["Start Time"] >= time_range[0])
    &
    (df["Start Time"] <= time_range[1])
]

if df.empty:
    st.warning("⚠️ No data after filters")
    df = trace_df.copy()

# ---------------------------
# DEVICE INFO
# ---------------------------
device_info = "N/A"

if (
    "Device Brand" in df.columns
    and
    "Device Model" in df.columns
):

    devices = (
        df["Device Brand"]
        .astype(str)
        .fillna("")
        +
        " "
        +
        df["Device Model"]
        .astype(str)
        .fillna("")
    )

    device_info = ", ".join(
        devices.dropna().unique()[:5]
    )

# ---------------------------
# KPI
# ---------------------------
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "📡 Sites",
    df[trace_col].nunique()
)

c2.metric(
    "⚡ Avg Throughput (Mbps)",
    round(df["Throughput"].mean(), 2)
)

c3.metric(
    "👤 Users",
    df["IMSI"].nunique()
    if "IMSI" in df.columns else 0,
    delta=f"MSISDN: {msisdn_value}"
)

c4.metric(
    "📱 Devices",
    device_info
)

c5.metric(
    "📊 Records",
    len(df)
)

# ---------------------------
# TIME SERIES
# ---------------------------
df["Time"] = df["Start Time"].dt.floor("min")

time_data = (
    df.groupby("Time")["Throughput"]
    .mean()
    .reset_index()
)

fig = px.line(
    time_data,
    x="Time",
    y="Throughput",
    title="📈 Throughput Over Time",
    template="plotly_dark"
)

fig.update_traces(
    mode="lines",
    line=dict(
        width=3,
        color="purple"
    )
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# ---------------------------
# HOURLY
# ---------------------------
st.subheader("📈 Hourly Average Throughput")

df["Time_Hour"] = (
    df["Start Time"].dt.floor("h")
)

hourly_data = (
    df.groupby("Time_Hour")["Throughput"]
    .mean()
    .reset_index()
)

fig2 = px.line(
    hourly_data,
    x="Time_Hour",
    y="Throughput",
    title="📊 Hourly Average Throughput",
    template="plotly_dark"
)

fig2.update_traces(
    mode="lines+markers",
    line=dict(
        width=3,
        color="purple"
    ),
    marker=dict(
        size=6,
        color="purple"
    )
)

st.plotly_chart(
    fig2,
    use_container_width=True
)

# ---------------------------
# NETWORK COMPARISON
# ---------------------------
st.subheader("📊 Network Performance Comparison")

net_col = next(
    (
        c for c in [
            "Roaming Status",
            "Network Type",
            "Service Provider"
        ]
        if c in df.columns
    ),
    None
)

if net_col:

    # ---------------------------
    # NORMALIZE NETWORK NAME
    # ---------------------------
    df["Network"] = (
        df[net_col]
        .astype(str)
        .str.upper()
    )

    dl_col = "Downlink Throughput (Kbps)"
    ul_col = "Uplink Throughput (Kbps)"

    df[dl_col] = pd.to_numeric(df[dl_col], errors="coerce") / 1000
    df[ul_col] = pd.to_numeric(df[ul_col], errors="coerce") / 1000

    # ---------------------------
    # GROUPING
    # ---------------------------
    comparison = (
        df.groupby("Network")
        .agg(
            Avg_DL=(dl_col, "mean"),
            Median_DL=(dl_col, "median"),
            Avg_UL=(ul_col, "mean"),
            Median_UL=(ul_col, "median"),
            Records=("Throughput", "count")
        )
        .reset_index()
    )

    # ---------------------------
    # CLASSIFY LOCAL / ROAMING
    # ---------------------------
    def classify_network(row):
        if "Roaming Status" in df.columns:
            val = str(row.get("Roaming Status", "")).upper()
            if val == "ROAMING":
                return "Roaming"
        return "Local"

    comparison["Category"] = df.groupby(net_col).first().reset_index().apply(
        lambda row: classify_network(row),
        axis=1
    )

    # ---------------------------
    # COLORS
    # ---------------------------
    color_map = {
        "Local": "#8e44ad",   # 🟣 موف
        "Roaming": "orange"   # 🟠 برتقالي
    }

    # ---------------------------
    # CHART
    # ---------------------------
  

    fig3 = px.bar(
        comparison,
        x="Network",
        y="Avg_DL",
        text_auto=".2f",
        template=plot_template,
        color="Category",
        color_discrete_map=color_map
    )

    fig3.update_layout(
        xaxis_title="Network Type",
        yaxis_title="Avg Downlink (Mbps)",
        title="",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        bargap=0.4,
        legend_title_text="Connection Type",
        font=dict(size=13)
    )

    fig3.update_traces(
        textposition="outside",
        marker_line_width=0
    )

    st.plotly_chart(fig3, use_container_width=True)

    # ---------------------------
    # TABLE (BOTTOM)
    # ---------------------------
    st.markdown("### 📋 Detailed Network Statistics")

    st.dataframe(
        comparison.style.format({
            "Avg_DL": "{:.2f}",
            "Median_DL": "{:.2f}",
            "Avg_UL": "{:.2f}",
            "Median_UL": "{:.2f}"
        }),
        use_container_width=True
    )
# ---------------------------
# MAP
# ---------------------------
st.subheader("🗺️ Sites Map")

site_perf = (
    df.groupby(trace_col)["Throughput"]
    .mean()
    .reset_index()
)

map_df = pd.merge(
    site_perf,
    on_air_df,
    left_on=trace_col,
    right_on="Site ID",
    how="left"
)

map_df["Latitude"] = pd.to_numeric(
    map_df["Latitude"],
    errors="coerce"
)

map_df["Longitude"] = pd.to_numeric(
    map_df["Longitude"],
    errors="coerce"
)

map_df = map_df.dropna()

map_df = map_df.drop_duplicates(
    subset=["Site ID"]
)

m = folium.Map(
    location=[30.05, 31.3],
    zoom_start=10
)

# ---------------------------
# ACTIVE SITES
# ---------------------------
for _, row in map_df.iterrows():

    color = (
        "red"
        if row["Throughput"] < 1
        else "green"
    )

    folium.Marker(
        [row["Latitude"], row["Longitude"]],
        popup=f"{row['Site ID']} | Throughput: {round(row['Throughput'],2)}",
        icon=folium.Icon(color=color)
    ).add_to(m)

# ---------------------------
# USER LOCATION
# ---------------------------
if user_location is not None:

    folium.Marker(
        user_location,
        popup="👤 User Location",
        icon=folium.Icon(
            color="purple",
            icon="user"
        )
    ).add_to(m)

    folium.Circle(
        location=user_location,
        radius=500,
        color="purple",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)

# ---------------------------
# PLANNED SITES
# ---------------------------
if planned_df is not None:

    shown_sites = set()

    for _, p in planned_df.iterrows():

        if p["Site ID"] in shown_sites:
            continue

        for _, a in map_df.iterrows():

            dist = haversine(
                p["Latitude"],
                p["Longitude"],
                a["Latitude"],
                a["Longitude"]
            )

            # only near serving sites
            if dist <= 2:

                folium.CircleMarker(
                    [p["Latitude"], p["Longitude"]],
                    radius=6,
                    color="blue",
                    fill=True,
                    fill_opacity=0.6,
                    popup=f"PLANNED: {p['Site ID']}"
                ).add_to(m)

                shown_sites.add(
                    p["Site ID"]
                )

                break

# ---------------------------
# DOWN SITES IMPACT
# ---------------------------
st.subheader("🚨 Down Sites Impact Analysis")

alerts = []

if down_df is not None:

    shown_down = set()

    for _, down in down_df.iterrows():

        if down["Site ID"] in shown_down:
            continue

        for _, serving in map_df.iterrows():

            if (
                down["Site ID"]
                ==
                serving["Site ID"]
            ):
                continue

            dist = haversine(
                down["Latitude"],
                down["Longitude"],
                serving["Latitude"],
                serving["Longitude"]
            )

            # only nearby serving sites
            if dist <= 2:

                alerts.append({
                    "Down Site": down["Site ID"],
                    "Serving Site": serving["Site ID"],
                    "Distance (KM)": round(dist, 2)
                })

                # map marker
                folium.CircleMarker(
                    [down["Latitude"], down["Longitude"]],
                    radius=9,
                    color="red",
                    fill=True,
                    fill_color="red",
                    fill_opacity=0.7,
                    popup=f"DOWN SITE: {down['Site ID']}"
                ).add_to(m)

                shown_down.add(
                    down["Site ID"]
                )

                break

if alerts:

    df_alerts = (
        pd.DataFrame(alerts)
        .drop_duplicates()
        .sort_values("Distance (KM)")
    )

    st.dataframe(
        df_alerts,
        use_container_width=True
    )

else:
    st.success(
        "✅ No impacted serving sites near down sites"
    )

# ---------------------------
# SHOW MAP
# ---------------------------
st_folium(
    m,
    width=1200,
    height=600
)

# ---------------------------
# ISSUES
# ---------------------------
st.subheader("🚨 Issues")

df["Issue"] = "Good"

df.loc[
    df["Throughput"] < 1,
    "Issue"
] = "Low Throughput"

df.loc[
    df["Throughput"] == 0,
    "Issue"
] = "Zero Traffic"

issues_df = (
    df.groupby([trace_col, "Issue"])
    .size()
    .reset_index(name="Count")
)

st.dataframe(
    issues_df,
    use_container_width=True
)

# ---------------------------
# SAMPLE DATA
# ---------------------------
st.subheader("📋 Sample Data")

st.dataframe(
    df.head(100),
    use_container_width=True
)
