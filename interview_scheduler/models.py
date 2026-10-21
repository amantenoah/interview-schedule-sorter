"""Immutable domain models used by the workbook and optimizer layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


def _format_clock(minutes: int) -> tuple[str, str]:
    hour_24, minute = divmod(minutes, 60)
    meridiem = "AM" if hour_24 < 12 else "PM"
    hour_12 = hour_24 % 12 or 12
    return f"{hour_12}:{minute:02d}", meridiem


@dataclass(frozen=True, order=True, slots=True)
class TimeSlot:
    """A half-hour interval represented as minutes after midnight."""

    start_minutes: int
    end_minutes: int

    def __post_init__(self) -> None:
        if self.end_minutes - self.start_minutes != 30:
            raise ValueError("A time slot must be exactly 30 minutes long.")

    @property
    def label(self) -> str:
        start, start_meridiem = _format_clock(self.start_minutes)
        end, end_meridiem = _format_clock(self.end_minutes)
        if start_meridiem == end_meridiem:
            return f"{start}-{end} {end_meridiem}"
        return f"{start} {start_meridiem}-{end} {end_meridiem}"


@dataclass(frozen=True, slots=True)
class WeekdayAvailability:
    weekday: str
    slots: tuple[tuple[TimeSlot, frozenset[str]], ...]

    def available_for(self, time_slot: TimeSlot) -> frozenset[str]:
        for candidate, available in self.slots:
            if candidate == time_slot:
                return available
        raise KeyError(f"No availability found for {self.weekday} {time_slot.label}.")


@dataclass(frozen=True, slots=True)
class AvailabilityGrid:
    interviewers: tuple[str, ...]
    weekdays: tuple[WeekdayAvailability, ...]

    def available_for(self, weekday: str, time_slot: TimeSlot) -> frozenset[str]:
        weekday_key = weekday.casefold()
        for entry in self.weekdays:
            if entry.weekday.casefold() == weekday_key:
                return entry.available_for(time_slot)
        raise KeyError(f"No availability sheet found for {weekday}.")


@dataclass(frozen=True, slots=True)
class SlotDemand:
    interview_date: date
    time_slot: TimeSlot
    available_interviewers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SlotAssignment:
    interview_date: date
    time_slot: TimeSlot
    interviewers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Schedule:
    assignments: tuple[SlotAssignment, ...]

