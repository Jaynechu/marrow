---
description: Cortex — write the handoff now, then rotate to a fresh window.
---

⚙️ [CMD ct-clear] Switch to new window now: 1) TaskStop ALL running background tasks  - wake-signal monitor + any subagent tasks. 2) Update handoff and lie_down(rotate=true, next_wake_min=$ARGUMENTS) — N=0 to start new session now.
