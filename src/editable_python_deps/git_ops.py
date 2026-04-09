"""Thin git subprocess wrappers, all routed through a SubprocessRunner.

Mutating operations use ``runner.run`` and are skipped in dry-run mode.
Read-only state probes use ``runner.probe_state`` with a sensible default
so dry-run can still make decisions.
"""

from __future__ import annotations

import logging
from pathlib import Path

from editable_python_deps import constants as CONST
from editable_python_deps.io import (
    Printer,
    default_printer,
    style_info,
    style_muted,
    style_warning,
)
from editable_python_deps.runner import SubprocessRunner

logger = logging.getLogger(__name__)


# --- environment probes -----------------------------------------------------


def git_is_available(runner: SubprocessRunner) -> bool:
    """Return True if ``git`` is on PATH."""
    try:
        result = runner.probe_env([CONST.GIT_BIN, "--version"], check=False)
    except Exception:  # noqa: BLE001
        return False
    return result.returncode == 0


# --- mutating operations ----------------------------------------------------


def git_clone_branch(
    runner: SubprocessRunner, url: str, dest: Path, *, branch: str
) -> None:
    runner.run(
        [CONST.GIT_BIN, "clone", "--branch", branch, url, str(dest)],
    )


def git_fetch(
    runner: SubprocessRunner,
    repo_dir: Path,
    *,
    remote: str = "origin",
    branch: str,
) -> None:
    runner.run(
        [CONST.GIT_BIN, "-C", str(repo_dir), "fetch", remote, branch, "--quiet"],
    )


def git_merge_ff_only(runner: SubprocessRunner, repo_dir: Path, *, ref: str) -> None:
    runner.run(
        [CONST.GIT_BIN, "-C", str(repo_dir), "merge", "--ff-only", ref],
    )


# --- state probes -----------------------------------------------------------


def git_rev_parse(runner: SubprocessRunner, repo_dir: Path, *, ref: str) -> str:
    """Return the SHA pointed at by ``ref`` (HEAD, FETCH_HEAD, ...)."""
    fake_sha = "0" * 40
    result = runner.probe_state(
        [CONST.GIT_BIN, "-C", str(repo_dir), "rev-parse", ref],
        dry_run_stdout=fake_sha + "\n",
    )
    return result.stdout.strip()


def git_is_ancestor(
    runner: SubprocessRunner,
    repo_dir: Path,
    *,
    ancestor: str,
    descendant: str,
) -> bool:
    """Return True iff ``ancestor`` is reachable from ``descendant``.

    Wraps ``git merge-base --is-ancestor <ancestor> <descendant>`` (exits 0
    when true, 1 when false). Used to gate fast-forward pulls: a clean FF
    is safe iff ``HEAD`` is an ancestor of ``FETCH_HEAD``.
    """
    result = runner.probe_state(
        [
            CONST.GIT_BIN,
            "-C",
            str(repo_dir),
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
        ],
        check=False,
        dry_run_returncode=0,  # dry-run assumes the FF is safe
    )
    return result.returncode == 0


def git_status_is_clean(runner: SubprocessRunner, repo_dir: Path) -> bool:
    """Return True iff the working tree, index, and untracked set are all clean.

    Mirrors the bash script: a repo is "dirty" if any of:
      * ``git diff`` shows unstaged changes,
      * ``git diff --cached`` shows staged changes,
      * ``git ls-files --others --exclude-standard`` shows untracked files.
    """
    # Use status --porcelain which combines all three checks in one call.
    result = runner.probe_state(
        [CONST.GIT_BIN, "-C", str(repo_dir), "status", "--porcelain"],
        dry_run_stdout="",
    )
    return result.stdout.strip() == ""


def show_diff_no_index(
    runner: SubprocessRunner,
    left: Path,
    right: Path,
    *,
    header: str,
    printer: Printer = default_printer,
) -> None:
    """Print a coloured ``git diff --no-index`` between two files.

    Used purely for human-readable output during ``off`` so the user can see
    any unrelated WIP edits about to be overwritten by the restore.

    Falls back to ``diff -u`` if ``git`` is not on PATH.
    """
    printer("")
    printer(style_info(header))
    printer(
        style_muted("  ")
        + style_warning("LEFT")
        + style_muted(f"  (---) = original backup (non-editable): {left}")
    )
    printer(
        style_muted("  ")
        + style_warning("RIGHT")
        + style_muted(f" (+++) = current (editable)            : {right}")
    )
    printer(
        style_muted("  (In the diff below: '-' lines are ")
        + style_warning("LEFT")
        + style_muted("/backup; '+' lines are ")
        + style_warning("RIGHT")
        + style_muted("/current)\n")
    )

    if git_is_available(runner):
        # Probe whether there is any difference at all.
        quiet = runner.probe_state(
            [
                CONST.GIT_BIN,
                "-c",
                "core.pager=cat",
                "-c",
                "pager.diff=false",
                "diff",
                "--no-index",
                "--quiet",
                str(left),
                str(right),
            ],
            check=False,
            dry_run_stdout="",
            dry_run_returncode=0,
        )
        if quiet.returncode == 0:
            printer(style_muted("(no differences)"))
            return

        diff_result = runner.probe_state(
            [
                CONST.GIT_BIN,
                "-c",
                "core.pager=cat",
                "-c",
                "pager.diff=false",
                "diff",
                "--no-index",
                "--color=always",
                str(left),
                str(right),
            ],
            check=False,
            dry_run_stdout="(diff suppressed in dry-run)\n",
        )
        printer(diff_result.stdout.rstrip("\n"))
        printer(style_muted("End of diff"))
        return

    # Fallback: plain diff -u
    diff_result = runner.probe_state(
        ["diff", "-u", str(left), str(right)],
        check=False,
        dry_run_stdout="(diff suppressed in dry-run)\n",
    )
    printer(diff_result.stdout.rstrip("\n"))
    printer(style_muted("End of diff"))
