import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pandas as pd
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(ROOT_DIR, "data", "processed", "sales_dw.db")
SCHEMA_SQL_PATH = os.path.join(ROOT_DIR, "sql", "01_schema.sql")

def initialize_database(db_path: str = DEFAULT_DB_PATH, schema_path: str = SCHEMA_SQL_PATH):
    """Execute DDL schema to create tables and indexes."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(schema_sql)
    conn.commit()
    conn.close()
    logger.info(f"Initialized database schema at: {db_path}")

def generate_enterprise_sales_warehouse(
    db_path: str = DEFAULT_DB_PATH,
    n_transactions: int = 40000,
    random_seed: int = 42
) -> Dict[str, int]:
    """Generate normalized dimensions and transactional facts for the sales data warehouse."""
    np.random.seed(random_seed)
    initialize_database(db_path)
    
    # 1. Date Dimension (2023-01-01 to 2024-12-31)
    logger.info("Generating dim_date...")
    dates = pd.date_range("2023-01-01", "2024-12-31", freq="D")
    dim_date = pd.DataFrame({
        "date_key": [int(d.strftime("%Y%m%d")) for d in dates],
        "full_date": [d.strftime("%Y-%m-%d") for d in dates],
        "year": dates.year,
        "quarter": dates.quarter,
        "month": dates.month,
        "month_name": dates.strftime("%B"),
        "week_of_year": dates.isocalendar().week.astype(int),
        "day_of_week": dates.dayofweek + 1,
        "is_weekend": [1 if d.dayofweek >= 5 else 0 for d in dates]
    })
    
    # 2. Region Dimension
    logger.info("Generating dim_region...")
    dim_region = pd.DataFrame([
        {"region_id": "REG-NA-E", "region_name": "North America - East", "territory_lead": "Sarah Jenkins", "currency": "USD"},
        {"region_id": "REG-NA-W", "region_name": "North America - West", "territory_lead": "David Chen", "currency": "USD"},
        {"region_id": "REG-EMEA", "region_name": "EMEA (Europe/MidEast)", "territory_lead": "Marcello Silva", "currency": "EUR"},
        {"region_id": "REG-APAC", "region_name": "Asia-Pacific", "territory_lead": "Kenji Tanaka", "currency": "USD"},
        {"region_id": "REG-LATAM", "region_name": "Latin America", "territory_lead": "Elena Rodriguez", "currency": "USD"}
    ])
    
    # 3. Product Dimension (40 B2B Enterprise Products)
    logger.info("Generating dim_product...")
    categories = {
        "Hardware": ["Rack Servers", "Network Switches", "Storage Arrays", "Edge Gateways"],
        "Software": ["ERP Suite", "CRM Cloud", "Security Firewall OS", "BI Analytics Engine"],
        "Cloud Solutions": ["Compute Cluster", "Managed Kubernetes", "Object Storage Vault", "API Gateway"],
        "Enterprise Services": ["Implementation Advisory", "Managed 24/7 Support", "Cloud Migration", "Architecture Audit"]
    }
    products = []
    p_id = 1
    for cat, subcats in categories.items():
        for sub in subcats:
            for tier in ["Standard", "Pro", "Enterprise"]:
                base_cost = np.random.uniform(200.0, 4500.0)
                margin = np.random.uniform(0.35, 0.70)
                list_p = base_cost / (1.0 - margin)
                products.append({
                    "product_id": f"PROD-{p_id:04d}",
                    "product_name": f"{sub} - {tier}",
                    "category": cat,
                    "subcategory": sub,
                    "standard_cost": round(base_cost, 2),
                    "list_price": round(list_p, 2)
                })
                p_id += 1
    dim_product = pd.DataFrame(products)
    
    # 4. Customer Dimension (1,200 B2B Customers)
    logger.info("Generating dim_customer...")
    segments = ["Enterprise", "Mid-Market", "SMB", "Public Sector"]
    industries = ["Financial Services", "Healthcare", "Manufacturing", "Retail & E-commerce", "Technology", "Logistics"]
    customers = []
    for c_idx in range(1, 1201):
        c_seg = np.random.choice(segments, p=[0.25, 0.40, 0.25, 0.10])
        ind = np.random.choice(industries)
        first_dt = pd.to_datetime(np.random.choice(dates[:300])).strftime("%Y-%m-%d")
        customers.append({
            "customer_id": f"CUST-{c_idx:04d}",
            "customer_name": f"Enterprise Client {c_idx:04d}",
            "customer_segment": c_seg,
            "country": "United States" if np.random.rand() > 0.3 else "International",
            "state": "California" if np.random.rand() > 0.5 else "New York",
            "industry": ind,
            "first_purchase_date": first_dt
        })
    dim_customer = pd.DataFrame(customers)
    
    # 5. Sales Rep Dimension (25 Sales Reps)
    logger.info("Generating dim_sales_rep...")
    reps = []
    reg_ids = dim_region["region_id"].tolist()
    tiers = ["Senior Director", "Account Executive", "Junior Associate"]
    for r_idx in range(1, 26):
        r_region = np.random.choice(reg_ids)
        r_tier = np.random.choice(tiers, p=[0.2, 0.6, 0.2])
        reps.append({
            "sales_rep_id": f"REP-{r_idx:03d}",
            "rep_name": f"Sales Exec {r_idx:02d}",
            "region_id": r_region,
            "quota_tier": r_tier
        })
    dim_sales_rep = pd.DataFrame(reps)
    
    # 6. Fact Sales Transactions (n_transactions)
    logger.info(f"Generating {n_transactions:,} fact_sales transactions...")
    channels = ["Direct Sales", "Partner / Reseller", "Digital Self-Service", "Inside Sales"]
    
    # Sampling with Q4 seasonality weights
    month_weights = [0.06, 0.07, 0.08, 0.07, 0.08, 0.09, 0.08, 0.08, 0.09, 0.10, 0.12, 0.14]
    date_probs = [month_weights[d.month - 1] for d in dates]
    date_probs = np.array(date_probs) / sum(date_probs)
    
    sampled_dates = pd.to_datetime(np.random.choice(dates, size=n_transactions, p=date_probs))
    sampled_cust = np.random.choice(dim_customer["customer_id"], size=n_transactions)
    sampled_prod = np.random.choice(dim_product["product_id"], size=n_transactions)
    sampled_rep = np.random.choice(dim_sales_rep["sales_rep_id"], size=n_transactions)
    sampled_chan = np.random.choice(channels, size=n_transactions, p=[0.45, 0.25, 0.15, 0.15])
    
    # Map product pricing dictionary for vectorized lookup
    prod_dict = dim_product.set_index("product_id")[["standard_cost", "list_price"]].to_dict(orient="index")
    rep_region_map = dim_sales_rep.set_index("sales_rep_id")["region_id"].to_dict()
    
    tx_records = []
    order_counter = 100000
    for i in range(n_transactions):
        dt = sampled_dates[i]
        date_k = int(dt.strftime("%Y%m%d"))
        cid = sampled_cust[i]
        pid = sampled_prod[i]
        rid = sampled_rep[i]
        reg_id = rep_region_map[rid]
        chan = sampled_chan[i]
        
        # Order bundling: some line items share order_id
        if i % 3 != 0 or i == 0:
            order_counter += 1
        oid = f"ORD-{order_counter}"
        
        p_info = prod_dict[pid]
        u_cost = p_info["standard_cost"]
        u_price = p_info["list_price"]
        
        # Quantity
        units = int(np.random.choice([1, 2, 3, 5, 10, 20], p=[0.45, 0.25, 0.15, 0.10, 0.04, 0.01]))
        discount_rate = float(np.random.choice([0.0, 0.05, 0.10, 0.15, 0.20], p=[0.4, 0.25, 0.2, 0.1, 0.05]))
        
        gross_rev = round(units * u_price, 2)
        disc_amt = round(gross_rev * discount_rate, 2)
        net_rev = round(gross_rev - disc_amt, 2)
        cogs = round(units * u_cost, 2)
        gross_prof = round(net_rev - cogs, 2)
        
        # Return probability (~3.2%)
        is_ret = 1 if np.random.rand() < 0.032 else 0
        ret_amt = net_rev if is_ret else 0.0
        
        tx_records.append({
            "transaction_id": f"TX-{i+1:06d}",
            "order_id": oid,
            "date_key": date_k,
            "customer_id": cid,
            "product_id": pid,
            "region_id": reg_id,
            "sales_rep_id": rid,
            "order_channel": chan,
            "units_sold": units,
            "unit_price": u_price,
            "unit_cost": u_cost,
            "discount_amount": disc_amt,
            "gross_revenue": gross_rev,
            "net_revenue": net_rev,
            "cogs": cogs,
            "gross_profit": gross_prof,
            "is_returned": is_ret,
            "return_amount": ret_amt
        })
        
    fact_sales = pd.DataFrame(tx_records)
    
    # 7. Fact Sales Targets (Budget by Region, Category, Month)
    logger.info("Generating fact_sales_targets...")
    unique_ym = sorted(list(set([d.strftime("%Y-%m") for d in dates])))
    targets = []
    t_id = 1
    for ym in unique_ym:
        for reg in dim_region["region_id"]:
            for cat in dim_product["category"].unique():
                # Realistic budget quota target
                base_target = np.random.uniform(90000.0, 320000.0)
                targets.append({
                    "target_id": f"TGT-{t_id:05d}",
                    "year_month": ym,
                    "region_id": reg,
                    "category": cat,
                    "target_revenue": round(base_target, 2),
                    "target_units": int(base_target / 1200.0)
                })
                t_id += 1
    fact_sales_targets = pd.DataFrame(targets)
    
    # Insert everything into SQLite
    conn = sqlite3.connect(db_path)
    dim_date.to_sql("dim_date", conn, if_exists="replace", index=False)
    dim_customer.to_sql("dim_customer", conn, if_exists="replace", index=False)
    dim_product.to_sql("dim_product", conn, if_exists="replace", index=False)
    dim_region.to_sql("dim_region", conn, if_exists="replace", index=False)
    dim_sales_rep.to_sql("dim_sales_rep", conn, if_exists="replace", index=False)
    fact_sales.to_sql("fact_sales", conn, if_exists="replace", index=False)
    fact_sales_targets.to_sql("fact_sales_targets", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    
    counts = {
        "dim_date": len(dim_date),
        "dim_customer": len(dim_customer),
        "dim_product": len(dim_product),
        "dim_region": len(dim_region),
        "dim_sales_rep": len(dim_sales_rep),
        "fact_sales": len(fact_sales),
        "fact_sales_targets": len(fact_sales_targets)
    }
    logger.info(f"Database generation complete! Summary: {counts}")
    return counts

if __name__ == "__main__":
    generate_enterprise_sales_warehouse()
