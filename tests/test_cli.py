"""
Comprehensive CLI end-to-end integration test suite for git-mgr.
Tests Typer CLI commands using CliRunner across single-repo daily developer workflows,
recovery safety net, scaffolding engine, and multi-repo discovery and bulk operations.
"""

from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from git_manager.cli import app
from git_manager.core.git_driver import GitDriver
from tests.conftest import run_git

runner = CliRunner()


class TestCliRootAndHelp:
    """Tests for CLI root entrypoint, help flags, and version output."""

    def test_root_help_displays_subcommands(self) -> None:
        """Verify root --help displays all available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "git-mgr" in result.output
        assert "status" in result.output
        assert "branch" in result.output
        assert "branches" in result.output
        assert "commit" in result.output
        assert "stash" in result.output
        assert "sync" in result.output
        assert "snapshot" in result.output
        assert "undo" in result.output
        assert "log-linear" in result.output
        assert "scaffold" in result.output
        assert "scan" in result.output
        assert "sync-all" in result.output
        assert "auth" in result.output

    def test_root_version_displays_version(self) -> None:
        """Verify --version and -v display current package version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "git-mgr" in result.output
        assert "version" in result.output

        res_short = runner.invoke(app, ["-v"])
        assert res_short.exit_code == 0
        assert "version" in res_short.output

    def test_root_no_args_launches_tui(self, monkeypatch) -> None:
        """Verify running with no arguments launches the alternate-screen TUI."""
        launched: list[tuple[object, object]] = []
        monkeypatch.setattr(
            "git_manager.cli._launch_tui",
            lambda path, workspace: launched.append((path, workspace)),
        )
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert launched == [(None, None)]


class TestCliStatus:
    """Tests for 'git-mgr status' command."""

    def test_status_clean_repo(self, temp_git_repo: Path) -> None:
        """Verify status displays clean repository state card."""
        result = runner.invoke(app, ["status", str(temp_git_repo)])
        assert result.exit_code == 0
        assert "Repository Status" in result.output
        assert "CLEAN" in result.output
        assert "main" in result.output

    def test_status_dirty_repo(self, dirty_git_repo: Path) -> None:
        """Verify status displays dirty state breakdown (staged, unstaged, untracked)."""
        result = runner.invoke(app, ["status", str(dirty_git_repo)])
        assert result.exit_code == 0
        assert "DIRTY" in result.output
        assert "Staged" in result.output
        assert "Unstaged" in result.output
        assert "Untracked" in result.output
        assert "staged.txt" in result.output
        assert "README.md" in result.output
        assert "untracked.log" in result.output

    def test_status_outside_git_repo_fails(self, tmp_path: Path) -> None:
        """Verify status outside a Git repository exits with code 1 and error message."""
        non_repo = tmp_path / "not_a_repo"
        non_repo.mkdir()
        result = runner.invoke(app, ["status", str(non_repo)])
        assert result.exit_code == 1
        assert "not inside a valid Git repository" in result.output


class TestCliBranch:
    """Tests for 'git-mgr branch' and 'git-mgr branches' commands."""

    def test_branch_creation_with_valid_prefix(self, temp_git_repo: Path) -> None:
        """Verify creating branch with allowed prefix succeeds."""
        result = runner.invoke(
            app,
            ["branch", "feat/user-authentication", "--path", str(temp_git_repo)],
        )
        assert result.exit_code == 0
        assert "Successfully switched to branch 'feat/user-authentication'" in result.output

        driver = GitDriver(temp_git_repo)
        assert driver.get_current_branch() == "feat/user-authentication"

    def test_branch_creation_with_invalid_prefix_fails(self, temp_git_repo: Path) -> None:
        """Verify branch creation fails validation if prefix is missing or non-compliant."""
        result = runner.invoke(
            app,
            ["branch", "invalid-branch-no-prefix", "--path", str(temp_git_repo)],
        )
        assert result.exit_code == 1
        assert (
            "Branch Validation Failed" in result.output
            or "lacks a required prefix" in result.output
        )

    def test_branch_creation_with_force_bypasses_validation(self, temp_git_repo: Path) -> None:
        """Verify --force flag bypasses prefix validation."""
        result = runner.invoke(
            app,
            ["branch", "custom-nonstandard-branch", "--force", "--path", str(temp_git_repo)],
        )
        assert result.exit_code == 0
        assert "Successfully switched to branch 'custom-nonstandard-branch'" in result.output

        driver = GitDriver(temp_git_repo)
        assert driver.get_current_branch() == "custom-nonstandard-branch"

    def test_branches_list_display(self, temp_git_repo: Path) -> None:
        """Verify 'branches' command lists branches in a table with current indicator."""
        # Create a second branch
        run_git(["branch", "feat/alpha"], cwd=temp_git_repo)

        result = runner.invoke(app, ["branches", "--path", str(temp_git_repo)])
        assert result.exit_code == 0
        assert "Branches:" in result.output
        assert "main" in result.output
        assert "feat/alpha" in result.output
        assert "*" in result.output


