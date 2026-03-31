"""TaskWeb - Web interface for Taskwarrior."""

import subprocess

__version__ = "0.1.0"

try:
    __commit__ = (
        subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        .decode()
        .strip()
    )
except Exception:
    __commit__ = ""
