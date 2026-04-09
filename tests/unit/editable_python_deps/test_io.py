"""Unit tests for editable_python_deps.io."""

from __future__ import annotations

from editable_python_deps.io import (
    default_printer,
    style_info,
    style_muted,
    style_success,
    style_warning,
)


# --- default_printer --------------------------------------------------------


def test_default_printer__writes_to_stderr(capsys):
    # Given a message and the default printer
    message = "hello stderr"

    # When the printer is called
    default_printer(message)

    # Then the message lands on stderr (not stdout)
    captured = capsys.readouterr()
    assert message in captured.err
    assert captured.out == ""


# --- style helpers ----------------------------------------------------------

ESC = "\x1b["


def test_style_success__contains_ansi():
    # Given a string passed through style_success
    styled = style_success("ok")

    # Then the result contains an ANSI escape and the original text
    assert ESC in styled
    assert "ok" in styled


def test_style_info__contains_ansi():
    # Given a string passed through style_info
    styled = style_info("info")

    # Then the result contains an ANSI escape and the original text
    assert ESC in styled
    assert "info" in styled


def test_style_muted__contains_ansi():
    # Given a string passed through style_muted
    styled = style_muted("muted")

    # Then the result contains an ANSI escape and the original text
    assert ESC in styled
    assert "muted" in styled


def test_style_warning__contains_ansi():
    # Given a string passed through style_warning
    styled = style_warning("(new)")

    # Then the result contains an ANSI escape and the original text
    assert ESC in styled
    assert "(new)" in styled


def test_default_printer__strips_ansi_when_not_a_tty(capsys):
    # Given a styled message (capsys redirects stderr to a non-TTY pipe)
    styled = style_success("ok")

    # When the printer is called
    default_printer(styled)

    # Then the captured stderr contains the raw text but no ANSI escapes
    captured = capsys.readouterr()
    assert "ok" in captured.err
    assert ESC not in captured.err
