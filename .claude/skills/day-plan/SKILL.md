name: day-plan
description: Daily open / evening close ritual for marrow. Morning = Scan → Brainstorm → Synthesize → Self-grill → Plan → Dispatch. Evening = review + handover update + optional night /goal. Trigger = /day-plan, /day-plan evening, (开工), (复盘).

---

# day-plan

One skill, two modes. Default = morning. Pass `evening` to switch.

User is non-coder. Lead every visible line with user-visible outcome in plain words.

## Morning mode

### 1. Scan (silent, auto)
Read: `git status`, `~/.config/marrow/handover.md`, `PROGRESS.md` + `git log --oneline -10`, dashboard Affect band, `FUTURE.md`.
Output ≤6 plain-word bullets. No jargon.

### 2. Brainstorm (user in the loop)
Open: (今天有没有想加的 feature 或对项目方向的疑问?)
- Answerable from code/docs → explore first.
- Real fork → list ≤3 paths, one line each, with my pick. User confirms with one word.
One question per turn. Stop when wish list resolved.

### 3. Synthesize (silent, auto)
Merge leftover + brainstorm → candidate list. Classify: HIGH/MED bug, half-done feature, uncommitted M, decision pending. Order by dependency. Cap by Affect band — low band → ≤1 objective.

### 4. Self-grill (auto, conditional)
Invoke `grill` skill **only if** Synthesize hit: decision deadlock, dependency cycle, scope unclear. Otherwise skip.

### 5. Plan output

```
## Today

Objectives
- Session A (main): <outcome sentence>. Done: <machine-checkable cmd>.
- Session B (wt): <outcome sentence>. Done: <cmd>.

Dispatch
- Main: Session A
- Worktree: Session B — branch: <slug>
- Agents: <type> × N for <subtask>

Constraints
- Active sessions ≤ 3 (incl. study)
- Wt over serial unless schema overlap
```

Plan rejected if Dispatch missing or any Done lacks verifiable command.
End with one declarative line — main session starts now.

**Save plan to** `~/Desktop/NY/<slug>.md` — slug ≤4 words, no date prefix (e.g. `tombstone-fd-fix.md`). Hard cap 150 lines, target ≤100.

## Evening mode (review window)

### 1. Today vs Plan
One sentence: what shipped, what slipped.

### 2. Handover update
Edit `~/.config/marrow/handover.md`: Done, Open (incl. today's leftover), Plan (tomorrow's seed), Reference (file:line).
Never wipe untouched items. Preserve pass-through.

### 3. Night /goal (optional)
**Only if** spare quota AND leftover is mechanical (fix-and-test, not design).
Pick one HIGH/MED with machine-checkable success. Write:
- **Condition**: pytest exit 0 / dashboard field flips / grep hit count.
- **Objective**: outcome line only, no how-to.
- **Echo**: done command printed to transcript.

Show user goal text. User fires before sleep. Skip if leftover needs design judgment.

## Rules
- Outcome-first in every visible line.
- Objectives = lecture opening, not textbook.
- No code/step-by-step in plan. Done = command only.
- Plan file ≤150 lines (target ≤100). Slug ≤4 words, no date.
- CN labels in (parentheses).
- Agents/wt over inline main work when independent.
- End plan/report on declarative — no upsell (要不要 / 需要我).

## Skill chain
- Brainstorm: borrows from `brainstorming` skill (Phase 1 + 2 only).
- Self-grill: delegates to `grill` skill.
- Dispatch: references `using-git-worktrees` when wt slot used.
