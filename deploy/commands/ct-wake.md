---
description: Cortex — release the breaker & wake now. Args: tg | cli | all (default all).
---

⚙️ [CMD ct-wake] This is the **release** for `/ct-pause` and for an automatic fuse trip. Scope comes from the argument: `tg`, `cli`, or `all` / empty. Every scope wakes its shell immediately — nothing waits for a next pass.

Setup: read `venv_python` and `repo_root` from `[cortex]` in `~/.config/marrow/config.toml` (fall back to marrow's `config.default.toml` if a key is blank/missing). Run everything via Bash with cwd `<repo_root>`.

One command, scope by argument — `<venv_python> -m cortex.ctl wake --shell <tg|cli|all>`:

1. **tg** — releases ONLY the tg half (cli stays tripped), books a due-now round in the tg shell ledger and kicks the bridge's scheduler socket, so the bridge feeds that round at once. Bridge down = the booking still stands and fires on its next start/pass; the output line says which of the two happened.
2. **cli** — releases ONLY the cli half (tg stays tripped) and wakes the resident window through the standard run_wake pipeline (alive resident → ear signal; dead → rotated ? fresh : resume). A window already alive AND awake is a no-op: it is on duty already.
3. **all** (or no argument) — clears the WHOLE breaker (both shells, manual or auto) and does both kicks, tg first. Autonomous activity resumes fully: scheduled wakes, fed rounds, watchdog reaps.

Any alarm that came due while the breaker stood was never consumed, so it fires on that same round.

Do not spawn or resume any window yourself — the CLI owns the wake pipeline. For a release WITHOUT an immediate round, use `<venv_python> -m cortex.ctl resume [--shell cli|tg]` instead.

Report the one-line output in plain words (breaker cleared? / tg kicked or booked-only / already-awake no-op / ear wake / resumed or spawned fresh). To inspect state first: `<venv_python> -m cortex.ctl status`.
