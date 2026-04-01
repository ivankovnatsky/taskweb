"""TaskWeb - Web interface for Taskwarrior."""

import os
import subprocess

__version__ = "0.1.0"

# Try env var first (set by Nix build), then fall back to git
_env_commit = os.environ.get("TASKWEB_COMMIT", "")

if _env_commit:
    __commit_full__ = _env_commit
    __commit__ = _env_commit[:7] if len(_env_commit) > 7 else _env_commit
else:
    try:
        __commit__ = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        __commit_full__ = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        __commit__ = ""
        __commit_full__ = ""
