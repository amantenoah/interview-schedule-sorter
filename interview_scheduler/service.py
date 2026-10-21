"""Application service that coordinates workbook parsing, scheduling, and output."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from interview_scheduler.errors import InputValidationError
from interview_scheduler.models import AvailabilityGrid, SlotDemand
from interview_scheduler.optimizer import assign_interviewers
from interview_scheduler.workbook import EXPECTED_TIME_SLOTS, read_availability, write_schedule

INTERVIEW_DAY_NUMBERS = (1, 2, 3, 4, 7, 8, 9, 10, 11)
EXPECTED_WEEKDAYS = (
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
)


def build_interview_dates(year: int = 2026) -> tuple[date, ...]:
    """Build the requested September dates and verify their weekday pattern."""

    dates = tuple(date(year, 9, day_number) for day_number in INTERVIEW_DAY_NUMBERS)
    weekdays = tuple(interview_date.strftime("%A") for interview_date in dates)
    if weekdays != EXPECTED_WEEKDAYS:
        raise InputValidationError(
            f"September {year} does not match the requested Tuesday-Friday / Monday-Friday pattern."
        )
    return dates


def _expand_demands(grid: AvailabilityGrid, dates: tuple[date, ...]) -> tuple[SlotDemand, ...]:
    return tuple(
        SlotDemand(
            interview_date,
            slot,
            tuple(sorted(grid.available_for(interview_date.strftime("%A"), slot), key=str.casefold)),
        )
        for interview_date in dates
        for slot in EXPECTED_TIME_SLOTS
    )


def create_interview_schedule(
    input_path: str | Path,
    output_path: str | Path,
    *,
    year: int = 2026,
    force: bool = False,
) -> Path:
    """Create a complete schedule from the recurring weekday availability workbook."""

    source, destination = Path(input_path), Path(output_path)
    if source.resolve(strict=False) == destination.resolve(strict=False):
        raise InputValidationError("The output path must be different from the input workbook.")
    if destination.exists() and not force:
        raise FileExistsError(f"Output already exists: {destination}. Pass --force to replace it.")
    grid = read_availability(source)
    demands = _expand_demands(grid, build_interview_dates(year))
    schedule = assign_interviewers(demands, grid.interviewers)
    return write_schedule(schedule, destination)