class TestCliCommit:
    """Tests for 'git-mgr commit' command."""

    def test_commit_with_type_and_message_flags(self, temp_git_repo: Path) -> None:
        """Verify committing with --type and -m flags creates compliant commit."""
        (temp_git_repo / "new_feature.py").write_text("print('feat')", encoding="utf-8")
        run_git(["add", "new_feature.py"], cwd=temp_git_repo)

        result = runner.invoke(
            app,
            [
                "commit",
                "--type",
                "feat",
                "--scope",
                "core",
                "-m",
                "add feature component",
                "--path",
                str(temp_git_repo),
            ],
        )
        assert result.exit_code == 0
        assert "Committed: feat(core): add feature component" in result.output

    def test_commit_with_direct_conventional_message(self, temp_git_repo: Path) -> None:
        """Verify committing with full conventional message passed to -m."""
        (temp_git_repo / "fix.py").write_text("print('fix')", encoding="utf-8")
        run_git(["add", "fix.py"], cwd=temp_git_repo)

        result = runner.invoke(
            app,
            ["commit", "-m", "fix: correct calculation bug", "--path", str(temp_git_repo)],
        )
        assert result.exit_code == 0
        assert "Committed: fix: correct calculation bug" in result.output

    def test_commit_with_breaking_flag(self, temp_git_repo: Path) -> None:
        """Verify --breaking flag inserts breaking change indicator."""
        (temp_git_repo / "api.py").write_text("print('api')", encoding="utf-8")
        run_git(["add", "api.py"], cwd=temp_git_repo)

        result = runner.invoke(
            app,
            [
                "commit",
                "--type",
                "feat",
                "-m",
                "drop legacy endpoint",
                "--breaking",
                "--path",
                str(temp_git_repo),
            ],
        )
        assert result.exit_code == 0
        assert "feat!: drop legacy endpoint" in result.output

    def test_commit_non_conventional_message_rejected(self, temp_git_repo: Path) -> None:
        """Verify non-conventional commit messages without --type fail with code 1."""
        (temp_git_repo / "dummy.txt").write_text("content", encoding="utf-8")
        run_git(["add", "dummy.txt"], cwd=temp_git_repo)

        result = runner.invoke(
            app,
            ["commit", "-m", "random non-conventional message", "--path", str(temp_git_repo)],
        )
        assert result.exit_code == 1
        assert "Conventional Commit validation failed" in result.output

    def test_commit_missing_message_and_no_auto_fails(self, temp_git_repo: Path) -> None:
        """Verify missing message without --auto exits with code 1."""
        result = runner.invoke(app, ["commit", "--path", str(temp_git_repo)])
        assert result.exit_code == 1
        assert "Commit message is required" in result.output

    def test_commit_auto_staged_diff_analysis(self, temp_git_repo: Path) -> None:
        """Verify --auto analyzes staged files and automatically formats Conventional Commit."""
        docs_dir = temp_git_repo / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "guide.md").write_text("# User Guide", encoding="utf-8")
        run_git(["add", "docs/guide.md"], cwd=temp_git_repo)

        result = runner.invoke(app, ["commit", "--auto", "--path", str(temp_git_repo)])
        assert result.exit_code == 0
        assert "Committed: docs" in result.output

    def test_commit_auto_no_staged_changes_fails(self, temp_git_repo: Path) -> None:
        """Verify --auto with no staged files exits with code 1."""
        result = runner.invoke(app, ["commit", "--auto", "--path", str(temp_git_repo)])
        assert result.exit_code == 1
        assert "No staged changes found" in result.output


