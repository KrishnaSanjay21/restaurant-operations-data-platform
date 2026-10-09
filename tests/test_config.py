from pathlib import Path

from restaurant_ops.config import load_config


def test_portfolio_profile_exceeds_target_by_configuration() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root, "portfolio")
    assert config.profile.complaints_limit >= 250_000
    assert config.profile.inspections_limit == 0
    assert config.minimum_portfolio_records == 500_000

