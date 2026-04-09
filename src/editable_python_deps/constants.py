# CLI constants
PROGRAM_NAME = "editable-python-deps"
PROGRAM_DESCRIPTION = (
    "Switch a Poetry project's dependencies between non-editable, lockfile-pinned "
    "form and editable git clones living under a local working directory."
)
DEFAULT_LOG_LEVEL = "INFO"

# Config file
DEFAULT_CONFIG_FILENAME = ".editable-deps.toml"
DEFAULT_LOCAL_CLONING_DIR = ".editable-deps/"
DEFAULT_BRANCH = "develop"
SUPPORTED_CONFIG_VERSIONS = frozenset({"1"})
CURRENT_CONFIG_VERSION = "1"

# Backup file names (located alongside pyproject.toml when in editable state).
BACKUP_PYPROJECT_FILENAME = ".pyproject.toml.non-editable-backup"
BACKUP_LOCK_FILENAME = ".poetry.lock.non-editable-backup"

# gitignore/Dockerignore augmentation
IGNORE_FILE_MARKER_COMMENT = (
    "# Added by editable-python-deps to exclude cloned editable dependency repos"
)

# Dry-run logging
DRY_RUN_RUN_PREFIX = "[dry-run] Would run: "
DRY_RUN_ACT_PREFIX = "[dry-run] Would: "

# Subprocess names
GIT_BIN = "git"
POETRY_BIN = "poetry"

# Logging constants
#
# Good for CLI logs
# Messages like: "2024-06-01 12:00:00 INFO     This is a log message"
LOG_MSG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
#
# Good for CLIs or scripts where knowing the module is important, especially when working with multiple packages.
# Messages like: "2024-06-01 12:00:00 INFO     [editable_python_deps.main] This is a log message"
# LOG_MSG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
#
# Good for debugging, as it includes the module, function name and line number.
# Messages like: "2026-03-24 09:41:12,341 WARNING  [myapp.db] queries:fetch_user:87 | Slow query detected"
DEBUG_LOG_MSG_FORMAT = (
    "%(asctime)s %(levelname)-8s [%(name)s] "
    "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
)

# ISO 8601 format without timezone
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
