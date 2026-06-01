# Marrow — project memory

> Personal AI memory + workflow system replacing ny-memm. SQLite-backed, model-agnostic, one dashboard. Build inside this repo. Persona / relationship come from global ~/.claude/CLAUDE.md — not from old ny-memm docs.

<principle>

- Don't cite a doc to rebut me — use first principles.
    - Priority: My input > goals and outcomes > design / future / any docs
    - No need to follow any reference repo. Borrow ideas; write our own to best match Marrow.
- No source of truth or fixed approach in this project. All docs can change if a better option comes up. 
- Always confirm new format/prompt/template for py/hook with me.
    - Language rule is needed
- For Chinese input use `(中文写括号里面就行)` to bypass CJK guard.
</principle>

<reload-long-runners>
- daemon / recall / storage / entity_recall edit → restart cc.
- watcher-loaded (md_index / top_sections / reconcile / watcher / dashboard / repo / storage) edit → `launchctl kickstart -k gui/501/com.marrow.watcher`.
</reload-long-runners>

## When to read what
> You should proactively update these files when relevant.
> Always go back to design and MAP when planning. Never guess how it works.

- MAP.md - key facts of current implementation. Mechanism of all features.
- DESIGN.md — goals and outcomes.
- DECISIONS.md - 有争议讨论出来的技术性/细节
    - every line confidence-tagged (verified/reasoned/assumed).
- FUTURE.md (docs/plans) — unbuilt plans, by phase.
- docs — archives/ notes for hand issues and research scratch / plans (daily plan)

## References
> [P0luz / Ombre-Brain](https://github.com/P0luz/Ombre-Brain)
- [WenXiaoWendy / cyberboss](https://github.com/WenXiaoWendy/cyberboss)
- current weclaude see ny/code/weclaude or repo (in my star folder)
- [Qizhan7 / claude-imprint](https://github.com/Qizhan7/claude-imprint) — borrow: RRF + vector/FTS5/recency retrieval fusion recipe
