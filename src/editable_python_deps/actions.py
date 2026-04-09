"""High-level actions composed by the click subcommands.

Each public function returns ``True`` on success so it can flow through the
existing ``_cli_wrapper`` in :mod:`editable_python_deps.cli`.
"""

from __future__ import annotations

import logging
import shutil
import typing as t
from pathlib import Path

from editable_python_deps import constants as CONST
from editable_python_deps import git_ops, poetry_ops
from editable_python_deps.config import (
    Config,
    default_config_path,
    dumps_config,
    load_config,
)
from editable_python_deps.exceptions import (
    BackupStateError,
    ConfigNotFoundError,
)
from editable_python_deps.project import (
    ProjectPaths,
    find_project_dir,
)
from editable_python_deps.runner import SubprocessRunner

logger = logging.getLogger(__name__)


# --- public actions ---------------------------------------------------------


def editable_dependencies(
    *,
    config_path: t.Optional[Path],
    dry_run: bool,
) -> bool:
    """Switch to editable dependency state. Idempotent w.r.t. backup creation."""
    runner = SubprocessRunner(dry_run=dry_run)
    poetry_ops.require_poetry(runner)
    project_dir = find_project_dir()
    paths = ProjectPaths.from_project_dir(project_dir)
    paths.require_pyproject_and_lock()

    config = _load_or_offer_setup(config_path, project_dir, runner=runner)

    if paths.has_backups():
        logger.info(
            "Backup files already exist; not overwriting them. "
            "If you expected to be in non-editable state, run "
            "`editable-python-deps off` first."
        )
    else:
        logger.info("Snapshotting non-editable state to backup files.")
        _copy_file(runner, paths.pyproject, paths.backup_pyproject)
        _copy_file(runner, paths.lock, paths.backup_lock)

    _ensure_clones_exist(runner, config, project_dir)

    base_dir = config.absolute_cloning_directory(project_dir)
    for source in config.sources:
        repo_path = base_dir / source.name
        logger.info("Adding editable: %s from %s", source.name, repo_path)
        poetry_ops.poetry_add_editable(runner, project_dir, repo_path)

    logger.info("Editable dependency state is now active.")
    return True


def no_editable_dependencies(
    *,
    config_path: t.Optional[Path],
    dry_run: bool,
) -> bool:
    """Restore non-editable state from backup files. Lenient when config missing."""
    runner = SubprocessRunner(dry_run=dry_run)
    poetry_ops.require_poetry(runner)
    project_dir = find_project_dir()
    paths = ProjectPaths.from_project_dir(project_dir)

    if not paths.has_backups():
        raise BackupStateError(
            "Backup files are missing; cannot safely restore non-editable state.\n"
            f"  Expected:\n    {paths.backup_pyproject}\n    {paths.backup_lock}\n\n"
            "  If you have run `editable-python-deps off` successfully before,\n"
            "  then the backup files have already been removed.\n\n"
            "  Otherwise recover pyproject.toml/poetry.lock from git history (or re-checkout) "
            "and retry."
        )

    # Lenient config handling: warn if missing, proceed regardless.
    try:
        load_config(config_path or default_config_path(project_dir))
    except ConfigNotFoundError as exc:
        logger.warning(
            "%s. Restoring from backups anyway. Run `editable-python-deps setup` "
            "afterwards to recreate the config.",
            exc,
        )

    git_ops.show_diff_no_index(
        runner,
        paths.backup_pyproject,
        paths.pyproject,
        header="Diff: pyproject.toml restore preview",
    )

    logger.info("Restoring non-editable files from backup.")
    _copy_file(runner, paths.backup_pyproject, paths.pyproject)
    _copy_file(runner, paths.backup_lock, paths.lock)

    logger.info("Re-installing from restored lockfile.")
    poetry_ops.poetry_sync_or_install(runner, project_dir)

    logger.info("Cleaning up backup files.")
    _delete_file(runner, paths.backup_pyproject)
    _delete_file(runner, paths.backup_lock)

    logger.info("Restored non-editable dependency state.")
    return True


def show_status(
    *,
    config_path: t.Optional[Path],
    dry_run: bool,  # accepted for symmetry; unused
) -> bool:
    """Print: project dir, config presence, editable/non-editable state, sources."""
    del dry_run  # symmetric signature only

    project_dir = find_project_dir()
    paths = ProjectPaths.from_project_dir(project_dir)
    state = "editable" if paths.has_backups() else "non-editable"
    if paths.has_partial_backups():
        state = "corrupt (only one backup file present)"

    target_path = config_path or default_config_path(project_dir)
    sources_summary: str
    config_loc: str
    try:
        config = load_config(target_path)
        config_loc = str(target_path)
        sources_summary = "\n".join(
            f"    - {s.name} <- {s.url}" for s in config.sources
        )
    except ConfigNotFoundError:
        config_loc = f"(missing) expected at {target_path}"
        sources_summary = "    (no sources — config missing)"

    logger.info("Project directory : %s", project_dir)
    logger.info("Config file       : %s", config_loc)
    logger.info("Dependency state  : %s", state)
    logger.info("Sources:\n%s", sources_summary)
    return True


