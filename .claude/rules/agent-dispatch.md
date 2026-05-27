# Agent dispatch

Main session = orchestrator. Outsource implementation, scanning, summarising. Inline if <20 LOC or trivial.
Worktree-isolated parallel builds preferred for risky / experimental work.

<models>
- Haiku: mechanical lookup, scan, raw summary — no reasoning.
- Sonnet: default for coding and implementation.
- Opus: reserve for genuine reasoning. Use sparingly.
</models>

<agents>
- Search / locate → Explore
- Web / GitHub / doc digest → fetcher
- Tests / logs / status → fact-checker
- Coding → general-purpose (isolation: "worktree")
</agents>

<Subagent_contract>
- Return verified facts + verdict, not raw output.
- Cite file:line for code, source URL for web.
- State "could not verify X" — no guessing.
- ≤400 words unless caller asks for more.
- New md → `docs/notes/<slug>.md`, notify caller.
- No settings / hook / config edits inside subagent.
</Subagent_contract>

<Worktree>
- First action: `pwd && git rev-parse --show-toplevel`. If cwd not under `.claude/worktrees/agent-*` → STOP, report, no writes.
- Stay in own worktree + branch. Don't merge to main. Don't reach outside assigned scope.
- Commit freely on own branch. No push — main session decides.
- Clean scratch/tmp before exit; main session handles merge + teardown.
</Worktree>