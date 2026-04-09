"""Load, validate, and write ``.editable-deps.toml`` configuration files.

The config file lives next to a project's ``pyproject.toml`` (overridable via
``-c/--config <path>``) and lists the editable dependencies that
``editable-python-deps on`` should clone and add to the Poetry project.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass
from pathlib import Path

import tomlkit

from editable_python_deps import constants as CONST
from editable_python_deps.exceptions import ConfigError, ConfigNotFoundError


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    branch: t.Optional[str] = None  # None → use Config.default_branch


@dataclass(frozen=True)
class Config:
    version: str
    local_cloning_directory: Path
    default_branch: str
    sources: t.Tuple[Source, ...]

    def effective_branch(self, source: Source) -> str:
        return source.branch or self.default_branch

    def absolute_cloning_directory(self, project_dir: Path) -> Path:
        return (project_dir / self.local_cloning_directory).resolve()


# --- public load/save -------------------------------------------------------


def default_config_path(project_dir: Path) -> Path:
    """Return the conventional location of ``.editable-deps.toml``."""
    return project_dir / CONST.DEFAULT_CONFIG_FILENAME


def load_config(path: Path) -> Config:
    """Read TOML, parse and validate.

    Raises:
        ConfigNotFoundError: if ``path`` does not exist.
        ConfigError: if the file is malformed or fails validation.
    """
    if not path.is_file():
        raise ConfigNotFoundError(f"Config file not found: {path}")
    try:
        raw = tomlkit.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ConfigError(f"Could not parse {path}: {exc}") from exc
    return _config_from_raw(raw, source_path=path)


def write_config(path: Path, config: Config) -> None:
    """Serialize ``config`` to TOML and write it to ``path``."""
    path.write_text(dumps_config(config), encoding="utf-8")


def dumps_config(config: Config) -> str:
    """Render a Config to TOML text (no file I/O)."""
    return tomlkit.dumps(_config_to_doc(config))


# --- private parsing helpers ------------------------------------------------


def _config_from_raw(raw: t.Mapping[str, t.Any], *, source_path: Path) -> Config:
    version = str(raw.get("version", "")).strip()
    if version not in CONST.SUPPORTED_CONFIG_VERSIONS:
        raise ConfigError(
            f"{source_path}: unsupported version {version!r}; "
            f"supported: {sorted(CONST.SUPPORTED_CONFIG_VERSIONS)}"
        )

    raw_dir = raw.get("local_cloning_directory") or CONST.DEFAULT_LOCAL_CLONING_DIR
    cloning_dir = Path(str(raw_dir))
    if cloning_dir.is_absolute():
        raise ConfigError(
            f"{source_path}: local_cloning_directory must be a relative path; "
            f"got {cloning_dir}"
        )

    default_branch = str(raw.get("default_branch") or CONST.DEFAULT_BRANCH)

    raw_sources = raw.get("sources") or []
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ConfigError(f"{source_path}: at least one [[sources]] entry is required")

    sources = tuple(_source_from_raw(s, source_path=source_path) for s in raw_sources)
    _validate_unique_names(sources, source_path=source_path)

    return Config(
        version=version,
        local_cloning_directory=cloning_dir,
        default_branch=default_branch,
        sources=sources,
    )


def _source_from_raw(raw: t.Mapping[str, t.Any], *, source_path: Path) -> Source:
    name = raw.get("name")
    url = raw.get("url")
    if not name or not url:
        raise ConfigError(
            f"{source_path}: each [[sources]] entry needs both 'name' and 'url'"
        )
    branch = raw.get("branch")
    return Source(
        name=str(name),
        url=str(url),
        branch=str(branch) if branch else None,
    )


def _validate_unique_names(sources: t.Tuple[Source, ...], *, source_path: Path) -> None:
    seen: t.Set[str] = set()
    for s in sources:
        if s.name in seen:
            raise ConfigError(f"{source_path}: duplicate source name {s.name!r}")
        seen.add(s.name)


def _config_to_doc(config: Config) -> tomlkit.TOMLDocument:
    doc = tomlkit.document()
    doc.add("version", config.version)
    doc.add("local_cloning_directory", str(config.local_cloning_directory))
    doc.add("default_branch", config.default_branch)
    sources_array = tomlkit.aot()
    for s in config.sources:
        item = tomlkit.table()
        item.add("name", s.name)
        item.add("url", s.url)
        if s.branch:
            item.add("branch", s.branch)
        sources_array.append(item)
    doc.add("sources", sources_array)
    return doc
