"""Unit tests for editable_python_deps.poetry_ops."""

from __future__ import annotations

from pathlib import Path

import pytest

from editable_python_deps import poetry_ops
from editable_python_deps.exceptions import PoetryNotFoundError


# --- poetry_is_available / require_poetry -----------------------------------


def test_poetry_is_available__true_when_command_succeeds(fp, runner_real):
    # Given a registered poetry --version
    fp.register(["poetry", "--version"], stdout="Poetry (version 2.3.2)\n")

    # When poetry_is_available is queried
    actual = poetry_ops.poetry_is_available(runner_real)

    # Then it is True
    assert actual is True


def test_poetry_is_available__false_when_command_fails(fp, runner_real):
    # Given a poetry --version that returns non-zero
    fp.register(["poetry", "--version"], returncode=127)

    # When poetry_is_available is queried
    actual = poetry_ops.poetry_is_available(runner_real)

    # Then it is False
    assert actual is False


def test_require_poetry__noop_when_available(fp, runner_real):
    # Given poetry is available
    fp.register(["poetry", "--version"], stdout="Poetry (version 2.3.2)\n")

    # When require_poetry is called
    # Then no exception is raised
    poetry_ops.require_poetry(runner_real)


def test_require_poetry__raises_when_unavailable(fp, runner_real):
    # Given poetry is not available
    fp.register(["poetry", "--version"], returncode=127)

    # When require_poetry is called
    # Then PoetryNotFoundError is raised
    with pytest.raises(PoetryNotFoundError):
        poetry_ops.require_poetry(runner_real)


# --- poetry_add_editable ----------------------------------------------------


def test_poetry_add_editable(fp, runner_real, tmp_path):
    # Given a registered poetry add --editable command
    repo_path = tmp_path / "repo"
    fp.register(["poetry", "add", "--editable", str(repo_path)])

    # When poetry_add_editable is invoked
    poetry_ops.poetry_add_editable(runner_real, tmp_path, repo_path)

    # Then the registered command was called
    assert fp.call_count(["poetry", "add", "--editable", str(repo_path)]) == 1


# --- poetry_sync_or_install -------------------------------------------------


def test_poetry_sync_or_install__uses_poetry_sync_when_supported(
    fp, runner_real, tmp_path
):
    # Given poetry help sync exits zero (sync command supported)
    fp.register(["poetry", "help", "sync"], returncode=0)
    fp.register(["poetry", "sync"], returncode=0)

    # When poetry_sync_or_install is called
    poetry_ops.poetry_sync_or_install(runner_real, tmp_path)

    # Then `poetry sync` ran (and the install fallback did not)
    assert fp.call_count(["poetry", "sync"]) == 1


def test_poetry_sync_or_install__falls_back_to_install_sync_flag(
    fp, runner_real, tmp_path
):
    # Given help sync fails but install --help mentions --sync
    fp.register(["poetry", "help", "sync"], returncode=1)
    fp.register(
        ["poetry", "install", "--help"],
        returncode=0,
        stdout="Options:\n  --sync   Synchronize the environment.\n",
    )
    fp.register(["poetry", "install", "--sync"], returncode=0)

    # When poetry_sync_or_install is called
    poetry_ops.poetry_sync_or_install(runner_real, tmp_path)

    # Then `poetry install --sync` ran
    assert fp.call_count(["poetry", "install", "--sync"]) == 1


def test_poetry_sync_or_install__falls_back_to_plain_install(fp, runner_real, tmp_path):
    # Given neither sync nor --sync are supported
    fp.register(["poetry", "help", "sync"], returncode=1)
    fp.register(
        ["poetry", "install", "--help"],
        returncode=0,
        stdout="Options:\n  --no-dev   Skip dev dependencies.\n",
    )
    fp.register(["poetry", "install"], returncode=0)

    # When poetry_sync_or_install is called
    poetry_ops.poetry_sync_or_install(runner_real, tmp_path)

    # Then plain `poetry install` ran
    assert fp.call_count(["poetry", "install"]) == 1
