# Native install version pin — escape 2.1.143

> Why: 2.1.143 has the toolcall parse bug (see 2026-05-18_cc-2143-toolcall-parse-bug.md). Pin to 2.1.141, stop auto-update reverting it.

## Symptom
Native install (not npm). Manual downgrade auto-reverts within minutes; symlink/version-file edits revert.

## Root cause chain
- `~/.local/bin/claude` = symlink → `~/.local/share/claude/versions/<ver>`.
- Native updater rewrites symlink to highest version in `versions/` on every start, no target-exists check (observed: dangling to a deleted 2.1.143).
- Delete/rename newest binary → updater re-lands same version (observed: 2.1.143 back within the same second as `rm`).
- Concurrent sessions each run own background updater; one downgrades, another's start re-tops symlink → "back in 10 min".
- `autoUpdates: false` (settings.json + ~/.claude.json) does not govern native path. Real switches: `~/.claude.json` `autoUpdatesProtectedForNative` (exists in practice, absent from official docs) + env `DISABLE_AUTOUPDATER`.

## Done (this session)
- `~/.claude/settings.json` → added `"env": { "DISABLE_AUTOUPDATER": "1" }`
- `~/.claude.json` → `autoUpdatesProtectedForNative: true → false`
- symlink → 2.1.141 (re-topped by live old sessions until all closed)
- `versions/`: kept `2.1.142.disabled`, `2.1.143.disabled` as fallback

## Remaining (user, order matters)
1. Close ALL claude sessions — else updater keeps pulling.
2. System terminal (not inside claude):
   - `rm -rf ~/.local/share/claude/versions/2.1.143*`
   - `ln -sfn ~/.local/share/claude/versions/2.1.141 ~/.local/bin/claude`
   - `claude --version` → expect 2.1.141
3. Reopen claude (new process carries DISABLE_AUTOUPDATER).

## Notes
- Official downgrade: `curl -fsSL https://claude.ai/install.sh | bash -s <version>` — do Done steps 1-2 first, else reinstall re-upgrades.
- `minimumVersion` = version FLOOR / anti-downgrade; do NOT use to pin an old version (opposite effect).
- `DISABLE_AUTOUPDATER` (official) blocks auto-update; `DISABLE_UPDATES` stricter, also blocks manual `claude update`.
