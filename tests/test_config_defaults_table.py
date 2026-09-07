"""config.default.toml is the single defaults table.

1. No config read carries an inline literal fallback.
2. Every key in the table is referenced by name somewhere in the package.
3. load() with an empty user file yields every key of the table.
"""
from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

from marrow import config

PKG = Path(config.__file__).parent
DEFAULTS = PKG / "config.default.toml"

# `.get("key", <scalar literal>)` — a fallback value duplicated outside the
# table. `.get("section", {})` is fine (section access, not a default value).
_FALLBACK_RE = re.compile(
    r"""\.get\(\s*["'][a-z_]+["']\s*,\s*(?:-?\d|["']|True|False)"""
)
_OPT_OUT = "# config-fallback-ok"

# Keys hosted here but consumed outside the marrow package, or reached through
# a runtime-built name rather than a literal.
_EXTERNAL_KEYS = {
    "llm.emergency",              # chain slot, kept for forks
    "tiers.mid",                  # tier name arrives as a caller argument
    "cortex.wake_signal_log_file",  # cortex repo writes it
    "cortex.breaker.enabled",     # cortex repo + tg bridge read this file
    "cortex.breaker.fuse_threshold",
    "cortex.breaker.window_hours",
    "cortex.breaker.trip_message",
}


def _py_files() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def _table() -> dict:
    with DEFAULTS.open("rb") as f:
        return tomllib.load(f)


def _flat(data: dict, prefix: str = "") -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    for k, v in data.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.extend(_flat(v, path))
        else:
            out.append((path, v))
    return out


# ── static resolver: which expressions evaluate to a config section ──────────

def _section_of(node, env: dict, funcs: dict, sections: set) -> str | None:
    if isinstance(node, ast.BoolOp):
        for v in node.values:
            got = _section_of(v, env, funcs, sections)
            if got:
                return got
        return None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return funcs.get(node.func.id)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr != "get" or not node.args:
            return None
        arg = node.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            return None
        base = _section_of(node.func.value, env, funcs, sections)
        return f"{base}.{arg.value}" if base else arg.value
    if isinstance(node, ast.Subscript):
        if not (isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            return None
        base = _section_of(node.value, env, funcs, sections)
        return f"{base}.{node.slice.value}" if base else node.slice.value
    return None


def _config_fallback_lines(path: Path, sections: set) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    env: dict[str, str] = {}
    funcs: dict[str, str] = {}
    for _ in range(3):
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                got = _section_of(node.value, env, funcs, sections)
                if got and got.split(".")[0] in sections:
                    env[node.targets[0].id] = got
            if isinstance(node, ast.FunctionDef):
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Return) and inner.value is not None:
                        got = _section_of(inner.value, env, funcs, sections)
                        if got and got.split(".")[0] in sections:
                            funcs[node.name] = got
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and len(node.args) > 1):
            continue
        arg = node.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            continue
        section = _section_of(node.func.value, env, funcs, sections)
        if not section or section.split(".")[0] not in sections:
            continue
        line = lines[node.lineno - 1]
        if _OPT_OUT in line or not _FALLBACK_RE.search(line):
            continue
        hits.append(f"{path.relative_to(PKG)}:{node.lineno}: {line.strip()}")
    return hits


def test_no_inline_literal_config_fallbacks():
    """Fail listing every config read that still carries a literal fallback.

    Mark a genuine non-config dict access with `# config-fallback-ok` on the
    same line to opt it out.
    """
    sections = set(_table())
    hits: list[str] = []
    for path in _py_files():
        hits.extend(_config_fallback_lines(path, sections))
    assert not hits, (
        "config reads must trust config.default.toml:\n" + "\n".join(sorted(hits))
    )


def test_every_default_key_is_referenced():
    """A key with no reader is dead config — remove it or wire it up."""
    blob = "\n".join(p.read_text(encoding="utf-8") for p in _py_files())
    orphans = []
    for key, _ in _flat(_table()):
        if key in _EXTERNAL_KEYS:
            continue
        leaf = key.rsplit(".", 1)[-1]
        if f'"{leaf}"' not in blob and f"'{leaf}'" not in blob:
            orphans.append(key)
    assert not orphans, f"unreferenced config keys: {orphans}"


def test_load_with_empty_user_file_returns_every_default_key(monkeypatch, tmp_path):
    """An install whose config.toml is empty still resolves every key."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_path)

    cfg = config.load()
    missing = []
    for key, _ in _flat(_table()):
        cur = cfg
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                missing.append(key)
                break
    assert not missing, f"keys lost by load(): {missing}"
