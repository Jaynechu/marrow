"""Guard: marrow/timeutil.py is the only place that does tz conversion.

Scans marrow/**/*.py code tokens (comments and strings skipped) for local
clock reads and tz conversions. Allowed only in:
- timeutil.py: the single conversion boundary.
- config.py: resolves the configured / OS timezone that timeutil caches.
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent / "marrow"
_ALLOWED = {"timeutil.py", "config.py"}
_BANNED = {
    "date.today()": re.compile(r"\b(?:date|datetime)\.today\("),
    "naive datetime.now()": re.compile(r"\bnow\(\)"),
    "ZoneInfo(": re.compile(r"\bZoneInfo\("),
    ".astimezone(": re.compile(r"\.astimezone\("),
    "utcnow(": re.compile(r"\butcnow\("),
    "get_tz(": re.compile(r"\bget_tz\("),
}
_SKIP = {tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING}
for _name in ("FSTRING_MIDDLE", "TSTRING_MIDDLE"):
    if hasattr(tokenize, _name):
        _SKIP.add(getattr(tokenize, _name))


def _code_lines(path: Path) -> dict[int, str]:
    lines: dict[int, str] = {}
    src = path.read_text(encoding="utf-8")
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in _SKIP:
            continue
        lines[tok.start[0]] = lines.get(tok.start[0], "") + tok.string
    return lines


def _violations(pkg: Path = _PKG) -> list[str]:
    out = []
    for path in sorted(pkg.rglob("*.py")):
        if path.relative_to(pkg).as_posix() in _ALLOWED:
            continue
        for lineno, code in _code_lines(path).items():
            for label, pat in _BANNED.items():
                if pat.search(code):
                    out.append(f"{path.relative_to(pkg.parent)}:{lineno}: {label}")
    return out


def test_no_tz_conversion_outside_timeutil():
    assert _violations() == []


def test_guard_catches_each_pattern(tmp_path):
    bad = tmp_path / "marrow"
    bad.mkdir()
    (bad / "timeutil.py").write_text("x = datetime.now()\n")
    (bad / "leak.py").write_text(
        "# datetime.now() in a comment is fine\n"
        "s = 'ZoneInfo(\"x\")'\n"
        "a = date.today()\n"
        "b = datetime.now()\n"
        "c = ZoneInfo('UTC')\n"
        "d = x.astimezone(tz)\n"
        "e = datetime.utcnow()\n"
        "f = config.get_tz()\n"
        "g = datetime.now(timezone.utc)\n"
    )
    found = _violations(bad)
    assert [v.split(": ", 1)[1] for v in found] == [
        "date.today()", "naive datetime.now()", "ZoneInfo(", ".astimezone(",
        "utcnow(", "get_tz(",
    ]
    assert all(v.startswith("marrow/leak.py:") for v in found)
