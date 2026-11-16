"""
Local 3-Pillar CI Pre-Flight Validator for Phantom Git.
Mirrors remote GitHub Actions gates locally to eliminate CI failure emails:
1. Code Quality & Type Integrity
2. Unit & Component Tests
3. Production Standalone Build
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable

from git_manager.core.models import (
    CIPillarResult,
    CIPillarStatus,
    CIPreFlightReport,
    GitResult,
    TestingTier,
)

CommandRunner = Callable[[list[str], Path, int], GitResult]

PILLAR_QUALITY = "Code Quality & Type Integrity"
PILLAR_TESTS = "Unit & Component Tests"
PILLAR_BUILD = "Production Standalone Build"


def detect_project_type(repo_path: Path | str) -> str:
    """
    Detect project ecosystem for a repository directory.

    Returns:
        'python', 'node', or 'unknown'.
    """
    root = Path(repo_path).resolve()
    if (
        (root / "pyproject.toml").exists()
        or (root / "setup.py").exists()
        or (root / "requirements.txt").exists()
    ):
        return "python"
    if (root / "package.json").exists():
        return "node"
    return "unknown"


def _default_command_runner(cmd: list[str], cwd: Path, timeout: int) -> GitResult:
    """Execute a local CLI check command safely without shell injection."""
    resolved_cmd = list(cmd)
    if resolved_cmd:
        executable = shutil.which(resolved_cmd[0])
        if executable:
            resolved_cmd[0] = executable

    try:
        proc = subprocess.run(
            resolved_cmd,
            cwd=str(cwd),
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
            command=cmd,
        )
    except FileNotFoundError:
        return GitResult(
            stdout="",
            stderr=f"Executable '{cmd[0]}' not found on PATH.",
            exit_code=127,
            success=False,
            command=cmd,
        )
    except subprocess.TimeoutExpired:
        return GitResult(
            stdout="",
            stderr=f"Command timed out after {timeout}s: {' '.join(cmd)}",
            exit_code=-1,
            success=False,
            command=cmd,
        )


class CIPreFlightRunner:
    """
    Executes the 3 CI pillars locally before pushing or opening Pull Requests.
    """

    def __init__(
        self,
        repo_path: Path | str,
        timeout: int = 300,
        command_runner: CommandRunner | None = None,
        tier: TestingTier | str = TestingTier.PRODUCTION,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.timeout = timeout
        self._runner = command_runner or _default_command_runner
        self.project_type = detect_project_type(self.repo_path)
        self.tier = (
            tier if isinstance(tier, TestingTier) else TestingTier(str(tier).lower().strip())
        )

    def _exec(self, cmd: list[str]) -> GitResult:
        return self._runner(cmd, self.repo_path, self.timeout)

    def _read_package_scripts(self) -> dict[str, str]:
        pkg_file = self.repo_path / "package.json"
        if not pkg_file.is_file():
            return {}
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            return scripts if isinstance(scripts, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _has_mypy_configured(self) -> bool:
        if (self.repo_path / "mypy.ini").is_file():
            return True
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.is_file():
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.mypy]" in content:
                    return True
            except OSError:
                pass
        return False

    def _is_mypy_installed(self) -> bool:
        return importlib.util.find_spec("mypy") is not None

    def _has_e2e_configured(self) -> bool:
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.is_file():
            try:
                return "e2e" in pyproject.read_text(encoding="utf-8")
            except OSError:
                pass
        return False

    def _run_command_sequence(
        self,
        pillar_name: str,
        commands: list[list[str]],
        success_default: str,
        start_time: float,
        non_blocking_commands: list[list[str]] | None = None,
    ) -> CIPillarResult:
        outputs: list[str] = []
        cmd_strs: list[str] = []
        for cmd in commands:
            cmd_strs.append(" ".join(cmd))
            res = self._exec(cmd)
            combined = "\n".join(part for part in (res.stdout.strip(), res.stderr.strip()) if part)
            if combined:
                outputs.append(combined)
            if not res.success:
                return CIPillarResult(
                    name=pillar_name,
                    status=CIPillarStatus.FAILED,
                    command=" && ".join(cmd_strs),
                    exit_code=res.exit_code,
                    output="\n".join(outputs),
                    duration_seconds=round(time.monotonic() - start_time, 3),
                )

        for cmd in non_blocking_commands or []:
            cmd_strs.append(" ".join(cmd))
            res = self._exec(cmd)
            combined = "\n".join(part for part in (res.stdout.strip(), res.stderr.strip()) if part)
            if not res.success and combined:
                outputs.append(f"[WARN (non-blocking lint)]: {combined}")
            elif combined:
                outputs.append(combined)

        return CIPillarResult(
            name=pillar_name,
            status=CIPillarStatus.PASSED,
            command=" && ".join(cmd_strs),
            exit_code=0,
            output="\n".join(outputs) or success_default,
            duration_seconds=round(time.monotonic() - start_time, 3),
        )

    def run_code_quality_and_types(self) -> CIPillarResult:
        """
        Pillar 1: Code Quality & Type Integrity.
        - Prototype tier: blocking syntax/type checks + non-blocking linter warnings.
        - Production/Strict tiers: blocking lint, format, and type integrity checks.
        """
        start = time.monotonic()

        if self.project_type == "python":
            if self.tier == TestingTier.PROTOTYPE:
                commands: list[list[str]] = [
                    [sys.executable, "-m", "ruff", "check", "--select", "E9,F63,F7,F82", "."],
                ]
                if self._has_mypy_configured() and self._is_mypy_installed():
                    commands.append([sys.executable, "-m", "mypy", "."])
                non_blocking = [[sys.executable, "-m", "ruff", "check", "."]]
                return self._run_command_sequence(
                    PILLAR_QUALITY,
                    commands,
                    "Prototype syntax/type checks passed.",
                    start,
                    non_blocking_commands=non_blocking,
                )

            commands = [
                [sys.executable, "-m", "ruff", "check", "."],
                [sys.executable, "-m", "ruff", "format", "--check", "."],
            ]
            if self._has_mypy_configured() and self._is_mypy_installed():
                commands.append([sys.executable, "-m", "mypy", "."])

            return self._run_command_sequence(
                PILLAR_QUALITY,
                commands,
                "All code quality and formatting checks passed.",
                start,
            )

        if self.project_type == "node":
            scripts = self._read_package_scripts()
            has_tsconfig = (self.repo_path / "tsconfig.json").is_file()
            has_lint = "lint" in scripts

            if not has_tsconfig and not has_lint:
                return CIPillarResult(
                    name=PILLAR_QUALITY,
                    status=CIPillarStatus.SKIPPED,
                    command="",
                    exit_code=0,
                    output="No 'lint' script or 'tsconfig.json' found in Node project.",
                    duration_seconds=round(time.monotonic() - start, 3),
                )

            if self.tier == TestingTier.PROTOTYPE:
                commands = [["npx", "tsc", "--noEmit"]] if has_tsconfig else []
                non_blocking = [["npm", "run", "lint"]] if has_lint else []
                return self._run_command_sequence(
                    PILLAR_QUALITY,
                    commands,
                    "Prototype type check passed.",
                    start,
                    non_blocking_commands=non_blocking,
                )

            commands = []
            if has_lint:
                commands.append(["npm", "run", "lint"])
            if has_tsconfig:
                commands.append(["npx", "tsc", "--noEmit"])

            return self._run_command_sequence(
                PILLAR_QUALITY,
                commands,
                "Lint and type checks passed.",
                start,
            )

        return CIPillarResult(
            name=PILLAR_QUALITY,
            status=CIPillarStatus.SKIPPED,
            output="Unsupported or unrecognized project type.",
            duration_seconds=round(time.monotonic() - start, 3),
        )

    def run_unit_and_component_tests(self) -> CIPillarResult:
        """
        Pillar 2: Unit & Component Tests.
        - Prototype tier: skipped so UI/feature iteration stays fast.
        - Production tier: runs unit/component tests.
        - Strict tier: runs unit tests + E2E tests if configured.
        """
        start = time.monotonic()

        if self.tier == TestingTier.PROTOTYPE:
            return CIPillarResult(
                name=PILLAR_TESTS,
                status=CIPillarStatus.SKIPPED,
                output="Skipped in 'prototype' tier (Stage 1 focuses on Type Integrity & Build).",
                duration_seconds=round(time.monotonic() - start, 3),
            )

        if self.project_type == "python":
            cmd = [sys.executable, "-m", "pytest", "-q"]
            res = self._exec(cmd)
            combined = "\n".join(part for part in (res.stdout.strip(), res.stderr.strip()) if part)
            if res.exit_code not in (0, 5):
                return CIPillarResult(
                    name=PILLAR_TESTS,
                    status=CIPillarStatus.FAILED,
                    command=" ".join(cmd),
                    exit_code=res.exit_code,
                    output=combined or "Unit tests failed.",
                    duration_seconds=round(time.monotonic() - start, 3),
                )

            cmd_str = " ".join(cmd)
            outputs: list[str] = []
            if res.exit_code == 5:
                outputs.append("No tests collected (pytest exit code 5).")
            elif combined:
                outputs.append(combined)

            if self.tier == TestingTier.STRICT and self._has_e2e_configured():
                e2e_cmd = [sys.executable, "-m", "pytest", "-m", "e2e", "-q"]
                e2e_res = self._exec(e2e_cmd)
                cmd_str = f"{cmd_str} && {' '.join(e2e_cmd)}"
                e2e_out = "\n".join(
                    part for part in (e2e_res.stdout.strip(), e2e_res.stderr.strip()) if part
                )
                if e2e_res.exit_code not in (0, 5):
                    return CIPillarResult(
                        name=PILLAR_TESTS,
                        status=CIPillarStatus.FAILED,
                        command=cmd_str,
                        exit_code=e2e_res.exit_code,
                        output="\n".join([*outputs, e2e_out]).strip() or "E2E tests failed.",
                        duration_seconds=round(time.monotonic() - start, 3),
                    )
                if e2e_out:
                    outputs.append(e2e_out)

            return CIPillarResult(
                name=PILLAR_TESTS,
                status=CIPillarStatus.PASSED,
                command=cmd_str,
                exit_code=res.exit_code,
                output="\n".join(outputs) or "All unit tests passed.",
                duration_seconds=round(time.monotonic() - start, 3),
            )

        if self.project_type == "node":
            scripts = self._read_package_scripts()
            test_script = str(scripts.get("test", ""))
            has_unit = bool(test_script) and "no test specified" not in test_script
            has_e2e = self.tier == TestingTier.STRICT and "test:e2e" in scripts

            if not has_unit and not has_e2e:
                return CIPillarResult(
                    name=PILLAR_TESTS,
                    status=CIPillarStatus.SKIPPED,
                    output="No test script configured in package.json.",
                    duration_seconds=round(time.monotonic() - start, 3),
                )

            commands: list[list[str]] = []
            if has_unit:
                commands.append(["npm", "test", "--", "--watchAll=false"])
            if has_e2e:
                commands.append(["npm", "run", "test:e2e"])

            return self._run_command_sequence(
                PILLAR_TESTS,
                commands,
                "Tests passed.",
                start,
            )

        return CIPillarResult(
            name=PILLAR_TESTS,
            status=CIPillarStatus.SKIPPED,
            output="Unsupported or unrecognized project type.",
            duration_seconds=round(time.monotonic() - start, 3),
        )

    def run_production_standalone_build(self) -> CIPillarResult:
        """
        Pillar 3: Production Standalone Build.
        Python: python -m compileall -q src (or .) for syntax/bytecode integrity.
        Node: npm run build (if 'build' script exists).
        """
        start = time.monotonic()

        if self.project_type == "python":
            target = "src" if (self.repo_path / "src").is_dir() else "."
            cmd = [sys.executable, "-m", "compileall", "-q", target]
            res = self._exec(cmd)
            combined = "\n".join(part for part in (res.stdout.strip(), res.stderr.strip()) if part)
            return CIPillarResult(
                name=PILLAR_BUILD,
                status=CIPillarStatus.PASSED if res.success else CIPillarStatus.FAILED,
                command=" ".join(cmd),
                exit_code=res.exit_code,
                output=combined
                or (
                    f"Bytecode compilation succeeded for '{target}'."
                    if res.success
                    else "Build compilation failed."
                ),
                duration_seconds=round(time.monotonic() - start, 3),
            )

        if self.project_type == "node":
            scripts = self._read_package_scripts()
            if "build" not in scripts:
                return CIPillarResult(
                    name=PILLAR_BUILD,
                    status=CIPillarStatus.SKIPPED,
                    output="No 'build' script configured in package.json.",
                    duration_seconds=round(time.monotonic() - start, 3),
                )
            cmd = ["npm", "run", "build"]
            res = self._exec(cmd)
            combined = "\n".join(part for part in (res.stdout.strip(), res.stderr.strip()) if part)
            return CIPillarResult(
                name=PILLAR_BUILD,
                status=CIPillarStatus.PASSED if res.success else CIPillarStatus.FAILED,
                command=" ".join(cmd),
                exit_code=res.exit_code,
                output=combined
                or ("Production build succeeded." if res.success else "Build failed."),
                duration_seconds=round(time.monotonic() - start, 3),
            )

        return CIPillarResult(
            name=PILLAR_BUILD,
            status=CIPillarStatus.SKIPPED,
            output="Unsupported or unrecognized project type.",
            duration_seconds=round(time.monotonic() - start, 3),
        )

    def run_all(self) -> CIPreFlightReport:
        """Execute all 3 CI pillars locally and return a structured report."""
        pillars = [
            self.run_code_quality_and_types(),
            self.run_unit_and_component_tests(),
            self.run_production_standalone_build(),
        ]
        return CIPreFlightReport(
            repo_path=str(self.repo_path),
            project_type=self.project_type,
            tier=self.tier,
            pillars=pillars,
        )


def run_ci_preflight(
    repo_path: Path | str,
    timeout: int = 300,
    command_runner: CommandRunner | None = None,
    tier: TestingTier | str = TestingTier.PRODUCTION,
) -> CIPreFlightReport:
    """Convenience function to run all 3 local CI pre-flight pillars."""
    runner = CIPreFlightRunner(
        repo_path=repo_path,
        timeout=timeout,
        command_runner=command_runner,
        tier=tier,
    )
    return runner.run_all()
