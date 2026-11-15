-- ==============================================================================
-- 12 Core Business KPIs & Multi-Dimensional Drill-down SQL Queries
-- Techniques: Common Table Expressions (CTEs), Window Functions, Rolling Aggregations
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- KPI 1, 2, 9, 10: Monthly Revenue Dynamics, Margin, MoM & YoY Growth
-- ------------------------------------------------------------------------------
WITH monthly_sales AS (
    SELECT 
        d.year,
        d.month,
        d.year_month,
        COUNT(DISTINCT s.order_id) AS total_orders,
        SUM(s.units_sold) AS total_units_sold,
        SUM(s.gross_revenue) AS gross_revenue,
        SUM(s.discount_amount) AS total_discounts,
        SUM(s.net_revenue) AS net_revenue,
        SUM(s.cogs) AS total_cogs,
        SUM(s.gross_profit) AS gross_profit,
        ROUND((SUM(s.gross_profit) * 1.0 / NULLIF(SUM(s.net_revenue), 0)) * 100, 2) AS gross_margin_pct,
        ROUND(SUM(s.net_revenue) * 1.0 / NULLIF(COUNT(DISTINCT s.order_id), 0), 2) AS average_order_value
    FROM fact_sales s
    JOIN dim_date d ON s.date_key = d.date_key
    WHERE s.is_returned = 0
    GROUP BY d.year, d.month, d.year_month
),
growth_metrics AS (
    SELECT
        year_month,
        net_revenue,
        gross_profit,
        gross_margin_pct,
        average_order_value,
        -- Month-over-Month (MoM) Growth
        LAG(net_revenue, 1) OVER (ORDER BY year_month) AS prev_month_revenue,
        ROUND(
            ((net_revenue - LAG(net_revenue, 1) OVER (ORDER BY year_month)) * 1.0 /
            NULLIF(LAG(net_revenue, 1) OVER (ORDER BY year_month), 0)) * 100, 2
        ) AS mom_growth_pct,
        -- Year-over-Year (YoY) Growth
        LAG(net_revenue, 12) OVER (ORDER BY year_month) AS prev_year_revenue,
        ROUND(
            ((net_revenue - LAG(net_revenue, 12) OVER (ORDER BY year_month)) * 1.0 /
            NULLIF(LAG(net_revenue, 12) OVER (ORDER BY year_month), 0)) * 100, 2
        ) AS yoy_growth_pct,
        -- Rolling 3-Month Moving Average
        ROUND(AVG(net_revenue) OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS rolling_3m_avg_revenue
    FROM monthly_sales
)
SELECT * FROM growth_metrics;


-- ------------------------------------------------------------------------------
-- KPI 8 & 12: Budget-versus-Actual Variance Analysis & Quota Attainment
-- ------------------------------------------------------------------------------
WITH actuals AS (
    SELECT
        d.year || '-' || printf('%02d', d.month) AS year_month,
        s.region_id,
        p.category,
        SUM(s.net_revenue) AS actual_revenue,
        SUM(s.units_sold) AS actual_units
    FROM fact_sales s
    JOIN dim_date d ON s.date_key = d.date_key
    JOIN dim_product p ON s.product_id = p.product_id
    WHERE s.is_returned = 0
    GROUP BY d.year, d.month, s.region_id, p.category
)
SELECT
    t.year_month,
    r.region_name,
    t.category,
    t.target_revenue,
    COALESCE(a.actual_revenue, 0.0) AS actual_revenue,
    ROUND(COALESCE(a.actual_revenue, 0.0) - t.target_revenue, 2) AS revenue_variance,
    ROUND(
        ((COALESCE(a.actual_revenue, 0.0) - t.target_revenue) * 1.0 / NULLIF(t.target_revenue, 0)) * 100, 2
    ) AS variance_pct,
    ROUND(
        (COALESCE(a.actual_revenue, 0.0) * 1.0 / NULLIF(t.target_revenue, 0)) * 100, 2
    ) AS quota_attainment_pct,
    CASE
        WHEN COALESCE(a.actual_revenue, 0.0) >= t.target_revenue THEN 'Exceeded'
        WHEN COALESCE(a.actual_revenue, 0.0) >= t.target_revenue * 0.90 THEN 'Within 10% Budget'
        ELSE 'Deficit'
    END AS budget_status
FROM fact_sales_targets t
JOIN dim_region r ON t.region_id = r.region_id
LEFT JOIN actuals a ON t.year_month = a.year_month 
                   AND t.region_id = a.region_id 
                   AND t.category = a.category;


-- ------------------------------------------------------------------------------
-- KPI 7: Product Return Rate & Defect Revenue Loss
-- ------------------------------------------------------------------------------
SELECT
    p.category,
    p.subcategory,
    COUNT(s.transaction_id) AS total_orders,
    SUM(s.is_returned) AS returned_units_count,
    ROUND((SUM(s.is_returned) * 1.0 / NULLIF(COUNT(s.transaction_id), 0)) * 100, 2) AS return_rate_pct,
    SUM(s.gross_revenue) AS total_gross_sales,
    SUM(s.return_amount) AS total_refunded_value,
    ROUND((SUM(s.return_amount) * 1.0 / NULLIF(SUM(s.gross_revenue), 0)) * 100, 2) AS revenue_loss_pct
FROM fact_sales s
JOIN dim_product p ON s.product_id = p.product_id
GROUP BY p.category, p.subcategory
ORDER BY returned_units_count DESC;


-- ------------------------------------------------------------------------------
-- KPI 6: Customer Acquisition & Repeat Purchase Ratio
-- ------------------------------------------------------------------------------
WITH customer_order_counts AS (
    SELECT
        customer_id,
        COUNT(DISTINCT order_id) AS total_orders,
        MIN(date_key) AS first_order_date,
        SUM(net_revenue) AS total_spend
    FROM fact_sales
    WHERE is_returned = 0
    GROUP BY customer_id
)
SELECT
    COUNT(customer_id) AS total_active_customers,
    SUM(CASE WHEN total_orders = 1 THEN 1 ELSE 0 END) AS one_time_buyers,
    SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END) AS repeat_buyers,
    ROUND((SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(customer_id)) * 100, 2) AS repeat_customer_rate_pct,
    ROUND(AVG(total_spend), 2) AS average_customer_lifetime_spend
FROM customer_order_counts;


-- ------------------------------------------------------------------------------
-- KPI 11: Customer Pareto Concentration (Top Decile 80/20 Check)
-- ------------------------------------------------------------------------------
WITH ranked_customers AS (
    SELECT
        customer_id,
        SUM(net_revenue) AS customer_revenue,
        NTILE(10) OVER (ORDER BY SUM(net_revenue) DESC) AS revenue_decile,
        SUM(SUM(net_revenue)) OVER () AS total_company_revenue
    FROM fact_sales
    WHERE is_returned = 0
    GROUP BY customer_id
)
SELECT
    revenue_decile,
    COUNT(customer_id) AS customers_in_decile,
    ROUND(SUM(customer_revenue), 2) AS decile_revenue,
    ROUND((SUM(customer_revenue) * 1.0 / MAX(total_company_revenue)) * 100, 2) AS decile_pct_of_total_revenue
FROM ranked_customers
GROUP BY revenue_decile
ORDER BY revenue_decile ASC;
