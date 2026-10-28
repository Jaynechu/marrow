"""housekeep.db passes: md_index tombstones, worktree slug shells, vec pass error."""
from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

import pytest

from _housekeep_shared import make_ctx
from marrow import storage
from marrow.housekeep import db as hdb


@pytest.fixture()
def db(tmp_path):
    conn = storage.init_db(str(tmp_path / "t.db"))
    yield conn
    conn.close()


def _tomb(conn, block_id, age_days):
    tomb = "NULL" if age_days is None else f"datetime('now', '-{age_days} days')"
    conn.execute(
        "INSERT INTO md_index (path, block_id, content_hash, last_seen_at, "
        f"tombstone_at) VALUES ('/p/{block_id}.md', ?, 'h', datetime('now'), {tomb})",
        (block_id,))


def test_prune_md_index_tombstones_deletes_old_only(db):
    for bid, age in (("live", None), ("recent", 5), ("boundary", 29),
                     ("old1", 40), ("old2", 120)):
        _tomb(db, bid, age)
    db.commit()
    assert hdb.prune_md_index_tombstones(db, 30) == 2
    left = {r["block_id"] for r in db.execute("SELECT block_id FROM md_index")}
    assert left == {"boundary", "live", "recent"}


def test_prune_md_index_tombstones_dry_run_counts_only(db):
    _tomb(db, "old", 40)
    db.commit()
    assert hdb.prune_md_index_tombstones(db, 30, dry_run=True) == 1
    assert db.execute("SELECT COUNT(*) FROM md_index").fetchone()[0] == 1


def test_prune_md_index_tombstones_empty_noop(db):
    assert hdb.prune_md_index_tombstones(db, 30) == 0


def _slugs(root: Path, names: list[str], age_days: float = 30) -> None:
    root.mkdir(parents=True, exist_ok=True)
    t = time.time() - age_days * 86400
    for n in names:
        (root / n).mkdir()
        (root / n / "s.jsonl").write_text("{}\n")
        for p in (root / n / "s.jsonl", root / n):
            os.utime(p, (t, t))


def test_prune_worktrees_removes_only_worktree_slugs(tmp_path):
    root = tmp_path / "projects"
    _slugs(root, ["-Users-x-CC-Lab-marrow", "-Users-x-marrow--claude-worktrees-agent-a"])
    (root / "stray-worktrees-file").write_text("x")
    assert hdb.prune_projects_worktrees(root, 7) == 1
    assert sorted(p.name for p in root.iterdir()) == [
        "-Users-x-CC-Lab-marrow", "stray-worktrees-file"]


def test_prune_worktrees_keeps_recently_active_slug(tmp_path):
    root = tmp_path / "projects"
    _slugs(root, ["-a--claude-worktrees-agent-old"])
    _slugs(root, ["-a--claude-worktrees-agent-live"], age_days=30)
    (root / "-a--claude-worktrees-agent-live" / "new.jsonl").write_text("{}\n")
    assert hdb.prune_projects_worktrees(root, 7) == 1
    assert [p.name for p in root.iterdir()] == ["-a--claude-worktrees-agent-live"]


def test_prune_worktrees_dry_run_keeps_dirs(tmp_path):
    root = tmp_path / "projects"
    _slugs(root, ["-Users-x-marrow--claude-worktrees-agent-a"])
    assert hdb.prune_projects_worktrees(root, 7, dry_run=True) == 1
    assert len(list(root.iterdir())) == 1


def test_prune_worktrees_missing_dir_noop(tmp_path):
    assert hdb.prune_projects_worktrees(tmp_path / "nope", 7) == 0


def test_vec_evict_stale_backup_is_pass_error(tmp_path):
    ctx = make_ctx(tmp_path)
    r = hdb.vec_evict(ctx)
    assert r["error"] and "vec_evict skipped" in r["error"]


def test_vec_evict_fresh_backup_ok(tmp_path):
    ctx = make_ctx(tmp_path)
    (ctx.backup_root / "daily" / f"marrow-{date.today().isoformat()}.db").touch()
    r = hdb.vec_evict(ctx)
    assert r["error"] is None and r["items"] == 0


def test_dry_run_connection_is_read_only(tmp_path):
    ctx = make_ctx(tmp_path, dry_run=True)
    conn = hdb.connect(ctx)
    try:
        with pytest.raises(Exception, match="readonly"):
            conn.execute("DELETE FROM md_index")
    finally:
        conn.close()
