"""
Unit and CLI integration tests for Phantom Git's 5-Step GitHub Flow Engine:
1. Feature branch isolation (pgit flow start)
2. Local 3-pillar verification & strict commit guard (pgit commit --strict-flow)
3. Pull Request creation (pgit flow pr)
4. Remote CI check inspection & AI diagnostic log retrieval (pgit flow checks / logs)
5. Squash and Merge & return to main (pgit flow merge)
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from git_manager.cli import app
from git_manager.core import github_flow
from git_manager.core.env_manager import sync_env_example
from git_manager.core.git_driver import GitDriver
from git_manager.core.github_flow import GitHubFlowEngine, classify_ci_failure
from git_manager.core.models import (
    CIFailureCategory,
    CIPillarResult,
    CIPillarStatus,
    CIPreFlightReport,
    GitResult,
)
from tests.conftest import run_git

runner = CliRunner()


class TestGitHubFlowStart:
    """Tests for Step 1: start_feature."""

    def test_start_feature_creates_branch_and_syncs_base(
        self, temp_git_repo: Path, monkeypatch
    ) -> None:
        driver = GitDriver(temp_git_repo)
        orig_run = driver.run
        recorded_git_calls: list[list[str]] = []

        def fake_driver_run(args: list[str], **kwargs) -> GitResult:
            recorded_git_calls.append(args)
            if args == ["remote"]:
                return GitResult(
                    stdout="origin\n", exit_code=0, success=True, command=["git", *args]
                )
            if args[:2] == ["pull", "--rebase"]:
                return GitResult(
                    stdout="Already up to date.\n",
                    exit_code=0,
                    success=True,
                    command=["git", *args],
                )
            return orig_run(args, **kwargs)

        monkeypatch.setattr(driver, "run", fake_driver_run)
        engine = GitHubFlowEngine(driver)
        engine.start_feature("feat/user-auth")

        assert driver.get_current_branch() == "feat/user-auth"
        assert ["pull", "--rebase", "origin", "main"] in recorded_git_calls

    def test_start_feature_rejects_main_and_invalid_prefix(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        engine = GitHubFlowEngine(driver)

        with pytest.raises(ValueError, match="feature branch name"):
            engine.start_feature("main")

        with pytest.raises(ValueError):
            engine.start_feature("bad-no-prefix")

    def test_start_feature_preserves_dirty_files(self, dirty_git_repo: Path) -> None:
        driver = GitDriver(dirty_git_repo)
        engine = GitHubFlowEngine(driver)
        engine.start_feature("fix/dirty-preservation", sync_base=True)

        assert driver.get_current_branch() == "fix/dirty-preservation"
        assert (dirty_git_repo / "untracked.log").exists()


class TestGitHubFlowPRAndChecks:
    """Tests for Steps 3 & 4: open_pull_request, get_pr_checks, fetch_ci_failure_logs."""

    def test_open_pr_blocked_on_main(self, temp_git_repo: Path) -> None:
        engine = GitHubFlowEngine(GitDriver(temp_git_repo))
        with pytest.raises(ValueError, match="Cannot open a Pull Request from 'main'"):
            engine.open_pull_request(run_checks=False)

    def test_open_pr_blocked_when_preflight_fails(self, temp_git_repo: Path, monkeypatch) -> None:
        driver = GitDriver(temp_git_repo)
        driver.switch("feat/broken-build", create=True)
        engine = GitHubFlowEngine(driver)

        failing_report = CIPreFlightReport(
            repo_path=str(temp_git_repo),
            project_type="python",
            pillars=[
                CIPillarResult(
                    name="Code Quality & Type Integrity",
                    status=CIPillarStatus.FAILED,
                    output="ruff error",
                )
            ],
        )
        monkeypatch.setattr(github_flow, "run_ci_preflight", lambda path: failing_report)

        with pytest.raises(RuntimeError, match="3-pillar CI pre-flight failed"):
            engine.open_pull_request(title="feat: broken", run_checks=True)

    def test_open_pr_pushes_branch_and_calls_gh(self, temp_git_repo: Path, monkeypatch) -> None:
        driver = GitDriver(temp_git_repo)
        driver.switch("feat/oauth-login", create=True)
        (temp_git_repo / "auth.py").write_text("def login(): return True\n", encoding="utf-8")
        driver.stage(["auth.py"])
        driver.commit("feat(auth): add oauth login")

        orig_run = driver.run
        git_calls: list[list[str]] = []

        def fake_driver_run(args: list[str], **kwargs) -> GitResult:
            git_calls.append(args)
            if args[:3] == ["push", "-u", "origin"]:
                return GitResult(
                    stdout="branch 'feat/oauth-login' set up to track 'origin/feat/oauth-login'.",
                    exit_code=0,
                    success=True,
                    command=["git", *args],
                )
            return orig_run(args, **kwargs)

        monkeypatch.setattr(driver, "run", fake_driver_run)

        gh_calls: list[list[str]] = []

        def fake_gh(args: list[str], cwd: Path, timeout: int) -> GitResult:
            gh_calls.append(args)
            return GitResult(
                stdout="https://github.com/org/repo/pull/42\n",
                exit_code=0,
                success=True,
                command=["gh", *args],
            )

        engine = GitHubFlowEngine(driver, gh_runner=fake_gh)
        res = engine.open_pull_request(
            title="feat(auth): add oauth login",
            body="Implements OAuth login flow.",
            run_checks=False,
        )
        assert "pull/42" in res.stdout
        assert ["push", "-u", "origin", "feat/oauth-login"] in git_calls
        assert gh_calls[0][:3] == ["pr", "create", "--base"]
        assert "--head" in gh_calls[0]
        assert "feat/oauth-login" in gh_calls[0]

    def test_get_pr_checks_json_and_fallback(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        payload = json.dumps(
            [
                {
                    "name": "Code Quality & Type Integrity",
                    "state": "SUCCESS",
                    "link": "https://ci/1",
                },
                {"name": "Unit & Component Tests", "state": "FAILURE", "link": "https://ci/2"},
            ]
        )

        def fake_gh_json(args: list[str], cwd: Path, timeout: int) -> GitResult:
            return GitResult(stdout=payload, exit_code=1, success=False, command=["gh", *args])

        checks = GitHubFlowEngine(driver, gh_runner=fake_gh_json).get_pr_checks()
        assert len(checks) == 2
        assert checks[0].name == "Code Quality & Type Integrity"
        assert checks[0].state == "SUCCESS"
        assert checks[1].state == "FAILURE"

        def fake_gh_lines(args: list[str], cwd: Path, timeout: int) -> GitResult:
            return GitResult(
                stdout="Production Standalone Build\tpass\t12s\thttps://ci/3\n",
                exit_code=0,
                success=True,
                command=["gh", *args],
            )

        line_checks = GitHubFlowEngine(driver, gh_runner=fake_gh_lines).get_pr_checks()
        assert len(line_checks) == 1
        assert line_checks[0].name == "Production Standalone Build"
        assert line_checks[0].state == "PASS"

    def test_fetch_ci_failure_logs_writes_ai_report(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        driver.switch("fix/ci-bug", create=True)

        runs_json = json.dumps(
            [
                {
                    "databaseId": 98765,
                    "name": "CI",
                    "workflowName": "CI",
                    "status": "completed",
                    "conclusion": "failure",
                    "url": "https://github.com/org/repo/actions/runs/98765",
                }
            ]
        )

        def fake_gh(args: list[str], cwd: Path, timeout: int) -> GitResult:
            if args[0] == "run" and args[1] == "list":
                return GitResult(stdout=runs_json, exit_code=0, success=True, command=["gh", *args])
            if args[0] == "run" and args[1] == "view":
                return GitResult(
                    stdout="Unit & Component Tests\nAssertionError: expected 200 got 500\n",
                    exit_code=0,
                    success=True,
                    command=["gh", *args],
                )
            return GitResult(exit_code=1, success=False, command=["gh", *args])

        engine = GitHubFlowEngine(driver, gh_runner=fake_gh)
        report = engine.fetch_ci_failure_logs()

        assert "AI Diagnostic CI Failure Report" in report
        assert "Unit & Component Tests" in report
        assert "AssertionError: expected 200 got 500" in report
        saved_file = temp_git_repo / ".phantom-git" / "last-ci-failure.md"
        assert saved_file.exists()
        assert "98765" in saved_file.read_text(encoding="utf-8")


class TestGitHubFlowMerge:
    """Tests for Step 5: squash_and_merge."""

    def test_merge_blocked_when_checks_fail(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        driver.switch("feat/unverified", create=True)

        fail_checks = json.dumps([{"name": "Unit & Component Tests", "state": "FAILURE"}])

        def fake_gh(args: list[str], cwd: Path, timeout: int) -> GitResult:
            return GitResult(stdout=fail_checks, exit_code=1, success=False, command=["gh", *args])

        engine = GitHubFlowEngine(driver, gh_runner=fake_gh)
        with pytest.raises(RuntimeError, match="Cannot merge PR while checks are not green"):
            engine.squash_and_merge(auto_merge=False)

    def test_squash_and_merge_switches_back_to_main(self, temp_git_repo: Path, monkeypatch) -> None:
        driver = GitDriver(temp_git_repo)
        driver.switch("feat/clean-pr", create=True)

        orig_run = driver.run
        git_calls: list[list[str]] = []

        def fake_driver_run(args: list[str], **kwargs) -> GitResult:
            git_calls.append(args)
            if args == ["remote"]:
                return GitResult(
                    stdout="origin\n", exit_code=0, success=True, command=["git", *args]
                )
            if args[:2] == ["pull", "--rebase"]:
                return GitResult(
                    stdout="Updating main..\n",
                    exit_code=0,
                    success=True,
                    command=["git", *args],
                )
            return orig_run(args, **kwargs)

        monkeypatch.setattr(driver, "run", fake_driver_run)

        calls: list[list[str]] = []

        def fake_gh(args: list[str], cwd: Path, timeout: int) -> GitResult:
            calls.append(args)
            if args[:2] == ["pr", "checks"]:
                return GitResult(
                    stdout=json.dumps([{"name": "CI", "state": "SUCCESS"}]),
                    exit_code=0,
                    success=True,
                    command=["gh", *args],
                )
            if args[:2] == ["pr", "merge"]:
                return GitResult(stdout="Merged!", exit_code=0, success=True, command=["gh", *args])
            return GitResult(exit_code=0, success=True, command=["gh", *args])

        engine = GitHubFlowEngine(driver, gh_runner=fake_gh)
        engine.squash_and_merge()

        assert driver.get_current_branch() == "main"
        assert ["pull", "--rebase", "origin", "main"] in git_calls
        merge_call = next(c for c in calls if c[:2] == ["pr", "merge"])
        assert "--squash" in merge_call
        assert "--delete-branch" in merge_call


class TestGitHubFlowCLI:
    """CLI tests for `pgit flow ...` and `pgit commit --strict-flow`."""

    def test_commit_strict_flow_blocks_main_and_allows_feature(self, temp_git_repo: Path) -> None:
        (temp_git_repo / "file.txt").write_text("hello", encoding="utf-8")
        run_git(["add", "file.txt"], cwd=temp_git_repo)

        blocked = runner.invoke(
            app,
            [
                "commit",
                "-t",
                "feat",
                "-m",
                "direct main commit",
                "--strict-flow",
                "--path",
                str(temp_git_repo),
            ],
        )
        assert blocked.exit_code == 1
        assert "Main Branch Protected" in blocked.output

        # Start feature branch via CLI and commit
        start_res = runner.invoke(
            app,
            ["flow", "start", "feat/strict-ok", "--no-sync", "--path", str(temp_git_repo)],
        )
        assert start_res.exit_code == 0

        ok_res = runner.invoke(
            app,
            [
                "commit",
                "-t",
                "feat",
                "-m",
                "feature commit",
                "--strict-flow",
                "--path",
                str(temp_git_repo),
            ],
        )
        assert ok_res.exit_code == 0
        assert "Committed: feat: feature commit" in ok_res.output

    def test_flow_checks_and_logs_cli(self, temp_git_repo: Path, monkeypatch) -> None:
        driver = GitDriver(temp_git_repo)
        driver.switch("feat/cli-flow", create=True)

        runs_json = json.dumps(
            [{"databaseId": 555, "name": "CI", "status": "completed", "conclusion": "failure"}]
        )
        checks_json = json.dumps(
            [{"name": "Production Standalone Build", "state": "FAILURE", "link": "https://ci/555"}]
        )

        def fake_gh_runner(
            self, args: list[str], check: bool = True, timeout: int = 30
        ) -> GitResult:
            if args[:2] == ["pr", "checks"]:
                return GitResult(
                    stdout=checks_json, exit_code=1, success=False, command=["gh", *args]
                )
            if args[:2] == ["run", "list"]:
                return GitResult(stdout=runs_json, exit_code=0, success=True, command=["gh", *args])
            if args[:2] == ["run", "view"]:
                return GitResult(
                    stdout="Production Standalone Build\nSyntaxError in build",
                    exit_code=0,
                    success=True,
                    command=["gh", *args],
                )
            return GitResult(stdout="", exit_code=0, success=True, command=["gh", *args])

        monkeypatch.setattr(GitHubFlowEngine, "run_gh", fake_gh_runner)

        checks_res = runner.invoke(app, ["flow", "checks", "--path", str(temp_git_repo)])
        assert checks_res.exit_code == 0
        assert "Production Standalone Build" in checks_res.output
        assert "FAILURE" in checks_res.output

        logs_res = runner.invoke(app, ["flow", "logs", "--path", str(temp_git_repo)])
        assert logs_res.exit_code == 0
        assert "AI Diagnostic CI Failure Report" in logs_res.output
        assert "SyntaxError in build" in logs_res.output


class TestStagingPromotionAndClassifier:
    """Tests for 3-branch (staging -> main) flow, promotion, CI classifier, and env hygiene."""

    def test_init_branches_and_auto_target_staging(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        engine = GitHubFlowEngine(driver)

        res = engine.init_branches(push_remote=False)
        assert res["created_staging"] is True
        assert engine.resolve_default_base_branch() == "staging"

        # Starting a feature branch now branches cleanly off staging
        engine.start_feature("feat/staging-base", sync_base=True)
        assert driver.get_current_branch() == "feat/staging-base"

    def test_promote_staging_to_main_uses_merge_commit(
        self, temp_git_repo: Path, monkeypatch
    ) -> None:
        driver = GitDriver(temp_git_repo)
        run_git(["branch", "staging", "main"], cwd=temp_git_repo)
        driver.switch("staging", create=False)
        (temp_git_repo / "staging_feat.txt").write_text("ready for prod", encoding="utf-8")
        driver.stage(["staging_feat.txt"])
        driver.commit("feat: staging verified release")

        orig_run = driver.run

        def fake_driver_run(args: list[str], **kwargs) -> GitResult:
            if args == ["remote"]:
                return GitResult(
                    stdout="origin\n", exit_code=0, success=True, command=["git", *args]
                )
            if args[:3] == ["push", "-u", "origin"]:
                return GitResult(stdout="pushed", exit_code=0, success=True, command=["git", *args])
            if args[:2] == ["pull", "--rebase"]:
                return GitResult(
                    stdout="up to date", exit_code=0, success=True, command=["git", *args]
                )
            return orig_run(args, **kwargs)

        monkeypatch.setattr(driver, "run", fake_driver_run)

        gh_calls: list[list[str]] = []

        def fake_gh(args: list[str], cwd: Path, timeout: int) -> GitResult:
            gh_calls.append(args)
            if args[:2] == ["pr", "list"]:
                return GitResult(stdout="[]", exit_code=0, success=True, command=["gh", *args])
            if args[:2] == ["pr", "create"]:
                return GitResult(
                    stdout="https://github.com/org/repo/pull/99",
                    exit_code=0,
                    success=True,
                    command=["gh", *args],
                )
            if args[:2] == ["pr", "checks"]:
                return GitResult(
                    stdout=json.dumps([{"name": "CI", "state": "SUCCESS"}]),
                    exit_code=0,
                    success=True,
                    command=["gh", *args],
                )
            if args[:2] == ["pr", "merge"]:
                return GitResult(stdout="Merged!", exit_code=0, success=True, command=["gh", *args])
            return GitResult(exit_code=0, success=True, command=["gh", *args])

        engine = GitHubFlowEngine(driver, gh_runner=fake_gh)
        out = engine.promote_staging_to_main()

        assert out["merged"] is True
        assert out["merge_strategy"] == "merge"
        assert driver.get_current_branch() == "main"
        merge_cmd = next(c for c in gh_calls if c[:2] == ["pr", "merge"])
        assert "--merge" in merge_cmd
        assert "--squash" not in merge_cmd
        assert "--delete-branch" not in merge_cmd

    def test_classify_ci_failure_categories(self) -> None:
        cat_env, rem_env, keys = classify_ci_failure(
            "Error: Missing required environment variable: SUPABASE_SERVICE_ROLE_KEY in process.env.OPENAI_API_KEY"
        )
        assert cat_env == CIFailureCategory.MISSING_ENV_OR_SECRET
        assert "SUPABASE_SERVICE_ROLE_KEY" in keys
        assert "pgit env set" in rem_env

        cat_test, _, files = classify_ci_failure(
            "FAIL src/components/Hero.test.tsx\nTestingLibraryElementError: Unable to find an element with the text"
        )
        assert cat_test == CIFailureCategory.STALE_TEST_FAILURE
        assert "src/components/Hero.test.tsx" in files

        cat_type, _, _ = classify_ci_failure(
            "src/app/page.tsx(14,5): error TS2322: Type 'string' is not assignable to type 'number'."
        )
        assert cat_type == CIFailureCategory.TYPE_OR_LINT_ERROR

    def test_env_sync_and_cli_env_set(self, temp_git_repo: Path, monkeypatch) -> None:
        (temp_git_repo / ".env.local").write_text(
            "OPENAI_API_KEY=sk-secret-do-not-copy\nDATABASE_URL=postgres://localhost/db\n",
            encoding="utf-8",
        )
        src_dir = temp_git_repo / "src"
        src_dir.mkdir()
        (src_dir / "config.ts").write_text(
            "export const url = process.env.NEXT_PUBLIC_APP_URL;",
            encoding="utf-8",
        )

        report = sync_env_example(temp_git_repo)
        assert "OPENAI_API_KEY" in report.added_keys
        assert "DATABASE_URL" in report.added_keys
        assert "NEXT_PUBLIC_APP_URL" in report.added_keys

        example_txt = (temp_git_repo / ".env.example").read_text(encoding="utf-8")
        assert "OPENAI_API_KEY=" in example_txt
        assert "sk-secret-do-not-copy" not in example_txt

        # Test `pgit env sync` and `pgit env set` CLI
        sync_res = runner.invoke(app, ["env", "sync", "--path", str(temp_git_repo)])
        assert sync_res.exit_code == 0
        assert "already up to date" in sync_res.output

        captured: list[list[str]] = []

        def fake_run_gh(self, args: list[str], check: bool = True, timeout: int = 30) -> GitResult:
            captured.append(args)
            return GitResult(stdout="", exit_code=0, success=True, command=["gh", *args])

        monkeypatch.setattr(GitHubFlowEngine, "run_gh", fake_run_gh)
        set_res = runner.invoke(
            app,
            [
                "env",
                "set",
                "STRIPE_KEY",
                "rk_test_123",
                "--env",
                "staging",
                "--path",
                str(temp_git_repo),
            ],
        )
        assert set_res.exit_code == 0
        assert [
            "secret",
            "set",
            "STRIPE_KEY",
            "--body",
            "rk_test_123",
            "--env",
            "staging",
        ] in captured
