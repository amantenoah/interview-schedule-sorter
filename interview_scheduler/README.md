# Interview Scheduler

This program reads recurring Monday-Friday interviewer availability from an
Excel workbook and creates the September 2026 interview roster.

## Input workbook

- Sheets named `Monday`, `Tuesday`, `Wednesday`, `Thursday`, and `Friday`
  (matching is case-insensitive; unrelated extra sheets are ignored).
- `A4` contains `time`; interviewer names occupy consecutive cells from `B4`
  through at most `W4`.
- `A5:A18` contains the 14 half-hour intervals from `10:00-10:30 AM` through
  `4:30-5:00 PM`. `12:00 NN` is also accepted as a noon marker.
- Availability cells contain only `available` or `x`.
- The five sheets must contain the same interviewer names, although their
  column order may differ.

No manual CSV or other conversion is required. The program validates and
normalizes this layout in memory before scheduling.

## Install and run

See the project's [dependency list](../DEPENDENCIES.md) for the required
Python packages, locked versions, and installation options.

Recommended setup with `uv` (the checked-in lockfile installs the project and
all runtime dependencies into `.venv`):

```powershell
uv sync --locked
.\.venv\Scripts\Activate.ps1
python -m interview_scheduler availability.xlsx interview_schedule.xlsx
```

Without `uv`, create a regular pip-enabled environment and always invoke pip
through the same Python interpreter:

```powershell
py -m venv .venv-pip
.\.venv-pip\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python -m interview_scheduler availability.xlsx interview_schedule.xlsx
```

Avoid using bare `pip`. On Windows it can resolve to a global installation even
while `python` resolves to the active virtual environment.

Use `--force` to replace an existing output. The optional `--year` argument
defaults to `2026` and only accepts a year in which the requested September
dates have the stated Tuesday-Friday / Monday-Friday weekday pattern.

The optimizer assigns three distinct available interviewers to every cell. It
uses a fair min-cost-flow schedule as its starting point, then applies a
deterministic local search with this priority order:

1. favor blocks of two or three consecutive half-hours and avoid isolated or
   unnecessarily long runs;
2. minimize overall workload imbalance; and
3. minimize assignment concentration within individual days.

Continuity is the primary objective, so the optimizer may accept a slightly
wider workload spread when that produces better two- or three-slot blocks.
Fairness breaks ties between schedules with equal continuity quality.
Availability can make isolated or longer assignments unavoidable; blocks never
cross a date or a gap between time slots. If any slot has fewer than three
available people, the program creates no output and lists all affected dates
and times.
