"""Entity-aware force-include for recall: surface events linked to named entities.

Reverse-match approach: iterate entities_live rows; for each row check if
name.lower() is a substring of query.lower(). No tokenizer dependency, fully
CJK-safe (catches 2-char names like (南南) that the trigram tokenizer / char-
split tokens silently drop).

Force-include rows are prepended in recall_fusion before ms_cap reservation.
"""
from __future__ import annotations

import math
import sqlite3


def entity_force_include(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
) -> list[dict]:
    """Return events force-linked to entities whose name appears in query.

    - Reverse substring match: name.lower() in query.lower().
    - Inner event fetch: LIKE-scan for name <3 chars (trigram tokenizer floor);
      else try FTS5 first, fall back to LIKE on empty.
    - Scores: 1.0 + 0.1 * log1p(mention_count).
    - Cap at limit // 2 (min 1).
    - Dedup by event id.
    """
    q_lower = query.lower().strip()
    if not q_lower:
        return []

    rows = conn.execute(
        "SELECT id, name, mention_count FROM entities_live"
    ).fetchall()
    matched: list[dict] = []
    for r in rows:
        name = r["name"] or ""
        if not name:
            continue
        if name.lower() in q_lower:
            matched.append({
                "id": r["id"],
                "name": name,
                "mention_count": r["mention_count"] or 0,
            })

    if not matched:
        return []

    # Longer names first — more specific (rules out (南) matching when (南南) is present).
    matched.sort(key=lambda e: len(e["name"]), reverse=True)

    force_cap = max(1, limit // 2)
    results: list[dict] = []
    seen_eid: set[int] = set()

    for entity in matched:
        if len(results) >= force_cap:
            break
        name = entity["name"]
        score = 1.0 + 0.1 * math.log1p(entity["mention_count"])

        event_rows: list = []
        if len(name) >= 3:
            try:
                fts_q = '"' + name.replace('"', '""') + '"'
                event_rows = conn.execute(
                    "SELECT e.id, e.session_id, e.timestamp, e.role, "
                    "e.content, e.channel, e.compressed "
                    "FROM events_fts f JOIN events e ON e.id = f.rowid "
                    "WHERE events_fts MATCH ? ORDER BY rank LIMIT ?",
                    (fts_q, force_cap * 2),
                ).fetchall()
            except Exception:
                event_rows = []

        if not event_rows:
            event_rows = conn.execute(
                "SELECT id, session_id, timestamp, role, content, "
                "channel, compressed FROM events "
                "WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (f"%{name}%", force_cap * 2),
            ).fetchall()

        for er in event_rows:
            if len(results) >= force_cap:
                break
            evid = er["id"]
            if evid in seen_eid:
                continue
            seen_eid.add(evid)
            results.append({
                "kind": "event",
                "id": evid,
                "session_id": er["session_id"],
                "timestamp": er["timestamp"],
                "role": er["role"],
                "content": er["content"],
                "channel": er["channel"],
                "compressed": er["compressed"],
                "bm25": 1.0,
                "vec": 0.0,
                "fts_hit": True,
                "score": score,
                "force_include": True,
            })

    return results
