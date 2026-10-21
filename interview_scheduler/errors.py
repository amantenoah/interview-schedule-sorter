"""Domain errors raised by the interview scheduler."""


class InterviewSchedulerError(Exception):
    """Base class for expected, user-correctable scheduler errors."""


class InputValidationError(InterviewSchedulerError):
    """Raised when the availability workbook does not match the contract."""


class SchedulingError(InterviewSchedulerError):
    """Raised when the requested interviews cannot be fully staffed."""
