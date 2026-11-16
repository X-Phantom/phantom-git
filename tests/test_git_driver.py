"""
Integration and unit tests for GitDriver and Git subprocess operations.
Executes against disposable Git sandboxes and verifies edge cases.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from git_manager.core.git_driver import (
    GitDriver,
    check_git_version,
    find_repo_root,
    get_git_version,
)
from git_manager.core.models import GitCommandError
from tests.conftest import safe_rmtree


def test_driver_init(temp_git_repo: Path):
    """Verify GitDriver initialization with Path, str, and None."""
    driver_path = GitDriver(temp_git_repo)
    assert driver_path.repo_path == temp_git_repo

    driver_str = GitDriver(str(temp_git_repo))
    assert driver_str.repo_path == temp_git_repo

    driver_default = GitDriver()
    assert driver_default.repo_path == Path.cwd().resolve()


def test_run_valid_command(temp_git_repo: Path):
    """Verify safe execution of valid git command."""
    driver = GitDriver(temp_git_repo)
    result = driver.run(["status"])
    assert result.success is True
    assert result.exit_code == 0
    assert "On branch main" in result.stdout
    assert result.command == ["git", "status"]
    assert result.output != ""


def test_run_invalid_command(temp_git_repo: Path):
    """Verify error handling on invalid command when check=True and check=False."""
    driver = GitDriver(temp_git_repo)

    # With check=False
    res = driver.run(["invalid-subcommand-xyz"], check=False)
    assert res.success is False
    assert res.exit_code != 0
    assert "is not a git command" in res.stderr

    # With check=True
    with pytest.raises(GitCommandError) as exc_info:
        driver.run(["invalid-subcommand-xyz"], check=True)

    err = exc_info.value
    assert err.exit_code != 0
    assert err.command == ["git", "invalid-subcommand-xyz"]
    assert "is not a git command" in err.stderr


def test_run_timeout(temp_git_repo: Path):
    """Verify TimeoutExpired raises GitCommandError with exit_code=-1."""
    driver = GitDriver(temp_git_repo)
    with patch(
        "subprocess.run",
        side_effect=__import__("subprocess").TimeoutExpired(cmd=["git"], timeout=1),
    ):
        with pytest.raises(GitCommandError) as exc_info:
            driver.run(["status"], timeout=1)
        assert exc_info.value.exit_code == -1
        assert "timed out" in exc_info.value.stderr


def test_check_git_version(temp_git_repo: Path):
    """Verify git version detection and compatibility validation."""
    driver = GitDriver(temp_git_repo)
    ver = driver.check_git_version()
    assert isinstance(ver, tuple)
    assert len(ver) == 3
    assert ver[0] >= 2
    assert ver >= (2, 23, 0)

    # get_git_version alias
    assert get_git_version() == ver
    assert driver.get_git_version() == ver

    # Fails if required version is higher than current
    with pytest.raises(RuntimeError) as exc_info:
        check_git_version(min_version=(999, 0))
    assert "unsupported" in str(exc_info.value)


def test_get_repo_root_and_find_repo_root(temp_git_repo: Path):
    """Verify resolving repository root inside repo, subfolder, and outside repo."""
    driver = GitDriver(temp_git_repo)
    assert driver.get_repo_root() == temp_git_repo
    assert driver.find_repo_root() == temp_git_repo

    # Subfolder
    sub = temp_git_repo / "sub" / "deep"
    sub.mkdir(parents=True)
    assert find_repo_root(sub) == temp_git_repo
    assert GitDriver(sub).get_repo_root() == temp_git_repo

    # Outside repository
    temp_dir = tempfile.mkdtemp(prefix="git_mgr_non_repo_")
    non_repo = Path(temp_dir).resolve()
    try:
        assert find_repo_root(non_repo) is None
        with pytest.raises(GitCommandError):
            GitDriver(non_repo).get_repo_root()
    finally:
        safe_rmtree(non_repo)


def test_is_bare(temp_git_repo: Path):
    """Verify bare repository detection."""
    driver = GitDriver(temp_git_repo)
    assert driver.is_bare() is False

    temp_dir = tempfile.mkdtemp(prefix="git_mgr_bare_")
    bare_path = Path(temp_dir).resolve()
    try:
        driver.run(["init", "--bare"], cwd=bare_path)
        bare_driver = GitDriver(bare_path)
        assert bare_driver.is_bare() is True
    finally:
        safe_rmtree(bare_path)


def test_get_status_clean_repo(temp_git_repo: Path):
    """Verify get_status on a pristine repository."""
    driver = GitDriver(temp_git_repo)
    status = driver.get_status()

    assert status.is_clean is True
    assert status.branch_name == "main"
    assert status.commit_sha is not None
    assert status.upstream is None
    assert status.ahead_count == 0
    assert status.behind_count == 0
    assert len(status.staged_files) == 0
    assert len(status.unstaged_files) == 0
    assert len(status.untracked_files) == 0
    assert status.total_changed_files == 0
    assert status.stash_count == 0


def test_get_status_dirty_repo(dirty_git_repo: Path):
    """Verify get_status correctly categorizes staged, unstaged, and untracked files."""
    driver = GitDriver(dirty_git_repo)
    status = driver.get_status()

    assert status.is_clean is False
    assert status.branch_name == "main"
    assert status.total_changed_files == 3

    # Staged
    staged_paths = [f.path for f in status.staged_files]
    assert "staged.txt" in staged_paths
    assert status.staged_files[0].is_staged is True

    # Unstaged
    unstaged_paths = [f.path for f in status.unstaged_files]
    assert "README.md" in unstaged_paths
    assert status.unstaged_files[0].is_modified is True

    # Untracked
    untracked_paths = [f.path for f in status.untracked_files]
    assert "untracked.log" in untracked_paths
    assert status.untracked_files[0].is_untracked is True


def test_get_status_ahead_behind(temp_git_repo: Path):
    """Verify ahead and behind counts when tracking an upstream repository."""
    temp_dir = tempfile.mkdtemp(prefix="git_mgr_remote_")
    remote_path = Path(temp_dir).resolve()

    try:
        # Create bare remote
        driver = GitDriver(temp_git_repo)
        driver.run(["init", "--bare"], cwd=remote_path)

        # Add origin and push
        driver.run(["remote", "add", "origin", str(remote_path)])
        driver.run(["push", "-u", "origin", "main"])

        # Check clean tracking status
        status = driver.get_status()
        assert status.upstream == "origin/main"
        assert status.ahead_count == 0
        assert status.behind_count == 0

        # Make local commit -> ahead = 1
        readme = temp_git_repo / "README.md"
        readme.write_text("ahead commit content", encoding="utf-8")
        driver.stage(["README.md"])
        driver.commit("feat: ahead commit")

        status_ahead = driver.get_status()
        assert status_ahead.ahead_count == 1
        assert status_ahead.behind_count == 0

    finally:
        safe_rmtree(remote_path)


def test_stage_and_unstage(temp_git_repo: Path):
    """Verify staging specific files, all files, and unstaging."""
    driver = GitDriver(temp_git_repo)
    f1 = temp_git_repo / "f1.txt"
    f2 = temp_git_repo / "f2.txt"
    f1.write_text("file 1", encoding="utf-8")
    f2.write_text("file 2", encoding="utf-8")

    # Stage specific file
    driver.stage(["f1.txt"])
    st = driver.get_status()
    assert len(st.staged_files) == 1
    assert st.staged_files[0].path == "f1.txt"
    assert len(st.untracked_files) == 1
    assert st.untracked_files[0].path == "f2.txt"

    # Unstage specific file
    driver.unstage(["f1.txt"])
    st_unstaged = driver.get_status()
    assert len(st_unstaged.staged_files) == 0

    # Stage all
    driver.stage_files()  # test alias
    st_all = driver.get_status()
    assert len(st_all.staged_files) == 2

    # Unstage all
    driver.unstage_files()  # test alias
    st_none = driver.get_status()
    assert len(st_none.staged_files) == 0


def test_commit(temp_git_repo: Path):
    """Verify creating commits and handling empty commits."""
    driver = GitDriver(temp_git_repo)

    # Empty commit without allow_empty -> error
    with pytest.raises(GitCommandError) as exc_info:
        driver.commit("empty commit")
    combined_err = exc_info.value.stdout + " " + exc_info.value.stderr
    assert "nothing to commit" in combined_err or "no changes added" in combined_err

    # Empty commit with allow_empty -> success
    sha1 = driver.commit("chore: empty commit", allow_empty=True)
    assert len(sha1) == 40
    assert driver.run(["rev-parse", "HEAD"]).stdout.strip() == sha1

    # Standard commit with staged content
    new_file = temp_git_repo / "test.txt"
    new_file.write_text("committed content", encoding="utf-8")
    driver.stage(["test.txt"])
    sha2 = driver.create_commit("feat: real commit")  # test alias
    assert len(sha2) == 40
    assert sha2 != sha1


def test_switch(temp_git_repo: Path):
    """Verify switching branches and creating new branches."""
    driver = GitDriver(temp_git_repo)
    assert driver.get_current_branch() == "main"

    # Create and switch to new branch
    driver.switch("feat/test-branch", create=True)
    assert driver.get_current_branch() == "feat/test-branch"

    # Switch back to main
    driver.switch_branch("main")  # test alias
    assert driver.get_current_branch() == "main"

    # Switching to non-existent branch raises error
    with pytest.raises(GitCommandError) as exc_info:
        driver.switch("non-existent-branch-xyz")
    assert "invalid reference" in exc_info.value.stderr or "fatal" in exc_info.value.stderr


def test_switch_uncommitted_collision(temp_git_repo: Path):
    """Verify switch fails with GitCommandError when uncommitted changes collide."""
    driver = GitDriver(temp_git_repo)

    # Create branch feature and commit a modification to README.md
    driver.switch("feature", create=True)
    readme = temp_git_repo / "README.md"
    readme.write_text("# Feature branch line\n", encoding="utf-8")
    driver.stage(["README.md"])
    driver.commit("feat: update readme on feature")

    # Switch back to main
    driver.switch("main")
    # Make a dirty local uncommitted modification to README.md on main
    readme.write_text("# Conflicting local changes\n", encoding="utf-8")

    # Attempt to switch to feature should raise GitCommandError
    with pytest.raises(GitCommandError) as exc_info:
        driver.switch("feature")
    assert (
        "overwritten by checkout" in exc_info.value.stderr
        or "overwritten by checkout" in exc_info.value.output
    )


def test_restore(temp_git_repo: Path):
    """Verify restoring modified working tree files and staged index."""
    driver = GitDriver(temp_git_repo)
    readme = temp_git_repo / "README.md"
    original_text = readme.read_text(encoding="utf-8")

    # Unstaged modification
    readme.write_text("Modified text that will be restored", encoding="utf-8")
    assert readme.read_text(encoding="utf-8") != original_text

    driver.restore(["README.md"])
    assert readme.read_text(encoding="utf-8") == original_text

    # Staged restoration
    readme.write_text("Staged modification", encoding="utf-8")
    driver.stage(["README.md"])
    assert driver.get_status().staged_files[0].path == "README.md"

    driver.restore(["README.md"], staged=True)
    assert len(driver.get_status().staged_files) == 0

    # Empty paths returns no-op
    no_op = driver.restore([])
    assert no_op.success is True


def test_stash_operations(temp_git_repo: Path):
    """Verify stash_save with untracked files, stash_list, and stash_pop."""
    driver = GitDriver(temp_git_repo)

    # 1. Stash on clean repo returns False
    assert driver.stash_save() is False
    assert driver.stash_list() == []

    # 2. Add unstaged and untracked files
    readme = temp_git_repo / "README.md"
    readme.write_text("modified for stash", encoding="utf-8")
    scratch = temp_git_repo / "scratch.py"
    scratch.write_text("print('stash me')", encoding="utf-8")

    # Stash save with message and untracked (default)
    saved = driver.stash_save("WIP test stash")
    assert saved is True

    # Working tree is clean now
    st = driver.get_status()
    assert st.is_clean is True
    assert scratch.exists() is False

    # Stash list shows 1 entry
    stashes = driver.stash_list()
    assert len(stashes) == 1
    assert "WIP test stash" in stashes[0]
    assert driver.get_status().stash_count == 1

    # Pop stash
    popped = driver.stash_pop(0)
    assert popped is True

    # Changes and untracked file restored
    assert scratch.exists() is True
    assert readme.read_text(encoding="utf-8") == "modified for stash"
    assert driver.get_status().stash_count == 0

    # Pop on empty stash returns False
    assert driver.stash_pop(0) is False


def test_get_log(temp_git_repo: Path):
    """Verify retrieving commit history with structured log entries."""
    driver = GitDriver(temp_git_repo)

    # Initial repo has 1 commit
    logs = driver.get_log(10)
    assert len(logs) == 1
    assert logs[0]["subject"] == "chore: initial commit"
    assert logs[0]["author_name"] == "Test User"
    assert logs[0]["author_email"] == "test@example.com"
    assert len(logs[0]["hash"]) == 40
    assert len(logs[0]["short_hash"]) >= 7
    assert "T" in logs[0]["timestamp"]  # ISO-8601

    # Add second commit
    f = temp_git_repo / "new.txt"
    f.write_text("hi", encoding="utf-8")
    driver.stage(["new.txt"])
    driver.commit("feat: second commit with | pipe character")

    logs2 = driver.get_log(10)
    assert len(logs2) == 2
    assert logs2[0]["subject"] == "feat: second commit with | pipe character"
    assert logs2[1]["subject"] == "chore: initial commit"


def test_porcelain_renamed_status(temp_git_repo: Path) -> None:
    """Verify porcelain status parsing correctly handles renamed files (format '2 ')."""
    driver = GitDriver(temp_git_repo)
    readme = temp_git_repo / "README.md"
    readme.write_text("content", encoding="utf-8")
    driver.run(["mv", "README.md", "README_NEW.md"])

    status = driver.get_status()
    assert len(status.staged_files) >= 1
    assert any("README_NEW.md" in f.path for f in status.staged_files)


def test_pull_rebase_invocation(temp_git_repo: Path, tmp_path: Path) -> None:
    """Verify pull_rebase executes clean rebase on tracking branch."""
    downstream = tmp_path / "downstream_driver_test"
    driver = GitDriver(temp_git_repo)
    driver.run(["clone", str(temp_git_repo), str(downstream)])

    down_driver = GitDriver(downstream)
    down_driver.run(["config", "user.name", "Test User"])
    down_driver.run(["config", "user.email", "test@example.com"])

    res = down_driver.pull_rebase()
    assert res.success is True
    assert "up to date" in res.stdout.lower() or "up to date" in res.output.lower()
