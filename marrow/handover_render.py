"""Sync handover.md skeleton renderer — §4.1, zero LLM calls, <500ms.

Rendered output goes to ~/.config/marrow/handover.md (NOT ~/cc-lab/marrow/handover.md).
Split rationale: ~/cc-lab/marrow/handover.md is hand-edited by Lumi each session;
writing there would clobber her content. The rendered skeleton is a separate
machine-written artifact read by SessionStart for inject.
"""
from __future__ import annotations

import re
import sqlite3
import tempfile
import os
from datetime import datetime
from pathlib import Path

from . import config
from . import top_sections
from .dashboard import _atomic_write

_TEMPLATE_PATH = Path(__file__).parent / "handover_template.md"

# Sandwich markers from the template
_SEP_OPEN = "—————以下这一段应该是跟dashboard的top一模一样的—————"
_SEP_CLOSE = "—————以上这一段应该是跟dashboard的top一模一样的—————"

_RENDERED_PATH = config.DATA_DIR / "handover.md"


def _strip_instruction_lines(text: str) -> str:
    """Remove lines starting with '> ' (system instruction lines)."""
    kept = []
    for line in text.splitlines():
        if line.startswith("> "):
            continue
        kept.append(line)
    return "\n".join(kept)


def _replace_top_sections(text: str, rendered: str) -> str:
    """Replace content between _SEP_OPEN and _SEP_CLOSE with rendered block."""
    i = text.find(_SEP_OPEN)
    j = text.find(_SEP_CLOSE)
    if i == -1 or j == -1 or j <= i:
        # Markers not found — prepend rendered block
        return rendered + "\n\n" + text
    before = text[:i + len(_SEP_OPEN)]
    after = text[j:]
    return before + "\n" + rendered + "\n" + after


def write_handover(conn: sqlite3.Connection, session_id: str) -> Path:
    """Atomic write of handover.md sync skeleton per §4.1."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    # Strip system instruction lines (lines starting with '> ')
    template = _strip_instruction_lines(template)

    # Replace {{YYYY-MM-DD HH:MM}} with current local time
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    template = template.replace("{{YYYY-MM-DD HH:MM}}", now_str)

    # Render the 4 top sections and splice into the sandwich block
    top = top_sections.render_top(conn)
    template = _replace_top_sections(template, top)

    # Stamp narrative slot just before EOF
    if not template.endswith("\n"):
        template += "\n"
    template += f"<!-- narrative: pending sid:{session_id} -->\n"

    out_path = _RENDERED_PATH
    _atomic_write(str(out_path), template)
    return out_path
