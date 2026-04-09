"""Unit tests for editable_python_deps.cli using click.testing.CliRunner."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from editable_python_deps.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli__help__lists_all_subcommands(runner):
    # Given a CliRunner
    # When --help is invoked
    result = runner.invoke(cli, ["--help"])

    # Then the help output exits 0 and lists all four subcommands
    assert result.exit_code == 0
    for subcommand in ("on", "off", "status", "setup"):
        assert subcommand in result.output


def test_cli__on__help(runner):
    # Given a CliRunner
    # When `on --help` is invoked
    result = runner.invoke(cli, ["on", "--help"])

    # Then the subcommand-level help exits 0
    assert result.exit_code == 0
    assert "editable" in result.output.lower()


def test_cli__off__help(runner):
    # When `off --help` is invoked
    result = runner.invoke(cli, ["off", "--help"])

    # Then the subcommand-level help exits 0
    assert result.exit_code == 0
    assert "non-editable" in result.output.lower() or "restore" in result.output.lower()


def test_cli__dry_run_propagates_to_action(runner, monkeypatch):
    # Given an action that records the dry_run value it received
    captured = {}

    def fake_action(*, config_path, dry_run):
        captured["dry_run"] = dry_run
        captured["config_path"] = config_path
        return True

    monkeypatch.setattr(
        "editable_python_deps.actions.editable_dependencies", fake_action
    )

    # When --dry-run on is invoked
    result = runner.invoke(cli, ["--dry-run", "on"])

    # Then the action saw dry_run=True
    assert result.exit_code == 0, result.output
    assert captured["dry_run"] is True


def test_cli__config_option_propagates_to_action(runner, monkeypatch, tmp_path):
    # Given an action that records the config_path it received
    captured = {}
    target = tmp_path / "custom.toml"
    target.write_text("placeholder")

    def fake_action(*, config_path, dry_run):
        captured["config_path"] = config_path
        return True

    monkeypatch.setattr("editable_python_deps.actions.show_status", fake_action)

    # When -c <path> status is invoked
    result = runner.invoke(cli, ["-c", str(target), "status"])

    # Then the action saw the supplied config path
    assert result.exit_code == 0, result.output
    assert captured["config_path"] == target


def test_cli__action_returning_false_exits_one(runner, monkeypatch):
    # Given an action that returns False
    monkeypatch.setattr("editable_python_deps.actions.show_status", lambda **kw: False)

    # When status is invoked
    result = runner.invoke(cli, ["status"])

    # Then the CLI exits with code 1
    assert result.exit_code == 1


def test_cli__action_raising_known_error_exits_one_with_clean_message(
    runner, monkeypatch
):
    # Given an action that raises an EditablePythonDepsError subclass
    from editable_python_deps.exceptions import BackupStateError

    def boom(**kw):
        raise BackupStateError("backup files missing")

    monkeypatch.setattr("editable_python_deps.actions.no_editable_dependencies", boom)

    # When off is invoked
    result = runner.invoke(cli, ["off"])

    # Then exit code is 1 and the message is formatted with "Error:" prefix
    assert result.exit_code == 1
    assert "Error: backup files missing" in result.output


def test_cli__keyboard_interrupt_exits_two(runner, monkeypatch):
    # Given an action that raises KeyboardInterrupt
    def cancel(**kw):
        raise KeyboardInterrupt

    monkeypatch.setattr("editable_python_deps.actions.run_setup", cancel)

    # When setup is invoked
    result = runner.invoke(cli, ["setup"])

    # Then exit code is 2
    assert result.exit_code == 2
    assert "cancelled" in result.output.lower()
