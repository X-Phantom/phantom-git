"""
Linear history and rebase automation engine for git-mgr.
Ensures trunk-based, non-merge-bubble linear history, automated upstream synchronization
via 'git pull --rebase', and formatted linear graph inspection.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from git_manager.core.git_driver import GitDriver
from git_manager.core.models import GitResult

TYPE_EXTRACTION_REGEX = re.compile(
    r"^(?P<type>feat|fix|chore|docs|refactor|ci|test|perf|style|build)(?:\([^)]+\))?!?:",
    re.IGNORECASE,
)


def ensure_rebase_configured(
    driver: GitDriver,
    global_config: bool = False,
) -> GitResult:
    """
    Configure Git to enforce rebase by default on pull operations.

    Args:
        driver: GitDriver instance
        global_config: If True, applies '--global' flag, otherwise applies to repository

    Returns:
        GitResult of the configuration command
    """
    args = ["config"]
    if global_config:
        args.append("--global")
    args.extend(["pull.rebase", "true"])
    return driver.run(args, check=True)


def get_linear_graph(
    driver: GitDriver,
    max_count: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve condensed linear commit history with commit hash, branch/tag decorations,
    relative date, author, subject, and Conventional Commit type.

    Args:
        driver: GitDriver instance
        max_count: Maximum number of commits to retrieve

    Returns:
        list[dict[str, Any]] with commit metadata
    """
    res = driver.run(
        ["log", f"-n{max_count}", "--format=%H|%h|%d|%ar|%an|%s"],
        check=False,
    )
    if not res.success or not res.stdout.strip():
        return []

    commits: list[dict[str, Any]] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("|", 5)
        if len(parts) < 6:
            continue

        full_hash = parts[0].strip()
        short_hash = parts[1].strip()
        decorations_raw = parts[2].strip()
        relative_date = parts[3].strip()
        author = parts[4].strip()
        subject = parts[5].strip()

        # Clean decorations: strip leading/trailing whitespace and parentheses
        clean_decorations = decorations_raw.strip(" ()")

        # Extract Conventional Commit type
        match = TYPE_EXTRACTION_REGEX.match(subject)
        commit_type = match.group("type").lower() if match else "other"

        commits.append(
            {
                "hash": full_hash,
                "short_hash": short_hash,
                "decorations": clean_decorations,
                "relative_date": relative_date,
                "author": author,
                "subject": subject,
                "commit_type": commit_type,
            }
        )

    return commits


def sync_linear_rebase(
    repo_path: Path | str | None = None,
    remote: str = "origin",
    branch: str | None = None,
) -> GitResult:
    """
    Safely pull upstream changes using 'git pull --rebase'.
    Guarantees dirty tree protection via auto-stashing.

    Args:
        repo_path: Path to repository
        remote: Remote name (default: 'origin')
        branch: Upstream branch name (defaults to current branch)

    Returns:
        GitResult of the pull/rebase operation
    """
    driver = GitDriver(repo_path)
    status = driver.get_status()

    stash_saved = False
    if not status.is_clean:
        stash_saved = driver.stash_save(
            message="git-mgr auto-stash before sync_linear_rebase",
            include_untracked=True,
        )

    target_branch = branch or (
        status.branch_name if status.branch_name != "HEAD" else driver.get_current_branch()
    )

    # Check configured remotes
    remotes_res = driver.run(["remote"], check=False)
    available_remotes = [r.strip() for r in remotes_res.stdout.splitlines() if r.strip()]

    try:
        if remote in available_remotes:
            # Fetch upstream
            driver.run(["fetch", remote], check=False)
            cmd = ["pull", "--rebase", remote, target_branch]
        else:
            cmd = ["pull", "--rebase"]

        result = driver.run(cmd, check=True)
    finally:
        if stash_saved:
            driver.stash_pop()

    return result


def get_linear_log(
    repo_path: Path | str | None = None,
    max_count: int = 15,
) -> list[dict[str, Any]]:
    """
    Convenience function matching TASK-P4-06:
    Returns condensed oneline linear graph for repo_path.
    """
    driver = GitDriver(repo_path)
    return get_linear_graph(driver, max_count=max_count)
