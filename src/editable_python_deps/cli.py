import logging
import sys
import typing as t
from pathlib import Path

import click

import editable_python_deps
from editable_python_deps import constants as CONST


@click.command(
    name=CONST.PROGRAM_NAME,
    help=CONST.PROGRAM_DESCRIPTION,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("arg", type=str, metavar="ARG")
@click.option(
    "-c",
    "--config",
    "config",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Path to a config file.",
)
@click.option(
    "-s",
    "--setup",
    "setup",
    is_flag=True,
    default=False,
    help="Run in setup mode.",
)
@click.option(
    "--log-level",
    "log_level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default=CONST.DEFAULT_LOG_LEVEL,
    show_default=True,
    help="Set the logging level.",
)
@click.option(
    "--traceback",
    "show_traceback",
    is_flag=True,
    default=False,
    help="Show full traceback on errors.",
)
@click.version_option(
    version=editable_python_deps.__version__,
    prog_name=CONST.PROGRAM_NAME,
)
def cli(
    arg: str,
    config: t.Optional[Path],
    setup: bool,
    log_level: str,
    show_traceback: bool,
) -> None:
    # Why import inside the function?
    # The main function may have an import loading penalty, so we delay it
    # until we know we need it (i.e. after click has parsed args and not
    # exited early via --help or --version).
    from editable_python_deps.main import main
    from editable_python_deps.utils.logging_utils import setup_logging

    # Logging setup
    #
    # NB: Following python.org best practices, the package logger is 'silent' by
    # default - setup_logging will remove the NullHandler and add a
    # StreamHandler to the top-level package logger. Subloggers will inherit
    # handlers and level from the package logger.
    setup_logging(level=log_level.upper())
    logging.getLogger(__name__)

    # With entrypoint functions it best to use keyword arguments, so that when
    # you change the click options the function signature change is caught
    # explicitly here (or you can better catch a regression).
    _cli_wrapper(
        main,
        show_traceback=show_traceback,
        arg=arg,
        config=config,
        setup=setup,
    )


def run_cli() -> None:
    """
    Run the CLI. This function is typically called from the command line via
    the ``editable-python-deps`` script entrypoint.
    """
    cli()


def _cli_wrapper(  # noqa: C901
    func: t.Callable[..., bool],
    show_traceback: bool = False,
    **kwargs: t.Any,
) -> None:
    """Wrap API function calls with exception handling and sys.exit."""
    from editable_python_deps.exceptions import EditablePythonDepsError

    err_msg_traceback_help = "Run with --traceback for full error details."
    try:
        exit_success_bool = func(**kwargs)
        sys.exit(0 if exit_success_bool else 1)
    except KeyboardInterrupt:
        click.echo("Operation cancelled by user. Exiting.", err=True)
        sys.exit(2)
    except EditablePythonDepsError as e:
        # Expected, in-package error: give the user a clean message and only
        # show the traceback if they explicitly asked for it. We deliberately
        # do NOT nudge them toward --traceback here, since the error was
        # anticipated and the message above should be self-explanatory.
        errmsgs = [f"Error: {e}"]
        if show_traceback:
            import traceback

            errmsgs.append(traceback.format_exc())
        click.echo("\n".join(errmsgs), err=True)
        sys.exit(1)
    except Exception as e:
        import traceback

        errmsgs = []
        err_msg_head = (
            f"Unexpected error occurred of type {type(e).__name__} " f"with reason: {e}"
        )
        errmsgs.append(err_msg_head)
        errmsgs.append(
            traceback.format_exc() if show_traceback else err_msg_traceback_help
        )
        click.echo("\n".join(errmsgs), err=True)
        sys.exit(1)
