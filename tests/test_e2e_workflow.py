"""
End-to-End Integration and Real-World Workflow Simulation Suite for git-mgr.
Validates the complete single-repo developer lifecycle (scaffolding, branching,
dirty state detection, snapshot bookmarks, stash context switching, conventional
commits, safety net undo rollbacks) and multi-repo ecosystem operations
(discovery, health auditing, protected bulk linear rebase synchronization).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typer.testing import CliRunner

from git_manager.cli import app
from git_manager.core.git_driver import GitDriver
from git_manager.core.models import RepoHealthStatus
from git_manager.core.safety_net import SafetyNet
from git_manager.multirepo.health_check import audit_repositories
from git_manager.multirepo.scanner import discover_repositories
from tests.conftest import run_git

runner = CliRunner()


def _init_local_repo(repo_path: Path) -> GitDriver:
    """Helper to initialize an isolated git repo with configured dummy user and initial commit."""
    repo_path.mkdir(parents=True, exist_ok=True)
    run_git(["init", "-b", "main"], cwd=repo_path)
    run_git(["config", "user.name", "Test User"], cwd=repo_path)
    run_git(["config", "user.email", "test@example.com"], cwd=repo_path)
    run_git(["config", "commit.gpgsign", "false"], cwd=repo_path)

    readme = repo_path / "README.md"
    readme.write_text("# Sample Project\n\nInitial repository baseline.", encoding="utf-8")
    run_git(["add", "README.md"], cwd=repo_path)
    run_git(["commit", "-m", "chore: initialize repository"], cwd=repo_path)
    return GitDriver(repo_path)


class TestE2ESingleRepoLifecycleWorkflow:
    """
    Comprehensive End-to-End single-repository integration workflow simulation.
    Covers the 10-step full developer/agent lifecycle:
    1. Initialize temporary Git repository.
    2. Run 'git-mgr scaffold init' (scaffolding 3 layers + AI .gitignore).
    3. Verify standard configuration files exist on disk.
    4. Stage and commit scaffolded files via Conventional Commits.
    5. Create and switch to feature branch 'feat/login-endpoint'.
    6. Modify tracked file and create untracked scratch file; verify status is DIRTY.
    7. Create safety bookmark snapshot 'before-experiment'.
    8. Test stash context switching with untracked files guaranteed and restore via pop.
    9. Stage and commit feature via 'git-mgr commit -t feat -m "add login endpoint"'.
    10. Test Safety Net rollback via 'git-mgr undo --force', verifying HEAD state is restored
        and the pre-experiment snapshot remains intact.
    """

    def test_full_single_repo_lifecycle(self, tmp_path: Path) -> None:
        """Execute full 10-step end-to-end single-repo lifecycle simulation."""
        repo_dir = tmp_path / "e2e_single_repo"
        driver = _init_local_repo(repo_dir)

        # --------------------------------------------------------------------
        # Step 1: Verify Initial Clean Baseline
        # --------------------------------------------------------------------
        status_init = driver.get_status()
        assert status_init.is_clean is True
        assert status_init.branch_name == "main"

        # --------------------------------------------------------------------
        # Step 2: Run 'git-mgr scaffold init'
        # --------------------------------------------------------------------
        res_scaffold = runner.invoke(
            app,
            [
                "scaffold",
                "init",
                "--project-name",
                "auth-service",
                "--project-type",
                "python",
                "--path",
                str(repo_dir),
            ],
        )
        assert res_scaffold.exit_code == 0, f"Scaffold failed: {res_scaffold.output}"
        assert "Created" in res_scaffold.output

        # --------------------------------------------------------------------
        # Step 3: Verify scaffolded files exist on disk
        # --------------------------------------------------------------------
        expected_files = [
            repo_dir / "lefthook.yml",
            repo_dir / ".pre-commit-config.yaml",
            repo_dir / ".github" / "workflows" / "ci.yml",
            repo_dir / ".github" / "workflows" / "security.yml",
            repo_dir / ".github" / "workflows" / "release-please.yml",
            repo_dir / "release-please-config.json",
            repo_dir / ".release-please-manifest.json",
            repo_dir / ".gitignore",
        ]
        for fpath in expected_files:
            assert fpath.exists(), f"Expected scaffolded file missing: {fpath}"

        # Verify AI .gitignore patterns exist
        gitignore_content = (repo_dir / ".gitignore").read_text(encoding="utf-8")
        assert ".gemini/" in gitignore_content
        assert ".antigravity/" in gitignore_content

        # --------------------------------------------------------------------
        # Step 4: Stage and commit scaffolded files using git-mgr commit
        # --------------------------------------------------------------------
        run_git(["add", "-A"], cwd=repo_dir)

        res_commit_scaffold = runner.invoke(
            app,
            [
                "commit",
                "-t",
                "chore",
                "-m",
                "scaffold 3-layer automation guardrails",
                "--path",
                str(repo_dir),
            ],
        )
        assert res_commit_scaffold.exit_code == 0, f"Commit failed: {res_commit_scaffold.output}"
        assert "Committed" in res_commit_scaffold.output

        # Verify latest commit subject
        latest_subject = driver.run(["log", "-1", "--format=%s"]).stdout.strip()
        assert latest_subject == "chore: scaffold 3-layer automation guardrails"
        assert driver.get_status().is_clean is True

        # --------------------------------------------------------------------
        # Step 5: Create and switch to feature branch
        # --------------------------------------------------------------------
        branch_name = "feat/login-endpoint"
        res_branch = runner.invoke(
            app,
            ["branch", branch_name, "--path", str(repo_dir)],
        )
        assert res_branch.exit_code == 0, f"Branch switch failed: {res_branch.output}"
        assert f"Successfully switched to branch '{branch_name}'" in res_branch.output
        assert driver.get_current_branch() == branch_name

        # --------------------------------------------------------------------
        # Step 6: Modify tracked file, create untracked scratch file, verify DIRTY
        # --------------------------------------------------------------------
        readme = repo_dir / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8")
            + "\n\n## Login Endpoint Documentation\nEndpoints: POST /api/v1/login",
            encoding="utf-8",
        )

        scratch_file = repo_dir / "agent_scratch_experiment.py"
        scratch_file.write_text("# Scratchpad code generated by agent", encoding="utf-8")

        res_status = runner.invoke(app, ["status", str(repo_dir)])
        assert res_status.exit_code == 0
        assert "DIRTY" in res_status.output
        assert "README.md" in res_status.output
        assert "agent_scratch_experiment.py" in res_status.output

        # --------------------------------------------------------------------
        # Step 7: Create safety snapshot "before-experiment"
        # --------------------------------------------------------------------
        res_snapshot = runner.invoke(
            app,
            ["snapshot", "before-experiment", "--path", str(repo_dir)],
        )
        assert res_snapshot.exit_code == 0, f"Snapshot failed: {res_snapshot.output}"
        assert "Created safety bookmark 'before-experiment'" in res_snapshot.output

        safety = SafetyNet(driver)
        snapshots = safety.list_snapshots()
        assert any("before-experiment" in s.label for s in snapshots)

        # --------------------------------------------------------------------
        # Step 8: Test stash context switching with untracked files guaranteed
        # --------------------------------------------------------------------
        res_stash_save = runner.invoke(
            app,
            ["stash", "save", "-m", "wip login endpoint experiment", "--path", str(repo_dir)],
        )
        assert res_stash_save.exit_code == 0, f"Stash save failed: {res_stash_save.output}"
        assert "Stash saved" in res_stash_save.output

        # Working tree must now be completely clean and untracked file stashed away
        assert driver.get_status().is_clean is True
        assert not scratch_file.exists(), "Untracked file must be removed by stash -u"

        # Pop stash to restore context
        res_stash_pop = runner.invoke(
            app,
            ["stash", "pop", "--path", str(repo_dir)],
        )
        assert res_stash_pop.exit_code == 0, f"Stash pop failed: {res_stash_pop.output}"
        assert "Stash applied and removed from stash list" in res_stash_pop.output

        # Scratch file must be restored and status dirty again
        assert scratch_file.exists(), "Untracked file must be restored after stash pop"
        assert driver.get_status().is_clean is False

        # --------------------------------------------------------------------
        # Step 9: Stage changes and commit feature
        # --------------------------------------------------------------------
        run_git(["add", "-A"], cwd=repo_dir)

        pre_commit_head = driver.run(["rev-parse", "HEAD"]).stdout.strip()
        res_commit_feat = runner.invoke(
            app,
            [
                "commit",
                "-t",
                "feat",
                "-m",
                "add login endpoint authentication",
                "--path",
                str(repo_dir),
            ],
        )
        assert res_commit_feat.exit_code == 0, f"Commit feat failed: {res_commit_feat.output}"
        assert "add login endpoint authentication" in res_commit_feat.output

        post_commit_head = driver.run(["rev-parse", "HEAD"]).stdout.strip()
        assert post_commit_head != pre_commit_head
        assert (
            driver.run(["log", "-1", "--format=%s"]).stdout.strip()
            == "feat: add login endpoint authentication"
        )

        # --------------------------------------------------------------------
        # Step 10: Test Safety Net rollback via 'git-mgr undo --force'
        # --------------------------------------------------------------------
        res_undo = runner.invoke(
            app,
            ["undo", "--force", "--path", str(repo_dir)],
        )
        assert res_undo.exit_code == 0, f"Undo failed: {res_undo.output}"
        assert "Safely reverted state back" in res_undo.output

        # HEAD must be restored to pre-commit commit SHA
        restored_head = driver.run(["rev-parse", "HEAD"]).stdout.strip()
        assert restored_head == pre_commit_head

        # Snapshot created in Step 7 remains fully accessible
        post_undo_snapshots = safety.list_snapshots()
        assert any("before-experiment" in s.label for s in post_undo_snapshots)


class TestE2EMultiRepoEcosystemSimulation:
    """
    Real-world multi-repo workspace simulation representing typical Project Archive layout:
    - Root Workspace containing 3 repositories:
      1. Repo 1 (Clean, synced with remote tracking branch)
      2. Repo 2 (Dirty with uncommitted agent scratch files)
      3. Repo 3 (Clean, ahead of remote tracking branch by 1 commit)
    - Verifies 'git-mgr scan' accurately detects all repositories and health categories.
    - Verifies 'git-mgr sync-all' safely rebases clean tracking repos, skips dirty repos
      without data loss, and maintains workspace integrity.
    """

    def test_multirepo_scan_and_sync_ecosystem(self, tmp_path: Path) -> None:
        """Execute full multi-repo discovery, health audit, and safe rebase sync simulation."""
        workspace_dir = tmp_path / "Project_Archive_Workspace"
        workspace_dir.mkdir(parents=True)

        # 1. Setup shared upstream remote
        upstream_dir = tmp_path / "upstream_repo"
        upstream_driver = _init_local_repo(upstream_dir)

        # --------------------------------------------------------------------
        # Setup Repo 1: Clean, synced with remote
        # --------------------------------------------------------------------
        repo1_dir = workspace_dir / "service-payment"
        run_git(["clone", str(upstream_dir), str(repo1_dir)], cwd=tmp_path)
        repo1_driver = GitDriver(repo1_dir)
        repo1_driver.run(["config", "user.name", "Test User"])
        repo1_driver.run(["config", "user.email", "test@example.com"])

        # --------------------------------------------------------------------
        # Setup Repo 2: Dirty with untracked agent files
        # --------------------------------------------------------------------
        repo2_dir = workspace_dir / "service-user"
        run_git(["clone", str(upstream_dir), str(repo2_dir)], cwd=tmp_path)
        repo2_driver = GitDriver(repo2_dir)
        repo2_driver.run(["config", "user.name", "Test User"])
        repo2_driver.run(["config", "user.email", "test@example.com"])

        # Create uncommitted dirty changes and untracked agent files
        (repo2_dir / "README.md").write_text("Unstaged modification by agent.", encoding="utf-8")
        untracked_agent_file = repo2_dir / "agent_notes.scratch"
        untracked_agent_file.write_text(
            "Critical uncommitted agent scratchpad data", encoding="utf-8"
        )

        # --------------------------------------------------------------------
        # Setup Repo 3: Clean, ahead of remote tracking branch
        # --------------------------------------------------------------------
        repo3_dir = workspace_dir / "service-notification"
        run_git(["clone", str(upstream_dir), str(repo3_dir)], cwd=tmp_path)
        repo3_driver = GitDriver(repo3_dir)
        repo3_driver.run(["config", "user.name", "Test User"])
        repo3_driver.run(["config", "user.email", "test@example.com"])

        # Make local commit ahead of origin
        (repo3_dir / "notifier.py").write_text("def notify(): pass\n", encoding="utf-8")
        repo3_driver.run(["add", "notifier.py"])
        repo3_driver.run(["commit", "-m", "feat: implement notification dispatcher"])

        # --------------------------------------------------------------------
        # Step A: Run 'git-mgr scan' and verify all 3 repositories and health
        # --------------------------------------------------------------------
        res_scan = runner.invoke(app, ["scan", str(workspace_dir)])
        assert res_scan.exit_code == 0, f"Scan command failed: {res_scan.output}"
        assert "Multi-Repo Health Dashboard" in res_scan.output
        assert "service-payment" in res_scan.output
        assert "service-user" in res_scan.output
        assert "service-notification" in res_scan.output

        # Programmatic audit verification
        discovered = discover_repositories(workspace_dir)
        assert len(discovered) == 3
        health_map = {h.name: h for h in audit_repositories(discovered)}

        assert "service-payment" in health_map
        assert "service-user" in health_map
        assert "service-notification" in health_map

        assert health_map["service-payment"].status == RepoHealthStatus.CLEAN
        assert health_map["service-payment"].is_clean is True

        assert health_map["service-user"].status == RepoHealthStatus.DIRTY
        assert health_map["service-user"].is_clean is False
        assert health_map["service-user"].untracked_count >= 1

        assert health_map["service-notification"].status == RepoHealthStatus.AHEAD
        assert health_map["service-notification"].ahead_count == 1
        assert health_map["service-notification"].behind_count == 0

        # --------------------------------------------------------------------
        # Step B: Add new upstream commit to verify linear rebase in Repo 1
        # --------------------------------------------------------------------
        (upstream_dir / "shared_schema.sql").write_text(
            "CREATE TABLE upstream (id INT);", encoding="utf-8"
        )
        upstream_driver.run(["add", "shared_schema.sql"])
        upstream_driver.run(["commit", "-m", "feat: add upstream shared schema"])

        # --------------------------------------------------------------------
        # Step C: Run 'git-mgr sync-all' and verify synchronization guarantees
        # --------------------------------------------------------------------
        res_sync_all = runner.invoke(app, ["sync-all", str(workspace_dir)])
        assert res_sync_all.exit_code == 0, f"Sync-all failed: {res_sync_all.output}"
        assert "Sync Summary" in res_sync_all.output

        # Verify Repo 1 pulled upstream commit via linear rebase
        assert (repo1_dir / "shared_schema.sql").exists(), "Repo 1 must have pulled upstream change"
        assert repo1_driver.get_status().is_clean is True

        # Verify Repo 2 was safely skipped (SKIPPED_DIRTY) with zero data loss
        assert untracked_agent_file.exists(), "Untracked file in dirty repo must NOT be deleted"
        assert (
            untracked_agent_file.read_text(encoding="utf-8")
            == "Critical uncommitted agent scratchpad data"
        )
        assert "Unstaged modification by agent." in (repo2_dir / "README.md").read_text(
            encoding="utf-8"
        )
        assert repo2_driver.get_status().is_clean is False

        # Verify Repo 3 remains ahead without corrupting local commits
        assert (repo3_dir / "notifier.py").exists()
        assert (
            repo3_driver.run(["log", "-1", "--format=%s"]).stdout.strip()
            == "feat: implement notification dispatcher"
        )

    def test_multirepo_sync_dry_run_leaves_disk_untouched(self, tmp_path: Path) -> None:
        """Verify 'git-mgr sync-all --dry-run' previews sync actions without mutating working trees."""
        workspace_dir = tmp_path / "DryRun_Workspace"
        workspace_dir.mkdir(parents=True)

        upstream_dir = tmp_path / "upstream_repo_dry"
        upstream_driver = _init_local_repo(upstream_dir)

        downstream_dir = workspace_dir / "service-analytics"
        run_git(["clone", str(upstream_dir), str(downstream_dir)], cwd=tmp_path)
        downstream_driver = GitDriver(downstream_dir)
        downstream_driver.run(["config", "user.name", "Test User"])
        downstream_driver.run(["config", "user.email", "test@example.com"])

        # Create upstream change
        (upstream_dir / "analytics_schema.json").write_text('{"v": 1}', encoding="utf-8")
        upstream_driver.run(["add", "analytics_schema.json"])
        upstream_driver.run(["commit", "-m", "feat: add analytics schema"])

        # Run sync-all with --dry-run
        res_dry = runner.invoke(app, ["sync-all", "--dry-run", str(workspace_dir)])
        assert res_dry.exit_code == 0
        assert "Sync Summary" in res_dry.output

        # Verify downstream repo did NOT pull the file yet
        assert not (downstream_dir / "analytics_schema.json").exists()


class TestE2EAutoCommitAndLinearLog:
    """
    End-to-end integration test validating heuristic Conventional Commit analysis (--auto)
    and linear log visualization (log-linear) with badges.
    """

    def test_auto_commit_heuristic_and_linear_log_render(self, tmp_path: Path) -> None:
        """Verify --auto analyzes staged diffs correctly and log-linear renders formatted table."""
        repo_dir = tmp_path / "auto_commit_repo"
        driver = _init_local_repo(repo_dir)

        # 1. Feature commit via --auto
        feature_code = repo_dir / "src" / "billing" / "invoice.py"
        feature_code.parent.mkdir(parents=True, exist_ok=True)
        feature_code.write_text("class Invoice:\n    pass\n", encoding="utf-8")
        run_git(["add", "-A"], cwd=repo_dir)

        res_auto_feat = runner.invoke(app, ["commit", "--auto", "--path", str(repo_dir)])
        assert res_auto_feat.exit_code == 0
        assert "Committed" in res_auto_feat.output
        feat_subject = driver.run(["log", "-1", "--format=%s"]).stdout.strip()
        assert feat_subject.startswith("feat")
        assert "implement updates" in feat_subject

        # 2. Docs commit via --auto
        docs_file = repo_dir / "docs" / "architecture.md"
        docs_file.parent.mkdir(parents=True, exist_ok=True)
        docs_file.write_text("# Architecture Guide\nDetails here.", encoding="utf-8")
        run_git(["add", "-A"], cwd=repo_dir)

        res_auto_docs = runner.invoke(app, ["commit", "--auto", "--path", str(repo_dir)])
        assert res_auto_docs.exit_code == 0
        docs_subject = driver.run(["log", "-1", "--format=%s"]).stdout.strip()
        assert docs_subject.startswith("docs")

        # 3. Test log-linear output
        res_log = runner.invoke(app, ["log-linear", "--path", str(repo_dir)])
        assert res_log.exit_code == 0
        assert "Linear Commit History" in res_log.output
        assert "feat" in res_log.output
        assert "docs" in res_log.output


class TestE2EStandaloneBinaryVerification:
    """
    Verification of standalone packaging CLI entrypoint execution directly from terminal shell.
    Tests 'git-mgr --help', 'git-mgr --version', and execution without Python interpreter wrapper.
    """

    def test_standalone_cli_help(self) -> None:
        """Verify git-mgr executable runs directly and outputs Typer command reference."""
        # Use python executable's Scripts directory or entry point
        env = os.environ.copy()
        python_scripts = Path(os.sys.executable).parent / "Scripts"
        env["PATH"] = f"{python_scripts}{os.pathsep}{env.get('PATH', '')}"

        # Test standalone invocation
        cmd = ["git-mgr", "--help"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
            env=env,
        )
        assert proc.returncode == 0
        assert "git-mgr" in proc.stdout
        assert "status" in proc.stdout
        assert "branch" in proc.stdout
        assert "commit" in proc.stdout
        assert "snapshot" in proc.stdout
        assert "undo" in proc.stdout
        assert "scaffold" in proc.stdout
        assert "scan" in proc.stdout
        assert "sync-all" in proc.stdout

    def test_standalone_cli_version(self) -> None:
        """Verify git-mgr --version prints version string."""
        env = os.environ.copy()
        python_scripts = Path(os.sys.executable).parent / "Scripts"
        env["PATH"] = f"{python_scripts}{os.pathsep}{env.get('PATH', '')}"

        proc = subprocess.run(
            ["git-mgr", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
            env=env,
        )
        assert proc.returncode == 0
        assert "git-mgr" in proc.stdout
        assert "version" in proc.stdout
