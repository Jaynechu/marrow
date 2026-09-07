"""Read cortex's own settings from cortex — marrow never stores a copy.

The cortex repo owns every cortex knob (its packaged config.default.toml plus
the user file merged over it). Marrow shells out to
`<venv_python> -m cortex.ctl config --resolved` from `[cortex].repo_root` and
parses the printed TOML.

The subprocess costs ~55ms and the result is cached for the life of the
process. That cache only helps a long-lived process (the MCP daemon): a hook
is a FRESH process on every turn, so it would pay the full cost each time.
Hook call sites therefore gate on a config-free shape pre-check
(`cortex_bridge.could_carry_marker`) and only reach here for a prompt that
could actually be a cortex marker line.

Cortex disabled / unconfigured / the command failing all raise
CortexConfigError. There are no literal fallbacks here: a cortex value that
cannot be read is an error at the call site, never an invented number.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from . import config

_ARGS = ("-m", "cortex.ctl", "config", "--resolved")
_TIMEOUT = 3.0  # reachable from a per-turn hook — never hang a prompt
_MISSING = object()

# cortex [paths] entries marrow resolves. An empty value in cortex config means
# "cortex's own default", which cortex derives under its home — mirrored here
# because `config --resolved` prints the raw merged table, not resolved paths.
_PATH_DEFAULTS = {
    "wake_state_file": "state/wake_state.json",
    "watchdog_pidfile": "state/watchdog.pid",
}

_CACHE: dict | None = None


class CortexConfigError(RuntimeError):
    """The cortex config could not be read."""


def reset() -> None:
    """Drop the per-process cache (tests, and any caller that just changed
    cortex config in the same process)."""
    global _CACHE
    _CACHE = None


def load() -> dict:
    """The effective cortex config, cached per process."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    cx = config.load()["cortex"]
    if not cx["enabled"]:
        raise CortexConfigError("cortex is disabled ([cortex].enabled = false)")
    py = str(cx["venv_python"] or "").strip()
    root = str(cx["repo_root"] or "").strip()
    if not py or not root:
        raise CortexConfigError(
            "cortex is not configured ([cortex].venv_python + [cortex].repo_root)")
    cmd = [str(Path(py).expanduser()), *_ARGS]
    try:
        p = subprocess.run(cmd, cwd=str(Path(root).expanduser()),
                           capture_output=True, text=True, timeout=_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CortexConfigError(f"cortex config command failed: {exc}") from exc
    if p.returncode != 0:
        detail = (p.stderr or p.stdout or "").strip()
        raise CortexConfigError(
            f"cortex config command exited {p.returncode}: {detail}")
    try:
        _CACHE = tomllib.loads(p.stdout)
    except ValueError as exc:
        raise CortexConfigError(f"cortex config is not valid TOML: {exc}") from exc
    return _CACHE


def get(section: str, key: str, default=_MISSING):
    """One value from the resolved cortex config. Dotted `section` walks nested
    tables. Without `default` a missing key raises — it means the cortex
    defaults table lost a key marrow depends on."""
    node = load()
    try:
        for part in section.split("."):
            node = node[part]
        return node[key]
    except (KeyError, TypeError):
        if default is not _MISSING:
            return default
        raise CortexConfigError(f"cortex config has no [{section}].{key}") from None


def home() -> Path:
    """cortex's own home dir: cortex [paths].cortex_home, else the dir both
    repos default to (marrow [cortex].home)."""
    raw = str(get("paths", "cortex_home") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(config.load()["cortex"]["home"]).expanduser()


def path(key: str) -> Path:
    """A cortex [paths] file. Absolute value used as-is; empty = cortex's own
    default under home()."""
    raw = str(get("paths", key) or "").strip()
    if raw:
        return Path(raw).expanduser()
    return home() / _PATH_DEFAULTS[key]
