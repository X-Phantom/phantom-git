"""
Branch hygiene validator, formatting engine, and safe switcher for git-mgr.
Enforces branch prefix standards (feat/, fix/, chore/, etc.), kebab-case slugs,
and atomic dirty tree protection during branch transitions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from git_manager.core.git_driver import GitDriver
from git_manager.core.models import GitResult
from git_manager.core.safety_net import SafetyNet

ALLOWED_PREFIX_NAMES: tuple[str, ...] = (
    "feat",
    "fix",
    "chore",
    "docs",
    "refactor",
    "ci",
    "test",
    "perf",
)

ALLOWED_BRANCH_PREFIXES: tuple[str, ...] = tuple(f"{p}/" for p in ALLOWED_PREFIX_NAMES)

# Regex matching valid lowercase slug after the prefix: alphanumeric, hyphens, underscores, dots
BRANCH_SLUG_REGEX = re.compile(r"^[a-z0-9]+([a-z0-9._-]*[a-z0-9])?$")


def validate_branch_name(name: str) -> tuple[bool, str | None]:
    """
    Validate that a branch name adheres to hygiene standards.
    Requirements:
    1. Must start with an allowed prefix: feat/, fix/, chore/, docs/, refactor/, ci/, test/, perf/.
    2. Must be strictly lowercase.
    3. The slug after the prefix must be a valid kebab-case slug (alphanumeric, hyphens, dots, underscores).
    4. Must not contain Git-illegal reference characters or spaces.

    Returns:
        tuple[bool, str | None]: (True, None) if valid, or (False, error_reason) if invalid.
    """
    if not isinstance(name, str) or not name.strip():
        return False, "Branch name cannot be empty."

    name = name.strip()

    if " " in name:
        return False, "Branch name cannot contain spaces."

    if any(char in name for char in ("~", "^", ":", "?", "*", "[", "\\", "@{")):
        return False, "Branch name contains illegal Git reference characters."

    if ".." in name or "//" in name:
        return False, "Branch name cannot contain consecutive dots ('..') or slashes ('//')."

    if name.endswith("/") or name.startswith("/"):
        return False, "Branch name cannot start or end with a slash."

    if name.endswith(".lock"):
        return False, "Branch name cannot end with '.lock'."

    if "/" not in name:
        allowed_str = ", ".join(ALLOWED_BRANCH_PREFIXES)
        return (
            False,
            f"Branch '{name}' lacks a required prefix. Must start with one of: {allowed_str}",
        )

    prefix, slug = name.split("/", 1)

    if prefix != prefix.lower():
        return False, f"Branch prefix '{prefix}' must be strictly lowercase."

    if prefix not in ALLOWED_PREFIX_NAMES:
        allowed_str = ", ".join(ALLOWED_BRANCH_PREFIXES)
        return (
            False,
            f"Invalid branch prefix '{prefix}/'. Allowed prefixes are: {allowed_str}",
        )

    if not slug:
        return False, "Branch description slug cannot be empty after the prefix."

    if slug != slug.lower():
        return False, "Branch name must be strictly lowercase."

    if not BRANCH_SLUG_REGEX.match(slug):
        return (
            False,
            f"Branch description '{slug}' must be a lowercase slug containing only "
            "alphanumeric characters, hyphens, underscores, or dots.",
        )

    return True, None


def format_branch_name(branch_type: str, description: str) -> str:
    """
    Normalize a branch type and description into standard '<type>/<kebab-case-desc>'.

    Args:
        branch_type: The prefix type (e.g. 'feat', 'feat/', 'fix')
        description: Freeform description (e.g. 'Add User Authentication!')

    Returns:
        Formatted branch name (e.g. 'feat/add-user-authentication')
    """
    clean_type = branch_type.strip().strip("/").lower()
    clean_desc = description.strip().lower()

    # Replace consecutive dots and illegal git characters
    clean_desc = re.sub(r"\.{2,}", "-", clean_desc)
    clean_desc = re.sub(r"[^a-z0-9._-]+", "-", clean_desc)
    # Collapse multiple consecutive hyphens
    clean_desc = re.sub(r"-+", "-", clean_desc)
    # Strip leading and trailing hyphens, dots, or underscores
    clean_desc = clean_desc.strip("-._")

    if not clean_desc:
        clean_desc = "unnamed"

    return f"{clean_type}/{clean_desc}"


class BranchManager:
    """
    Branch operations manager with branch hygiene enforcement,
    dirty tree protection, and safe checkout/creation.
    """

    def __init__(
        self,
        driver: GitDriver | Path | str | None = None,
        safety_net: SafetyNet | None = None,
    ) -> None:
        """
        Initialize BranchManager.
        Accepts GitDriver or path, and an optional SafetyNet instance.
        """
        if isinstance(driver, GitDriver):
            self.driver = driver
        else:
            self.driver = GitDriver(driver)

        self.safety_net = safety_net or SafetyNet(self.driver)

    def list_branches(self) -> list[dict[str, Any]]:
        """
        List all local and remote branches with current status, upstream, and tracking info.

        Returns:
            list[dict[str, Any]] containing:
                - name: short branch name (e.g. 'feat/auth' or 'origin/main')
                - full_ref: git refname (e.g. 'refs/heads/feat/auth')
                - is_current: bool whether HEAD points to this branch
                - is_remote: bool whether branch is remote
                - upstream: upstream short name or None
                - tracking_status: track string (e.g. '[ahead 1]') or ''
                - commit_sha: commit short sha
                - subject: commit subject line
        """
        format_spec = "%(HEAD)|%(refname)|%(refname:short)|%(upstream:short)|%(upstream:track)|%(objectname:short)|%(contents:subject)"
        res = self.driver.run(["branch", "-a", f"--format={format_spec}"], check=False)
        if not res.success or not res.stdout.strip():
            return []

        branches: list[dict[str, Any]] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("|", 6)
            if len(parts) < 6:
                continue

            is_current = parts[0].strip() == "*"
            full_ref = parts[1].strip()
            short_name = parts[2].strip()
            upstream = parts[3].strip() or None
            track = parts[4].strip()
            commit_sha = parts[5].strip()
            subject = parts[6].strip() if len(parts) > 6 else ""

            # Filter out symbolic HEAD references (e.g. origin/HEAD -> origin/main)
            if short_name.endswith("/HEAD") or full_ref.endswith("/HEAD"):
                continue

            is_remote = full_ref.startswith("refs/remotes/")

            branches.append(
                {
                    "name": short_name,
                    "full_ref": full_ref,
                    "is_current": is_current,
                    "is_remote": is_remote,
                    "upstream": upstream,
                    "tracking_status": track,
                    "commit_sha": commit_sha,
                    "subject": subject,
                }
            )

        return branches

    def create_and_switch(
        self,
        branch_name: str,
        auto_stash: bool = True,
        force: bool = False,
    ) -> GitResult:
        """
        Create a new branch and switch to it with hygiene validation and dirty tree protection.

        Args:
            branch_name: Target branch name (e.g. 'feat/user-auth')
            auto_stash: If True, stashes uncommitted changes before switching and pops them after
            force: If True, bypasses branch name hygiene validation

        Returns:
            GitResult of the checkout/switch command

        Raises:
            ValueError: If branch_name fails hygiene validation and force is False
            GitCommandError: If branch creation fails
        """
        if not force:
            is_valid, reason = validate_branch_name(branch_name)
            if not is_valid:
                raise ValueError(f"Invalid branch name '{branch_name}': {reason}")

        status = self.driver.get_status()
        stash_saved = False

        if auto_stash and not status.is_clean:
            stash_msg = f"git-mgr auto-stash before create_and_switch to {branch_name}"
            stash_saved = self.driver.stash_save(message=stash_msg, include_untracked=True)

        try:
            result = self.driver.run(["switch", "-c", branch_name], check=True)
        finally:
            if stash_saved:
                self.driver.stash_pop()

        return result

    def switch(
        self,
        branch_name: str,
        auto_stash: bool = True,
    ) -> GitResult:
        """
        Switch to an existing branch safely with dirty tree protection.

        Args:
            branch_name: Name of existing local or remote tracking branch
            auto_stash: If True, stashes uncommitted changes before switching and pops them after

        Returns:
            GitResult of the switch command

        Raises:
            GitCommandError: If switch fails
        """
        status = self.driver.get_status()
        stash_saved = False

        if auto_stash and not status.is_clean:
            stash_msg = f"git-mgr auto-stash before switch to {branch_name}"
            stash_saved = self.driver.stash_save(message=stash_msg, include_untracked=True)

        try:
            result = self.driver.run(["switch", branch_name], check=True)
        finally:
            if stash_saved:
                self.driver.stash_pop()

        return result


def switch_or_create(
    repo_path: Path | str | None = None,
    branch_name: str = "",
    auto_stash: bool = True,
    force: bool = False,
) -> GitResult:
    """
    Convenience function matching TASK-P4-02:
    Switches to branch if it exists, or validates and creates it if it does not.
    """
    mgr = BranchManager(repo_path)
    branches = mgr.list_branches()
    existing_local = {b["name"] for b in branches if not b.get("is_remote")}
    existing_remote = {b["name"] for b in branches if b.get("is_remote")}
    remote_short_matches = {
        b["name"].split("/", 1)[-1] for b in branches if b.get("is_remote") and "/" in b["name"]
    }

    if (
        branch_name in existing_local
        or branch_name in existing_remote
        or branch_name in remote_short_matches
    ):
        return mgr.switch(branch_name, auto_stash=auto_stash)

    return mgr.create_and_switch(branch_name, auto_stash=auto_stash, force=force)
