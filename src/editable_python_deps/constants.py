# CLI constants
PROGRAM_NAME = "editable-python-deps"
PROGRAM_DESCRIPTION = "An example Python script."
DEFAULT_LOG_LEVEL = "INFO"

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
