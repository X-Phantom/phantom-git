"""
GitHub CLI (`gh`) authentication, repository discovery, and publishing manager for Phantom Git.
Handles Windows PATH resolution for `gh.exe`, token/browser OAuth authentication,
account repository listing cross-referenced with local workspace clones, and repo publishing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Callable

from git_manager.core.git_driver import GitDriver
from git_manager.core.models import (
    GitCommandError,
    GitHubAccountStatus,
    GitHubRepoItem,
    GitResult,
)
from git_manager.multirepo.scanner import discover_repositories

GHAuthRunner = Callable[[list[str], Path, str | None, int], GitResult]


def find_gh_binary() -> str:
    """
    Locate the GitHub CLI (`gh`) binary across PATH and standard Windows install paths.
    If discovered outside PATH, prepends its directory to os.environ['PATH'].
    """
    discovered = shutil.which("gh")
    if discovered:
        return discovered

    candidates = [
        Path("C:/Program Files/GitHub CLI/gh.exe"),
        Path("C:/Program Files (x86)/GitHub CLI/gh.exe"),
        Path.home() / "AppData/Local/Programs/GitHub CLI/gh.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            parent_dir = str(candidate.parent)
            current_path = os.environ.get("PATH", "")
            path_parts = current_path.split(os.pathsep) if current_path else []
            if parent_dir not in path_parts:
                os.environ["PATH"] = (
                    f"{parent_dir}{os.pathsep}{current_path}" if current_path else parent_dir
                )
            return str(candidate)

    return "gh"


def _default_gh_auth_runner(
    args: list[str],
    cwd: Path,
    input_text: str | None,
    timeout: int,
) -> GitResult:
    """Execute a `gh` subprocess command with optional stdin and UTF-8 decoding."""
    gh_bin = find_gh_binary()
    cmd = [gh_bin, *args]
    env = {
        **os.environ,
        "GH_PROMPT_DISABLED": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    GitDriver.notify_command(" ".join(["gh", *args]))

    stdin_bytes = input_text.encode("utf-8") if input_text is not None else None
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            input=stdin_bytes,
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
                "Install it from https://cli.github.com/ or run 'winget install GitHub.cli'."
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


def _parse_auth_status_output(output: str, host: str, success: bool) -> GitHubAccountStatus:
    """Parse `gh auth status` output into a structured GitHubAccountStatus model."""
    text = output or ""
    if not success:
        return GitHubAccountStatus(
            authenticated=False,
            host=host,
            raw_output=text.strip(),
        )

    username: str | None = None
    user_match = re.search(
        r"Logged in to\s+\S+\s+(?:account|as)\s+([A-Za-z0-9_.-]+)",
        text,
        re.IGNORECASE,
    )
    if not user_match:
        user_match = re.search(r"(?:account|as)\s+([A-Za-z0-9_.-]+)", text, re.IGNORECASE)
    if user_match:
        username = user_match.group(1).strip()

    protocol = "https"
    proto_match = re.search(r"Git operations protocol:\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if proto_match:
        protocol = proto_match.group(1).strip().lower()

    scopes: list[str] = []
    scope_match = re.search(r"Token scopes:\s*(.+)", text, re.IGNORECASE)
    if scope_match:
        raw_scopes = scope_match.group(1).strip()
        for item in raw_scopes.split(","):
            cleaned = item.strip().strip("'\"")
            if cleaned:
                scopes.append(cleaned)

    return GitHubAccountStatus(
        authenticated=True,
        username=username,
        host=host,
        protocol=protocol,
        scopes=scopes,
        raw_output=text.strip(),
    )


class GitHubAuthManager:
    """Manages GitHub CLI authentication, account repositories, and repo publishing."""

    def __init__(self, gh_runner: GHAuthRunner | None = None) -> None:
        self._gh_runner = gh_runner or _default_gh_auth_runner

    def run_gh(
        self,
        args: list[str],
        cwd: Path | None = None,
        input_text: str | None = None,
        timeout: int = 30,
        check: bool = False,
    ) -> GitResult:
        """Execute a `gh` command through the configured runner."""
        target_cwd = Path(cwd).resolve() if cwd else Path.cwd().resolve()
        if self._gh_runner is not _default_gh_auth_runner:
            GitDriver.notify_command(" ".join(["gh", *args]))
        res = self._gh_runner(args, target_cwd, input_text, timeout)
        if check and not res.success:
            raise GitCommandError(
                command=res.command or ["gh", *args],
                exit_code=res.exit_code,
                stderr=res.stderr,
                stdout=res.stdout,
            )
        return res

    def get_status(self, hostname: str = "github.com") -> GitHubAccountStatus:
        """Inspect current GitHub authentication state via `gh auth status`."""
        res = self.run_gh(["auth", "status", "--hostname", hostname], check=False)
        combined = "\n".join(part for part in (res.stdout.strip(), res.stderr.strip()) if part)
        return _parse_auth_status_output(combined, host=hostname, success=res.success)

    def login_with_token(
        self,
        token: str,
        hostname: str = "github.com",
        git_protocol: str = "https",
    ) -> GitHubAccountStatus:
        """Authenticate `gh` CLI using a Personal Access Token and configure Git credentials."""
        cleaned_token = (token or "").strip()
        if not cleaned_token:
            raise ValueError("GitHub Personal Access Token cannot be empty.")

        self.run_gh(
            [
                "auth",
                "login",
                "--hostname",
                hostname,
                "--git-protocol",
                git_protocol,
                "--with-token",
            ],
            input_text=f"{cleaned_token}\n",
            check=True,
        )
        self.run_gh(["auth", "setup-git", "--hostname", hostname], check=False)
        return self.get_status(hostname=hostname)

    def start_web_login(
        self,
        hostname: str = "github.com",
        git_protocol: str = "https",
        scopes: str = "repo,workflow,read:org",
    ) -> subprocess.Popen[str]:
        """Spawn interactive `gh auth login --web` so the caller can complete browser OAuth."""
        gh_bin = find_gh_binary()
        args = [
            "auth",
            "login",
            "--hostname",
            hostname,
            "--git-protocol",
            git_protocol,
            "--web",
            "-s",
            scopes,
        ]
        GitDriver.notify_command(" ".join(["gh", *args]))
        return subprocess.Popen(
            [gh_bin, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def logout(self, hostname: str = "github.com") -> GitResult:
        """Log out of GitHub CLI for the specified host."""
        return self.run_gh(
            ["auth", "logout", "--hostname", hostname],
            input_text="Y\n",
            check=False,
        )

    def list_repos(
        self,
        workspace_path: Path | None = None,
        limit: int = 50,
    ) -> list[GitHubRepoItem]:
        """Fetch repositories on the connected GitHub account and match local clones."""
        res = self.run_gh(
            [
                "repo",
                "list",
                "--limit",
                str(limit),
                "--json",
                "name,nameWithOwner,isPrivate,defaultBranchRef,updatedAt,url,description",
            ],
            check=True,
        )
        raw = res.stdout.strip() or "[]"
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse GitHub repository list JSON: {exc}") from exc

        local_by_slug: dict[str, Path] = {}
        local_by_name: dict[str, Path] = {}
        if workspace_path and Path(workspace_path).exists():
            for repo_dir in discover_repositories(workspace_path, max_depth=3):
                local_by_name.setdefault(repo_dir.name.lower(), repo_dir)
                try:
                    driver = GitDriver(repo_dir)
                    remote_res = driver.run(["remote", "get-url", "origin"], check=False)
                    if remote_res.success and remote_res.stdout.strip():
                        remote_url = remote_res.stdout.strip().lower()
                        match = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", remote_url)
                        if match:
                            local_by_slug[match.group(1)] = repo_dir
                except Exception:
                    pass

        repos: list[GitHubRepoItem] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            full_name = str(item.get("nameWithOwner", name))
            branch_ref = item.get("defaultBranchRef")
            default_branch = (
                str(branch_ref.get("name", "main"))
                if isinstance(branch_ref, dict) and branch_ref.get("name")
                else "main"
            )
            matched_local = local_by_slug.get(full_name.lower()) or local_by_name.get(name.lower())
            repos.append(
                GitHubRepoItem(
                    name=name,
                    full_name=full_name,
                    is_private=bool(item.get("isPrivate", False)),
                    default_branch=default_branch,
                    updated_at=str(item.get("updatedAt", "")),
                    url=str(item.get("url", "")),
                    description=str(item.get("description") or ""),
                    local_path=str(matched_local) if matched_local else None,
                )
            )
        return repos

    def clone_repo(self, full_name: str, target_parent_dir: Path) -> Path:
        """Clone a GitHub repository into `target_parent_dir/<repo_name>`."""
        parent = Path(target_parent_dir).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        repo_name = full_name.rstrip("/").split("/")[-1]
        dest = parent / repo_name
        self.run_gh(["repo", "clone", full_name, str(dest)], cwd=parent, timeout=120, check=True)
        return dest

    def publish_repo(
        self,
        driver: GitDriver,
        repo_name: str | None = None,
        private: bool = False,
        description: str = "",
    ) -> str:
        """
        Ensure the local repository has at least one commit and `main` branch,
        then create/push it to GitHub under the authenticated account.
        """
        head_check = driver.run(["rev-parse", "--verify", "HEAD"], check=False)
        if not head_check.success:
            raise ValueError(
                "Repository has no commits yet. Stage and commit files before publishing to GitHub."
            )

        main_check = driver.run(["rev-parse", "--verify", "refs/heads/main"], check=False)
        if not main_check.success:
            driver.run(["branch", "main"], check=True)

        origin_check = driver.run(["remote", "get-url", "origin"], check=False)
        if not origin_check.success or not origin_check.stdout.strip():
            target_name = (repo_name or driver.repo_path.name).strip().replace(" ", "-")
            visibility_flag = "--private" if private else "--public"
            args = [
                "repo",
                "create",
                target_name,
                visibility_flag,
                "--source",
                str(driver.repo_path),
                "--remote",
                "origin",
                "--push",
            ]
            if description.strip():
                args.extend(["--description", description.strip()])
            res = self.run_gh(args, cwd=driver.repo_path, timeout=60, check=True)
            url_res = driver.run(["remote", "get-url", "origin"], check=False)
            return url_res.stdout.strip() or res.stdout.strip()

        driver.run(["push", "-u", "origin", "main"], check=True)
        staging_check = driver.run(["rev-parse", "--verify", "refs/heads/staging"], check=False)
        if staging_check.success:
            driver.run(["push", "-u", "origin", "staging"], check=True)

        return origin_check.stdout.strip()
