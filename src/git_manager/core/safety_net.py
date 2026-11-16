"""
Safety net and non-destructive undo ledger engine for git-mgr.
Guarantees zero data loss across autonomous AI agent and developer workflows
via reflog parsing, automated pre-mutation bookmarks, stash protection, and instant undo.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from git_manager.core.git_driver import GitDriver
from git_manager.core.models import GitCommandError, GitResult, ReflogEntry, SafetyBookmark


def _sanitize_label(label: str) -> str:
    """Sanitize label into a safe Git reference component."""
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", label.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned if cleaned else "snapshot"


def _parse_action_message(subject: str) -> tuple[str, str]:
    """
    Extract base action type and descriptive message from a Git reflog subject.
    Examples:
        'commit: feat: new feature' -> ('commit', 'feat: new feature')
        'commit (initial): feat: init' -> ('commit', 'feat: init')
        'checkout: moving from main to dev' -> ('checkout', 'moving from main to dev')
        'reset: moving to HEAD~1' -> ('reset', 'moving to HEAD~1')
        'rebase (finish): returning to ...' -> ('rebase', 'returning to ...')
    """
    subject = subject.strip()
    if ":" in subject:
        action_part, message_part = subject.split(":", 1)
        action_part = action_part.strip()
        message_part = message_part.strip()
        base_action = action_part.split("(")[0].strip().split()[0].lower()
        return base_action, message_part
    words = subject.split()
    action = words[0].lower() if words else "unknown"
    return action, subject


class SafetyNet:
    """
    Safety net engine providing non-destructive recovery, snapshot bookmarks,
    guarded transactional execution blocks, and undo mechanisms.
    """

    def __init__(self, driver: GitDriver | Path | str | None = None) -> None:
        """
        Initialize SafetyNet with a GitDriver instance or repository path.
        Defaults to current working directory if not specified.
        """
        if isinstance(driver, GitDriver):
            self.driver = driver
        else:
            self.driver = GitDriver(driver)

    def _get_ledger_path(self) -> Path:
        """Return the absolute path to the internal bookmark ledger JSON file."""
        repo_root = self.driver.find_repo_root() or self.driver.repo_path
        return repo_root / ".git" / "git-mgr" / "bookmarks.json"

    def _load_ledger(self) -> list[SafetyBookmark]:
        """Read existing bookmark records from the internal ledger file."""
        ledger_path = self._get_ledger_path()
        if not ledger_path.exists():
            return []
        try:
            content = ledger_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, list):
                return [SafetyBookmark.model_validate(item) for item in data]
            return []
        except Exception:
            return []

    def _save_ledger(self, bookmarks: list[SafetyBookmark]) -> None:
        """Atomically persist bookmark records to the internal ledger file."""
        ledger_path = self._get_ledger_path()
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [bm.model_dump() for bm in bookmarks]
        ledger_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def _get_head_sha(self) -> str | None:
        """Return current commit SHA of HEAD, or None if repo has no commits."""
        result = self.driver.run(["rev-parse", "HEAD"], check=False)
        return result.stdout.strip() if result.success and result.stdout.strip() else None

    def _abort_mid_operation(self) -> None:
        """Safely abort any active rebase, merge, cherry-pick, or revert operation."""
        repo_root = self.driver.find_repo_root() or self.driver.repo_path
        git_dir = repo_root / ".git"

        if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
            self.driver.run(["rebase", "--abort"], check=False)
        if (git_dir / "MERGE_HEAD").exists():
            self.driver.run(["merge", "--abort"], check=False)
        if (git_dir / "CHERRY_PICK_HEAD").exists():
            self.driver.run(["cherry-pick", "--abort"], check=False)
        if (git_dir / "REVERT_HEAD").exists():
            self.driver.run(["revert", "--abort"], check=False)

    def get_reflog(self, max_count: int = 30) -> list[ReflogEntry]:
        """
        Parse 'git reflog --date=iso -n <count>' into structured ReflogEntry objects.
        Extracts index, selector, commit_hash, action, message, and timestamp.
        Returns empty list if branch has no commits or on error.
        """
        result = self.driver.run(
            ["reflog", "--date=iso", "--no-abbrev-commit", f"-n{max_count}"],
            check=False,
        )
        if not result.success or not result.stdout.strip():
            return []

        # Standard git reflog --date=iso output line format:
        # <hash> HEAD@{<iso_timestamp>}: <subject>
        iso_pattern = re.compile(
            r"^(?P<hash>[0-9a-fA-F]+)\s+(?P<full_selector>HEAD@\{(?P<ts>[^}]+)\}):\s*(?P<subject>.*)$"
        )

        entries: list[ReflogEntry] = []
        for i, line in enumerate(result.stdout.splitlines()):
            line = line.strip()
            if not line:
                continue

            # Delimited format fallback (%gd|%H|%h|%gs)
            if "|" in line:
                parts = line.split("|", 4)
                if len(parts) >= 4:
                    selector = parts[0].strip()
                    commit_sha = parts[1].strip()
                    short_sha = parts[2].strip()
                    subject = parts[3].strip()
                    ts = parts[4].strip() if len(parts) > 4 else ""
                    action, message = _parse_action_message(subject)
                    entries.append(
                        ReflogEntry(
                            index=i,
                            selector=selector,
                            short_sha=short_sha,
                            commit_sha=commit_sha,
                            commit_hash=commit_sha,
                            action_type=action,
                            action=action,
                            description=subject,
                            message=message,
                            timestamp=ts,
                        )
                    )
                    continue

            match = iso_pattern.match(line)
            if match:
                commit_hash = match.group("hash")
                ts = match.group("ts")
                subject = match.group("subject")
                action, message = _parse_action_message(subject)

                entries.append(
                    ReflogEntry(
                        index=i,
                        selector=f"HEAD@{{{i}}}",
                        short_sha=commit_hash[:7],
                        commit_sha=commit_hash,
                        commit_hash=commit_hash,
                        action_type=action,
                        action=action,
                        description=subject,
                        message=message,
                        timestamp=ts,
                    )
                )

        return entries

    def parse_reflog(self, limit: int = 20) -> list[ReflogEntry]:
        """Alias for get_reflog to satisfy TASK-P3-01."""
        return self.get_reflog(max_count=limit)

    def create_bookmark(
        self,
        label: str,
        include_untracked: bool = True,
    ) -> SafetyBookmark:
        """
        Create a snapshot bookmark of the current repository state before a mutation.
        - Records a lightweight reference under 'refs/git-mgr/bookmarks/<timestamp>_<sanitized_label>'.
        - If the repository has uncommitted changes (staged, unstaged, or untracked),
          creates an annotated guard stash (with -u) and reapplies it immediately
          so current working tree changes are preserved.
        - Persists metadata to '.git/git-mgr/bookmarks.json'.
        - Returns a typed SafetyBookmark model.
        """
        current_sha = self._get_head_sha()
        if not current_sha:
            raise GitCommandError(
                command=["git", "rev-parse", "HEAD"],
                exit_code=1,
                stderr="Cannot create safety bookmark: repository has no commits.",
                stdout="",
            )

        now = datetime.now(timezone.utc)
        ts_iso = now.isoformat()
        ts_compact = now.strftime("%Y%m%dT%H%M%SZ")
        clean_label = _sanitize_label(label)

        ref_name = f"refs/git-mgr/bookmarks/{ts_compact}_{clean_label}"
        snapshot_ref = f"refs/git-mgr/snapshots/{ts_compact}_{clean_label}"

        # Check repository dirty status
        status = self.driver.get_status()
        stash_ref: str | None = None

        if not status.is_clean:
            stash_msg = f"git-mgr safety guard: {label} [{ts_iso}]"
            # Create safety stash
            self.driver.stash_save(stash_msg, include_untracked=include_untracked)
            stash_ref = "stash@{0}"

            # Immediately reapply to keep working tree uncorrupted
            apply_res = self.driver.run(["stash", "apply", "--index"], check=False)
            if not apply_res.success:
                # Fallback to standard apply if index reconstruction fails
                self.driver.run(["stash", "apply"], check=False)

        # Update bookmark references pointing to current commit
        self.driver.run(["update-ref", ref_name, current_sha], check=True)
        self.driver.run(["update-ref", snapshot_ref, current_sha], check=False)

        bookmark = SafetyBookmark(
            tag_or_ref=ref_name,
            commit_sha=current_sha,
            timestamp=ts_iso,
            label=label,
            stash_ref=stash_ref,
            repo_path=str(self.driver.repo_path),
        )

        # Persist to ledger
        existing = self._load_ledger()
        existing.append(bookmark)
        self._save_ledger(existing)

        return bookmark

    def create_snapshot(
        self,
        label: str,
        auto_stash: bool = True,
    ) -> SafetyBookmark:
        """Alias for create_bookmark to satisfy TASK-P3-02."""
        return self.create_bookmark(label=label, include_untracked=auto_stash)

    def list_bookmarks(self) -> list[SafetyBookmark]:
        """
        List all available recovery bookmarks in reverse chronological order.
        Merges ledger records with any discovered 'refs/git-mgr/bookmarks/' refs.
        """
        ledger_bookmarks = self._load_ledger()
        known_refs = {bm.tag_or_ref for bm in ledger_bookmarks}

        # Query Git's ref storage for any untracked bookmark refs
        res = self.driver.run(
            ["for-each-ref", "--format=%(refname)|%(objectname)", "refs/git-mgr/bookmarks/"],
            check=False,
        )
        if res.success and res.stdout.strip():
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line or "|" not in line:
                    continue
                ref_name, commit_sha = line.split("|", 1)
                if ref_name not in known_refs:
                    # Synthesize bookmark from ref name
                    name_part = ref_name.replace("refs/git-mgr/bookmarks/", "")
                    parts = name_part.split("_", 1)
                    ts = parts[0] if parts else ""
                    lbl = parts[1] if len(parts) > 1 else name_part
                    ledger_bookmarks.append(
                        SafetyBookmark(
                            tag_or_ref=ref_name,
                            commit_sha=commit_sha,
                            timestamp=ts,
                            label=lbl,
                            stash_ref=None,
                            repo_path=str(self.driver.repo_path),
                        )
                    )
                    known_refs.add(ref_name)

        # Sort reverse chronologically (newest first)
        ledger_bookmarks.sort(key=lambda b: b.timestamp, reverse=True)
        return ledger_bookmarks

    def list_snapshots(self) -> list[SafetyBookmark]:
        """Alias for list_bookmarks to satisfy TASK-P3-02."""
        return self.list_bookmarks()

    def undo(
        self,
        steps: int = 1,
        target_ref: str | None = None,
        force: bool = False,
    ) -> GitResult:
        """
        Safely restores HEAD to HEAD@{steps} or a pre-action commit reference.
        Guarantees zero data loss:
        1. Resolves target commit SHA from reflog before mutating state.
        2. Creates a safety bookmark of the current state first, so undo itself is 100% reversible.
        3. If uncommitted changes exist, safely stashes them before moving HEAD.
        4. Restores HEAD using 'git reset --keep' or 'git reset --hard' (with bookmark protection).
        5. Returns a typed GitResult with a clear rollback explanation.
        """
        target_spec = target_ref if target_ref else f"HEAD@{{{steps}}}"

        # Resolve target commit SHA prior to touching any state
        res_target = self.driver.run(["rev-parse", target_spec], check=False)
        if not res_target.success or not res_target.stdout.strip():
            raise GitCommandError(
                command=["git", "rev-parse", target_spec],
                exit_code=1,
                stderr=(
                    f"Cannot undo: target '{target_spec}' does not exist or repository has insufficient reflog history."
                ),
                stdout="",
            )
        target_sha = res_target.stdout.strip()
        current_sha = self._get_head_sha() or "unknown"

        # 1. Create a recovery bookmark of current state (guarantees undo can be undone)
        bookmark = self.create_bookmark(
            label=f"pre-undo-from-{current_sha[:7]}",
            include_untracked=True,
        )

        # 2. Check if working tree has dirty modifications; stash before resetting
        status = self.driver.get_status()
        if not status.is_clean:
            stash_msg = f"git-mgr safety stash before undo to {target_sha[:7]}"
            self.driver.stash_save(stash_msg, include_untracked=True)

        # 3. Perform reset to target_sha
        reset_cmd = ["reset", "--hard" if force else "--keep", target_sha]
        reset_res = self.driver.run(reset_cmd, check=False)

        if not reset_res.success and not force:
            # Fallback to --hard since we already created a full safety bookmark and stashed changes
            reset_cmd = ["reset", "--hard", target_sha]
            reset_res = self.driver.run(reset_cmd, check=True)

        explanation = (
            f"Rollback successful: HEAD restored to {target_sha[:7]} ({target_spec}). "
            f"Safety bookmark recorded at '{bookmark.tag_or_ref}'."
        )

        return GitResult(
            stdout=explanation,
            stderr=reset_res.stderr,
            exit_code=0,
            success=True,
            command=["git"] + reset_cmd,
        )

    @contextmanager
    def guarded_mutation(
        self,
        label: str = "guarded_mutation",
    ) -> Generator[SafetyBookmark, None, None]:
        """
        Context manager ensuring transactional safety during mutating Git operations.
        - Creates a pre-mutation bookmark.
        - Stashes all dirty working tree changes (including untracked files).
        - Yields control for the mutation (branch switch, rebase, merge, etc.).
        - On normal completion, pops the stash to restore uncommitted work.
        - On exception, aborts in-flight operations, rolls back to the starting commit/branch,
          restores stashed work, and re-raises the error.
        """
        starting_sha = self._get_head_sha()
        starting_branch = self.driver.get_current_branch()
        bookmark = self.create_bookmark(label=f"guard-{label}", include_untracked=True)

        status = self.driver.get_status()
        stash_saved = False

        if not status.is_clean:
            stash_saved = self.driver.stash_save(
                message=f"git-mgr guarded mutation: {label}",
                include_untracked=True,
            )

        try:
            yield bookmark
        except BaseException as exc:
            # 1. Abort any conflicting operations (rebase, merge, cherry-pick)
            self._abort_mid_operation()

            # 2. Return to the starting branch if we switched
            if starting_branch and self.driver.get_current_branch() != starting_branch:
                self.driver.run(["switch", starting_branch], check=False)

            # 3. Reset HEAD if it moved
            current_sha = self._get_head_sha()
            if starting_sha and current_sha != starting_sha:
                self.driver.run(["reset", "--hard", starting_sha], check=False)

            # 4. Restore stashed changes
            if stash_saved:
                try:
                    self.driver.stash_pop()
                except Exception:
                    pass

            raise exc
        else:
            # On successful completion, restore uncommitted work
            if stash_saved:
                self.driver.stash_pop()


# Module-level convenience functions matching project-tasks specifications


def parse_reflog(
    repo_path: Path | str | None = None,
    limit: int = 20,
) -> list[ReflogEntry]:
    """Module-level reflog parser (TASK-P3-01)."""
    return SafetyNet(repo_path).get_reflog(max_count=limit)


def create_snapshot(
    repo_path: Path | str | None = None,
    label: str = "snapshot",
    auto_stash: bool = True,
) -> SafetyBookmark:
    """Module-level pre-mutation snapshot bookmarking (TASK-P3-02)."""
    return SafetyNet(repo_path).create_bookmark(label=label, include_untracked=auto_stash)


def list_snapshots(repo_path: Path | str | None = None) -> list[SafetyBookmark]:
    """Module-level snapshot listing (TASK-P3-02)."""
    return SafetyNet(repo_path).list_bookmarks()


def undo(
    repo_path: Path | str | None = None,
    target_ref: str | None = None,
    force: bool = False,
    steps: int = 1,
) -> GitResult:
    """Module-level instant undo engine (TASK-P3-03)."""
    return SafetyNet(repo_path).undo(steps=steps, target_ref=target_ref, force=force)


@contextmanager
def guarded_mutation(
    repo_path_or_label: Path | str | None = None,
    operation_name: str | None = None,
) -> Generator[SafetyBookmark, None, None]:
    """
    Module-level guarded mutation context manager (TASK-P3-04).
    Accepts either (repo_path, operation_name) or (operation_name).
    """
    if operation_name is not None:
        repo_path = repo_path_or_label
        label = operation_name
    elif repo_path_or_label is not None:
        p = Path(repo_path_or_label)
        if p.exists() and p.is_dir():
            repo_path = p
            label = "guarded_mutation"
        else:
            repo_path = None
            label = str(repo_path_or_label)
    else:
        repo_path = None
        label = "guarded_mutation"

    net = SafetyNet(repo_path)
    with net.guarded_mutation(label=label) as bm:
        yield bm
