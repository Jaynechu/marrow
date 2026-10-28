"""Weekly housekeep job (com.marrow.housekeep): shared run context + file helpers."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from .._atomic import atomic_write

Runner = Callable[..., tuple[int, str]]


@dataclass
class Ctx:
    dry_run: bool
    today: date
    hk: dict
    db: str
    data_dir: Path
    state_dir: Path
    backup_root: Path
    drift_dir: Path
    log_root: Path
    repos_root: Path
    projects_dir: Path
    launch_agents: Path
    home: Path
    report_path: Path
    vec_window_days: int
    run: Runner
    disk_free: Callable[[], int]
    prev_sizes: dict = field(default_factory=dict)

    @property
    def hk_state(self) -> Path:
        return self.state_dir / "housekeep"


def make_runner(timeout_s: int) -> Runner:
    def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout_s, cwd=cwd)
        except FileNotFoundError as e:
            return 127, str(e)
        except subprocess.TimeoutExpired:
            return 124, f"timeout after {timeout_s}s"
        return r.returncode, (r.stdout + r.stderr).strip()
    return _run


def build_ctx(dry_run: bool) -> Ctx:
    from .. import config, timeutil
    from ..paths import paths
    cfg = config.load()
    hk = cfg["housekeep"]
    home = Path.home()
    return Ctx(
        dry_run=dry_run,
        today=timeutil.local_today(),
        hk=hk,
        db=cfg["paths"]["db"],
        data_dir=config.DATA_DIR,
        state_dir=Path(paths.state_dir),
        backup_root=Path(cfg["paths"]["backup_dir"]).expanduser(),
        drift_dir=Path(paths.drift_backup_dir),
        log_root=config.log_root(),
        repos_root=Path(hk["repos_root"]).expanduser(),
        projects_dir=home / ".claude" / "projects",
        launch_agents=home / "Library" / "LaunchAgents",
        home=home,
        report_path=Path(hk["report_path"]).expanduser(),
        vec_window_days=int(cfg["recall"]["vec_window_days"]),
        run=make_runner(int(hk["cmd_timeout_s"])),
        disk_free=lambda: shutil.disk_usage(home).free,
    )


def tree_size(p: Path) -> int:
    try:
        st = p.lstat()
    except OSError:
        return 0
    if not p.is_dir() or p.is_symlink():
        return st.st_size
    total = 0
    stack = [str(p)]
    while stack:
        try:
            it = os.scandir(stack.pop())
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    else:
                        total += e.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    return total


def latest_mtime(p: Path) -> float:
    newest = p.lstat().st_mtime
    if p.is_dir() and not p.is_symlink():
        for root, dirs, files in os.walk(p):
            for n in dirs + files:
                try:
                    newest = max(newest, os.lstat(os.path.join(root, n)).st_mtime)
                except OSError:
                    continue
    return newest


def remove(p: Path) -> int:
    size = tree_size(p)
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p)
    else:
        p.unlink()
    return size


def fmt_size(n: float) -> str:
    if abs(n) < 1024:
        return f"{n:.0f} B"
    for unit in ("KB", "MB"):
        n /= 1024
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
    return f"{n / 1024:.1f} GB"


def tilde(p: Path | str, home: Path) -> str:
    s = str(p)
    h = str(home)
    return "~" + s[len(h):] if s == h or s.startswith(h + "/") else s


def read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(str(p), json.dumps(data, indent=1, sort_keys=True) + "\n")


def result(items: int = 0, bytes_freed: int = 0, error: str | None = None,
           **extra) -> dict:
    return {"items": items, "bytes_freed": bytes_freed, "error": error, **extra}
