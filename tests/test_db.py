from pathlib import Path

from core.db import init_db, query, upsert_frame
from pipeline.seed_demo import build_demo


def test_upsert_is_idempotent(tmp_path: Path):
    path = tmp_path / "test.duckdb"
    init_db(path)
    contracts, _ = build_demo(periods=2)
    upsert_frame("contracts", contracts, ["trade_date", "exchange", "contract"], path)
    upsert_frame("contracts", contracts, ["trade_date", "exchange", "contract"], path)
    count = query("SELECT count(*) n FROM contracts", path=path).iloc[0]["n"]
    assert count == len(contracts)
