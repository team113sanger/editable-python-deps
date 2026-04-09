"""Unit tests for editable_python_deps.git_ops."""

from __future__ import annotations

from pathlib import Path

import pytest

from editable_python_deps import git_ops


# --- environment probes -----------------------------------------------------


def test_git_is_available__true_when_command_succeeds(fp, runner_real):
    # Given a registered git --version
    fp.register(["git", "--version"], stdout="git version 2.42.0\n")

    # When git_is_available is queried
    actual = git_ops.git_is_available(runner_real)

    # Then it is True
    assert actual is True


def test_git_is_available__false_when_command_returns_nonzero(fp, runner_real):
    # Given a fake git that returns non-zero
    fp.register(["git", "--version"], returncode=127)

    # When git_is_available is queried
    actual = git_ops.git_is_available(runner_real)

    # Then it is False
    assert actual is False


# --- mutating operations ----------------------------------------------------


def test_git_clone_branch(fp, runner_real, tmp_path):
    # Given a registered git clone command
    dest = tmp_path / "repo"
    fp.register(
        [
            "git",
            "clone",
            "--branch",
            "develop",
            "git@example.com:foo/bar.git",
            str(dest),
        ]
    )

    # When git_clone_branch is invoked
    git_ops.git_clone_branch(
        runner_real, "git@example.com:foo/bar.git", dest, branch="develop"
    )

    # Then the registered command was called exactly once
    assert (
        fp.call_count(
            [
                "git",
                "clone",
                "--branch",
                "develop",
                "git@example.com:foo/bar.git",
                str(dest),
            ]
        )
        == 1
    )


def test_git_fetch(fp, runner_real, tmp_path):
    # Given a registered git fetch command
    fp.register(["git", "-C", str(tmp_path), "fetch", "origin", "develop", "--quiet"])

    # When git_fetch is invoked
    git_ops.git_fetch(runner_real, tmp_path, branch="develop")

    # Then the registered command was called exactly once
    assert (
        fp.call_count(
            ["git", "-C", str(tmp_path), "fetch", "origin", "develop", "--quiet"]
        )
        == 1
    )


def test_git_merge_ff_only(fp, runner_real, tmp_path):
    # Given a registered fast-forward merge command
    fp.register(["git", "-C", str(tmp_path), "merge", "--ff-only", "FETCH_HEAD"])

    # When git_merge_ff_only is invoked
    git_ops.git_merge_ff_only(runner_real, tmp_path, ref="FETCH_HEAD")

    # Then the registered command was called exactly once
    assert (
        fp.call_count(["git", "-C", str(tmp_path), "merge", "--ff-only", "FETCH_HEAD"])
        == 1
    )


# --- state probes -----------------------------------------------------------


def test_git_rev_parse__strips_trailing_newline(fp, runner_real, tmp_path):
    # Given a registered rev-parse that returns a SHA + newline
    sha = "deadbeefcafebabedeadbeefcafebabe00000000"
    fp.register(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], stdout=f"{sha}\n")

    # When git_rev_parse is invoked
    actual = git_ops.git_rev_parse(runner_real, tmp_path, ref="HEAD")

    # Then the trimmed SHA is returned
    assert actual == sha


def test_git_status_is_clean__returns_true_when_porcelain_is_empty(
    fp, runner_real, tmp_path
):
    # Given a clean working tree (empty porcelain output)
    fp.register(["git", "-C", str(tmp_path), "status", "--porcelain"], stdout="")

    # When checking cleanliness
    actual = git_ops.git_status_is_clean(runner_real, tmp_path)

    # Then the helper returns True
    assert actual is True


def test_git_status_is_clean__returns_false_when_files_modified(
    fp, runner_real, tmp_path
):
    # Given a dirty working tree (non-empty porcelain output)
    fp.register(
        ["git", "-C", str(tmp_path), "status", "--porcelain"],
        stdout=" M README.md\n",
    )

    # When checking cleanliness
    actual = git_ops.git_status_is_clean(runner_real, tmp_path)

    # Then the helper returns False
    assert actual is False


# --- git_is_ancestor --------------------------------------------------------


def test_git_is_ancestor__true_when_returncode_zero(fp, runner_real, tmp_path):
    # Given merge-base --is-ancestor returns 0 (HEAD is an ancestor)
    fp.register(
        [
            "git",
            "-C",
            str(tmp_path),
            "merge-base",
            "--is-ancestor",
            "HEAD",
            "FETCH_HEAD",
        ],
        returncode=0,
    )

    # When git_is_ancestor is invoked
    actual = git_ops.git_is_ancestor(
        runner_real, tmp_path, ancestor="HEAD", descendant="FETCH_HEAD"
    )

    # Then the helper returns True
    assert actual is True


def test_git_is_ancestor__false_when_returncode_one(fp, runner_real, tmp_path):
    # Given merge-base --is-ancestor returns 1 (not an ancestor)
    fp.register(
        [
            "git",
            "-C",
            str(tmp_path),
            "merge-base",
            "--is-ancestor",
            "HEAD",
            "FETCH_HEAD",
        ],
        returncode=1,
    )

    # When git_is_ancestor is invoked
    actual = git_ops.git_is_ancestor(
        runner_real, tmp_path, ancestor="HEAD", descendant="FETCH_HEAD"
    )

    # Then the helper returns False
    assert actual is False


# --- show_diff_no_index -----------------------------------------------------


def test_show_diff_no_index__when_git_available_and_no_diff(fp, runner_real, tmp_path):
    # Given git is available AND the quiet probe reports no diff
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("hello")
    right.write_text("hello")

    fp.register(["git", "--version"], stdout="git version 2.42.0\n")
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
            str(left),
            str(right),
        ],
        returncode=0,
    )

    # When show_diff_no_index is invoked
    captured: list[str] = []
    git_ops.show_diff_no_index(
        runner_real,
        left,
        right,
        header="Diff: preview",
        printer=captured.append,
    )

    # Then output mentions "no differences"
    assert any("no differences" in line for line in captured)


def test_show_diff_no_index__falls_back_to_diff_when_git_unavailable(
    fp, runner_real, tmp_path
):
    # Given git is unavailable AND a diff -u fallback is registered
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("a")
    right.write_text("b")

    fp.register(["git", "--version"], returncode=127)
    fp.register(
        ["diff", "-u", str(left), str(right)],
        returncode=1,
        stdout="--- left\n+++ right\n",
    )

    # When show_diff_no_index is invoked
    captured: list[str] = []
    git_ops.show_diff_no_index(
        runner_real,
        left,
        right,
        header="Diff: preview",
        printer=captured.append,
    )

    # Then the fallback diff output is in the captured lines
    joined = "\n".join(captured)
    assert "--- left" in joined or "End of diff" in joined
