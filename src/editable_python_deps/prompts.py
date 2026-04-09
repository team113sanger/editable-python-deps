"""Interactive setup wizard, built on prompt_toolkit's dialog shortcuts.

The wizard collects ``local_cloning_directory``, ``default_branch``, and
a list of editable-source entries, then returns a fully-formed
:class:`Config`. The action layer is responsible for writing the config
to disk via the runner so dry-run is honoured.

The wizard is a sequence of modal dialogs:

1. Intro confirm (yes/no)
2. Local cloning directory (input)
3. Default git branch (input)
4. Source review menu (radiolist) — loops on Add / Edit / Remove / Finish
5. Per-source three-input capture flow with Cancel = drop this source
6. Final summary confirm (yes/no)

Cancel on the top-level dialogs (1, 2, 3, 6) raises ``KeyboardInterrupt``
so ``_cli_wrapper`` exits with code 2. Cancel inside a source-capture
dialog returns ``None`` which bounces back to the review menu with the
prior sources intact.
"""

from __future__ import annotations

import re
import typing as t
from pathlib import Path
from urllib.parse import urlsplit

from prompt_toolkit.shortcuts import (
    input_dialog,
    radiolist_dialog,
    yes_no_dialog,
)
from prompt_toolkit.validation import ValidationError, Validator

from editable_python_deps import constants as CONST
from editable_python_deps.config import Config, Source, load_config
from editable_python_deps.exceptions import ConfigNotFoundError
from editable_python_deps.io import Printer, default_printer

_DIALOG_TITLE = "editable-python-deps setup"


# --- validators -------------------------------------------------------------


class _NonEmptyValidator(Validator):
    def validate(self, document) -> None:  # type: ignore[override]
        if not document.text.strip():
            raise ValidationError(message="Value cannot be empty.")


class _RelativePathValidator(Validator):
    def validate(self, document) -> None:  # type: ignore[override]
        text = document.text.strip()
        if not text:
            raise ValidationError(message="Value cannot be empty.")
        if Path(text).is_absolute():
            raise ValidationError(message="Path must be relative.")


# scp-style SSH: user@host:path  (path is anything non-whitespace)
_SSH_RE = re.compile(r"^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:[^\s]+$")


def _looks_like_http_url(text: str) -> bool:
    try:
        parts = urlsplit(text)
    except Exception:  # noqa: BLE001
        return False
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


class _GitUrlValidator(Validator):
    """Light validation: accept SSH (scp-style) or HTTP(S) git URLs."""

    _MESSAGE = (
        "Expected an SSH (git@host:path) or HTTPS " "(https://host/path) git URL."
    )

    def validate(self, document) -> None:  # type: ignore[override]
        text = document.text.strip()
        if not text:
            raise ValidationError(message=self._MESSAGE)
        if _SSH_RE.match(text) or _looks_like_http_url(text):
            return
        raise ValidationError(message=self._MESSAGE)


# --- entry point ------------------------------------------------------------


def run_setup_wizard(
    *,
    project_dir: Path,
    existing_path: Path,
    printer: Printer = default_printer,  # noqa: ARG001 (kept for symmetry)
) -> Config:
    """Run the dialog wizard and return a populated Config."""
    del printer  # unused inside dialogs; kept on the signature for callers
    existing = _try_load(existing_path)

    if not _confirm_intro_dialog(project_dir, existing_path, existing):
        raise KeyboardInterrupt

    cloning_dir = _input_with_validator(
        text=("Local cloning directory (relative to the project root):"),
        default=_default(existing, "local_cloning_directory"),
        validator=_RelativePathValidator(),
    )
    default_branch = _input_with_validator(
        text="Default git branch for editable sources:",
        default=_default(existing, "default_branch"),
        validator=_NonEmptyValidator(),
    )

    sources = _collect_sources_via_review_loop(
        existing=existing.sources if existing else (),
    )
    if not sources:
        # Q2: refusing zero-source configs is implemented by raising
        # KeyboardInterrupt so _cli_wrapper exits with code 2.
        raise KeyboardInterrupt

    config = Config(
        version=CONST.CURRENT_CONFIG_VERSION,
        local_cloning_directory=Path(cloning_dir),
        default_branch=default_branch,
        sources=tuple(sources),
    )

    if not _confirm_summary_dialog(config, target=existing_path):
        raise KeyboardInterrupt
    return config


# --- dialog wrappers --------------------------------------------------------


def _confirm_intro_dialog(
    project_dir: Path, target: Path, existing: t.Optional[Config]
) -> bool:
    state = "(exists)" if existing else "(new)"
    text = (
        f"Project directory:\n  {project_dir}\n\n"
        f"Config file:\n  {target}  {state}\n\n"
        "An 'editable source' is a git repository this tool will clone "
        "locally and add to your Poetry project as an --editable "
        "dependency. You can edit the file by hand later.\n\n"
        "Continue?"
    )
    return bool(yes_no_dialog(title=_DIALOG_TITLE, text=text).run())


def _input_with_validator(*, text: str, default: str, validator: Validator) -> str:
    """Run input_dialog and treat Cancel as KeyboardInterrupt."""
    result = input_dialog(
        title=_DIALOG_TITLE,
        text=text,
        default=default,
        validator=validator,
    ).run()
    if result is None:
        raise KeyboardInterrupt
    return result.strip()


