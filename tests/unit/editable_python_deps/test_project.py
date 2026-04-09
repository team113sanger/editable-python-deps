"""Unit tests for editable_python_deps.project."""

from __future__ import annotations

from pathlib import Path

import pytest

from editable_python_deps.exceptions import (
    BackupStateError,
    ProjectDirNotFoundError,
)
from editable_python_deps.project import ProjectPaths, find_project_dir


# --- find_project_dir -------------------------------------------------------


def test_find_project_dir__returns_start_when_pyproject_present(fake_project_dir):
    # Given a project directory containing pyproject.toml
    # When find_project_dir is called with that directory as the start
    actual = find_project_dir(start=fake_project_dir)

    # Then it returns the resolved project directory
    assert actual == fake_project_dir.resolve()


def test_find_project_dir__raises_when_pyproject_absent(tmp_path):
    # Given a directory with no pyproject.toml
    # When find_project_dir is called
    # Then it raises ProjectDirNotFoundError
    with pytest.raises(ProjectDirNotFoundError):
        find_project_dir(start=tmp_path)


# --- ProjectPaths -----------------------------------------------------------


def test_ProjectPaths__from_project_dir__derives_all_paths(fake_project_dir):
    # Given a fake project directory
    # When ProjectPaths is constructed
    paths = ProjectPaths.from_project_dir(fake_project_dir)

    # Then all derived paths sit alongside the project dir
    assert paths.project_dir == fake_project_dir
    assert paths.pyproject == fake_project_dir / "pyproject.toml"
    assert paths.lock == fake_project_dir / "poetry.lock"
    assert (
        paths.backup_pyproject
        == fake_project_dir / ".pyproject.toml.non-editable-backup"
    )
    assert paths.backup_lock == fake_project_dir / ".poetry.lock.non-editable-backup"


def test_ProjectPaths__has_backups__false_when_no_backups(fake_project_dir):
    # Given a project with no backup files
    paths = ProjectPaths.from_project_dir(fake_project_dir)

    # When has_backups is queried
    actual = paths.has_backups()

    # Then it is False
    assert actual is False


def test_ProjectPaths__has_backups__true_when_both_backups_exist(
    fake_project_with_backup,
):
    # Given a project with both backup files
    paths = ProjectPaths.from_project_dir(fake_project_with_backup)

    # When has_backups is queried
    actual = paths.has_backups()

    # Then it is True
    assert actual is True


def test_ProjectPaths__has_partial_backups__true_when_only_one_backup(
    fake_project_dir,
):
    # Given a project with only one of the two backup files
    paths = ProjectPaths.from_project_dir(fake_project_dir)
    paths.backup_pyproject.write_text("partial")

    # When has_partial_backups is queried
    actual = paths.has_partial_backups()

    # Then it is True
    assert actual is True


def test_ProjectPaths__require_pyproject_and_lock__raises_when_missing(tmp_path):
    # Given a directory with neither pyproject nor lock
    paths = ProjectPaths.from_project_dir(tmp_path)

    # When require_pyproject_and_lock is called
    # Then it raises BackupStateError listing both missing files
    with pytest.raises(BackupStateError) as exc_info:
        paths.require_pyproject_and_lock()
    msg = str(exc_info.value)
    assert "pyproject.toml" in msg
    assert "poetry.lock" in msg


def test_ProjectPaths__require_pyproject_and_lock__noop_when_present(
    fake_project_dir,
):
    # Given a fake project with both files
    paths = ProjectPaths.from_project_dir(fake_project_dir)

    # When require_pyproject_and_lock is called
    # Then it returns None silently
    assert paths.require_pyproject_and_lock() is None
