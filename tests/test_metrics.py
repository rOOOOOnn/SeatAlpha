from metrics.signals import calculate_metrics
from pipeline.seed_demo import build_demo


def test_metrics_are_bounded_and_complete():
    contracts, positions = build_demo(periods=25)
    result = calculate_metrics(contracts, positions)
    assert not result.empty
    assert result["net_position_ratio"].between(-1, 1).all()
    assert result[["bull_score", "divergence_score"]].notna().all().all()


def test_latest_day_has_all_demo_symbols():
    contracts, positions = build_demo(periods=5)
    result = calculate_metrics(contracts, positions)
    latest = result[result["trade_date"].eq(result["trade_date"].max())]
    assert latest["symbol"].nunique() == contracts["symbol"].nunique()
