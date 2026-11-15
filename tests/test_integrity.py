import sqlite3
import pandas as pd
from src.seed_dw import DEFAULT_DB_PATH

def test_referential_integrity():
    """Verify zero orphan foreign key records in fact_sales."""
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    
    # 1. Check Date FK
    orphan_date = pd.read_sql("""
        SELECT COUNT(*) AS cnt FROM fact_sales s
        LEFT JOIN dim_date d ON s.date_key = d.date_key
        WHERE d.date_key IS NULL
    """, conn)["cnt"].iloc[0]
    assert orphan_date == 0, f"Found {orphan_date} orphan date_keys in fact_sales"
    
    # 2. Check Customer FK
    orphan_cust = pd.read_sql("""
        SELECT COUNT(*) AS cnt FROM fact_sales s
        LEFT JOIN dim_customer c ON s.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
    """, conn)["cnt"].iloc[0]
    assert orphan_cust == 0, f"Found {orphan_cust} orphan customer_ids in fact_sales"
    
    # 3. Check Product FK
    orphan_prod = pd.read_sql("""
        SELECT COUNT(*) AS cnt FROM fact_sales s
        LEFT JOIN dim_product p ON s.product_id = p.product_id
        WHERE p.product_id IS NULL
    """, conn)["cnt"].iloc[0]
    assert orphan_prod == 0, f"Found {orphan_prod} orphan product_ids in fact_sales"
    
    conn.close()

def test_financial_reconciliation():
    """Verify Net Revenue equals Gross Revenue minus Discount."""
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    discrepancies = pd.read_sql("""
        SELECT COUNT(*) AS cnt FROM fact_sales
        WHERE ABS((gross_revenue - discount_amount) - net_revenue) > 0.05
    """, conn)["cnt"].iloc[0]
    conn.close()
    
    assert discrepancies == 0, f"Found {discrepancies} financial calculation mismatches"
