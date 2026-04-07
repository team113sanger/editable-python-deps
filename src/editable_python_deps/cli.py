import logging
from pathlib import Path
import sys

import argparse


def cli() -> argparse.Namespace:
    # Unlike most functions, in our CLI function we import our package modules
    # within to delay the import until we know we need it.
    import editable_python_deps  # noqa: F401
    import editable_python_deps.constants as CONST  # noqa: F401

    # CLI constants
    default_log_level = CONST.DEFAULT_LOG_LEVEL
    description = CONST.PROGRAM_DESCRIPTION

    # Create the parser
    parser = argparse.ArgumentParser(
        description=description,
        prog=CONST.PROGRAM_NAME,
    )

    # Add arguments
    parser.add_argument(
        "input_file",
        type=Path,
        help="The input file to process",
        metavar="INPUT-FILE",
    )
    parser.add_argument(
        "output_file",
        type=Path,
        help="The output file to write to",
        metavar="OUTPUT-FILE",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {editable_python_deps.__version__}",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        default=default_log_level,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=f"Set the logging level (default: {default_log_level})",
    )

    # Parse the arguments
    args = parser.parse_args()
    return args


def run_cli() -> None:
    """
    Run the CLI. This function is typically called from the command line.
    """
    args = cli()
    # NB: Early exit if --version or --help were provided, so we skip unnecessary
    # imports and setup.

    # Why import outside of the function?
    # Typically if --version or --help are not provided we want to run the main
    # function. This may have an import loading penalty, and so we delay it
    # until we know we need it.
    from editable_python_deps.main import main  # noqa: F401
    from editable_python_deps.utils.logging_utils import setup_logging

    # Logging setup
    #
    # NB: Following python.org best practices, the package logger is 'silent' by
    # default - setup_logging will remove the NullHandler and add a
    # StreamHandler to the top-level package logger. Subloggers will inherit
    # handlers and level from the package logger.
    #
    # We want to use the sublogger for this module, so we get it by name after setup.
    setup_logging(level=args.log_level)
    logger = logging.getLogger(__name__)

    # With entrypoint functions it best to use keyword arguments, so that when
    # you change the namespace returned by the cli you don't have to change the
    # function signature (or you can better catch a regression)
    outcome = main(input_file=args.input_file, output_file=args.output_file)

    # If the main function returns a boolean and hasn't raised an
    # exception, we can use that to set the exit code
    # 0 = success (True)
    # 1 = failure (False)
    exit_code = 0 if outcome else 1
    if exit_code == 1:
        logger.error("Done. Exiting unsuccessfully.")
    else:
        logger.debug("Done. Exiting successfully.")
    sys.exit(exit_code)

    return  # Return will never be reached, but is here for clarity
