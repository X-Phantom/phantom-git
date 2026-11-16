"""
Architectural contracts and data models for git-mgr.
All core structures use Pydantic v2 for deterministic serialization,
runtime validation, and safe agentic interaction.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
import re
from pydantic import BaseModel, Field, ConfigDict, model_validator


class GitCommandError(Exception):
    """Exception raised when a git command returns a non-zero exit code."""

    def __init__(
        self,
        command: List[str],
        exit_code: int,
        stderr: str,
        stdout: str = "",
        message: Optional[str] = None,
    ):
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr.strip()
        self.stdout = stdout.strip()
        cmd_str = " ".join(command)
        default_msg = f"Git command failed (exit code {exit_code}): '{cmd_str}'\n{self.stderr}"
        super().__init__(message or default_msg)


class GitResult(BaseModel):
    """Execution output from a low-level Git subprocess invocation."""

    model_config = ConfigDict(frozen=True)

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    success: bool = True
    command: List[str] = Field(default_factory=list)

    @property
    def output(self) -> str:
        """Returns trimmed standard output, or standard error if output is empty."""
        return self.stdout.strip() if self.stdout.strip() else self.stderr.strip()

    def check(self) -> "GitResult":
        """Raise GitCommandError if the command failed with a non-zero exit code."""
        if not self.success or self.exit_code != 0:
            raise GitCommandError(
                command=self.command,
                exit_code=self.exit_code,
                stderr=self.stderr,
                stdout=self.stdout,
            )
        return self


class FileStatus(BaseModel):
    """Status metadata for an individual file in a Git working tree."""

    model_config = ConfigDict(frozen=True)

    path: str
    staged_status: Optional[str] = None  # e.g., 'M', 'A', 'D', 'R'
    unstaged_status: Optional[str] = None  # e.g., 'M', 'D', '?'
    is_untracked: bool = False

    @property
    def is_staged(self) -> bool:
        """Whether the file has changes in the index ready to commit."""
        return self.staged_status is not None and self.staged_status != "?"

    @property
    def is_modified(self) -> bool:
        """Whether the file has modifications either staged or unstaged."""
        return self.staged_status == "M" or self.unstaged_status == "M"

    @property
    def is_deleted(self) -> bool:
        """Whether the file is marked for deletion."""
        return self.staged_status == "D" or self.unstaged_status == "D"


class RepoStatus(BaseModel):
    """Comprehensive snapshot of a repository's working tree and branch state."""

    model_config = ConfigDict(frozen=True)

    repo_path: str
    branch_name: str
    commit_sha: Optional[str] = None
    upstream: Optional[str] = None
    ahead_count: int = 0
    behind_count: int = 0
    staged_files: List[FileStatus] = Field(default_factory=list)
    unstaged_files: List[FileStatus] = Field(default_factory=list)
    untracked_files: List[FileStatus] = Field(default_factory=list)
    is_clean: bool = True
    stash_count: int = 0

    @property
    def total_changed_files(self) -> int:
        """Total count of modified, staged, and untracked files."""
        return len(self.staged_files) + len(self.unstaged_files) + len(self.untracked_files)

    @property
    def is_diverged(self) -> bool:
        """Whether branch has both unpushed local and unmerged upstream commits."""
        return self.ahead_count > 0 and self.behind_count > 0


class ConventionalCommit(BaseModel):
    """Structured representation of a Conventional Commits 1.0.0 message."""

    model_config = ConfigDict(frozen=True)

    type: str  # feat, fix, chore, docs, style, refactor, perf, test, build, ci
    scope: Optional[str] = None
    is_breaking: bool = False
    subject: str
    body: Optional[str] = None
    breaking_description: Optional[str] = None
    footers: Dict[str, str] = Field(default_factory=dict)

    def format_message(self) -> str:
        """Format the object into a compliant Conventional Commit message string."""
        breaking_mark = "!" if self.is_breaking else ""
        scope_str = f"({self.scope})" if self.scope else ""
        header = f"{self.type}{scope_str}{breaking_mark}: {self.subject}"

        lines = [header]

        if self.body:
            lines.append("")
            lines.append(self.body.strip())

        if self.breaking_description:
            lines.append("")
            lines.append(f"BREAKING CHANGE: {self.breaking_description.strip()}")

        for key, value in self.footers.items():
            lines.append("")
            lines.append(f"{key}: {value.strip()}")

        return "\n".join(lines).strip()


