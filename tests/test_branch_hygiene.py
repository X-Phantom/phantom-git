"""
Comprehensive unit and integration tests for branch hygiene and linear history.
Covers prefix enforcement, kebab-case slugs, safe switching, auto-stashing,
rebase configuration, and linear commit graphs.
"""

from pathlib import Path
import pytest

from git_manager.core.branch_hygiene import (
    ALLOWED_BRANCH_PREFIXES,
    BranchManager,
    format_branch_name,
    switch_or_create,
    validate_branch_name,
)
from git_manager.core.git_driver import GitDriver
from git_manager.core.linear_history import (
    ensure_rebase_configured,
    get_linear_graph,
    get_linear_log,
    sync_linear_rebase,
)


class TestBranchNameValidation:
    """Tests for validate_branch_name rules and edge cases."""

    @pytest.mark.parametrize(
        "branch_name",
        [
            "feat/user-authentication",
            "fix/issue-102",
            "chore/cleanup-dependencies",
            "docs/api-reference",
            "refactor/simplify-models",
            "ci/github-actions-matrix",
            "test/e2e-browser-suite",
            "perf/query-cache-v2",
            "feat/v1.0.0-release-prep",
            "fix/bug_in_parser",
        ],
    )
    def test_valid_branch_names(self, branch_name: str) -> None:
        is_valid, reason = validate_branch_name(branch_name)
        assert is_valid is True
        assert reason is None

    @pytest.mark.parametrize(
        ("branch_name", "expected_err_substring"),
        [
            ("", "cannot be empty"),
            ("   ", "cannot be empty"),
            ("my-feature", "lacks a required prefix"),
            ("feature/user-auth", "Invalid branch prefix"),
            ("FEAT/user-auth", "must be strictly lowercase"),
            ("feat/UserAuth", "must be strictly lowercase"),
            ("feat/spaces in branch", "cannot contain spaces"),
            ("feat/", "cannot start or end with a slash"),
            ("/feat/foo", "cannot start or end with a slash"),
            ("feat/branch.lock", "cannot end with '.lock'"),
            ("feat/foo..bar", "cannot contain consecutive dots"),
            ("feat/foo//bar", "cannot contain consecutive dots ('..') or slashes ('//')"),
            ("feat/branch?name", "contains illegal Git reference characters"),
            ("feat/branch*name", "contains illegal Git reference characters"),
            ("feat/branch~1", "contains illegal Git reference characters"),
            ("feat/branch^head", "contains illegal Git reference characters"),
        ],
    )
    def test_invalid_branch_names(self, branch_name: str, expected_err_substring: str) -> None:
        is_valid, reason = validate_branch_name(branch_name)
        assert is_valid is False
        assert reason is not None
        assert expected_err_substring.lower() in reason.lower()

    def test_allowed_prefixes_contains_standard_types(self) -> None:
        expected = ["feat/", "fix/", "chore/", "docs/", "refactor/", "ci/", "test/", "perf/"]
        for p in expected:
            assert p in ALLOWED_BRANCH_PREFIXES


class TestFormatBranchName:
    """Tests for format_branch_name normalization."""

    def test_format_branch_name_standard(self) -> None:
        formatted = format_branch_name("feat", "Add User Authentication!")
        assert formatted == "feat/add-user-authentication"

    def test_format_branch_name_with_trailing_slash(self) -> None:
        formatted = format_branch_name("fix/", "issue #102: bug in parser")
        assert formatted == "fix/issue-102-bug-in-parser"

    def test_format_branch_name_multiple_spaces_and_symbols(self) -> None:
        formatted = format_branch_name("chore", "clean...up   dependencies & caches")
        assert formatted == "chore/clean-up-dependencies-caches"

    def test_format_branch_name_empty_description(self) -> None:
        formatted = format_branch_name("docs", "   ")
        assert formatted == "docs/unnamed"


