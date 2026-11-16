"""Multi-repository discovery, health auditing, and linear syncing."""

from git_manager.core.models import (
    RepoHealth,
    RepoHealthStatus,
    RepoSyncResult,
    SyncRecord,
    SyncReport,
    SyncStatus,
)
from git_manager.multirepo.health_check import (
    audit_repositories,
    audit_repository,
    audit_repository_health,
)
from git_manager.multirepo.scanner import (
    DEFAULT_EXCLUDE_DIRS,
    discover_repositories,
)
from git_manager.multirepo.sync import (
    sync_all_repositories,
    sync_repositories,
)

__all__ = [
    "DEFAULT_EXCLUDE_DIRS",
    "discover_repositories",
    "audit_repository",
    "audit_repositories",
    "audit_repository_health",
    "sync_repositories",
    "sync_all_repositories",
    "RepoHealth",
    "RepoHealthStatus",
    "RepoSyncResult",
    "SyncRecord",
    "SyncReport",
    "SyncStatus",
]
