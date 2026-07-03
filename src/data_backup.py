"""Auto-backup athlete data via GitHub API (primary) or local git (fallback).

Works on Streamlit Cloud when GITHUB_TOKEN is set in secrets.
Works locally via git push if no token is configured.

Setup for Streamlit Cloud:
  1. Create a GitHub Personal Access Token (classic) with `repo` scope
  2. Add to .streamlit/secrets.toml:
     [github]
     token = "ghp_xxxxxxxxxxxx"
  3. Or set env var GITHUB_TOKEN
"""

import json
import os
import subprocess
from base64 import b64encode
from pathlib import Path
from hashlib import sha1

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "athletes"

# GitHub repo info — derive from git remote, or hardcode for Cloud
_GITHUB_REPO = None  # "Jax227/sports-agent"


def _get_github_token() -> str | None:
    """Get GitHub token from Streamlit secrets, env var, or .streamlit/secrets.toml."""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # Try Streamlit secrets
    try:
        import streamlit as st
        token = st.secrets.get("github", {}).get("token")
        if token:
            return token
    except Exception:
        pass

    # Try reading .streamlit/secrets.toml directly (non-Streamlit context)
    try:
        secrets_path = ROOT / ".streamlit" / "secrets.toml"
        if secrets_path.exists():
            content = secrets_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("token") and "=" in line:
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    except Exception:
        pass

    return None


def _get_github_repo() -> str | None:
    """Detect GitHub repo from git remote or config."""
    global _GITHUB_REPO
    if _GITHUB_REPO:
        return _GITHUB_REPO

    # Try git remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=5,
        )
        url = result.stdout.strip()
        # Extract owner/repo from various URL formats
        # git@github.com:Jax227/sports-agent.git
        # https://github.com/Jax227/sports-agent.git
        for prefix in ["github.com:", "github.com/"]:
            if prefix in url:
                path = url.split(prefix, 1)[1].removesuffix(".git")
                _GITHUB_REPO = path
                return _GITHUB_REPO
    except Exception:
        pass

    return None


def _api_request(method: str, endpoint: str, token: str, data: dict | None = None) -> dict | None:
    """Make a GitHub API v3 request. Returns parsed JSON or None on failure."""
    import urllib.request
    import urllib.error

    url = f"https://api.github.com{endpoint}"
    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body_bytes:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"[backup] GitHub API {method} {endpoint} failed: {e.code} {error_body[:200]}")
        return None
    except Exception as e:
        print(f"[backup] GitHub API request error: {e}")
        return None


def _collect_data_files() -> dict[str, str]:
    """Walk data/athletes/ and return {relative_path: file_content} for all JSON files."""
    files = {}
    if not DATA_DIR.is_dir():
        return files
    for p in DATA_DIR.rglob("*.json"):
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        files[rel] = content
    return files


def _compute_blob_sha(content: str) -> str:
    """Compute a git blob SHA for the given content."""
    header = f"blob {len(content)}\0"
    store = header + content
    return sha1(store.encode("utf-8")).hexdigest()


def backup_via_github_api(action: str = "data_change") -> bool:
    """Backup data files via GitHub API. Works on Streamlit Cloud.

    1. Read all data/athletes/ JSON files
    2. Create blobs for each
    3. Create a tree based on the current master HEAD
    4. Create a commit
    5. Update master ref
    """
    token = _get_github_token()
    if not token:
        return False

    repo = _get_github_repo()
    if not repo:
        print("[backup] Cannot determine GitHub repo")
        return False

    # Get current master HEAD SHA
    ref_data = _api_request("GET", f"/repos/{repo}/git/ref/heads/master", token)
    if not ref_data:
        # Try 'main' branch
        ref_data = _api_request("GET", f"/repos/{repo}/git/ref/heads/main", token)
    if not ref_data:
        print("[backup] Cannot get master/main ref")
        return False

    base_sha = ref_data["object"]["sha"]

    # Get the base tree SHA
    commit_data = _api_request("GET", f"/repos/{repo}/git/commits/{base_sha}", token)
    if not commit_data:
        return False
    base_tree_sha = commit_data["tree"]["sha"]

    # Collect current data files
    local_files = _collect_data_files()
    if not local_files:
        return False

    # Get existing tree to detect changes
    existing_tree = _api_request(
        "GET", f"/repos/{repo}/git/trees/{base_tree_sha}?recursive=1", token
    )

    # Check if any file actually changed (compare blob SHAs)
    existing_blobs = {}
    if existing_tree and "tree" in existing_tree:
        for item in existing_tree["tree"]:
            if item["type"] == "blob":
                existing_blobs[item["path"]] = item["sha"]

    changed = False
    tree_items = []
    for rel_path, content in sorted(local_files.items()):
        new_sha = _compute_blob_sha(content)
        old_sha = existing_blobs.get(rel_path)
        if new_sha != old_sha:
            changed = True
        tree_items.append({
            "path": rel_path,
            "mode": "100644",
            "type": "blob",
            "sha": new_sha,
        })

    if not changed:
        return False

    # Create tree
    tree_result = _api_request(
        "POST", f"/repos/{repo}/git/trees", token,
        data={"base_tree": base_tree_sha, "tree": tree_items},
    )
    if not tree_result:
        print("[backup] Failed to create tree")
        return False
    new_tree_sha = tree_result["sha"]

    # Create commit
    commit_result = _api_request(
        "POST", f"/repos/{repo}/git/commits", token,
        data={
            "message": f"data: auto-backup {action}",
            "tree": new_tree_sha,
            "parents": [base_sha],
        },
    )
    if not commit_result:
        print("[backup] Failed to create commit")
        return False
    new_commit_sha = commit_result["sha"]

    # Update ref
    branch = ref_data["ref"].split("/")[-1]  # "master" or "main"
    update_result = _api_request(
        "PATCH", f"/repos/{repo}/git/refs/heads/{branch}", token,
        data={"sha": new_commit_sha, "force": False},
    )
    if not update_result:
        print("[backup] Failed to update ref")
        return False

    print(f"[backup] GitHub API: committed {commit_result['sha'][:7]} to {repo}")
    return True


def backup_via_git(action: str = "data_change") -> bool:
    """Backup via local git add/commit/push. Works locally with SSH/HTTPS."""
    try:
        # Verify git is available
        check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=5,
        )
        if check.returncode != 0:
            return False

        # Stage data files
        subprocess.run(
            ["git", "add", str(DATA_DIR.relative_to(ROOT))],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )

        # Check for changes
        status = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )
        if not status.stdout.strip():
            return False

        # Commit
        subprocess.run(
            ["git", "commit", "-m", f"data: auto-backup {action}"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )

        # Push
        push_result = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30,
        )
        if push_result.returncode == 0:
            print(f"[backup] git: committed and pushed ({action})")
            return True
        else:
            print(f"[backup] git push failed (commit saved locally): {push_result.stderr[:200]}")
            return False
    except Exception:
        return False


def backup_on_change(action: str = "data_change") -> bool:
    """Persist athlete data to git. Tries GitHub API first, falls back to local git.

    Returns True if any backup succeeded.
    """
    # Primary: GitHub API (works on Streamlit Cloud)
    if backup_via_github_api(action):
        return True

    # Fallback: local git (works locally)
    if backup_via_git(action):
        return True

    return False
