"""Atomic subprocess + filesystem mutation wrapper.

The :class:`SubprocessRunner` is the single chokepoint for every git, poetry,
and filesystem mutation in the package. It exists so that ``--dry-run`` is a
single, well-defined behaviour switch rather than a flag every helper has to
re-implement.

Method semantics:

- :meth:`SubprocessRunner.run` — mutating subprocess. Skipped + logged in
  dry-run mode.
- :meth:`SubprocessRunner.act` — mutating Python callable (e.g. ``shutil.copy``).
  Skipped + logged in dry-run mode.
- :meth:`SubprocessRunner.probe_env` — static environment check (e.g.
  ``git --version``). **Always** executes regardless of dry-run because the
  result is needed to fail fast on missing tooling.
- :meth:`SubprocessRunner.probe_state` — dynamic state check (e.g.
  ``git status --porcelain``). Faked with a caller-supplied default in dry-run
  so the surrounding logic can still make decisions.

Why four methods rather than one method with kwargs: self-documenting call
sites. ``runner.probe_env(["poetry", "help", "sync"])`` reads obviously
differently from ``runner.probe_state(...)``.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
import typing as t
from dataclasses import dataclass
from pathlib import Path

from editable_python_deps import constants as CONST
from editable_python_deps.exceptions import SubprocessFailureError

logger = logging.getLogger(__name__)

CommandLike = t.Sequence[str]


@dataclass
class RunResult:
    """Lightweight stand-in for ``subprocess.CompletedProcess``.

    The runner returns instances of this class so that dry-run code paths can
    fabricate plausible results without invoking ``subprocess.run`` at all.
    """

    args: t.List[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    skipped: bool = False  # True when produced by the dry-run code path

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class SubprocessRunner:
    """Single atomic wrapper for all subprocess + Python-level mutations."""

    def __init__(
        self,
        *,
        dry_run: bool = False,
        logger_: t.Optional[logging.Logger] = None,
    ) -> None:
        self.dry_run = dry_run
        self._log = logger_ or logger

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _format_cmd(cmd: CommandLike, cwd: t.Optional[Path]) -> str:
        quoted = " ".join(shlex.quote(str(c)) for c in cmd)
        return f"{quoted} (cwd={cwd})" if cwd else quoted

    @staticmethod
    def _coerce_cmd(cmd: CommandLike) -> t.List[str]:
        return [str(c) for c in cmd]

    # ------------------------------------------------------------------- public

    def run(
        self,
        cmd: CommandLike,
        *,
        cwd: t.Optional[Path] = None,
        env: t.Optional[t.Mapping[str, str]] = None,
        check: bool = True,
        capture_output: bool = False,
    ) -> RunResult:
        """Mutating subprocess. Skipped (logged) in dry-run mode."""
        coerced = self._coerce_cmd(cmd)
        formatted = self._format_cmd(coerced, cwd)
        self._log.debug("Running: %s", formatted)
        if self.dry_run:
            self._log.info("%s%s", CONST.DRY_RUN_RUN_PREFIX, formatted)
            return RunResult(args=coerced, returncode=0, skipped=True)
        return self._execute(
            coerced, cwd=cwd, env=env, check=check, capture_output=capture_output
        )

    def act(self, description: str, fn: t.Callable[[], t.Any]) -> None:
        """Mutating Python callable. Skipped (logged) in dry-run mode."""
        self._log.debug("Acting: %s", description)
        if self.dry_run:
            self._log.info("%s%s", CONST.DRY_RUN_ACT_PREFIX, description)
            return None
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            raise SubprocessFailureError(
                f"Filesystem operation failed: {description}: {exc}"
            ) from exc
        return None

    def probe_env(
        self,
        cmd: CommandLike,
        *,
        cwd: t.Optional[Path] = None,
        env: t.Optional[t.Mapping[str, str]] = None,
        check: bool = True,
    ) -> RunResult:
        """Static environment probe. Always executes (even in dry-run)."""
        coerced = self._coerce_cmd(cmd)
        formatted = self._format_cmd(coerced, cwd)
        self._log.debug("Probing env: %s", formatted)
        return self._execute(
            coerced, cwd=cwd, env=env, check=check, capture_output=True
        )

    def probe_state(
        self,
        cmd: CommandLike,
        *,
        cwd: t.Optional[Path] = None,
        env: t.Optional[t.Mapping[str, str]] = None,
        dry_run_stdout: str = "",
        dry_run_returncode: int = 0,
        check: bool = True,
    ) -> RunResult:
        """Dynamic state probe. Faked with caller-supplied default in dry-run."""
        coerced = self._coerce_cmd(cmd)
        formatted = self._format_cmd(coerced, cwd)
        self._log.debug("Probing state: %s", formatted)
        if self.dry_run:
            self._log.info(
                "%s%s [faked: returncode=%d]",
                CONST.DRY_RUN_RUN_PREFIX,
                formatted,
                dry_run_returncode,
            )
            return RunResult(
                args=coerced,
                returncode=dry_run_returncode,
                stdout=dry_run_stdout,
                skipped=True,
            )
        return self._execute(
            coerced, cwd=cwd, env=env, check=check, capture_output=True
        )

    # ------------------------------------------------------------------ private

    def _execute(
        self,
        cmd: t.List[str],
        *,
        cwd: t.Optional[Path],
        env: t.Optional[t.Mapping[str, str]],
        check: bool,
        capture_output: bool,
    ) -> RunResult:
        try:
            completed = subprocess.run(  # noqa: S603 - cmd is a controlled list
                cmd,
                cwd=str(cwd) if cwd else None,
                env=dict(env) if env else None,
                check=False,
                text=True,
                capture_output=capture_output,
            )
        except FileNotFoundError as exc:
            raise SubprocessFailureError(
                f"Command not found: {cmd[0]!r} ({exc})"
            ) from exc
        if check and completed.returncode != 0:
            raise SubprocessFailureError(
                f"Command failed (exit {completed.returncode}): "
                f"{self._format_cmd(cmd, cwd)}\n"
                f"  stdout: {(completed.stdout or '')!r}\n"
                f"  stderr: {(completed.stderr or '')!r}"
            )
        return RunResult(
            args=cmd,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            skipped=False,
        )
