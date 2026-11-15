import os
import sqlite3
import pandas as pd
from src.seed_dw import DEFAULT_DB_PATH

def test_database_tables_exist():
    """Verify all 7 star-schema tables exist in the SQLite data warehouse."""
    assert os.path.exists(DEFAULT_DB_PATH), f"Database not found at {DEFAULT_DB_PATH}"
    
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    
    expected_tables = [
        "dim_date", "dim_customer", "dim_product", "dim_region",
        "dim_sales_rep", "fact_sales", "fact_sales_targets"
    ]
    for tbl in expected_tables:
        assert tbl in tables, f"Expected table {tbl} was not found in schema"

def test_fact_sales_record_volume():
    """Verify fact_sales contains at least 30,000 transaction line items."""
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    count = pd.read_sql("SELECT COUNT(*) AS cnt FROM fact_sales", conn)["cnt"].iloc[0]
    conn.close()
    assert count >= 30000, f"Expected >= 30k rows in fact_sales, got {count}"
