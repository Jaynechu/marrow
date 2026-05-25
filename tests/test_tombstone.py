"""Tests for handover_norm + tombstone Protocol + AuditLogTombstoneStore."""
from __future__ import annotations

import pytest

from marrow import storage
from marrow.handover_norm import (bullet_lines, hash_bullet, normalize_bullet)
from marrow.tombstone import (AuditLogTombstoneStore, diff_user_removed,
                              filter_tombstoned, record_user_deletes)


@pytest.fixture()
def conn(tmp_path):
    db = str(tmp_path / "t.db")
    c = storage.init_db(db)
    yield c
    c.close()


# ── handover_norm ─────────────────────────────────────────────────────────

def test_normalize_strips_bullet_marker_and_whitespace():
    assert normalize_bullet("- hello world") == "hello world"
    assert normalize_bullet("  *  hello   world  ") == "hello world"
    assert normalize_bullet("+ HELLO WORLD") == "hello world"


def test_normalize_unifies_cjk_punct():
    a = normalize_bullet("- 修了 bug，提交了！")
    b = normalize_bullet("- 修了 bug, 提交了!")
    assert a == b


def test_hash_stable_across_punct_and_case():
    a = hash_bullet("- Hello, World!")
    b = hash_bullet("* hello， world！")
    c = hash_bullet("+ HELLO,   WORLD!  ")
    assert a == b == c


def test_hash_different_for_different_content():
    assert hash_bullet("- hello world") != hash_bullet("- hello earth")


def test_bullet_lines_only_real_bullets():
    text = "intro\n- a\n* b\n+ c\nnot a bullet\n-incorrect (no space)\n"
    out = bullet_lines(text)
    assert out == ["- a", "* b", "+ c"]


# ── AuditLogTombstoneStore ───────────────────────────────────────────────

def test_audit_store_tombstone_and_list(conn):
    store = AuditLogTombstoneStore(conn)
    store.tombstone("hash-a", summary="bullet a")
    store.tombstone("hash-b", summary="bullet b")
    assert store.list_tombstones() == {"hash-a", "hash-b"}


def test_audit_store_tombstone_dedup_returns_unique_set(conn):
    store = AuditLogTombstoneStore(conn)
    store.tombstone("hash-a", summary="one")
    store.tombstone("hash-a", summary="another")  # duplicate insertion
    assert store.list_tombstones() == {"hash-a"}


def test_audit_store_clear_tombstone(conn):
    store = AuditLogTombstoneStore(conn)
    store.tombstone("hash-a", summary="bullet a")
    store.tombstone("hash-b", summary="bullet b")
    store.clear_tombstone("hash-a")
    assert store.list_tombstones() == {"hash-b"}


def test_audit_store_record_and_get_hash_no_op(conn):
    """Placeholder impl: record/get_hash are no-ops until md_index ships."""
    store = AuditLogTombstoneStore(conn)
    store.record_block("blk-1", "h1")
    assert store.get_hash("blk-1") is None


# ── filter_tombstoned ────────────────────────────────────────────────────

def test_filter_drops_matching_hashes():
    bullets = ["- keep me", "- drop me"]
    tomb = {hash_bullet("- drop me")}
    assert filter_tombstoned(bullets, tomb) == ["- keep me"]


def test_filter_empty_set_keeps_everything():
    bullets = ["- a", "- b", "- c"]
    assert filter_tombstoned(bullets, set()) == bullets


# ── diff_user_removed ────────────────────────────────────────────────────

def test_diff_finds_removed_bullets():
    prior = "## A\n- keep\n- remove me\n## B\n- also remove\n"
    current = "## A\n- keep\n## B\n"
    removed = diff_user_removed(prior, current)
    assert "- remove me" in removed
    assert "- also remove" in removed
    assert "- keep" not in removed


def test_diff_identical_returns_empty():
    text = "## A\n- one\n- two\n"
    assert diff_user_removed(text, text) == []


def test_diff_ignores_punctuation_drift():
    """Re-rephrased same bullet (punct diff only) is NOT a removal."""
    prior = "- hello, world!"
    current = "- hello， world！"
    assert diff_user_removed(prior, current) == []


# ── record_user_deletes ──────────────────────────────────────────────────

def test_record_user_deletes_tombstones_diff(conn):
    store = AuditLogTombstoneStore(conn)
    prior = "- keep\n- drop\n"
    current = "- keep\n"
    n = record_user_deletes(store, prior, current)
    assert n == 1
    assert hash_bullet("- drop") in store.list_tombstones()


def test_record_user_deletes_tombstone_survives_resave(conn):
    """End-to-end: user-deleted bullet stays gone after the next sonnet emit
    re-includes it. Render filters via the tombstone hash."""
    store = AuditLogTombstoneStore(conn)
    prior = "- decision X\n- decision Y\n"
    edited = "- decision X\n"  # user removed Y
    record_user_deletes(store, prior, edited)

    # Sonnet re-emits Y in the next session.
    resaved_bullets = ["- decision X", "- decision Y"]
    filtered = filter_tombstoned(resaved_bullets, store.list_tombstones())
    assert filtered == ["- decision X"]
