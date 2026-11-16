"""
Unit and CLI integration tests for Phantom Git's 3-Pillar CI Pre-Flight Validator:
1. Code Quality & Type Integrity
2. Unit & Component Tests
3. Production Standalone Build
"""

from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner

from git_manager.cli import app
from git_manager.core import ci_checks
from git_manager.core.ci_checks import (
    PILLAR_BUILD,
    PILLAR_QUALITY,
    PILLAR_TESTS,
    CIPreFlightRunner,
    detect_project_type,
    run_ci_preflight,
)
from git_manager.core.models import (
    CIPillarResult,
    CIPillarStatus,
    CIPreFlightReport,
    GitResult,
    TestingTier,
)

runner = CliRunner()


class TestDetectProjectType:
    """Tests for ecosystem auto-detection."""

    def test_detect_python_variants(self, tmp_path: Path) -> None:
        p1 = tmp_path / "py_pyproject"
        p1.mkdir()
        (p1 / "pyproject.toml").write_text("[project]\nname='a'\n", encoding="utf-8")
        assert detect_project_type(p1) == "python"

        p2 = tmp_path / "py_setup"
        p2.mkdir()
        (p2 / "setup.py").write_text("", encoding="utf-8")
        assert detect_project_type(p2) == "python"

        p3 = tmp_path / "py_reqs"
        p3.mkdir()
        (p3 / "requirements.txt").write_text("typer\n", encoding="utf-8")
        assert detect_project_type(p3) == "python"

    def test_detect_node_and_unknown(self, tmp_path: Path) -> None:
        node_dir = tmp_path / "node_app"
        node_dir.mkdir()
        (node_dir / "package.json").write_text('{"name": "app"}', encoding="utf-8")
        assert detect_project_type(node_dir) == "node"

        empty_dir = tmp_path / "unknown"
        empty_dir.mkdir()
        assert detect_project_type(empty_dir) == "unknown"


