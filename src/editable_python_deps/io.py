"""User-facing output helpers.

All non-logging output (wizard prompts, diff previews, status banners) goes
through a single :data:`Printer` callable so callers can be redirected in
tests and so output is colourised consistently.

The default printer is :func:`click.echo` writing to stderr, which is
terminal-aware (it strips ANSI when piped) and matches click's other output
paths.
"""

from __future__ import annotations

import typing as t

import click

# A Printer is any callable that takes a single pre-formatted string.
# Colours are baked in by the caller via click.style before the string ever
# reaches the printer.
Printer = t.Callable[[str], None]


def default_printer(message: str) -> None:
    """Default printer: :func:`click.echo` to stderr.

    Using :func:`click.echo` (not :func:`print`) means ANSI escapes from
    :func:`click.style` are auto-stripped when stderr is not a TTY.
    """
    click.echo(message, err=True)


# --- colour palette ---------------------------------------------------------
# Restricted, intentional. Green = success/affirmation, blue = informational
# headers/labels, grey ("bright_black") = secondary detail. No backgrounds,
# no bold/italic.


def style_success(text: str) -> str:
    return click.style(text, fg="green")


def style_info(text: str) -> str:
    return click.style(text, fg="blue")


def style_muted(text: str) -> str:
    return click.style(text, fg="bright_black")


def style_warning(text: str) -> str:
    """Yellow — used sparingly to draw attention to small inline tokens."""
    return click.style(text, fg="yellow")
