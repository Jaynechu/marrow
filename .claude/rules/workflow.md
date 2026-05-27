# Coding Workflow

<env>

- `claude -p`, Agent SDK, cc gh actions, third-party Agent-SDK apps → credit pool from 6/15; Anthropic API key not an option; stream-json subprocess OK.
- Hook stdout injection cap ~10000 chars.
- Keep in mind: Easy migration + multi-channel e.g. codex, cloud, local LLM
</env>

<Principle>

- Never bypass hooks, signing, or pre-commit checks.
- Read log or code before any plausible explanation.
- No guess, assumption, fabrication - solid evidence please.
- Attempt before give up - no lazy alternative until root cause known.
- Don't flip your call to match mine before audit — push back with evidence.
</Principle>

<Before>

- No plan, no coding — both agree before start.
- I give goal or outcome; you design the how.
- Understand my real need and apply first-principles if vague or unsure.
- Brainstorm and grill yourself.
- Find best approach to match my goals.
- Balance outcome and efficiency - do not over-engineer but also meet my requirements.
- Always add standard safety nets proactively. e.g. alert, audit log, flock, xx caps, catchup.
- Code/config > prompt/instruction.
</Before>

<During>

- Stay on main goal.
- English only in code/config.
- Minimum comments.
- Module soft cap 300 lines.
- Self-review for over-engineering every 50 LOC.
- Implement only what was asked.
  - Surface missing essentials proactively — obvious feature, guard, or pattern.
  - Min diff for edits - BUT prioritise outcome + fix root cause.
- In-scope harmless follow-ups auto-OK (e.g. cleanup, typo, minor consistency).
- Ask if destructive.
- Rule of Three - Wait for third caller before extracting abstraction.
- Delete cleanly: no rename-to-unused, no tombstone, no re-export shim.
- Fix every failure before reporting.
- Keep going until the goal is truly achieved.
- Commit and push as below.
</During>

<Test>

- Always test (except no code change): linter, pytest, dry-run, tdd, live verification.
- TDD skill: deterministic logic with fixed behaviour contract.
- UI/frontend: launch dev server, exercise in-browser — golden path, edges, regression. Untestable here → say so explicitly.
- Side-effect scripts (deploy / migration / pipeline / file rewrite): `--dry-run` first, then `--apply`.
- Validate at boundaries only (user input, external APIs); trust internal code and framework.
</Test>

<After>

- Reporting in plain wording - highlight outcomes first
- Essential details only
- Follow format in `response.md`.
- Do not report files changed by Lumi or another session
</After>

<git>

- Frequent commit (auto) - at least one per logical unit.
  - See last session's leftovers (only when inactive not actively working) or my modification → commit together.
- Push at session/phase end (auto).
- No need to ask me for commit or push, only report when destructive or conflict.
- `~/.claude`: local commit after config/hooks change; no push.
</git>

<housekeeping>

- Don't ask - always clean-up.
- After worktree merges into main, rm worktree/branch. Be careful if unsafe or un-merged.
- Drop empty/stale stash entries once content verified landed or irrelevant.
- Session end: sweep `/tmp/*.py` `/tmp/*.db` scratch.
- Session end: drift sweep across docs.
- Prune local-only branches with no commits ahead of main.
- Each session clean its own rubbish - if find previous stale left-over, clean it together.
- GitHub ops: `gh` CLI over `WebFetch` or hand-rolled cURL.
- OSS used or borrowed: star on GitHub, then sort into matching list.
</housekeeping>

