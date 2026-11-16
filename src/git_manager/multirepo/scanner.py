"""
Multi-repository directory scanner for git-mgr.
Provides high-performance filesystem traversal to discover Git repositories
while aggressively pruning dependencies, virtual environments, caches, and build artifacts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Set

DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        ".git",
        ".cache",
        "dist",
        "build",
        "__pycache__",
        ".tox",
        ".idea",
        ".vscode",
        "site-packages",
    }
)


def _is_git_repository(candidate: Path) -> bool:
    """
    Check if a given path is a valid Git repository root.
    Handles both standard directories (.git/) and submodule/worktree references (.git file).
    """
    git_entry = candidate / ".git"
    if not git_entry.exists():
        return False
    if git_entry.is_dir():
        # Standard repo: contains HEAD or config
        return (git_entry / "HEAD").exists() or (git_entry / "config").exists()
    if git_entry.is_file():
        # Worktree or submodule gitlink file
        try:
            content = git_entry.read_text(encoding="utf-8", errors="replace")
            return "gitdir:" in content.lower()
        except Exception:
            return True
    return False


def discover_repositories(
    root_path: Path | str,
    max_depth: int = 4,
    exclude_dirs: set[str] | None = None,
) -> list[Path]:
    """
    Traverse a filesystem tree from root_path discovering Git repository roots.

    Prunes resource-intensive and non-project folders immediately to maximize
    traversal speed and prevent runaway recursion.

    Args:
        root_path: Filesystem path to begin recursive search from.
        max_depth: Maximum directory nesting depth to explore (default: 4).
        exclude_dirs: Optional additional directory names to prune during scan.

    Returns:
        Sorted list of resolved Path objects pointing to repository root directories.
    """
    root = Path(root_path).resolve()
    if not root.exists() or not root.is_dir():
        return []

    effective_excludes: Set[str] = set(DEFAULT_EXCLUDE_DIRS)
    if exclude_dirs:
        effective_excludes.update(exclude_dirs)

    discovered_repos: list[Path] = []

    # Check if root itself is a Git repository
    if _is_git_repository(root):
        discovered_repos.append(root)

    if max_depth <= 0:
        return discovered_repos

    for current_dir_str, dir_names, _files in os.walk(str(root), topdown=True):
        current_dir = Path(current_dir_str)

        try:
            rel_path = current_dir.relative_to(root)
            depth = len(rel_path.parts)
        except ValueError:
            depth = 0

        # In-place directory pruning to avoid traversing ignored subtrees
        dir_names[:] = [d for d in dir_names if d not in effective_excludes]

        # Stop descending further if at or above max_depth
        if depth >= max_depth:
            dir_names.clear()
            continue

        # Inspect immediate children for Git markers
        for child_name in dir_names:
            child_path = current_dir / child_name
            if _is_git_repository(child_path):
                resolved_child = child_path.resolve()
                if resolved_child not in discovered_repos:
                    discovered_repos.append(resolved_child)

    return sorted(discovered_repos, key=lambda p: str(p).lower())
