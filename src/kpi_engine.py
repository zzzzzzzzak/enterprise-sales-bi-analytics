import os
import sys
import json
import sqlite3
import logging
from typing import Dict, Any
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(ROOT_DIR, "data", "processed", "sales_dw.db")
OUTPUT_JSON = os.path.join(ROOT_DIR, "data", "processed", "sales_kpi_summary.json")

def compute_all_12_kpis(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Compute the 12 core business KPIs from the star schema."""
    conn = sqlite3.connect(db_path)
    
    # 1. High-Level Performance Aggregates
    exec_sql = """
    SELECT
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(units_sold) AS total_units_sold,
        SUM(gross_revenue) AS gross_revenue,
        SUM(discount_amount) AS total_discounts,
        SUM(net_revenue) AS net_revenue,
        SUM(cogs) AS total_cogs,
        SUM(gross_profit) AS gross_profit,
        SUM(is_returned) AS returned_orders_count,
        SUM(return_amount) AS total_return_amount
    FROM fact_sales;
    """
    exec_df = pd.read_sql(exec_sql, conn).iloc[0]
    
    # Non-returned sales for core operational metrics
    net_sales = float(exec_df["net_revenue"] - exec_df["total_return_amount"])
    gross_margin = float(exec_df["gross_profit"] / exec_df["net_revenue"] * 100)
    aov = float(exec_df["net_revenue"] / exec_df["total_orders"])
    return_rate = float(exec_df["returned_orders_count"] / len(pd.read_sql("SELECT transaction_id FROM fact_sales", conn)) * 100)
    
    # 2. Budget vs Actual Variance
    budget_sql = """
    WITH actuals AS (
        SELECT 
            strftime('%Y-%m', d.full_date) AS year_month,
            s.region_id,
            p.category,
            SUM(s.net_revenue) AS actual_rev
        FROM fact_sales s
        JOIN dim_date d ON s.date_key = d.date_key
        JOIN dim_product p ON s.product_id = p.product_id
        WHERE s.is_returned = 0
        GROUP BY 1, 2, 3
    )
    SELECT
        SUM(t.target_revenue) AS total_budget,
        SUM(COALESCE(a.actual_rev, 0.0)) AS total_actual_attained
    FROM fact_sales_targets t
    LEFT JOIN actuals a ON t.year_month = a.year_month
                       AND t.region_id = a.region_id
                       AND t.category = a.category;
    """
    b_df = pd.read_sql(budget_sql, conn).iloc[0]
    total_budget = float(b_df["total_budget"])
    total_attained = float(b_df["total_actual_attained"])
    budget_variance = total_attained - total_budget
    attainment_pct = (total_attained / total_budget) * 100.0
    
    # 3. Customer Repeat Rate
    cust_sql = """
    SELECT
        customer_id,
        COUNT(DISTINCT order_id) as order_cnt
    FROM fact_sales
    WHERE is_returned = 0
    GROUP BY customer_id;
    """
    cust_df = pd.read_sql(cust_sql, conn)
    total_customers = len(cust_df)
    repeat_customers = int((cust_df["order_cnt"] > 1).sum())
    repeat_rate = (repeat_customers / total_customers) * 100.0 if total_customers > 0 else 0.0
    
    # 4. Top Decile Pareto Concentration (80/20 check)
    pareto_sql = """
    WITH customer_spend AS (
        SELECT customer_id, SUM(net_revenue) as spend
        FROM fact_sales
        WHERE is_returned = 0
        GROUP BY customer_id
    ),
    ranked AS (
        SELECT 
            customer_id, spend,
            NTILE(10) OVER (ORDER BY spend DESC) AS decile,
            SUM(spend) OVER () AS total_company_spend
        FROM customer_spend
    )
    SELECT
        SUM(spend) AS top_decile_spend,
        MAX(total_company_spend) AS company_spend
    FROM ranked
    WHERE decile = 1;
    """
    p_df = pd.read_sql(pareto_sql, conn).iloc[0]
    top_decile_concentration = float(p_df["top_decile_spend"] / p_df["company_spend"] * 100.0)
    
    conn.close()
    
    summary = {
        "kpi_summary": {
            "gross_revenue": round(float(exec_df["gross_revenue"]), 2),
            "net_sales_revenue": round(net_sales, 2),
            "total_units_sold": int(exec_df["total_units_sold"]),
            "average_order_value": round(aov, 2),
            "gross_margin_pct": round(gross_margin, 2),
            "total_orders": int(exec_df["total_orders"]),
            "total_active_customers": total_customers,
            "repeat_customer_rate_pct": round(repeat_rate, 2),
            "product_return_rate_pct": round(return_rate, 2),
            "total_budget_revenue": round(total_budget, 2),
            "budget_variance_dollar": round(budget_variance, 2),
            "quota_attainment_pct": round(attainment_pct, 2),
            "top_decile_revenue_concentration_pct": round(top_decile_concentration, 2)
        }
    }
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(summary, f, indent=2)
        
    logger.info(f"Computed all 12 KPIs successfully. Saved to: {OUTPUT_JSON}")
    return summary

if __name__ == "__main__":
    compute_all_12_kpis()
