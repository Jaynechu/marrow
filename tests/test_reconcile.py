"""Tests for marrow/reconcile.py — milestone md->DB reconcile."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from marrow import reconcile, storage, subpages


@pytest.fixture()
def db(tmp_path):
    p = str(tmp_path / "t.db")
    conn = storage.init_db(p)
    with conn:
        # pinned=1 = confirmed/subpage-eligible. Reconcile + render both
        # scope themselves to pinned=1 rows now; pinned=0 = candidate.
        conn.execute(
            "INSERT INTO milestones(scope,date,title,description,pinned) "
            "VALUES('us','2026-01-17','First meeting','In the rain',1)"
        )
        conn.execute(
            "INSERT INTO milestones(scope,date,title,pinned) "
            "VALUES('me','2026-03-01','Head of school award',1)"
        )
    conn.close()
    return p


def _render_to_md(db_path: str, folder: Path, state: Path) -> Path:
    conn = storage.connect(db_path)
    try:
        cfg = subpages.SubPageConfig(
            key="milestone",
            render=subpages.render_milestone,
            path=str(folder / "milestone.md"),
            state_dir=str(state),
        )
        subpages.write_subpage(cfg, conn, db=db_path)
    finally:
        conn.close()
    return folder / "milestone.md"


# ── 1. fresh DB -> render -> reconcile no-op ────────────────────────────────

def test_reconcile_noop_on_freshly_rendered(db, tmp_path):
    folder = tmp_path / "ny"
    state = tmp_path / "state"
    md = _render_to_md(db, folder, state)
    conn = storage.connect(db)
    try:
        rpt = reconcile.reconcile_milestones(conn, md)
    finally:
        conn.close()
    assert rpt.inserted == 0
    assert rpt.updated == 0
    assert rpt.deleted == 0
    assert rpt.unchanged == 2


# ── 2. md with new unanchored row -> insert ─────────────────────────────────

def test_reconcile_inserts_unanchored(db, tmp_path):
    folder = tmp_path / "ny"
    state = tmp_path / "state"
    md = _render_to_md(db, folder, state)
    text = md.read_text(encoding="utf-8")
    # Inject a new row under ## Me without an id anchor.
    new_line = "- 2026-05-22 **Round 2 milestone** — added by Lumi\n"
    text = text.replace("## Me\n\n", "## Me\n\n" + new_line)
    md.write_text(text, encoding="utf-8")

    conn = storage.connect(db)
    try:
        rpt = reconcile.reconcile_milestones(conn, md)
        rows = conn.execute(
            "SELECT id, title FROM milestones WHERE title='Round 2 milestone'"
        ).fetchall()
    finally:
        conn.close()
    assert rpt.inserted == 1
    assert len(rows) == 1

    # After re-render the new row should have an anchor.
    md2 = _render_to_md(db, folder, state)
    txt2 = md2.read_text()
    rid = rows[0]["id"]
    assert f"Round 2 milestone" in txt2
    assert f"<!-- id:{rid} -->" in txt2


# ── 3. md with edited title on anchored row -> update; updated_at advances ─

def test_reconcile_updates_and_advances_updated_at(db, tmp_path):
    folder = tmp_path / "ny"
    state = tmp_path / "state"
    md = _render_to_md(db, folder, state)
    # capture original updated_at
    conn = storage.connect(db)
    try:
        old = conn.execute(
            "SELECT id, updated_at FROM milestones WHERE title='First meeting'"
        ).fetchone()
    finally:
        conn.close()
    assert old is not None
    old_ts = old["updated_at"]

    # Edit the title.
    text = md.read_text().replace("First meeting", "First meeting EDITED")
    md.write_text(text)

    # Sleep just enough so timestamp differs (UTC second granularity).
    time.sleep(1.1)
    conn = storage.connect(db)
    try:
        rpt = reconcile.reconcile_milestones(conn, md)
        row = conn.execute(
            "SELECT title, updated_at, created_at FROM milestones WHERE id=?",
            (old["id"],),
        ).fetchone()
    finally:
        conn.close()
    assert rpt.updated == 1
    assert row["title"] == "First meeting EDITED"
    assert row["updated_at"] > old_ts
    assert row["updated_at"] >= row["created_at"]


# ── 4. md with anchored row removed -> delete + backup ─────────────────────

def test_reconcile_deletes_when_row_removed(db, tmp_path):
    folder = tmp_path / "ny"
    state = tmp_path / "state"
    md = _render_to_md(db, folder, state)
    text = md.read_text()
    # Strip the "First meeting" row.
    new_lines = [
        ln for ln in text.splitlines() if "First meeting" not in ln
    ]
    md.write_text("\n".join(new_lines) + "\n")

    conn = storage.connect(db)
    try:
        rpt = reconcile.reconcile_milestones(conn, md)
        remaining = conn.execute(
            "SELECT COUNT(*) c FROM milestones"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert rpt.deleted == 1
    assert remaining == 1
    # Backup taken because destructive.
    assert list(Path(md.parent).glob("milestone.*.bak.md"))


# ── 5. unchanged md -> no audit_log, no backup ──────────────────────────────

def test_reconcile_unchanged_is_inert(db, tmp_path):
    folder = tmp_path / "ny"
    state = tmp_path / "state"
    md = _render_to_md(db, folder, state)
    # Audit rows accumulate from the initial render? No, render doesn't audit.
    conn = storage.connect(db)
    try:
        before = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE target_table='milestones'"
        ).fetchone()["c"]
        rpt = reconcile.reconcile_milestones(conn, md)
        after = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE target_table='milestones'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert not rpt.any_change()
    assert after == before
    # No backup files.
    assert not list(Path(md.parent).glob("milestone.*.bak.md"))
