"""
Comprehensive test suite for SafetyNet and undo ledger operations.
Validates reflog parsing, snapshot bookmarking, stash protection, reversible undo,
and transactional guarded mutations against isolated Git sandboxes.
"""

from pathlib import Path
import pytest

from git_manager.core.git_driver import GitDriver
from git_manager.core.models import GitCommandError, SafetyBookmark
from git_manager.core.safety_net import (
    SafetyNet,
    create_snapshot,
    guarded_mutation,
    list_snapshots,
    parse_reflog,
    undo,
)


def test_reflog_empty_repo(temp_git_repo: Path) -> None:
    """Verify reflog parsing returns empty list when repository has no commits or history."""
    driver = GitDriver(temp_git_repo)
    # Reset repo to empty (delete commits)
    driver.run(["update-ref", "-d", "refs/heads/main"], check=False)
    driver.run(["update-ref", "-d", "HEAD"], check=False)

    net = SafetyNet(driver)
    entries = net.get_reflog(max_count=10)
    assert entries == []
    assert net.parse_reflog(limit=10) == []


def test_reflog_parsing_commits_and_branches(temp_git_repo: Path) -> None:
    """Verify reflog parsing accurately captures commits, branch switches, and metadata."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    # 1. Add another commit
    file1 = temp_git_repo / "file1.txt"
    file1.write_text("content 1", encoding="utf-8")
    driver.stage(["file1.txt"])
    c2_sha = driver.commit("feat: add file1")

    # 2. Switch to a new branch
    driver.switch("feat/test-branch", create=True)

    # 3. Add a third commit
    file2 = temp_git_repo / "file2.txt"
    file2.write_text("content 2", encoding="utf-8")
    driver.stage(["file2.txt"])
    c3_sha = driver.commit("feat: add file2")

    # 4. Switch back to main
    driver.switch("main")

    entries = net.get_reflog(max_count=20)
    assert len(entries) >= 4

    # Verify latest entry is switching back to main
    assert entries[0].index == 0
    assert entries[0].selector == "HEAD@{0}"
    assert entries[0].action in ("checkout", "switch")
    assert "main" in entries[0].description

    # Verify actions and SHAs are parsed properly
    actions = [e.action for e in entries]
    assert "checkout" in actions
    assert "commit" in actions

    commit_hashes = [e.commit_hash for e in entries]
    assert c3_sha in commit_hashes or any(c3_sha.startswith(h) for h in commit_hashes)
    assert c2_sha in commit_hashes or any(c2_sha.startswith(h) for h in commit_hashes)

    # Verify attributes for both old and new schema
    top = entries[0]
    assert top.commit_hash == top.commit_sha
    assert top.action == top.action_type
    assert top.message == top.description or len(top.message) > 0
    assert top.timestamp != ""


def test_create_bookmark_clean_repo(temp_git_repo: Path) -> None:
    """Verify creating a bookmark in a clean repository creates proper refs and ledger record."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    head_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()
    bookmark = net.create_bookmark(label="clean-checkpoint")

    assert isinstance(bookmark, SafetyBookmark)
    assert bookmark.label == "clean-checkpoint"
    assert bookmark.commit_sha == head_sha
    assert bookmark.stash_ref is None
    assert "refs/git-mgr/bookmarks/" in bookmark.tag_or_ref

    # Verify the reference physically exists in Git
    ref_check = driver.run(["rev-parse", bookmark.tag_or_ref])
    assert ref_check.stdout.strip() == head_sha


def test_create_bookmark_dirty_repo(dirty_git_repo: Path) -> None:
    """Verify creating a bookmark in a dirty repo creates a guard stash while preserving working tree."""
    driver = GitDriver(dirty_git_repo)
    net = SafetyNet(driver)

    status_before = driver.get_status()
    assert not status_before.is_clean

    bookmark = net.create_bookmark(label="pre-mutation-dirty", include_untracked=True)

    assert bookmark.stash_ref is not None
    assert "stash@" in bookmark.stash_ref

    # Verify working tree changes were NOT destroyed (staged, unstaged, untracked intact)
    status_after = driver.get_status()
    assert len(status_after.staged_files) == len(status_before.staged_files)
    assert len(status_after.unstaged_files) == len(status_before.unstaged_files)
    assert len(status_after.untracked_files) == len(status_before.untracked_files)

    # Verify guard stash exists in stash list
    stashes = driver.stash_list()
    assert len(stashes) >= 1
    assert "git-mgr safety guard: pre-mutation-dirty" in stashes[0]


