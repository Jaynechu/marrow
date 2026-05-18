"""SessionEnd code-only transcript clean. CC .jsonl -> event rows.

Keep human dialogue verbatim (user + assistant text blocks). Drop tool_use /
tool_result / thinking / system / attachment / meta / sidechain noise.
Deterministic, no LLM. Output feeds repo.archive_events (idempotent).
"""
from __future__ import annotations

import json
import re

# Buddy MCP appends an invisible end-of-turn HTML comment to assistant text
# (<!-- buddy: ... -->). It is a legal text block so the type-based filter
# below never sees it; strip it here or it leaks into events -> digest ->
# diary as if 铁锅 were a speaker.
_BUDDY = re.compile(r"\s*<!--\s*buddy\s*:.*?-->", re.S | re.I)


def is_headless(jsonl_path: str) -> bool:
    """True if this transcript is a spawned headless `claude -p` run.

    Structural marker, payload-independent: CC tags every user/assistant
    line with `entrypoint` — interactive sessions carry "cli", SDK/headless
    spawns (prompt-lint haiku, diary digest, any subprocess claude) carry
    "sdk-cli". Those are not real sessions and must never reach events.
    Absent entrypoint (legacy CC) -> treat as real, don't silently drop.
    """
    try:
        fh = open(jsonl_path, encoding="utf-8")
    except FileNotFoundError:
        return False
    with fh as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("type") not in ("user", "assistant"):
                continue
            ep = o.get("entrypoint")
            return ep is not None and ep != "cli"
    return False


def _text(content) -> str:
    if isinstance(content, str):
        s = content
    elif isinstance(content, list):
        s = "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
            and b.get("text")
        )
    else:
        return ""
    return _BUDDY.sub("", s).strip()


def clean(jsonl_path: str) -> list[dict]:
    rows: list[dict] = []
    if is_headless(jsonl_path):
        return rows  # spawned claude -p (lint/digest): not a real session
    try:
        fh = open(jsonl_path, encoding="utf-8")
    except FileNotFoundError:
        return rows  # unflushed/headless transcript: nothing to clean, not an error
    with fh as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("type") not in ("user", "assistant"):
                continue
            if o.get("isMeta") or o.get("isSidechain"):
                continue
            msg = o.get("message") or {}
            text = _text(msg.get("content"))
            if not text:
                continue
            rows.append({
                "session_id": o.get("sessionId") or o.get("session_id") or "",
                "timestamp": o.get("timestamp", ""),
                "role": msg.get("role") or o.get("type"),
                "content": text,
                "channel": "cli",
            })
    return rows
