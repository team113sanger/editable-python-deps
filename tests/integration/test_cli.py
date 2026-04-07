import subprocess
import shlex
import shutil

import pytest

import editable_python_deps
from editable_python_deps import constants

MODULE_NAME = editable_python_deps.__name__
PROGRAM_NAME = constants.PROGRAM_NAME

# HELPERS


def get_subprocess_message(subproces_result: subprocess.CompletedProcess) -> str:
    indent = " " * 2

    msg = (
        f"Error running CLI command. "
        f"{indent}Command: {subproces_result.args}\n"
        f"{indent}Return code: {subproces_result.returncode}\n"
        f"{indent}Stdout: {subproces_result.stdout!r}\n"
        f"{indent}Stderr: {subproces_result.stderr!r}"
    )
    return msg


# TESTS


def test_python_dash_m__version():
    # Precondition
    # We assume the system has python installed but occasionally the binary may
    # be named python3 with no python binary.
    python_exec = "python"
    if shutil.which("python") is None:
        assert (
            shutil.which("python3") is not None
        ), "Python is not installed or not in PATH"
        python_exec = "python3"

    # Given
    cmd = f"{python_exec} -m {MODULE_NAME} --version"
    expected_version = editable_python_deps.__version__

    # When
    subproces_result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)

    # Then
    errmsg = get_subprocess_message(subproces_result)
    assert subproces_result.returncode == 0, errmsg
    assert PROGRAM_NAME in subproces_result.stdout
    assert expected_version in subproces_result.stdout


def test_cli_on_path():
    # When
    result = shutil.which(PROGRAM_NAME)
    err_msg = (
        f"{PROGRAM_NAME} is not in PATH, has the name changed in pyproject.toml "
        "or the constants.py file? Did you run `poetry install` if developing?"
    )
    assert result is not None, err_msg


def test_cli__version():
    # Given
    cmd = f"{PROGRAM_NAME} --version"
    expected_version = editable_python_deps.__version__

    # When
    subproces_result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)

    # Then
    errmsg = get_subprocess_message(subproces_result)
    assert subproces_result.returncode == 0, errmsg
    assert PROGRAM_NAME in subproces_result.stdout
    assert expected_version in subproces_result.stdout


def test_cli__help():
    # Given
    cmd = f"{PROGRAM_NAME} --help"

    # When
    subproces_result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)

    # Then
    errmsg = get_subprocess_message(subproces_result)
    assert subproces_result.returncode == 0, errmsg
    assert PROGRAM_NAME in subproces_result.stdout
