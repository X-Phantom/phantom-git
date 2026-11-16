"""
5-Step GitHub Flow Orchestration Engine for Phantom Git.
Automates isolated feature-branch workflows:
1. Start feature branch off main (pgit flow start)
2. Local 3-pillar pre-flight verification & AI commits (pgit check / pgit commit)
3. Push & Open Pull Request (pgit flow pr)
4. Inspect PR CI checks & pull failed logs for AI repair (pgit flow checks / logs)
5. Squash and Merge & return cleanly to main (pgit flow merge)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

from git_manager.core.branch_hygiene import switch_or_create, validate_branch_name
from git_manager.core.ci_checks import (
    PILLAR_BUILD,
    PILLAR_QUALITY,
    PILLAR_TESTS,
    run_ci_preflight,
)
from git_manager.core.git_driver import GitDriver
from git_manager.core.github_auth import find_gh_binary
from git_manager.core.models import (
    CIFailureCategory,
    GitCommandError,
    GitHubFlowStatus,
    GitResult,
    PRCheckItem,
)

GHRunner = Callable[[list[str], Path, int], GitResult]

PROTECTED_BRANCHES = ("main", "master", "staging")
_GREEN_STATES = {"SUCCESS", "PASS", "SKIPPED", "NEUTRAL"}
_FAIL_CONCLUSIONS = {"failure", "timed_out", "startup_failure", "action_required"}


def classify_ci_failure(log_text: str) -> tuple[CIFailureCategory, str, list[str]]:
    """
    Classify raw GitHub Actions failure logs into an actionable AI root-cause category.

    Returns:
        Tuple of (CIFailureCategory, recommended_ai_remediation, extracted_identifiers).
    """
    text = log_text or ""

    # 1. Missing Environment Variable or GitHub Secret
    env_matches: list[str] = []
    env_patterns = [
        r"process\.env\.([A-Z][A-Z0-9_]{2,})",
        r"os\.environ\[['\"]([A-Z][A-Z0-9_]{2,})['\"]\]",
        r"KeyError:\s*['\"]([A-Z][A-Z0-9_]{2,})['\"]",
        r"Missing required environment variable[:\s]+([A-Z][A-Z0-9_]{2,})",
        r"\b((?:SUPABASE|OPENAI|ANTHROPIC|GEMINI|STRIPE|DATABASE|NEXT_PUBLIC|VPS)_[A-Z0-9_]+)\b",
    ]
    has_env_indicator = bool(
        re.search(
            r"(missing required environment variable|secret .* not found|KeyError:|env.*undefined|"
            r"is not defined in environment|process\.env\.|os\.environ\[)",
            text,
            re.IGNORECASE,
        )
    )
    if has_env_indicator:
        for pat in env_patterns:
            for found in re.findall(pat, text):
                if found not in env_matches:
                    env_matches.append(found)
        remediation = (
            f"Run `pgit env sync` and set missing variable(s) via "
            f"`pgit env set {env_matches[0]} <VALUE> --env staging` (or `--env production`)."
            if env_matches
            else "Check GitHub Settings -> Environments -> staging/production for missing secrets and run `pgit env set`."
        )
        return CIFailureCategory.MISSING_ENV_OR_SECRET, remediation, env_matches

    # 2. Stale or Failing Unit/Component Test Assertions
    stale_test_patterns = [
        r"FAIL\s+\S+\.(?:test|spec)\.(?:ts|tsx|js|jsx)",
        r"FAILED\s+\S*test_\S*\.py",
        r"AssertionError",
        r"TestingLibraryElementError",
        r"Unable to find an element with the text",
        r"Expected:.*Received:",
    ]
    if any(re.search(pat, text) for pat in stale_test_patterns):
        test_files = re.findall(r"(\S+(?:\.test|\.spec)\.\w+|\S*test_\S*\.py)", text)
        unique_tests = list(dict.fromkeys(test_files))[:5]
        return (
            CIFailureCategory.STALE_TEST_FAILURE,
            "Inspect failing test assertions: if UI/logic changed intentionally, update the stale test file; otherwise fix the regression in application code.",
            unique_tests,
        )

    # 3. Type Integrity or Linter Error
    type_lint_patterns = [
        r"error TS\d+:",
        r"ruff check",
        r"\beslint\b",
        r"\b[FEW]\d{3,4}\b\s+\S+",
        r"mypy:",
    ]
    if any(re.search(pat, text) for pat in type_lint_patterns):
        return (
            CIFailureCategory.TYPE_OR_LINT_ERROR,
            "Fix the reported type mismatches, unused imports, or lint violations at the indicated file and line numbers, then verify with `pgit check`.",
            [],
        )

    # 4. Production Build / Compilation Error
    build_patterns = [
        r"npm run build",
        r"SyntaxError",
        r"Module not found:\s*Can't resolve",
        r"Build failed because of",
        r"ModuleNotFoundError",
    ]
    if any(re.search(pat, text) for pat in build_patterns):
        return (
            CIFailureCategory.BUILD_COMPILATION_ERROR,
            "Resolve missing imports, case-sensitive path mismatches, or syntax errors blocking the production build and verify locally with `pgit check`.",
            [],
        )

    return (
        CIFailureCategory.UNKNOWN_FAILURE,
        "Inspect the failure trace below, fix locally, and verify with `pgit check` before pushing.",
        [],
    )


def _default_gh_runner(args: list[str], cwd: Path, timeout: int) -> GitResult:
    """Execute a GitHub CLI (`gh`) command headlessly with UTF-8 decoding."""
    gh_bin = find_gh_binary()
    cmd = [gh_bin, *args]
    env = {
        **os.environ,
        "GH_PROMPT_DISABLED": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    GitDriver.notify_command(" ".join(["gh", *args]))

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
        stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        return GitResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=proc.returncode,
            success=(proc.returncode == 0),
            command=["gh", *args],
        )
    except FileNotFoundError:
        return GitResult(
            stdout="",
            stderr=(
                "GitHub CLI ('gh') is not installed or not found on PATH. "
                "Install it from https://cli.github.com/ and run 'gh auth login'."
            ),
            exit_code=127,
            success=False,
            command=["gh", *args],
        )
    except subprocess.TimeoutExpired:
        return GitResult(
            stdout="",
            stderr=f"GitHub CLI command timed out after {timeout}s: gh {' '.join(args)}",
            exit_code=-1,
            success=False,
            command=["gh", *args],
        )


class GitHubFlowEngine:
    """Orchestrates the 5-step GitHub Flow loop around GitDriver and GitHub CLI."""

    def __init__(
        self,
        driver: GitDriver,
        gh_runner: GHRunner | None = None,
    ) -> None:
        self.driver = driver
        self._gh_runner = gh_runner or _default_gh_runner

    def run_gh(self, args: list[str], check: bool = True, timeout: int = 30) -> GitResult:
        """Run a `gh` CLI subcommand inside the repository root."""
        if self._gh_runner is not _default_gh_runner:
            GitDriver.notify_command(" ".join(["gh", *args]))
        res = self._gh_runner(args, self.driver.repo_path, timeout)
        if check and not res.success:
            raise GitCommandError(
                command=res.command or ["gh", *args],
                exit_code=res.exit_code,
                stderr=res.stderr,
                stdout=res.stdout,
            )
        return res

    def _has_origin_remote(self) -> bool:
        res = self.driver.run(["remote"], check=False)
        if not res.success:
            return False
        return "origin" in [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def _local_branch_exists(self, branch_name: str) -> bool:
        res = self.driver.run(["rev-parse", "--verify", f"refs/heads/{branch_name}"], check=False)
        return res.success

    def resolve_default_base_branch(self) -> str:
        """Return 'staging' if the persistent staging branch exists, otherwise 'main'."""
        return "staging" if self._local_branch_exists("staging") else "main"

    def init_branches(self, push_remote: bool = True) -> dict[str, Any]:
        """
        Bootstrap the 3-branch GitHub Flow topology (`feat/* -> staging -> main`):
        Creates persistent `staging` branch off `main` and optionally pushes both to `origin`.
        """
        if not self._local_branch_exists("main"):
            current = self.driver.get_current_branch()
            if current and current not in ("(detached)", "HEAD"):
                self.driver.run(["branch", "main"], check=True)
            else:
                raise RuntimeError("Cannot locate 'main' branch to bootstrap 'staging'.")

        created_staging = False
        if not self._local_branch_exists("staging"):
            self.driver.run(["branch", "staging", "main"], check=True)
            created_staging = True

        pushed = False
        if push_remote and self._has_origin_remote():
            self.driver.run(["push", "-u", "origin", "main"], check=True)
            self.driver.run(["push", "-u", "origin", "staging"], check=True)
            pushed = True

        return {
            "created_staging": created_staging,
            "pushed_to_origin": pushed,
            "branches": ["main", "staging"],
        }

    # ------------------------------------------------------------------------
    # Step 1: Start Isolated Feature Branch
    # ------------------------------------------------------------------------

    def start_feature(
        self,
        branch_name: str,
        base_branch: str | None = None,
        sync_base: bool = True,
        force: bool = False,
    ) -> GitResult:
        """
        Step 1 of GitHub Flow:
        Create an isolated feature/fix branch off the synced base branch (`staging` or `main`).
        """
        cleaned_name = branch_name.strip()
        if cleaned_name in PROTECTED_BRANCHES:
            raise ValueError(
                f"Cannot use '{cleaned_name}' as a feature branch name. "
                "Use a prefixed branch like 'feat/my-feature' or 'fix/bug-name'."
            )

        if not force:
            is_valid, reason = validate_branch_name(cleaned_name)
            if not is_valid:
                raise ValueError(reason or f"Invalid branch name '{cleaned_name}'.")

        effective_base = base_branch or self.resolve_default_base_branch()

        stashed = False
        try:
            if sync_base and self._local_branch_exists(effective_base):
                status = self.driver.get_status()
                if not status.is_clean:
                    stashed = self.driver.stash_save(
                        message=f"phantom-git: auto-stash before flow start {cleaned_name}",
                        include_untracked=True,
                    )
                if self.driver.get_current_branch() != effective_base:
                    self.driver.switch(effective_base, create=False)
                if self._has_origin_remote():
                    self.driver.run(["pull", "--rebase", "origin", effective_base], check=False)

            return switch_or_create(
                self.driver.repo_path,
                branch_name=cleaned_name,
                auto_stash=True,
                force=force,
            )
        finally:
            if stashed:
                self.driver.stash_pop(0)

    # ------------------------------------------------------------------------
    # Step 3: Push & Open Pull Request
    # ------------------------------------------------------------------------

    def open_pull_request(
        self,
        title: str | None = None,
        body: str | None = None,
        base_branch: str | None = None,
        draft: bool = False,
        run_checks: bool = True,
    ) -> GitResult:
        """
        Step 3 of GitHub Flow:
        Validate 3 CI pillars locally (optional), push branch, and open a PR via `gh pr create`.
        """
        current_branch = self.driver.get_current_branch()
        if current_branch in ("main", "master"):
            raise ValueError(
                "Cannot open a Pull Request from 'main'. "
                "Create a feature branch first with 'pgit flow start <type>/<name>'."
            )
        if current_branch == "staging":
            raise ValueError(
                "You are on 'staging'. To promote staging to production ('main'), "
                "use 'pgit flow promote' instead."
            )
        if current_branch in ("(detached)", "HEAD", ""):
            raise ValueError("Cannot open a Pull Request from a detached HEAD state.")

        effective_base = base_branch or self.resolve_default_base_branch()

        if run_checks:
            report = run_ci_preflight(self.driver.repo_path)
            if not report.passed:
                failed = [p.name for p in report.pillars if p.status.value == "failed"]
                raise RuntimeError(
                    f"3-pillar CI pre-flight failed ({', '.join(failed)}). "
                    "Fix local errors before opening a Pull Request or pass run_checks=False."
                )

        self.driver.run(["push", "-u", "origin", current_branch], check=True)

        gh_args = ["pr", "create", "--base", effective_base, "--head", current_branch]
        if title:
            gh_args.extend(["--title", title])
            gh_args.extend(
                [
                    "--body",
                    body or "Created via Phantom Git (`pgit flow pr`).",
                ]
            )
        else:
            gh_args.append("--fill")
            if body:
                gh_args.extend(["--body", body])

        if draft:
            gh_args.append("--draft")

        return self.run_gh(gh_args, check=True)

    # ------------------------------------------------------------------------
    # Step 4: Inspect Remote PR Checks & Fetch Failed Logs
    # ------------------------------------------------------------------------

    def get_pr_checks(self) -> list[PRCheckItem]:
        """Step 4a: Query remote GitHub Actions PR check statuses via `gh pr checks`."""
        res = self.run_gh(["pr", "checks", "--json", "name,state,link"], check=False)
        raw_out = res.stdout.strip()

        if raw_out.startswith("["):
            try:
                items = json.loads(raw_out)
                return [
                    PRCheckItem(
                        name=str(item.get("name", "")),
                        state=str(item.get("state", "UNKNOWN")).upper(),
                        link=item.get("link") or None,
                    )
                    for item in items
                    if isinstance(item, dict)
                ]
            except json.JSONDecodeError:
                pass

        # Fallback: line parsing for older `gh` CLI versions without `--json`
        if not res.success and not raw_out:
            combined_err = f"{res.stderr} {res.stdout}".lower()
            if "no checks reported" in combined_err:
                return []
            raise GitCommandError(
                command=res.command or ["gh", "pr", "checks"],
                exit_code=res.exit_code,
                stderr=res.stderr,
                stdout=res.stdout,
            )

        parsed_items: list[PRCheckItem] = []
        for line in raw_out.splitlines():
            parts = [p.strip() for p in line.split("\t") if p.strip()]
            if not parts:
                continue
            name = parts[0]
            state = parts[1].upper() if len(parts) > 1 else "UNKNOWN"
            link = next((p for p in parts[2:] if p.startswith("http")), None)
            parsed_items.append(PRCheckItem(name=name, state=state, link=link))
        return parsed_items

    def fetch_ci_failure_logs(
        self,
        output_file: Path | str | None = None,
        save_default: bool = True,
    ) -> str:
        """
        Step 4b: Fetch failed GitHub Actions logs for the current branch and format
        an AI-ready diagnostic report highlighting any failing CI pillars.
        """
        branch = self.driver.get_current_branch()
        runs_res = self.run_gh(
            [
                "run",
                "list",
                "--branch",
                branch,
                "--limit",
                "5",
                "--json",
                "databaseId,name,conclusion,status,workflowName,url",
            ],
            check=True,
        )

        try:
            runs = json.loads(runs_res.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse GitHub Actions run list JSON: {exc}") from exc

        failed_runs = [
            r
            for r in runs
            if isinstance(r, dict)
            and (
                str(r.get("conclusion", "")).lower() in _FAIL_CONCLUSIONS
                or (
                    str(r.get("status", "")).lower() == "completed"
                    and str(r.get("conclusion", "")).lower()
                    not in ("success", "skipped", "neutral", "")
                )
            )
        ]

        if not failed_runs:
            return f"No failed GitHub Actions workflow runs found for branch '{branch}'."

        latest = failed_runs[0]
        run_id = latest.get("databaseId")
        wf_name = latest.get("workflowName") or latest.get("name") or "CI"
        conclusion = latest.get("conclusion") or "failure"
        run_url = latest.get("url") or ""

        log_res = self.run_gh(["run", "view", str(run_id), "--log-failed"], check=False)
        raw_logs = (
            log_res.stdout.strip() or log_res.stderr.strip() or "No failure log output returned."
        )
        log_lines = raw_logs.splitlines()
        if len(log_lines) > 250:
            raw_logs = "\n".join(["... (truncated earlier lines) ...", *log_lines[-250:]])

        detected_pillars = [
            pillar
            for pillar in (PILLAR_QUALITY, PILLAR_TESTS, PILLAR_BUILD)
            if pillar.lower() in raw_logs.lower() or pillar.lower() in str(wf_name).lower()
        ]
        pillars_line = (
            ", ".join(detected_pillars) if detected_pillars else "Inspect log trace below"
        )
        category, remediation, extracted = classify_ci_failure(raw_logs)
        extracted_line = ", ".join(f"`{item}`" for item in extracted) if extracted else "None"

        report_md = "\n".join(
            [
                "# Phantom Git — AI Diagnostic CI Failure Report",
                "",
                f"- **Branch**: `{branch}`",
                f"- **Workflow**: `{wf_name}` (Run ID: `{run_id}`)",
                f"- **Conclusion**: `{conclusion}`",
                f"- **Detected Gate(s)**: {pillars_line}",
                f"- **Root Cause Category**: `{category.value}`",
                f"- **Extracted Identifiers**: {extracted_line}",
                f"- **Run URL**: {run_url or 'N/A'}",
                "",
                "## Recommended AI Remediation",
                remediation,
                "",
                "## Failed Job Log Trace",
                "",
                "```text",
                raw_logs,
                "```",
                "",
                "## Next Action for AI Agent",
                "1. Apply the recommended remediation above on this feature branch.",
                "2. Verify all gates locally with `pgit check` before pushing.",
                "3. Commit and push to re-trigger GitHub Actions on the open PR.",
                "",
            ]
        )

        dest: Path | None = None
        if output_file is not None:
            dest = Path(output_file).resolve()
        elif save_default:
            dest = (self.driver.repo_path / ".phantom-git" / "last-ci-failure.md").resolve()

        if dest is not None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(report_md, encoding="utf-8", newline="\n")

        return report_md

    # ------------------------------------------------------------------------
    # Step 5: Squash and Merge & Clean Return to Main
    # ------------------------------------------------------------------------

    def squash_and_merge(
        self,
        auto_merge: bool = False,
        delete_branch: bool = True,
        base_branch: str | None = None,
    ) -> GitResult:
        """
        Step 5 of GitHub Flow:
        Verify PR checks are green (or queue --auto merge), squash-merge the PR,
        delete the temporary remote branch, and switch local repo back to base_branch.
        """
        current_branch = self.driver.get_current_branch()
        if current_branch in ("main", "master"):
            raise ValueError(
                "Cannot squash-and-merge from 'main'. Switch to your feature branch first."
            )
        if current_branch == "staging":
            raise ValueError(
                "Cannot squash-merge 'staging'. Use 'pgit flow promote' to merge 'staging' -> 'main' with a merge commit."
            )

        effective_base = base_branch or self.resolve_default_base_branch()

        if not auto_merge:
            checks = self.get_pr_checks()
            non_green = [c for c in checks if c.state.upper() not in _GREEN_STATES]
            if non_green:
                summary = ", ".join(f"{c.name}={c.state}" for c in non_green)
                raise RuntimeError(
                    f"Cannot merge PR while checks are not green ({summary}). "
                    "Fix failures or pass auto_merge=True."
                )

        gh_args = ["pr", "merge", "--squash"]
        if delete_branch:
            gh_args.append("--delete-branch")
        if auto_merge:
            gh_args.append("--auto")

        merge_res = self.run_gh(gh_args, check=True)

        if self._local_branch_exists(effective_base):
            self.driver.switch(effective_base, create=False)
            if self._has_origin_remote():
                self.driver.run(["pull", "--rebase", "origin", effective_base], check=False)

        return merge_res

    def promote_staging_to_main(
        self,
        watch_checks: bool = False,
        auto_merge: bool = False,
    ) -> dict[str, Any]:
        """
        Flow B — Promote persistent `staging` branch to `main` (Production):
        Opens a promotion PR (`staging -> main`), verifies CI checks, and merges
        with a standard `--merge` commit so `staging` and `main` histories stay in sync.
        """
        if not self._local_branch_exists("staging"):
            raise ValueError(
                "Branch 'staging' does not exist. Run 'pgit flow init-branches' first."
            )

        if self.driver.get_current_branch() != "staging":
            status = self.driver.get_status()
            if not status.is_clean:
                raise RuntimeError(
                    "Working tree has uncommitted changes. Commit or stash before promoting 'staging'."
                )
            self.driver.switch("staging", create=False)

        if self._has_origin_remote():
            self.driver.run(["push", "-u", "origin", "staging"], check=True)

        existing_pr_res = self.run_gh(
            [
                "pr",
                "list",
                "--base",
                "main",
                "--head",
                "staging",
                "--json",
                "number,url",
            ],
            check=False,
        )
        pr_url: str | None = None
        if existing_pr_res.success and existing_pr_res.stdout.strip().startswith("["):
            try:
                existing = json.loads(existing_pr_res.stdout)
                if existing:
                    pr_url = existing[0].get("url")
            except json.JSONDecodeError:
                pass

        if not pr_url:
            create_res = self.run_gh(
                [
                    "pr",
                    "create",
                    "--base",
                    "main",
                    "--head",
                    "staging",
                    "--title",
                    "Release: Promote Staging to Production",
                    "--body",
                    "Automated promotion of verified staging build to production.",
                ],
                check=True,
            )
            pr_url = create_res.stdout.strip() or None

        if watch_checks:
            self.run_gh(["pr", "checks", "--watch"], check=False)

        if not auto_merge:
            checks = self.get_pr_checks()
            non_green = [c for c in checks if c.state.upper() not in _GREEN_STATES]
            if non_green:
                summary = ", ".join(f"{c.name}={c.state}" for c in non_green)
                raise RuntimeError(
                    f"Cannot promote staging while PR checks are not green ({summary})."
                )

        gh_args = ["pr", "merge", "--merge"]
        if auto_merge:
            gh_args.append("--auto")
        self.run_gh(gh_args, check=True)

        if self._local_branch_exists("main"):
            self.driver.switch("main", create=False)
            if self._has_origin_remote():
                self.driver.run(["pull", "--rebase", "origin", "main"], check=False)

        return {
            "pr_url": pr_url,
            "merged": not auto_merge,
            "auto_merge": auto_merge,
            "merge_strategy": "merge",
        }

    def get_flow_status(self, base_branch: str | None = None) -> GitHubFlowStatus:
        """Collect combined local branch and remote PR check status."""
        branch = self.driver.get_current_branch()
        effective_base = base_branch or self.resolve_default_base_branch()
        is_feat = branch not in (*PROTECTED_BRANCHES, effective_base, "(detached)", "HEAD", "")
        pr_number: int | None = None
        pr_url: str | None = None
        pr_state: str | None = None
        checks: list[PRCheckItem] = []

        if is_feat:
            pr_res = self.run_gh(
                ["pr", "view", "--json", "number,url,state"],
                check=False,
            )
            if pr_res.success and pr_res.stdout.strip().startswith("{"):
                try:
                    data = json.loads(pr_res.stdout)
                    pr_number = data.get("number")
                    pr_url = data.get("url")
                    pr_state = data.get("state")
                except json.JSONDecodeError:
                    pass
            try:
                checks = self.get_pr_checks()
            except GitCommandError:
                checks = []

        all_green = bool(checks) and all(c.state.upper() in _GREEN_STATES for c in checks)
        return GitHubFlowStatus(
            branch_name=branch,
            is_feature_branch=is_feat,
            pr_number=pr_number,
            pr_url=pr_url,
            pr_state=pr_state,
            checks=checks,
            all_checks_green=all_green,
        )
