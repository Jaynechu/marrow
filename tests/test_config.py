"""Tests for marrow/config.py path accessors."""
from __future__ import annotations

from pathlib import Path

from marrow import config


def test_sub_pages_path_defaults_under_ny(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    p = config.sub_pages_path()
    assert p.endswith("Desktop/NY/sub_pages")
    assert Path(p).is_absolute()


def test_sub_pages_state_path_defaults_under_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    p = config.sub_pages_state_path()
    assert p == str(tmp_path / "state")
    assert Path(p).is_absolute()


def test_sub_pages_path_overridable(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        '[paths]\n'
        f'sub_pages = "{tmp_path / "pages"}"\n'
        f'sub_pages_state = "{tmp_path / "state2"}"\n'
    )
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_path)
    assert config.sub_pages_path() == str(tmp_path / "pages")
    assert config.sub_pages_state_path() == str(tmp_path / "state2")


def test_sub_pages_path_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[paths]\nsub_pages = "~/mw_pages"\n')
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_path)
    p = config.sub_pages_path()
    assert "~" not in p
    assert p == str(Path.home() / "mw_pages")
