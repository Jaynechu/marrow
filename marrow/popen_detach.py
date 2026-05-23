"""Fire-and-forget subprocess helper.

All four flags are mandatory per pipeline §3 hard constraint
(docs/notes/2026-05-23_sessionend-llm-pipeline.md §3).
Root cause: ny-memm 5/11 stuck-prompt was caused by a subshell fd leak;
missing any one of these four flags reproduces it 100%.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def popen_detach(args: list[str], log_path: Path) -> subprocess.Popen:
    """Fire-and-forget. stdin=DEVNULL, stdout/stderr->log_path (append),
    start_new_session=True, close_fds=True. Caller does NOT wait.

    Four flags are mandatory (pipeline §3 + ny-memm 5/11 stuck-prompt history):
    - stdin=DEVNULL: no tty reattach
    - stdout/stderr->log_path: diagnosable; DEVNULL silences crashes silently
    - start_new_session=True: setsid, detach controlling tty
    - close_fds=True: no fd leak
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "ab")  # noqa: WPS515 — intentionally not closed; child owns it
    return subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
        close_fds=True,
    )
