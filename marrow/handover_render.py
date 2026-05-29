"""Handover shared plumbing for the diff-based 3-section file.

The diff-apply itself lives in handover_diff.py. This module keeps the pieces
both share: the rendered-path anchor, the template skeleton, flock, atomic
write, and the snapshot/overwritten audit trail used for rollback.

Output: DATA_DIR/handover.md.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from . import config
from .dashboard import _atomic_write

_TEMPLATE_PATH = Path(__file__).parent / "handover_template.md"

# Sandwich markers from the template (top-section host for dashboard sync).
_SEP_OPEN = "<!-- marrow:top:start -->"
_SEP_CLOSE = "<!-- marrow:top:end -->"

_RENDERED_PATH = config.DATA_DIR / "handover.md"

_LOCK_RETRIES = 3
_LOCK_BACKOFF = 0.05


# ── template helpers ────────────────────────────────────────────────────────

def _strip_instruction_lines(text: str) -> str:
    """Remove `> ` system instruction lines. Preserve trailing newline so \
downstream regex inject points keep their `\\n` anchor."""
    kept = [ln for ln in text.splitlines() if not ln.startswith("> ")]
    out = "\n".join(kept)
    if text.endswith("\n") and not out.endswith("\n"):
        out += "\n"
    return out


def render_skeleton(conn: sqlite3.Connection) -> str:
    """Build template body without top-section markers, no stamp, current ts."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    template = _strip_instruction_lines(template)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    template = template.replace("{{YYYY-MM-DD HH:MM}}", now_str)
    # Strip the entire top section (markers + content between them).
    i = template.find(_SEP_OPEN)
    j = template.find(_SEP_CLOSE)
    if i != -1 and j != -1 and j > i:
        template = template[:i] + template[j + len(_SEP_CLOSE):]
    return template.lstrip("\n")


# ── audit snapshot ─────────────────────────────────────────────────────────

def _write_snapshot_audit(conn: sqlite3.Connection, sid: str, prior: str) -> None:
    """Persist the pre-overwrite handover.md body to audit_log for rollback."""
    if not prior:
        return
    digest = hashlib.sha256(prior.encode("utf-8")).hexdigest()
    head = prior[:200].replace("\n", "\\n")
    summary = f"sha256={digest} head={head} body={prior}"
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_log (target_table, target_id, action, summary)"
                " VALUES ('handover', ?, 'handover_snapshot', ?)",
                (sid, summary),
            )
    except sqlite3.Error:
        pass


def _load_last_snapshot_body(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT summary FROM audit_log"
        " WHERE target_table='handover' AND action='handover_snapshot'"
        " ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row or not row["summary"]:
        return ""
    i = row["summary"].find("body=")
    return row["summary"][i + 5:] if i >= 0 else ""


# ── flock ───────────────────────────────────────────────────────────────────

def _acquire_flock(path: Path):
    """LOCK_EX with 3x 50ms backoff. Returns open fd or None."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    for attempt in range(_LOCK_RETRIES):
        fd = open(path, "r+", encoding="utf-8")
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except (BlockingIOError, OSError) as e:
            fd.close()
            if isinstance(e, OSError) and not isinstance(e, BlockingIOError):
                if e.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    return None
            if attempt == _LOCK_RETRIES - 1:
                return None
            time.sleep(_LOCK_BACKOFF)
    return None


def _release_flock(fd) -> None:
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
    finally:
        fd.close()


# ── overwritten-body audit (diff-apply uses this for rollback trail) ─────────

def _write_overwritten_audit(conn: sqlite3.Connection, sid: str,
                              prior: str) -> None:
    """Record the body we just overwrote, separate from the canonical snapshot.
    `_load_last_snapshot_body` reads only `handover_snapshot` rows; this row
    uses a different action so rollback can find the pre-overwrite text
    without polluting the diff baseline."""
    if not prior:
        return
    digest = hashlib.sha256(prior.encode("utf-8")).hexdigest()
    head = prior[:200].replace("\n", "\\n")
    summary = f"sha256={digest} head={head} body={prior}"
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_log (target_table, target_id, action, summary)"
                " VALUES ('handover', ?, 'handover_overwritten', ?)",
                (sid, summary),
            )
    except sqlite3.Error:
        pass
