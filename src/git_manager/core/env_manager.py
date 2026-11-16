"""
Environment variable hygiene (.env.example synchronization) and
GitHub Environment secret/variable provisioning for Phantom Git.
"""

from __future__ import annotations

import os
from pathlib import Path
import re

from git_manager.core.git_driver import GitDriver
from git_manager.core.github_flow import GHRunner, GitHubFlowEngine
from git_manager.core.models import EnvSyncReport, GitResult

_ENV_FILES = (
    ".env",
    ".env.local",
    ".env.development",
    ".env.staging",
    ".env.production",
)
_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}
_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".pytest_cache",
}
_VALID_ENVIRONMENTS = ("staging", "production", "repo")

_ENV_LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=")
_CODE_ENV_PATTERNS = (
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)"),
    re.compile(r"os\.environ\.get\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),
    re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),
    re.compile(r"os\.environ\[\s*['\"]([A-Z][A-Z0-9_]+)['\"]\s*\]"),
)


def _extract_keys_from_env_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    keys: list[str] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = _ENV_LINE_RE.match(stripped)
            if m and m.group(1) not in keys:
                keys.append(m.group(1))
    except OSError:
        pass
    return keys


def sync_env_example(repo_path: Path | str) -> EnvSyncReport:
    """
    Scan local `.env*` files and application source code for environment variable
    keys, and append missing keys as safe empty placeholders (`KEY=`) to `.env.example`.
    Never copies secret values.
    """
    root = Path(repo_path).resolve()
    example_path = root / ".env.example"

    discovered: list[str] = []

    def _add_key(k: str) -> None:
        if k not in discovered:
            discovered.append(k)

    # 1. Scan local .env* files
    for env_name in _ENV_FILES:
        for k in _extract_keys_from_env_file(root / env_name):
            _add_key(k)

    # 2. Scan source files
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() not in _SOURCE_EXTS:
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pat in _CODE_ENV_PATTERNS:
                for match in pat.findall(content):
                    _add_key(match)

    existing = _extract_keys_from_env_file(example_path)
    added = [k for k in discovered if k not in existing]

    if added or not example_path.exists():
        lines: list[str] = []
        if example_path.exists():
            raw = example_path.read_text(encoding="utf-8", errors="ignore")
            lines = raw.splitlines()
        else:
            lines = ["# Environment Variables Example (Managed by Phantom Git)"]

        if added:
            if lines and lines[-1].strip():
                lines.append("")
            for key in added:
                lines.append(f"{key}=")

        example_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    return EnvSyncReport(
        env_example_path=str(example_path),
        discovered_keys=discovered,
        added_keys=added,
        existing_keys=existing,
    )


def set_github_env_secret(
    driver: GitDriver,
    key: str,
    value: str,
    environment: str = "staging",
    is_variable: bool = False,
    gh_runner: GHRunner | None = None,
) -> GitResult:
    """
    Set a GitHub Environment secret (or non-sensitive variable) using `gh`.
    """
    clean_key = key.strip()
    if not clean_key:
        raise ValueError("Environment key name cannot be empty.")

    norm_env = environment.lower().strip()
    if norm_env not in _VALID_ENVIRONMENTS:
        raise ValueError(
            f"Unsupported environment '{environment}'. Expected one of: {', '.join(_VALID_ENVIRONMENTS)}."
        )

    cmd_type = "variable" if is_variable else "secret"
    args = [cmd_type, "set", clean_key, "--body", value]
    if norm_env != "repo":
        args.extend(["--env", norm_env])

    engine = GitHubFlowEngine(driver, gh_runner=gh_runner)
    return engine.run_gh(args, check=True)
