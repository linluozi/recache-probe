"""Measure how much time a Python process spends re-entering CPython's regex cache.

``re.match(pattern_str, s)`` calls ``re._compile`` on *every* call, even when the
pattern is already in ``re``'s 512-entry cache.  A precompiled ``Pattern`` skips
that path.  :class:`Probe` wraps ``re._compile`` and counts/attributes those
re-entries, so the tax can be measured instead of guessed.
"""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

__all__ = ["PatternStat", "Probe", "probe", "format_report"]


@dataclass
class PatternStat:
    """Aggregated re-entries for one ``(pattern, flags)`` pair."""

    calls: int = 0
    seconds: float = 0.0


@dataclass
class Probe:
    """Counts ``re._compile`` entries inside a ``with`` block."""

    calls: int = 0
    str_calls: int = 0
    compile_seconds: float = 0.0
    wall_seconds: float = 0.0
    stats: dict[tuple[str, int], PatternStat] = field(default_factory=dict)
    _saved: object | None = None
    _started: float = 0.0

    @property
    def unique_patterns(self) -> int:
        """Number of distinct string patterns that were re-entered."""
        return len(self.stats)

    @property
    def tax_ratio(self) -> float:
        """Time spent in ``re._compile`` divided by wall time of the block."""
        return self.compile_seconds / self.wall_seconds if self.wall_seconds else 0.0

    def top(self, limit: int = 10) -> list[tuple[str, int, int, float]]:
        """Return ``(pattern, flags, calls, seconds)`` sorted by seconds desc."""
        rows = [
            (pattern, flags, stat.calls, stat.seconds)
            for (pattern, flags), stat in self.stats.items()
        ]
        rows.sort(key=lambda row: row[3], reverse=True)
        return rows[:limit]

    def __enter__(self) -> "Probe":
        original = re._compile  # type: ignore[attr-defined]
        self._saved = original
        current = self

        def counted(pattern: object, flags: int):
            started = time.perf_counter()
            try:
                return original(pattern, flags)
            finally:
                elapsed = time.perf_counter() - started
                current.calls += 1
                current.compile_seconds += elapsed
                if isinstance(pattern, str):
                    current.str_calls += 1
                    key = (pattern, flags)
                    stat = current.stats.get(key)
                    if stat is None:
                        stat = current.stats[key] = PatternStat()
                    stat.calls += 1
                    stat.seconds += elapsed

        re._compile = counted  # type: ignore[attr-defined]
        self._started = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.wall_seconds = time.perf_counter() - self._started
        if self._saved is not None:
            re._compile = self._saved  # type: ignore[attr-defined]
            self._saved = None


@contextmanager
def probe() -> Iterator[Probe]:
    """Context manager returning a fresh :class:`Probe`."""
    p = Probe()
    with p:
        yield p


def format_report(p: Probe, limit: int = 10) -> str:
    """Human-readable summary of a probe run."""
    lines = [
        "regex cache probe",
        f"  re._compile calls : {p.calls} ({p.str_calls} with a string pattern)",
        f"  unique patterns   : {p.unique_patterns}",
        f"  time in _compile  : {p.compile_seconds * 1e3:.3f} ms "
        f"({p.tax_ratio * 100:.2f}% of {p.wall_seconds:.3f} s wall)",
    ]
    if p.stats:
        lines.append("  top patterns (by time):")
        for pattern, flags, calls, seconds in p.top(limit):
            shown = pattern if len(pattern) <= 60 else pattern[:57] + "..."
            lines.append(
                f"    {seconds * 1e3:8.3f} ms  {calls:8d}x  flags={flags}  {shown!r}"
            )
    return "\n".join(lines)