class SemVerBump(str, Enum):
    """Semantic version increment magnitude."""

    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class SafetyBookmark(BaseModel):
    """Internal bookmark metadata created before any mutating operation."""

    model_config = ConfigDict(frozen=True)

    tag_or_ref: str
    commit_sha: str
    timestamp: str
    label: str
    stash_ref: Optional[str] = None
    repo_path: str = ""

    @property
    def commit_hash(self) -> str:
        """Alias for commit_sha."""
        return self.commit_sha

    @property
    def ref(self) -> str:
        """Alias for tag_or_ref."""
        return self.tag_or_ref


class ReflogEntry(BaseModel):
    """Parsed single entry from git reflog."""

    model_config = ConfigDict(frozen=True)

    selector: str  # e.g., 'HEAD@{0}'
    short_sha: str = ""
    commit_sha: str = ""
    commit_hash: str = ""
    action_type: str = ""  # commit, checkout, reset, rebase, merge
    action: str = ""
    description: str = ""
    message: str = ""
    index: int = 0
    timestamp: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            sha = data.get("commit_hash") or data.get("commit_sha") or data.get("short_sha", "")
            data.setdefault("commit_sha", str(sha))
            data.setdefault("commit_hash", str(sha))
            data.setdefault("short_sha", str(sha)[:7] if sha else "")

            act = data.get("action") or data.get("action_type", "")
            data.setdefault("action", str(act))
            data.setdefault("action_type", str(act))

            msg = data.get("message") or data.get("description", "")
            data.setdefault("message", str(msg))
            data.setdefault("description", str(msg))

            if "index" not in data and "selector" in data:
                m = re.search(r"@\{(\d+)\}", str(data["selector"]))
                if m:
                    data["index"] = int(m.group(1))
        return data


class RepoHealthStatus(str, Enum):
    """Repository health and synchronization classification."""

    CLEAN = "clean"
    HEALTHY = "healthy"
    DIRTY = "dirty"
    DIVERGED = "diverged"
    AHEAD = "ahead"
    BEHIND = "behind"
    DETACHED = "detached"


class RepoHealth(BaseModel):
    """Multi-repository health metrics and diagnostic summary."""

    model_config = ConfigDict(frozen=True)

    path: str
    name: str
    current_branch: str
    is_clean: bool
    modified_count: int = 0
    untracked_count: int = 0
    stash_count: int = 0
    ahead_count: int = 0
    behind_count: int = 0
    upstream_name: Optional[str] = None
    has_remote: bool = False
    status: Optional[RepoHealthStatus] = None
    recommendation: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        """Whether repository is clean and in healthy synchronization state."""
        if self.status:
            return self.status in (RepoHealthStatus.CLEAN, RepoHealthStatus.HEALTHY)
        return self.is_clean and self.ahead_count == 0 and self.behind_count == 0

    @property
    def status_summary(self) -> str:
        """One-line status descriptor."""
        if self.status == RepoHealthStatus.DETACHED or self.current_branch in (
            "(detached)",
            "HEAD",
        ):
            return "Detached HEAD"
        if not self.is_clean:
            return "Dirty (uncommitted changes)"
        if self.ahead_count > 0 and self.behind_count > 0:
            return f"Diverged (+{self.ahead_count}/-{self.behind_count})"
        if self.ahead_count > 0:
            return f"Ahead (+{self.ahead_count})"
        if self.behind_count > 0:
            return f"Behind (-{self.behind_count})"
        return "Clean"


class SyncStatus(str, Enum):
    """Multi-repo synchronization outcome."""

    SYNCED = "synced"
    SKIPPED_DIRTY = "skipped_dirty"
    SKIPPED_NO_UPSTREAM = "skipped_no_upstream"
    NO_UPSTREAM = "skipped_no_upstream"
    SKIPPED_DIVERGED = "skipped_diverged"
    DIVERGED = "skipped_diverged"
    ALREADY_UP_TO_DATE = "already_up_to_date"
    UP_TO_DATE = "already_up_to_date"
    FAILED = "failed"


