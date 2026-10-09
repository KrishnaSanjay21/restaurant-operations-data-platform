import json
from pathlib import Path

import pandas as pd

from restaurant_ops.normalize import (
    normalize_address,
    normalize_complaints,
    normalize_inspections,
)

FIXTURES = Path(__file__).parent / "fixtures"


def frame(name: str) -> pd.DataFrame:
    return pd.DataFrame(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def test_address_normalization() -> None:
    assert normalize_address("100 Main Street") == "100 MAIN ST"
    assert normalize_address(" 15  Broadway ") == "15 BROADWAY"


def test_inspections_reject_invalid_and_remove_exact_duplicate() -> None:
    accepted, rejected, duplicates = normalize_inspections(frame("inspections.json"))
    assert len(accepted) == 1
    assert len(rejected) == 1
    assert duplicates == 1
    assert accepted.iloc[0]["restaurant_id"] == "50100001"
    assert accepted.iloc[0]["score"] == 20


def test_complaints_are_idempotent_by_unique_key() -> None:
    accepted, rejected, duplicates = normalize_complaints(frame("complaints.json"))
    assert len(accepted) == 1
    assert len(rejected) == 1
    assert duplicates == 1
    assert accepted.iloc[0]["complaint_id"] == "1001"

