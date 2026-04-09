"""Shared pytest fixtures.

The fixtures here are deliberately compositional: ``fake_project_with_backup``
extends ``fake_project_with_config`` extends ``fake_project_dir``, so most
tests can ask for the highest-level fixture they need and get a fully-formed
fake project for free.

See https://docs.pytest.org/en/8.2.x/how-to/fixtures.html for fixture docs.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


# --- text fixtures ----------------------------------------------------------


@pytest.fixture
def fake_pyproject_text() -> str:
    """Minimal pyproject.toml a Poetry project would have."""
    return textwrap.dedent(
        """\
        [project]
        name = "fake-project"
        version = "0.0.1"
        requires-python = ">=3.10"
        dependencies = []

        [build-system]
        requires = ["poetry-core>=2.0.0"]
        build-backend = "poetry.core.masonry.api"
        """
    )


@pytest.fixture
def fake_poetry_lock_text() -> str:
    """A placeholder lock file (content does not matter for our tests)."""
    return "# This is a fake poetry.lock for tests.\n"


@pytest.fixture
def fake_editable_deps_toml_text() -> str:
    """A 2-source .editable-deps.toml that round-trips through tomlkit."""
    return textwrap.dedent(
        """\
        version = "1"
        local_cloning_directory = ".editable-deps/"
        default_branch = "develop"

        [[sources]]
        name = "alpha"
        url = "git@example.com:org/alpha.git"

        [[sources]]
        name = "beta"
        url = "git@example.com:org/beta.git"
        """
    )


# --- directory fixtures ------------------------------------------------------


@pytest.fixture
def fake_project_dir(
    tmp_path: Path,
    fake_pyproject_text: str,
    fake_poetry_lock_text: str,
) -> Path:
    """A tmp dir with pyproject.toml + poetry.lock — the bare minimum project."""
    (tmp_path / "pyproject.toml").write_text(fake_pyproject_text)
    (tmp_path / "poetry.lock").write_text(fake_poetry_lock_text)
    return tmp_path


@pytest.fixture
def fake_project_with_config(
    fake_project_dir: Path,
    fake_editable_deps_toml_text: str,
) -> Path:
    """fake_project_dir + a valid .editable-deps.toml."""
    (fake_project_dir / ".editable-deps.toml").write_text(fake_editable_deps_toml_text)
    return fake_project_dir


@pytest.fixture
def fake_project_with_backup(fake_project_with_config: Path) -> Path:
    """fake_project_with_config + the two backup sentinel files (editable state)."""
    p = fake_project_with_config
    (p / ".pyproject.toml.non-editable-backup").write_text(
        (p / "pyproject.toml").read_text()
    )
    (p / ".poetry.lock.non-editable-backup").write_text((p / "poetry.lock").read_text())
    return p


# --- runner fixtures --------------------------------------------------------


@pytest.fixture
def runner_dry():
    from editable_python_deps.runner import SubprocessRunner

    return SubprocessRunner(dry_run=True)


@pytest.fixture
def runner_real():
    from editable_python_deps.runner import SubprocessRunner

    return SubprocessRunner(dry_run=False)
