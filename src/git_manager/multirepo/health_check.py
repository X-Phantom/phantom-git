"""
Multi-repository health checking and auditing engine for git-mgr.
Inspects working tree status, upstream synchronization, divergence, and uncommitted
changes across single or multiple repositories with actionable recommendations.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Sequence

from git_manager.core.git_driver import GitDriver
from git_manager.core.models import (
    GitCommandError,
    RepoHealth,
    RepoHealthStatus,
)


def audit_repository(repo_path: Path | str) -> RepoHealth:
    """
    Audit an individual Git repository and produce a structured health assessment.

    Inspects branch tracking, ahead/behind counts, working tree cleanliness,
    untracked files, and stashes, then assigns a definitive RepoHealthStatus
    and human-readable recommendation.

    Args:
        repo_path: Path to the target Git repository root.

    Returns:
        RepoHealth object containing diagnostic metrics and recommendations.
    """
    target_path = Path(repo_path).resolve()
    repo_name = target_path.name
    driver = GitDriver(target_path)

    try:
        status = driver.get_status()
    except GitCommandError as exc:
        return RepoHealth(
            path=str(target_path),
            name=repo_name,
            current_branch="unknown",
            is_clean=False,
            modified_count=0,
            untracked_count=0,
            stash_count=0,
            ahead_count=0,
            behind_count=0,
            upstream_name=None,
            has_remote=False,
            status=RepoHealthStatus.DIRTY,
            recommendation=f"Failed to inspect repository: {exc.stderr or str(exc)}",
        )

    # Detect remote configuration
    remotes_res = driver.run(["remote"], check=False)
    has_remote = bool(remotes_res.stdout.strip())

    # Detect detached HEAD state
    is_detached = status.branch_name in ("(detached)", "HEAD")
    current_branch = "(detached)" if is_detached else status.branch_name

    modified_count = len(status.staged_files) + len(status.unstaged_files)
    untracked_count = len(status.untracked_files)
    stash_count = status.stash_count
    ahead_count = status.ahead_count
    behind_count = status.behind_count
    upstream_name = status.upstream
    is_clean = status.is_clean

    # Classify health status and generate recommendation
    if is_detached:
        health_status = RepoHealthStatus.DETACHED
        recommendation = "Detached HEAD state; checkout a branch before making commits."
    elif not is_clean:
        health_status = RepoHealthStatus.DIRTY
        recommendation = "Uncommitted work present; stash or commit changes."
    elif ahead_count > 0 and behind_count > 0:
        health_status = RepoHealthStatus.DIVERGED
        recommendation = (
            f"Branch has diverged from upstream (+{ahead_count}/-{behind_count}); "
            f"rebase or merge upstream changes."
        )
    elif ahead_count > 0:
        health_status = RepoHealthStatus.AHEAD
        recommendation = f"Local branch is ahead by {ahead_count} commit(s); push changes."
    elif behind_count > 0:
        health_status = RepoHealthStatus.BEHIND
        recommendation = (
            f"Local branch is behind by {behind_count} commit(s); run git-mgr sync to pull updates."
        )
    elif status.commit_sha is None:
        health_status = RepoHealthStatus.CLEAN
        recommendation = "Repository has no commits yet; make an initial commit."
    else:
        health_status = RepoHealthStatus.CLEAN
        recommendation = "Repository is healthy and up to date."

    return RepoHealth(
        path=str(target_path),
        name=repo_name,
        current_branch=current_branch,
        is_clean=is_clean,
        modified_count=modified_count,
        untracked_count=untracked_count,
        stash_count=stash_count,
        ahead_count=ahead_count,
        behind_count=behind_count,
        upstream_name=upstream_name,
        has_remote=has_remote,
        status=health_status,
        recommendation=recommendation,
    )


# Alias matching TASK-P6-02 specification
audit_repository_health = audit_repository


def audit_repositories(
    repo_paths: Sequence[Path | str],
    max_workers: int = 4,
) -> list[RepoHealth]:
    """
    Audit health across multiple Git repositories concurrently.

    Args:
        repo_paths: Sequence of repository root paths to audit.
        max_workers: Maximum concurrent worker threads (default: 4).

    Returns:
        List of RepoHealth objects preserving the input order.
    """
    paths = [Path(p).resolve() for p in repo_paths]
    if not paths:
        return []

    if len(paths) == 1:
        return [audit_repository(paths[0])]

    workers = min(max_workers, len(paths))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(audit_repository, paths))
