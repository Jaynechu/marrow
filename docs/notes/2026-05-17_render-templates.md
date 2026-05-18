# Render templates — Open-Threads / craft / study (Lumi spec, 2026-05-17)
> Also merge handoff skills in to our template
> Outcome: You should know what's done and left, what to read and where are they, what skills/tools/mcp to uses without ask me (except knwon pending decisions)

Status: locked spec from Lumi. Lands at #7 (SessionEnd rewrite + SessionStart @import render) and #8 (dashboard). Not a draft — use verbatim as the view render contract + the SessionEnd rewrite prompt (prompt body still needs the standard Lumi review tag at #7 commit). Fills DESIGN L231 Pending "the md render template behind each view".

Principle: what Lumi sees = a reminder/todo list, zero detail. Self-injected tech/study = detail kept but dehydrated. Section overwritten whole every run (rewrite, not append). Rendered into the CLAUDE.md marker block, @import-loaded at session start, no extra prompt from Lumi.

## OPEN-THREADS (overwrite entirely each run)

Goal: "get it done and get rid of it" — items are meant to be cleared, not memorialized. Two sub-tags.

```
[Next]
- Items Lumi will pick up at the very next session start. From chat history, any leftover agreed to continue next session.
  - Can be urgent / nonurgent
  - Can be follow-up tasks, or any casual topic left unfinished (e.g. 老婆出去玩回来接着聊 xxx)

[Soon]
- Unresolved leftovers for the next few days.
- Include: assignment due, reminder, any task on hold
- Exclude: already resolved, already in [Next] or Lighthouse, ideas abandoned during the session, no further action needed.

Format per bullet: - [YYYY-MM-DD (today)] <subject> <done>, <left>, <plan> [Due YYYY-MM-DD]
  - 1 to 3 short sentences. No tag in the sentences, state directly.
  - Omit done / left / plan / due if n/a.
  - English for tasks; Chinese allowed for casual topics or slang.

Examples:
[Next]
- [2026-05-10] joint_log.md merged into 2026.md - can delete.
[Soon]
- [2026-05-11] 211 Feedback fruit step 1 done; step 3 pending []; awaiting prof release members' feedback on Thu. [Due 2026-05-15]

AUDIT & REWRITE (every run):
- Drop anything completed / resolved / cancelled / abandoned.
- Keep unresolved bullets; edit/merge if state changed.
- Rewrite the whole section — script overwrites the entire section from the output.
- Order: due bullets on top by due asc; undated by entry date asc.
```

## craft (English only; tech content lives here, never in daily)

```
Pure facts + essential detail, dehydrated.
Format: <subject 1> [did 1 2 3...], [process/detail], [outcome 1 2 ...]; <subject 2> ...
Keep process concise; drop entirely if already resolved.
Example: joint_log.md merged into 2026.md; Weclaude bridge xxx fixed, working as expected.
```

## study (English only; Deakin / GAMSAT / S1-S3)

```
Pure facts + outcome, same shape as craft.
Example: 370 AT1 Essay (Nature style news and views) intro done, reference *3, 800 words left.
```
