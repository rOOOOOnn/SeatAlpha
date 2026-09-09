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


def test_ranking_replacement_does_not_mix_old_provider(tmp_path: Path):
    from pipeline.update import _replace_position_partitions

    path = tmp_path / "rankings.duckdb"
    init_db(path)
    _, positions = build_demo(periods=2)
    upsert_frame("broker_positions", positions, ["trade_date", "exchange", "contract", "broker"], path)
    incoming = positions.iloc[[0]].copy()
    incoming["broker"] = "新会员"
    incoming["source"] = "ifind-member-ranking"
    _replace_position_partitions(incoming, path)
    row = incoming.iloc[0]
    result = query("SELECT broker, source FROM broker_positions WHERE trade_date=? AND exchange=? AND contract=?",
                   [row.trade_date, row.exchange, row.contract], path)
    assert result.to_dict("records") == [{"broker": "新会员", "source": "ifind-member-ranking"}]
