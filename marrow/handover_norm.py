"""Bullet normalisation + sha1 hash for handover tombstone matching.

Hash strategy: case-folded + bullet marker stripped + whitespace collapsed +
CN/EN punctuation unified. Same wording with different punctuation / spacing
hashes to the same value so user edits survive sonnet re-rephrasing.
"""
from __future__ import annotations

import hashlib
import re

_PUNCT_MAP = str.maketrans({
    "，": ",", "。": ".", "！": "!", "？": "?", "；": ";", "：": ":",
    "（": "(", "）": ")", "【": "[", "】": "]",
    "「": '"', "」": '"', "“": '"', "”": '"', "‘": "'", "’": "'", "、": ",",
})
_PUNCT_RE = re.compile(r"[^\w\s一-鿿]")
_WS_RE = re.compile(r"\s+")
_BULLET_PREFIX = re.compile(r"^\s*[-*+•]\s+")


def normalize_bullet(line: str) -> str:
    s = _BULLET_PREFIX.sub("", line or "")
    s = s.strip().translate(_PUNCT_MAP).lower()
    s = _PUNCT_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def hash_bullet(line: str) -> str:
    return hashlib.sha1(normalize_bullet(line).encode("utf-8")).hexdigest()


def bullet_lines(text: str) -> list[str]:
    """Pull bullet lines out of a body block (lines starting with `- `/`* `/`+ `)."""
    out = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s.startswith(("- ", "* ", "+ ")):
            out.append(s)
    return out
