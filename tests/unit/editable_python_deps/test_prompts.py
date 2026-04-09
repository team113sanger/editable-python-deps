"""Light unit tests for editable_python_deps.prompts.

The actual prompt_toolkit dialog event loops are exercised manually via the
``editable-python-deps setup`` smoke test. These tests cover validators,
``_default``, ``_try_load``, and the :func:`run_setup_wizard` happy paths
with the dialog wrappers patched out.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from prompt_toolkit.document import Document
from prompt_toolkit.validation import ValidationError

from editable_python_deps import prompts
from editable_python_deps.config import Config, Source
from editable_python_deps.prompts import (
    _GitUrlValidator,
    _NonEmptyValidator,
    _RelativePathValidator,
    _default,
    _try_load,
)


# --- validators -------------------------------------------------------------


def test_NonEmptyValidator__rejects_empty_input():
    # Given an empty document
    doc = Document(text="")

    # When the validator is invoked
    # Then ValidationError is raised
    with pytest.raises(ValidationError):
        _NonEmptyValidator().validate(doc)


def test_NonEmptyValidator__accepts_non_empty_input():
    # Given a document with content
    doc = Document(text="hello")

    # When the validator is invoked
    # Then no exception is raised
    _NonEmptyValidator().validate(doc)


def test_RelativePathValidator__rejects_absolute_path():
    # Given a document containing an absolute path
    doc = Document(text="/abs/path")

    # When the validator is invoked
    # Then ValidationError is raised
    with pytest.raises(ValidationError):
        _RelativePathValidator().validate(doc)


def test_RelativePathValidator__accepts_relative_path():
    # Given a document containing a relative path
    doc = Document(text=".editable-deps/")

    # When the validator is invoked
    # Then no exception is raised
    _RelativePathValidator().validate(doc)


# --- _GitUrlValidator -------------------------------------------------------


def test__GitUrlValidator__accepts_ssh_form():
    # Given a scp-style SSH URL
    doc = Document(text="git@gitlab.example.com:org/repo.git")

    # When the validator runs
    # Then no exception is raised
    _GitUrlValidator().validate(doc)


def test__GitUrlValidator__accepts_https_form():
    # Given an HTTPS URL
    doc = Document(text="https://gitlab.example.com/org/repo.git")

    # When the validator runs
    # Then no exception is raised
    _GitUrlValidator().validate(doc)


def test__GitUrlValidator__accepts_http_form():
    # Given an HTTP URL
    doc = Document(text="http://localhost/repo.git")

    # When the validator runs
    # Then no exception is raised
    _GitUrlValidator().validate(doc)


def test__GitUrlValidator__rejects_bare_word():
    # Given a bare package name (the typo we want to catch)
    doc = Document(text="dermatlas-web-client")

    # When the validator runs
    # Then ValidationError is raised
    with pytest.raises(ValidationError):
        _GitUrlValidator().validate(doc)


def test__GitUrlValidator__rejects_path_only():
    # Given a path that is neither SSH nor HTTPS
    doc = Document(text="/home/me/repo")

    # When the validator runs
    # Then ValidationError is raised
    with pytest.raises(ValidationError):
        _GitUrlValidator().validate(doc)


def test__GitUrlValidator__rejects_empty():
    # Given an empty input
    doc = Document(text="")

    # When the validator runs
    # Then ValidationError is raised
    with pytest.raises(ValidationError):
        _GitUrlValidator().validate(doc)


# --- _default ---------------------------------------------------------------


def test__default__falls_back_to_constants_when_no_existing():
    # Given no existing config
    # When _default looks up local_cloning_directory
    actual = _default(None, "local_cloning_directory")

    # Then it returns the constant default
    assert actual == ".editable-deps/"


def test__default__uses_existing_value_when_present():
    # Given an existing config
    existing = Config(
        version="1",
        local_cloning_directory=Path("./custom-deps/"),
        default_branch="main",
        sources=(Source(name="a", url="u"),),
    )

    # When _default looks up local_cloning_directory
    actual = _default(existing, "local_cloning_directory")

    # Then it stringifies the existing value
    assert "custom-deps" in actual


# --- _try_load --------------------------------------------------------------


def test__try_load__returns_none_when_file_missing(tmp_path):
    # Given a path that does not exist
    missing = tmp_path / "no.toml"

    # When _try_load is called
    actual = _try_load(missing)

    # Then it returns None instead of raising
    assert actual is None


def test__try_load__returns_config_when_file_present(fake_project_with_config):
    # Given a project with a valid config file
    path = fake_project_with_config / ".editable-deps.toml"

    # When _try_load is called
    actual = _try_load(path)

    # Then it returns a Config
    assert actual is not None
    assert actual.version == "1"


# --- _collect_sources_via_review_loop --------------------------------------


def _stub_review(monkeypatch, choices):
    """Make _review_dialog return successive items from `choices`."""
    iterator = iter(choices)
    monkeypatch.setattr(prompts, "_review_dialog", lambda sources: next(iterator))


def test_collect_sources_via_review_loop__add_then_finish(monkeypatch):
    # Given a single Add followed by Finish
    captured = Source(name="alpha", url="git@example.com:org/alpha.git")
    _stub_review(monkeypatch, ["add", "finish"])
    monkeypatch.setattr(prompts, "_capture_source_dialog", lambda *, prefill: captured)

    # When the loop runs from an empty list
    result = prompts._collect_sources_via_review_loop(existing=())

    # Then the result has exactly one source
    assert result == [captured]


def test_collect_sources_via_review_loop__cancel_during_add_keeps_prior_sources(
    monkeypatch,
):
    # Given Add (returns valid), Add (Cancel = None), Finish
    alpha = Source(name="alpha", url="git@example.com:org/alpha.git")
    capture_results = iter([alpha, None])
    _stub_review(monkeypatch, ["add", "add", "finish"])
    monkeypatch.setattr(
        prompts,
        "_capture_source_dialog",
        lambda *, prefill: next(capture_results),
    )

    # When the loop runs
    result = prompts._collect_sources_via_review_loop(existing=())

    # Then only the first (valid) source survives
    assert result == [alpha]


def test_collect_sources_via_review_loop__edit_replaces_existing(monkeypatch):
    # Given one existing source plus Edit then Finish
    original = Source(name="alpha", url="git@example.com:org/alpha.git")
    edited = Source(name="alpha", url="git@example.com:org/alpha-v2.git")
    _stub_review(monkeypatch, ["edit", "finish"])
    monkeypatch.setattr(prompts, "_pick_source_dialog", lambda sources, *, action: 0)
    monkeypatch.setattr(prompts, "_capture_source_dialog", lambda *, prefill: edited)

    # When the loop runs starting with the original
    result = prompts._collect_sources_via_review_loop(existing=(original,))

    # Then the original was replaced by the edited source
    assert result == [edited]


def test_collect_sources_via_review_loop__remove_drops_entry(monkeypatch):
    # Given two existing sources plus Remove then Finish
    alpha = Source(name="alpha", url="git@example.com:org/alpha.git")
    beta = Source(name="beta", url="git@example.com:org/beta.git")
    _stub_review(monkeypatch, ["remove", "finish"])
    monkeypatch.setattr(prompts, "_pick_source_dialog", lambda sources, *, action: 0)

    # When the loop runs
    result = prompts._collect_sources_via_review_loop(existing=(alpha, beta))

    # Then alpha was removed and beta remains
    assert result == [beta]


def test_collect_sources_via_review_loop__cancel_returns_empty(monkeypatch):
    # Given the user immediately cancels the review menu
    _stub_review(monkeypatch, ["cancel"])

    # When the loop runs
    result = prompts._collect_sources_via_review_loop(existing=())

    # Then the result is an empty list
    assert result == []


# --- run_setup_wizard happy path (all dialogs monkeypatched) ----------------


def test_run_setup_wizard__happy_path(monkeypatch, tmp_path):
    # Given a target path with no existing config and a stubbed dialog flow
    target = tmp_path / ".editable-deps.toml"
    captured = Source(name="alpha", url="git@example.com:org/alpha.git")

    monkeypatch.setattr(
        prompts,
        "_confirm_intro_dialog",
        lambda project_dir, target, existing: True,
    )
    monkeypatch.setattr(
        prompts,
        "_input_with_validator",
        lambda *, text, default, validator: default,
    )
    monkeypatch.setattr(
        prompts,
        "_collect_sources_via_review_loop",
        lambda *, existing: [captured],
    )
    monkeypatch.setattr(
        prompts,
        "_confirm_summary_dialog",
        lambda config, *, target: True,
    )

    # When the wizard runs
    config = prompts.run_setup_wizard(project_dir=tmp_path, existing_path=target)

    # Then a populated Config is returned
    assert config.version == "1"
    assert config.local_cloning_directory == Path(".editable-deps/")
    assert config.default_branch == "develop"
    assert config.sources == (captured,)


def test_run_setup_wizard__user_declines_intro(monkeypatch, tmp_path):
    # Given the user clicks No on the intro dialog
    target = tmp_path / ".editable-deps.toml"
    monkeypatch.setattr(
        prompts,
        "_confirm_intro_dialog",
        lambda project_dir, target, existing: False,
    )

    # When the wizard runs
    # Then KeyboardInterrupt propagates so _cli_wrapper renders "cancelled"
    with pytest.raises(KeyboardInterrupt):
        prompts.run_setup_wizard(project_dir=tmp_path, existing_path=target)


def test_run_setup_wizard__zero_sources_raises_keyboard_interrupt(
    monkeypatch, tmp_path
):
    # Given the source review loop returns no sources
    target = tmp_path / ".editable-deps.toml"
    monkeypatch.setattr(
        prompts,
        "_confirm_intro_dialog",
        lambda project_dir, target, existing: True,
    )
    monkeypatch.setattr(
        prompts,
        "_input_with_validator",
        lambda *, text, default, validator: default,
    )
    monkeypatch.setattr(
        prompts,
        "_collect_sources_via_review_loop",
        lambda *, existing: [],
    )

    # When the wizard runs
    # Then it refuses to write a zero-source config
    with pytest.raises(KeyboardInterrupt):
        prompts.run_setup_wizard(project_dir=tmp_path, existing_path=target)


def test_run_setup_wizard__user_declines_summary(monkeypatch, tmp_path):
    # Given the user clicks No on the final summary dialog
    target = tmp_path / ".editable-deps.toml"
    captured = Source(name="alpha", url="git@example.com:org/alpha.git")

    monkeypatch.setattr(
        prompts,
        "_confirm_intro_dialog",
        lambda project_dir, target, existing: True,
    )
    monkeypatch.setattr(
        prompts,
        "_input_with_validator",
        lambda *, text, default, validator: default,
    )
    monkeypatch.setattr(
        prompts,
        "_collect_sources_via_review_loop",
        lambda *, existing: [captured],
    )
    monkeypatch.setattr(
        prompts,
        "_confirm_summary_dialog",
        lambda config, *, target: False,
    )

    # When the wizard runs
    # Then KeyboardInterrupt propagates
    with pytest.raises(KeyboardInterrupt):
        prompts.run_setup_wizard(project_dir=tmp_path, existing_path=target)
