from src.kpi_engine import compute_all_12_kpis

def test_12_kpi_computation():
    """Verify KPI engine computes valid metrics within business bounds."""
    summary = compute_all_12_kpis()
    assert "kpi_summary" in summary
    kpis = summary["kpi_summary"]
    
    assert kpis["gross_revenue"] > 0
    assert kpis["net_sales_revenue"] > 0
    assert kpis["net_sales_revenue"] <= kpis["gross_revenue"]
    assert 0.0 <= kpis["gross_margin_pct"] <= 100.0
    assert 0.0 <= kpis["product_return_rate_pct"] <= 15.0
    assert kpis["average_order_value"] > 0
    assert kpis["total_active_customers"] > 0
    assert 0.0 <= kpis["top_decile_revenue_concentration_pct"] <= 100.0
