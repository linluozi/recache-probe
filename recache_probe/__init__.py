"""recache-probe: measure CPython's regex-cache re-entry tax."""

from .probe import PatternStat, Probe, format_report, probe

__all__ = ["PatternStat", "Probe", "format_report", "probe"]
__version__ = "0.1.0"
