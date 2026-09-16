from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

COMPANY_FILES = ("gfqh", "citicsf", "gtjaqh", "dzqh")
DATE_FOLDER = re.compile(r"\d{8}")


@dataclass(frozen=True)
class FuturesViewSettings:
    enabled: bool
    root: Path
    auto_update: bool = True
    llm_backend: str = "api"
    timeout_seconds: int = 3600

    @property
    def output_root(self) -> Path:
        return self.root / "output"

    @property
    def database_path(self) -> Path:
        return self.root / "data" / "view_database.sqlite3"

    @property
    def runner_path(self) -> Path:
        return self.root / "run_all.ps1"

    @property
    def project_available(self) -> bool:
        return self.runner_path.is_file() and (self.root / "src" / "futures_view").is_dir()


@dataclass(frozen=True)
class FuturesViewUpdateResult:
    status: str
    target_date: date
    message: str
    output: str = ""


@dataclass(frozen=True)
class FuturesViewBundle:
    target_date: date
    summary: dict[str, Any]
    outlook: list[dict[str, Any]]
    daily_records: list[dict[str, Any]]
    history_records: list[dict[str, Any]]
    quality: dict[str, Any]
    excel_path: Path | None


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def discover_default_root(seatalpha_root: Path) -> Path:
    return seatalpha_root.parent.parent / "期货公司观点" / "futures_view_pipeline_v0_1"


