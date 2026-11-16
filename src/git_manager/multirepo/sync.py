"""
Bulk linear rebase synchronization engine for git-mgr.
Performs rigorous pre-flight safety checks, skips uncommitted dirty working trees
and diverged branches, and synchronizes clean repositories via 'git pull --rebase'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from git_manager.core.git_driver import GitDriver
from git_manager.core.linear_history import sync_linear_rebase
from git_manager.core.models import (
    GitCommandError,
    SyncRecord,
    SyncReport,
    SyncStatus,
)


def sync_repositories(
    repo_paths: Sequence[Path | str],
    dry_run: bool = False,
    force: bool = False,
    on_progress: Callable[..., None] | None = None,
) -> SyncReport:
    """
    Perform bulk upstream synchronization across a sequence of Git repositories.

    Pre-flight safety rules:
    - If working tree is dirty and force=False: safely skip (SKIPPED_DIRTY) to prevent
      merge conflicts or uncommitted data loss.
    - If branch has diverged (both ahead and behind): safely skip (SKIPPED_DIVERGED).
    - If branch has no upstream tracking branch: skip (SKIPPED_NO_UPSTREAM).
    - If clean and tracking upstream: pull upstream changes using linear rebase.

    Args:
        repo_paths: Sequence of repository root directories.
        dry_run: If True, evaluates pre-flight conditions without modifying disk.
        force: If True, auto-stashes uncommitted changes before rebasing.
        on_progress: Optional callback invoked after each repository is evaluated.

    Returns:
        Comprehensive SyncReport summarizing sync outcomes and itemized records.
    """
    records: list[SyncRecord] = []
    synced_count = 0
    skipped_count = 0
    failed_count = 0
    up_to_date_count = 0

    for raw_path in repo_paths:
        target_path = Path(raw_path).resolve()

        # Pre-flight 1: Validate repository existence
        git_dir = target_path / ".git"
        if not git_dir.exists():
            record = SyncRecord(
                repo_path=str(target_path),
                status=SyncStatus.FAILED,
                message=f"Directory '{target_path}' is not a valid Git repository.",
            )
            failed_count += 1
            records.append(record)
            if on_progress:
                _notify_progress(on_progress, target_path, record)
            continue

        driver = GitDriver(target_path)

        # Pre-flight 2: Query repository status
        try:
            status = driver.get_status()
        except GitCommandError as exc:
            record = SyncRecord(
                repo_path=str(target_path),
                status=SyncStatus.FAILED,
                message=f"Failed to inspect repository status: {exc.stderr or str(exc)}",
            )
            failed_count += 1
            records.append(record)
            if on_progress:
                _notify_progress(on_progress, target_path, record)
            continue

        # Pre-flight 3: Dirty tree protection
        if not status.is_clean and not force:
            record = SyncRecord(
                repo_path=str(target_path),
                status=SyncStatus.SKIPPED_DIRTY,
                message=(
                    f"Skipped: working tree is dirty ({status.total_changed_files} "
                    f"uncommitted files). Use force=True to auto-stash."
                ),
            )
            skipped_count += 1
            records.append(record)
            if on_progress:
                _notify_progress(on_progress, target_path, record)
            continue

        # Pre-flight 4: Tracking upstream verification
        if not status.upstream:
            record = SyncRecord(
                repo_path=str(target_path),
                status=SyncStatus.SKIPPED_NO_UPSTREAM,
                message=(
                    f"Skipped: branch '{status.branch_name}' has no upstream "
                    f"tracking branch configured."
                ),
            )
            skipped_count += 1
            records.append(record)
            if on_progress:
                _notify_progress(on_progress, target_path, record)
            continue

        # Pre-flight 5: Branch divergence protection
        if status.is_diverged:
            record = SyncRecord(
                repo_path=str(target_path),
                status=SyncStatus.SKIPPED_DIVERGED,
                message=(
                    f"Skipped: branch '{status.branch_name}' has diverged from "
                    f"upstream (+{status.ahead_count}/-{status.behind_count})."
                ),
            )
            skipped_count += 1
            records.append(record)
            if on_progress:
                _notify_progress(on_progress, target_path, record)
            continue

        # Pre-flight 6: Dry-run simulation
        if dry_run:
            if status.behind_count == 0:
                record = SyncRecord(
                    repo_path=str(target_path),
                    status=SyncStatus.ALREADY_UP_TO_DATE,
                    message=f"[dry-run] Branch '{status.branch_name}' is already up to date with {status.upstream}.",
                )
                up_to_date_count += 1
            else:
                record = SyncRecord(
                    repo_path=str(target_path),
                    status=SyncStatus.SYNCED,
                    message=f"[dry-run] Would pull --rebase {status.behind_count} commit(s) from {status.upstream}.",
                )
                synced_count += 1
            records.append(record)
            if on_progress:
                _notify_progress(on_progress, target_path, record)
            continue

        # Execution path
        try:
            if force and not status.is_clean:
                # Force mode with dirty tree: use auto-stashing rebase
                res = sync_linear_rebase(repo_path=target_path)
            else:
                # Clean tree: standard pull --rebase
                res = driver.run(["pull", "--rebase"], check=True)

            output_lower = res.output.lower()
            if "already up to date" in output_lower or "is up to date" in output_lower:
                record = SyncRecord(
                    repo_path=str(target_path),
                    status=SyncStatus.ALREADY_UP_TO_DATE,
                    message="Already up to date.",
                )
                up_to_date_count += 1
            else:
                record = SyncRecord(
                    repo_path=str(target_path),
                    status=SyncStatus.SYNCED,
                    message=f"Successfully synchronized with upstream: {res.output}",
                )
                synced_count += 1
        except GitCommandError as exc:
            # Rebase failure safety recovery: abort any in-progress rebase
            driver.run(["rebase", "--abort"], check=False)
            record = SyncRecord(
                repo_path=str(target_path),
                status=SyncStatus.FAILED,
                message=f"Pull rebase failed: {exc.stderr or exc.stdout}",
            )
            failed_count += 1
        except Exception as exc:
            driver.run(["rebase", "--abort"], check=False)
            record = SyncRecord(
                repo_path=str(target_path),
                status=SyncStatus.FAILED,
                message=f"Unexpected error during synchronization: {str(exc)}",
            )
            failed_count += 1

        records.append(record)
        if on_progress:
            _notify_progress(on_progress, target_path, record)

    return SyncReport(
        records=records,
        synced_count=synced_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        up_to_date_count=up_to_date_count,
        total_count=len(records),
    )


# Alias matching TASK-P6-03 specification
sync_all_repositories = sync_repositories


def _notify_progress(
    callback: Callable[..., None],
    target_path: Path,
    record: SyncRecord,
) -> None:
    """Helper to safely call progress callback with variable signature support."""
    try:
        callback(target_path, record)
    except TypeError:
        try:
            callback(target_path, record.status, record.message)
        except Exception:
            pass
    except Exception:
        pass
