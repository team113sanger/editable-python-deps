"""Thin Poetry subprocess wrappers, all routed through a SubprocessRunner.

Mirrors the bash helpers ``_editable_deps_check_poetry`` and
``_editable_deps_poetry_install_sync_if_supported``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from editable_python_deps import constants as CONST
from editable_python_deps.exceptions import PoetryNotFoundError
from editable_python_deps.runner import SubprocessRunner

logger = logging.getLogger(__name__)


def poetry_is_available(runner: SubprocessRunner) -> bool:
    """Return True if poetry is on PATH and runs."""
    try:
        result = runner.probe_env([CONST.POETRY_BIN, "--version"], check=False)
    except Exception:  # noqa: BLE001
        return False
    return result.returncode == 0


def require_poetry(runner: SubprocessRunner) -> None:
    """Raise PoetryNotFoundError if poetry is not available."""
    if not poetry_is_available(runner):
        raise PoetryNotFoundError("Poetry is not installed or not on the PATH.")


def poetry_add_editable(
    runner: SubprocessRunner, project_dir: Path, repo_path: Path
) -> None:
    runner.run(
        [CONST.POETRY_BIN, "add", "--editable", str(repo_path)],
        cwd=project_dir,
    )


def _poetry_help_sync_supported(runner: SubprocessRunner) -> bool:
    result = runner.probe_env([CONST.POETRY_BIN, "help", "sync"], check=False)
    return result.returncode == 0


def _poetry_install_sync_flag_supported(runner: SubprocessRunner) -> bool:
    result = runner.probe_env([CONST.POETRY_BIN, "install", "--help"], check=False)
    return "--sync" in (result.stdout or "")


def poetry_sync_or_install(runner: SubprocessRunner, project_dir: Path) -> None:
    """Run the most modern equivalent of ``poetry sync`` available.

    Preference order (mirrors the bash script):
      1. ``poetry sync`` (newer Poetry; preferred)
      2. ``poetry install --sync`` (older Poetry; no sync command)
      3. ``poetry install`` (very old Poetry)
    """
    if _poetry_help_sync_supported(runner):
        runner.run([CONST.POETRY_BIN, "sync"], cwd=project_dir)
        return
    if _poetry_install_sync_flag_supported(runner):
        runner.run([CONST.POETRY_BIN, "install", "--sync"], cwd=project_dir)
        return
    logger.info(
        "Neither 'poetry sync' nor 'poetry install --sync' is available; "
        "using plain 'poetry install'."
    )
    runner.run([CONST.POETRY_BIN, "install"], cwd=project_dir)
