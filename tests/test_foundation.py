"""
Foundation tests verifying package structure, CLI skeleton, data models,
and disposable Git sandbox fixtures.
"""

from pathlib import Path
from typer.testing import CliRunner
import git_manager
from git_manager import __version__
from git_manager.cli import app
from git_manager.core.models import (
    GitResult,
    GitCommandError,
    FileStatus,
    RepoStatus,
    ConventionalCommit,
    SafetyBookmark,
    ReflogEntry,
    RepoHealth,
    SemVerBump,
    SyncStatus,
    SyncReport,
)
from tests.conftest import run_git

runner = CliRunner()


def test_package_metadata():
    """Verify package imports correctly and exposes expected metadata."""
    assert git_manager.__name__ == "git_manager"
    assert git_manager.__app_name__ == "Phantom Git"
    assert "phantom-git" in git_manager.__cli_names__
    assert __version__ == "0.5.0"


def test_cli_version():
    """Verify CLI --version outputs version and exits cleanly."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Phantom Git" in result.output
    assert "git-mgr" in result.output
    assert "0.5.0" in result.output


def test_cli_help():
    """Verify CLI --help shows command usage and options."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Agentic Git Orchestrator" in result.output


def test_git_result_model():
    """Verify GitResult methods, error raising, and output property."""
    success_res = GitResult(
        stdout="hello world\n", stderr="", exit_code=0, success=True, command=["git", "status"]
    )
    assert success_res.output == "hello world"
    assert success_res.check() == success_res

    fail_res = GitResult(
        stdout="",
        stderr="fatal: error occurred",
        exit_code=128,
        success=False,
        command=["git", "checkout"],
    )
    assert fail_res.output == "fatal: error occurred"
    try:
        fail_res.check()
        assert False, "Should have raised GitCommandError"
    except GitCommandError as e:
        assert e.exit_code == 128
        assert "fatal: error occurred" in str(e)
        assert e.command == ["git", "checkout"]


def test_file_status_model():
    """Verify FileStatus flags for staged, modified, and deleted files."""
    staged = FileStatus(path="foo.py", staged_status="M", unstaged_status=None)
    assert staged.is_staged is True
    assert staged.is_modified is True
    assert staged.is_deleted is False

    untracked = FileStatus(
        path="bar.py", staged_status=None, unstaged_status="?", is_untracked=True
    )
    assert untracked.is_staged is False
    assert untracked.is_untracked is True

    deleted = FileStatus(path="old.py", staged_status="D", unstaged_status=None)
    assert deleted.is_staged is True
    assert deleted.is_deleted is True


def test_repo_status_model():
    """Verify RepoStatus counters and divergence detection."""
    status = RepoStatus(
        repo_path="/path/to/repo",
        branch_name="main",
        commit_sha="abcdef1234567890",
        upstream="origin/main",
        ahead_count=2,
        behind_count=3,
        staged_files=[FileStatus(path="a.py", staged_status="A")],
        unstaged_files=[FileStatus(path="b.py", unstaged_status="M")],
        untracked_files=[FileStatus(path="c.py", unstaged_status="?", is_untracked=True)],
        is_clean=False,
        stash_count=1,
    )
    assert status.total_changed_files == 3
    assert status.is_diverged is True
    assert status.is_clean is False


def test_conventional_commit_formatting():
    """Verify ConventionalCommit generates standard commit messages."""
    commit = ConventionalCommit(
        type="feat",
        scope="auth",
        is_breaking=True,
        subject="implement OAuth2 token exchange",
        body="Refactored legacy cookie auth to bearer tokens for AI agents.",
        breaking_description="Old session cookies are no longer recognized.",
        footers={"Closes": "#42", "Refs": "#101"},
    )
    msg = commit.format_message()
    expected_lines = [
        "feat(auth)!: implement OAuth2 token exchange",
        "",
        "Refactored legacy cookie auth to bearer tokens for AI agents.",
        "",
        "BREAKING CHANGE: Old session cookies are no longer recognized.",
        "",
        "Closes: #42",
        "",
        "Refs: #101",
    ]
    assert msg == "\n".join(expected_lines)


