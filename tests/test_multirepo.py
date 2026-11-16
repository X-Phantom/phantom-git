"""
Comprehensive test suite for Phase 6: Multi-Repo Discovery & Health Dashboard.
Tests directory scanner, health auditor, and bulk linear rebase synchronization.
"""

from __future__ import annotations

from pathlib import Path

from git_manager.core.git_driver import GitDriver
from git_manager.core.models import (
    RepoHealth,
    RepoHealthStatus,
    SyncReport,
    SyncStatus,
)
from git_manager.multirepo.health_check import (
    audit_repositories,
    audit_repository,
    audit_repository_health,
)
from git_manager.multirepo.scanner import discover_repositories
from git_manager.multirepo.sync import (
    sync_all_repositories,
    sync_repositories,
)
from tests.conftest import run_git


class TestMultiRepoScanner:
    """Test suite for repository discovery and directory pruning."""

    def test_discover_repositories_basic(self, multi_repo_sandbox: Path) -> None:
        """Verify discover_repositories identifies all repos in multi_repo_sandbox in sorted order."""
        repos = discover_repositories(multi_repo_sandbox)
        assert len(repos) == 3

        repo_names = [r.name for r in repos]
        assert "repo-alpha" in repo_names
        assert "repo-beta" in repo_names
        assert "repo-gamma" in repo_names

        # Verify sorted order
        assert repos == sorted(repos, key=lambda p: str(p).lower())

    def test_discover_repositories_max_depth(self, multi_repo_sandbox: Path) -> None:
        """Verify max_depth boundaries prevent runaway or deep traversal."""
        # Depth 1: alpha and beta are immediate children (depth 1), gamma is nested in services/ (depth 2)
        repos_depth_1 = discover_repositories(multi_repo_sandbox, max_depth=1)
        names_depth_1 = [r.name for r in repos_depth_1]
        assert "repo-alpha" in names_depth_1
        assert "repo-beta" in names_depth_1
        assert "repo-gamma" not in names_depth_1

        # Depth 2: includes services/repo-gamma
        repos_depth_2 = discover_repositories(multi_repo_sandbox, max_depth=2)
        names_depth_2 = [r.name for r in repos_depth_2]
        assert "repo-gamma" in names_depth_2

        # Depth 0 on a non-repo directory yields empty list
        assert discover_repositories(multi_repo_sandbox, max_depth=0) == []

        # Depth 0 on a repo itself returns that repo
        alpha_path = multi_repo_sandbox / "repo-alpha"
        assert discover_repositories(alpha_path, max_depth=0) == [alpha_path.resolve()]

    def test_discover_repositories_pruning_exclusions(self, multi_repo_sandbox: Path) -> None:
        """Verify excluded directories (node_modules, .venv, dist, custom) are strictly ignored."""
        # Create dummy git structures inside ignored directory names
        for excluded in ("node_modules", ".venv", "dist", "custom_pack"):
            ignored_repo = multi_repo_sandbox / excluded / "nested-lib"
            ignored_repo.mkdir(parents=True)
            run_git(["init", "-b", "main"], cwd=ignored_repo)
            run_git(["config", "user.name", "Test User"], cwd=ignored_repo)
            run_git(["config", "user.email", "test@example.com"], cwd=ignored_repo)
            (ignored_repo / "dummy.txt").write_text("dummy", encoding="utf-8")
            run_git(["add", "dummy.txt"], cwd=ignored_repo)
            run_git(["commit", "-m", "chore: init"], cwd=ignored_repo)

        # Scan with default excludes + custom_pack
        repos = discover_repositories(
            multi_repo_sandbox,
            max_depth=4,
            exclude_dirs={"custom_pack"},
        )
        repo_names = [r.name for r in repos]

        assert "nested-lib" not in repo_names
        assert len(repos) == 3

    def test_discover_repositories_nested_repo(self, multi_repo_sandbox: Path) -> None:
        """Verify discovery finds valid repositories nested inside another directory or project."""
        nested = multi_repo_sandbox / "packages" / "internal" / "core-utils"
        nested.mkdir(parents=True)
        run_git(["init", "-b", "main"], cwd=nested)
        run_git(["config", "user.name", "Test User"], cwd=nested)
        run_git(["config", "user.email", "test@example.com"], cwd=nested)
        (nested / "utils.py").write_text("def util(): pass", encoding="utf-8")
        run_git(["add", "utils.py"], cwd=nested)
        run_git(["commit", "-m", "feat: init utils"], cwd=nested)

        repos = discover_repositories(multi_repo_sandbox, max_depth=4)
        names = [r.name for r in repos]
        assert "core-utils" in names

    def test_discover_repositories_submodule_gitlink(self, tmp_path: Path) -> None:
        """Verify scanner recognizes git worktree or submodule gitlink files (.git file)."""
        worktree_dir = tmp_path / "worktree-repo"
        worktree_dir.mkdir()
        git_link = worktree_dir / ".git"
        git_link.write_text("gitdir: /some/path/.git/worktrees/wt\n", encoding="utf-8")

        repos = discover_repositories(tmp_path, max_depth=2)
        assert worktree_dir.resolve() in repos

    def test_discover_repositories_nonexistent_or_file(self, tmp_path: Path) -> None:
        """Verify scanner returns empty list for nonexistent paths or files."""
        assert discover_repositories(tmp_path / "does_not_exist") == []
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("hello", encoding="utf-8")
        assert discover_repositories(file_path) == []


