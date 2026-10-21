"""Dependency-aware startup for ``python -m interview_scheduler``."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence

MainFunction = Callable[[Sequence[str] | None], int]


def _load_main() -> MainFunction:
    from interview_scheduler.cli import main

    return main


def _print_dependency_help(dependency: str) -> None:
    print(
        f"Error: Python {sys.executable} cannot import the required dependency {dependency!r}.\n"
        "If this project uses uv, run this from the repository root:\n"
        "  uv sync --locked\n"
        "Otherwise install the project with the same Python interpreter:\n"
        "  python -m pip install -e .\n"
        "Do not rely on bare 'pip'; it may point to a different Python installation.",
        file=sys.stderr,
    )


def run(
    argv: Sequence[str] | None = None,
    *,
    main_loader: Callable[[], MainFunction] = _load_main,
) -> int:
    """Load the CLI lazily and explain missing runtime dependencies."""

    try:
        main = main_loader()
    except ModuleNotFoundError as error:
        if error.name not in {"defusedxml", "openpyxl"}:
            raise
        _print_dependency_help(error.name)
        return 3
    return main(argv)
