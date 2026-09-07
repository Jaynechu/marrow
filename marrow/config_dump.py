"""Render the packaged defaults file and the effective merged config as TOML.

Backs `mw config --defaults` / `mw config --resolved`. Uses tomli_w when the
environment has it; otherwise a minimal serializer covering the value types
config.default.toml uses (str, bool, int, float, list, nested table).
"""
from __future__ import annotations

from . import config


def defaults_text() -> str:
    """The packaged config.default.toml, verbatim."""
    return config._DEFAULT.read_text(encoding="utf-8")


def resolved_text() -> str:
    """The effective merged config (defaults + user file + derived paths)."""
    return dumps(config.load())


def dumps(data: dict) -> str:
    try:
        import tomli_w
    except ImportError:
        return _dumps(data)
    return tomli_w.dumps(data)


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        if "\n" in value:
            body = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
            return f'"""\n{body}"""' if body.endswith("\n") else f'"""{body}"""'
        body = (value.replace("\\", "\\\\").replace('"', '\\"')
                .replace("\t", "\\t").replace("\r", "\\r"))
        return f'"{body}"'
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    raise TypeError(f"unsupported TOML value type: {type(value).__name__}")


def _key(name: str) -> str:
    ok = name and all(c.isalnum() or c in "_-" for c in name)
    return name if ok else _fmt(name)


def _lines(data: dict, prefix: str = "") -> list[str]:
    out: list[str] = []
    for k, v in data.items():
        if not isinstance(v, dict):
            out.append(f"{_key(k)} = {_fmt(v)}")
    for k, v in data.items():
        if isinstance(v, dict):
            path = f"{prefix}{_key(k)}"
            out.append("")
            out.append(f"[{path}]")
            out.extend(_lines(v, prefix=f"{path}."))
    return out


def _dumps(data: dict) -> str:
    return "\n".join(_lines(data)).strip() + "\n"
