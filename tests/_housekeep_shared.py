"""Shared fixtures for housekeep tests: a temp-only Ctx and a fake runner."""
from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

from marrow import config, storage
from marrow.housekeep import Ctx


def default_hk() -> dict:
    with Path(config.__file__).with_name("config.default.toml").open("rb") as f:
        return dict(tomllib.load(f)["housekeep"])


class FakeRun:
    """Records every command; answers from a {prefix tuple: (rc, out)} table."""

    def __init__(self, table: dict | None = None):
        self.table = table or {}
        self.calls: list[tuple] = []

    def __call__(self, cmd, cwd=None):
        self.calls.append(tuple(cmd))
        best = None
        for prefix, ans in self.table.items():
            if tuple(cmd[:len(prefix)]) == prefix:
                if best is None or len(prefix) > len(best[0]):
                    best = (prefix, ans)
        if best is None:
            return 0, ""
        ans = best[1]
        return ans(cmd) if callable(ans) else ans


def make_ctx(tmp_path: Path, *, dry_run: bool = False, today: date | None = None,
             hk: dict | None = None, run: FakeRun | None = None,
             free: int = 500 * 1024 ** 3) -> Ctx:
    home = tmp_path / "home"
    data = home / ".config" / "marrow"
    for d in (data / "state", data / "backup" / "daily", home / "Library" / "Logs",
              home / "Library" / "LaunchAgents", home / "CC-Lab",
              home / ".claude" / "projects"):
        d.mkdir(parents=True, exist_ok=True)
    db = data / "marrow.db"
    if not db.exists():
        storage.init_db(str(db)).close()
    hk_cfg = default_hk()
    hk_cfg.update(hk or {})
    return Ctx(
        dry_run=dry_run,
        today=today or date.today(),
        hk=hk_cfg,
        db=str(db),
        data_dir=data,
        state_dir=data / "state",
        backup_root=data / "backup",
        drift_dir=data / "backup" / "drift",
        log_root=home / "Library" / "Logs",
        repos_root=home / "CC-Lab",
        projects_dir=home / ".claude" / "projects",
        launch_agents=home / "Library" / "LaunchAgents",
        home=home,
        report_path=home / "CC-Lab" / "docs" / "mw-housekeep-report.md",
        vec_window_days=90,
        run=run or FakeRun(),
        disk_free=lambda: free,
    )
