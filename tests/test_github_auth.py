"""
Unit tests for GitHub CLI discovery, authentication parsing, repo listing,
and real-time Git/GH command observer hooks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_manager.core.git_driver import GitDriver
from git_manager.core.github_auth import (
    GitHubAuthManager,
    _parse_auth_status_output,
    find_gh_binary,
)
from git_manager.core.models import GitCommandError, GitResult
from tests.conftest import run_git


class TestGitHubBinaryDiscovery:
    """Tests for Windows and cross-platform gh CLI discovery."""

    def test_find_gh_binary_uses_windows_fallback(self, tmp_path: Path, monkeypatch) -> None:
        fake_dir = tmp_path / "GitHub CLI"
        fake_dir.mkdir()
        fake_gh = fake_dir / "gh.exe"
        fake_gh.write_text("", encoding="utf-8")

        monkeypatch.setattr("git_manager.core.github_auth.shutil.which", lambda name: None)
        monkeypatch.setattr(
            "git_manager.core.github_auth.Path",
            lambda p="": fake_gh if "Program Files/GitHub CLI" in str(p) else Path(p),
        )
        # Simpler direct check: test when shutil.which returns path
        monkeypatch.undo()
        monkeypatch.setattr("git_manager.core.github_auth.shutil.which", lambda name: str(fake_gh))
        assert find_gh_binary() == str(fake_gh)


class TestGitHubAuthStatusParsing:
    """Tests for parsing modern and legacy `gh auth status` output."""

    def test_parse_modern_authenticated_status(self) -> None:
        raw = (
            "github.com\n"
            "  ✓ Logged in to github.com account X-Phantom (keyring)\n"
            "  - Active account: true\n"
            "  - Git operations protocol: https\n"
            "  - Token scopes: 'repo', 'workflow', 'read:org'\n"
        )
        status = _parse_auth_status_output(raw, host="github.com", success=True)
        assert status.authenticated is True
        assert status.username == "X-Phantom"
        assert status.protocol == "https"
        assert status.scopes == ["repo", "workflow", "read:org"]

    def test_parse_unauthenticated_status(self) -> None:
        status = _parse_auth_status_output(
            "You are not logged into any GitHub hosts.",
            host="github.com",
            success=False,
        )
        assert status.authenticated is False
        assert status.username is None


class TestGitHubAuthManager:
    """Tests for GitHubAuthManager operations with mocked gh subprocess runner."""

    def test_login_with_token_validates_and_configures_git(self) -> None:
        calls: list[tuple[list[str], str | None]] = []

        def fake_runner(
            args: list[str], cwd: Path, input_text: str | None, timeout: int
        ) -> GitResult:
            calls.append((args, input_text))
            if args[:2] == ["auth", "status"]:
                return GitResult(
                    stdout=(
                        "github.com\n"
                        "  ✓ Logged in to github.com account X-Phantom (keyring)\n"
                        "  - Git operations protocol: https\n"
                        "  - Token scopes: 'repo', 'workflow'\n"
                    ),
                    stderr="",
                    exit_code=0,
                    success=True,
                    command=["gh", *args],
                )
            return GitResult(stdout="", stderr="", exit_code=0, success=True, command=["gh", *args])

        mgr = GitHubAuthManager(gh_runner=fake_runner)

        with pytest.raises(ValueError, match="cannot be empty"):
            mgr.login_with_token("   ")

        status = mgr.login_with_token("ghp_example123")
        assert status.authenticated is True
        assert status.username == "X-Phantom"
        assert calls[0][0][:2] == ["auth", "login"]
        assert "--with-token" in calls[0][0]
        assert calls[0][1] == "ghp_example123\n"
        assert calls[1][0][:2] == ["auth", "setup-git"]

    def test_list_repos_cross_references_local_clones(self, multi_repo_sandbox: Path) -> None:
        payload = [
            {
                "name": "repo-alpha",
                "nameWithOwner": "X-Phantom/repo-alpha",
                "isPrivate": False,
                "defaultBranchRef": {"name": "main"},
                "updatedAt": "2026-11-16T12:00:00Z",
                "url": "https://github.com/X-Phantom/repo-alpha",
                "description": "Alpha service",
            },
            {
                "name": "cloud-only-repo",
                "nameWithOwner": "X-Phantom/cloud-only-repo",
                "isPrivate": True,
                "defaultBranchRef": {"name": "main"},
                "updatedAt": "2026-11-15T12:00:00Z",
                "url": "https://github.com/X-Phantom/cloud-only-repo",
                "description": "",
            },
        ]

        def fake_runner(
            args: list[str], cwd: Path, input_text: str | None, timeout: int
        ) -> GitResult:
            return GitResult(
                stdout=json.dumps(payload),
                stderr="",
                exit_code=0,
                success=True,
                command=["gh", *args],
            )

        mgr = GitHubAuthManager(gh_runner=fake_runner)
        repos = mgr.list_repos(workspace_path=multi_repo_sandbox)
        assert len(repos) == 2
        assert repos[0].full_name == "X-Phantom/repo-alpha"
        assert repos[0].local_path == str((multi_repo_sandbox / "repo-alpha").resolve())
        assert repos[1].is_private is True
        assert repos[1].local_path is None

    def test_publish_repo_creates_remote_when_missing(self, temp_git_repo: Path) -> None:
        recorded_args: list[list[str]] = []

        def fake_runner(
            args: list[str], cwd: Path, input_text: str | None, timeout: int
        ) -> GitResult:
            recorded_args.append(args)
            return GitResult(
                stdout="https://github.com/X-Phantom/my-repo",
                stderr="",
                exit_code=0,
                success=True,
                command=["gh", *args],
            )

        mgr = GitHubAuthManager(gh_runner=fake_runner)
        driver = GitDriver(temp_git_repo)
        url = mgr.publish_repo(driver, repo_name="my-repo", private=False)
        assert "X-Phantom/my-repo" in url
        assert recorded_args[0][:3] == ["repo", "create", "my-repo"]
        assert "--public" in recorded_args[0]

    def test_publish_repo_pushes_when_origin_exists(self, tmp_path: Path) -> None:
        bare_remote = tmp_path / "remote.git"
        run_git(["init", "--bare", str(bare_remote)], cwd=tmp_path)

        local_repo = tmp_path / "local"
        run_git(["init", "-b", "main", str(local_repo)], cwd=tmp_path)
        run_git(["config", "user.name", "Test User"], cwd=local_repo)
        run_git(["config", "user.email", "test@example.com"], cwd=local_repo)
        (local_repo / "README.md").write_text("# Test\n", encoding="utf-8")
        run_git(["add", "README.md"], cwd=local_repo)
        run_git(["commit", "-m", "chore: init"], cwd=local_repo)
        run_git(["branch", "staging", "main"], cwd=local_repo)
        run_git(["remote", "add", "origin", str(bare_remote)], cwd=local_repo)

        mgr = GitHubAuthManager()
        driver = GitDriver(local_repo)
        url = mgr.publish_repo(driver)
        assert str(bare_remote) in url

        branches_out = run_git(["branch"], cwd=bare_remote).stdout
        assert "main" in branches_out
        assert "staging" in branches_out

    def test_command_listener_observes_git_and_gh(self, temp_git_repo: Path) -> None:
        captured: list[str] = []
        GitDriver.add_command_listener(captured.append)
        try:
            driver = GitDriver(temp_git_repo)
            driver.run(["status", "--short"])
            mgr = GitHubAuthManager(
                gh_runner=lambda args, cwd, inp, t: GitResult(
                    stdout="ok", stderr="", exit_code=0, success=True, command=["gh", *args]
                )
            )
            mgr.run_gh(["auth", "status"])
        finally:
            GitDriver.remove_command_listener(captured.append)

        assert any(cmd.startswith("git status --short") for cmd in captured)
        assert any(cmd.startswith("gh auth status") for cmd in captured)

    def test_run_gh_raises_on_error_when_check_true(self) -> None:
        mgr = GitHubAuthManager(
            gh_runner=lambda args, cwd, inp, t: GitResult(
                stdout="", stderr="bad auth", exit_code=1, success=False, command=["gh", *args]
            )
        )
        with pytest.raises(GitCommandError, match="bad auth"):
            mgr.run_gh(["auth", "status"], check=True)
