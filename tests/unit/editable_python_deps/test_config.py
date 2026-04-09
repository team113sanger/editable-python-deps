"""Unit tests for editable_python_deps.config."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from editable_python_deps.config import (
    Config,
    Source,
    default_config_path,
    dumps_config,
    load_config,
    write_config,
)
from editable_python_deps.exceptions import ConfigError, ConfigNotFoundError


# --- Source / Config dataclasses --------------------------------------------


def test_Source__defaults_branch_to_none():
    # Given a Source created without a branch override
    source = Source(name="alpha", url="git@example.com:org/alpha.git")

    # When the branch attribute is read
    actual = source.branch

    # Then it is None
    assert actual is None


def test_Config__effective_branch__falls_back_to_default_when_source_branch_none():
    # Given a Config and a Source with no branch override
    config = Config(
        version="1",
        local_cloning_directory=Path(".editable-deps/"),
        default_branch="develop",
        sources=(Source(name="alpha", url="git@example.com:org/alpha.git"),),
    )

    # When effective_branch is queried
    actual = config.effective_branch(config.sources[0])

    # Then it returns the default branch
    assert actual == "develop"


def test_Config__effective_branch__uses_source_branch_when_set():
    # Given a Config and a Source with an explicit branch override
    source = Source(name="alpha", url="git@example.com:org/alpha.git", branch="main")
    config = Config(
        version="1",
        local_cloning_directory=Path(".editable-deps/"),
        default_branch="develop",
        sources=(source,),
    )

    # When effective_branch is queried
    actual = config.effective_branch(source)

    # Then it returns the source's branch override
    assert actual == "main"


def test_Config__absolute_cloning_directory__resolves_relative_to_project_dir(
    tmp_path,
):
    # Given a Config with a relative cloning directory and a project dir
    config = Config(
        version="1",
        local_cloning_directory=Path(".editable-deps/"),
        default_branch="develop",
        sources=(Source(name="a", url="u"),),
    )

    # When the absolute path is computed
    actual = config.absolute_cloning_directory(tmp_path)

    # Then it is project_dir / cloning_dir, fully resolved
    assert actual == (tmp_path / ".editable-deps").resolve()


# --- default_config_path ----------------------------------------------------


def test_default_config_path():
    # Given a project directory
    project_dir = Path("/some/project")

    # When the default config path is computed
    actual = default_config_path(project_dir)

    # Then it sits at project_dir/.editable-deps.toml
    assert actual == project_dir / ".editable-deps.toml"


# --- load_config ------------------------------------------------------------


def test_load_config__round_trip(fake_project_with_config):
    # Given a fake project with a valid .editable-deps.toml
    path = fake_project_with_config / ".editable-deps.toml"

    # When the config is loaded
    config = load_config(path)

    # Then the parsed values match the fixture
    assert config.version == "1"
    assert config.local_cloning_directory == Path(".editable-deps/")
    assert config.default_branch == "develop"
    assert len(config.sources) == 2
    assert {s.name for s in config.sources} == {"alpha", "beta"}


def test_load_config__raises_when_file_missing(tmp_path):
    # Given a path that does not exist
    missing = tmp_path / "no-such.toml"

    # When load_config is called
    # Then ConfigNotFoundError is raised
    with pytest.raises(ConfigNotFoundError):
        load_config(missing)


def test_load_config__raises_when_version_unsupported(tmp_path):
    # Given a config with an unsupported version
    path = tmp_path / ".editable-deps.toml"
    path.write_text(
        textwrap.dedent(
            """\
            version = "99"
            local_cloning_directory = ".editable-deps/"
            default_branch = "develop"
            [[sources]]
            name = "a"
            url = "git@example.com:a.git"
            """
        )
    )

    # When load_config is called
    # Then ConfigError is raised with version detail
    with pytest.raises(ConfigError) as exc_info:
        load_config(path)
    assert "unsupported version" in str(exc_info.value)


def test_load_config__raises_when_cloning_dir_is_absolute(tmp_path):
    # Given a config with an absolute cloning directory
    path = tmp_path / ".editable-deps.toml"
    path.write_text(
        textwrap.dedent(
            """\
            version = "1"
            local_cloning_directory = "/abs/path"
            default_branch = "develop"
            [[sources]]
            name = "a"
            url = "git@example.com:a.git"
            """
        )
    )

    # When load_config is called
    # Then ConfigError is raised
    with pytest.raises(ConfigError) as exc_info:
        load_config(path)
    assert "relative path" in str(exc_info.value)


def test_load_config__raises_when_sources_empty(tmp_path):
    # Given a config with an empty sources list
    path = tmp_path / ".editable-deps.toml"
    path.write_text(
        textwrap.dedent(
            """\
            version = "1"
            local_cloning_directory = ".editable-deps/"
            default_branch = "develop"
            """
        )
    )

    # When load_config is called
    # Then ConfigError is raised
    with pytest.raises(ConfigError) as exc_info:
        load_config(path)
    assert "[[sources]]" in str(exc_info.value)


def test_load_config__raises_when_source_missing_url(tmp_path):
    # Given a source missing the url field
    path = tmp_path / ".editable-deps.toml"
    path.write_text(
        textwrap.dedent(
            """\
            version = "1"
            local_cloning_directory = ".editable-deps/"
            default_branch = "develop"
            [[sources]]
            name = "a"
            """
        )
    )

    # When load_config is called
    # Then ConfigError is raised
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config__raises_when_source_names_duplicate(tmp_path):
    # Given two sources with the same name
    path = tmp_path / ".editable-deps.toml"
    path.write_text(
        textwrap.dedent(
            """\
            version = "1"
            local_cloning_directory = ".editable-deps/"
            default_branch = "develop"
            [[sources]]
            name = "a"
            url = "git@example.com:1.git"
            [[sources]]
            name = "a"
            url = "git@example.com:2.git"
            """
        )
    )

    # When load_config is called
    # Then ConfigError is raised mentioning duplicate
    with pytest.raises(ConfigError) as exc_info:
        load_config(path)
    assert "duplicate" in str(exc_info.value)


def test_load_config__per_source_branch_override(tmp_path):
    # Given a config with one source overriding the default branch
    path = tmp_path / ".editable-deps.toml"
    path.write_text(
        textwrap.dedent(
            """\
            version = "1"
            local_cloning_directory = ".editable-deps/"
            default_branch = "develop"
            [[sources]]
            name = "a"
            url = "git@example.com:a.git"
            branch = "main"
            [[sources]]
            name = "b"
            url = "git@example.com:b.git"
            """
        )
    )

    # When load_config is called
    config = load_config(path)

    # Then the override is preserved
    assert config.sources[0].branch == "main"
    assert config.sources[1].branch is None


# --- write_config / dumps_config --------------------------------------------


def test_write_config__round_trip_through_load_config(tmp_path):
    # Given an in-memory Config
    original = Config(
        version="1",
        local_cloning_directory=Path(".editable-deps/"),
        default_branch="develop",
        sources=(
            Source(name="a", url="git@example.com:a.git"),
            Source(name="b", url="git@example.com:b.git", branch="main"),
        ),
    )
    path = tmp_path / ".editable-deps.toml"

    # When the config is written and re-loaded
    write_config(path, original)
    reloaded = load_config(path)

    # Then the round-trip preserves all fields
    assert reloaded.version == original.version
    assert reloaded.local_cloning_directory == original.local_cloning_directory
    assert reloaded.default_branch == original.default_branch
    assert reloaded.sources == original.sources


def test_dumps_config__produces_valid_toml(tmp_path):
    # Given a Config
    config = Config(
        version="1",
        local_cloning_directory=Path(".editable-deps/"),
        default_branch="develop",
        sources=(Source(name="a", url="git@example.com:a.git"),),
    )

    # When dumps_config is called
    rendered = dumps_config(config)

    # Then the output contains all the expected keys
    assert 'version = "1"' in rendered
    assert "local_cloning_directory" in rendered
    assert "[[sources]]" in rendered
    assert 'name = "a"' in rendered
