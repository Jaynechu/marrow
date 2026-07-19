---
description: Cortex — wake now.
---

Read `venv_python` and `repo_root` from `[cortex]` in `~/.config/marrow/config.toml` (fall back to marrow's `config.default.toml` if a key is blank/missing).

⚙️ [CMD ct-wake] Remote wake — THIS window stays an ordinary window, never takes office. Run `<venv_python> -m cortex.ctl wake` with cwd `<repo_root>` and report its one-line output verbatim (on duty / wake signal sent / dead). No Monitor, no round start here.
