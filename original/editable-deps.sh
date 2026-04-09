#!/bin/bash
#
#####################
#  !!!IMPORTANT!!!  #
#####################
#
# This script has been replaced by the editable-python-deps package, which
# provides a more robust and user-friendly implementation of the same workflow.
#
#####################
#    DESCRIPTION    #
#####################
#
# Source this script to:
#   1. Clone editable dependency repos into ./_editable-deps/
#   2. Define shell functions: editable_dependencies / no_editable_dependencies
#
# Switching logic:
#   - editable_dependencies:
#       snapshot pyproject.toml + poetry.lock -> hidden backups (once)
#       then poetry add --editable <path> ...
#   - no_editable_dependencies:
#       require backups
#       show diff (pyproject vs backup)
#       restore pyproject+lock from backups
#       poetry sync | poetry install --sync | poetry install
#       delete backups
#
#
#####################
# !!!CHANGE THIS!!! #
#####################
#
# --- USER DEFINABLE CONSTANTS ---
# _EDITABLE_DEPS_REPOS requires two whitespace seperated values -
#  - the package name as it appears in a pyproject.toml
#  - the repository SSH GitHub/GitLab URL that hosts the package
#
# Template for _EDITABLE_DEPS_REPOS:
## _EDITABLE_DEPS_REPOS="$(cat <<'EOF'
##   <package-name>  <repo-ssh-url>
## EOF
## )"

_EDITABLE_DEPS_REPOS="$(cat <<'EOF'
    dermatlas             git@gitlab.internal.sanger.ac.uk:DERMATLAS/dermatlas-py.git
    t113-google-drive     git@gitlab.internal.sanger.ac.uk:team113sanger/common/t113-google-drive.git
    dermatlas-web-client  git@gitlab.internal.sanger.ac.uk:DERMATLAS/dermatlas-web-client.git
EOF
)"

# OTHER CONSTANTS - USER CAN CHANGE BUT UNNECESSARY
_EDITABLE_DEPS_BASE_DIR_NAME="_editable-deps"
_EDITABLE_DEPS_DEFAULT_BRANCH="develop"

# --- STYLE / COLOURS (private constants) ---
# Honour NO_COLOR, and avoid emitting ANSI when stderr isn't a TTY.
# Forgive sourcing twice when _ED_* variables may already exist with `>/dev/null 2>&1 || true` term
_EDITABLE_DEPS_USE_COLOR=1
if [[ -n "${NO_COLOR:-}" || ! -t 2 ]]; then
  _EDITABLE_DEPS_USE_COLOR=0
fi

if [[ $_EDITABLE_DEPS_USE_COLOR -eq 1 ]]; then
  readonly _ED_RST=$'\033[0m' >/dev/null 2>&1 || true
  readonly _ED_BLD=$'\033[1m' >/dev/null 2>&1 || true
  readonly _ED_RED=$'\033[31m' >/dev/null 2>&1 || true
  readonly _ED_GRN=$'\033[32m' >/dev/null 2>&1 || true
  readonly _ED_YEL=$'\033[33m' >/dev/null 2>&1 || true
  readonly _ED_CYN=$'\033[36m' >/dev/null 2>&1 || true
else
  readonly _ED_RST="" >/dev/null 2>&1 || true
  readonly _ED_BLD="" >/dev/null 2>&1 || true
  readonly _ED_RED="" >/dev/null 2>&1 || true
  readonly _ED_GRN="" >/dev/null 2>&1 || true
  readonly _ED_YEL="" >/dev/null 2>&1 || true
  readonly _ED_CYN="" >/dev/null 2>&1 || true
fi

# Semantic tags (use these; avoid raw escapes elsewhere; forgive sourcing twice when _ED_* variables may already exist)
readonly _ED_ERR="${_ED_BLD}${_ED_RED}Error:${_ED_RST}" >/dev/null 2>&1 || true
readonly _ED_WARN="${_ED_BLD}${_ED_YEL}Warning:${_ED_RST}" >/dev/null 2>&1 || true
readonly _ED_NOTE="${_ED_BLD}${_ED_YEL}Note:${_ED_RST}" >/dev/null 2>&1 || true
readonly _ED_OK="${_ED_BLD}${_ED_GRN}Done:${_ED_RST}" >/dev/null 2>&1 || true
readonly _ED_HDR="${_ED_BLD}" >/dev/null 2>&1 || true
readonly _ED_ENDHDR="${_ED_RST}" >/dev/null 2>&1 || true
readonly _ED_PATH="${_ED_CYN}" >/dev/null 2>&1 || true
readonly _ED_ENDPATH="${_ED_RST}" >/dev/null 2>&1 || true
readonly _ED_CMD="${_ED_CYN}" >/dev/null 2>&1 || true
readonly _ED_ENDCMD="${_ED_RST}" >/dev/null 2>&1 || true

