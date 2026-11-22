
import streamlit as st
import pandas as pd
from datetime import time

from engine.scheduler import schedule_orders


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="KitchenPulse | Operations Control Tower",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🍳 KitchenPulse")
st.caption("Cloud Kitchen Operations Control Tower")

st.info(
    "Simulation environment | Synthetic orders and kitchen data. "
    "Scheduling policies and customer-impact weights are illustrative."
)


# ============================================================
# 2. CONFIGURATION
# ============================================================

stations = {
    "A": {
        "brands": ["Behrouz", "Oven Story"],
        "available_at": "12:00"
    },
    "B": {
        "brands": ["Faasos", "Oven Story"],
        "available_at": "12:05"
    },
    "C": {
        "brands": ["Faasos", "Behrouz", "Oven Story"],
        "available_at": "12:12"
    }
}

strategy_options = {
    "On-time first": "on_time_first",
    "Penalty first": "penalty_first",
    "Balanced": "balanced"
}


# ============================================================
# 3. SIDEBAR CONTROLS
# ============================================================

st.sidebar.title("Simulation Controls")

selected_strategy = st.sidebar.selectbox(
    "Scheduling policy",
    options=list(strategy_options.keys()),
    index=2
)

current_time = st.sidebar.time_input(
    "Simulated current time",
    value=time(12, 20)
)

st.sidebar.divider()

st.sidebar.caption("Kitchen configuration")

for station, details in stations.items():
    st.sidebar.markdown(f"**Station {station}**")
    st.sidebar.caption(
        "Compatible brands: " + ", ".join(details["brands"])
    )

st.sidebar.divider()

st.sidebar.caption(
    "Changing the simulation controls recalculates "
    "the kitchen schedule."
)


# ============================================================
# 4. LOAD DATA
# ============================================================

@st.cache_data
def load_orders():
    return pd.read_csv("data/orders.csv")


try:
    orders = load_orders()

except FileNotFoundError:
    st.error("Could not find data/orders.csv.")
    st.stop()


required_columns = [
    "order_id",
    "brand",
    "aggregator",
    "prep_time",
    "order_time",
    "committed_time",
    "status",
    "station",
    "prep_started_at"
]

missing_columns = [
    column for column in required_columns
    if column not in orders.columns
]

if missing_columns:
    st.error(f"Missing CSV columns: {missing_columns}")
    st.stop()


# ============================================================
# 5. RUN SCHEDULER
# ============================================================

try:
    schedule_results = schedule_orders(
        orders.to_dict("records"),
        stations,
        current_time=current_time,
        strategy=strategy_options[selected_strategy]
    )

except Exception as error:
    st.error(f"Scheduler error: {error}")
    st.stop()


schedule_df = pd.DataFrame(schedule_results)


# ============================================================
# 6. KPI CALCULATIONS
# ============================================================

total_orders = len(schedule_df)

on_time_orders = (
    schedule_df["Status"] == "On Time"
).sum()

late_orders = (
    schedule_df["Status"] == "Late"
).sum()

ready_orders = (
    schedule_df["Order State"] == "Ready"
).sum()

preparing_orders = (
    schedule_df["Order State"] == "Preparing"
).sum()

queued_orders = (
    schedule_df["Order State"] == "Queued"
).sum()

unassigned_orders = (
    schedule_df["Station"] == "Unassigned"
).sum()

total_delay = schedule_df["Delay"].fillna(0).sum()

total_penalty = schedule_df["Penalty"].fillna(0).sum()

non_ready_orders = total_orders - ready_orders

on_time_rate = (
    on_time_orders / non_ready_orders * 100
    if non_ready_orders > 0 else 0
)

max_delay = schedule_df["Delay"].fillna(0).max()


# ============================================================
# 7. ORDER PERFORMANCE
# ============================================================

st.subheader("Order Performance")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Orders",
    total_orders
)

col2.metric(
    "On-time Orders",
    on_time_orders,
    f"{on_time_rate:.1f}% of non-ready orders"
)

col3.metric(
    "Late Orders",
    late_orders
)

