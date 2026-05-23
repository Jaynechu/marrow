"""SessionEnd async LLM extraction worker.

CLI: python -m marrow.sessionend_async --sid <session_id>

Phase 2.5b: ping-pong isolation test + skip gate + idempotent audit.
Segment extraction (AFFECT/ENTITY/THREAD/MILESTONE/VOCAB/DIGEST/NARRATIVE)
lands in phase 2.5c — see TODO block below.
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import config, storage
from .llm import LLMClient

_LOGS_DIR = Path.home() / ".config" / "marrow" / "logs"

# Sentinel values written to audit_log.summary
_SUMMARY_OK = "ok"
_SUMMARY_SKIP = "skip:short_session"


def _write_audit(conn, sid: str, summary: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO audit_log (target_table, target_id, action, summary)"
            " VALUES ('events', ?, 'sessionend_extract', ?)",
            (sid, summary),
        )


def _user_event_count(conn, sid: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) c FROM events WHERE session_id = ? AND role = 'user'",
        (sid,),
    ).fetchone()
    return row["c"] if row else 0


def _already_done(conn, sid: str) -> bool:
    """Idempotent guard: if audit_log already shows ok for this sid, skip."""
    row = conn.execute(
        "SELECT 1 FROM audit_log"
        " WHERE action = 'sessionend_extract' AND target_id = ? AND summary = ?",
        (sid, _SUMMARY_OK),
    ).fetchone()
    return row is not None


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    sid: str | None = None
    i = 0
    while i < len(args):
        if args[i] == "--sid" and i + 1 < len(args):
            sid = args[i + 1]
            i += 2
        else:
            i += 1

    if not sid:
        print("usage: python -m marrow.sessionend_async --sid <session_id>",
              file=sys.stderr)
        return 2

    cfg = config.load()
    threshold = cfg.get("sessionend", {}).get("skip_turn_threshold", 5)
    db = config.db_path()
    conn = storage.connect(db)
    try:
        # Idempotent: already extracted successfully — nothing to do.
        if _already_done(conn, sid):
            return 0

        count = _user_event_count(conn, sid)
        if count <= threshold:
            _write_audit(conn, sid, _SUMMARY_SKIP)
            return 0

        # Ping-pong isolation test: CN body containing a PreToolUse-trigger-
        # style string to verify _ISOLATION flags suppress the global
        # prompt-guard.py hook. Without isolation this call would be blocked.
        ping_body = (
            "返回原文测试: (echo back this line verbatim, including the bracket). 老婆早。"
        )
        client = LLMClient(cfg=cfg)
        response = client.call(
            role="sessionend_pingpong",
            body=ping_body,
            tier="cheap",
        )
        if not response or not response.strip():
            raise ValueError("ping-pong returned empty response")

        # TODO(2.5c): segment extraction block — insert after ping-pong passes.
        # Segments to extract per docs/notes/2026-05-23_sessionend-llm-pipeline.md §2.3:
        #   ===AFFECT===     per-episode v/a/imp/label/entities
        #   ===ENTITY_CAND===  conf ≥0.8 → INSERT entities
        #   ===THREAD_CAND===  always → INSERT tasks
        #   ===MILESTONE_CAND=== conf ≥0.85 → INSERT milestones + alert + 7d confirm
        #   ===VOCAB_CAND===   conf ≥0.7 → INSERT vocab + use_count
        #   ===DIGEST===       compressed narrative; length flex by session density
        #   ===NARRATIVE===    handover async segment; atomic append to handover.md
        # Each segment gets its own prompt — BLOCKED pending Lumi confirm (§16.2).
        # One LLM call per segment; write DB rows atomically; re-run is idempotent.

        _write_audit(conn, sid, _SUMMARY_OK)
        return 0

    except Exception as e:  # noqa: BLE001
        try:
            _write_audit(conn, sid, f"fail:{type(e).__name__}")
        except Exception:
            pass
        return 1

    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
