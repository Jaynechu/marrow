---
description: Cortex — wake now.
---

Read `venv_python` and `repo_root` from `[cortex]` in `~/.config/marrow/config.toml` (fall back to marrow's `config.default.toml` if a key is blank/missing).

⚙️ [CMD ct-wake] Take office in THIS window: run `<venv_python> -m cortex.ctl wake` with cwd `<repo_root>` and report its one-line output. If it grants take-office, follow its arm instruction and start the round.
