"""Unit tests for editable_python_deps.runner.SubprocessRunner."""

from __future__ import annotations

import logging

import pytest

from editable_python_deps.exceptions import SubprocessFailureError
from editable_python_deps.runner import RunResult, SubprocessRunner


# --- RunResult --------------------------------------------------------------


def test_RunResult__ok__true_when_returncode_is_zero():
    # Given a RunResult with a zero returncode
    result = RunResult(args=["echo"], returncode=0)

    # When ok is read
    actual = result.ok

    # Then it is True
    assert actual is True


def test_RunResult__ok__false_when_returncode_is_nonzero():
    # Given a RunResult with a non-zero returncode
    result = RunResult(args=["false"], returncode=1)

    # When ok is read
    actual = result.ok

    # Then it is False
    assert actual is False


# --- SubprocessRunner.run ---------------------------------------------------


def test_SubprocessRunner__run__executes_registered_command(fp, runner_real):
    # Given a registered fake command
    fp.register(["echo", "hello"], stdout="hello\n")

    # When run is called
    result = runner_real.run(["echo", "hello"], capture_output=True)

    # Then the registered command was invoked once and returned its stdout
    assert result.returncode == 0
    assert result.stdout == "hello\n"
    assert result.skipped is False
    assert fp.call_count(["echo", "hello"]) == 1


def test_SubprocessRunner__run__skips_execution_in_dry_run_mode(fp, caplog):
    # Given a runner in dry-run mode and a command that is NOT registered with fp
    runner = SubprocessRunner(dry_run=True)
    cmd = ["git", "clone", "git@example.com:foo/bar.git", "/tmp/dest"]

    # When run() is called
    with caplog.at_level(logging.INFO, logger="editable_python_deps.runner"):
        result = runner.run(cmd)

    # Then no subprocess was actually invoked, the result is marked skipped, and a log line was emitted
    assert result.skipped is True
    assert result.returncode == 0
    assert any("[dry-run] Would run" in r.message for r in caplog.records)
    assert fp.call_count(cmd) == 0


def test_SubprocessRunner__run__raises_subprocess_failure_on_nonzero(fp, runner_real):
    # Given a registered fake command that exits non-zero
    fp.register(["false"], returncode=1)

    # When run() is called with check=True (the default)
    # Then it raises SubprocessFailureError
    with pytest.raises(SubprocessFailureError) as exc_info:
        runner_real.run(["false"])
    assert "exit 1" in str(exc_info.value)


def test_SubprocessRunner__run__check_false_returns_nonzero_without_raising(
    fp, runner_real
):
    # Given a registered fake command that exits non-zero
    fp.register(["false"], returncode=2)

    # When run() is called with check=False
    result = runner_real.run(["false"], check=False)

    # Then it returns a RunResult carrying the returncode
    assert result.returncode == 2
    assert result.ok is False


def test_SubprocessRunner__run__file_not_found_translated_to_subprocess_failure(
    runner_real,
):
    # Given a command for an executable that does not exist
    cmd = ["this-binary-definitely-does-not-exist-zzzz"]

    # When run() is called
    # Then it raises SubprocessFailureError (not FileNotFoundError)
    with pytest.raises(SubprocessFailureError) as exc_info:
        runner_real.run(cmd)
    assert "Command not found" in str(exc_info.value)


# --- SubprocessRunner.act ---------------------------------------------------


def test_SubprocessRunner__act__executes_callable_when_not_dry_run(runner_real):
    # Given a flag we will flip from a callable
    flag = {"called": False}

    def _flip() -> None:
        flag["called"] = True

    # When act() is called
    runner_real.act("flip flag", _flip)

    # Then the callable ran
    assert flag["called"] is True


def test_SubprocessRunner__act__skips_callable_in_dry_run(runner_dry, caplog):
    # Given a callable that would mutate state
    flag = {"called": False}

    def _flip() -> None:
        flag["called"] = True

    # When act() is called on a dry-run runner
    with caplog.at_level(logging.INFO, logger="editable_python_deps.runner"):
        runner_dry.act("flip flag", _flip)

    # Then the callable did NOT run and a dry-run log line was emitted
    assert flag["called"] is False
    assert any("[dry-run] Would" in r.message for r in caplog.records)


def test_SubprocessRunner__act__wraps_unexpected_exception(runner_real):
    # Given a callable that raises an unexpected error
    def _boom() -> None:
        raise OSError("disk on fire")

    # When act() is called
    # Then the error is wrapped in SubprocessFailureError
    with pytest.raises(SubprocessFailureError) as exc_info:
        runner_real.act("boom", _boom)
    assert "boom" in str(exc_info.value)
    assert "disk on fire" in str(exc_info.value)


# --- SubprocessRunner.probe_env ---------------------------------------------


def test_SubprocessRunner__probe_env__always_executes_even_in_dry_run(fp):
    # Given a dry-run runner and a registered probe
    runner = SubprocessRunner(dry_run=True)
    fp.register(["git", "--version"], stdout="git version 2.42.0\n")

    # When probe_env is called
    result = runner.probe_env(["git", "--version"])

    # Then the registered command DID execute (probe_env ignores dry_run)
    assert result.returncode == 0
    assert "git version" in result.stdout
    assert result.skipped is False
    assert fp.call_count(["git", "--version"]) == 1


# --- SubprocessRunner.probe_state -------------------------------------------


def test_SubprocessRunner__probe_state__faked_in_dry_run_with_caller_default(fp):
    # Given a dry-run runner and a command NOT registered with fp
    runner = SubprocessRunner(dry_run=True)
    cmd = ["git", "-C", "/no/such/repo", "status", "--porcelain"]

    # When probe_state is called with a caller-supplied default stdout
    result = runner.probe_state(cmd, dry_run_stdout="", dry_run_returncode=0)

    # Then the result is the synthetic default and no subprocess ran
    assert result.skipped is True
    assert result.returncode == 0
    assert result.stdout == ""
    assert fp.call_count(cmd) == 0


def test_SubprocessRunner__probe_state__executes_when_not_dry_run(fp, runner_real):
    # Given a registered fake state probe
    fp.register(
        ["git", "-C", "/some/repo", "status", "--porcelain"],
        stdout=" M README.md\n",
    )

    # When probe_state is called on a real (non-dry-run) runner
    result = runner_real.probe_state(
        ["git", "-C", "/some/repo", "status", "--porcelain"],
        dry_run_stdout="",
    )

    # Then it really executed and returned the registered stdout
    assert result.skipped is False
    assert result.stdout == " M README.md\n"


def test_SubprocessRunner__run__emits_debug_log_on_every_call(fp, runner_real, caplog):
    # Given a registered command and a runner with DEBUG logging captured
    fp.register(["true"])

    # When run is called
    with caplog.at_level(logging.DEBUG, logger="editable_python_deps.runner"):
        runner_real.run(["true"])

    # Then a Running: ... debug line was emitted
    assert any(
        "Running:" in r.message and r.levelname == "DEBUG" for r in caplog.records
    )
