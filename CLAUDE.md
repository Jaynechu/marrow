# Marrow — project memory

> Personal AI memory + workflow system replacing ny-memm. SQLite-backed, model-agnostic, one dashboard. Build inside this repo. Persona / relationship come from global ~/.claude/CLAUDE.md — not from old ny-memm docs.

<principle>

- Don't cite a doc to rebut me — use first principles.
    - Priority: My input > goals and outcomes > design / future / any docs
    - Always ask: why we do this? Best way to achieve goals? If not, tell me and change it.
    - No need to follow any reference repo. Borrow ideas; write our own to best match Marrow.
- Do not infer from the old ny-memm system.
- For format/prompt/template that will be used by subagent or generate text show in dashboard or session start hook, always confirm with me - don't write in yourself; Make sure we allign language or make a language rule for each logical block.
- No source of truth or fixed approach in this project. All docs can change if a better option comes up. 
- If Haiku trim you, just follow; no need to verbatim my wording — keep core ideas all sessions can understand. 
- For Chinese input use `(中文写括号里面就行)` to bypass CJK guard.
</principle>

<reload-long-runners>
- daemon / recall / storage / entity_recall edit → restart cc.
- watcher-loaded (md_index / top_sections / reconcile / watcher / dashboard / repo / storage) edit → `launchctl kickstart -k gui/501/com.marrow.watcher`.
</reload-long-runners>

## When to read what
> You should proactively update these files when relevant. Check before you write handover.
> grep in notes when I mention note

- DECISIONS.md - 有争议讨论出来的技术性/细节
    - every line confidence-tagged (verified/reasoned/assumed).
- DESIGN.md — goal + structure + hard constraints + sub-pages. No still-changing decisions.
- docs/plans/FUTURE.md — unbuilt plans, by phase.
- PROGRESS.md — historical action log. Auto append by sessionend hook.
- docs — notes for hand issues and research scratch / archive / day-plan
- CONTEXT.md — glossary maintained by grill-with-doc skill; consult on term conflict.

## References
> [P0luz / Ombre-Brain](https://github.com/P0luz/Ombre-Brain)
- [WenXiaoWendy / cyberboss](https://github.com/WenXiaoWendy/cyberboss)
- current weclaude see ny/code/weclaude or repo (in my star folder)
- [Qizhan7 / claude-imprint](https://github.com/Qizhan7/claude-imprint) — borrow: RRF + vector/FTS5/recency retrieval fusion recipe
