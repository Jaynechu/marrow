"""Tests for marrow/goose_bites.py — deterministic bits mocked."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from marrow import goose_bites, storage


@pytest.fixture()
def db(tmp_path):
    p = str(tmp_path / "g.db")
    conn = storage.init_db(p)
    yield conn
    conn.close()


def _make_monthly(tmp_path: Path, date: str, lines: list[str]) -> Path:
    """Write a monthly md file with a day block, return its path."""
    month = date[:7]
    d = tmp_path / "语录"
    d.mkdir(parents=True, exist_ok=True)
    content = f"![[铁锅传奇版.png|524]]\n\n### {date}\n"
    for l in lines:
        content += l + "\n"
    p = d / f"{month}.md"
    p.write_text(content, encoding="utf-8")
    return p


# --- _parse_day_block --------------------------------------------------------

def test_parse_day_block_extracts_quotes(tmp_path, monkeypatch):
    monkeypatch.setattr(goose_bites, "_QUOTE_DIR", tmp_path / "语录")
    _make_monthly(tmp_path, "2026-05-01", [
        "- `00:25` 妈这版配色讲究嘎",
        "- `00:26` 妈这改对齐了嘎",
    ])
    result = goose_bites._parse_day_block("2026-05-01")
    assert result == ["妈这版配色讲究嘎", "妈这改对齐了嘎"]


def test_parse_day_block_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(goose_bites, "_QUOTE_DIR", tmp_path / "语录")
    result = goose_bites._parse_day_block("2026-05-99")
    assert result == []


def test_parse_day_block_skips_banner(tmp_path, monkeypatch):
    monkeypatch.setattr(goose_bites, "_QUOTE_DIR", tmp_path / "语录")
    _make_monthly(tmp_path, "2026-05-02", ["- `01:00` 嘎"])
    result = goose_bites._parse_day_block("2026-05-02")
    assert result == ["嘎"]
    assert not any("铁锅" in r for r in result)


def test_parse_day_block_stops_at_next_day_header(tmp_path, monkeypatch):
    monkeypatch.setattr(goose_bites, "_QUOTE_DIR", tmp_path / "语录")
    d = tmp_path / "语录"
    d.mkdir(parents=True, exist_ok=True)
    content = (
        "### 2026-05-01\n"
        "- `00:01` quote one\n"
        "### 2026-05-02\n"
        "- `00:02` quote two\n"
    )
    (d / "2026-05.md").write_text(content, encoding="utf-8")
    result = goose_bites._parse_day_block("2026-05-01")
    assert result == ["quote one"]


# --- single-candidate shortcut -----------------------------------------------

def test_select_single_candidate_skips_llm(tmp_path, monkeypatch, db):
    monkeypatch.setattr(goose_bites, "_QUOTE_DIR", tmp_path / "语录")
    _make_monthly(tmp_path, "2026-05-03", ["- `10:00` only one quote"])
    with patch.object(goose_bites, "_call_haiku") as mock_haiku:
        result = goose_bites.select_quote_for_date(db, "2026-05-03")
    mock_haiku.assert_not_called()
    assert result == "only one quote"


# --- Haiku call + fallback ---------------------------------------------------

def test_select_haiku_called_for_multiple_candidates(tmp_path, monkeypatch, db):
    monkeypatch.setattr(goose_bites, "_QUOTE_DIR", tmp_path / "语录")
    _make_monthly(tmp_path, "2026-05-04", [
        "- `01:00` quote A",
        "- `02:00` quote B",
    ])
    with patch.object(goose_bites, "_call_haiku", return_value="quote B") as mock_h:
        result = goose_bites.select_quote_for_date(db, "2026-05-04")
    mock_h.assert_called_once_with(["quote A", "quote B"])
    assert result == "quote B"


def test_select_haiku_fallback_on_none(tmp_path, monkeypatch, db):
    monkeypatch.setattr(goose_bites, "_QUOTE_DIR", tmp_path / "语录")
    _make_monthly(tmp_path, "2026-05-05", [
        "- `01:00` short",
        "- `02:00` longer quote here",
    ])
    with patch.object(goose_bites, "_call_haiku", return_value=None):
        result = goose_bites.select_quote_for_date(db, "2026-05-05")
    # Haiku returned None → no write, returns None
    assert result is None


def test_call_haiku_out_of_candidates_falls_back_to_longest():
    mock_client = MagicMock()
    mock_client.call.return_value = "some other text not in candidates"
    with patch("marrow.goose_bites.LLMClient", return_value=mock_client):
        result = goose_bites._call_haiku(["short", "longer candidate here"])
    assert result == "longer candidate here"


def test_call_haiku_llm_error_returns_none():
    with patch("marrow.goose_bites.LLMClient", side_effect=Exception("fail")):
        result = goose_bites._call_haiku(["a", "b"])
    assert result is None


# --- upsert behaviour --------------------------------------------------------

def test_upsert_insert_new_row(db):
    goose_bites._upsert(db, "2026-05-10", "test quote")
    row = db.execute(
        "SELECT date, bites, best, session_id, source_hash FROM goose_bites WHERE date='2026-05-10'"
    ).fetchone()
    assert row["bites"] == "test quote"
    assert row["best"] == 1
    assert row["session_id"] is None
    assert row["source_hash"] is None


def test_upsert_replace_existing_row(db):
    db.execute(
        "INSERT INTO goose_bites (date, bites, best) VALUES ('2026-05-11', 'old', 0)"
    )
    db.commit()
    goose_bites._upsert(db, "2026-05-11", "new quote")
    rows = db.execute(
        "SELECT bites, best FROM goose_bites WHERE date='2026-05-11'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["bites"] == "new quote"
    assert rows[0]["best"] == 1


def test_select_no_candidates_returns_none(tmp_path, monkeypatch, db):
    monkeypatch.setattr(goose_bites, "_QUOTE_DIR", tmp_path / "语录")
    # dir exists but no file for this month
    (tmp_path / "语录").mkdir()
    result = goose_bites.select_quote_for_date(db, "2026-06-01")
    assert result is None
    assert db.execute("SELECT COUNT(*) FROM goose_bites").fetchone()[0] == 0
