import sqlite3

import pytest

from marrow import storage

PHASE1_TABLES = {
    "events", "threads", "milestones", "vocab", "stickers",
    "pit", "diary", "goose_bites", "alerts", "audit_log",
}
PHASE2_ABSENT = {"emotions", "people", "preferences", "dir"}


@pytest.fixture()
def db(tmp_path):
    conn = storage.init_db(str(tmp_path / "t.db"))
    yield conn
    conn.close()


def _names(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def test_phase1_tables_present(db):
    assert PHASE1_TABLES <= _names(db)


def test_phase2_tables_absent(db):
    assert not (PHASE2_ABSENT & _names(db))


def test_user_version(db):
    assert db.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION


def test_fts_synced_on_insert_update_delete(db):
    db.execute("INSERT INTO events(session_id,timestamp,role,content) "
               "VALUES('s','2026-05-17T00:00:00Z','user','hello marrow world')")
    db.commit()
    q = "SELECT rowid FROM events_fts WHERE events_fts MATCH 'marrow'"
    assert db.execute(q).fetchone() is not None
    rid = db.execute("SELECT id FROM events").fetchone()[0]
    db.execute("UPDATE events SET content='changed text' WHERE id=?", (rid,))
    db.commit()
    assert db.execute(q).fetchone() is None
    assert db.execute(
        "SELECT 1 FROM events_fts WHERE events_fts MATCH 'changed'"
    ).fetchone() is not None
    db.execute("DELETE FROM events WHERE id=?", (rid,))
    db.commit()
    assert db.execute(
        "SELECT 1 FROM events_fts WHERE events_fts MATCH 'changed'"
    ).fetchone() is None


def test_vec0_table_usable(db):
    cols = db.execute("PRAGMA table_info(events_vec)").fetchall()
    assert cols, "events_vec virtual table missing"


def test_init_idempotent(tmp_path):
    p = str(tmp_path / "i.db")
    storage.init_db(p).close()
    conn = storage.init_db(p)
    conn.execute("INSERT INTO events(session_id,timestamp,role,content) "
                 "VALUES('s','2026-05-17T00:00:00Z','user','x')")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    conn.close()


def test_foreign_key_set_null_on_vocab_delete(db):
    db.execute("INSERT INTO vocab(type,key) VALUES('cipher','P')")
    vid = db.execute("SELECT id FROM vocab").fetchone()[0]
    db.execute("INSERT INTO stickers(vocab_id,key,asset_path) VALUES(?,?,?)",
               (vid, "P", "/tmp/x.png"))
    db.execute("DELETE FROM vocab WHERE id=?", (vid,))
    db.commit()
    assert db.execute("SELECT vocab_id FROM stickers").fetchone()[0] is None
