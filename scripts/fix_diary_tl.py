"""Fix polluted diary.tl_line rows.

Rows where tl_line matches "MM-DD Day 【tone】" (rendered output written by
an early version of reconcile_timeline before the prefix-strip was added)
or is empty/whitespace-only are NULLed out.

Usage:
    python3 scripts/fix_diary_tl.py --db /path/to/marrow.db   # dry-run (default)
    python3 scripts/fix_diary_tl.py --db /path/to/marrow.db --apply

Always test against a DB copy first:
    cp ~/.config/marrow/marrow.db /tmp/marrow-fix-test.db
    python3 scripts/fix_diary_tl.py --db /tmp/marrow-fix-test.db
    python3 scripts/fix_diary_tl.py --db /tmp/marrow-fix-test.db --apply
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys

_RENDERED_DAY_RE = re.compile(r"^\d{2}-\d{2}\s+Day\s+【.+】\s*$")


def find_polluted(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return [(date, tl_line)] for rows that need NULLing."""
    rows = conn.execute(
        "SELECT date, tl_line FROM diary WHERE tl_line IS NOT NULL ORDER BY date"
    ).fetchall()
    bad: list[tuple[str, str]] = []
    for r in rows:
        tl = (r["tl_line"] or "").strip()
        if not tl or _RENDERED_DAY_RE.match(tl):
            bad.append((r["date"], r["tl_line"]))
    return bad


def main() -> None:
    parser = argparse.ArgumentParser(description="Null out polluted diary.tl_line rows")
    parser.add_argument("--db", required=True, help="Path to marrow.db")
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    bad = find_polluted(conn)
    if not bad:
        print("No polluted rows found.")
        conn.close()
        return

    print(f"{'DRY-RUN: ' if not args.apply else ''}Found {len(bad)} polluted row(s):\n")
    for date, tl in bad:
        print(f"  {date}  tl_line={tl!r}")

    if not args.apply:
        print(f"\nDry-run: {len(bad)} row(s) would be NULLed. Pass --apply to execute.")
        conn.close()
        return

    with conn:
        for date, _ in bad:
            conn.execute(
                "UPDATE diary SET tl_line = NULL WHERE date = ?", (date,)
            )
        conn.execute(
            "INSERT INTO audit_log (target_table, target_id, action, summary)"
            " VALUES ('diary', 'bulk', 'fix_diary_tl', ?)",
            (f"NULLed {len(bad)} polluted tl_line rows: "
             + ", ".join(d for d, _ in bad),),
        )
    print(f"\nApplied: {len(bad)} row(s) NULLed.")
    conn.close()


if __name__ == "__main__":
    main()
