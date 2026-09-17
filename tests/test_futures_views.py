import json
import os
import sqlite3
import subprocess
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

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
    for company in ("citicsf", "gtjaqh", "dzqh"):
        (output / f"{company}.json").write_text('{"records": []}', encoding="utf-8")
    (output / f"期货公司观点汇总_{stamp}.xlsx").write_bytes(b"test workbook")
    database = root / "data" / "view_database.sqlite3"
    database.parent.mkdir()
    with closing(sqlite3.connect(database)) as connection:
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
        connection.commit()
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
        (output / f"summary_{stamp}.json").write_text('{}', encoding="utf-8")
        (output / f"期货公司观点汇总_{stamp}.xlsx").write_bytes(b"test workbook")
        for company in ("gfqh", "citicsf", "gtjaqh", "dzqh"):
            (output / f"{company}.json").write_text('{"records": []}', encoding="utf-8")
        (output / f"quality_report_{stamp}.json").write_text(
            json.dumps({"target_date": target.isoformat(), "passed": True}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "completed", "")

    result = update_futures_views(settings, target, runner=runner)
    assert result.status == "updated"
    assert str(root / "run_all.ps1") in captured["command"][-1]
    assert target.isoformat() in captured["command"][-1]


def test_legacy_quality_passed_date_can_load_without_outlook(tmp_path):
    target = date(2026, 8, 24)
    root = _project(tmp_path / "views", target)
    (root / "output" / "20260824" / "current_view_20260824.json").unlink()
    settings = load_futures_view_settings(
        tmp_path, {"enabled": True, "root": str(root)}, environ={}
    )
    bundle = load_futures_view_bundle(settings, target)
    assert not bundle.outlook_available
    assert bundle.outlook == []


def test_missing_database_does_not_hide_valid_final_outputs(tmp_path):
    target = date(2026, 9, 11)
    root = _project(tmp_path / "views", target)
    (root / "data" / "view_database.sqlite3").unlink()
    settings = load_futures_view_settings(
        tmp_path, {"enabled": True, "root": str(root)}, environ={}
    )
    bundle = load_futures_view_bundle(settings, target)
    assert bundle.daily_records[0]["commodity"] == "铜"
    assert bundle.outlook[0]["commodity"] == "铜"
    assert bundle.history_records == []
    assert bundle.history_error


def test_force_update_does_not_accept_an_unchanged_old_quality_report(tmp_path):
    target = date(2026, 9, 11)
    root = _project(tmp_path / "views", target)
    settings = load_futures_view_settings(
        tmp_path, {"enabled": True, "root": str(root)}, environ={}
    )
    result = update_futures_views(
        settings,
        target,
        force=True,
        runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )
    assert result.status == "failed"
    assert update_futures_views(settings, target).status == "current"


def test_failed_auto_update_enters_cross_session_cooldown(tmp_path):
    target = date(2026, 9, 14)
    root = tmp_path / "views"
    (root / "src" / "futures_view").mkdir(parents=True)
    (root / "run_all.ps1").write_text("# test runner", encoding="utf-8")
    settings = load_futures_view_settings(
        tmp_path, {"enabled": True, "root": str(root)}, environ={}
    )
    result = update_futures_views(
        settings,
        target,
        runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 2, "", "failure"),
    )
    assert result.status == "failed"
    assert update_futures_views(settings, target).status == "cooldown"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell runner is Windows-specific")
def test_powershell_runner_propagates_source_project_failure(tmp_path):
    root = tmp_path / "views"
    (root / "src" / "futures_view").mkdir(parents=True)
    (root / "run_all.ps1").write_text(
        "param([string]$Date, [string]$LlmBackend)\ncmd /c exit 7\n",
        encoding="utf-8",
    )
    settings = load_futures_view_settings(
        tmp_path, {"enabled": True, "root": str(root)}, environ={}
    )
    result = update_futures_views(settings, date(2026, 9, 14), force=True)
    assert result.status == "failed"
    assert "退出码 7" in result.message


def test_company_views_page_handles_legacy_date_and_session_toggle(tmp_path, monkeypatch):
    root = _project(tmp_path / "views", date(2026, 8, 24))
    (root / "output" / "20260824" / "current_view_20260824.json").unlink()
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_ENABLED", "true")
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_AUTO_UPDATE", "false")
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_ROOT", str(root))

    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()
    app._page_hash = calc_hash("commodity-company-views")
    app.run()
    assert not app.exception
    assert [heading.value for heading in app.header] == ["国内大型期货公司观点"]
    assert any("尚未生成中期展望" in item.value for item in app.info)
    assert len(app.dataframe) >= 3

    next(item for item in app.toggle if item.label == "接入期货公司观点").set_value(False).run()
    assert not app.exception
    assert next(item for item in app.toggle if item.label == "接入期货公司观点").value is False


def test_company_views_page_renders_divergence_chart(tmp_path, monkeypatch):
    target = date(2026, 9, 16)
    root = _project(tmp_path / "views", target)
    stamp = target.strftime("%Y%m%d")
    (root / "output" / stamp / f"summary_{stamp}.json").write_text(
        json.dumps({
            "target_date": target.isoformat(),
            "rows": [{
                "sector": "黑色系",
                "scores": {"广发期货": -0.4, "中信期货": 0.0,
                           "国泰海通期货": -0.3, "东证期货": 1.0},
                "average": 0.075, "divergence": 1.4,
                "consistency": "中", "judgement": "中性",
            }],
            "current_view_count": 1,
        }), encoding="utf-8",
    )
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_ENABLED", "true")
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_AUTO_UPDATE", "false")
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_ROOT", str(root))

    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()
    app._page_hash = calc_hash("commodity-company-views")
    app.run()
    assert not app.exception
    assert any("机构观点与分歧" in json.loads(chart.proto.spec)["layout"]["title"]["text"]
               for chart in app.get("plotly_chart"))


def test_page_reload_recovers_stale_futures_components_module(tmp_path, monkeypatch):
    import ui.futures_views_components as components

    root = _project(tmp_path / "views")
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_ENABLED", "true")
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_AUTO_UPDATE", "false")
    monkeypatch.setenv("SEATALPHA_FUTURES_VIEW_ROOT", str(root))
    monkeypatch.delattr(components, "medium_outlook_frame")

    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()
    app._page_hash = calc_hash("commodity-company-views")
    app.run()
    assert not app.exception
    assert callable(components.medium_outlook_frame)
