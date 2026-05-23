"""Global test fixtures.

Autouse no-op for hooks.popen_detach: hook tests invoke hooks.main(['session_*']),
which fires popen_detach. The child subprocess loads REAL config (monkeypatch is
in-process only) and writes to ~/.config/marrow/marrow.db. Neutering the hook-side
reference keeps tests isolated. The direct popen_detach contract test imports from
marrow.popen_detach and is unaffected.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_hooks_popen_detach(monkeypatch, request):
    if "no_popen_patch" in request.keywords:
        return
    try:
        from marrow import hooks
        monkeypatch.setattr(hooks, "popen_detach", lambda *a, **kw: None)
    except ImportError:
        pass
    try:
        from marrow import sessionstart_catchup
        monkeypatch.setattr(sessionstart_catchup, "popen_detach", lambda *a, **kw: None)
    except ImportError:
        pass
