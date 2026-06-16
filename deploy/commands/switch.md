---
description: Switch to any session across channels — replaces res-oth.
---

Run `mw list-recent-sessions --limit 10` via Bash. Capture stdout (tab-sep: `sid\tmodel\tchannel\tcwd\tlast_active\ttitle\teffort`).

If no rows: tell Lumi (没有 session) and stop.

Otherwise render as:
```
Recent sessions:
  1. [<ch>·<project>] <title or "(untitled)">  (<sid8>)  <model>  <HH:MM>
  2. ...
Reply with a number to resume; anything else cancels.
```
- `sid8` = first 8 chars of full sid.
- `project` = last path component of cwd (e.g. `/Users/.../marrow` → `marrow`). Omit `·project` if cwd empty.
- `HH:MM` = extracted from last_active ISO timestamp (chars 11-16). Omit if missing.

When Lumi replies:
- Digit in range → write THREE lines (sid + cwd + effort) to `~/.config/marrow/next-resume.sid` via Bash:
  `mkdir -p ~/.config/marrow && printf '%s\n%s\n%s' '<full_sid>' '<cwd>' '<effort>' > ~/.config/marrow/next-resume.sid`
  Then say (目标已设定 <sid8> — Ctrl+D 退出即自动 resume).
- Anything else → no marker, reply (取消).

Constraints:
- One `mw` call, one marker write. No recall, no extra tool calls.
- Never write the marker file when Lumi cancels or picks an out-of-range number.
