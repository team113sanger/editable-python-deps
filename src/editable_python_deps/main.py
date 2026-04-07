import typing as t
from pathlib import Path

import logging

logger = logging.getLogger(__name__)


def main(
    arg: str,
    config: t.Optional[t.Union[str, Path]] = None,
    setup: bool = False,
) -> bool:
    """
    The first and main entry point of the package. Typically you expose this
    function to the cli. See cli.py.
    """
    # Recast the config path to a Path object for better portability and
    # manipulation.
    if config is not None:
        config = Path(config)

    # Example of using the logger
    logger.debug(f"arg: {arg}")
    logger.debug(f"config: {config}")
    logger.debug(f"setup: {setup}")

    return True  # Or False based on your logic to handle success or failure
