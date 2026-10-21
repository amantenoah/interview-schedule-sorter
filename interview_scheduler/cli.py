"""Command-line interface for the interview scheduler."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from openpyxl.utils.exceptions import InvalidFileException

from interview_scheduler.errors import InterviewSchedulerError
from interview_scheduler.service import create_interview_schedule


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="interview-scheduler",
        description="Create a fair September interview schedule from five weekday availability sheets.",
    )
    parser.add_argument("input", type=Path, help="Input .xlsx workbook with Monday-Friday sheets")
    parser.add_argument("output", type=Path, help="Destination .xlsx schedule")
    parser.add_argument("--year", type=int, default=2026, help="Interview year (default: 2026)")
    parser.add_argument("--force", action="store_true", help="Replace an existing output workbook")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        output = create_interview_schedule(
            arguments.input,
            arguments.output,
            year=arguments.year,
            force=arguments.force,
        )
    except (InterviewSchedulerError, InvalidFileException, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(f"Created interview schedule: {output}")
    return 0