def test_safety_bookmark_model():
    """Verify SafetyBookmark serialization and fields."""
    bookmark = SafetyBookmark(
        tag_or_ref="refs/git-mgr/snapshots/20261029_120000_pre-rebase",
        commit_sha="1234567890abcdef",
        timestamp="2026-10-29T12:00:00Z",
        label="pre-rebase",
        stash_ref="stash@{0}",
        repo_path="/repos/project",
    )
    data = bookmark.model_dump()
    assert data["label"] == "pre-rebase"
    assert data["stash_ref"] == "stash@{0}"


def test_reflog_entry_and_sync_models():
    """Verify ReflogEntry, SemVerBump, and SyncReport models."""
    entry = ReflogEntry(
        selector="HEAD@{0}",
        short_sha="abc1234",
        commit_sha="abc1234567890abcdef",
        action_type="commit",
        description="commit: feat: new feature",
    )
    assert entry.selector == "HEAD@{0}"
    assert entry.action_type == "commit"

    assert SemVerBump.MAJOR.value == "major"
    assert SemVerBump.MINOR.value == "minor"
    assert SemVerBump.PATCH.value == "patch"
    assert SemVerBump.NONE.value == "none"

    sync_rep = SyncReport(
        repo_path="/test/repo",
        status=SyncStatus.SYNCED,
        message="Successfully rebased",
    )
    assert sync_rep.status == SyncStatus.SYNCED


def test_repo_health_status_summary():
    """Verify RepoHealth generates accurate human-readable status summaries."""
    clean_repo = RepoHealth(path="/clean", name="clean", current_branch="main", is_clean=True)
    assert clean_repo.status_summary == "Clean"

    dirty_repo = RepoHealth(
        path="/dirty", name="dirty", current_branch="main", is_clean=False, modified_count=2
    )
    assert dirty_repo.status_summary == "Dirty (uncommitted changes)"

    diverged_repo = RepoHealth(
        path="/div", name="div", current_branch="main", is_clean=True, ahead_count=2, behind_count=1
    )
    assert "Diverged (+2/-1)" in diverged_repo.status_summary


def test_temp_git_repo_fixture(temp_git_repo: Path):
    """Verify temp_git_repo fixture creates an isolated, valid git repo with initial commit."""
    assert temp_git_repo.is_dir()
    assert (temp_git_repo / ".git").is_dir()
    assert (temp_git_repo / "README.md").is_file()

    # Check git log has 1 commit
    log_proc = run_git(["log", "--oneline"], cwd=temp_git_repo)
    assert "chore: initial commit" in log_proc.stdout


def test_dirty_git_repo_fixture(dirty_git_repo: Path):
    """Verify dirty_git_repo fixture provides unstaged, staged, and untracked changes."""
    status_proc = run_git(["status", "--porcelain"], cwd=dirty_git_repo)
    lines = status_proc.stdout.strip().splitlines()

    # Should contain M (unstaged), A (staged), and ?? (untracked)
    status_codes = [line[:2] for line in lines]
    assert any("M " in code or " M" in code for code in status_codes)
    assert any("A " in code for code in status_codes)
    assert any("??" in code for code in status_codes)


def test_multi_repo_sandbox_fixture(multi_repo_sandbox: Path):
    """Verify multi_repo_sandbox fixture creates all expected test repositories."""
    assert (multi_repo_sandbox / "repo-alpha" / ".git").is_dir()
    assert (multi_repo_sandbox / "repo-beta" / ".git").is_dir()
    assert (multi_repo_sandbox / "services" / "repo-gamma" / ".git").is_dir()

    # Check branch on gamma
    branch_proc = run_git(
        ["branch", "--show-current"], cwd=multi_repo_sandbox / "services" / "repo-gamma"
    )
    assert branch_proc.stdout.strip() == "feat/gamma-upgrade"
