import typing as t
import logging
import sys

from editable_python_deps import constants


def get_package_logger() -> logging.Logger:
    """
    Get the package logger object.
    """
    import editable_python_deps

    return editable_python_deps.LOGGER


def setup_logging(level: str = "INFO", name: t.Optional[str] = None) -> logging.Logger:
    """
    Configures and sets up a logger with a specified logging level and optional name.

    This function ensures that logs are output to `stderr` with a specific format
    (`"%(asctime)s - %(levelname)s - %(message)s"`) and prevents duplicate handlers
    from being added to the logger. If a logger with the same name is passed multiple
    times, it avoids adding redundant handlers. Additionally, it removes any
    `NullHandler` present in the logger.

    Args:
        level (str): The logging level as a string (e.g., "INFO", "DEBUG", "ERROR").
                     Defaults to "INFO".
        name (Optional[str]): The name of the logger. If not provided, the package
                              logger is used.

    Returns:
        logging.Logger: The configured logger instance.
    """
    level = level.strip().upper()
    is_debug = level == "DEBUG"
    msg_fmt = constants.DEBUG_LOG_MSG_FORMAT if is_debug else constants.LOG_MSG_FORMAT
    date_fmt = constants.LOG_TIME_FORMAT

    # 1) Determine the logging level enum from the helper
    logging_level = _get_logging_level_enum(level)

    # 2) Pick the logger: either the named one, or the package logger
    logger = logging.getLogger(name) if name else get_package_logger()

    # 3) Remove the NullHandler if present (only once)
    for handler in list(logger.handlers):
        if isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)

    # 4) Prepare the new StreamHandler + formatter
    new_handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(msg_fmt, datefmt=date_fmt)
    new_handler.setFormatter(formatter)

    # 5) Check for an "identical" handler already in place
    for h in logger.handlers:
        if (
            isinstance(h, logging.StreamHandler)
            and isinstance(h.formatter, logging.Formatter)
            and h.formatter._fmt == msg_fmt
        ):
            # found a matching handler, so skip adding
            break
    else:
        # no existing matching handler, so safe to add
        logger.addHandler(new_handler)

    # 6) Set the logger level
    logger.setLevel(logging_level)

    return logger


def update_logger_level(logger: logging.Logger, level: str) -> None:
    """
    Update the logger level.
    """
    logging_level = _get_logging_level_enum(level)

    logger.setLevel(logging_level)
    return None


def _get_logging_level_enum(level: str) -> int:
    """
    Get the logging level enum from the logging module.
    """
    logging_level = getattr(logging, level.strip().upper())
    if not isinstance(logging_level, int):
        raise ValueError(f"Invalid log level: {level}")
    return logging_level