col4.metric(
    "Unassigned Orders",
    unassigned_orders
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Queued", queued_orders)
col2.metric("Preparing", preparing_orders)
col3.metric("Ready", ready_orders)
col4.metric("Total Delay", f"{total_delay:.0f} min")


# ============================================================
# 8. ORDER CONTROL CENTRE
# ============================================================

st.divider()
st.subheader("📦 Order Control Centre")

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    brand_filter = st.multiselect(
        "Brand",
        options=sorted(orders["brand"].dropna().unique())
    )

with filter_col2:
    aggregator_filter = st.multiselect(
        "Aggregator",
        options=sorted(orders["aggregator"].dropna().unique())
    )

with filter_col3:
    status_filter = st.multiselect(
        "Order status",
        options=sorted(schedule_df["Status"].dropna().unique())
    )

filtered_df = schedule_df.copy()

if brand_filter:
    filtered_df = filtered_df[
        filtered_df["brand"].isin(brand_filter)
    ]

if aggregator_filter:
    filtered_df = filtered_df[
        filtered_df["aggregator"].isin(aggregator_filter)
    ]

if status_filter:
    filtered_df = filtered_df[
        filtered_df["Status"].isin(status_filter)
    ]

st.dataframe(
    filtered_df,
    use_container_width=True,
    hide_index=True
)

st.caption(
    f"Showing {len(filtered_df)} of {total_orders} orders"
)


# ============================================================
# 9. KITCHEN SCHEDULER
# ============================================================

st.divider()
st.subheader("👨‍🍳 Kitchen Scheduler")

st.write(
    f"Active scheduling policy: **{selected_strategy}**"
)

scheduler_columns = [
    "order_id",
    "brand",
    "aggregator",
    "Order State",
    "Station",
    "Start",
    "Completion",
    "Deadline",
    "Delay",
    "Penalty",
    "Status"
]

st.dataframe(
    schedule_df[scheduler_columns],
    use_container_width=True,
    hide_index=True
)

csv_data = schedule_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download schedule CSV",
    data=csv_data,
    file_name="kitchenpulse_schedule.csv",
    mime="text/csv"
)


# ============================================================
# 10. STATION STATUS
# ============================================================

st.divider()
st.subheader("🏭 Kitchen Station Status")

station_rows = []

for station in stations:

    station_orders = schedule_df[
        (schedule_df["Station"] == station)
        & (schedule_df["Order State"] != "Ready")
    ]

    preparing_at_station = station_orders[
        station_orders["Order State"] == "Preparing"
    ]

    queued_at_station = station_orders[
        station_orders["Order State"] == "Queued"
    ]

    assigned_count = len(station_orders)

    preparing_count = len(preparing_at_station)
    queued_count = len(queued_at_station)

    completion_times = [
        value
        for value in station_orders["Completion"].tolist()
        if pd.notna(value)
    ]

    if completion_times:
        next_available = max(completion_times)
    else:
        next_available = "Available"

    if preparing_count > 0:
        status = "Busy"
    elif queued_count > 0:
        status = "Scheduled"
    else:
        status = "Available"

    late_count = (
        station_orders["Status"] == "Late"
    ).sum()

    station_rows.append({
        "Station": station,
        "Status": status,
        "Assigned Orders": assigned_count,
        "Preparing": preparing_count,
        "Queued": queued_count,
        "Late Orders": late_count,
        "Next Available": next_available,
        "Compatible Brands": ", ".join(
            stations[station]["brands"]
        )
    })

station_df = pd.DataFrame(station_rows)

station_columns = st.columns(len(station_df))

for index, row in station_df.iterrows():

    with station_columns[index]:

        if row["Status"] == "Busy":
            st.error(f"Station {row['Station']} · Busy")

        elif row["Status"] == "Scheduled":
            st.warning(f"Station {row['Station']} · Scheduled")

        else:
            st.success(f"Station {row['Station']} · Available")

        st.metric(
            "Assigned Orders",
            row["Assigned Orders"]
        )

        st.caption(
            f"Preparing: {row['Preparing']} | "
            f"Queued: {row['Queued']}"
        )

        st.caption(
            f"Next available: {row['Next Available']}"
        )

