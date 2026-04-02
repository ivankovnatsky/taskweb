"""TaskWeb - Web interface for Taskwarrior."""

import os
import subprocess

__version__ = "0.1.0"

# Nix build substitutes this placeholder with the actual commit hash
_NIX_COMMIT = "@NIX_COMMIT@"

# Priority: Nix build-time substitution > env var > git
if _NIX_COMMIT != "@" + "NIX_COMMIT" + "@":
    __commit_full__ = _NIX_COMMIT
    __commit__ = _NIX_COMMIT[:7] if len(_NIX_COMMIT) > 7 else _NIX_COMMIT
else:
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
