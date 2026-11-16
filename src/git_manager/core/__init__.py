"""Core Git engine, models, safety mechanisms, branch hygiene, and commit engines."""

from git_manager.core.branch_hygiene import (
    ALLOWED_BRANCH_PREFIXES,
    ALLOWED_PREFIX_NAMES,
    BranchManager,
    format_branch_name,
    switch_or_create,
    validate_branch_name,
)
from git_manager.core.commit_parser import (
    calculate_semver_bump,
    compute_next_version,
    format_commit_message,
    parse_commit_message,
    suggest_commit_message,
    suggest_conventional_commit,
)
from git_manager.core.ci_checks import (
    PILLAR_BUILD,
    PILLAR_QUALITY,
    PILLAR_TESTS,
    CIPreFlightRunner,
    detect_project_type,
    run_ci_preflight,
)
from git_manager.core.env_manager import (
    set_github_env_secret,
    sync_env_example,
)
from git_manager.core.git_driver import (
    GitDriver,
    check_git_version,
    find_repo_root,
    get_git_version,
)
from git_manager.core.github_auth import (
    GitHubAuthManager,
    find_gh_binary,
)
from git_manager.core.github_flow import (
    PROTECTED_BRANCHES,
    GitHubFlowEngine,
    classify_ci_failure,
)
from git_manager.core.linear_history import (
    ensure_rebase_configured,
    get_linear_graph,
    get_linear_log,
    sync_linear_rebase,
)
from git_manager.core.models import (
    CIFailureCategory,
    CIPillarResult,
    CIPillarStatus,
    CIPreFlightReport,
    ConventionalCommit,
    EnvSyncReport,
    FileStatus,
    GitCommandError,
    GitHubAccountStatus,
    GitHubFlowStatus,
    GitHubRepoItem,
    GitResult,
    PRCheckItem,
    ReflogEntry,
    RepoHealth,
    RepoHealthStatus,
    RepoStatus,
    RepoSyncResult,
    SafetyBookmark,
    SemVerBump,
    SyncRecord,
    SyncReport,
    SyncStatus,
    TestingTier,
)
from git_manager.core.safety_net import (
    SafetyNet,
    create_snapshot,
    guarded_mutation,
    list_snapshots,
    parse_reflog,
    undo,
)

__all__ = [
    # Git Driver & Environment
    "GitDriver",
    "check_git_version",
    "get_git_version",
    "find_repo_root",
    # Data Models
    "CIFailureCategory",
    "CIPillarResult",
    "CIPillarStatus",
    "CIPreFlightReport",
    "ConventionalCommit",
    "EnvSyncReport",
    "FileStatus",
    "GitCommandError",
    "GitHubAccountStatus",
    "GitHubFlowStatus",
    "GitHubRepoItem",
    "GitResult",
    "PRCheckItem",
    "ReflogEntry",
    "RepoHealth",
    "RepoHealthStatus",
    "RepoStatus",
    "RepoSyncResult",
    "SafetyBookmark",
    "SemVerBump",
    "SyncRecord",
    "SyncReport",
    "SyncStatus",
    "TestingTier",
    # 3-Pillar CI Pre-Flight, Env Manager & GitHub Flow
    "CIPreFlightRunner",
    "GitHubAuthManager",
    "GitHubFlowEngine",
    "find_gh_binary",
    "PILLAR_BUILD",
    "PILLAR_QUALITY",
    "PILLAR_TESTS",
    "PROTECTED_BRANCHES",
    "classify_ci_failure",
    "detect_project_type",
    "run_ci_preflight",
    "set_github_env_secret",
    "sync_env_example",
    # Safety Net
    "SafetyNet",
    "parse_reflog",
    "create_snapshot",
    "list_snapshots",
    "guarded_mutation",
    "undo",
    # Branch Hygiene
    "ALLOWED_BRANCH_PREFIXES",
    "ALLOWED_PREFIX_NAMES",
    "BranchManager",
    "validate_branch_name",
    "format_branch_name",
    "switch_or_create",
    # Commit Parser & SemVer
    "parse_commit_message",
    "format_commit_message",
    "calculate_semver_bump",
    "compute_next_version",
    "suggest_conventional_commit",
    "suggest_commit_message",
    # Linear History
    "ensure_rebase_configured",
    "get_linear_graph",
    "sync_linear_rebase",
    "get_linear_log",
]