class TestMultiRepoHealthCheck:
    """Test suite for repository health auditing and diagnostic recommendations."""

    def test_audit_clean_repository(self, multi_repo_sandbox: Path) -> None:
        """Verify clean repository receives CLEAN status and healthy descriptor."""
        alpha = multi_repo_sandbox / "repo-alpha"
        health = audit_repository(alpha)

        assert isinstance(health, RepoHealth)
        assert health.name == "repo-alpha"
        assert health.current_branch == "main"
        assert health.is_clean is True
        assert health.status == RepoHealthStatus.CLEAN
        assert health.is_healthy is True
        assert health.status_summary == "Clean"
        assert "healthy" in health.recommendation.lower()

    def test_audit_dirty_repository(self, multi_repo_sandbox: Path) -> None:
        """Verify dirty repository with untracked files is classified as DIRTY."""
        beta = multi_repo_sandbox / "repo-beta"
        health = audit_repository(beta)

        assert health.name == "repo-beta"
        assert health.is_clean is False
        assert health.status == RepoHealthStatus.DIRTY
        assert health.is_healthy is False
        assert health.untracked_count >= 1
        assert "Dirty" in health.status_summary
        assert "uncommitted work" in health.recommendation.lower()

    def test_audit_ahead_repository(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify repository with unpushed local commits is classified as AHEAD."""
        # Clone temp_git_repo to create downstream tracking repo
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)

        down_driver = GitDriver(downstream)
        down_driver.run(["config", "user.name", "Test User"], check=True)
        down_driver.run(["config", "user.email", "test@example.com"], check=True)

        # Create a local commit
        (downstream / "local.txt").write_text("local edit", encoding="utf-8")
        down_driver.run(["add", "local.txt"], check=True)
        down_driver.run(["commit", "-m", "feat: local commit"], check=True)

        health = audit_repository(downstream)
        assert health.status == RepoHealthStatus.AHEAD
        assert health.ahead_count == 1
        assert health.behind_count == 0
        assert "Ahead (+1)" in health.status_summary
        assert "push changes" in health.recommendation.lower()

    def test_audit_behind_repository(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify repository behind upstream is classified as BEHIND."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)

        down_driver = GitDriver(downstream)
        down_driver.run(["config", "user.name", "Test User"], check=True)
        down_driver.run(["config", "user.email", "test@example.com"], check=True)

        # Make new commit in upstream repo
        (temp_git_repo / "upstream.txt").write_text("upstream edit", encoding="utf-8")
        driver.run(["add", "upstream.txt"], check=True)
        driver.run(["commit", "-m", "feat: upstream change"], check=True)

        # Fetch in downstream so upstream tracking branch is aware
        down_driver.run(["fetch", "origin"], check=True)

        health = audit_repository(downstream)
        assert health.status == RepoHealthStatus.BEHIND
        assert health.behind_count == 1
        assert health.ahead_count == 0
        assert "Behind (-1)" in health.status_summary
        assert "git-mgr sync" in health.recommendation.lower()

    def test_audit_diverged_repository(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify repository with both ahead and behind commits is classified as DIVERGED."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)

        down_driver = GitDriver(downstream)
        down_driver.run(["config", "user.name", "Test User"], check=True)
        down_driver.run(["config", "user.email", "test@example.com"], check=True)

        # 1. Upstream commit
        (temp_git_repo / "up.txt").write_text("up", encoding="utf-8")
        driver.run(["add", "up.txt"], check=True)
        driver.run(["commit", "-m", "feat: upstream commit"], check=True)

        # 2. Downstream commit
        (downstream / "down.txt").write_text("down", encoding="utf-8")
        down_driver.run(["add", "down.txt"], check=True)
        down_driver.run(["commit", "-m", "feat: downstream commit"], check=True)

        # 3. Fetch upstream in downstream
        down_driver.run(["fetch", "origin"], check=True)

        health = audit_repository(downstream)
        assert health.status == RepoHealthStatus.DIVERGED
        assert health.ahead_count == 1
        assert health.behind_count == 1
        assert "Diverged (+1/-1)" in health.status_summary
        assert "diverged" in health.recommendation.lower()

    def test_audit_detached_head(self, temp_git_repo: Path) -> None:
        """Verify detached HEAD state is identified with DETACHED status."""
        driver = GitDriver(temp_git_repo)
        # Detach HEAD
        driver.run(["checkout", "--detach", "HEAD"], check=True)

        health = audit_repository(temp_git_repo)
        assert health.status == RepoHealthStatus.DETACHED
        assert health.current_branch == "(detached)"
        assert health.status_summary == "Detached HEAD"
        assert "detached head" in health.recommendation.lower()

    def test_audit_empty_repo_no_commits(self, tmp_path: Path) -> None:
        """Verify newly initialized repository with no commits audits safely."""
        empty_repo = tmp_path / "empty_repo"
        empty_repo.mkdir()
        run_git(["init", "-b", "main"], cwd=empty_repo)

        health = audit_repository(empty_repo)
        assert health.is_clean is True
        assert health.status == RepoHealthStatus.CLEAN
        assert "no commits" in health.recommendation.lower()

    def test_audit_repositories_concurrent(self, multi_repo_sandbox: Path) -> None:
        """Verify audit_repositories audits a sequence of repositories concurrently."""
        repos = discover_repositories(multi_repo_sandbox)
        audits = audit_repositories(repos, max_workers=3)

        assert len(audits) == len(repos)
        assert [a.path for a in audits] == [str(r.resolve()) for r in repos]

        # Verify alias function
        single = audit_repository_health(repos[0])
        assert single.name == audits[0].name


class TestMultiRepoSync:
    """Test suite for bulk linear rebase synchronization and safety pre-flight checks."""

    def test_sync_skips_dirty_repository(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify dirty repositories are skipped with SKIPPED_DIRTY when force=False."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)

        # Make uncommitted dirty change in downstream
        (downstream / "dirty.txt").write_text("uncommitted work", encoding="utf-8")

        report = sync_repositories([downstream], force=False)
        assert isinstance(report, SyncReport)
        assert report.total == 1
        assert report.skipped == 1
        assert report.synced == 0
        assert report.records[0].status == SyncStatus.SKIPPED_DIRTY
        assert "dirty" in report.records[0].message.lower()

        # Verify uncommitted change is preserved intact
        assert (downstream / "dirty.txt").read_text(encoding="utf-8") == "uncommitted work"

    def test_sync_skips_no_upstream(self, multi_repo_sandbox: Path) -> None:
        """Verify repositories with no tracking remote are safely skipped."""
        alpha = multi_repo_sandbox / "repo-alpha"
        report = sync_repositories([alpha])

        assert report.skipped == 1
        assert report.records[0].status == SyncStatus.SKIPPED_NO_UPSTREAM
        assert "no upstream" in report.records[0].message.lower()

    def test_sync_skips_diverged(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify diverged repositories are safely skipped with SKIPPED_DIVERGED."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)
        down_driver = GitDriver(downstream)
        down_driver.run(["config", "user.name", "Test User"], check=True)
        down_driver.run(["config", "user.email", "test@example.com"], check=True)

        # 1. Upstream commit
        (temp_git_repo / "up.txt").write_text("upstream", encoding="utf-8")
        driver.run(["add", "up.txt"], check=True)
        driver.run(["commit", "-m", "feat: upstream change"], check=True)

        # 2. Local commit
        (downstream / "local.txt").write_text("local", encoding="utf-8")
        down_driver.run(["add", "local.txt"], check=True)
        down_driver.run(["commit", "-m", "feat: local change"], check=True)

        # 3. Fetch
        down_driver.run(["fetch", "origin"], check=True)

        report = sync_repositories([downstream])
        assert report.skipped == 1
        assert report.records[0].status == SyncStatus.SKIPPED_DIVERGED
        assert "diverged" in report.records[0].message.lower()

    def test_sync_clean_rebase_success(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify clean repository rebases cleanly and pulls new upstream commits."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)
        down_driver = GitDriver(downstream)
        down_driver.run(["config", "user.name", "Test User"], check=True)
        down_driver.run(["config", "user.email", "test@example.com"], check=True)

        # Create upstream commit
        (temp_git_repo / "new_feature.txt").write_text("feature content", encoding="utf-8")
        driver.run(["add", "new_feature.txt"], check=True)
        driver.run(["commit", "-m", "feat: new feature from upstream"], check=True)

        report = sync_repositories([downstream])
        assert report.synced == 1
        assert report.skipped == 0
        assert report.failed == 0
        assert report.records[0].status == SyncStatus.SYNCED

        # Verify new file exists in downstream
        assert (downstream / "new_feature.txt").exists()

    def test_sync_already_up_to_date(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify already synchronized repository reports ALREADY_UP_TO_DATE."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)

        report = sync_repositories([downstream])
        assert report.up_to_date == 1
        assert report.records[0].status == SyncStatus.ALREADY_UP_TO_DATE
        assert "already up to date" in report.records[0].message.lower()

    def test_sync_dry_run_does_not_mutate(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify dry_run evaluates without modifying the downstream repository."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)
        down_driver = GitDriver(downstream)
        down_driver.run(["config", "user.name", "Test User"], check=True)
        down_driver.run(["config", "user.email", "test@example.com"], check=True)

        # Create commit on upstream
        (temp_git_repo / "remote_doc.md").write_text("remote doc", encoding="utf-8")
        driver.run(["add", "remote_doc.md"], check=True)
        driver.run(["commit", "-m", "docs: update remote docs"], check=True)

        # Downstream fetches so it knows it is behind
        down_driver.run(["fetch", "origin"], check=True)

        report = sync_repositories([downstream], dry_run=True)
        assert report.synced == 1
        assert "[dry-run]" in report.records[0].message

        # Downstream must NOT have pulled the file yet
        assert not (downstream / "remote_doc.md").exists()

    def test_sync_force_auto_stashes_dirty(self, temp_git_repo: Path, tmp_path: Path) -> None:
        """Verify force=True auto-stashes dirty tree, completes rebase, and restores changes."""
        downstream = tmp_path / "downstream"
        driver = GitDriver(temp_git_repo)
        driver.run(["clone", str(temp_git_repo), str(downstream)], check=True)
        down_driver = GitDriver(downstream)
        down_driver.run(["config", "user.name", "Test User"], check=True)
        down_driver.run(["config", "user.email", "test@example.com"], check=True)

        # Make new commit on upstream
        (temp_git_repo / "force_sync.txt").write_text("upstream file", encoding="utf-8")
        driver.run(["add", "force_sync.txt"], check=True)
        driver.run(["commit", "-m", "feat: upstream force sync test"], check=True)

        # Dirty work in downstream
        dirty_file = downstream / "work_in_progress.txt"
        dirty_file.write_text("my uncommitted work", encoding="utf-8")

        report = sync_repositories([downstream], force=True)
        assert report.synced == 1
        assert report.records[0].status == SyncStatus.SYNCED

        # Upstream file received
        assert (downstream / "force_sync.txt").exists()
        # Dirty file restored
        assert dirty_file.exists()
        assert dirty_file.read_text(encoding="utf-8") == "my uncommitted work"

    def test_sync_all_repositories_alias_and_callback(self, multi_repo_sandbox: Path) -> None:
        """Verify sync_all_repositories alias and on_progress callback execution."""
        repos = discover_repositories(multi_repo_sandbox)
        progress_events: list[tuple[Path, SyncStatus]] = []

        def callback(path: Path, record) -> None:
            progress_events.append((path, record.status))

        report = sync_all_repositories(repos, on_progress=callback)
        assert isinstance(report, SyncReport)
        assert len(progress_events) == len(repos)
        assert report.total == len(repos)
