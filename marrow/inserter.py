"""Block-level inserter — md is SoT, hand-edits always win.

Phase 3 (Plan M wave 1): replaces the full-page render → atomic-overwrite
flow for subpages. Once a block lives in md, the inserter never rewrites
it — DB updates only land via "user deletes the block + inserter re-inserts
the fresh version". Tombstones block resurrection of user-deleted blocks.

Cold start (file absent OR no markers found): bootstrap the file fresh
by emitting all rows. The first auto-write records every block in
md_index so the next pass can ride the same contract.

API:
- InserterSpec — declarative subpage contract
- write_subpage_inserter(spec, conn, store) — entry point
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .md_index import TombstoneStore, parse_blocks

# Marker emitted around the auto-managed block. Same shape as legacy
# subpages so dashboard ## Content links stay stable.
_M0 = "<!-- marrow:{key}:start -->"
_M1 = "<!-- marrow:{key}:end -->"


def _hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _atomic_write(path: str, data: str) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".mrw.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@dataclass
class InserterSpec:
    """Declarative subpage contract for the block-level inserter.

    group_by:
    - "append"  — flat list, new rows append at file tail (profile, wallet).
    - "tag"     — section per categorical key (memes Personal/Public, stickers).
    - "date"    — section per date or date-range (diary, goose, milestone).
    - "none"    — single section, ordered by row order.

    section_of(row) returns the section label. section_order(labels) returns
    the canonical display order. Sections appear in the order returned by
    section_order; new sections append at the end of the canonical list.
    """
    key: str
    path: str
    fetch: Callable[[sqlite3.Connection], list[dict]]
    block_id_of: Callable[[dict], str]
    render_row: Callable[[dict], str]
    group_by: str = "append"
    section_of: Callable[[dict], str] = field(default=lambda _r: "")
    section_order: Callable[[Iterable[str]], list[str]] = field(
        default=lambda labels: sorted(set(labels)),
    )
    render_section_header: Callable[[str], str] = field(
        default=lambda label: f"## {label}",
    )
    empty_message: str = "_(none yet)_"

    def m0(self) -> str:
        return _M0.format(key=self.key)

    def m1(self) -> str:
        return _M1.format(key=self.key)


# ── public entry ──────────────────────────────────────────────────────────


def write_subpage_inserter(spec: InserterSpec, conn: sqlite3.Connection,
                           store: TombstoneStore) -> dict[str, int]:
    """Render `spec.path` in inserter mode.

    Returns counts: {bootstrapped, preserved, appended, tombstoned_skipped}.

    Contract — md hand-edits always win:
    - Cold start (file absent OR no markers) → bootstrap full emission,
      record baselines in store.
    - For each DB row r with block_id b:
      - b already in md → skip (md wins; never overwrite existing block).
      - b absent from md AND tombstoned in store → skip (no resurrection).
      - b absent from md AND not tombstoned → append at section.
    - md blocks whose id is not in the DB row set are left alone — they
      may be hand-added rows the watcher syncs next cycle. The inserter
      never deletes user content.
    """
    rows = spec.fetch(conn)
    path = spec.path
    counts = {"bootstrapped": 0, "preserved": 0,
              "appended": 0, "tombstoned_skipped": 0}

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if os.path.exists(path):
        existing = Path(path).read_text(encoding="utf-8")

    md_blocks, has_markers = parse_blocks(existing)
    md_ids = {b.block_id for b in md_blocks}

    if not has_markers:
        # Cold start — bootstrap full file.
        text = _bootstrap(spec, rows)
        _atomic_write(path, text)
        for r in rows:
            bid = spec.block_id_of(r)
            store.record_block(path, bid, _hash(spec.render_row(r)))
            counts["bootstrapped"] += 1
        return counts

    tombstoned = {tid for tid, _ts in store.list_tombstones(path)}
    new_rows_by_section: dict[str, list[tuple[str, str]]] = {}
    for r in rows:
        bid = spec.block_id_of(r)
        if bid in md_ids:
            counts["preserved"] += 1
            continue
        if bid in tombstoned:
            counts["tombstoned_skipped"] += 1
            continue
        section = spec.section_of(r)
        body = spec.render_row(r)
        new_rows_by_section.setdefault(section, []).append((bid, body))

    if new_rows_by_section:
        existing = _append_new_rows(spec, existing, new_rows_by_section)
        for _sec, items in new_rows_by_section.items():
            for bid, body in items:
                store.record_block(path, bid, _hash(body))
                counts["appended"] += 1
        _atomic_write(path, existing)

    return counts


# ── helpers ────────────────────────────────────────────────────────────────


def _bootstrap(spec: InserterSpec, rows: list[dict]) -> str:
    """Render full file fresh. Sections in canonical order."""
    out: list[str] = [spec.m0(), ""]
    if not rows:
        out.append(spec.empty_message)
        out.append("")
        out.append(spec.m1())
        out.append("")
        return "\n".join(out)
    sections: dict[str, list[dict]] = {}
    for r in rows:
        sections.setdefault(spec.section_of(r), []).append(r)
    labels = spec.section_order(sections.keys())
    for label in labels:
        if label:
            out.append(spec.render_section_header(label))
            out.append("")
        for r in sections.get(label, []):
            out.append(spec.render_row(r))
            out.append("")
    out.append(spec.m1())
    out.append("")
    return "\n".join(out)


def _append_new_rows(spec: InserterSpec, text: str,
                     new_by_section: dict[str, list[tuple[str, str]]]) -> str:
    """Insert new rows under their section header. If the section header
    is missing, append the header + rows just before the end marker.

    Behaviour is deliberately additive — never re-orders existing user content.
    """
    end_marker = spec.m1()
    end_idx = text.find(end_marker)
    if end_idx < 0:
        # No end marker — treat the entire file as the block, append at EOF.
        end_idx = len(text)
    section_labels = spec.section_order(new_by_section.keys())
    inserts: list[str] = []
    for label in section_labels:
        items = new_by_section.get(label, [])
        if not items:
            continue
        if label:
            header = spec.render_section_header(label)
            h_idx = text.find(header, 0, end_idx)
            if h_idx >= 0:
                cursor = text.find("\n##", h_idx + len(header))
                if cursor < 0 or cursor > end_idx:
                    cursor = end_idx
                addition = "\n".join(
                    body + "\n" for _bid, body in items
                )
                text = text[:cursor] + "\n" + addition + text[cursor:]
                # end_idx may have shifted if cursor < end_idx.
                end_idx = text.find(end_marker)
                if end_idx < 0:
                    end_idx = len(text)
                continue
            inserts.append(header)
            inserts.append("")
        for _bid, body in items:
            inserts.append(body)
            inserts.append("")
    if inserts:
        prelude = "\n".join(inserts) + "\n"
        text = text[:end_idx] + prelude + text[end_idx:]
    return text
