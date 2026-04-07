import typing as t
from pathlib import Path

import logging

logger = logging.getLogger(__name__)


def main(input_file: t.Union[str, Path], output_file: t.Union[str, Path]) -> bool:
    """
    The first and main entry point of the package. Typically you expose this
    function to the cli. See cli.py.
    """
    # Recast the input and output file paths to Path objects for better
    # portability and manipulation.
    input_file = Path(input_file)
    output_file = Path(output_file)

    # Example of using the logger
    logger.debug(f"Input file: {input_file}")
    logger.debug(f"Output file: {output_file}")

    return True  # Or False based on your logic to handle success or failure
