"""Diff-based apply for the 3-section handover (Done / Doing / Lumi's Note).

Doing identity is the `<!-- id:N -->` comment, NOT a text hash. apply_diff()
takes the parsed DOING_DIFF (CLOSE/UPDATE/KEEP/ADD by id) + NOTE_DONE remove
list and rewrites the file atomically under flock. Spec:
- id allocation: max(all `<!-- id:N -->` in Doing+Done) + 1.
- hand-edit reconcile vs last snapshot: id gone from file → tombstone (never
  revive); Doing block with no id → assign a fresh id, keep.
- CLOSE → Done line; UPDATE → replace block (id kept); KEEP → no-op; ADD →
  fresh id; any existing id the diff omitted → keep it (defensive).
- Done 24h roll-off every write. Note: verbatim except NOTE_DONE lines (matched
  via hash_bullet, tolerant of rephrase).
"""
from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from . import handover_render as _hr
from .handover_norm import hash_bullet

_ID_RE = re.compile(r"<!--\s*id:(\d+)\s*-->")
_DONE_TS_RE = re.compile(r"<!--\s*done:(\d+)\s*-->")
_DOING_HEAD_RE = re.compile(r"^\s*(?:#\d+\b|\d+\.\s|\[)")

_DONE_HEADER = "Done"
_DOING_HEADER = "Doing"
_NOTE_HEADER = "Lumi's Note"

_DONE_MAX_AGE = 24 * 3600  # rolling 24h window for ## Done


# Section boundary = next `## ` header or the handover stamp ONLY. Unlike
# handover_render's helpers this does NOT break on `^<!--`, because the Doing
# section legitimately holds `<!-- id:N -->` lines at column 0.

def _section_body(text: str, header: str) -> str:
    pat = re.compile(
        rf"^## {re.escape(header)}[ \t]*\n(.*?)(?=^## |^<!--\s*handover:|\Z)",
        re.MULTILINE | re.DOTALL)
    m = pat.search(text or "")
    return m.group(1).strip("\n") if m else ""


def _section_present(text: str, header: str) -> bool:
    return bool(re.search(
        rf"^## {re.escape(header)}[ \t]*$", text or "", re.MULTILINE))


def _inject_section(text: str, header: str, body: str) -> str:
    pat = re.compile(
        rf"(^## {re.escape(header)}[ \t]*\n)(.*?)(?=^## |^<!--\s*handover:|\Z)",
        re.MULTILINE | re.DOTALL)
    if not pat.search(text):
        return text
    safe = body if body.endswith("\n") else body + "\n"
    return pat.sub(lambda m: f"{m.group(1)}{safe}\n", text, count=1)


# ── block normalisation ─────────────────────────────────────────────────────

def _normalise_block(block: str) -> str:
    """Canonical stored form of a Doing thread: drop the id comment + leading
    `N.` ordinal + any `#<id>` head prefix, strip trailing whitespace."""
    lines = [ln for ln in block.splitlines() if not _ID_RE.search(ln)]
    if lines:
        head = re.sub(r"^\s*\d+\.\s*", "", lines[0], count=1).rstrip()
        lines[0] = re.sub(r"^#\d+\s*", "", head).strip()
    return "\n".join(ln.rstrip() for ln in lines).rstrip()


def _done_line_for(block: str) -> str:
    """## Done bullet text for a CLOSEd thread: `- [scope] title — <Current>`."""
    lines = _normalise_block(block).splitlines()
    head = lines[0] if lines else ""
    text = head if head.startswith("-") else f"- {head}"
    for ln in lines:
        m = re.match(r"\s*-\s*Current:\s*(.*)", ln)
        if m and m.group(1).strip():
            return f"{text} — {m.group(1).strip()}"
    return text


# ── section parsers ─────────────────────────────────────────────────────────

