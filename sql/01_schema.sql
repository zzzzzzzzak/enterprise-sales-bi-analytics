-- ==============================================================================
-- Enterprise Sales & Performance Analytics Data Warehouse Schema (Star Schema)
-- ==============================================================================

-- 1. Date Dimension
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    week_of_year INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    is_weekend INTEGER NOT NULL
);

-- 2. Customer Dimension
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_segment TEXT NOT NULL,
    country TEXT NOT NULL,
    state TEXT NOT NULL,
    industry TEXT NOT NULL,
    first_purchase_date TEXT NOT NULL
);

-- 3. Product Dimension
CREATE TABLE IF NOT EXISTS dim_product (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    standard_cost REAL NOT NULL,
    list_price REAL NOT NULL
);

-- 4. Region Dimension
CREATE TABLE IF NOT EXISTS dim_region (
    region_id TEXT PRIMARY KEY,
    region_name TEXT NOT NULL,
    territory_lead TEXT NOT NULL,
    currency TEXT NOT NULL
);

-- 5. Sales Representative Dimension
CREATE TABLE IF NOT EXISTS dim_sales_rep (
    sales_rep_id TEXT PRIMARY KEY,
    rep_name TEXT NOT NULL,
    region_id TEXT NOT NULL,
    quota_tier TEXT NOT NULL,
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id)
);

-- 6. Fact Sales Transactions (Grain: Individual Line Item per Order)
CREATE TABLE IF NOT EXISTS fact_sales (
    transaction_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    date_key INTEGER NOT NULL,
    customer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    region_id TEXT NOT NULL,
    sales_rep_id TEXT NOT NULL,
    order_channel TEXT NOT NULL,
    units_sold INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    unit_cost REAL NOT NULL,
    discount_amount REAL NOT NULL,
    gross_revenue REAL NOT NULL,
    net_revenue REAL NOT NULL,
    cogs REAL NOT NULL,
    gross_profit REAL NOT NULL,
    is_returned INTEGER NOT NULL DEFAULT 0,
    return_amount REAL NOT NULL DEFAULT 0.0,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id),
    FOREIGN KEY (sales_rep_id) REFERENCES dim_sales_rep(sales_rep_id)
);

-- 7. Fact Sales Targets (Budget vs Actual Benchmarking)
CREATE TABLE IF NOT EXISTS fact_sales_targets (
    target_id TEXT PRIMARY KEY,
    year_month TEXT NOT NULL,
    region_id TEXT NOT NULL,
    category TEXT NOT NULL,
    target_revenue REAL NOT NULL,
    target_units INTEGER NOT NULL,
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id)
);

-- Analytical Indexes
CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON fact_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON fact_sales(product_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_region ON fact_sales(region_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_rep ON fact_sales(sales_rep_id);
CREATE INDEX IF NOT EXISTS idx_fact_targets_ym ON fact_sales_targets(year_month, region_id);