class SyncRecord(BaseModel):
    """Result of an automated sync operation on an individual repository."""

    model_config = ConfigDict(frozen=True)

    repo_path: str
    status: SyncStatus
    message: str


RepoSyncResult = SyncRecord


class SyncReport(BaseModel):
    """Comprehensive summary report of automated sync operations across repositories."""

    model_config = ConfigDict(frozen=True)

    records: List[SyncRecord] = Field(default_factory=list)
    synced_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    up_to_date_count: int = 0
    total_count: int = 0

    # Backwards-compatibility fields for single-repo direct instantiation
    repo_path: Optional[str] = None
    status: Optional[SyncStatus] = None
    message: Optional[str] = None

    @property
    def synced(self) -> int:
        """Total number of successfully synced repositories."""
        return self.synced_count

    @property
    def skipped(self) -> int:
        """Total number of skipped repositories."""
        return self.skipped_count

    @property
    def failed(self) -> int:
        """Total number of failed repositories."""
        return self.failed_count

    @property
    def up_to_date(self) -> int:
        """Total number of repositories already up to date."""
        return self.up_to_date_count

    @property
    def total(self) -> int:
        """Total repositories inspected."""
        return self.total_count or len(self.records)


class TestingTier(str, Enum):
    """Smart CI testing strictness tiers matching project maturity."""

    PROTOTYPE = "prototype"
    PRODUCTION = "production"
    STRICT = "strict"


class CIFailureCategory(str, Enum):
    """Root-cause classification of remote GitHub Actions CI failures."""

    TYPE_OR_LINT_ERROR = "type_or_lint_error"
    STALE_TEST_FAILURE = "stale_test_failure"
    MISSING_ENV_OR_SECRET = "missing_env_or_secret"
    BUILD_COMPILATION_ERROR = "build_compilation_error"
    UNKNOWN_FAILURE = "unknown_failure"


class CIPillarStatus(str, Enum):
    """Execution outcome for an individual CI pre-flight pillar."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CIPillarResult(BaseModel):
    """Diagnostic result for one of the 3 CI pre-flight validation pillars."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: CIPillarStatus
    command: str = ""
    exit_code: int = 0
    output: str = ""
    duration_seconds: float = 0.0


class CIPreFlightReport(BaseModel):
    """Aggregated 3-pillar pre-flight CI validation report."""

    model_config = ConfigDict(frozen=True)

    repo_path: str
    project_type: str
    tier: TestingTier = TestingTier.PRODUCTION
    pillars: List[CIPillarResult] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether all non-skipped CI pillars passed without failure."""
        return all(p.status != CIPillarStatus.FAILED for p in self.pillars)


class EnvSyncReport(BaseModel):
    """Summary of synchronizing discovered environment variables into .env.example."""

    model_config = ConfigDict(frozen=True)

    env_example_path: str
    discovered_keys: List[str] = Field(default_factory=list)
    added_keys: List[str] = Field(default_factory=list)
    existing_keys: List[str] = Field(default_factory=list)


class PRCheckItem(BaseModel):
    """Status of a single GitHub Actions check on a Pull Request."""

    model_config = ConfigDict(frozen=True)

    name: str
    state: str
    link: Optional[str] = None


class GitHubFlowStatus(BaseModel):
    """Snapshot of the current GitHub Flow branch and Pull Request state."""

    model_config = ConfigDict(frozen=True)

    branch_name: str
    is_feature_branch: bool
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    pr_state: Optional[str] = None
    checks: List[PRCheckItem] = Field(default_factory=list)
    all_checks_green: bool = False


class GitHubAccountStatus(BaseModel):
    """Authentication status for the connected GitHub account via gh CLI."""

    model_config = ConfigDict(frozen=True)

    authenticated: bool = False
    username: Optional[str] = None
    host: str = "github.com"
    protocol: str = "https"
    scopes: List[str] = Field(default_factory=list)
    raw_output: str = ""


class GitHubRepoItem(BaseModel):
    """Metadata for a repository accessible on the connected GitHub account."""

    model_config = ConfigDict(frozen=True)

    name: str
    full_name: str
    is_private: bool = False
    default_branch: str = "main"
    updated_at: str = ""
    url: str = ""
    description: str = ""
    local_path: Optional[str] = None