def parse_doing(body: str) -> tuple[dict[int, str], list[str]]:
    """Parse a `## Doing` body into ({id: normalised_block}, [no_id_block]).

    Thread head = `N.` / `#id` / `[scope]`; indented sub-lines belong to it.
    The `<!-- id:N -->` comment may stand on its own line or trail the head.
    No-id blocks → second list (hand-added)."""
    by_id: dict[int, str] = {}
    no_id: list[str] = []
    cur: list[str] = []

    def flush() -> None:
        if not cur:
            return
        raw = "\n".join(cur)
        ids = _ID_RE.findall(raw)
        norm = _normalise_block(raw)
        if not norm or norm.strip() in ("- N/A", "N/A"):
            return
        if ids:
            by_id[int(ids[-1])] = norm
        else:
            no_id.append(norm)

    for ln in (body or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if _ID_RE.fullmatch(s):  # id comment on its own line closes the block
            cur.append(ln)
            flush()
            cur = []
        elif _DOING_HEAD_RE.match(ln):
            flush()
            cur = [ln]
        elif cur:
            cur.append(ln)
        # else: junk before first head (lone `- N/A`) — ignored
    flush()
    return by_id, no_id


def parse_done(body: str) -> list[tuple[str, int]]:
    """`## Done` body → [(line, epoch)]. Lines with no `<!-- done:N -->` dropped."""
    out: list[tuple[str, int]] = []
    for ln in (body or "").splitlines():
        s = ln.strip()
        if not s or s in ("- N/A", "N/A"):
            continue
        m = _DONE_TS_RE.search(s)
        if not m:
            continue
        epoch = int(m.group(1))
        text = _DONE_TS_RE.sub("", s).rstrip()
        out.append((text, epoch))
    return out


def max_id(doing_body: str, done_body: str) -> int:
    """Highest id across both sections (0 if none)."""
    ids = [int(x) for x in _ID_RE.findall(doing_body or "")]
    ids += [int(x) for x in _ID_RE.findall(done_body or "")]
    return max(ids) if ids else 0


# ── renderers ───────────────────────────────────────────────────────────────

def render_doing(doing: dict[int, str]) -> str:
    """{id: block} → numbered threads + trailing id comments; ordinal renumbered
    1,2,3 by ascending id. Empty → `- N/A`."""
    if not doing:
        return "- N/A"
    parts: list[str] = []
    for n, ident in enumerate(sorted(doing), start=1):
        lines = doing[ident].splitlines()
        head = f"{n}. {lines[0]}" if lines else f"{n}."
        parts.append("\n".join([head] + lines[1:]) + f"\n<!-- id:{ident} -->")
    return "\n".join(parts)


def render_done(done: list[tuple[str, int]]) -> str:
    """Render [(line, epoch)] → bullets with `<!-- done:EPOCH -->`; [] → N/A."""
    if not done:
        return "- N/A"
    return "\n".join(f"{line} <!-- done:{epoch} -->" for line, epoch in done)


# ── core diff apply (pure) ──────────────────────────────────────────────────

def compute_apply(*, prior_text: str, last_snapshot: str, diff: dict,
                  note_done: list[str], now_epoch: int) -> str:
    """Pure transform: file body + last snapshot + diff → new body (no I/O)."""
    done_body = _section_body(prior_text, _DONE_HEADER)
    doing_body = _section_body(prior_text, _DOING_HEADER)
    note_body = (_section_body(prior_text, _NOTE_HEADER)
                 if _section_present(prior_text, _NOTE_HEADER) else None)

    doing, hand_added = parse_doing(doing_body)
    done = parse_done(done_body)
    next_id = max_id(doing_body, done_body) + 1

    # Hand-edit reconciliation vs last snapshot's Doing.
    snap_doing_body = _section_body(last_snapshot, _DOING_HEADER)
    snap_ids = {int(x) for x in _ID_RE.findall(snap_doing_body or "")}
    tombstoned = snap_ids - set(doing.keys())  # user hand-deleted these ids

    # Hand-added blocks (no id in current file) → assign fresh ids, keep.
    for blk in hand_added:
        doing[next_id] = blk
        next_id += 1

    # Apply verdicts. tombstoned ids are never revived.
    for cid in diff.get("close", []):
        if cid in tombstoned:
            continue
        blk = doing.pop(cid, None)
        if blk is None:
            continue
        done.append((_done_line_for(blk), now_epoch))

    for upd in diff.get("update", []):
        uid = upd.get("id")
        if uid in tombstoned or uid not in doing:
            continue
        norm = _normalise_block(upd.get("block", ""))
        if norm:
            doing[uid] = norm

    # KEEP is a no-op (id already retained). ADD assigns fresh ids.
    for blk in diff.get("add", []):
        norm = _normalise_block(blk)
        if norm:
            doing[next_id] = norm
            next_id += 1

    # ## Done 24h roll-off.
    done = [(line, ep) for line, ep in done
            if now_epoch - ep <= _DONE_MAX_AGE]

    # Note remove-done: drop lines that hash-match a NOTE_DONE entry.
    new_note = note_body
    if note_body is not None and note_done:
        remove_hashes = {hash_bullet(x) for x in note_done}
        kept = [ln for ln in note_body.splitlines()
                if hash_bullet(ln) not in remove_hashes]
        new_note = "\n".join(kept)

    # Compose the file from the current body + replaced sections.
    text = prior_text
    text = _inject_section(text, _DONE_HEADER, render_done(done))
    text = _inject_section(text, _DOING_HEADER, render_doing(doing))
    if new_note is not None:
        text = _inject_section(text, _NOTE_HEADER, new_note)
    return text


# ── public entry (I/O + flock + atomic) ──────────────────────────────────────

def apply_diff(conn: sqlite3.Connection, sid: str, diff: dict,
               note_done: list[str] | None = None) -> Path:
    """flock + read-or-seed + compute_apply + snapshot + atomic write. Lock-loss
    writes a `.partial.<sid>` file with an audit row, never crashes."""
    note_done = note_done or []
    now_epoch = int(time.time())
    path = _hr._RENDERED_PATH
    fd = _hr._acquire_flock(path)

    prior_text = _read_or_seed(conn, path)
    text = _stamp(compute_apply(
        prior_text=prior_text, last_snapshot=_hr._load_last_snapshot_body(conn),
        diff=diff, note_done=note_done, now_epoch=now_epoch), sid, now_epoch)

    if fd is None:
        partial = path.with_suffix(f".md.partial.{sid}")
        _hr._atomic_write(str(partial), text)
        _audit_lock_failed(conn, sid, partial)
        return partial
    try:
        _hr._write_snapshot_audit(conn, sid, text)
        if prior_text and prior_text.strip() != text.strip():
            _hr._write_overwritten_audit(conn, sid, prior_text)
        _hr._atomic_write(str(path), text)
    finally:
        _hr._release_flock(fd)
    return path


def _read_or_seed(conn: sqlite3.Connection, path: Path) -> str:
    """Current file body, or a fresh template skeleton if missing/empty."""
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        text = ""
    return text if text.strip() else _hr.render_skeleton(conn)


def _stamp(text: str, sid: str, now_epoch: int) -> str:
    now_str = datetime.fromtimestamp(now_epoch).strftime("%Y-%m-%d %H:%M")
    text = re.sub(
        r"^# Handover — \d{4}-\d{2}-\d{2} \d{2}:\d{2}[ \t]*$",
        f"# Handover — {now_str}", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"\n?<!--\s*handover: ready[^>]*-->\s*$", "\n", text)
    if not text.endswith("\n"):
        text += "\n"
    return f"{text}<!-- handover: ready sid:{sid} ts:{now_epoch} -->\n"


def _audit_lock_failed(conn: sqlite3.Connection, sid: str, partial: Path) -> None:
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_log (target_table, target_id, action, summary)"
                " VALUES ('handover', ?, 'handover_lock_failed', ?)",
                (sid, f"partial={partial.name}"))
    except sqlite3.Error:
        pass
