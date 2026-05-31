# Marrow Foundation Design

> Personal AI memory + workflow system. SQLite-backed, model-agnostic, one dashboard.
> Holds goal + structure + hard constraints only. Mechanism → MAP. Decisions → DECISIONS. History → PROGRESS. Unbuilt → FUTURE.

## Goals & Outcomes
> Always think about if goals are matched by the design.
1. High portability + adaptability — memory, affect, addons all survive any switch; commands and habits sync everywhere → One dashboard to manage all.
      - Multi-device: phone, desktop, etc.
      - Multi-platform: WeChat, desktop client, CLI
      - Local + cloud
      - Multi-provider: Claude, GPT, Gemini, local models — swap model/vendor by editing one config line.
2. Persistent memory — recall on mention, no context bloat → Past facts resurface on mention; cold recall fast; no context repeated.
3. Cross-window workflow continuity — pick up where you left off → handover.md written automatically by LLM and `@import`-ed into next session.
4. Emotional continuity — relationship + persona density transfer losslessly without static docs → Affect tracked per episode and resurfaced with recall; persona stays in CLAUDE.md (no DB-side persona docs).
5. High auto, low maintenance — system runs itself; manual edits respected → Memory + dashboard self-update; alerts surface what broke; one place to fix anything.
      - Memory auto-update (events / tables / tasks / catchup / aging).
      - Manual md edits sync back to DB.
      - Clear alerts + logs + comprehensive guides.
6. Expandable base for future addons → Memory system is the base; new capabilities plug in as MCPs.

## Architecture (main line)
- daemon — Python MCP server, serves CLI + WeChat clients.
- storage — SQLite + FTS5 + sqlite-vec.
- runtime — `claude` as stream-json subprocess inheriting OAuth subscription.
- bridge — local socket for WeChat permission routing (Phase 4).
- frontend — auto-rendered `dashboard.md` + static CLAUDE.md family. Memory pulled via MCP, never injected.
- supervisor — daemon watchdog; restart + alert on storm.

---

## Key Rules
- LLM: via `claude` CLI subprocess (OAuth), stream-json subscription (no-p default, claude -p fallback), no paid API. Caller passes intent + tier; provider/model/channel are config, swappable in one line (goal 1).
- Resonable alert, retry and catchup for all features.
- Data under `~/.config/marrow/`, code under `~/CC-Lab/marrow/`. Hook scripts ≤100 lines.
- Always notify me when formats or prompts for py/hook are created or edited.
- md is SoT, DB indexes/searches. Hand-edits never overwritten. Recovery from md.
- Atomic write in and edit update for every render.
- All hooks cap 10000 char. (system rule)


## Dashboard — single entry
- db ↔ md both way sync and refresh (Frontend pending)
- Top section: personal management like todo lists and emotion trends
- Bottom section: content and link of subpages

## Safety nets
> Baseline: Lumi never manually clears markers, never triggers catchup, never retries. No silent fail. Token bounded. Originals recoverable.
- Required nets: backup · retry · catchup · failure-alert · concurrent-write lock · atomic write · idempotency · timeout brake · edit safety · drift sweep · affect heartbeat · affect neutral fallback · affect catchup.
- Shipped mechanism → PROGRESS. Pending mechanism (drift sweep · retry thresholds · catchup scan window · edit-safety anchor format) → FUTURE.