st.dataframe(
    station_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# 11. BRAND PERFORMANCE
# ============================================================

st.divider()
st.subheader("📊 Brand-wise Order Performance")

brand_summary = (
    schedule_df[
        schedule_df["Order State"] != "Ready"
    ]
    .groupby("brand")
    .agg(
        Total_Orders=("order_id", "count"),
        On_Time=("Status", lambda x: (x == "On Time").sum()),
        Late=("Status", lambda x: (x == "Late").sum())
    )
    .reset_index()
)

if not brand_summary.empty:

    st.bar_chart(
        brand_summary.set_index("brand")[
            ["On_Time", "Late"]
        ]
    )

    st.dataframe(
        brand_summary,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# 12. STATION WORKLOAD
# ============================================================

st.divider()
st.subheader("📈 Station Workload")

workload_col1, workload_col2 = st.columns(2)

with workload_col1:
    st.markdown("**Orders assigned per station**")

    st.bar_chart(
        station_df.set_index("Station")[["Assigned Orders"]]
    )

with workload_col2:
    st.markdown("**Late orders per station**")

    st.bar_chart(
        station_df.set_index("Station")[["Late Orders"]]
    )


# ============================================================
# 13. CUSTOMER IMPACT
# ============================================================

st.divider()
st.subheader("⚠️ Customer Impact & Delay Analysis")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Total Delay",
    f"{total_delay:.0f} min"
)

col2.metric(
    "Customer Impact Penalty",
    f"{total_penalty:.0f}"
)

col3.metric(
    "Maximum Individual Delay",
    f"{max_delay:.0f} min"
)

st.caption(
    "Customer impact penalties are illustrative scoring weights, "
    "not measured customer satisfaction or actual financial loss."
)


# ============================================================
# 14. EXCEPTION MANAGEMENT
# ============================================================

st.divider()
st.subheader("🚨 Exception Management")

late_queued = schedule_df[
    (schedule_df["Order State"] == "Queued")
    & (schedule_df["Status"] == "Late")
].copy()

late_preparing = schedule_df[
    (schedule_df["Order State"] == "Preparing")
    & (schedule_df["Status"] == "Late")
].copy()

unassigned = schedule_df[
    schedule_df["Station"] == "Unassigned"
].copy()

exception_col1, exception_col2, exception_col3 = st.columns(3)

exception_col1.metric(
    "Queued orders at risk",
    len(late_queued)
)

exception_col2.metric(
    "Late preparation orders",
    len(late_preparing)
)

exception_col3.metric(
    "Unassigned orders",
    len(unassigned)
)


with st.expander(
    f"Queued orders at risk ({len(late_queued)})",
    expanded=True
):
    if late_queued.empty:
        st.success("No queued orders are currently projected to be late.")
    else:
        st.warning(
            "These queued orders are projected to miss their deadlines "
            "under the selected schedule."
        )

        st.dataframe(
            late_queued[scheduler_columns],
            use_container_width=True,
            hide_index=True
        )


with st.expander(
    f"Orders already preparing late ({len(late_preparing)})"
):
    if late_preparing.empty:
        st.success("No currently preparing orders are projected to be late.")
    else:
        st.error(
            "These orders are already being prepared and are projected "
            "to miss their deadlines."
        )

        st.dataframe(
            late_preparing[scheduler_columns],
            use_container_width=True,
            hide_index=True
        )


with st.expander(
    f"Orders without compatible stations ({len(unassigned)})"
):
    if unassigned.empty:
        st.success("All queued orders have compatible station allocations.")
    else:
        st.error(
            "These orders could not be assigned to a compatible station."
        )

        st.dataframe(
            unassigned[scheduler_columns],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# 15. FOOTER
# ============================================================

st.divider()

st.caption(
    "KitchenPulse | Product exploration prototype | "
    "Synthetic operational data | No live aggregator integrations"
)