class TestBranchManager:
    """Integration tests for BranchManager operations in disposable Git repositories."""

    def test_list_branches_initial(self, temp_git_repo: Path) -> None:
        mgr = BranchManager(temp_git_repo)
        branches = mgr.list_branches()
        assert len(branches) >= 1
        current = next((b for b in branches if b["is_current"]), None)
        assert current is not None
        assert current["name"] == "main"
        assert not current["is_remote"]
        assert len(current["commit_sha"]) >= 4

    def test_create_and_switch_valid(self, temp_git_repo: Path) -> None:
        mgr = BranchManager(temp_git_repo)
        res = mgr.create_and_switch("feat/new-api")
        assert res.success is True
        driver = GitDriver(temp_git_repo)
        assert driver.get_current_branch() == "feat/new-api"

    def test_create_and_switch_invalid_name_rejected(self, temp_git_repo: Path) -> None:
        mgr = BranchManager(temp_git_repo)
        with pytest.raises(ValueError, match="Invalid branch name"):
            mgr.create_and_switch("invalid_branch_name")

    def test_create_and_switch_force_bypasses_validation(self, temp_git_repo: Path) -> None:
        mgr = BranchManager(temp_git_repo)
        res = mgr.create_and_switch("legacy-naming-convention", force=True)
        assert res.success is True
        driver = GitDriver(temp_git_repo)
        assert driver.get_current_branch() == "legacy-naming-convention"

    def test_switch_existing_branch(self, temp_git_repo: Path) -> None:
        mgr = BranchManager(temp_git_repo)
        mgr.create_and_switch("feat/branch-a")
        mgr.create_and_switch("feat/branch-b")
        driver = GitDriver(temp_git_repo)
        assert driver.get_current_branch() == "feat/branch-b"

        res = mgr.switch("feat/branch-a")
        assert res.success is True
        assert driver.get_current_branch() == "feat/branch-a"

    def test_create_and_switch_auto_stashes_dirty_tree(self, dirty_git_repo: Path) -> None:
        mgr = BranchManager(dirty_git_repo)
        driver = GitDriver(dirty_git_repo)

        # Confirm dirty state
        status_before = driver.get_status()
        assert not status_before.is_clean

        # Create and switch with auto_stash=True
        res = mgr.create_and_switch("feat/dirty-stash-test", auto_stash=True)
        assert res.success is True
        assert driver.get_current_branch() == "feat/dirty-stash-test"

        # Working tree modifications preserved on new branch
        status_after = driver.get_status()
        assert not status_after.is_clean
        assert any("staged.txt" in f.path for f in status_after.staged_files)

    def test_switch_or_create_helper(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        # 1. Non-existent branch -> creates and switches
        res1 = switch_or_create(temp_git_repo, "feat/created-via-helper")
        assert res1.success is True
        assert driver.get_current_branch() == "feat/created-via-helper"

        # 2. Existing branch -> switches to it
        driver.switch("main")
        assert driver.get_current_branch() == "main"
        res2 = switch_or_create(temp_git_repo, "feat/created-via-helper")
        assert res2.success is True
        assert driver.get_current_branch() == "feat/created-via-helper"


class TestLinearHistory:
    """Tests for linear rebase configuration, linear logs, and sync."""

    def test_ensure_rebase_configured(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        res = ensure_rebase_configured(driver, global_config=False)
        assert res.success is True

        cfg_res = driver.run(["config", "pull.rebase"], check=True)
        assert cfg_res.stdout.strip() == "true"

    def test_get_linear_graph_and_log(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        # Create multiple conventional commits
        driver.run(["commit", "--allow-empty", "-m", "feat(auth): add login handler"], check=True)
        driver.run(
            ["commit", "--allow-empty", "-m", "fix(api): correct payload schema"], check=True
        )
        driver.run(["commit", "--allow-empty", "-m", "docs: update readme guide"], check=True)

        graph = get_linear_graph(driver, max_count=5)
        assert len(graph) >= 4

        types = [c["commit_type"] for c in graph]
        assert "docs" in types
        assert "fix" in types
        assert "feat" in types

        # Check fields
        top = graph[0]
        assert "hash" in top
        assert "short_hash" in top
        assert "relative_date" in top
        assert "author" in top
        assert "subject" in top

        # Test module-level convenience function
        log_entries = get_linear_log(temp_git_repo, max_count=2)
        assert len(log_entries) == 2

    def test_sync_linear_rebase_with_upstream_and_stash(
        self, temp_git_repo: Path, tmp_path: Path
    ) -> None:
        upstream_driver = GitDriver(temp_git_repo)

        # Clone into downstream
        downstream_dir = tmp_path / "downstream_repo"
        upstream_driver.run(["clone", str(temp_git_repo), str(downstream_dir)], check=True)
        downstream_driver = GitDriver(downstream_dir)
        downstream_driver.run(["config", "user.name", "Test User"], check=True)
        downstream_driver.run(["config", "user.email", "test@example.com"], check=True)

        # Make new commit in upstream
        upstream_driver.run(
            ["commit", "--allow-empty", "-m", "feat: upstream new feature"], check=True
        )

        # Make uncommitted dirty change in downstream
        dirty_file = downstream_dir / "dirty_scratch.txt"
        dirty_file.write_text("uncommitted work", encoding="utf-8")

        # Execute sync_linear_rebase
        res = sync_linear_rebase(downstream_dir, remote="origin")
        assert res.success is True

        # Verify upstream commit was pulled
        log = downstream_driver.get_log(max_count=2)
        assert any("upstream new feature" in e["subject"] for e in log)

        # Verify uncommitted change was restored by auto-stash
        assert dirty_file.exists()
        assert dirty_file.read_text(encoding="utf-8") == "uncommitted work"
