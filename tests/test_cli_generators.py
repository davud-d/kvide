"""User generator discovery and CLI startup integration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest

from kvide import cli


@pytest.fixture
def user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    return home / ".config" / "kvide" / "generators.toml"


def write_config(path: Path, name: str = "Default") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'[[generators]]\nname = "{name}"\ncommand = ["unused"]\n',
        encoding="utf-8",
    )


def start_cli(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    apps = []
    monkeypatch.setattr(cli.KvideApp, "run", lambda self: apps.append(self))
    assert cli.main([str(root), *args]) == 0
    return apps[0]


def test_default_is_loaded(user_config, tmp_path, monkeypatch):
    write_config(user_config)
    assert cli.default_generators_path() == user_config
    app = start_cli(tmp_path, monkeypatch)
    assert [g.name for g in app.generators] == ["Default"]
    assert app.generator_error is None


def test_explicit_path_disables_discovery(user_config, tmp_path, monkeypatch):
    write_config(user_config)
    explicit = tmp_path / "explicit.toml"
    write_config(explicit, "Explicit")
    discovery = Mock(side_effect=AssertionError("must not discover defaults"))
    monkeypatch.setattr(cli, "default_generators_path", discovery)
    app = start_cli(tmp_path, monkeypatch, "--generators", str(explicit))
    assert [g.name for g in app.generators] == ["Explicit"]
    discovery.assert_not_called()


def test_missing_explicit_does_not_fall_back(user_config, tmp_path, monkeypatch):
    write_config(user_config)
    app = start_cli(tmp_path, monkeypatch, "--generators", str(tmp_path / "missing"))
    assert app.generators == []
    assert app.generator_error.startswith("Cannot load generators:")


def test_missing_default_ignores_repository(user_config, tmp_path, monkeypatch):
    write_config(tmp_path / "generators.toml", "Repository")
    write_config(tmp_path / "kvide" / "generators.toml", "Repository")
    monkeypatch.chdir(tmp_path)
    assert cli.default_generators_path() is None
    app = start_cli(tmp_path, monkeypatch)
    assert app.generators == []
    assert app.generator_error is None


def test_xdg_overrides_home(user_config, tmp_path, monkeypatch):
    write_config(user_config)
    directory = tmp_path / "xdg"
    selected = directory / "kvide" / "generators.toml"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(directory))
    assert cli.default_generators_path() is None
    write_config(selected, "XDG")
    assert cli.default_generators_path() == selected
    assert [g.name for g in start_cli(tmp_path, monkeypatch).generators] == ["XDG"]


@pytest.mark.parametrize("value", ["", ".", "relative"])
def test_relative_xdg_uses_home(user_config, monkeypatch, value):
    write_config(user_config)
    monkeypatch.setenv("XDG_CONFIG_HOME", value)
    assert cli.default_generators_path() == user_config


def test_windows_appdata(user_config, tmp_path, monkeypatch):
    write_config(user_config)
    monkeypatch.setattr(cli.sys, "platform", "win32")
    assert cli.default_generators_path() is None
    monkeypatch.setenv("APPDATA", "relative")
    assert cli.default_generators_path() is None
    directory = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(directory))
    assert cli.default_generators_path() is None
    selected = directory / "kvide" / "generators.toml"
    write_config(selected)
    assert cli.default_generators_path() == selected


@pytest.mark.parametrize("content", ["[invalid", '[[generators]]\nname = "Bad"\ncommand = []'])
def test_invalid_default_notifies_at_startup(user_config, tmp_path, monkeypatch, content):
    user_config.parent.mkdir(parents=True)
    user_config.write_text(content, encoding="utf-8")
    app = start_cli(tmp_path, monkeypatch)
    assert app.generators == []
    assert app.generator_error.startswith("Cannot load generators:")
    notify = Mock()
    monkeypatch.setattr(app, "notify", notify)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            notify.assert_called_once_with(
                app.generator_error, severity="error", markup=False,
            )

    asyncio.run(scenario())