def load_futures_view_settings(
    seatalpha_root: Path,
    values: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> FuturesViewSettings:
    values = values or {}
    environ = environ or os.environ
    root_value = environ.get("SEATALPHA_FUTURES_VIEW_ROOT") or values.get("root")
    root = Path(str(root_value)).expanduser() if root_value else discover_default_root(seatalpha_root)
    enabled_value = environ.get("SEATALPHA_FUTURES_VIEW_ENABLED", values.get("enabled"))
    auto_value = environ.get("SEATALPHA_FUTURES_VIEW_AUTO_UPDATE", values.get("auto_update"))
    backend = str(
        environ.get("SEATALPHA_FUTURES_VIEW_LLM_BACKEND", values.get("llm_backend", "api"))
    ).strip().lower()
    if backend not in {"api", "browser"}:
        backend = "api"
    timeout_value = environ.get(
        "SEATALPHA_FUTURES_VIEW_TIMEOUT_SECONDS", values.get("timeout_seconds", 3600)
    )
    try:
        timeout_seconds = max(60, int(timeout_value))
    except (TypeError, ValueError):
        timeout_seconds = 3600
    return FuturesViewSettings(
        enabled=_as_bool(enabled_value, False),
        root=root.resolve(),
        auto_update=_as_bool(auto_value, True),
        llm_backend=backend,
        timeout_seconds=timeout_seconds,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def quality_passed(settings: FuturesViewSettings, target: date) -> bool:
    stamp = target.strftime("%Y%m%d")
    path = settings.output_root / stamp / f"quality_report_{stamp}.json"
    try:
        report = _read_json(path)
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    return report.get("target_date") == target.isoformat() and report.get("passed") is True


def available_view_dates(settings: FuturesViewSettings) -> list[date]:
    if not settings.output_root.is_dir():
        return []
    results: list[date] = []
    for folder in settings.output_root.iterdir():
        if not folder.is_dir() or not DATE_FOLDER.fullmatch(folder.name):
            continue
        try:
            candidate = date.fromisoformat(
                f"{folder.name[:4]}-{folder.name[4:6]}-{folder.name[6:8]}"
            )
        except ValueError:
            continue
        if quality_passed(settings, candidate):
            results.append(candidate)
    return sorted(results, reverse=True)


def _lock_path(settings: FuturesViewSettings) -> Path:
    digest = hashlib.sha256(str(settings.root).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"seatalpha-futures-view-{digest}.lock"


def _acquire_lock(path: Path, stale_seconds: int = 4 * 60 * 60) -> int | None:
    try:
        if path.exists() and time.time() - path.stat().st_mtime > stale_seconds:
            path.unlink(missing_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        return descriptor
    except FileExistsError:
        return None


def update_futures_views(
    settings: FuturesViewSettings,
    target: date,
    *,
    force: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> FuturesViewUpdateResult:
    if not settings.enabled:
        return FuturesViewUpdateResult("disabled", target, "期货公司观点接入未启用。")
    if not settings.project_available:
        return FuturesViewUpdateResult("unavailable", target, f"项目目录无效：{settings.root}")
    if quality_passed(settings, target) and not force:
        return FuturesViewUpdateResult("current", target, "目标交易日数据已通过质量门禁。")

    lock_path = _lock_path(settings)
    descriptor = _acquire_lock(lock_path)
    if descriptor is None:
        return FuturesViewUpdateResult("running", target, "另一个 SeatAlpha 会话正在更新观点。")
    os.close(descriptor)
    try:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(settings.runner_path),
            "-Date",
            target.isoformat(),
            "-LlmBackend",
            settings.llm_backend,
        ]
        completed = runner(
            command,
            cwd=settings.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.timeout_seconds,
            check=False,
        )
        combined = "\n".join(value for value in (completed.stdout, completed.stderr) if value)
        tail = combined[-8000:]
        if completed.returncode != 0:
            return FuturesViewUpdateResult(
                "failed", target, f"观点更新失败，退出码 {completed.returncode}。", tail
            )
        if not quality_passed(settings, target):
            return FuturesViewUpdateResult(
                "failed", target, "更新命令结束，但目标日期未通过质量门禁。", tail
            )
        return FuturesViewUpdateResult("updated", target, "观点已更新并通过质量门禁。", tail)
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(str(value or "") for value in (exc.stdout, exc.stderr))[-8000:]
        return FuturesViewUpdateResult("failed", target, "观点更新超时。", output)
    except OSError as exc:
        return FuturesViewUpdateResult("failed", target, f"无法启动观点项目：{exc}")
    finally:
        lock_path.unlink(missing_ok=True)


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"观点数据库不存在：{path}")
    uri = "file:" + str(path.resolve()).replace("\\", "/")
    try:
        connection = sqlite3.connect(f"{uri}?mode=ro", uri=True)
        connection.execute("PRAGMA schema_version").fetchone()
    except sqlite3.OperationalError:
        try:
            connection.close()
        except UnboundLocalError:
            pass
        # A restricted host may deny SQLite's read-only shared-memory sidecar.
        # The pipeline is never writing during a completed quality-gated read,
        # so an immutable fallback remains safe and does not touch the source.
        connection = sqlite3.connect(f"{uri}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _database_history(settings: FuturesViewSettings, target: date) -> list[dict]:
    iso_date = target.isoformat()
    with _connect_read_only(settings.database_path) as connection:
        history = [
            dict(row)
            for row in connection.execute(
                """
                SELECT company, sector, commodity, view, score, view_date, source_date,
                       evidence, confidence, source_type, source_title, source_url
                FROM view_history
                WHERE view_date <= ?
                ORDER BY view_date DESC, company, sector, commodity
                """,
                (iso_date,),
            )
        ]
    return history


def load_futures_view_bundle(settings: FuturesViewSettings, target: date) -> FuturesViewBundle:
    if target not in available_view_dates(settings):
        raise FileNotFoundError(f"{target.isoformat()} 没有通过质量门禁的观点数据。")
    stamp = target.strftime("%Y%m%d")
    output_dir = settings.output_root / stamp
    summary = _read_json(output_dir / f"summary_{stamp}.json")
    quality = _read_json(output_dir / f"quality_report_{stamp}.json")
    outlook_payload = _read_json(output_dir / f"current_view_{stamp}.json")
    daily_records: list[dict[str, Any]] = []
    for company_file in COMPANY_FILES:
        path = output_dir / f"{company_file}.json"
        if path.is_file():
            daily_records.extend(_read_json(path).get("records", []))
    history_records = _database_history(settings, target)
    excel_path = output_dir / f"期货公司观点汇总_{stamp}.xlsx"
    if not excel_path.is_file():
        excel_path = None
    return FuturesViewBundle(
        target_date=target,
        summary=summary,
        outlook=list(outlook_payload.get("views", [])),
        daily_records=daily_records,
        history_records=history_records,
        quality=quality,
        excel_path=excel_path,
    )
