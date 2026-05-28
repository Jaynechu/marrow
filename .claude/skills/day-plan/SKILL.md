name: day-plan
description: Daily open / evening close ritual for marrow. Morning = Scan → Brainstorm → Synthesize → Self-grill → Plan → Dispatch. Evening = review + handover update + optional night /goal. Trigger = /day-plan, /day-plan evening, (开工), (复盘).

---

# day-plan

One skill, two modes. Default = morning. Pass `evening` to switch.

User is non-coder. Lead every visible line with user-visible outcome in plain words.

This is a pure planning/brainstorming session.

## Rules
- Write plan in English ONLY. 
- Hard cap 300 lines, target ≤100/session. if over can split into 2 plans but still add top section to each plan.
- Plan file MUST start with Dispatch Policy at the top.
- Goal need to be clear and achievable.
- Bite-sized steps - max 8 - not too much details if LLM can understand what to do without guessing
- No code in plan. Done = command only.

**Save plan to** `marrow/docs/plans/<daily_YY-MM>.md`
- rm previous plans if done - maybe keep 3 days as reference.

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
> This step can be time-consuming and need multiple turns.

Phase 1. Understanding the project and Lumi's needs
> Don't ask obvious question if you know the answer.
- Where are we now? What's left and what's next?
- Any issue so far - are you happy with the previous work? (according to the scan results)
- Does Lumi want to ask any question, add a task at the top of the list, or add to future/later?

Phase 2. Explore and Design
Step 1: Listing tasks as candidates (leftover + new).
  - Group relevant tasks together (e.g. similar function, dependency, location)
  - Sort by priority
  - See which group Lumi want to do today.
Step 2: Explore best approaches for each group of tasks.
  > Discuss sessions one by one. No ALL-IN-ONE!!!
  - Maximise your first principle - find the best approach
  - Best solution = match project goals + Lumi's real usage scenarios/needs
  - Don't be boxed in by existing framework — break all known patterns/decisions
  - Don't ask questions that you know the answer.
Step 3: Check understanding and decision making.
  - All decision made? Not sure -> back to step 2
  - We should have a shared understanding and agreement after brainstorming.

Phase 3. Self-grill and confirmation
- ALWAYS invoke `grill` skill to grill both of us.
  - Anything missing, unclear, deadlock?
- If next session has to ask question before start or my outcomes not achieved by the end of session. Go back to Phase 2.


### 4. Plan output
- Output a /goal for each main session. Cap 4000 char.
  - /goal <pass condition> (machine-checkable cmd)
  Write effective conditions — Haiku reads the transcript and checks alignment until the loop ends.
- For steps/goals, you can give main session more space to investigate themselves as they are the ones reading all reference, they should know better than you.
  e.g. do not say clean-up path ABC, say clean all files contain...

**Always use the Template**

```
## Principle
- Keep going until the goal is truly achieved.
- The plan may missing tiny bits. Make it up if you can.
- If live (user-like) verification is possible, run it before reporting.
- The only standard of goal verification is whether it works in practice. 
  Tests and dry runs are just safeguards.
- When all done, pls clean-up and update short brief at the end of the plan
  2-3 sentences except plan changed

## Dispatch Policy (read first)
- Strictly follow `.claude/rules/agent-dispatch.md`.
- You are the orchestrator — dispatch tasks to agent or wt and keep context clean. 
- You can ask questions if not sure but no need to ask if you know the optimal answer.
- You can change agent count and agent type if needed
  - Still follow agent-dispatch.md and use less Opus

---

## Today

Session 1 (main)
**/goal <pass condition>**
- <outcome>
- bite-sized steps (≤8, no code)
- Dispatch: agent <type> for <subtask> | wt <slug> for <subtask>


Session 2 (main) — <goal> → <outcome>
**/goal <pass condition>**
- <outcome>
- bite-sized steps (≤8, no code)
- Dispatch: agent <type> for <subtask> | wt <slug> for <subtask>

Session ...

---
## Reference and Skills
- using-git-worktrees
...

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

