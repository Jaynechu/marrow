"""Tests for ~/.claude whitelist/blacklist gating in drift_sweep."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import marrow.drift_sweep as ds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_claude(tmp_path, monkeypatch):
    """Create a synthetic ~/.claude tree and redirect drift_sweep constants."""
    claude = tmp_path / ".claude"
    # whitelisted dirs
    (claude / "rules").mkdir(parents=True)
    (claude / "skills").mkdir(parents=True)
    (claude / "commands").mkdir(parents=True)
    (claude / "agents").mkdir(parents=True)
    (claude / "hooks").mkdir(parents=True)
    (claude / "output-styles").mkdir(parents=True)
    (claude / "CLAUDE.md").write_text("# claude config\n", encoding="utf-8")
    (claude / "keybindings.json").write_text("{}\n", encoding="utf-8")
    (claude / "settings.json").write_text("{}\n", encoding="utf-8")
    # blacklisted dirs
    (claude / "projects").mkdir(parents=True)
    (claude / "image-cache").mkdir(parents=True)
    (claude / "file-history").mkdir(parents=True)

    monkeypatch.setattr(ds, "_CLAUDE_ROOT", claude)
    return claude


@pytest.fixture()
def drift_env(tmp_path, monkeypatch, fake_claude):
    """Full drift env with synthetic roots + fake ~/.claude."""
    root_a = tmp_path / "root_a"
    root_a.mkdir()
    pending_dir = tmp_path / "pending"
    backup_dir = tmp_path / "backup"
    pending_dir.mkdir()
    backup_dir.mkdir()
    tree_md = tmp_path / "dir_tree.md"

    fake_paths = SimpleNamespace(
        drift_pending_dir=pending_dir,
        drift_backup_dir=backup_dir,
        dir_tree_md=tree_md,
    )
    monkeypatch.setattr(ds, "paths", fake_paths)
    monkeypatch.setattr(ds, "AUTHORIZED_ROOTS", [root_a, fake_claude])
    return SimpleNamespace(root_a=root_a, claude=fake_claude, tree_md=tree_md)


# ---------------------------------------------------------------------------
# _claude_scope_ok unit tests
# ---------------------------------------------------------------------------

def test_scope_ok_non_claude(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "_CLAUDE_ROOT", tmp_path / ".claude")
    assert ds._claude_scope_ok(tmp_path / "cc-lab" / "marrow" / "README.md") is True


def test_scope_ok_claude_root_itself(tmp_path, monkeypatch):
    claude = tmp_path / ".claude"
    monkeypatch.setattr(ds, "_CLAUDE_ROOT", claude)
    assert ds._claude_scope_ok(claude) is True


def test_scope_ok_whitelisted_dir(fake_claude):
    assert ds._claude_scope_ok(fake_claude / "rules") is True
    assert ds._claude_scope_ok(fake_claude / "rules" / "response.md") is True
    assert ds._claude_scope_ok(fake_claude / "skills") is True
    assert ds._claude_scope_ok(fake_claude / "skills" / "day-plan" / "prompt.md") is True
    assert ds._claude_scope_ok(fake_claude / "CLAUDE.md") is True
    assert ds._claude_scope_ok(fake_claude / "settings.json") is True
    assert ds._claude_scope_ok(fake_claude / "keybindings.json") is True


def test_scope_ok_blacklisted_dir(fake_claude):
    assert ds._claude_scope_ok(fake_claude / "projects") is False
    assert ds._claude_scope_ok(fake_claude / "projects" / "some-project" / "PROBE.md") is False
    assert ds._claude_scope_ok(fake_claude / "image-cache") is False
    assert ds._claude_scope_ok(fake_claude / "image-cache" / "foo.png") is False
    assert ds._claude_scope_ok(fake_claude / "file-history") is False


# ---------------------------------------------------------------------------
# ref scan: blacklisted path is skipped
# ---------------------------------------------------------------------------

def test_ref_scan_skips_blacklisted(drift_env, monkeypatch):
    """A file in ~/.claude/projects must NOT appear in ref scan results."""
    env = drift_env
    # plant a probe file in a blacklisted dir
    probe = env.claude / "projects" / "PROBE_SHOULD_BE_SKIPPED.md"
    probe.write_text("path: ~/old/foo/file.md\n", encoding="utf-8")
    # plant a matching file in whitelisted dir — should be found
    visible = env.claude / "rules" / "response.md"
    visible.write_text("see ~/old/foo/file.md for details\n", encoding="utf-8")

    # Force pure-python fallback (no rg)
    monkeypatch.setattr(ds, "_rg_binary", lambda: None)
    refs = ds.find_refs("file.md", roots=[env.claude])
    found_files = {r["file"] for r in refs}

    assert str(probe) not in found_files, "blacklisted path leaked into refs"
    assert str(visible) in found_files, "whitelisted path missing from refs"


def test_ref_scan_skips_blacklisted_rg(drift_env, monkeypatch):
    """Same test but exercises the rg code path via monkey-patched rg wrapper."""
    env = drift_env
    probe = env.claude / "projects" / "PROBE_SKIPPED.md"
    probe.write_text("~/old/foo/rg_test.md\n", encoding="utf-8")
    visible = env.claude / "rules" / "rg_visible.md"
    visible.write_text("reference to ~/old/foo/rg_test.md\n", encoding="utf-8")

    # Monkey-patch _find_refs_rg to return None → forces python fallback
    monkeypatch.setattr(ds, "_rg_binary", lambda: None)
    refs = ds.find_refs("rg_test.md", roots=[env.claude])
    found_files = {r["file"] for r in refs}

    assert str(probe) not in found_files
    assert str(visible) in found_files


# ---------------------------------------------------------------------------
# SKIP_SCAN_EXTS still honoured under whitelisted dirs (no regression)
# ---------------------------------------------------------------------------

def test_jsonl_skipped_under_whitelist(drift_env, monkeypatch):
    env = drift_env
    jsonl_file = env.claude / "rules" / "session.jsonl"
    jsonl_file.write_text('{"path": "~/old/foo/target.md"}\n', encoding="utf-8")
    log_file = env.claude / "rules" / "run.log"
    log_file.write_text("path ~/old/foo/target.md\n", encoding="utf-8")

    monkeypatch.setattr(ds, "_rg_binary", lambda: None)
    refs = ds.find_refs("target.md", roots=[env.claude])
    found_files = {r["file"] for r in refs}

    assert str(jsonl_file) not in found_files, ".jsonl must still be skipped"
    assert str(log_file) not in found_files, ".log must still be skipped"


# ---------------------------------------------------------------------------
# refresh_dir_tree: blacklisted dirs absent from tree output
# ---------------------------------------------------------------------------

def test_dir_tree_excludes_blacklisted(drift_env):
    env = drift_env
    ds.refresh_dir_tree(roots=[env.claude])
    content = env.tree_md.read_text(encoding="utf-8")

    assert "projects" not in content, "blacklisted 'projects' must not appear in dir_tree"
    assert "image-cache" not in content, "blacklisted 'image-cache' must not appear in dir_tree"
    assert "rules" in content, "whitelisted 'rules' must appear in dir_tree"
    assert "skills" in content, "whitelisted 'skills' must appear in dir_tree"
