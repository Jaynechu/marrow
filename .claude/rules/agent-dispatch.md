# Agent dispatch policy

> Main session = orchestrator. Implementation, scanning, summarising → outsource.
> Dispatch agents by default for all coding unless Lumi says inline.
> Inline if mini-task < 20 LOC


## Delegate by default
- grep / find / "where is X used" → Explore (Haiku)
- Web fetch / gh PR / long doc digest → fetcher (Haiku)
- pytest / log read / status check → fact-checker (Haiku)
- Implementation / coding → worktree-implementer (Sonnet/Opus, isolation:"worktree")
  - Sonnet by default - should be good enough for coding with a decent plan and clear instruction.
  - Only send Opus if deep reasoning is required. 
- Phase review (3-way concurrent) → `/rr` command
- Literature / journal claims → general-purpose with web search

## Agent reporting contract
- Return verified facts + verdict, not raw output.
- Cite file:line for code claims, source URL for web claims.
- State "could not verify X" instead of guessing.
- ≤400 words unless caller asks for more.
- No silent writing - notify user if new md created 
  - Save as docs/notes/<slug>.md
  - All findings should be reported to main session.
- No git commit / push / config / settings edit from inside a subagent.

