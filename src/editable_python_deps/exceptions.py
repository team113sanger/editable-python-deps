class EditablePythonDepsError(Exception):
    """Base exception for editable-python-deps."""


class ConfigError(EditablePythonDepsError):
    """Raised when the config file is malformed or fails validation."""


class ConfigNotFoundError(ConfigError):
    """Raised when the config file does not exist at the expected path."""


class BackupStateError(EditablePythonDepsError):
    """Raised when the backup files are in an unexpected state for the operation."""


class SubprocessFailureError(EditablePythonDepsError):
    """Raised when a subprocess invocation fails (non-zero exit or executable missing)."""


class WorkingTreeNotCleanError(EditablePythonDepsError):
    """Raised when a clone has uncommitted/untracked changes and we refuse to proceed."""


class PoetryNotFoundError(EditablePythonDepsError):
    """Raised when poetry is not installed or not on the PATH."""


class ProjectDirNotFoundError(EditablePythonDepsError):
    """Raised when no pyproject.toml can be found from the current working directory."""
