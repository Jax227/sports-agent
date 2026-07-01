"""Auto-backup athlete data to git after changes.

Only runs when:
  - Inside a git repository
  - A remote 'origin' is configured
  - git push succeeds (silently skips on failure)

This ensures data survives: app restarts, device reboots, Streamlit Cloud redeployments,
and can be recovered via git history if needed.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "athletes"


def _is_git_available() -> bool:
    """Check if we're in a git repo with a remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def backup_on_change(action: str = "data_change") -> bool:
    """Commit and push athlete data to git. Non-blocking on failure.

    Returns True if backup succeeded, False if skipped or failed.
    """
    if not _is_git_available():
        return False

    try:
        # Stage data files
        subprocess.run(
            ["git", "add", str(DATA_DIR.relative_to(ROOT))],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )

        # Check if there are changes to commit
        status = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )
        if not status.stdout.strip():
            return False  # No changes

        # Commit
        subprocess.run(
            ["git", "commit", "-m", f"data: auto-backup {action}"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )

        # Push (may fail on Streamlit Cloud, that's OK)
        push_result = subprocess.run(
            ["git", "push", "origin", "master"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30,
        )
        return push_result.returncode == 0
    except Exception:
        return False
