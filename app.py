import os
import sys
import sqlite3
import json
import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(
    page_title="Enterprise Sales & BI Analytics",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

DB_PATH = os.path.join(ROOT_DIR, "data", "processed", "sales_dw.db")
DAX_PATH = os.path.join(ROOT_DIR, "dax", "measures.dax")
SQL_QUERIES_PATH = os.path.join(ROOT_DIR, "sql", "02_kpi_queries.sql")

@st.cache_data
def get_db_connection():
    if not os.path.exists(DB_PATH):
        from src.seed_dw import generate_enterprise_sales_warehouse
        generate_enterprise_sales_warehouse(DB_PATH)
    return sqlite3.connect(DB_PATH)

conn = get_db_connection()

# Header
st.title("💼 Enterprise Sales & Business Intelligence KPI Suite")
st.caption("Star-Schema Analytics Warehouse | 12 Core KPIs Evaluated Across 5 Business Dimensions")

# Sidebar: 5 Drill-Down Dimensions
st.sidebar.header("🎯 Multi-Dimensional Drill-down Filters")

# Dimension 1: Time
years = ["All", 2023, 2024]
selected_year = st.sidebar.selectbox("1. Dimension: Year", years)

# Dimension 2: Region
regions = ["All"] + pd.read_sql("SELECT DISTINCT region_name FROM dim_region", conn)["region_name"].tolist()
selected_region = st.sidebar.selectbox("2. Dimension: Region / Geography", regions)

# Dimension 3: Product Category
categories = ["All"] + pd.read_sql("SELECT DISTINCT category FROM dim_product", conn)["category"].tolist()
selected_cat = st.sidebar.selectbox("3. Dimension: Product Category", categories)

# Dimension 4: Customer Segment
segments = ["All"] + pd.read_sql("SELECT DISTINCT customer_segment FROM dim_customer", conn)["customer_segment"].tolist()
selected_seg = st.sidebar.selectbox("4. Dimension: Customer Segment", segments)

# Dimension 5: Sales Channel
channels = ["All"] + pd.read_sql("SELECT DISTINCT order_channel FROM fact_sales", conn)["order_channel"].tolist()
selected_chan = st.sidebar.selectbox("5. Dimension: Sales Channel", channels)

# Build Dynamic Filtered SQL Query
where_clauses = ["s.is_returned = 0"]
params = []

if selected_year != "All":
    where_clauses.append("d.year = ?")
    params.append(selected_year)
if selected_region != "All":
    where_clauses.append("r.region_name = ?")
    params.append(selected_region)
if selected_cat != "All":
    where_clauses.append("p.category = ?")
    params.append(selected_cat)
if selected_seg != "All":
    where_clauses.append("c.customer_segment = ?")
    params.append(selected_seg)
if selected_chan != "All":
    where_clauses.append("s.order_channel = ?")
    params.append(selected_chan)

filter_sql = " AND ".join(where_clauses)

filtered_query = f"""
SELECT
    s.transaction_id,
    s.order_id,
    d.year,
    d.month,
    strftime('%Y-%m', d.full_date) AS year_month,
    r.region_name,
    p.category,
    p.subcategory,
    c.customer_segment,
    s.order_channel,
    s.units_sold,
    s.gross_revenue,
    s.discount_amount,
    s.net_revenue,
    s.cogs,
    s.gross_profit,
    s.is_returned,
    s.return_amount
FROM fact_sales s
JOIN dim_date d ON s.date_key = d.date_key
JOIN dim_region r ON s.region_id = r.region_id
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_customer c ON s.customer_id = c.customer_id
WHERE {filter_sql}
"""

df_filtered = pd.read_sql(filtered_query, conn, params=params)

# Executive KPI Cards (12 KPIs)
net_revenue = df_filtered["net_revenue"].sum() if not df_filtered.empty else 0.0
gross_profit = df_filtered["gross_profit"].sum() if not df_filtered.empty else 0.0
margin_pct = (gross_profit / net_revenue * 100.0) if net_revenue > 0 else 0.0
total_orders = df_filtered["order_id"].nunique() if not df_filtered.empty else 0
aov = (net_revenue / total_orders) if total_orders > 0 else 0.0
units_sold = df_filtered["units_sold"].sum() if not df_filtered.empty else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Net Sales Revenue", f"${net_revenue:,.0f}", "After Discounts")
k2.metric("Gross Profit", f"${gross_profit:,.0f}")
k3.metric("Gross Margin", f"{margin_pct:.1f}%")
k4.metric("Avg Order Value (AOV)", f"${aov:,.0f}")
k5.metric("Total Units Sold", f"{units_sold:,}")

st.markdown("---")

tabs = st.tabs([
    "📊 Monthly Trends & Variance",
    "📦 Product & Category Profitability",
    "👥 Customer & Pareto Analysis",
    "💻 SQL CTEs & DAX Blueprint"
])

with tabs[0]:
    st.subheader("Monthly Revenue Trajectory & Budget Variance")
    if not df_filtered.empty:
        monthly_trend = df_filtered.groupby("year_month")[["net_revenue", "gross_profit"]].sum().reset_index()
        monthly_trend["SMA 3M"] = monthly_trend["net_revenue"].rolling(3, min_periods=1).mean()
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("##### Monthly Net Sales & Rolling 3M Trend ($)")
            st.line_chart(monthly_trend.set_index("year_month")[["net_revenue", "SMA 3M"]])
            
        with c2:
            st.markdown("##### Revenue Contribution by Region")
            reg_rev = df_filtered.groupby("region_name")["net_revenue"].sum()
            st.bar_chart(reg_rev)
            
        st.markdown("##### Budget vs Actual Performance by Category")
        target_sql = """
        SELECT 
            t.category,
            SUM(t.target_revenue) AS budget_target
        FROM fact_sales_targets t
        GROUP BY t.category;
        """
        targets_df = pd.read_sql(target_sql, conn)
        actuals_cat = df_filtered.groupby("category")["net_revenue"].sum().reset_index()
        actuals_cat.columns = ["category", "actual_revenue"]
        
        comp_df = pd.merge(targets_df, actuals_cat, on="category", how="inner")
        comp_df["variance_$"] = comp_df["actual_revenue"] - comp_df["budget_target"]
        comp_df["attainment_%"] = (comp_df["actual_revenue"] / comp_df["budget_target"]) * 100.0
        
        st.dataframe(
            comp_df.style.format({
                "budget_target": "${:,.0f}",
                "actual_revenue": "${:,.0f}",
                "variance_$": "${:,.0f}",
                "attainment_%": "{:.1f}%"
            }),
            use_container_width=True
        )
    else:
        st.warning("No records matched the current filter criteria.")

with tabs[1]:
    st.subheader("Product Category Profitability & Margin Depth")
    if not df_filtered.empty:
        prod_perf = df_filtered.groupby(["category", "subcategory"]).agg({
            "units_sold": "sum",
            "net_revenue": "sum",
            "gross_profit": "sum"
        }).reset_index()
        prod_perf["margin_pct"] = (prod_perf["gross_profit"] / prod_perf["net_revenue"]) * 100.0
        
        st.dataframe(
            prod_perf.sort_values("net_revenue", ascending=False).style.format({
                "units_sold": "{:,}",
                "net_revenue": "${:,.0f}",
                "gross_profit": "${:,.0f}",
                "margin_pct": "{:.1f}%"
            }),
            use_container_width=True
        )

with tabs[2]:
    st.subheader("Customer Segment & Pareto Concentration (80/20 Rule)")
    if not df_filtered.empty:
        seg_summary = df_filtered.groupby("customer_segment").agg({
            "order_id": "nunique",
            "net_revenue": "sum"
        }).reset_index()
        seg_summary.columns = ["Customer Segment", "Total Orders", "Total Revenue"]
        seg_summary["AOV"] = seg_summary["Total Revenue"] / seg_summary["Total Orders"]
        
        st.dataframe(
            seg_summary.style.format({
                "Total Orders": "{:,}",
                "Total Revenue": "${:,.0f}",
                "AOV": "${:,.0f}"
            }),
            use_container_width=True
        )
        
        st.markdown("##### Channel Sales Distribution")
        chan_summary = df_filtered.groupby("order_channel")["net_revenue"].sum()
        st.bar_chart(chan_summary)

with tabs[3]:
    st.subheader("SQL Architecture & Production DAX Measures")
    st.markdown("""
    #### Star-Schema Architecture Highlights:
    * **1 Central Fact Table**: `fact_sales` (Grain: Individual Line Item per Order).
    * **1 Secondary Fact Table**: `fact_sales_targets` (Monthly Quotas by Category & Region).
    * **5 Dimensional Conformed Entities**: `dim_date`, `dim_customer`, `dim_product`, `dim_region`, `dim_sales_rep`.
    """)
    
    col_sql, col_dax = st.columns(2)
    with col_sql:
        st.markdown("##### 📄 SQL CTEs & Window Functions Reference")
        if os.path.exists(SQL_QUERIES_PATH):
            with open(SQL_QUERIES_PATH, "r") as f:
                st.code(f.read()[:2000] + "\n\n-- [See full sql/02_kpi_queries.sql for complete queries]", language="sql")
                
    with col_dax:
        st.markdown("##### 📊 Production DAX Measures Specification")
        if os.path.exists(DAX_PATH):
            with open(DAX_PATH, "r") as f:
                st.code(f.read(), language="dax")
