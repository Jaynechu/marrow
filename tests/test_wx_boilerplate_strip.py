"""Tests for strip_wx_boilerplate() in marrow/transcript.py.

Covers all three synapse-wx boilerplate patterns:
  1. Media Read instruction block (<instruction>Use the Read tool to view:...)
  2. Bridge merge-note lines ([bridge: ...])
  3. Lone dot-sentinel lines (pure "." left after media bubble)

Also verifies: mixed real text preserved, CJK content unharmed, full-strip
returns empty string (the skip-recall signal in hooks.py).
"""
from __future__ import annotations

import pytest

from marrow.transcript import strip_wx_boilerplate


# ── pattern 1: media Read instruction ────────────────────────────────────────

def test_strips_read_instruction_appended():
    text = "你好吗\n\n<instruction>Use the Read tool to view: /Users/Gabrielle/.config/synapse-wx/media/Images/2026-06-12_030000_abc123.jpg</instruction>"
    assert strip_wx_boilerplate(text) == "你好吗"


def test_strips_read_instruction_multiple_paths():
    text = "check this\n\n<instruction>Use the Read tool to view: /path/a.jpg, /path/b.jpg</instruction>"
    assert strip_wx_boilerplate(text) == "check this"


def test_strips_read_instruction_case_insensitive():
    text = "hi\n\n<INSTRUCTION>Use the Read tool to view: /path/x.jpg</INSTRUCTION>"
    assert strip_wx_boilerplate(text) == "hi"


# ── pattern 2: merge note lines ───────────────────────────────────────────────

def test_strips_merge_note_exact():
    text = "[bridge: your previous reply was dropped — new messages arrived mid-turn. Answer the full merged message below.]\nhello there"
    assert strip_wx_boilerplate(text) == "hello there"


def test_strips_merge_note_defensive_any_bridge_line():
    text = "[bridge: something else entirely]\nreal message"
    assert strip_wx_boilerplate(text) == "real message"


def test_merge_note_mid_text_stripped():
    # merge note always prepended as first line, but defensive: strips anywhere
    text = "first line\n[bridge: dropped]\nsecond line"
    assert strip_wx_boilerplate(text) == "first line\nsecond line"


# ── pattern 3: dot sentinel ───────────────────────────────────────────────────

def test_strips_dot_sentinel_alone():
    # pure-media bubble: body is "." plus instruction; after instruction strip
    # only the dot remains
    text = "."
    assert strip_wx_boilerplate(text) == ""


def test_dot_sentinel_with_read_instruction():
    text = ".\n\n<instruction>Use the Read tool to view: /path/img.jpg</instruction>"
    assert strip_wx_boilerplate(text) == ""


def test_dot_sentinel_does_not_strip_real_content():
    # a dot mid-sentence or at start of a longer line must survive
    text = "check file.txt please"
    assert strip_wx_boilerplate(text) == "check file.txt please"


# ── mixed: real text preserved after stripping ───────────────────────────────

def test_real_text_preserved_after_all_patterns():
    text = (
        "[bridge: dropped]\n"
        "你今天怎么样\n\n"
        "<instruction>Use the Read tool to view: /path/img.jpg</instruction>"
    )
    assert strip_wx_boilerplate(text) == "你今天怎么样"


def test_cjk_content_preserved():
    text = "记得上次我说的那件事吗"
    assert strip_wx_boilerplate(text) == text


def test_cjk_with_bridge_note():
    text = "[bridge: your previous reply was dropped — new messages arrived mid-turn. Answer the full merged message below.]\n我想问你一件事"
    assert strip_wx_boilerplate(text) == "我想问你一件事"


# ── full-strip → empty string (skip-recall signal) ───────────────────────────

def test_full_strip_returns_empty_for_pure_instruction():
    text = "<instruction>Use the Read tool to view: /path/img.jpg</instruction>"
    assert strip_wx_boilerplate(text) == ""


def test_full_strip_returns_empty_for_dot_plus_instruction():
    text = ".\n\n<instruction>Use the Read tool to view: /path/img.jpg</instruction>"
    assert strip_wx_boilerplate(text) == ""


def test_full_strip_returns_empty_for_bridge_only():
    text = "[bridge: your previous reply was dropped — new messages arrived mid-turn. Answer the full merged message below.]"
    assert strip_wx_boilerplate(text) == ""


# ── no-op on plain non-wx text ────────────────────────────────────────────────

def test_noop_on_plain_cli_prompt():
    text = "what is the capital of France?"
    assert strip_wx_boilerplate(text) == text


def test_noop_on_empty_string():
    assert strip_wx_boilerplate("") == ""


def test_noop_on_whitespace_only():
    assert strip_wx_boilerplate("   \n  ") == ""


# ── time anchor preserved (marrow already strips it for recall) ───────────────

def test_time_anchor_not_stripped_by_this_helper():
    # The [time: ...] prefix is handled separately by _WX_TIME_PREFIX_RE;
    # strip_wx_boilerplate must not double-strip or break it.
    text = "[time: 2026-06-12 Fri 03:19 | gap: 0m] 你好"
    result = strip_wx_boilerplate(text)
    assert "[time:" in result
    assert "你好" in result
