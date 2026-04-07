# You can single-source your package version setting the package version only in
# the project data in `pyproject.toml` or `setup.py`, using `importlib.metadata`.
#
# If your package requires Python 3.8 or above, you can use the standard library
# package `importlib.metadata` and not add a dependency.
#
# If you're supporting versions below 3.8, you need to add a dependency for the
# shim package `importlib-metadata` and import it if `importlib.metadata`
# is not present.
#
# You use the `version()` function to retrieve the version string for a package.
# The value of `__name__` normally provides the package name, but if you're
# running the package as a script (either `python -m my_package` or through
# a script installed with the package), `__name__` will be `"__main__"`,
# in which case you need to use `__package__` to get the package name.
# As far as I can tell there isn't a variable that covers both situations.
#
# Set the package version in your pyproject.toml or setup.py. If you're
# supporting Python versions before 3.8, add a conditional dependency for
# importlib-metadata (examples below).
#
# Choose one of the following code snippets, depending on what Python versions
# your package supports.
# Put the snippet in the __init__.py of your top-level package

###### supporting Python versions below 3.8 ######
import typing as t

if t.TYPE_CHECKING:
    from logging import Logger


def _set_version() -> str:  # noqa: C901
    """Set the package version from the project metadata in pyproject.toml."""
    from warnings import warn
    import importlib.metadata as importlib_metadata

    fallback_version = "0.0.0"

    try:
        # __package__ allows for the case where __name__ is "__main__"
        version = importlib_metadata.version(__package__ or __name__)
    except importlib_metadata.PackageNotFoundError:
        version = fallback_version

    if version == fallback_version:
        msg = (
            f"Package version will be {fallback_version} because Python could not find "
            f"package {__package__ or __name__} in project metadata. Either the "
            "version was not set in pyproject.toml or the package was not installed. "
            "If developing code, please install the package in editable "
            "mode with `poetry install` or `pip install -e .`"
        )
        warn(msg)
    return version


__version__ = _set_version()


def _get_logger() -> "Logger":
    """
    Get a logger object with the given name, by default the name of this package.
    """
    import logging

    logger = logging.getLogger(__name__)
    # Suppress logging of this package by default
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.WARNING)
    return logger


__version__ = _set_version()
LOGGER = _get_logger()
