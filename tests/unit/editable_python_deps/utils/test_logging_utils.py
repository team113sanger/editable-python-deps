import logging
import sys

import pytest

from unittest.mock import Mock

import editable_python_deps
from editable_python_deps.utils.logging_utils import (
    get_package_logger,
    setup_logging,
    update_logger_level,
)


# FIXTURES


@pytest.fixture
def mock_package_logger(monkeypatch):
    """Mock the editable_python_deps.LOGGER with a Mock logger."""
    mock_logger = Mock(spec=logging.Logger)
    mock_logger.handlers = []
    monkeypatch.setattr("editable_python_deps.LOGGER", mock_logger)
    return mock_logger


# TESTS


def test_get_package_logger():
    # Given
    expected_logger = editable_python_deps.LOGGER
    called_logger = logging.getLogger("editable_python_deps")

    # When
    actual = get_package_logger()

    # Then
    assert actual is expected_logger
    assert called_logger is expected_logger


def test_setup_logging__returns_package_logger_by_default():
    # Given
    unmocked_logger = logging.getLogger("editable_python_deps")

    # When
    actual = setup_logging()

    # Then
    assert actual is unmocked_logger


def test_setup_logging__modifies_package_logger_with_handler(mock_package_logger):
    # Given
    # mock_package_logger fixture provides the mocked logger

    # When
    actual = setup_logging()

    # Then
    assert actual is mock_package_logger
    mock_package_logger.setLevel.assert_called_once_with(logging.INFO)
    mock_package_logger.addHandler.assert_called_once()


def test_setup_logging__removes_null_handler(mock_package_logger):
    # Given
    null_handler = logging.NullHandler()
    other_handler = Mock(spec=logging.Handler)
    mock_package_logger.handlers = [null_handler, other_handler]

    # When
    setup_logging()

    # Then
    mock_package_logger.removeHandler.assert_called_once_with(null_handler)
