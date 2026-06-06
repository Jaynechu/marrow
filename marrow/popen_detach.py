"""Fire-and-forget subprocess helper.

Two flavours:

- popen_detach: parent opens log_path before fork, so the file is touched
  even when the child is silent. Use for spawns whose child entry does
  NOT call _redirect_stdio_from_argv (title summariser, watcher, etc.).
- popen_detach_lazy: parent redirects child stdio to DEVNULL; the child
  is responsible for opening log_path itself via _redirect_stdio_from_argv.
  Result: log file exists ONLY when the child actually writes. No
  0-byte residue for skip / already_done / silent paths.

All four flags (stdin=DEVNULL, stdout/stderr to log or DEVNULL,
start_new_session=True, close_fds=True) are mandatory — pipeline §3
hard constraint; missing any reproduces the 5/11 stuck-prompt fd leak.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def popen_detach(args: list[str], log_path: Path) -> subprocess.Popen:
    """Parent-opened log fd. Always creates log_path on spawn."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "ab")  # noqa: WPS515 — child owns it
    return subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
        close_fds=True,
    )


def popen_detach_lazy(args: list[str], log_path: Path) -> subprocess.Popen:
    """Parent stdio=DEVNULL; child opens log_path lazily on first write.

    The child entry module MUST call _redirect_stdio_from_argv() at the
    very top — before any heavyweight import — so import-time tracebacks
    also land in the log when they fire. Children that write nothing
    leave no file behind.
    """
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


class _LazyLog:
    """sys.stdout/stderr replacement. open() deferred until the first
    non-empty .write(), so a silent child never touches the filesystem.

    fileno() forces open — that's a deliberate concession for libraries
    that dup our fd (rare in this codebase; print/traceback go through
    .write only)."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._fh = None

    def _ensure(self):
        if self._fh is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self._path, "a", encoding="utf-8", buffering=1)
        return self._fh

    def write(self, data) -> int:
        if not data:
            return 0
        return self._ensure().write(data if isinstance(data, str) else str(data))

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        if self._fh is not None:
            try:
                self._fh.flush()
            except Exception:  # noqa: BLE001
                pass

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return self._ensure().fileno()

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:  # noqa: BLE001
                pass
            self._fh = None


def _redirect_stdio_from_argv() -> None:
    """Child entry helper. Parse `--log-path <p>` out of sys.argv and
    swap sys.stdout / sys.stderr to a lazy proxy on that path. No-op if
    `--log-path` is absent. Safe to call before any heavyweight import."""
    argv = sys.argv
    for i, a in enumerate(argv):
        if a == "--log-path" and i + 1 < len(argv):
            try:
                proxy = _LazyLog(Path(argv[i + 1]))
                sys.stdout = proxy
                sys.stderr = proxy
            except Exception:  # noqa: BLE001
                pass
            return