class TestPythonCIPreFlight:
    """Tests for Python 3-pillar execution with deterministic runners and real compileall."""

    def test_python_all_pillars_pass(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        (tmp_path / "src").mkdir()
        recorded: list[list[str]] = []

        def fake_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
            recorded.append(cmd)
            return GitResult(stdout="ok", exit_code=0, success=True, command=cmd)

        report = run_ci_preflight(tmp_path, command_runner=fake_runner)
        assert report.project_type == "python"
        assert report.passed is True
        assert len(report.pillars) == 3
        assert [p.name for p in report.pillars] == [PILLAR_QUALITY, PILLAR_TESTS, PILLAR_BUILD]
        assert all(p.status == CIPillarStatus.PASSED for p in report.pillars)

        cmd_joined = [" ".join(c) for c in recorded]
        assert any("ruff check ." in c for c in cmd_joined)
        assert any("ruff format --check ." in c for c in cmd_joined)
        assert any("pytest -q" in c for c in cmd_joined)
        assert any("compileall -q src" in c for c in cmd_joined)

    def test_python_mypy_invoked_when_configured_and_installed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n", encoding="utf-8")
        recorded: list[list[str]] = []

        def fake_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
            recorded.append(cmd)
            return GitResult(stdout="ok", exit_code=0, success=True, command=cmd)

        monkeypatch.setattr(ci_checks.importlib.util, "find_spec", lambda name: object())
        report = CIPreFlightRunner(tmp_path, command_runner=fake_runner).run_all()
        assert report.passed is True
        assert any("mypy ." in " ".join(c) for c in recorded)

    def test_python_quality_failure_marks_report_failed(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

        def fake_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
            if "ruff" in cmd and "check" in cmd:
                return GitResult(
                    stdout="src/app.py:1:1: F401 unused import",
                    exit_code=1,
                    success=False,
                    command=cmd,
                )
            return GitResult(stdout="ok", exit_code=0, success=True, command=cmd)

        report = run_ci_preflight(tmp_path, command_runner=fake_runner)
        assert report.passed is False
        assert report.pillars[0].status == CIPillarStatus.FAILED
        assert "F401" in report.pillars[0].output

    def test_python_pytest_exit_code_5_treated_as_passed(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

        def fake_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
            if "pytest" in cmd:
                return GitResult(
                    stdout="no tests ran",
                    exit_code=5,
                    success=False,
                    command=cmd,
                )
            return GitResult(stdout="ok", exit_code=0, success=True, command=cmd)

        report = run_ci_preflight(tmp_path, command_runner=fake_runner)
        assert report.passed is True
        assert report.pillars[1].status == CIPillarStatus.PASSED
        assert "exit code 5" in report.pillars[1].output

    def test_python_pytest_failure_marks_failed(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

        def fake_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
            if "pytest" in cmd:
                return GitResult(
                    stdout="1 failed in 0.1s",
                    exit_code=1,
                    success=False,
                    command=cmd,
                )
            return GitResult(stdout="ok", exit_code=0, success=True, command=cmd)

        report = run_ci_preflight(tmp_path, command_runner=fake_runner)
        assert report.passed is False
        assert report.pillars[1].status == CIPillarStatus.FAILED

    def test_real_compileall_detects_syntax_error(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        broken_file = src_dir / "broken.py"
        broken_file.write_text("def broken(:\n    pass\n", encoding="utf-8")

        res_fail = CIPreFlightRunner(tmp_path).run_production_standalone_build()
        assert res_fail.status == CIPillarStatus.FAILED

        broken_file.write_text("def fixed():\n    return 42\n", encoding="utf-8")
        res_pass = CIPreFlightRunner(tmp_path).run_production_standalone_build()
        assert res_pass.status == CIPillarStatus.PASSED


class TestNodeAndUnknownCIPreFlight:
    """Tests for Node.js/TypeScript and unknown project handling."""

    def test_node_all_pillars_run_and_pass(self, tmp_path: Path) -> None:
        pkg = {
            "name": "web-app",
            "scripts": {
                "lint": "eslint .",
                "test": "vitest run",
                "build": "vite build",
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")

        recorded: list[list[str]] = []

        def fake_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
            recorded.append(cmd)
            return GitResult(stdout="ok", exit_code=0, success=True, command=cmd)

        report = run_ci_preflight(tmp_path, command_runner=fake_runner)
        assert report.project_type == "node"
        assert report.passed is True
        assert all(p.status == CIPillarStatus.PASSED for p in report.pillars)
        assert ["npm", "run", "lint"] in recorded
        assert ["npx", "tsc", "--noEmit"] in recorded
        assert ["npm", "test", "--", "--watchAll=false"] in recorded
        assert ["npm", "run", "build"] in recorded

    def test_node_unconfigured_scripts_are_skipped(self, tmp_path: Path) -> None:
        pkg = {
            "name": "bare-node",
            "scripts": {
                "test": 'echo "Error: no test specified" && exit 1',
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

        report = run_ci_preflight(tmp_path)
        assert report.project_type == "node"
        assert report.passed is True
        assert all(p.status == CIPillarStatus.SKIPPED for p in report.pillars)

    def test_unknown_project_skips_gracefully(self, tmp_path: Path) -> None:
        report = run_ci_preflight(tmp_path)
        assert report.project_type == "unknown"
        assert report.passed is True
        assert all(p.status == CIPillarStatus.SKIPPED for p in report.pillars)


class TestCheckCliCommand:
    """Tests for `pgit check` and `pgit flow check` CLI subcommands."""

    def test_cli_check_passes_and_renders_table(self, temp_git_repo: Path, monkeypatch) -> None:
        fake_report = CIPreFlightReport(
            repo_path=str(temp_git_repo),
            project_type="python",
            pillars=[
                CIPillarResult(name=PILLAR_QUALITY, status=CIPillarStatus.PASSED, command="ruff"),
                CIPillarResult(name=PILLAR_TESTS, status=CIPillarStatus.PASSED, command="pytest"),
                CIPillarResult(
                    name=PILLAR_BUILD, status=CIPillarStatus.PASSED, command="compileall"
                ),
            ],
        )
        monkeypatch.setattr("git_manager.cli.run_ci_preflight", lambda path, tier=None: fake_report)

        res = runner.invoke(app, ["check", "--path", str(temp_git_repo)])
        assert res.exit_code == 0
        assert "3-Pillar CI Pre-Flight Report" in res.output
        assert "Code Quality & Type Integrity" in res.output
        assert "Unit & Component Tests" in res.output
        assert "Production Standalone Build" in res.output

    def test_cli_check_exits_1_on_failure(self, temp_git_repo: Path, monkeypatch) -> None:
        fake_report = CIPreFlightReport(
            repo_path=str(temp_git_repo),
            project_type="python",
            pillars=[
                CIPillarResult(
                    name=PILLAR_QUALITY,
                    status=CIPillarStatus.FAILED,
                    command="ruff check .",
                    exit_code=1,
                    output="E501 line too long",
                ),
                CIPillarResult(name=PILLAR_TESTS, status=CIPillarStatus.PASSED, command="pytest"),
                CIPillarResult(
                    name=PILLAR_BUILD, status=CIPillarStatus.PASSED, command="compileall"
                ),
            ],
        )
        monkeypatch.setattr("git_manager.cli.run_ci_preflight", lambda path, tier=None: fake_report)

        res = runner.invoke(app, ["flow", "check", "--path", str(temp_git_repo)])
        assert res.exit_code == 1
        assert "E501 line too long" in res.output
        assert "CI Pre-Flight Failed" in res.output


class TestSmartTestingTiers:
    """Tests for prototype, production, and strict testing tiers."""

    def test_prototype_tier_nonblocking_lint_and_skipped_tests(self, tmp_path: Path) -> None:
        pkg = {
            "name": "proto-app",
            "scripts": {
                "lint": "eslint .",
                "test": "vitest run",
                "build": "next build",
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")

        def fake_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
            if "lint" in cmd:
                return GitResult(
                    stdout="warning: unused var",
                    exit_code=1,
                    success=False,
                    command=cmd,
                )
            return GitResult(stdout="ok", exit_code=0, success=True, command=cmd)

        report = run_ci_preflight(tmp_path, command_runner=fake_runner, tier=TestingTier.PROTOTYPE)
        assert report.tier == TestingTier.PROTOTYPE
        assert report.passed is True
        assert report.pillars[0].status == CIPillarStatus.PASSED
        assert "non-blocking lint" in report.pillars[0].output
        assert report.pillars[1].status == CIPillarStatus.SKIPPED
        assert report.pillars[2].status == CIPillarStatus.PASSED

    def test_strict_tier_runs_e2e_tests(self, tmp_path: Path) -> None:
        pkg = {
            "name": "strict-saas",
            "scripts": {
                "lint": "eslint .",
                "test": "vitest run",
                "test:e2e": "playwright test",
                "build": "next build",
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        recorded: list[list[str]] = []

        def fake_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
            recorded.append(cmd)
            return GitResult(stdout="ok", exit_code=0, success=True, command=cmd)

        report = run_ci_preflight(tmp_path, command_runner=fake_runner, tier=TestingTier.STRICT)
        assert report.tier == TestingTier.STRICT
        assert report.passed is True
        assert ["npm", "run", "test:e2e"] in recorded
