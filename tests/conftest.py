"""
Pytest configuration and disposable sandbox fixtures for git-manager tests.
Guarantees complete isolation by executing all tests within disposable temporary Git repositories.
Handles Windows read-only file locks on .git/objects during teardown.
"""

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Generator, Dict
import pytest


def safe_rmtree(path: Path | str) -> None:
    """
    Remove a directory tree reliably across platforms.
    Clears read-only attributes on Windows before retrying deletion.
    """
    target = Path(path)
    if not target.exists():
        return

    def _handle_readonly(func, file_path, exc_info):
        try:
            os.chmod(file_path, stat.S_IWRITE | stat.S_IWUSR)
            func(file_path)
        except Exception:
            pass

    shutil.rmtree(target, onerror=_handle_readonly)


def run_git(
    args: list[str], cwd: Path, env: Dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    """Helper to execute git commands reliably inside test repositories."""
    git_env = os.environ.copy()
    git_env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test User",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test User",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    if env:
        git_env.update(env)

    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env=git_env,
    )


@pytest.fixture
def temp_git_repo() -> Generator[Path, None, None]:
    """
    Fixture providing a clean, initialized Git repository with an initial commit.
    Tears down safely, clearing Windows read-only locks.
    """
    temp_dir = tempfile.mkdtemp(prefix="git_mgr_test_")
    repo_path = Path(temp_dir).resolve()

    try:
        # Initialize repository
        run_git(["init", "-b", "main"], cwd=repo_path)
        run_git(["config", "user.name", "Test User"], cwd=repo_path)
        run_git(["config", "user.email", "test@example.com"], cwd=repo_path)
        run_git(["config", "commit.gpgsign", "false"], cwd=repo_path)

        # Create initial commit
        readme = repo_path / "README.md"
        readme.write_text("# Test Repository\n\nInitialized for git-mgr tests.", encoding="utf-8")
        run_git(["add", "README.md"], cwd=repo_path)
        run_git(["commit", "-m", "chore: initial commit"], cwd=repo_path)

        yield repo_path

    finally:
        safe_rmtree(repo_path)


@pytest.fixture
def dirty_git_repo(temp_git_repo: Path) -> Path:
    """
    Fixture providing a Git repository with dirty working state:
    - 1 unstaged modified file
    - 1 staged new file
    - 1 untracked new file
    """
    # 1. Modify existing file (unstaged)
    readme = temp_git_repo / "README.md"
    readme.write_text("# Test Repository\n\nModified unstaged line.", encoding="utf-8")

    # 2. Add new staged file
    staged_file = temp_git_repo / "staged.txt"
    staged_file.write_text("Staged content", encoding="utf-8")
    run_git(["add", "staged.txt"], cwd=temp_git_repo)

    # 3. Add untracked file
    untracked_file = temp_git_repo / "untracked.log"
    untracked_file.write_text("Untracked log content", encoding="utf-8")

    return temp_git_repo


@pytest.fixture
def multi_repo_sandbox() -> Generator[Path, None, None]:
    """
    Fixture providing a root directory containing multiple isolated Git repositories
    for testing discovery, scanner, and bulk multi-repo actions:
    - repo-alpha (clean main)
    - repo-beta (dirty working tree)
    - repo-gamma (nested under /services, on a feature branch)
    """
    temp_dir = tempfile.mkdtemp(prefix="git_mgr_multisandbox_")
    sandbox_root = Path(temp_dir).resolve()

    try:
        # Repo Alpha: Clean
        alpha = sandbox_root / "repo-alpha"
        alpha.mkdir(parents=True)
        run_git(["init", "-b", "main"], cwd=alpha)
        run_git(["config", "user.name", "Test User"], cwd=alpha)
        run_git(["config", "user.email", "test@example.com"], cwd=alpha)
        run_git(["config", "commit.gpgsign", "false"], cwd=alpha)
        (alpha / "alpha.txt").write_text("Alpha content", encoding="utf-8")
        run_git(["add", "alpha.txt"], cwd=alpha)
        run_git(["commit", "-m", "feat: initial alpha commit"], cwd=alpha)

        # Repo Beta: Dirty
        beta = sandbox_root / "repo-beta"
        beta.mkdir(parents=True)
        run_git(["init", "-b", "main"], cwd=beta)
        run_git(["config", "user.name", "Test User"], cwd=beta)
        run_git(["config", "user.email", "test@example.com"], cwd=beta)
        run_git(["config", "commit.gpgsign", "false"], cwd=beta)
        (beta / "beta.txt").write_text("Beta content", encoding="utf-8")
        run_git(["add", "beta.txt"], cwd=beta)
        run_git(["commit", "-m", "feat: initial beta commit"], cwd=beta)
        # Make dirty
        (beta / "untracked_scratch.txt").write_text("scratch", encoding="utf-8")

        # Repo Gamma: Nested service on feature branch
        gamma = sandbox_root / "services" / "repo-gamma"
        gamma.mkdir(parents=True)
        run_git(["init", "-b", "main"], cwd=gamma)
        run_git(["config", "user.name", "Test User"], cwd=gamma)
        run_git(["config", "user.email", "test@example.com"], cwd=gamma)
        run_git(["config", "commit.gpgsign", "false"], cwd=gamma)
        (gamma / "service.py").write_text("print('service')", encoding="utf-8")
        run_git(["add", "service.py"], cwd=gamma)
        run_git(["commit", "-m", "feat: initial service"], cwd=gamma)
        run_git(["checkout", "-b", "feat/gamma-upgrade"], cwd=gamma)

        yield sandbox_root

    finally:
        safe_rmtree(sandbox_root)
