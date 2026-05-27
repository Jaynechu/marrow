name: day-plan
description: Daily open / evening close ritual for marrow. Morning = Scan → Brainstorm → Synthesize → Self-grill → Plan → Dispatch. Evening = review + handover update + optional night /goal. Trigger = /day-plan, /day-plan evening, (开工), (复盘).

---

# day-plan

One skill, two modes. Default = morning. Pass `evening` to switch.

User is non-coder. Lead every visible line with user-visible outcome in plain words.

This is a pure planning/brainstorming session.

## Rules
- Write plan in English ONLY. 
- Hard cap 150 lines, target ≤100.
- Plan file MUST start with Dispatch Policy at the top.
- Goal need to be clear and achievable.
- Bite-sized steps - max 8 - not too much details if LLM can understand what to do without guessing
- No code in plan. Done = command only.

**Save plan to** `marrow/docs/plans/<slug>.md` — slug ≤4 words, no date prefix (e.g. `dashboard-rebuild.md`). 

## Morning mode

### 1. Scan (silent, auto)
Read: 
1. handover.md (already in context) — check any alert or open/plan
2. DESIGN.md — If we are still on right track - phase structure? new tasks meet goals?
3. DECISIONS.md — Deadlock? Any conflict among decisions? Or conflict with design?
4. docs/plans/FUTURE.md — Any features fit in this phase?
5. git status — uncommitted M - just commit at the end of session
6. git log --oneline -10
- No need to output before brainstorm.

### 2. Brainstorm (user in the loop)
- Check if Lumi want to add anything today or any questions.
- Answerable from code/docs → explore first.
- Real fork → list ≤3 paths, one line each, with my pick. User confirms with one word.
One question per turn. Stop when wish list resolved.
- Invoke `brainstorming` skill if involve new feature, schema/design change.
  - Can fork to new window if necessary.

### 3. Synthesize
- Merge leftover + brainstorm → candidate list. Classify: bug, half-done feature, decision pending. Order by dependency.
- Output 2-5 main goals & outcomes → plan draft (very short brief).
- If Lumi is happy then grill or create the actual plan.

### 4. Self-grill (auto, conditional)
Invoke `grill` skill **only if** Synthesize hit: decision deadlock, dependency cycle, scope unclear. Otherwise skip.

### 5. Plan output

```

## Dispatch Policy (read first)
- Strictly follow agent-dispatch.md
- You are the orchestrator — dispatch tasks to agent or wt and keep context clean. 
- You can ask questions if not sure but no need to ask if you know the optimal answer.
- You should not stop until the goal achieved and outcome tested.
- You decide agent count and agent type (follow agent-dispatch.md and less Opus)

## Today

Session 1 (main) — <goal> → <outcome>
- bite-sized steps (≤8, no code)
- Done: <machine-checkable cmd>
- Dispatch: agent <type> for <subtask> | wt <slug> for <subtask>

Session 2 (main) — <goal> → <outcome>
- steps
- Done: <cmd>
- Dispatch: ...

Session ...


```

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


## Skill chain
- Brainstorm: borrows from `brainstorming` skill (Phase 1 + 2 only).
- Self-grill: delegates to `grill` skill.
- Dispatch: references `using-git-worktrees` when wt slot used.