_editable_deps_print_stderr() {
    # Interpret escapes (for colours), but don't rely on echo -e portability.
    printf "%b\n" "$1" >&2
}

# --- MUST BE SOURCED (not executed) ---
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  _editable_deps_print_stderr "${_ED_ERR} This script must be sourced (so the functions stay in your shell)."
  _editable_deps_print_stderr "  Use: ${_ED_CMD}source ${0##*/}${_ED_ENDCMD}   (or: ${_ED_CMD}. ${0##*/}${_ED_ENDCMD})"
  exit 1
fi

# --- INTERNAL HELPERS ---

_editable_deps_realpath() {
    # realpath is present on most Linux; fall back to python if needed
    if command -v realpath >/dev/null 2>&1; then
        realpath "$1"
    else
        python3 - <<PY
import os,sys
print(os.path.realpath(sys.argv[1]))
PY
    fi
}

_editable_deps_check_poetry() {
    if ! command -v poetry >/dev/null 2>&1; then
        _editable_deps_print_stderr "${_ED_ERR} Poetry is not installed or not on the PATH."
        return 1
    fi
}

_editable_deps_pick_project_dir() {
    # Prefer CWD if it looks like a poetry project; else fall back to script dir.
    if [[ -f "${PWD}/pyproject.toml" ]]; then
        echo "${PWD}"
        return 0
    fi

    local script_path script_dir
    script_path="$(_editable_deps_realpath "${BASH_SOURCE[0]}")"
    script_dir="$(dirname "$script_path")"

    if [[ -f "${script_dir}/pyproject.toml" ]]; then
        echo "${script_dir}"
        return 0
    fi

    _editable_deps_print_stderr "${_ED_ERR} Could not find pyproject.toml in \$PWD or next to this script."
    _editable_deps_print_stderr "  Run: ${_ED_CMD}cd <project-root>${_ED_ENDCMD} then source this script again."
    return 1
}

_editable_deps_require_project_files() {
    local project_dir="$1"
    local pyproject="${project_dir}/pyproject.toml"
    local lock="${project_dir}/poetry.lock"

    if [[ ! -f "$pyproject" ]]; then
        _editable_deps_print_stderr "${_ED_ERR} Missing ${_ED_PATH}${pyproject}${_ED_ENDPATH}"
        return 1
    fi
    if [[ ! -f "$lock" ]]; then
        _editable_deps_print_stderr "${_ED_ERR} Missing ${_ED_PATH}${lock}${_ED_ENDPATH} (this workflow expects a lockfile)."
        return 1
    fi
}

_editable_deps_print_diff_pyproject() {
    local current_pyproject="$1"
    local backup_pyproject="$2"

    _editable_deps_print_stderr ""
    _editable_deps_print_stderr "${_ED_HDR}Diff: pyproject.toml restore preview${_ED_ENDHDR}"
    _editable_deps_print_stderr "  LEFT  (---) = backup (non-editable snapshot): ${_ED_PATH}${backup_pyproject}${_ED_ENDPATH}"
    _editable_deps_print_stderr "  RIGHT (+++) = current (working file)       : ${_ED_PATH}${current_pyproject}${_ED_ENDPATH}"
    _editable_deps_print_stderr "  (In the diff below: '-' lines are LEFT/backup; '+' lines are RIGHT/current)\n"

    if command -v git >/dev/null 2>&1; then
        # Probe (quiet) without paging, bypassing any git alias/function.
        if command git -c core.pager=cat -c pager.diff=false diff --no-index --quiet \
            "$backup_pyproject" "$current_pyproject"; then
            _editable_deps_print_stderr "(no differences)"
            return 0
        fi

        # Print: force pager off AND make stdout non-tty to prevent any pager path.
        command git -c core.pager=cat -c pager.diff=false diff --no-index --color=always \
            "$backup_pyproject" "$current_pyproject" | cat
        _editable_deps_print_stderr "\n${_ED_HDR}End of diff${_ED_ENDHDR}"
        return 0
    fi

    # Fallback: diff -u with labels if supported
    if diff --help 2>/dev/null | grep -q -- '--label'; then
        diff -u \
          --label "LEFT  (backup non-editable snapshot)" \
          --label "RIGHT (current working pyproject)" \
          "$backup_pyproject" "$current_pyproject" || true
    else
        diff -u "$backup_pyproject" "$current_pyproject" || true
    fi
    _editable_deps_print_stderr "\n${_ED_HDR}End of diff${_ED_ENDHDR}"
}