def run_setup(
    *,
    config_path: t.Optional[Path],
    dry_run: bool,
) -> bool:
    """Run the interactive wizard, write the config, and ensure clones exist."""
    runner = SubprocessRunner(dry_run=dry_run)
    project_dir = find_project_dir()
    target_path = config_path or default_config_path(project_dir)

    # Late import so the prompt_toolkit dep cost is only paid when used.
    from editable_python_deps.prompts import run_setup_wizard

    config = run_setup_wizard(project_dir=project_dir, existing_path=target_path)

    rendered = dumps_config(config)
    _write_text_file(runner, target_path, rendered)

    _ensure_clones_exist(runner, config, project_dir)
    _augment_ignore_file(runner, project_dir, config, filename=".dockerignore")
    _augment_ignore_file(runner, project_dir, config, filename=".gitignore")

    logger.info("Setup complete. Config written to %s.", target_path)
    return True


# --- private composition helpers --------------------------------------------


def _load_or_offer_setup(
    config_path: t.Optional[Path],
    project_dir: Path,
    *,
    runner: SubprocessRunner,
) -> Config:
    """Load config; if missing, run setup wizard once and reload."""
    target = config_path or default_config_path(project_dir)
    try:
        return load_config(target)
    except ConfigNotFoundError:
        logger.info("No config at %s; launching setup wizard.", target)
        run_setup(config_path=config_path, dry_run=runner.dry_run)
        return load_config(target)


def _ensure_clones_exist(
    runner: SubprocessRunner, config: Config, project_dir: Path
) -> None:
    """Clone or update each editable source under the cloning directory.

    Mirrors :func:`_editable_deps_git_clone_or_update` from the bash script:

    1. If the repo doesn't exist locally, clone it on the configured branch.
    2. If it exists with uncommitted/untracked changes, log a warning and skip.
    3. Otherwise fetch and fast-forward to the configured branch.
    """
    base_dir = config.absolute_cloning_directory(project_dir)
    _make_directory(runner, base_dir)

    for source in config.sources:
        repo_path = base_dir / source.name
        branch = config.effective_branch(source)

        if not repo_path.exists():
            logger.info(
                "Cloning %s from %s into %s ...",
                source.name,
                source.url,
                repo_path,
            )
            git_ops.git_clone_branch(runner, source.url, repo_path, branch=branch)
            continue

        if not git_ops.git_status_is_clean(runner, repo_path):
            logger.warning(
                "%s has uncommitted changes — skipping pull. "
                "Push or discard changes in %s to use the latest %s commit.",
                source.name,
                repo_path,
                branch,
            )
            continue

        _fetch_and_ff_if_safe(runner, source.name, repo_path, branch)
    return


def _fetch_and_ff_if_safe(
    runner: SubprocessRunner, name: str, repo_path: Path, branch: str
) -> None:
    """Fetch the configured branch and fast-forward only when it is safe.

    Skips the FF (with a warning) if the local branch is ahead of, or has
    diverged from, the remote — leaving any unpushed work intact.
    """
    logger.info("Fetching latest %s for %s ...", branch, name)
    git_ops.git_fetch(runner, repo_path, branch=branch)
    local_sha = git_ops.git_rev_parse(runner, repo_path, ref="HEAD")
    remote_sha = git_ops.git_rev_parse(runner, repo_path, ref="FETCH_HEAD")
    if local_sha == remote_sha:
        logger.info("%s is already up to date.", name)
        return

    if git_ops.git_is_ancestor(
        runner, repo_path, ancestor="HEAD", descendant="FETCH_HEAD"
    ):
        logger.info("Fast-forwarding %s to latest %s.", name, branch)
        git_ops.git_merge_ff_only(runner, repo_path, ref="FETCH_HEAD")
        return

    logger.warning(
        "%s has unpushed local commits on %s (or has diverged from "
        "origin/%s); skipping fast-forward to avoid clobbering your "
        "work. Push (or rebase) the local commits in %s and re-run "
        "`editable-python-deps on`.",
        name,
        branch,
        branch,
        repo_path,
    )


def _augment_ignore_file(
    runner: SubprocessRunner, project_dir: Path, config: Config, filename: str
) -> None:
    """Append the cloning directory to .dockerignore or .gitignore if it exists."""
    ignore_file = project_dir / filename
    if not ignore_file.is_file():
        return

    entry = config.local_cloning_directory.as_posix().rstrip("/") + "/"
    existing = ignore_file.read_text(encoding="utf-8")
    needle = f"\n{entry}\n"
    if needle in ("\n" + existing + "\n"):
        return

    def _append() -> None:
        with ignore_file.open("a", encoding="utf-8") as fh:
            if not existing.endswith("\n"):
                fh.write("\n")
            fh.write(CONST.IGNORE_FILE_MARKER_COMMENT + "\n")
            fh.write(entry + "\n")

    runner.act(f"append {entry!r} to {ignore_file}", _append)


# --- thin filesystem wrappers (kept here, not split into a module) ---------


def _copy_file(runner: SubprocessRunner, src: Path, dst: Path) -> None:
    runner.act(
        f"cp {src} -> {dst}",
        lambda: shutil.copy2(str(src), str(dst)),
    )


def _delete_file(runner: SubprocessRunner, path: Path) -> None:
    runner.act(
        f"rm {path}",
        lambda: path.unlink(),
    )


def _make_directory(runner: SubprocessRunner, path: Path) -> None:
    runner.act(
        f"mkdir -p {path}",
        lambda: path.mkdir(parents=True, exist_ok=True),
    )


def _write_text_file(runner: SubprocessRunner, path: Path, content: str) -> None:
    runner.act(
        f"write {path}",
        lambda: path.write_text(content, encoding="utf-8"),
    )
