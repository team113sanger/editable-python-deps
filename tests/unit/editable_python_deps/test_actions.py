"""Unit tests for editable_python_deps.actions.

These tests use the compositional ``fake_project_*`` fixtures plus
``pytest-subprocess`` to fake every git/poetry call. monkeypatch is used to
redirect ``find_project_dir`` so the tests are isolated from the actual CWD.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from editable_python_deps import actions, project
from editable_python_deps.exceptions import (
    BackupStateError,
    PoetryNotFoundError,
)


# --- shared fixtures --------------------------------------------------------


@pytest.fixture
def patch_find_project_dir(monkeypatch):
    """Return a function that patches find_project_dir to return a fixed path."""

    def _patch(target_dir: Path) -> None:
        monkeypatch.setattr(
            "editable_python_deps.actions.find_project_dir",
            lambda *a, **kw: target_dir,
        )

    return _patch


@pytest.fixture
def patch_cwd_to_project(monkeypatch, fake_project_with_config):
    """chdir into the fake project so find_project_dir picks it up naturally."""
    monkeypatch.chdir(fake_project_with_config)
    return fake_project_with_config


def _register_poetry_available(fp):
    fp.register(
        ["poetry", "--version"], stdout="Poetry (version 2.3.2)\n", occurrences=10
    )


def _register_poetry_sync(fp):
    fp.register(["poetry", "help", "sync"], returncode=0, occurrences=10)
    fp.register(["poetry", "sync"], returncode=0, occurrences=10)


# --- editable_dependencies --------------------------------------------------


def test_editable_dependencies__creates_backups_and_runs_poetry_add(
    fp, patch_find_project_dir, fake_project_with_config
):
    # Given a fake project with config and the editable clones already present
    project_dir = fake_project_with_config
    base_dir = project_dir / ".editable-deps"
    base_dir.mkdir()
    for name in ("alpha", "beta"):
        (base_dir / name).mkdir()  # pretend the clone exists
    patch_find_project_dir(project_dir)

    _register_poetry_available(fp)
    fp.register(
        ["poetry", "add", "--editable", str(base_dir / "alpha")],
        occurrences=1,
    )
    fp.register(
        ["poetry", "add", "--editable", str(base_dir / "beta")],
        occurrences=1,
    )
    # Existing clones with clean working trees:
    fp.register(
        ["git", "-C", str(base_dir / "alpha"), "status", "--porcelain"],
        stdout="",
        occurrences=10,
    )
    fp.register(
        ["git", "-C", str(base_dir / "beta"), "status", "--porcelain"],
        stdout="",
        occurrences=10,
    )
    fp.register(
        ["git", "-C", str(base_dir / "alpha"), "fetch", "origin", "develop", "--quiet"],
        occurrences=10,
    )
    fp.register(
        ["git", "-C", str(base_dir / "beta"), "fetch", "origin", "develop", "--quiet"],
        occurrences=10,
    )
    sha = "a" * 40
    for name in ("alpha", "beta"):
        fp.register(
            ["git", "-C", str(base_dir / name), "rev-parse", "HEAD"],
            stdout=f"{sha}\n",
            occurrences=10,
        )
        fp.register(
            ["git", "-C", str(base_dir / name), "rev-parse", "FETCH_HEAD"],
            stdout=f"{sha}\n",
            occurrences=10,
        )

    # When editable_dependencies runs
    actions.editable_dependencies(config_path=None, dry_run=False)

    # Then backups exist on disk and poetry add was called for each source
    assert (project_dir / ".pyproject.toml.non-editable-backup").is_file()
    assert (project_dir / ".poetry.lock.non-editable-backup").is_file()
    assert fp.call_count(["poetry", "add", "--editable", str(base_dir / "alpha")]) == 1
    assert fp.call_count(["poetry", "add", "--editable", str(base_dir / "beta")]) == 1


def test_editable_dependencies__idempotent_when_backups_already_exist(
    fp, patch_find_project_dir, fake_project_with_backup, caplog
):
    # Given a fake project ALREADY in editable state (backups present)
    project_dir = fake_project_with_backup
    base_dir = project_dir / ".editable-deps"
    base_dir.mkdir()
    for name in ("alpha", "beta"):
        (base_dir / name).mkdir()
    patch_find_project_dir(project_dir)

    _register_poetry_available(fp)
    for name in ("alpha", "beta"):
        fp.register(
            ["git", "-C", str(base_dir / name), "status", "--porcelain"],
            stdout="",
            occurrences=10,
        )
        fp.register(
            [
                "git",
                "-C",
                str(base_dir / name),
                "fetch",
                "origin",
                "develop",
                "--quiet",
            ],
            occurrences=10,
        )
        fp.register(
            ["git", "-C", str(base_dir / name), "rev-parse", "HEAD"],
            stdout="a" * 40 + "\n",
            occurrences=10,
        )
        fp.register(
            ["git", "-C", str(base_dir / name), "rev-parse", "FETCH_HEAD"],
            stdout="a" * 40 + "\n",
            occurrences=10,
        )
        fp.register(
            ["poetry", "add", "--editable", str(base_dir / name)],
            occurrences=1,
        )

    # Snapshot original backup contents
    backup_pyproject_before = (
        project_dir / ".pyproject.toml.non-editable-backup"
    ).read_text()

    # When editable_dependencies runs
    with caplog.at_level(logging.INFO, logger="editable_python_deps.actions"):
        actions.editable_dependencies(config_path=None, dry_run=False)

    # Then a "not overwriting" log line was emitted and backups are unchanged
    assert any("Backup files already exist" in r.message for r in caplog.records)
    backup_pyproject_after = (
        project_dir / ".pyproject.toml.non-editable-backup"
    ).read_text()
    assert backup_pyproject_after == backup_pyproject_before


def test_editable_dependencies__skips_ff_when_local_ahead(
    fp, patch_find_project_dir, fake_project_with_backup, caplog
):
    # Given a project in editable state where local HEAD is *ahead* of
    # origin (HEAD != FETCH_HEAD AND merge-base --is-ancestor returns 1).
    project_dir = fake_project_with_backup
    base_dir = project_dir / ".editable-deps"
    base_dir.mkdir()
    for name in ("alpha", "beta"):
        (base_dir / name).mkdir()
    patch_find_project_dir(project_dir)

    _register_poetry_available(fp)
    for name in ("alpha", "beta"):
        fp.register(
            ["git", "-C", str(base_dir / name), "status", "--porcelain"],
            stdout="",
            occurrences=10,
        )
        fp.register(
            [
                "git",
                "-C",
                str(base_dir / name),
                "fetch",
                "origin",
                "develop",
                "--quiet",
            ],
            occurrences=10,
        )
        fp.register(
            ["git", "-C", str(base_dir / name), "rev-parse", "HEAD"],
            stdout="a" * 40 + "\n",
            occurrences=10,
        )
        fp.register(
            ["git", "-C", str(base_dir / name), "rev-parse", "FETCH_HEAD"],
            stdout="b" * 40 + "\n",
            occurrences=10,
        )
        fp.register(
            [
                "git",
                "-C",
                str(base_dir / name),
                "merge-base",
                "--is-ancestor",
                "HEAD",
                "FETCH_HEAD",
            ],
            returncode=1,  # HEAD is NOT an ancestor → local is ahead/diverged
            occurrences=10,
        )
        fp.register(
            ["poetry", "add", "--editable", str(base_dir / name)],
            occurrences=1,
        )

    # When editable_dependencies runs
    with caplog.at_level(logging.WARNING, logger="editable_python_deps.actions"):
        actions.editable_dependencies(config_path=None, dry_run=False)

    # Then the warning fired and `git merge --ff-only` was NOT called
    assert any("unpushed local commits" in r.message for r in caplog.records)
    for name in ("alpha", "beta"):
        assert (
            fp.call_count(
                ["git", "-C", str(base_dir / name), "merge", "--ff-only", "FETCH_HEAD"]
            )
            == 0
        )


def test_editable_dependencies__performs_ff_when_remote_ahead(
    fp, patch_find_project_dir, fake_project_with_backup
):
    # Given a project in editable state where the remote is ahead
    # (HEAD != FETCH_HEAD AND merge-base --is-ancestor returns 0).
    project_dir = fake_project_with_backup
    base_dir = project_dir / ".editable-deps"
    base_dir.mkdir()
    for name in ("alpha", "beta"):
        (base_dir / name).mkdir()
    patch_find_project_dir(project_dir)

    _register_poetry_available(fp)
    for name in ("alpha", "beta"):
        fp.register(
            ["git", "-C", str(base_dir / name), "status", "--porcelain"],
            stdout="",
            occurrences=10,
        )
        fp.register(
            [
                "git",
                "-C",
                str(base_dir / name),
                "fetch",
                "origin",
                "develop",
                "--quiet",
            ],
            occurrences=10,
        )
        fp.register(
            ["git", "-C", str(base_dir / name), "rev-parse", "HEAD"],
            stdout="a" * 40 + "\n",
            occurrences=10,
        )
        fp.register(
            ["git", "-C", str(base_dir / name), "rev-parse", "FETCH_HEAD"],
            stdout="b" * 40 + "\n",
            occurrences=10,
        )
        fp.register(
            [
                "git",
                "-C",
                str(base_dir / name),
                "merge-base",
                "--is-ancestor",
                "HEAD",
                "FETCH_HEAD",
            ],
            returncode=0,  # HEAD IS an ancestor → safe to FF
            occurrences=10,
        )
        fp.register(
            ["git", "-C", str(base_dir / name), "merge", "--ff-only", "FETCH_HEAD"],
            occurrences=1,
        )
        fp.register(
            ["poetry", "add", "--editable", str(base_dir / name)],
            occurrences=1,
        )

    # When editable_dependencies runs
    actions.editable_dependencies(config_path=None, dry_run=False)

    # Then `git merge --ff-only` was called once per source
    for name in ("alpha", "beta"):
        assert (
            fp.call_count(
                ["git", "-C", str(base_dir / name), "merge", "--ff-only", "FETCH_HEAD"]
            )
            == 1
        )


def test_editable_dependencies__raises_when_poetry_missing(
    fp, patch_find_project_dir, fake_project_with_config
):
    # Given poetry is not available
    patch_find_project_dir(fake_project_with_config)
    fp.register(["poetry", "--version"], returncode=127)

    # When editable_dependencies runs
    # Then PoetryNotFoundError is raised
    with pytest.raises(PoetryNotFoundError):
        actions.editable_dependencies(config_path=None, dry_run=False)


def test_editable_dependencies__dry_run_does_not_mutate_disk(
    fp, patch_find_project_dir, fake_project_with_config
):
    # Given a dry-run invocation against a non-editable project
    project_dir = fake_project_with_config
    patch_find_project_dir(project_dir)
    _register_poetry_available(fp)

    # When editable_dependencies is called in dry-run
    actions.editable_dependencies(config_path=None, dry_run=True)

    # Then no backup files were created and no .editable-deps/ dir exists
    assert not (project_dir / ".pyproject.toml.non-editable-backup").exists()
    assert not (project_dir / ".poetry.lock.non-editable-backup").exists()
    assert not (project_dir / ".editable-deps").exists()


# --- no_editable_dependencies -----------------------------------------------


def test_no_editable_dependencies__raises_when_backups_missing(
    fp, patch_find_project_dir, fake_project_with_config
):
    # Given a project with config but no backup files
    patch_find_project_dir(fake_project_with_config)
    _register_poetry_available(fp)

    # When no_editable_dependencies is called
    # Then BackupStateError is raised
    with pytest.raises(BackupStateError):
        actions.no_editable_dependencies(config_path=None, dry_run=False)


def test_no_editable_dependencies__restores_and_deletes_backups(
    fp, patch_find_project_dir, fake_project_with_backup
):
    # Given a project in editable state (backups present); modify the live
    # pyproject.toml to look "post-editable" so we can prove the restore worked.
    project_dir = fake_project_with_backup
    backup_text = (project_dir / ".pyproject.toml.non-editable-backup").read_text()
    (project_dir / "pyproject.toml").write_text(
        backup_text + "\n# editable garbage to be reverted\n"
    )

    patch_find_project_dir(project_dir)
    _register_poetry_available(fp)
    _register_poetry_sync(fp)
    # Register the git diff probes used by show_diff_no_index.
    fp.register(["git", "--version"], stdout="git version 2.42.0\n", occurrences=10)
    fp.register(
        [
            "git",
            "-c",
            "core.pager=cat",
            "-c",
            "pager.diff=false",
            "diff",
            "--no-index",
            "--quiet",
            str(project_dir / ".pyproject.toml.non-editable-backup"),
            str(project_dir / "pyproject.toml"),
        ],
        returncode=1,  # files differ
        occurrences=10,
    )
    fp.register(
        [
            "git",
            "-c",
            "core.pager=cat",
            "-c",
            "pager.diff=false",
            "diff",
            "--no-index",
            "--color=always",
            str(project_dir / ".pyproject.toml.non-editable-backup"),
            str(project_dir / "pyproject.toml"),
        ],
        stdout="--- backup\n+++ current\n",
        occurrences=10,
    )

    # When no_editable_dependencies runs
    actions.no_editable_dependencies(config_path=None, dry_run=False)

    # Then pyproject.toml was restored to the backup, and backups are gone
    assert (project_dir / "pyproject.toml").read_text() == backup_text
    assert not (project_dir / ".pyproject.toml.non-editable-backup").exists()
    assert not (project_dir / ".poetry.lock.non-editable-backup").exists()
    assert fp.call_count(["poetry", "sync"]) == 1


def test_no_editable_dependencies__lenient_when_config_missing_but_backups_present(
    fp, patch_find_project_dir, fake_project_dir, caplog
):
    # Given a project with backups but NO .editable-deps.toml
    (fake_project_dir / ".pyproject.toml.non-editable-backup").write_text(
        (fake_project_dir / "pyproject.toml").read_text()
    )
    (fake_project_dir / ".poetry.lock.non-editable-backup").write_text(
        (fake_project_dir / "poetry.lock").read_text()
    )
    patch_find_project_dir(fake_project_dir)

    _register_poetry_available(fp)
    _register_poetry_sync(fp)
    fp.register(["git", "--version"], stdout="git version 2.42.0\n", occurrences=10)
    fp.register(
        [
            "git",
            "-c",
            "core.pager=cat",
            "-c",
            "pager.diff=false",
            "diff",
            "--no-index",
            "--quiet",
            str(fake_project_dir / ".pyproject.toml.non-editable-backup"),
            str(fake_project_dir / "pyproject.toml"),
        ],
        returncode=0,  # no diff
        occurrences=10,
    )

    # When no_editable_dependencies runs
    with caplog.at_level(logging.WARNING, logger="editable_python_deps.actions"):
        actions.no_editable_dependencies(config_path=None, dry_run=False)

    # Then a warning about missing config was emitted, but the restore proceeded
    assert any("Restoring from backups anyway" in r.message for r in caplog.records)
    assert not (fake_project_dir / ".pyproject.toml.non-editable-backup").exists()


# --- show_status ------------------------------------------------------------


def test_show_status__non_editable_state(
    patch_find_project_dir, fake_project_with_config, caplog
):
    # Given a project with config and no backups
    patch_find_project_dir(fake_project_with_config)

    # When show_status runs
    with caplog.at_level(logging.INFO, logger="editable_python_deps.actions"):
        actions.show_status(config_path=None, dry_run=False)

    # Then the state is reported as non-editable
    messages = " ".join(r.message for r in caplog.records)
    assert "non-editable" in messages
    assert "alpha" in messages and "beta" in messages


def test_show_status__editable_state(
    patch_find_project_dir, fake_project_with_backup, caplog
):
    # Given a project in editable state (backups present)
    patch_find_project_dir(fake_project_with_backup)

    # When show_status runs
    with caplog.at_level(logging.INFO, logger="editable_python_deps.actions"):
        actions.show_status(config_path=None, dry_run=False)

    # Then the state is reported as editable
    messages = " ".join(r.message for r in caplog.records)
    assert "editable" in messages
    # And specifically NOT "non-editable" as the state line
    state_lines = [r.message for r in caplog.records if "Dependency state" in r.message]
    assert any("editable" in m and "non-editable" not in m for m in state_lines)


def test_show_status__missing_config(patch_find_project_dir, fake_project_dir, caplog):
    # Given a project with no config file
    patch_find_project_dir(fake_project_dir)

    # When show_status runs
    with caplog.at_level(logging.INFO, logger="editable_python_deps.actions"):
        actions.show_status(config_path=None, dry_run=False)

    # Then the missing-config marker appears
    messages = " ".join(r.message for r in caplog.records)
    assert "missing" in messages.lower()
