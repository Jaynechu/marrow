"""atlas — dir-tree subpage: parse, reconcile, render helpers, fs walk.

Public API:
- reconcile_atlas(conn, md_path) — md heading tree -> db upsert/delete
- atlas_sweep_fs(conn) — depth-aware walk: stub new dirs, mark vanished stale
- _heading_level(path, root) — compute h-level (2-6) for a path under root
- _root_shorthand(root) — ~/path display form

Each atlas row = one directory. depth=0 means "don't auto-expand children".
stale=1 means fs walk could not find the path (never deleted; preserves fields).
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ~/.claude whitelisted top-level entries — only these are recurse-able.
# S2a (DriftWatcher) may later expose CLAUDE_WHITELIST; if it's there import
# it, otherwise fall back to this hard-coded set.
# TODO: dedupe after S2a merges and exposes drift_sweep.CLAUDE_WHITELIST.
try:
    from .drift_sweep import CLAUDE_WHITELIST  # type: ignore[attr-defined]
except ImportError:
    CLAUDE_WHITELIST: frozenset[str] = frozenset({
        "CLAUDE.md", "rules", "commands", "skills",
        "agents", "output-styles", "hooks", "keybindings.json",
        "settings.json",
    })

try:
    from .drift_sweep import EXCLUDE_DIRS_TREE
except ImportError:
    EXCLUDE_DIRS_TREE: set[str] = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
    }

_CLAUDE_ROOT = Path.home() / ".claude"

_NOW = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())  # noqa: E731

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _root_shorthand(root: str | Path) -> str:
    """Absolute path → `~/relative/` display form."""
    p = Path(root).expanduser().resolve()
    try:
        rel = p.relative_to(Path.home())
        return f"~/{rel}/"
    except ValueError:
        return str(p) + "/"


def _heading_level(path: str | Path, root: str | Path) -> int:
    """Return heading level 2–6 for a path relative to root.

    Root itself → h2 (used for section headers, not row headings).
    First-level child → h3. Each additional depth +1, capped at h6.
    """
    p = Path(path).expanduser().resolve()
    r = Path(root).expanduser().resolve()
    try:
        rel = p.relative_to(r)
        depth = len(rel.parts)  # 1 for direct child, 2 for grandchild …
    except ValueError:
        return 6
    return min(2 + depth, 6)


def _root_of(path: str | Path, roots: list[Path]) -> Path | None:
    """Return the AUTHORIZED_ROOT that is an ancestor of path, or None."""
    p = Path(path).expanduser().resolve()
    for root in roots:
        r = root.expanduser().resolve()
        try:
            p.relative_to(r)
            return r
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Render helpers (used by build_atlas_spec)
# ---------------------------------------------------------------------------


def _render_atlas_row(r: dict, roots: list[Path]) -> str:
    """Heading + bullet block for one atlas row.

    Heading level determined by depth relative to root.
    `(stale)` suffix when stale=1.
    Bullets: note, write_hint (as 'write'), naming_hint (as 'naming'), depth.
    Empty fields omitted; depth always rendered.
    """
    path = r["path"]
    root = _root_of(path, roots)
    level = _heading_level(path, root) if root else 6
    hashes = "#" * level
    name = Path(path).name + "/"
    stale_sfx = " (stale)" if r.get("stale") else ""
    lines: list[str] = [f"{hashes} {name}{stale_sfx}", ""]
    if r.get("note"):
        lines.append(f"- note: {r['note']}")
    if r.get("write_hint"):
        lines.append(f"- write: {r['write_hint']}")
    if r.get("naming_hint"):
        lines.append(f"- naming: {r['naming_hint']}")
    lines.append(f"- depth: {r.get('depth', 0)}")
    return "\n".join(lines)


def _section_header(root_path: str) -> str:
    return f"## {_root_shorthand(root_path)}"


# ---------------------------------------------------------------------------
# Parser — md heading tree → list[dict]
# ---------------------------------------------------------------------------

_H_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
_BULLET_RE = re.compile(
    r"^-\s+(note|write|naming|depth):\s*(.*)$"
)
_STALE_RE = re.compile(r"\s*\(stale\)\s*$")


def _parse_atlas_md(md_text: str, roots: list[Path]) -> list[dict]:
    """Parse atlas heading tree into list of row dicts.

    Each dict: {path, note, write_hint, naming_hint, depth}.
    Heading levels used to reconstruct absolute path:
    - ## = root section header (path = root absolute)
    - ### = first-level dir under root
    - #### / ##### / ###### = deeper levels

    Root stack: we track current path at each heading level to reconstruct
    children. Dir name stripped of trailing `/` and `(stale)` suffix.
    """
    rows: list[dict] = []

    # Map heading level -> path for ancestry reconstruction.
    # level_stack[N] = absolute Path at heading level N.
    level_stack: dict[int, Path] = {}

    cur_row: dict | None = None
    cur_root: Path | None = None

    def _flush():
        nonlocal cur_row
        if cur_row and cur_row.get("path"):
            rows.append(cur_row)
        cur_row = None

    for raw in md_text.splitlines():
        line = raw.rstrip()

        m = _H_RE.match(line)
        if m:
            _flush()
            level = len(m.group(1))
            raw_name = m.group(2)
            # Strip (stale) suffix before resolving path
            name = _STALE_RE.sub("", raw_name).rstrip("/").strip()

            if level == 2:
                # Section header — find matching root by shorthand or name
                path = _match_root(name, roots)
                cur_root = path
                level_stack = {2: path} if path else {}
                cur_row = None  # root rows are not db rows
                continue

            if cur_root is None:
                continue

            # Reconstruct absolute path from current level context
            parent_level = level - 1
            parent = level_stack.get(parent_level)
            if parent is None:
                # Try to walk up until we find a known level
                for lvl in range(parent_level - 1, 1, -1):
                    parent = level_stack.get(lvl)
                    if parent:
                        break
            if parent is None:
                continue

            abs_path = parent / name
            level_stack[level] = abs_path
            # Invalidate deeper levels (sibling replaces children)
            for lvl in list(level_stack.keys()):
                if lvl > level:
                    del level_stack[lvl]

            cur_row = {
                "path": str(abs_path),
                "note": None,
                "write_hint": None,
                "naming_hint": None,
                "depth": 0,
            }
            continue

        if cur_row is None:
            continue

        bm = _BULLET_RE.match(line)
        if bm:
            field, value = bm.group(1), bm.group(2).strip()
            if field == "note":
                cur_row["note"] = value or None
            elif field == "write":
                cur_row["write_hint"] = value or None
            elif field == "naming":
                cur_row["naming_hint"] = value or None
            elif field == "depth":
                try:
                    cur_row["depth"] = int(value)
                except (ValueError, TypeError):
                    cur_row["depth"] = 0

    _flush()
    return rows


def _match_root(name: str, roots: list[Path]) -> Path | None:
    """Match section header name (e.g. `~/cc-lab/` or `/abs/path/`) to a root."""
    home = Path.home()
    # Normalise: strip trailing slash, expand ~/
    stripped = name.rstrip("/")
    if stripped.startswith("~/"):
        stripped = str(home / stripped[2:])
    # Try to resolve the name directly as an absolute path first
    try:
        candidate = Path(stripped).resolve()
        for root in roots:
            r = root.expanduser().resolve()
            if r == candidate:
                return r
    except Exception:
        pass
    # Fall back: match by name or relative-from-home
    clean = stripped.lstrip("/")
    for root in roots:
        r = root.expanduser().resolve()
        try:
            rel = str(r.relative_to(home))
            if rel == clean or r.name == clean:
                return r
        except ValueError:
            pass
        if r.name == clean or str(r) == clean or str(r) == stripped:
            return r
    return None


# ---------------------------------------------------------------------------
# Reconcile
# ---------------------------------------------------------------------------


def reconcile_atlas(conn: sqlite3.Connection, md_path: Path) -> int:
    """Parse atlas.md heading tree → upsert into atlas table.

    Paths in md → upsert (preserves stale flag from db, updates fields).
    Paths in db NOT in md → DELETE (user explicitly removed the row).
    Returns number of rows changed (insert + update + delete).
    """
    from . import drift_sweep
    roots = [r.expanduser().resolve() for r in drift_sweep.AUTHORIZED_ROOTS]

    md_path = Path(md_path)
    if not md_path.exists():
        return 0

    text = md_path.read_text(encoding="utf-8")
    md_rows = _parse_atlas_md(text, roots)

    now = _NOW()
    changed = 0

    with conn:
        md_paths = {r["path"] for r in md_rows}

        # Upsert rows present in md
        for r in md_rows:
            conn.execute(
                "INSERT INTO atlas (path, note, write_hint, naming_hint,"
                " depth, stale, updated_at)"
                " VALUES (?, ?, ?, ?, ?, 0, ?)"
                " ON CONFLICT(path) DO UPDATE SET"
                "  note=excluded.note,"
                "  write_hint=excluded.write_hint,"
                "  naming_hint=excluded.naming_hint,"
                "  depth=excluded.depth,"
                "  updated_at=excluded.updated_at",
                (r["path"], r.get("note"), r.get("write_hint"),
                 r.get("naming_hint"), r.get("depth", 0), now),
            )
            changed += 1

        # Delete db rows not present in md. Two protections:
        # 1. Root rows (## ~/root/ are section markers, parser intentionally
        #    skips them — would otherwise be deleted on every reconcile and
        #    depth-aware sweep would lose its seeds).
        # 2. Stub-only rows (no manual hint fields) — these are produced by
        #    atlas_sweep_fs and not yet rendered to md. Without this guard,
        #    sweep→reconcile→render in a single refresh would delete every
        #    new stub before render saw it. User-modified rows (any hint
        #    non-null) still get deleted when removed from md.
        root_strs = {str(r) for r in roots}
        db_rows = conn.execute(
            "SELECT path, note, write_hint, naming_hint FROM atlas"
        ).fetchall()
        for row in db_rows:
            path = row[0]
            if path in md_paths or path in root_strs:
                continue
            has_manual = any(v not in (None, "") for v in (row[1], row[2], row[3]))
            if not has_manual:
                continue
            conn.execute("DELETE FROM atlas WHERE path=?", (path,))
            changed += 1

    return changed


# ---------------------------------------------------------------------------
# fs walk
# ---------------------------------------------------------------------------

def _is_claude_allowed(entry: Path) -> bool:
    """Check if a path directly under ~/.claude is whitelisted for recursion."""
    return entry.name in CLAUDE_WHITELIST


def atlas_sweep_fs(conn: sqlite3.Connection) -> dict[str, int]:
    """Depth-aware fs walk: stub new dirs, mark vanished dirs stale.

    For each atlas row with depth > 0:
    - Walk subdirs up to that depth.
    - New subdir not in atlas → INSERT stub (depth=0, stale=0).
    - Existing row found → clear stale if it was stale.
    For each atlas row under a walked root:
    - Not found in walk results → set stale=1 (NEVER delete).

    Respects EXCLUDE_DIRS_TREE and ~/.claude whitelist.
    Returns {"stubbed": N, "unstaled": N, "staled": N}.
    """
    from . import drift_sweep
    roots = [r.expanduser().resolve() for r in drift_sweep.AUTHORIZED_ROOTS]
    counts = {"stubbed": 0, "unstaled": 0, "staled": 0}
    now = _NOW()

    # Load all rows with depth > 0 — these are the "expand" seeds.
    seed_rows = [
        dict(r) for r in conn.execute(
            "SELECT path, depth FROM atlas WHERE depth > 0"
        ).fetchall()
    ]

    # Collect all subdir paths found in fs for each seed.
    found_paths: set[str] = set()  # absolute path strings found during walk

    for row in seed_rows:
        seed_path = Path(row["path"])
        max_depth = row["depth"]
        if not seed_path.exists() or not seed_path.is_dir():
            continue
        _walk_collect(seed_path, max_depth, found_paths)

    # Collect all atlas paths that live UNDER any seed (children to check stale)
    seed_path_strs = {row["path"] for row in seed_rows}

    # Build set of all atlas paths that are under one of the seeds
    all_rows = {
        row[0]: row[1]
        for row in conn.execute("SELECT path, stale FROM atlas").fetchall()
    }

    # Paths to check stale = atlas rows that are NOT seeds themselves but
    # could be children of a seed.
    children_to_check: set[str] = set()
    for p in all_rows:
        if p in seed_path_strs:
            continue  # seeds themselves — stale via caller; not auto-managed
        # Is this path a child of any seed?
        pp = Path(p)
        for row in seed_rows:
            seed = Path(row["path"])
            try:
                pp.relative_to(seed)
                children_to_check.add(p)
                break
            except ValueError:
                continue

    with conn:
        # Stub new dirs
        for p_str in found_paths:
            if p_str not in all_rows:
                conn.execute(
                    "INSERT OR IGNORE INTO atlas"
                    " (path, note, write_hint, naming_hint, depth, stale, updated_at)"
                    " VALUES (?, '', NULL, NULL, 0, 0, ?)",
                    (p_str, now),
                )
                counts["stubbed"] += 1
            elif all_rows[p_str] == 1:
                # Was stale — it's back
                conn.execute(
                    "UPDATE atlas SET stale=0, updated_at=? WHERE path=?",
                    (now, p_str),
                )
                counts["unstaled"] += 1

        # Mark stale: children in atlas that weren't found in walk
        for p_str in children_to_check:
            if p_str not in found_paths and all_rows.get(p_str, 0) == 0:
                conn.execute(
                    "UPDATE atlas SET stale=1, updated_at=? WHERE path=?",
                    (now, p_str),
                )
                counts["staled"] += 1

    return counts


def _walk_collect(root: Path, max_depth: int, found: set[str],
                  _current_depth: int = 0) -> None:
    """Recursively collect direct subdir paths up to max_depth.

    Respects EXCLUDE_DIRS_TREE. For ~/.claude root, only recurses into
    CLAUDE_WHITELIST entries.
    """
    if _current_depth >= max_depth:
        return
    try:
        entries = sorted(root.iterdir())
    except (PermissionError, OSError):
        return

    is_claude = root.resolve() == _CLAUDE_ROOT.resolve()

    for entry in entries:
        if not entry.is_dir():
            continue
        if entry.name in EXCLUDE_DIRS_TREE:
            continue
        if is_claude and not _is_claude_allowed(entry):
            continue
        found.add(str(entry.resolve()))
        _walk_collect(entry, max_depth, found, _current_depth + 1)


# ---------------------------------------------------------------------------
# Seed after migration
# ---------------------------------------------------------------------------

def seed_atlas_from_roots(conn: sqlite3.Connection) -> int:
    """Insert one stub row per AUTHORIZED_ROOTS entry with depth=1.

    Called once after v12 migration (or first `mw refresh atlas`).
    Idempotent — INSERT OR IGNORE.
    """
    from . import drift_sweep

    now = _NOW()
    inserted = 0
    with conn:
        for root in drift_sweep.AUTHORIZED_ROOTS:
            p = root.expanduser().resolve()
            conn.execute(
                "INSERT OR IGNORE INTO atlas"
                " (path, note, write_hint, naming_hint, depth, stale, updated_at)"
                " VALUES (?, NULL, NULL, NULL, 1, 0, ?)",
                (str(p), now),
            )
            if conn.execute(
                "SELECT changes()"
            ).fetchone()[0]:
                inserted += 1
    return inserted
