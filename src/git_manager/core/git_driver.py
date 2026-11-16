"""
Core Git engine and subprocess execution driver.
Provides typed, robust Git primitives for human developers and autonomous AI agents.
Handles porcelain v2 parsing, environment sanitization, and Windows-safe pathing.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from git_manager.core.models import FileStatus, GitCommandError, GitResult, RepoStatus


def _clean_path(raw_path: str) -> str:
    """Strip quotes and decode C-style escape sequences if needed."""
    path = raw_path.strip()
    if path.startswith('"') and path.endswith('"'):
        try:
            return bytes(path[1:-1], "utf-8").decode("unicode_escape")
        except Exception:
            return path[1:-1]
    return path


def check_git_version(min_version: tuple[int, int] = (2, 23)) -> tuple[int, int, int]:
    """
    Validate that Git is installed and meets the minimum required version.
    Returns (major, minor, patch).
    Raises RuntimeError if Git is not installed or below min_version.
    """
    if not shutil.which("git"):
        raise RuntimeError("Git executable not found on system PATH.")

    try:
        proc = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to execute git: {e}") from e

    if proc.returncode != 0:
        raise RuntimeError(f"Git invocation failed: {proc.stderr.strip()}")

    output = proc.stdout.strip()
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", output)
    if not match:
        raise RuntimeError(f"Could not parse Git version from output: '{output}'")

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3)) if match.group(3) else 0
    version_tuple = (major, minor, patch)

    if (major, minor) < min_version:
        raise RuntimeError(
            f"Git version {major}.{minor}.{patch} is unsupported. "
            f"Minimum required version is {min_version[0]}.{min_version[1]}."
        )

    return version_tuple


def get_git_version() -> tuple[int, int, int]:
    """Alias for check_git_version() returning (major, minor, patch)."""
    return check_git_version()


def find_repo_root(path: Path | str | None = None) -> Path | None:
    """
    Find repository root directory traversing upward from path.
    Returns resolved Path if inside a Git repository, or None otherwise.
    """
    target = Path(path).resolve() if path else Path.cwd().resolve()
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip()).resolve()
        return None
    except Exception:
        return None


class GitDriver:
    """
    High-level, typed Git interface executing subprocess commands deterministically.
    Safe for autonomous agent workflows without interactive tty deadlocks.
    """

    _command_listeners: list[Callable[[str], None]] = []

    @classmethod
    def add_command_listener(cls, listener: Callable[[str], None]) -> None:
        """Register a callback invoked whenever a git or gh command is executed."""
        if listener not in cls._command_listeners:
            cls._command_listeners.append(listener)

    @classmethod
    def remove_command_listener(cls, listener: Callable[[str], None]) -> None:
        """Unregister a previously registered command listener."""
        if listener in cls._command_listeners:
            cls._command_listeners.remove(listener)

    @classmethod
    def notify_command(cls, command_str: str) -> None:
        """Notify all registered command listeners without disrupting command execution."""
        for listener in list(cls._command_listeners):
            try:
                listener(command_str)
            except Exception:
                pass

    def __init__(self, repo_path: Path | str | None = None) -> None:
        """
        Initialize GitDriver pointing to a repository path.
        Defaults to current working directory if not specified.
        """
        self.repo_path: Path = (
            Path(repo_path).resolve() if repo_path is not None else Path.cwd().resolve()
        )

    def run(
        self,
        args: list[str],
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        timeout: int = 30,
    ) -> GitResult:
        """
        Execute a git subprocess command safely.

        Args:
            args: Subcommand and flags (e.g. ['status', '--porcelain=v2'])
            cwd: Working directory override (defaults to self.repo_path)
            env: Extra environment variables to inject
            check: Whether to raise GitCommandError on non-zero exit code
            timeout: Subprocess execution timeout in seconds

        Returns:
            GitResult containing stdout, stderr, exit_code, success flag, and command
        """
        target_cwd = Path(cwd).resolve() if cwd else self.repo_path
        cmd_env = os.environ.copy()
        # Headless safety: Never prompt for credentials or open pagers
        cmd_env["GIT_TERMINAL_PROMPT"] = "0"
        cmd_env["GIT_PAGER"] = "cat"
        if env:
            cmd_env.update(env)

        full_command = ["git"] + list(args)
        self.notify_command(" ".join(full_command))

        try:
            proc = subprocess.run(
                full_command,
                cwd=str(target_cwd),
                env=cmd_env,
                capture_output=True,
                timeout=timeout,
            )
            stdout = proc.stdout.decode("utf-8", errors="replace")
            stderr = proc.stderr.decode("utf-8", errors="replace")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            raise GitCommandError(
                command=full_command,
                exit_code=-1,
                stderr=f"Git command timed out after {timeout} seconds",
                stdout="",
            )
        except FileNotFoundError:
            raise GitCommandError(
                command=full_command,
                exit_code=127,
                stderr="Git executable not found on system PATH",
                stdout="",
            )

        result = GitResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            success=(exit_code == 0),
            command=full_command,
        )

        if check and not result.success:
            result.check()

        return result

    def get_repo_root(self) -> Path:
        """
        Resolves top-level repo directory via 'git rev-parse --show-toplevel'.
        Raises GitCommandError if not in a repository.
        """
        result = self.run(["rev-parse", "--show-toplevel"], check=True)
        return Path(result.stdout.strip()).resolve()

    def find_repo_root(self) -> Path | None:
        """Find repository root directory or None if not inside a repository."""
        return find_repo_root(self.repo_path)

    def check_git_version(self, min_version: tuple[int, int] = (2, 23)) -> tuple[int, int, int]:
        """Validate Git installation meets minimum version."""
        return check_git_version(min_version)

    def get_git_version(self) -> tuple[int, int, int]:
        """Return Git version tuple (major, minor, patch)."""
        return check_git_version()

    def is_bare(self) -> bool:
        """Check if repository is a bare repository."""
        result = self.run(["rev-parse", "--is-bare-repository"], check=False)
        return result.stdout.strip().lower() == "true"

    def get_current_branch(self) -> str:
        """
        Get the current branch name.
        Returns '(detached)' or commit SHA if in detached HEAD state.
        """
        result = self.run(["branch", "--show-current"], check=False)
        branch = result.stdout.strip()
        if branch:
            return branch
        # Fallback for detached HEAD or initial repo
        rev = self.run(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
        branch = rev.stdout.strip()
        return branch if branch else "HEAD"

    def get_status(self) -> RepoStatus:
        """
        Parse 'git status --porcelain=v2 --branch -uall' into structured RepoStatus.
        Accurately parses staged, unstaged, untracked, branch upstream, and ahead/behind counts.
        """
        result = self.run(["status", "--porcelain=v2", "--branch", "-uall"], check=True)
        stashes = self.stash_list()

        commit_sha: str | None = None
        branch_name: str = "HEAD"
        upstream: str | None = None
        ahead_count: int = 0
        behind_count: int = 0

        staged_files: list[FileStatus] = []
        unstaged_files: list[FileStatus] = []
        untracked_files: list[FileStatus] = []

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("# branch.oid "):
                oid = line[len("# branch.oid ") :].strip()
                commit_sha = None if oid == "(initial)" else oid
            elif line.startswith("# branch.head "):
                branch_name = line[len("# branch.head ") :].strip()
            elif line.startswith("# branch.upstream "):
                upstream = line[len("# branch.upstream ") :].strip()
            elif line.startswith("# branch.ab "):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        ahead_count = int(parts[2].lstrip("+"))
                        behind_count = int(parts[3].lstrip("-"))
                    except ValueError:
                        pass
            elif line.startswith("1 "):
                # Ordinary changed entry
                tokens = line.split(" ", 8)
                if len(tokens) >= 9:
                    xy = tokens[1]
                    file_path = _clean_path(tokens[8])
                    x, y = xy[0], xy[1]
                    s_status = x if x != "." else None
                    u_status = y if y != "." else None
                    status_obj = FileStatus(
                        path=file_path,
                        staged_status=s_status,
                        unstaged_status=u_status,
                        is_untracked=False,
                    )
                    if s_status is not None:
                        staged_files.append(status_obj)
                    if u_status is not None:
                        unstaged_files.append(status_obj)
            elif line.startswith("2 "):
                # Renamed or copied entry
                tokens = line.split(" ", 9)
                if len(tokens) >= 10:
                    xy = tokens[1]
                    paths_part = tokens[9]
                    file_path = _clean_path(paths_part.split("\t", 1)[0])
                    x, y = xy[0], xy[1]
                    s_status = x if x != "." else None
                    u_status = y if y != "." else None
                    status_obj = FileStatus(
                        path=file_path,
                        staged_status=s_status,
                        unstaged_status=u_status,
                        is_untracked=False,
                    )
                    if s_status is not None:
                        staged_files.append(status_obj)
                    if u_status is not None:
                        unstaged_files.append(status_obj)
            elif line.startswith("u "):
                # Unmerged / conflicted entry
                tokens = line.split(" ", 10)
                if len(tokens) >= 11:
                    xy = tokens[1]
                    file_path = _clean_path(tokens[10])
                    status_obj = FileStatus(
                        path=file_path,
                        staged_status="U" if xy[0] != "." else None,
                        unstaged_status="U" if xy[1] != "." else "U",
                        is_untracked=False,
                    )
                    unstaged_files.append(status_obj)
            elif line.startswith("? "):
                # Untracked entry
                file_path = _clean_path(line[2:])
                status_obj = FileStatus(
                    path=file_path,
                    staged_status=None,
                    unstaged_status="?",
                    is_untracked=True,
                )
                untracked_files.append(status_obj)

        is_clean = len(staged_files) == 0 and len(unstaged_files) == 0 and len(untracked_files) == 0

        return RepoStatus(
            repo_path=str(self.repo_path),
            branch_name=branch_name,
            commit_sha=commit_sha,
            upstream=upstream,
            ahead_count=ahead_count,
            behind_count=behind_count,
            staged_files=staged_files,
            unstaged_files=unstaged_files,
            untracked_files=untracked_files,
            is_clean=is_clean,
            stash_count=len(stashes),
        )

    def stage(self, paths: list[str] | None = None) -> GitResult:
        """Stage changes for commit. If paths is None or empty, stages all changes ('git add -A')."""
        if not paths:
            return self.run(["add", "-A"])
        return self.run(["add", "--"] + list(paths))

    def stage_files(self, paths: list[str] | None = None) -> GitResult:
        """Alias for stage()."""
        return self.stage(paths)

    def unstage(self, paths: list[str] | None = None) -> GitResult:
        """Unstage staged changes using 'git restore --staged'."""
        if not paths:
            return self.run(["restore", "--staged", "."])
        return self.run(["restore", "--staged", "--"] + list(paths))

    def unstage_files(self, paths: list[str] | None = None) -> GitResult:
        """Alias for unstage()."""
        return self.unstage(paths)

    def commit(self, message: str, allow_empty: bool = False) -> str:
        """
        Create a commit with the specified message.
        Returns the new commit full SHA.
        """
        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        self.run(args, check=True)
        res = self.run(["rev-parse", "HEAD"], check=True)
        return res.stdout.strip()

    def create_commit(self, message: str, allow_empty: bool = False) -> str:
        """Alias for commit()."""
        return self.commit(message, allow_empty=allow_empty)

    def switch(self, branch: str, create: bool = False) -> GitResult:
        """
        Switch branches using modern 'git switch'.
        If create is True, uses 'git switch -c <branch>'.
        """
        if create:
            return self.run(["switch", "-c", branch])
        return self.run(["switch", branch])

    def switch_branch(self, branch: str, create: bool = False) -> GitResult:
        """Alias for switch()."""
        return self.switch(branch, create=create)

    def restore(self, paths: list[str], staged: bool = False) -> GitResult:
        """Restore specified working tree files or index."""
        if not paths:
            return GitResult(
                stdout="", stderr="", exit_code=0, success=True, command=["git", "restore"]
            )
        if staged:
            return self.run(["restore", "--staged", "--"] + list(paths))
        return self.run(["restore", "--"] + list(paths))

    def stash_save(self, message: str | None = None, include_untracked: bool = True) -> bool:
        """
        Stash working tree changes.
        Defaults to include_untracked=True (-u) to protect scratch and agent-generated files.
        Returns True if changes were stashed, False if working tree was clean.
        """
        args = ["stash", "push"]
        if include_untracked:
            args.append("-u")
        if message:
            args.extend(["-m", message])
        result = self.run(args, check=False)
        if not result.success:
            raise GitCommandError(
                command=result.command,
                exit_code=result.exit_code,
                stderr=result.stderr,
                stdout=result.stdout,
            )
        output = result.stdout.strip() + " " + result.stderr.strip()
        if "No local changes to save" in output:
            return False
        return True

    def stash_pop(self, index: int = 0) -> bool:
        """
        Pop a stashed state from stash@{index}.
        Returns True on success, or False if no stash exists at that index.
        Raises GitCommandError on merge conflict.
        """
        target = f"stash@{{{index}}}"
        result = self.run(["stash", "pop", target], check=False)
        if result.success:
            return True
        output = result.stderr.strip() + " " + result.stdout.strip()
        if "No stash entries found" in output or "is not a valid reference" in output:
            return False
        raise GitCommandError(
            command=result.command,
            exit_code=result.exit_code,
            stderr=result.stderr,
            stdout=result.stdout,
        )

    def stash_list(self) -> list[str]:
        """Return list of stash entries from 'git stash list'."""
        result = self.run(["stash", "list"], check=False)
        if not result.stdout.strip():
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def pull_rebase(self) -> GitResult:
        """Pull upstream changes using 'git pull --rebase'."""
        return self.run(["pull", "--rebase"])

    def get_log(self, max_count: int = 10) -> list[dict[str, str]]:
        """
        Retrieve recent commits as a list of dictionaries with commit metadata.
        Returns empty list if branch has no commits yet.
        """
        result = self.run(
            ["log", f"-n{max_count}", "--format=%H|%h|%an|%ae|%aI|%s"],
            check=False,
        )
        if not result.success or not result.stdout.strip():
            return []
        entries: list[dict[str, str]] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 5)
            if len(parts) == 6:
                entries.append(
                    {
                        "hash": parts[0],
                        "short_hash": parts[1],
                        "author_name": parts[2],
                        "author_email": parts[3],
                        "timestamp": parts[4],
                        "subject": parts[5],
                    }
                )
        return entries