_editable_deps_poetry_install_sync_if_supported() {
    # Preference order:
    #   1) poetry sync            (newer Poetry; preferred)
    #   2) poetry install --sync  (older Poetry; no sync cmd)
    #   3) poetry install         (very old Poetry)

    local POETRY=(command poetry)

    if "${POETRY[@]}" help sync >/dev/null 2>&1; then
        "${POETRY[@]}" sync
        return $?
    fi

    if "${POETRY[@]}" install --help 2>/dev/null | grep -q -- '--sync'; then
        "${POETRY[@]}" install --sync
        return $?
    fi

    _editable_deps_print_stderr "${_ED_NOTE} Neither '${_ED_CMD}poetry sync${_ED_ENDCMD}' nor '${_ED_CMD}poetry install --sync${_ED_ENDCMD}' is available; using plain '${_ED_CMD}poetry install${_ED_ENDCMD}'."
    "${POETRY[@]}" install
}

_editable_deps_git_clone_or_update() {
    local package_name="$1"
    local repo_url="$2"
    local target_dir="$3"
    local target_path="${target_dir}/${package_name}"

    if [[ ! -d "$target_path" ]]; then
        _editable_deps_print_stderr "Cloning ${_ED_PATH}${package_name}${_ED_ENDPATH} from ${_ED_PATH}${repo_url}${_ED_ENDPATH} into ${_ED_PATH}${target_path}${_ED_ENDPATH}..."
        git clone --branch "$_EDITABLE_DEPS_DEFAULT_BRANCH" "$repo_url" "$target_path"
        return $?
    fi

    if ! git -C "$target_path" diff --quiet || \
       ! git -C "$target_path" diff --cached --quiet || \
       [[ -n "$(git -C "$target_path" ls-files --others --exclude-standard)" ]]; then
        _editable_deps_print_stderr "${_ED_WARN} ${package_name} has uncommitted changes — skipping pull. Using current local state."
        _editable_deps_print_stderr "  Push or discard changes in ${_ED_PATH}${target_path}${_ED_ENDPATH} to use the latest ${_ED_PATH}${_EDITABLE_DEPS_DEFAULT_BRANCH}${_ED_ENDPATH} commit."
        return 0
    fi

    _editable_deps_print_stderr "Fetching latest ${_ED_PATH}${_EDITABLE_DEPS_DEFAULT_BRANCH}${_ED_ENDPATH} for ${_ED_PATH}${package_name}${_ED_ENDPATH}..."
    git -C "$target_path" fetch origin "$_EDITABLE_DEPS_DEFAULT_BRANCH" --quiet

    local local_sha remote_sha
    local_sha="$(git -C "$target_path" rev-parse HEAD)"
    remote_sha="$(git -C "$target_path" rev-parse FETCH_HEAD)"

    if [[ "$local_sha" == "$remote_sha" ]]; then
        _editable_deps_print_stderr "${package_name} is already up to date."
    else
        _editable_deps_print_stderr "Fast-forwarding ${package_name} to latest ${_ED_PATH}${_EDITABLE_DEPS_DEFAULT_BRANCH}${_ED_ENDPATH}..."
        git -C "$target_path" merge --ff-only FETCH_HEAD
    fi
}

# --- PUBLIC FUNCTIONS (left in caller's scope) ---

editable_dependencies() {
    _editable_deps_check_poetry || return 1

    local project_dir
    project_dir="$(_editable_deps_pick_project_dir)" || return 1
    _editable_deps_require_project_files "$project_dir" || return 1

    local pyproject="${project_dir}/pyproject.toml"
    local lock="${project_dir}/poetry.lock"
    local backup_pyproject="${project_dir}/.pyproject.toml.non-editable-backup"
    local backup_lock="${project_dir}/.poetry.lock.non-editable-backup"

    if [[ -e "$backup_pyproject" || -e "$backup_lock" ]]; then
        _editable_deps_print_stderr "${_ED_NOTE} Backup files already exist; not overwriting them."
        _editable_deps_print_stderr "  If you expected to be in non-editable state, consider running ${_ED_CMD}no_editable_dependencies${_ED_ENDCMD} first."
    else
        _editable_deps_print_stderr "Snapshotting non-editable state:"
        _editable_deps_print_stderr "  cp ${_ED_PATH}${pyproject}${_ED_ENDPATH} -> ${_ED_PATH}${backup_pyproject}${_ED_ENDPATH}"
        _editable_deps_print_stderr "  cp ${_ED_PATH}${lock}${_ED_ENDPATH} -> ${_ED_PATH}${backup_lock}${_ED_ENDPATH}"
        cp -p "$pyproject" "$backup_pyproject" || return 1
        cp -p "$lock" "$backup_lock" || return 1
    fi

    local target_dir="${project_dir}/${_EDITABLE_DEPS_BASE_DIR_NAME}"
    mkdir -p "$target_dir" || return 1

    local package_name repo_url
    while read -r package_name repo_url; do
        [[ -z "${package_name:-}" || -z "${repo_url:-}" ]] && continue

        local repo_path="${target_dir}/${package_name}"
        if [[ ! -d "$repo_path" ]]; then
            _editable_deps_print_stderr "${_ED_ERR} Repo not cloned for ${package_name} — re-source the script or run setup again."
            return 1
        fi

        _editable_deps_print_stderr "Making ${_ED_PATH}${package_name}${_ED_ENDPATH} editable from ${_ED_PATH}${repo_path}${_ED_ENDPATH}..."
        command poetry add --editable "$repo_path" || return 1
    done < <(printf '%s\n' "$_EDITABLE_DEPS_REPOS")
}

