# editable-python-deps

A development-environment utility that lets you reproducibly switch
specified Python dependencies of a Poetry project from their normal
non-editable, lockfile-pinned form into local, user-editable git clones
and back again.

The motivating workflow is "I'm cross-cutting two related
Poetry projects and I want to edit-and-test the dependency in place
instead of going through the commit → push → wait-for-CI → `poetry update`
loop."

## Concept

```
BEFORE                                    AFTER with 'editable-python-deps'
------                                    -----
                                           Run 'editable-python-deps on'
                                              |
                                              ▼
 Edit upstream library separately          Edit & integrate upstream library changes locally
      |                                       |
      ▼                                       ▼
 Commit, tag, push                         Test --► Broken? Or a new feature?
      |                                       |
      ▼                                       ▼
 Wait ~20 min for CI...                    Just fix it
      |                                       |
      ▼                                       ▼
 poetry update --► Integrate --► Broken?   Confident it works
                              |               |
                              ▼               ▼
                           Start over      Commit, tag, push
                                              |
                                              ▼
                                           Run 'editable-python-deps off'
```

## Install

The tool is not on PyPI yet. Install it from the public GitHub repo with
[`pipx`](https://pipx.pypa.io/):

```bash
pipx install "git+https://github.com/team113sanger/editable-python-deps.git"

# Latest commit on the develop branch (may need --force if you already have it installed)
pipx install "git+https://github.com/team113sanger/editable-python-deps.git@develop"

# A specific tag
pipx install "git+https://github.com/team113sanger/editable-python-deps.git@v0.1.0"

# A specific commit SHA
pipx install "git+https://github.com/team113sanger/editable-python-deps.git@a1b2c3d"
```

To upgrade later:

```bash
pipx upgrade editable-python-deps
```

To remove:

```bash
pipx uninstall editable-python-deps
```

## Quick start

Run the commands below from the root of any Poetry project (i.e. the
directory containing `pyproject.toml`).

```bash
# 1. Switch the project into editable state. Clones each configured
#    source under .editable-deps/<name>/ and runs
#    `poetry add --editable <path>` for each one.
#
#   On first run, an interactive setup wizard will guide you
#   through configuring the editable dependencies.
#    
#   This command is idempotent and when run multiple times will
#   safely pull the latest changes without overwriting 
#   any uncommitted work in the clones.
editable-python-deps on

# 2. ... edit code in .editable-deps/<name>/ ...

# 3. Switch back to the lockfile-pinned state, restoring pyproject.toml
#    and poetry.lock from backups taken during 'on'.
editable-python-deps off
```

Extra commmands:
```bash
# A. Interactive setup. Run (or re-run) a setup wizard
#    that records which git repos to clone as editable dependencies.
editable-python-deps setup

# B. Show the current state at any time.
editable-python-deps status
```

By default the tool creates two things alongside your `pyproject.toml`:

| Path | Purpose |
|---|---|
| `.editable-deps.toml` | Per-project config listing the editable sources, their git URLs, and the default branch. Safe to commit, edit by hand, or regenerate via `setup`. |
| `.editable-deps/<repo>/` | The local clone of each editable source. Created on first `on`; preserved between runs so any uncommitted work you do there is never lost. |

`on` is idempotent: running it again refuses to overwrite existing
backups, will not pull a clone that has uncommitted changes, and will
skip any fast-forward where the local branch is ahead of (or has
diverged from) `origin` so unpushed commits are never silently clobbered.

Use `editable-python-deps --help` (and `<subcommand> --help`) for the
full option surface, including `--dry-run` for previewing what `on` /
`off` / `setup` would do without touching disk.

## For developers

The project uses [Poetry](https://python-poetry.org/) for dependency
management and packaging, and [pytest](https://docs.pytest.org/) for
tests. Target environment is **Python 3.10 or newer**.

Build a wheel locally and install it via `pipx`:

```bash
python3 -m venv .venv
source .venv/bin/activate
poetry install              # creates .venv/ with all dev deps
poetry build                # produces dist/editable_python_deps-*.whl
pipx install --force dist/*.whl
```

Run the test suite:

```bash
source .venv/bin/activate
pytest tests/
```

Format and lint with the configured pre-commit hooks (black + flake8):

```bash
source .venv/bin/activate
pre-commit install         #  first time only, sets up git hooks
pre-commit run --all-files
```

The repository is hosted on
<https://github.com/team113sanger/editable-python-deps> (mirrored from an
[Sanger's private GitLab](https://gitlab.internal.sanger.ac.uk/team113sanger/common/editable-python-deps)).
Open issues on the GitHub side and create fork if contributing outside Sanger.