class TestCliStash:
    """Tests for 'git-mgr stash' commands (save, list, pop)."""

    def test_stash_save_list_and_pop(self, dirty_git_repo: Path) -> None:
        """Verify full stash cycle: save including untracked, list, and pop."""
        # 1. Stash save
        save_res = runner.invoke(
            app,
            ["stash", "save", "-m", "work in progress", "--path", str(dirty_git_repo)],
        )
        assert save_res.exit_code == 0
        assert "Stash saved: 'work in progress'" in save_res.output

        # Working tree should now be clean
        driver = GitDriver(dirty_git_repo)
        assert driver.get_status().is_clean is True

        # 2. Stash list
        list_res = runner.invoke(app, ["stash", "list", "--path", str(dirty_git_repo)])
        assert list_res.exit_code == 0
        assert "work in progress" in list_res.output

        # 3. Stash pop
        pop_res = runner.invoke(app, ["stash", "pop", "--path", str(dirty_git_repo)])
        assert pop_res.exit_code == 0
        assert "Stash applied and removed" in pop_res.output

        # Working tree should be dirty again
        assert driver.get_status().is_clean is False

    def test_stash_save_clean_repo(self, temp_git_repo: Path) -> None:
        """Verify stash save on clean repo outputs informative message without failing."""
        result = runner.invoke(app, ["stash", "save", "--path", str(temp_git_repo)])
        assert result.exit_code == 0
        assert "No local changes" in result.output

    def test_stash_list_empty(self, temp_git_repo: Path) -> None:
        """Verify stash list on repository with no stashes outputs info message."""
        result = runner.invoke(app, ["stash", "list", "--path", str(temp_git_repo)])
        assert result.exit_code == 0
        assert "No stash entries found" in result.output


