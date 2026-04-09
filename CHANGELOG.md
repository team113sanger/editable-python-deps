# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- `editable-python-deps` is now a Python CLI package with four
  subcommands — `on`, `off`, `status`, and `setup`
- transcoded from the original bash script `original/editable-deps.sh`.
- The CLI is installable via `pipx` and is configured per-project through a
  `.editable-deps.toml` file produced by an interactive `prompt_toolkit` dialog
  wizard.

## [0.1.0] - 2026-04-07
### Added
- Initial project setup using the template from [example-python-cicd](https://gitlab.internal.sanger.ac.uk/team113sanger/common/example-python-cicd).
- Template version is 0.1.6 -- consult its `CHANGELOG.md` for more details.
