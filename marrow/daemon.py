"""Marrow MCP server (stdio). Thin protocol shell over repo.py.

Phase 1 tool set: recall only. The session-start handoff is rendered by the
SessionStart hook importing repo.handoff (it loads once at launch via the
CLAUDE.md marker block, not pulled per-turn). LLMClient is wired here so any
pipeline provider failure lands in the alerts table.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import config, repo, storage
from .llm import LLMClient

mcp = FastMCP("marrow")

_DB = config.db_path()
# on_alert sink: provider chain failure -> alerts table (no silent degrade).
llm = LLMClient(
    on_alert=lambda sev, t, m, s: repo.add_alert(sev, t, m, s, db=_DB)
)


@mcp.tool()
def recall(query: str, limit: int = 10) -> list[dict]:
    """Recall past session turns matching a query (full-text search over
    archived dialogue). Call when the user references the past."""
    conn = storage.connect(_DB)
    try:
        return repo.recall(conn, query, limit)
    finally:
        conn.close()


def main() -> None:
    storage.init_db(_DB).close()
    mcp.run()


if __name__ == "__main__":
    main()
