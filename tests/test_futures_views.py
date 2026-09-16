import json
import sqlite3
import subprocess
from datetime import date
from pathlib import Path

from services.futures_views import (
    available_view_dates,
    load_futures_view_bundle,
    load_futures_view_settings,
    update_futures_views,
)


def _project(root: Path, target: date = date(2026, 9, 11)) -> Path:
    (root / "src" / "futures_view").mkdir(parents=True)
    (root / "run_all.ps1").write_text("# test runner", encoding="utf-8")
    stamp = target.strftime("%Y%m%d")
    output = root / "output" / stamp
    output.mkdir(parents=True)
    (output / f"quality_report_{stamp}.json").write_text(
        json.dumps({"target_date": target.isoformat(), "passed": True, "total_records": 1}),
        encoding="utf-8",
    )
    (output / f"summary_{stamp}.json").write_text(
        json.dumps({"target_date": target.isoformat(), "rows": [], "current_view_count": 1}),
        encoding="utf-8",
    )
    (output / f"current_view_{stamp}.json").write_text(
        json.dumps({"as_of_date": target.isoformat(), "views": [{"commodity": "铜"}]}),
        encoding="utf-8",
    )
    (output / "gfqh.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "company": "广发期货", "sector": "有色金属", "commodity": "铜",
                        "view": "看多", "score": 1.0, "view_date": target.isoformat(),
                        "evidence": "库存下降",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    database = root / "data" / "view_database.sqlite3"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE view_history (
                company TEXT, sector TEXT, commodity TEXT, view TEXT, score REAL,
                view_date TEXT, source_date TEXT, supply TEXT, demand TEXT,
                inventory TEXT, core_logic TEXT, medium_outlook TEXT, evidence TEXT,
                confidence TEXT, source_type TEXT, source_name TEXT, source_title TEXT,
                source_url TEXT, quality_rank INTEGER
            )
            """
        )
        connection.execute(
            "INSERT INTO view_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "广发期货", "有色金属", "铜", "看多", 1.0, target.isoformat(),
                target.isoformat(), "", "", "", "库存下降", "", "库存下降",
                "中", "官方网站", "广发期货研究资讯", "铜日报", "https://example.com", 620,
            ),
        )
    return root


def test_settings_are_disabled_by_default_and_environment_can_enable(tmp_path):
    settings = load_futures_view_settings(tmp_path, environ={})
    assert not settings.enabled
    configured = load_futures_view_settings(
        tmp_path,
        values={"enabled": False, "root": str(tmp_path / "ignored")},
        environ={
            "SEATALPHA_FUTURES_VIEW_ENABLED": "true",
            "SEATALPHA_FUTURES_VIEW_ROOT": str(tmp_path / "views"),
            "SEATALPHA_FUTURES_VIEW_AUTO_UPDATE": "false",
        },
    )
    assert configured.enabled
    assert not configured.auto_update
    assert configured.root == (tmp_path / "views").resolve()


def test_bundle_reads_validated_outputs_and_sqlite_history_read_only(tmp_path):
    target = date(2026, 9, 11)
    root = _project(tmp_path / "views", target)
    settings = load_futures_view_settings(
        tmp_path, {"enabled": True, "root": str(root)}, environ={}
    )
    assert available_view_dates(settings) == [target]
    bundle = load_futures_view_bundle(settings, target)
    assert bundle.outlook[0]["commodity"] == "铜"
    assert bundle.daily_records[0]["company"] == "广发期货"
    assert bundle.history_records[0]["evidence"] == "库存下降"


def test_auto_update_skips_a_date_that_already_passed_quality_gate(tmp_path):
    target = date(2026, 9, 11)
    root = _project(tmp_path / "views", target)
    settings = load_futures_view_settings(
        tmp_path, {"enabled": True, "root": str(root)}, environ={}
    )

    def unexpected_runner(*args, **kwargs):
        raise AssertionError("runner should not be called")

    result = update_futures_views(settings, target, runner=unexpected_runner)
    assert result.status == "current"


def test_auto_update_invokes_the_other_projects_entry_point(tmp_path):
    target = date(2026, 9, 14)
    root = tmp_path / "views"
    (root / "src" / "futures_view").mkdir(parents=True)
    (root / "run_all.ps1").write_text("# test runner", encoding="utf-8")
    settings = load_futures_view_settings(
        tmp_path, {"enabled": True, "root": str(root)}, environ={}
    )
    captured = {}

    def runner(command, **kwargs):
        captured["command"] = command
        stamp = target.strftime("%Y%m%d")
        output = root / "output" / stamp
        output.mkdir(parents=True)
        (output / f"quality_report_{stamp}.json").write_text(
            json.dumps({"target_date": target.isoformat(), "passed": True}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "completed", "")

    result = update_futures_views(settings, target, runner=runner)
    assert result.status == "updated"
    assert str(root / "run_all.ps1") in captured["command"]
    assert target.isoformat() in captured["command"]