no_editable_dependencies() {
    _editable_deps_check_poetry || return 1

    local project_dir
    project_dir="$(_editable_deps_pick_project_dir)" || return 1

    local pyproject="${project_dir}/pyproject.toml"
    local lock="${project_dir}/poetry.lock"
    local backup_pyproject="${project_dir}/.pyproject.toml.non-editable-backup"
    local backup_lock="${project_dir}/.poetry.lock.non-editable-backup"

    if [[ ! -f "$backup_pyproject" || ! -f "$backup_lock" ]]; then
        _editable_deps_print_stderr "${_ED_ERR} Backup files are missing; cannot safely restore non-editable state."
        _editable_deps_print_stderr "  Expected:"
        _editable_deps_print_stderr "    ${_ED_PATH}${backup_pyproject}${_ED_ENDPATH}"
        _editable_deps_print_stderr "    ${_ED_PATH}${backup_lock}${_ED_ENDPATH}"
        _editable_deps_print_stderr "  Recover pyproject.toml/poetry.lock from git history (or re-checkout) and retry."
        return 1
    fi

    _editable_deps_print_diff_pyproject "$pyproject" "$backup_pyproject"

    _editable_deps_print_stderr "\nRestoring non-editable files from backup..."
    cp -f "$backup_pyproject" "$pyproject" || return 1
    cp -f "$backup_lock" "$lock" || return 1

    _editable_deps_print_stderr "\nRe-installing from restored lockfile..."
    _editable_deps_poetry_install_sync_if_supported || return 1

    _editable_deps_print_stderr "\nCleaning up backup files..."
    rm -f "$backup_pyproject" "$backup_lock" || return 1

    _editable_deps_print_stderr "${_ED_OK} restored non-editable dependency state."
}

# --- ONE-TIME SETUP (runs on source) ---

_editable_deps_setup() {
    _editable_deps_check_poetry || return 1

    local project_dir
    project_dir="$(_editable_deps_pick_project_dir)" || return 1

    local target_dir="${project_dir}/${_EDITABLE_DEPS_BASE_DIR_NAME}"
    mkdir -p "$target_dir" || return 1

    local dockerignore_path="${project_dir}/.dockerignore"
    if [[ -f "$dockerignore_path" ]]; then
        if ! grep -q "^${_EDITABLE_DEPS_BASE_DIR_NAME}/$" "$dockerignore_path"; then
            _editable_deps_print_stderr "Updating .dockerignore to exclude ${_ED_PATH}${_EDITABLE_DEPS_BASE_DIR_NAME}/${_ED_ENDPATH}..."
            {
                echo "# Added by editable-deps.sh to exclude cloned editable dependency repos"
                echo "${_EDITABLE_DEPS_BASE_DIR_NAME}/"
            } >> "$dockerignore_path"
        fi
    fi

    local package_name repo_url
    while read -r package_name repo_url; do
        [[ -z "${package_name:-}" || -z "${repo_url:-}" ]] && continue
        _editable_deps_git_clone_or_update "$package_name" "$repo_url" "$target_dir" || return 1
    done < <(printf '%s\n' "$_EDITABLE_DEPS_REPOS")

    _editable_deps_print_stderr ""
    _editable_deps_print_stderr "Available commands: ${_ED_CMD}editable_dependencies${_ED_ENDCMD}, ${_ED_CMD}no_editable_dependencies${_ED_ENDCMD}"
}

_editable_deps_setup
unset -f _editable_deps_setup
