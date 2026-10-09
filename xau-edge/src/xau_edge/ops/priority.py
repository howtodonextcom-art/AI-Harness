"""Run heavy batch jobs politely: lower this process's priority so the desk and the PC stay usable.

Windows: BELOW_NORMAL_PRIORITY_CLASS through the Win32 API (no extra dependency). Elsewhere:
``os.nice``. It never raises: failing to lower the priority only means the job runs at normal one.
"""

from __future__ import annotations

import os
import sys

BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def lower_priority() -> bool:
    """True when the priority was lowered."""
    try:
        if sys.platform == "win32":
            import ctypes  # noqa: PLC0415 - Windows only

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined,unused-ignore]
            handle = kernel32.GetCurrentProcess()
            return bool(kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS))
        os.nice(10)
    except (OSError, AttributeError):
        return False
    return True


def default_workers() -> int:
    """Parallel batch workers that leave most of the machine free: a quarter of the cores."""
    return max(1, (os.cpu_count() or 4) // 4)
