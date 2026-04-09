"""Project directory discovery + path computation.

A "project" here means the directory containing a ``pyproject.toml`` and a
``poetry.lock`` (and optionally a ``.editable-deps.toml`` and the backup
files when in editable state).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from editable_python_deps import constants as CONST
from editable_python_deps.exceptions import (
    BackupStateError,
    ProjectDirNotFoundError,
)


def find_project_dir(start: Path | None = None) -> Path:
    """Pick the directory we should treat as the project root.

    Mirrors :func:`_editable_deps_pick_project_dir` from the bash script:
    prefer the current working directory if it contains a ``pyproject.toml``,
    otherwise raise. We deliberately do **not** walk up parent directories;
    callers should ``cd`` into the project root first.
    """
    cwd = (start or Path.cwd()).resolve()
    if (cwd / "pyproject.toml").is_file():
        return cwd
    raise ProjectDirNotFoundError(
        f"Could not find pyproject.toml in {cwd}. "
        f"cd into your project root and try again."
    )


@dataclass(frozen=True)
class ProjectPaths:
    """All the file paths we care about for one project, derived from project_dir."""

    project_dir: Path
    pyproject: Path
    lock: Path
    backup_pyproject: Path
    backup_lock: Path

    @classmethod
    def from_project_dir(cls, project_dir: Path) -> "ProjectPaths":
        return cls(
            project_dir=project_dir,
            pyproject=project_dir / "pyproject.toml",
            lock=project_dir / "poetry.lock",
            backup_pyproject=project_dir / CONST.BACKUP_PYPROJECT_FILENAME,
            backup_lock=project_dir / CONST.BACKUP_LOCK_FILENAME,
        )

    def has_backups(self) -> bool:
        """True iff both backup files exist (i.e. we are in editable state)."""
        return self.backup_pyproject.is_file() and self.backup_lock.is_file()

    def has_partial_backups(self) -> bool:
        """True iff exactly one of the backup files exists (corrupted state)."""
        return self.backup_pyproject.is_file() != self.backup_lock.is_file()

    def require_pyproject_and_lock(self) -> None:
        """Raise BackupStateError if pyproject or lock are missing."""
        missing = []
        if not self.pyproject.is_file():
            missing.append(str(self.pyproject))
        if not self.lock.is_file():
            missing.append(str(self.lock))
        if missing:
            raise BackupStateError(
                "Missing required project files:\n  " + "\n  ".join(missing)
            )