def test_list_bookmarks_and_snapshots(temp_git_repo: Path) -> None:
    """Verify listing bookmarks orders them chronologically and aggregates ledger + git refs."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    bm1 = net.create_bookmark("step-one")
    bm2 = net.create_bookmark("step-two")
    assert bm1.label == "step-one"
    assert bm2.label == "step-two"

    bookmarks = net.list_bookmarks()
    assert len(bookmarks) >= 2
    labels = [b.label for b in bookmarks]
    assert "step-two" in labels
    assert "step-one" in labels

    # Verify aliases
    snapshots = net.list_snapshots()
    assert len(snapshots) == len(bookmarks)


def test_create_bookmark_no_commits_raises_error(temp_git_repo: Path) -> None:
    """Verify create_bookmark raises GitCommandError when repository has no commits."""
    driver = GitDriver(temp_git_repo)
    driver.run(["update-ref", "-d", "refs/heads/main"], check=False)
    driver.run(["update-ref", "-d", "HEAD"], check=False)

    net = SafetyNet(driver)
    with pytest.raises(GitCommandError) as exc_info:
        net.create_bookmark("fail-bookmark")
    assert "no commits" in exc_info.value.stderr.lower()


def test_undo_single_commit(temp_git_repo: Path) -> None:
    """Verify undo(steps=1) reverts a bad commit to the preceding state."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    c1_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()

    # Commit bad code
    bad_file = temp_git_repo / "bad.py"
    bad_file.write_text("print('bad')", encoding="utf-8")
    driver.stage(["bad.py"])
    c2_sha = driver.commit("feat: bad commit")

    assert driver.run(["rev-parse", "HEAD"]).stdout.strip() == c2_sha

    # Undo
    result = net.undo(steps=1)
    assert result.success
    assert "Rollback successful" in result.stdout

    current_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()
    assert current_sha == c1_sha
    assert not bad_file.exists()


def test_undo_reversible(temp_git_repo: Path) -> None:
    """Verify calling undo twice reverses the undo itself (undo is reversible)."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    c1_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()

    f = temp_git_repo / "feature.txt"
    f.write_text("good feature", encoding="utf-8")
    driver.stage(["feature.txt"])
    c2_sha = driver.commit("feat: good feature")

    # First undo: HEAD moves from c2 to c1
    res1 = net.undo(steps=1)
    assert res1.success
    assert driver.run(["rev-parse", "HEAD"]).stdout.strip() == c1_sha

    # Second undo: HEAD moves back from c1 to c2
    res2 = net.undo(steps=1)
    assert res2.success
    assert driver.run(["rev-parse", "HEAD"]).stdout.strip() == c2_sha
    assert f.exists()
    assert f.read_text(encoding="utf-8") == "good feature"


def test_undo_with_target_ref(temp_git_repo: Path) -> None:
    """Verify undo targeting a specific safety bookmark ref."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    c1_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()
    bm_c1 = net.create_bookmark("checkpoint-c1")

    # Add commit c2
    (temp_git_repo / "f2.txt").write_text("2", encoding="utf-8")
    driver.stage(["f2.txt"])
    driver.commit("feat: c2")

    # Add commit c3
    (temp_git_repo / "f3.txt").write_text("3", encoding="utf-8")
    driver.stage(["f3.txt"])
    driver.commit("feat: c3")

    # Rollback directly to checkpoint-c1
    res = net.undo(target_ref=bm_c1.tag_or_ref)
    assert res.success
    assert driver.run(["rev-parse", "HEAD"]).stdout.strip() == c1_sha


def test_undo_with_dirty_tree(dirty_git_repo: Path) -> None:
    """Verify undo preserves uncommitted changes in a safety stash when resetting HEAD."""
    driver = GitDriver(dirty_git_repo)
    net = SafetyNet(driver)

    # Add a commit on top of dirty state
    clean_file = dirty_git_repo / "clean.txt"
    clean_file.write_text("clean", encoding="utf-8")
    driver.stage(["clean.txt"])
    c2_sha = driver.commit("feat: clean commit")

    # Make working tree dirty again
    (dirty_git_repo / "scratch.txt").write_text("scratch", encoding="utf-8")

    # Undo
    res = net.undo(steps=1)
    assert res.success
    assert driver.run(["rev-parse", "HEAD"]).stdout.strip() != c2_sha

    # Stash was created for the dirty work
    stashes = driver.stash_list()
    assert any("git-mgr safety stash before undo" in s for s in stashes)


def test_undo_invalid_target_raises_error(temp_git_repo: Path) -> None:
    """Verify undo with an invalid step index or nonexistent ref raises GitCommandError."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    with pytest.raises(GitCommandError) as exc_info:
        net.undo(steps=999)
    assert (
        "does not exist" in exc_info.value.stderr.lower()
        or "insufficient" in exc_info.value.stderr.lower()
    )


def test_guarded_mutation_clean_success(temp_git_repo: Path) -> None:
    """Verify guarded_mutation succeeds cleanly on clean working tree."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    with net.guarded_mutation("branch-switch") as bm:
        assert isinstance(bm, SafetyBookmark)
        driver.switch("feat/new-work", create=True)
        (temp_git_repo / "new.txt").write_text("work", encoding="utf-8")
        driver.stage(["new.txt"])
        driver.commit("feat: new work")

    assert driver.get_current_branch() == "feat/new-work"
    assert driver.get_status().is_clean


