"""Click-based command-line interface for editable-python-deps.

The shape is a ``@click.group`` with four subcommands:

* ``on``     — switch the project to editable dependency state.
* ``off``    — restore the non-editable state from backup files.
* ``status`` — print the current state and source list.
* ``setup``  — interactively create or update ``.editable-deps.toml``.

Group-level options (``-c/--config``, ``--log-level``, ``--traceback``,
``--dry-run``) propagate to subcommands via :class:`CliContext` carried on
``ctx.obj``. Each subcommand body is two lines: import the action, dispatch
through :func:`_cli_wrapper`. The wrapper provides uniform exception →
exit-code semantics for the whole package.
"""

from __future__ import annotations

import logging
import sys
import typing as t
from dataclasses import dataclass
from pathlib import Path

import click

import editable_python_deps
from editable_python_deps import constants as CONST


@dataclass
class CliContext:
    """Shared state propagated to subcommands via ``ctx.obj``."""

    config_path: t.Optional[Path]
    log_level: str
    show_traceback: bool
    dry_run: bool


@click.group(
    name=CONST.PROGRAM_NAME,
    help=CONST.PROGRAM_DESCRIPTION,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Path to .editable-deps.toml (default: alongside pyproject.toml).",
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
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    default=False,
    help="Log mutating subprocesses and filesystem operations without executing them.",
)
@click.version_option(
    version=editable_python_deps.__version__,
    prog_name=CONST.PROGRAM_NAME,
)
@click.pass_context
def cli(
    ctx: click.Context,
    config_path: t.Optional[Path],
    log_level: str,
    show_traceback: bool,
    dry_run: bool,
) -> None:
    # Late imports keep --help and --version snappy.
    from editable_python_deps.utils.logging_utils import setup_logging

    setup_logging(level=log_level.upper())
    logging.getLogger(__name__)

    ctx.obj = CliContext(
        config_path=config_path,
        log_level=log_level.upper(),
        show_traceback=show_traceback,
        dry_run=dry_run,
    )


@cli.command(name="on", help="Switch to editable dependency state.")
@click.pass_obj
def cmd_on(obj: CliContext) -> None:
    from editable_python_deps.actions import editable_dependencies

    _cli_wrapper(
        editable_dependencies,
        show_traceback=obj.show_traceback,
        config_path=obj.config_path,
        dry_run=obj.dry_run,
    )


@cli.command(name="off", help="Restore non-editable state from backup files.")
@click.pass_obj
def cmd_off(obj: CliContext) -> None:
    from editable_python_deps.actions import no_editable_dependencies

    _cli_wrapper(
        no_editable_dependencies,
        show_traceback=obj.show_traceback,
        config_path=obj.config_path,
        dry_run=obj.dry_run,
    )


@cli.command(name="status", help="Show whether dependencies are editable.")
@click.pass_obj
def cmd_status(obj: CliContext) -> None:
    from editable_python_deps.actions import show_status

    _cli_wrapper(
        show_status,
        show_traceback=obj.show_traceback,
        config_path=obj.config_path,
        dry_run=obj.dry_run,
    )


@cli.command(name="setup", help="Interactively create or update .editable-deps.toml.")
@click.pass_obj
def cmd_setup(obj: CliContext) -> None:
    from editable_python_deps.actions import run_setup

    _cli_wrapper(
        run_setup,
        show_traceback=obj.show_traceback,
        config_path=obj.config_path,
        dry_run=obj.dry_run,
    )


def run_cli() -> None:
    """Run the CLI. Invoked by the ``editable-python-deps`` script entrypoint."""
    cli()


def _cli_wrapper(  # noqa: C901
    func: t.Callable[..., bool],
    show_traceback: bool = False,
    **kwargs: t.Any,
) -> None:
    """Wrap action calls with exception handling and ``sys.exit``."""
    from editable_python_deps.exceptions import EditablePythonDepsError

    err_msg_traceback_help = "Run with --traceback for full error details."
    try:
        exit_success_bool = func(**kwargs)
        sys.exit(0 if exit_success_bool else 1)
    except KeyboardInterrupt:
        click.echo("Operation cancelled by user. Exiting.", err=True)
        sys.exit(2)
    except EditablePythonDepsError as e:
        # Expected, in-package error: clean message; traceback only on demand.
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