class TestCliSync:
    """Tests for 'git-mgr sync' command."""

    def test_sync_dirty_repo_without_force_fails(self, dirty_git_repo: Path) -> None:
        """Verify sync aborts if working tree has uncommitted dirty changes without --force."""
        result = runner.invoke(app, ["sync", "--path", str(dirty_git_repo)])
        assert result.exit_code == 1
        assert "uncommitted changes" in result.output
        assert "--force" in result.output

    def test_sync_linear_rebase_success(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify sync successfully rebases clean downstream repo with upstream commits."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)

        down_driver = GitDriver(downstream)
        down_driver.run(["config", "user.name", "Test User"], check=True)
        down_driver.run(["config", "user.email", "test@example.com"], check=True)

        # Make new commit on upstream
        (temp_git_repo / "feature.txt").write_text("upstream feature", encoding="utf-8")
        driver.run(["add", "feature.txt"], check=True)
        driver.run(["commit", "-m", "feat: new feature upstream"], check=True)

        # Run git-mgr sync on downstream
        result = runner.invoke(app, ["sync", "--path", str(downstream)])
        assert result.exit_code == 0
        assert "Synchronized with upstream via linear rebase" in result.output

        # Verify downstream has the new file
        assert (downstream / "feature.txt").exists()


class TestCliSafetyNet:
    """Tests for 'snapshot', 'undo', and 'log-linear' recovery commands."""

    def test_snapshot_creates_bookmark(self, temp_git_repo: Path) -> None:
        """Verify snapshot creates a safety bookmark under refs/git-mgr/bookmarks/."""
        result = runner.invoke(
            app,
            ["snapshot", "before_refactor", "--path", str(temp_git_repo)],
        )
        assert result.exit_code == 0
        assert "Created safety bookmark 'before_refactor'" in result.output

        driver = GitDriver(temp_git_repo)
        refs_res = driver.run(["for-each-ref", "refs/git-mgr/bookmarks/"], check=True)
        assert "before_refactor" in refs_res.stdout

    def test_undo_reverts_commit(self, temp_git_repo: Path) -> None:
        """Verify undo reverts previous commit safely via reflog."""
        driver = GitDriver(temp_git_repo)
        initial_sha = driver.get_status().commit_sha

        # Create a new commit to undo
        (temp_git_repo / "file_to_undo.txt").write_text("temporary", encoding="utf-8")
        driver.run(["add", "file_to_undo.txt"], check=True)
        driver.run(["commit", "-m", "feat: commit to revert"], check=True)
        assert driver.get_status().commit_sha != initial_sha

        # Run undo
        result = runner.invoke(
            app,
            ["undo", "--steps", "1", "--force", "--path", str(temp_git_repo)],
        )
        assert result.exit_code == 0
        assert "Safely reverted state back" in result.output
        assert driver.get_status().commit_sha == initial_sha

    def test_log_linear_displays_table(self, temp_git_repo: Path) -> None:
        """Verify log-linear outputs a formatted commit history table."""
        result = runner.invoke(
            app,
            ["log-linear", "--max", "5", "--path", str(temp_git_repo)],
        )
        assert result.exit_code == 0
        assert "Linear Commit History" in result.output
        assert "chore" in result.output
        assert "initial commit" in result.output


class TestCliScaffold:
    """Tests for 'scaffold init' and 'scaffold ruleset' commands."""

    def test_scaffold_init_python_project(self, tmp_path: Path) -> None:
        """Verify scaffold init creates Layer 1, 2, 3, and .gitignore files."""
        target = tmp_path / "new_project"
        target.mkdir()

        result = runner.invoke(
            app,
            [
                "scaffold",
                "init",
                "--project-name",
                "test-pkg",
                "--project-type",
                "python",
                "--path",
                str(target),
            ],
        )
        assert result.exit_code == 0
        assert "Created" in result.output

        assert (target / ".gitignore").exists()
        assert (target / "lefthook.yml").exists()
        assert (target / ".pre-commit-config.yaml").exists()
        assert (target / ".github" / "workflows" / "ci.yml").exists()
        assert (target / ".github" / "workflows" / "release-please.yml").exists()

    def test_scaffold_init_dry_run(self, tmp_path: Path) -> None:
        """Verify --dry-run previews generated templates without modifying disk."""
        target = tmp_path / "dry_run_target"
        target.mkdir()

        result = runner.invoke(
            app,
            [
                "scaffold",
                "init",
                "--dry-run",
                "--project-name",
                "dry-app",
                "--path",
                str(target),
            ],
        )
        assert result.exit_code == 0
        assert "Dry run preview" in result.output
        assert not (target / ".gitignore").exists()

    def test_scaffold_ruleset_stdout(self) -> None:
        """Verify scaffold ruleset prints PowerShell script to standard output."""
        result = runner.invoke(app, ["scaffold", "ruleset", "--type", "ps1"])
        assert result.exit_code == 0
        assert "gh api" in result.output
        assert "rulesets" in result.output

    def test_scaffold_ruleset_file_export(self, tmp_path: Path) -> None:
        """Verify scaffold ruleset exports script to output path."""
        out_file = tmp_path / "ruleset.sh"
        result = runner.invoke(
            app,
            ["scaffold", "ruleset", "--type", "sh", "--output", str(out_file)],
        )
        assert result.exit_code == 0
        assert "Ruleset setup script written to" in result.output
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "gh api" in content

    def test_scaffold_ruleset_invalid_type_fails(self) -> None:
        """Verify invalid script type exits with error code 1."""
        result = runner.invoke(app, ["scaffold", "ruleset", "--type", "unsupported"])
        assert result.exit_code == 1
        assert "Unsupported script_type" in result.output


class TestCliMultiRepo:
    """Tests for 'scan' and 'sync-all' multi-repo commands."""

    def test_scan_discovers_repositories(self, multi_repo_sandbox: Path) -> None:
        """Verify scan identifies all repos in multi-repo sandbox and prints health dashboard."""
        result = runner.invoke(app, ["scan", str(multi_repo_sandbox)])
        assert result.exit_code == 0
        assert "Multi-Repo Health Dashboard" in result.output
        assert "repo-alpha" in result.output
        assert "repo-beta" in result.output
        assert "repo-gamma" in result.output

    def test_scan_empty_directory(self, tmp_path: Path) -> None:
        """Verify scan on folder with no Git repos outputs informative message."""
        empty_dir = tmp_path / "no_git_here"
        empty_dir.mkdir()
        result = runner.invoke(app, ["scan", str(empty_dir)])
        assert result.exit_code == 0
        assert "No Git repositories discovered" in result.output

    def test_sync_all_dry_run(self, multi_repo_sandbox: Path) -> None:
        """Verify sync-all with --dry-run inspects repos and prints summary report without modifying."""
        result = runner.invoke(
            app,
            ["sync-all", str(multi_repo_sandbox), "--dry-run"],
        )
        assert result.exit_code == 0
        assert "Multi-Repo Sync Summary Report" in result.output
        assert "Total:" in result.output
        assert "repo-alpha" in result.output
        assert "repo-beta" in result.output

    def test_sync_all_execution(self, multi_repo_sandbox: Path) -> None:
        """Verify sync-all skips un-tracked/dirty repos and reports results."""
        result = runner.invoke(app, ["sync-all", str(multi_repo_sandbox)])
        assert result.exit_code == 0
        assert "Multi-Repo Sync Summary Report" in result.output
        assert "repo-alpha" in result.output
        assert "repo-beta" in result.output


class TestConsoleEncoding:
    """Tests for Windows console encoding and safe glyph fallback mechanisms."""

    def test_safe_glyph_fallback(self) -> None:
        """Verify _safe_glyph returns fallback character when encoding cannot encode symbol."""
        import io
        import sys
        from git_manager.utils.console import _safe_glyph

        class MockCP1252Stream(io.StringIO):
            encoding = "cp1252"

        orig = sys.stdout
        try:
            sys.stdout = MockCP1252Stream()
            assert _safe_glyph("✔", "+") == "+"
            assert _safe_glyph("✘", "x") == "x"
            assert _safe_glyph("⚠", "!") == "!"
            assert _safe_glyph("ℹ", "i") == "i"
        finally:
            sys.stdout = orig

    def test_branch_switch_in_cp1252_env(self, temp_git_repo: Path) -> None:
        """Verify branch creation and switching works without UnicodeEncodeError in cp1252 env."""
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "cp1252"

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "git_manager.cli",
                "branch",
                "feat/cp1252-test",
                "--path",
                str(temp_git_repo),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert proc.returncode == 0
        assert "feat/cp1252-test" in proc.stdout
        assert "Branch Validation Failed" not in proc.stdout
        assert "UnicodeEncodeError" not in proc.stderr


class TestCliAuth:
    """Tests for 'pgit auth' GitHub sign-in and repository commands."""

    def test_auth_status_authenticated(self, monkeypatch) -> None:
        from git_manager.core.models import GitHubAccountStatus

        monkeypatch.setattr(
            "git_manager.cli.GitHubAuthManager.get_status",
            lambda self, hostname="github.com": GitHubAccountStatus(
                authenticated=True,
                username="X-Phantom",
                host=hostname,
                protocol="https",
                scopes=["repo", "workflow"],
            ),
        )
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "X-Phantom" in result.output
        assert "Authenticated" in result.output

    def test_auth_login_with_token(self, monkeypatch) -> None:
        from git_manager.core.models import GitHubAccountStatus

        monkeypatch.setattr(
            "git_manager.cli.GitHubAuthManager.login_with_token",
            lambda self, token, hostname="github.com", git_protocol="https": GitHubAccountStatus(
                authenticated=True,
                username="X-Phantom",
                host=hostname,
                protocol=git_protocol,
            ),
        )
        result = runner.invoke(app, ["auth", "login", "--token", "ghp_test123"])
        assert result.exit_code == 0
        assert "X-Phantom" in result.output

    def test_auth_repos_renders_table(self, monkeypatch, tmp_path: Path) -> None:
        from git_manager.core.models import GitHubRepoItem

        monkeypatch.setattr(
            "git_manager.cli.GitHubAuthManager.list_repos",
            lambda self, workspace_path=None, limit=50: [
                GitHubRepoItem(
                    name="phantom-git",
                    full_name="X-Phantom/phantom-git",
                    is_private=False,
                    default_branch="main",
                    url="https://github.com/X-Phantom/phantom-git",
                    local_path=str(tmp_path / "phantom-git"),
                )
            ],
        )
        result = runner.invoke(app, ["auth", "repos", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "X-Phantom/phantom-git" in result.output
        assert "Connected GitHub Repositories" in result.output