def test_guarded_mutation_dirty_success(temp_git_repo: Path) -> None:
    """Verify guarded_mutation stashes dirty files, switches branch, and restores dirty files on destination."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    # Create uncommitted modifications and untracked file
    readme = temp_git_repo / "README.md"
    readme.write_text("dirty edit in README", encoding="utf-8")
    untracked = temp_git_repo / "untracked.txt"
    untracked.write_text("untracked agent output", encoding="utf-8")

    with net.guarded_mutation("switch-with-stash"):
        # Working tree must be pristine during mutation
        assert driver.get_status().is_clean
        driver.switch("feat/destination-branch", create=True)

    # After exiting block, uncommitted changes must be restored on destination branch
    assert driver.get_current_branch() == "feat/destination-branch"
    assert readme.read_text(encoding="utf-8") == "dirty edit in README"
    assert untracked.exists()
    assert untracked.read_text(encoding="utf-8") == "untracked agent output"


def test_guarded_mutation_exception_rollback(temp_git_repo: Path) -> None:
    """Verify guarded_mutation rolls back branch, commit, and restores dirty work on exception."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    initial_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()
    initial_branch = driver.get_current_branch()

    readme = temp_git_repo / "README.md"
    readme.write_text("uncommitted work to preserve", encoding="utf-8")
    untracked = temp_git_repo / "agent_notes.txt"
    untracked.write_text("do not lose this notes file", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Mutation explosion"):
        with net.guarded_mutation("doomed-operation"):
            driver.switch("broken-branch", create=True)
            (temp_git_repo / "broken.txt").write_text("broken", encoding="utf-8")
            driver.stage(["broken.txt"])
            driver.commit("feat: broken commit")
            raise RuntimeError("Mutation explosion")

    # Verify rollback:
    # 1. Back on original branch
    assert driver.get_current_branch() == initial_branch
    # 2. Back at initial commit SHA
    assert driver.run(["rev-parse", "HEAD"]).stdout.strip() == initial_sha
    # 3. Dirty work is completely restored
    assert readme.read_text(encoding="utf-8") == "uncommitted work to preserve"
    assert untracked.exists()
    assert untracked.read_text(encoding="utf-8") == "do not lose this notes file"


def test_module_level_convenience_functions(temp_git_repo: Path) -> None:
    """Verify module-level convenience helpers match project task specifications."""
    # 1. parse_reflog
    entries = parse_reflog(temp_git_repo, limit=5)
    assert len(entries) >= 1

    # 2. create_snapshot and list_snapshots
    snap = create_snapshot(temp_git_repo, label="module-snap")
    assert isinstance(snap, SafetyBookmark)
    snapshots = list_snapshots(temp_git_repo)
    assert any(s.label == "module-snap" for s in snapshots)

    # 3. guarded_mutation with string label
    with guarded_mutation(temp_git_repo, "module-guard") as bm:
        assert bm.commit_sha == snap.commit_sha

    # 4. undo after adding a second commit so HEAD@{1} exists
    extra = temp_git_repo / "extra.txt"
    extra.write_text("extra", encoding="utf-8")
    driver = GitDriver(temp_git_repo)
    driver.stage(["extra.txt"])
    driver.commit("feat: extra commit")

    res = undo(temp_git_repo, steps=1)
    assert res.success


def test_list_bookmarks_recovers_untracked_git_refs(temp_git_repo: Path) -> None:
    """Verify list_snapshots recovers bookmarks directly from refs/git-mgr/bookmarks/ if ledger is deleted."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    bm = net.create_bookmark("orphan-bookmark")
    assert bm.label == "orphan-bookmark"

    # Delete ledger file
    ledger_file = temp_git_repo / ".git" / "git-mgr-safety-ledger.json"
    if ledger_file.exists():
        ledger_file.unlink()

    # list_snapshots should synthesize bookmark from git refs
    snapshots = net.list_snapshots()
    assert any("orphan-bookmark" in s.label for s in snapshots)


def test_undo_with_explicit_target_ref(temp_git_repo: Path) -> None:
    """Verify undo reverting to an explicit target commit hash."""
    driver = GitDriver(temp_git_repo)
    net = SafetyNet(driver)

    initial_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()

    # Create new commit
    file1 = temp_git_repo / "step1.txt"
    file1.write_text("step1", encoding="utf-8")
    driver.stage(["step1.txt"])
    driver.commit("feat: step 1")

    # Undo back to initial_sha explicitly
    res = net.undo(target_ref=initial_sha, force=True)
    assert res.success is True
    current_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()
    assert current_sha == initial_sha
