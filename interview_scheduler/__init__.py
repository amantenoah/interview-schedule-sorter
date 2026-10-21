"""Create fair member-interview schedules from recurring availability."""

from pathlib import Path


def create_interview_schedule(
    input_path: str | Path,
    output_path: str | Path,
    *,
    year: int = 2026,
    force: bool = False,
) -> Path:
    """Load spreadsheet dependencies only when the API is actually called."""

    from interview_scheduler.service import create_interview_schedule as implementation

    return implementation(input_path, output_path, year=year, force=force)

__all__ = ["create_interview_schedule"]
__version__ = "1.0.0"