def _collect_sources_via_review_loop(
    existing: t.Sequence[Source],
) -> t.List[Source]:
    sources: t.List[Source] = list(existing)
    while True:
        choice = _review_dialog(sources)
        if choice == "finish":
            return sources
        if choice == "cancel":
            return []
        _apply_review_action(choice, sources)


def _apply_review_action(choice: str, sources: t.List[Source]) -> None:
    """Mutate ``sources`` in place per the chosen review-menu action."""
    handler = _REVIEW_ACTIONS.get(choice)
    if handler is not None:
        handler(sources)


def _action_add(sources: t.List[Source]) -> None:
    new_source = _capture_source_dialog(prefill=None)
    if new_source is not None:
        sources.append(new_source)


def _action_edit(sources: t.List[Source]) -> None:
    index = _pick_source_dialog(sources, action="edit")
    if index is None:
        return
    edited = _capture_source_dialog(prefill=sources[index])
    if edited is not None:
        sources[index] = edited


def _action_remove(sources: t.List[Source]) -> None:
    index = _pick_source_dialog(sources, action="remove")
    if index is not None:
        del sources[index]


_REVIEW_ACTIONS: t.Dict[str, t.Callable[[t.List[Source]], None]] = {
    "add": _action_add,
    "edit": _action_edit,
    "remove": _action_remove,
}


def _review_dialog(sources: t.Sequence[Source]) -> str:
    """Show the source review radiolist; return one of add/edit/remove/finish/cancel."""
    if sources:
        listing_lines = [
            f"  {i + 1}. {s.name} <- {s.url}" for i, s in enumerate(sources)
        ]
        listing = "\n".join(listing_lines)
        text = f"Currently captured ({len(sources)}):\n{listing}"
    else:
        text = (
            "Currently captured (0):\n" "  (none yet — add your first editable source)"
        )

    values: t.List[t.Tuple[str, str]] = [
        ("add", "Add a new editable source"),
    ]
    if sources:
        values.append(("edit", "Edit an existing source"))
        values.append(("remove", "Remove an existing source"))
        values.append(
            (
                "finish",
                f"Finish (write config with {len(sources)} source"
                f"{'s' if len(sources) != 1 else ''})",
            )
        )

    result = radiolist_dialog(
        title="Editable sources",
        text=text,
        values=values,
        default="add",
    ).run()
    if result is None:
        return "cancel"
    return result


def _pick_source_dialog(sources: t.Sequence[Source], *, action: str) -> t.Optional[int]:
    """Show a radiolist of sources; return the chosen index or None on Cancel."""
    values = [(i, f"{i + 1}. {s.name} <- {s.url}") for i, s in enumerate(sources)]
    result = radiolist_dialog(
        title=f"Pick a source to {action}",
        text=f"Choose which editable source to {action}.",
        values=values,
        default=0,
    ).run()
    if result is None:
        return None
    return int(result)


def _capture_source_dialog(*, prefill: t.Optional[Source]) -> t.Optional[Source]:
    """Run three input_dialogs to capture one source. Cancel anywhere → None."""
    name = input_dialog(
        title="Editable source — name",
        text="Package name (the name poetry uses for this dependency):",
        default=prefill.name if prefill else "",
        validator=_NonEmptyValidator(),
    ).run()
    if name is None:
        return None
    url = input_dialog(
        title="Editable source — repository URL",
        text="Repository URL (HTTPS or SSH):",
        default=prefill.url if prefill else "",
        validator=_GitUrlValidator(),
    ).run()
    if url is None:
        return None
    branch = input_dialog(
        title="Editable source — branch override",
        text="Branch override (leave blank to use the wizard default):",
        default=(prefill.branch or "") if prefill else "",
    ).run()
    if branch is None:
        return None
    branch_text = branch.strip()
    return Source(
        name=name.strip(),
        url=url.strip(),
        branch=branch_text or None,
    )


def _confirm_summary_dialog(config: Config, *, target: Path) -> bool:
    listing_lines = [
        f"    {i + 1}. {s.name} <- {s.url}" + (f" [{s.branch}]" if s.branch else "")
        for i, s in enumerate(config.sources)
    ]
    listing = "\n".join(listing_lines)
    text = (
        f"Will write to:\n  {target}\n\n"
        f"  local_cloning_directory: {config.local_cloning_directory}\n"
        f"  default_branch         : {config.default_branch}\n"
        f"  sources                : {len(config.sources)}\n\n"
        f"{listing}\n\n"
        "Write this config?"
    )
    return bool(yes_no_dialog(title="New configuration", text=text).run())


# --- helpers (testable without hitting prompt_toolkit) ----------------------


def _try_load(path: Path) -> t.Optional[Config]:
    try:
        return load_config(path)
    except ConfigNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        return None


def _default(existing: t.Optional[Config], attr: str) -> str:
    if existing is None:
        defaults = {
            "local_cloning_directory": CONST.DEFAULT_LOCAL_CLONING_DIR,
            "default_branch": CONST.DEFAULT_BRANCH,
        }
        return defaults[attr]
    return str(getattr(existing, attr))
