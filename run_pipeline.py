import os
import sys
import logging

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.seed_dw import generate_enterprise_sales_warehouse
from src.kpi_engine import compute_all_12_kpis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    print("=" * 70)
    print("ENTERPRISE SALES BI & ANALYTICS WAREHOUSE PIPELINE")
    print("=" * 70)
    
    print("\n[1/2] Seeding star-schema data warehouse (Facts & Dimensions)...")
    counts = generate_enterprise_sales_warehouse()
    print(f"Warehouse Populated: {counts['fact_sales']:,} Sales Facts, {counts['dim_customer']:,} Customers, {counts['dim_product']} Products")
    
    print("\n[2/2] Executing SQL KPI engine across 12 business performance metrics...")
    summary = compute_all_12_kpis()
    kpi = summary["kpi_summary"]
    
    print("\n" + "=" * 70)
    print("CORE BUSINESS PERFORMANCE METRICS SUMMARY (12 KPIs)")
    print("=" * 70)
    print(f"1.  Gross Sales Revenue:            ${kpi['gross_revenue']:,.2f}")
    print(f"2.  Net Sales Revenue:              ${kpi['net_sales_revenue']:,.2f}")
    print(f"3.  Total Units Sold:               {kpi['total_units_sold']:,}")
    print(f"4.  Average Order Value (AOV):      ${kpi['average_order_value']:,.2f}")
    print(f"5.  Gross Profit Margin:            {kpi['gross_margin_pct']:.2f}%")
    print(f"6.  Total Order Volume:             {kpi['total_orders']:,}")
    print(f"7.  Active B2B Customers:           {kpi['total_active_customers']:,}")
    print(f"8.  Repeat Customer Ratio:          {kpi['repeat_customer_rate_pct']:.1f}%")
    print(f"9.  Product Return Rate:            {kpi['product_return_rate_pct']:.2f}%")
    print(f"10. Target Budget Revenue:          ${kpi['total_budget_revenue']:,.2f}")
    print(f"11. Budget-vs-Actual Variance:      ${kpi['budget_variance_dollar']:,.2f}")
    print(f"12. Quota Attainment Ratio:         {kpi['quota_attainment_pct']:.1f}%")
    print("=" * 70)
    print("Run interactive dashboard with: streamlit run app.py")

if __name__ == "__main__":
    main()
