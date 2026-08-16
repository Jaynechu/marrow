"""dim('upsert', kind=person|pref|place, ...) — recall-miss create, hit update.

Embedder is unavailable in tests, so match_entity falls back to the alias/name
overlap gate (cosine step no-ops with a warn). That is enough to exercise the
create / update / reject paths deterministically.
"""
from __future__ import annotations

import pytest

from marrow import config, daemon, storage


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    storage.init_db(db).close()
    monkeypatch.setattr(daemon, "_DB", db)
    monkeypatch.setattr(config, "db_path", lambda: db)
    return db


def _rows(db):
    conn = storage.connect(db)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, kind, name, fact, aliases, source FROM entities"
            " ORDER BY id").fetchall()]
    finally:
        conn.close()


def test_create_on_miss(env):
    out = daemon.dim("upsert", kind="person", name="王医生", fact="ED consultant")
    assert out["ok"] is True
    assert out["action"] == "create"
    rows = _rows(env)
    assert len(rows) == 1
    assert rows[0]["name"] == "王医生"
    assert rows[0]["fact"] == "ED consultant"
    assert rows[0]["source"] == "session"


def test_update_fact_on_name_hit(env):
    first = daemon.dim("upsert", kind="person", name="王医生", fact="ED consultant")
    out = daemon.dim("upsert", kind="person", name="王医生", fact="ED director now",
                      replace=True)
    assert out["action"] == "update"
    assert out["id"] == first["id"]
    rows = _rows(env)
    assert len(rows) == 1
    assert rows[0]["fact"] == "ED director now"


def test_update_fact_guard_blocks_differing_fact_without_replace(env):
    first = daemon.dim("upsert", kind="person", name="王医生", fact="ED consultant")
    out = daemon.dim("upsert", kind="person", name="王医生", fact="ED director now")
    assert out == {"ok": False, "action": "needs_review", "id": first["id"],
                    "kind": "person", "old_fact": "ED consultant",
                    "error": "existing fact differs; merge with old_fact and resend with replace=true"}
    rows = _rows(env)
    assert len(rows) == 1
    assert rows[0]["fact"] == "ED consultant"


def test_update_fact_guard_skips_alias_merge_too(env):
    first = daemon.dim("upsert", kind="person", name="王医生", aliases=["Dr Wang"],
                       fact="ED consultant")
    out = daemon.dim("upsert", kind="person", name="王医生", aliases=["老王"],
                      fact="ED director now")
    assert out["action"] == "needs_review"
    rows = _rows(env)
    assert len(rows) == 1
    assert "老王" not in (rows[0]["aliases"] or "")


def test_update_fact_equal_passes_through(env):
    first = daemon.dim("upsert", kind="person", name="王医生", fact="ED consultant")
    out = daemon.dim("upsert", kind="person", name="王医生", fact="ED consultant")
    assert out == {"ok": True, "action": "update", "id": first["id"], "kind": "person"}


def test_update_fact_none_leaves_fact_untouched(env):
    first = daemon.dim("upsert", kind="person", name="王医生", fact="ED consultant")
    out = daemon.dim("upsert", kind="person", name="王医生", aliases=["Dr Wang"])
    assert out == {"ok": True, "action": "update", "id": first["id"], "kind": "person"}
    rows = _rows(env)
    assert rows[0]["fact"] == "ED consultant"
    assert "Dr Wang" in rows[0]["aliases"]


def test_update_merges_aliases_on_alias_hit(env):
    daemon.dim("upsert", kind="person", name="王医生", aliases=["Dr Wang"])
    out = daemon.dim("upsert", kind="person", name="Dr Wang", aliases=["老王"])
    assert out["action"] == "update"
    rows = _rows(env)
    assert len(rows) == 1
    assert "老王" in rows[0]["aliases"]
    assert rows[0]["name"] == "王医生"  # canonical row untouched


def test_reject_unknown_kind(env):
    out = daemon.dim("upsert", kind="gadget", name="iPhone")
    assert out["ok"] is False
    assert "kind" in out["error"]
    assert _rows(env) == []


def test_reject_empty_name(env):
    out = daemon.dim("upsert", kind="person", name="   ")
    assert out["ok"] is False
    assert _rows(env) == []


def test_distinct_names_create_separate_rows(env):
    daemon.dim("upsert", kind="place", name="Clayton gym")
    daemon.dim("upsert", kind="place", name="Monash library")
    assert len(_rows(env)) == 2
