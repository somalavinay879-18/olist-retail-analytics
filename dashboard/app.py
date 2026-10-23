"""Streamlit dashboard for the Olist retail analytics project.

Run from the repository root:
    pip install -r dashboard/requirements.txt
    streamlit run dashboard/app.py

It reads the aggregated KPI tables in dashboard/data/ (exported by the pipeline).
"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="Olist Retail Analytics", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv")


monthly = load("kpi_monthly")
category = load("kpi_category")
state = load("kpi_state")
seller = load("kpi_seller")

monthly = monthly[monthly["orders"] > 0].sort_values("year_month").reset_index(drop=True)
months = monthly["year_month"].tolist()

st.title("Olist Retail Analytics")
st.caption("Sales and delivery performance of about 100,000 orders from a Brazilian e-commerce marketplace "
           "(2016-2018). Revenue is item price only, without freight.")

# --- sidebar filter -------------------------------------------------------------------------
default_start = "2017-01" if "2017-01" in months else months[0]
default_end = "2018-08" if "2018-08" in months else months[-1]
start, end = st.sidebar.select_slider("Period", options=months, value=(default_start, default_end))
st.sidebar.caption("The first months of 2016 and the last two months of 2018 contain very few orders, "
                   "so the default period is January 2017 to August 2018.")

m = monthly[(monthly["year_month"] >= start) & (monthly["year_month"] <= end)].copy()
m["late_pct"] = m["late_rate"] * 100

# --- headline numbers -----------------------------------------------------------------------
orders = int(m["orders"].sum())
revenue = float(m["revenue"].sum())
delivered = int(m["delivered_orders"].sum())
late = int(m["late_orders"].sum())
aov = revenue / orders if orders else 0.0
late_rate = 100 * late / delivered if delivered else 0.0
avg_days = (m["avg_delivery_days"].fillna(0) * m["delivered_orders"]).sum() / delivered if delivered else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Orders", f"{orders:,}")
c2.metric("Revenue", f"{revenue / 1e6:.2f} M BRL")
c3.metric("Average order value", f"{aov:,.0f} BRL")
c4.metric("Late deliveries", f"{late_rate:.1f} %")
c5.metric("Avg delivery time", f"{avg_days:.1f} days")

tab_sales, tab_delivery, tab_category, tab_region, tab_seller = st.tabs(
    ["Sales", "Delivery", "Categories", "Regions", "Sellers"])

with tab_sales:
    st.subheader("Revenue per month (BRL)")
    st.line_chart(m.set_index("year_month")["revenue"])
    left, right = st.columns(2)
    with left:
        st.subheader("Orders per month")
        st.bar_chart(m.set_index("year_month")["orders"])
    with right:
        st.subheader("Average order value (BRL)")
        st.line_chart(m.set_index("year_month")["aov"])
    st.caption("Revenue peaks in November 2017 (Black Friday season).")

with tab_delivery:
    left, right = st.columns(2)
    with left:
        st.subheader("Late deliveries per month (%)")
        st.line_chart(m.set_index("year_month")["late_pct"])
    with right:
        st.subheader("Average review score per month")
        st.line_chart(m.set_index("year_month")["avg_review_score"])
    st.caption("A delivery is late if it arrives on a later day than the estimated delivery date. "
               "Months with many late deliveries have lower review scores.")

with tab_category:
    top_n = st.slider("Number of categories", 5, 30, 10)
    top = category.sort_values("revenue", ascending=False).head(top_n)
    chart = (alt.Chart(top).mark_bar()
             .encode(x=alt.X("revenue:Q", title="Revenue (BRL)"),
                     y=alt.Y("category_en:N", sort="-x", title=None),
                     tooltip=["category_en", "orders", "revenue"])
             .properties(height=28 * top_n + 40, width=700))
    st.altair_chart(chart)
    table = top.assign(revenue_share_pct=(top["revenue_share"] * 100).round(1))
    st.dataframe(table[["category_en", "orders", "items_sold", "revenue", "revenue_share_pct"]],
                 hide_index=True)
    st.caption("Category figures cover the whole dataset, not only the selected period.")

with tab_region:
    min_orders = st.slider("Minimum orders per state", 100, 5000, 1000, step=100)
    s = state[state["orders"] >= min_orders].copy()
    s["late_pct"] = (s["late_rate"] * 100).round(1)
    s["avg_delivery_days"] = s["avg_delivery_days"].round(1)
    left, right = st.columns(2)
    with left:
        st.subheader("Late deliveries by customer state (%)")
        chart = (alt.Chart(s).mark_bar()
                 .encode(x=alt.X("customer_state:N", sort="-y", title="State"),
                         y=alt.Y("late_pct:Q", title="Late deliveries (%)"),
                         tooltip=["customer_state", "orders", "late_pct"])
                 .properties(height=320, width=420))
        st.altair_chart(chart)
    with right:
        st.subheader("Average delivery time (days)")
        chart = (alt.Chart(s).mark_bar()
                 .encode(x=alt.X("customer_state:N", sort="-y", title="State"),
                         y=alt.Y("avg_delivery_days:Q", title="Days"),
                         tooltip=["customer_state", "orders", "avg_delivery_days"])
                 .properties(height=320, width=420))
        st.altair_chart(chart)
    st.dataframe(s.sort_values("orders", ascending=False)[
        ["customer_state", "orders", "revenue", "avg_delivery_days", "late_pct"]], hide_index=True)
    st.caption("State figures cover the whole dataset, not only the selected period.")

with tab_seller:
    min_seller_orders = st.slider("Minimum delivered orders per seller", 10, 300, 50, step=10)
    sel = seller[seller["delivered_orders"] >= min_seller_orders].copy()
    sel["late_pct"] = (sel["late_rate"] * 100).round(1)
    sel = sel.sort_values("late_pct", ascending=False).head(20)
    st.subheader(f"Sellers with the highest late-delivery rate (at least {min_seller_orders} delivered orders)")
    st.dataframe(sel[["seller_id", "orders", "delivered_orders", "late_orders", "late_pct", "revenue"]],
                 hide_index=True)
    st.caption("Seller IDs are anonymised in the source data.")

st.divider()
st.caption("Data: Brazilian E-Commerce Public Dataset by Olist (Kaggle), CC BY-NC-SA 4.0. "
           "Aggregated figures only; non-commercial portfolio project.")
