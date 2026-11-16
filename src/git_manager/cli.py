"""
Command Line Interface for git-mgr.
Modern, type-safe CLI powered by Typer and formatted with Rich.
Orchestrates single-repo daily developer workflows, safety net recoveries,
scaffolding automation, and multi-repo discovery and synchronization.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.table import Table

from git_manager import __version__
from git_manager.core.branch_hygiene import BranchManager, switch_or_create
from git_manager.core.ci_checks import run_ci_preflight
from git_manager.core.commit_parser import (
    parse_commit_message,
    suggest_conventional_commit,
)
from git_manager.core.env_manager import set_github_env_secret, sync_env_example
from git_manager.core.git_driver import GitDriver, find_repo_root
from git_manager.core.github_auth import GitHubAuthManager, find_gh_binary
from git_manager.core.github_flow import GitHubFlowEngine
from git_manager.core.linear_history import get_linear_log, sync_linear_rebase
from git_manager.core.models import (
    CIPillarStatus,
    ConventionalCommit,
    GitCommandError,
    TestingTier,
)
from git_manager.core.safety_net import SafetyNet
from git_manager.multirepo.health_check import audit_repositories
from git_manager.multirepo.scanner import discover_repositories
from git_manager.multirepo.sync import sync_all_repositories
from git_manager.scaffold.engine import ScaffoldEngine
from git_manager.scaffold.ruleset import generate_ruleset_script
from git_manager.utils.console import (
    console,
    create_panel,
    print_error,
    print_info,
    print_success,
    print_warning,
    render_ci_preflight_table,
    render_linear_log,
    render_multirepo_table,
    render_pr_checks_table,
    render_repo_status_table,
    render_sync_summary_table,
)

app = typer.Typer(
    name="phantom-git",
    help=(
        "Phantom Git (pgit / git-mgr) — Agentic Git Orchestrator & Multi-Repo Manager "
        "designed for developers and AI agents."
    ),
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
)

scaffold_app = typer.Typer(
    name="scaffold",
    help="Scaffold Layer 1 hooks, Layer 2 CI, Layer 3 Release Please, and AI .gitignore.",
    no_args_is_help=True,
)
app.add_typer(scaffold_app, name="scaffold")

flow_app = typer.Typer(
    name="flow",
    help="5-Step GitHub Flow orchestrator (init-branches, start, check, pr, checks, logs, merge, promote).",
    no_args_is_help=True,
)
app.add_typer(flow_app, name="flow")

env_app = typer.Typer(
    name="env",
    help="Environment variable hygiene (.env.example sync) and GitHub Environment secrets.",
    no_args_is_help=True,
)
app.add_typer(env_app, name="env")

auth_app = typer.Typer(
    name="auth",
    help="Sign into GitHub and manage connected account repositories.",
    no_args_is_help=True,
)
app.add_typer(auth_app, name="auth")


def version_callback(value: bool) -> None:
    """Print the version string and exit."""
    if value:
        console.print(
            f"[bold cyan]Phantom Git[/bold cyan] (phantom-git / pgit / git-mgr) "
            f"version [bold green]{__version__}[/bold green]"
        )
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show Phantom Git version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target repository path when launching TUI directly.",
    ),
    workspace: Optional[Path] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Parent workspace directory when launching TUI directly.",
    ),
) -> None:
    """Phantom Git root entrypoint. Launches the interactive TUI when run without a subcommand."""
    if ctx.invoked_subcommand is None:
        _launch_tui(path, workspace)


def _get_driver_or_exit(path: Optional[Path] = None) -> GitDriver:
    """
    Validate and return a GitDriver instance for the specified path or current working directory.
    Exits with code 1 and rich error message if not inside a valid Git repository.
    """
    target = Path(path).resolve() if path else Path.cwd().resolve()
    if not target.exists():
        print_error(f"Path '{target}' does not exist.", title="Path Not Found")
        raise typer.Exit(code=1)

    root = find_repo_root(target)
    if root is None:
        print_error(
            f"'{target}' is not inside a valid Git repository.",
            title="Not a Git Repository",
        )
        raise typer.Exit(code=1)
    return GitDriver(root)


# ============================================================================
# Status Command
# ============================================================================


@app.command("status")
def status_command(
    path: Optional[Path] = typer.Argument(
        None,
        help="Optional path to repository (defaults to current directory).",
    ),
) -> None:
    """Rich dashboard of current repo (branch, remote, staged/unstaged/untracked files, stashes, clean status)."""
    driver = _get_driver_or_exit(path)
    try:
        status = driver.get_status()
        console.print(render_repo_status_table(status))
    except Exception as exc:
        print_error(f"Failed to read repository status: {exc}")
        raise typer.Exit(code=1)


# ============================================================================
# Branch Commands
# ============================================================================


@app.command("branch")
def branch_command(
    name: str = typer.Argument(
        ...,
        help="Target branch name (e.g. 'feat/user-auth', 'fix/issue-102').",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Bypass branch prefix hygiene validation.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Validates prefix, safe switch or creation with auto-stash."""
    driver = _get_driver_or_exit(path)
    try:
        switch_or_create(driver.repo_path, branch_name=name, auto_stash=True, force=force)
    except ValueError as exc:
        print_error(str(exc), title="Branch Validation Failed")
        raise typer.Exit(code=1)
    except GitCommandError as exc:
        print_error(f"Git branch operation failed: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    print_success(f"Successfully switched to branch '{name}'.")


@app.command("branches")
def branches_command(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Lists local and remote branches in a clean table with current marker."""
    driver = _get_driver_or_exit(path)
    mgr = BranchManager(driver)
    branches = mgr.list_branches()
    if not branches:
        print_info("No branches found in repository.")
        return

    table = Table(
        title=f"Branches: [bold cyan]{driver.repo_path.name}[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_header=True,
    )
    table.add_column("", width=2, justify="center")
    table.add_column("Branch Name", style="bold white")
    table.add_column("Type", justify="center")
    table.add_column("Upstream", style="dim")
    table.add_column("Tracking", style="dim")
    table.add_column("Commit", style="dim cyan")
    table.add_column("Subject", style="white")

    for b in branches:
        marker = "[bold green]*[/bold green]" if b.get("is_current") else " "
        name_style = f"[bold green]{b['name']}[/bold green]" if b.get("is_current") else b["name"]
        btype = "[magenta]remote[/magenta]" if b.get("is_remote") else "[cyan]local[/cyan]"
        table.add_row(
            marker,
            name_style,
            btype,
            b.get("upstream") or "",
            b.get("tracking_status") or "",
            b.get("commit_sha", "")[:7],
            b.get("subject", ""),
        )
    console.print(table)


# ============================================================================
# Commit Command
# ============================================================================


@app.command("commit")
def commit_command(
    message: Optional[str] = typer.Option(
        None,
        "--message",
        "-m",
        help="Commit subject or full Conventional Commit message.",
    ),
    type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Conventional Commit type (feat, fix, chore, docs, test, etc.).",
    ),
    scope: Optional[str] = typer.Option(
        None,
        "--scope",
        "-s",
        help="Optional commit scope.",
    ),
    breaking: bool = typer.Option(
        False,
        "--breaking",
        "-b",
        help="Flag commit as a breaking change (!).",
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        "-a",
        help="Analyze staged diff with suggest_conventional_commit and commit.",
    ),
    strict_flow: bool = typer.Option(
        False,
        "--strict-flow",
        help="Block direct commits on main/master/staging branch.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Conventional Commits assistant. If --auto, analyzes staged changes and commits!"""
    driver = _get_driver_or_exit(path)

    current_branch = driver.get_current_branch()
    if current_branch in ("main", "master", "staging"):
        if strict_flow:
            print_error(
                f"Direct commits to '{current_branch}' are blocked under strict GitHub Flow. "
                "Run 'pgit flow start feat/<name>' first.",
                title="Main Branch Protected",
            )
            raise typer.Exit(code=1)
        print_warning(
            f"Tip: You are committing directly on '{current_branch}'. "
            "For GitHub Flow isolation, use 'pgit flow start <type>/<name>'."
        )

    if auto:
        try:
            suggested = suggest_conventional_commit(driver)
        except ValueError as exc:
            print_error(str(exc), title="Auto-Commit Suggestion Failed")
            raise typer.Exit(code=1)

        commit_type = (type or suggested.type).lower().strip()
        commit_scope = scope if scope is not None else suggested.scope
        commit_subject = message if message is not None else suggested.subject
        is_breaking = breaking or suggested.is_breaking

        final_commit = ConventionalCommit(
            type=commit_type,
            scope=commit_scope,
            is_breaking=is_breaking,
            subject=commit_subject,
        )
        formatted_message = final_commit.format_message()
    else:
        if not message:
            print_error(
                "Commit message is required when --auto is not specified. Use -m/--message or --auto.",
                title="Missing Commit Message",
            )
            raise typer.Exit(code=1)

        if type:
            final_commit = ConventionalCommit(
                type=type.lower().strip(),
                scope=scope,
                is_breaking=breaking,
                subject=message.strip(),
            )
            formatted_message = final_commit.format_message()
        else:
            try:
                parsed = parse_commit_message(message)
                if breaking and not parsed.is_breaking:
                    parsed = ConventionalCommit(
                        type=parsed.type,
                        scope=parsed.scope,
                        is_breaking=True,
                        subject=parsed.subject,
                        body=parsed.body,
                        breaking_description=parsed.breaking_description,
                        footers=parsed.footers,
                    )
                formatted_message = parsed.format_message()
            except ValueError as exc:
                print_error(
                    f"Conventional Commit validation failed: {exc}\n"
                    "Use standard format 'type(scope): subject' or provide -t/--type.",
                    title="Invalid Commit Message",
                )
                raise typer.Exit(code=1)

    try:
        driver.commit(formatted_message)
    except GitCommandError as exc:
        print_error(f"Git commit failed: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    header_line = formatted_message.splitlines()[0]
    print_success(f"Committed: [bold cyan]{header_line}[/bold cyan]")


# ============================================================================
# Stash Command
# ============================================================================


class StashAction(str, Enum):
    SAVE = "save"
    POP = "pop"
    LIST = "list"


@app.command("stash")
def stash_command(
    action: StashAction = typer.Argument(
        StashAction.LIST,
        help="Stash action: 'save', 'pop', or 'list'. Defaults to 'list'.",
    ),
    message: Optional[str] = typer.Option(
        None,
        "--message",
        "-m",
        help="Optional message for stash (used with 'save').",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Context switching with untracked files guaranteed (-u)."""
    driver = _get_driver_or_exit(path)

    try:
        if action == StashAction.SAVE:
            msg = message or "git-mgr automated stash"
            saved = driver.stash_save(message=msg, include_untracked=True)
            if saved:
                print_success(f"Stash saved: '{msg}' (including untracked files).")
            else:
                print_info("No local changes to save to stash.")

        elif action == StashAction.POP:
            driver.stash_pop()
            print_success("Stash applied and removed from stash list.")

        elif action == StashAction.LIST:
            stashes = driver.stash_list()
            if not stashes:
                print_info("No stash entries found.")
            else:
                table = Table(
                    title=f"Stash Entries: [bold cyan]{driver.repo_path.name}[/bold cyan]",
                    box=box.ROUNDED,
                    border_style="cyan",
                    header_style="bold cyan",
                    show_header=True,
                )
                table.add_column("Ref", style="bold cyan")
                table.add_column("Description", style="white")
                for s in stashes:
                    parts = s.split(":", 1)
                    ref_part = parts[0].strip() if len(parts) > 1 else "stash"
                    desc_part = parts[1].strip() if len(parts) > 1 else s
                    table.add_row(ref_part, desc_part)
                console.print(table)
    except GitCommandError as exc:
        print_error(f"Git stash operation failed: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)


# ============================================================================
# Sync Command
# ============================================================================


@app.command("sync")
def sync_command(
    remote: str = typer.Option(
        "origin",
        "--remote",
        "-r",
        help="Remote name to pull from.",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch",
        "-b",
        help="Remote branch name (defaults to current tracking branch).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Auto-stash uncommitted dirty changes before syncing.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Safe git pull --rebase with working tree protection."""
    driver = _get_driver_or_exit(path)

    status = driver.get_status()
    if not status.is_clean and not force:
        print_error(
            "Working directory has uncommitted changes. Use --force to auto-stash and sync.",
            title="Dirty Working Tree",
        )
        raise typer.Exit(code=1)

    try:
        sync_linear_rebase(driver.repo_path, remote=remote, branch=branch)
    except GitCommandError as exc:
        print_error(f"Rebase sync failed: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    print_success("Synchronized with upstream via linear rebase.")


# ============================================================================
# Safety Net Recovery Commands: snapshot, undo, log-linear
# ============================================================================


@app.command("snapshot")
def snapshot_command(
    label: str = typer.Argument(
        "manual_snapshot",
        help="Bookmark label identifier.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Creates safety bookmark under refs/git-mgr/bookmarks/."""
    driver = _get_driver_or_exit(path)
    safety = SafetyNet(driver)

    try:
        bookmark = safety.create_bookmark(label=label, include_untracked=True)
    except GitCommandError as exc:
        print_error(f"Failed to create snapshot bookmark: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)
    except Exception as exc:
        print_error(f"Snapshot error: {exc}")
        raise typer.Exit(code=1)

    print_success(
        f"Created safety bookmark '{bookmark.label}' at {bookmark.commit_sha[:8]} "
        f"([dim]{bookmark.tag_or_ref}[/dim])"
    )


@app.command("undo")
def undo_command(
    steps: int = typer.Option(
        1,
        "--steps",
        "-s",
        help="Number of reflog steps to revert backwards (default 1).",
    ),
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="Specific target commit ref/hash to revert to.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Bypass safety checks or confirmation.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Reversible rollback via reflog."""
    driver = _get_driver_or_exit(path)
    safety = SafetyNet(driver)

    try:
        safety.undo(steps=steps, target_ref=target, force=force)
    except GitCommandError as exc:
        print_error(f"Undo operation failed: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)
    except Exception as exc:
        print_error(f"Undo error: {exc}")
        raise typer.Exit(code=1)

    target_name = target or f"HEAD@{{{steps}}}"
    print_success(f"Safely reverted state back to '{target_name}'.")


@app.command("log-linear")
def log_linear_command(
    max_count: int = typer.Option(
        15,
        "--max",
        "--limit",
        "-n",
        help="Maximum number of commits to display (default 15).",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Condensed linear commit graph with SemVer/Conventional Commit badges."""
    driver = _get_driver_or_exit(path)
    commits = get_linear_log(driver.repo_path, max_count=max_count)
    if not commits:
        print_info("No commit history found.")
    else:
        console.print(render_linear_log(commits))


# ============================================================================
# Scaffolding Subcommands: init, ruleset
# ============================================================================


def _print_scaffold_summary(
    engine: ScaffoldEngine,
    target_dir: Path,
    name: str,
    dry_run: bool,
) -> None:
    """Render scaffolded file creation/skip summary."""
    if dry_run:
        print_info(f"Dry run preview for '{name}' ({len(engine.manifest.rendered)} files):")
        for rel_file in sorted(engine.manifest.rendered.keys()):
            console.print(f"  [dim]- {rel_file}[/dim]")
        return

    for p in engine.manifest.created:
        try:
            rel = p.relative_to(target_dir)
        except ValueError:
            rel = p
        print_success(f"Created [bold]{rel}[/bold]")
    for p in engine.manifest.skipped:
        try:
            rel = p.relative_to(target_dir)
        except ValueError:
            rel = p
        print_warning(f"Skipped existing [dim]{rel}[/dim]")


@scaffold_app.command("init")
def scaffold_init_command(
    project_name: Optional[str] = typer.Option(
        None,
        "--project-name",
        "-n",
        help="Project / package name (defaults to repository directory name).",
    ),
    project_type: str = typer.Option(
        "python",
        "--project-type",
        "-t",
        help="Project ecosystem: 'python' or 'node'.",
    ),
    tier: str = typer.Option(
        "production",
        "--tier",
        help="Testing strictness tier: 'prototype', 'production', or 'strict'.",
    ),
    deploy_mode: str = typer.Option(
        "pm2",
        "--deploy-mode",
        help="Custom VPS runtime mode: 'pm2' or 'docker'.",
    ),
    build_strategy: str = typer.Option(
        "github",
        "--build-strategy",
        help="Where production builds execute: 'github' (artifact SCP) or 'vps' (SSH remote build).",
    ),
    domain: str = typer.Option(
        "yourdomain.com",
        "--domain",
        help="Primary domain used for Staging and Production URLs.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "--force",
        "-f",
        help="Overwrite existing configuration files.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate template rendering without writing to disk.",
    ),
    layer: str = typer.Option(
        "all",
        "--layer",
        "-l",
        help="Layer to scaffold: '1' (hooks), '2' (CI), '3' (Release Please), or 'all'.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target repository path (defaults to current directory).",
    ),
) -> None:
    """Scaffolds Layer 1 hooks, Layer 2 CI, Layer 3 Release Please, AI .gitignore, and AGENTS.md."""
    target_dir = (path or Path.cwd()).resolve()
    name = project_name or target_dir.name
    app_slug = name.lower().replace(" ", "-").strip() or "app"

    engine = ScaffoldEngine(
        target_dir=target_dir,
        dry_run=dry_run,
        overwrite=overwrite,
        raise_on_collision=False,
    )

    norm_layer = layer.strip().lower()
    if norm_layer in ("1", "layer1"):
        engine.scaffold_layer1(project_type=project_type)
    elif norm_layer in ("2", "layer2"):
        engine.scaffold_layer2(
            project_type=project_type,
            testing_tier=tier,
            deploy_mode=deploy_mode,
            build_strategy=build_strategy,
            domain=domain,
            app_name=app_slug,
        )
    elif norm_layer in ("3", "layer3"):
        engine.scaffold_layer3(package_name=name, project_type=project_type)
    else:
        engine.scaffold_all(
            project_name=name,
            project_type=project_type,
            overwrite=overwrite,
            testing_tier=tier,
            deploy_mode=deploy_mode,
            build_strategy=build_strategy,
            domain=domain,
        )

    _print_scaffold_summary(engine, target_dir, name, dry_run)


@scaffold_app.command("vps")
def scaffold_vps_command(
    app_name: Optional[str] = typer.Option(
        None,
        "--app-name",
        "-n",
        help="Application identifier used for VPS directories and processes.",
    ),
    project_type: str = typer.Option(
        "node",
        "--project-type",
        "-t",
        help="Project ecosystem: 'node' or 'python'.",
    ),
    deploy_mode: str = typer.Option(
        "pm2",
        "--deploy-mode",
        help="Process manager mode: 'pm2' or 'docker'.",
    ),
    proxy: str = typer.Option(
        "nginx",
        "--proxy",
        help="Reverse proxy template: 'nginx' or 'caddy'.",
    ),
    domain: str = typer.Option(
        "yourdomain.com",
        "--domain",
        help="Primary domain (staging.<domain> -> :3001, <domain> -> :3000).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "--force",
        "-f",
        help="Overwrite existing VPS configuration files.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate template rendering without writing to disk.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target repository path (defaults to current directory).",
    ),
) -> None:
    """Scaffolds custom VPS provisioning, PM2/Docker, and Nginx/Caddy configs under deploy/vps/."""
    target_dir = (path or Path.cwd()).resolve()
    name = app_name or target_dir.name

    engine = ScaffoldEngine(
        target_dir=target_dir,
        dry_run=dry_run,
        overwrite=overwrite,
        raise_on_collision=False,
    )
    try:
        engine.scaffold_vps_configs(
            app_name=name,
            project_type=project_type,
            deploy_mode=deploy_mode,
            proxy_type=proxy,
            domain=domain,
        )
    except ValueError as exc:
        print_error(str(exc), title="VPS Scaffold Error")
        raise typer.Exit(code=1)

    _print_scaffold_summary(engine, target_dir, name, dry_run)


@scaffold_app.command("agents")
def scaffold_agents_command(
    project_name: Optional[str] = typer.Option(
        None,
        "--project-name",
        "-n",
        help="Project name (defaults to repository directory name).",
    ),
    project_type: str = typer.Option(
        "python",
        "--project-type",
        "-t",
        help="Project ecosystem: 'python' or 'node'.",
    ),
    tier: str = typer.Option(
        "production",
        "--tier",
        help="Testing strictness tier referenced in AGENTS.md.",
    ),
    deploy_mode: str = typer.Option(
        "pm2",
        "--deploy-mode",
        help="Custom VPS runtime mode referenced in AGENTS.md.",
    ),
    domain: str = typer.Option(
        "yourdomain.com",
        "--domain",
        help="Primary domain referenced in AGENTS.md.",
    ),
    cursor_claude: bool = typer.Option(
        False,
        "--cursor-claude",
        "--sync-ide-rules",
        help="Also generate synchronized .cursorrules and CLAUDE.md files.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "--force",
        "-f",
        help="Overwrite existing hygiene files.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate template rendering without writing to disk.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target repository path (defaults to current directory).",
    ),
) -> None:
    """Scaffolds AGENTS.md, PR template, Dependabot, and optional .cursorrules / CLAUDE.md."""
    target_dir = (path or Path.cwd()).resolve()
    name = project_name or target_dir.name

    engine = ScaffoldEngine(
        target_dir=target_dir,
        dry_run=dry_run,
        overwrite=overwrite,
        raise_on_collision=False,
    )
    engine.scaffold_agent_hygiene(
        project_name=name,
        project_type=project_type,
        testing_tier=tier,
        deploy_mode=deploy_mode,
        domain=domain,
        sync_cursor_claude=cursor_claude,
    )
    _print_scaffold_summary(engine, target_dir, name, dry_run)


@scaffold_app.command("ruleset")
def scaffold_ruleset_command(
    script_type: str = typer.Option(
        "ps1",
        "--type",
        "-t",
        help="Script type: 'ps1' (PowerShell) or 'sh' (Bash).",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional output file path to write the script.",
    ),
    repo_name: Optional[str] = typer.Option(
        None,
        "--repo-name",
        "-r",
        help="Repository in 'owner/repo' format (e.g. 'myorg/myrepo').",
    ),
) -> None:
    """Outputs or prints GitHub CLI ruleset setup script."""
    try:
        script = generate_ruleset_script(
            repo_full_name=repo_name,
            script_type=script_type,
        )
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    if output:
        output_path = Path(output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(script, encoding="utf-8")
        print_success(f"Ruleset setup script written to '{output_path}'.")
    else:
        console.print(script)


# ============================================================================
# Multi-Repo Commands: scan, sync-all
# ============================================================================


@app.command("scan")
def scan_command(
    directory: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan for Git repositories (defaults to current directory).",
    ),
    max_depth: int = typer.Option(
        4,
        "--max-depth",
        "-d",
        help="Maximum folder search depth.",
    ),
) -> None:
    """Discovers repositories and prints rich multi-repo health table."""
    root = directory or Path.cwd()
    root_path = Path(root).resolve()
    repos = discover_repositories(root_path, max_depth=max_depth)

    if not repos:
        print_info(f"No Git repositories discovered in '{root_path}'.")
        return

    health_list = audit_repositories(repos)
    console.print(render_multirepo_table(health_list))


@app.command("sync-all")
def sync_all_command(
    directory: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan and synchronize repositories (defaults to current directory).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate linear rebase sync without modifying repositories.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Auto-stash uncommitted dirty changes across repositories.",
    ),
    max_depth: int = typer.Option(
        4,
        "--max-depth",
        "-d",
        help="Maximum directory search depth.",
    ),
) -> None:
    """Discovers and synchronizes clean repositories across projects, printing a rich summary report."""
    root = directory or Path.cwd()
    root_path = Path(root).resolve()
    repos = discover_repositories(root_path, max_depth=max_depth)

    if not repos:
        print_info(f"No Git repositories discovered in '{root_path}'.")
        return

    report = sync_all_repositories(repos, dry_run=dry_run, force=force)
    console.print(render_sync_summary_table(report))


# ============================================================================
# 3-Pillar CI Pre-Flight Validator & 5-Step GitHub Flow Commands
# ============================================================================


def _run_preflight_and_render(
    driver: GitDriver,
    tier: TestingTier = TestingTier.PRODUCTION,
) -> None:
    """Run all 3 local CI pre-flight pillars, render diagnostic table, and exit on failure."""
    report = run_ci_preflight(driver.repo_path, tier=tier)
    console.print(render_ci_preflight_table(report))

    for pillar in report.pillars:
        if pillar.status == CIPillarStatus.FAILED and pillar.output:
            console.print(
                create_panel(
                    pillar.output,
                    title=f"[bold red]{pillar.name} — Failure Output[/bold red]",
                    border_style="red",
                )
            )

    if not report.passed:
        print_error(
            "One or more CI pre-flight pillars failed. Resolve locally before pushing to GitHub.",
            title="CI Pre-Flight Failed",
        )
        raise typer.Exit(code=1)

    print_success(f"CI pre-flight ({report.tier.value} tier) passed. Ready to push safely!")


@app.command("check")
def check_command(
    tier: TestingTier = typer.Option(
        TestingTier.PRODUCTION,
        "--tier",
        "-t",
        help="Testing strictness tier: 'prototype', 'production', or 'strict'.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Run local 3-pillar CI pre-flight checks (Quality/Types, Tests, Standalone Build)."""
    driver = _get_driver_or_exit(path)
    _run_preflight_and_render(driver, tier=tier)


@flow_app.command("init-branches")
def flow_init_branches_command(
    no_push: bool = typer.Option(
        False,
        "--no-push",
        help="Create local staging branch without pushing main/staging to origin.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Bootstrap the 3-branch GitHub Flow topology (feat/* -> staging -> main)."""
    driver = _get_driver_or_exit(path)
    engine = GitHubFlowEngine(driver)
    try:
        res = engine.init_branches(push_remote=not no_push)
    except (RuntimeError, GitCommandError) as exc:
        print_error(f"Failed to initialize staging/main branches: {exc}")
        raise typer.Exit(code=1)

    status_note = "created 'staging'" if res["created_staging"] else "'staging' already existed"
    push_note = " and pushed to origin" if res["pushed_to_origin"] else ""
    print_success(f"3-branch topology ready ({status_note}{push_note}).")


@flow_app.command("start")
def flow_start_command(
    name: str = typer.Argument(
        ...,
        help="Feature/fix branch name (e.g. 'feat/user-auth', 'fix/navbar-layout').",
    ),
    base: Optional[str] = typer.Option(
        None,
        "--base",
        "-b",
        help="Base branch to sync and branch off (defaults to 'staging' if present, else 'main').",
    ),
    no_sync: bool = typer.Option(
        False,
        "--no-sync",
        help="Skip pulling latest base branch from origin before branching.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Bypass branch naming prefix validation.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Step 1: Sync base branch and create an isolated feature branch."""
    driver = _get_driver_or_exit(path)
    engine = GitHubFlowEngine(driver)
    try:
        engine.start_feature(
            branch_name=name,
            base_branch=base,
            sync_base=not no_sync,
            force=force,
        )
    except ValueError as exc:
        print_error(str(exc), title="GitHub Flow Start Failed")
        raise typer.Exit(code=1)
    except GitCommandError as exc:
        print_error(f"Git error starting feature branch: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    print_success(
        f"Step 1 complete: Working on isolated feature branch '[bold cyan]{name}[/bold cyan]'."
    )


@flow_app.command("check")
def flow_check_command(
    tier: TestingTier = typer.Option(
        TestingTier.PRODUCTION,
        "--tier",
        "-t",
        help="Testing strictness tier: 'prototype', 'production', or 'strict'.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Step 2: Run local 3-pillar CI pre-flight validation before pushing."""
    driver = _get_driver_or_exit(path)
    _run_preflight_and_render(driver, tier=tier)


@flow_app.command("pr")
def flow_pr_command(
    title: Optional[str] = typer.Option(
        None,
        "--title",
        "-t",
        help="Pull Request title (uses --fill from commits if omitted).",
    ),
    body: Optional[str] = typer.Option(
        None,
        "--body",
        "-m",
        help="Pull Request description body.",
    ),
    base: Optional[str] = typer.Option(
        None,
        "--base",
        "-b",
        help="Target base branch (defaults to 'staging' if present, else 'main').",
    ),
    draft: bool = typer.Option(
        False,
        "--draft",
        help="Create Pull Request as a draft.",
    ),
    no_check: bool = typer.Option(
        False,
        "--no-check",
        help="Skip local 3-pillar CI pre-flight validation before pushing.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Step 3: Validate 3 CI gates locally, push branch, and open a Pull Request."""
    driver = _get_driver_or_exit(path)
    engine = GitHubFlowEngine(driver)
    try:
        res = engine.open_pull_request(
            title=title,
            body=body,
            base_branch=base,
            draft=draft,
            run_checks=not no_check,
        )
    except (ValueError, RuntimeError) as exc:
        print_error(str(exc), title="Pull Request Blocked")
        raise typer.Exit(code=1)
    except GitCommandError as exc:
        print_error(f"Failed to open Pull Request: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    pr_out = res.stdout.strip()
    print_success("Step 3 complete: Pull Request opened on GitHub.")
    if pr_out:
        console.print(f"  [bold cyan]{pr_out}[/bold cyan]")


@flow_app.command("checks")
def flow_checks_command(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Step 4a: Inspect remote GitHub Actions PR check statuses."""
    driver = _get_driver_or_exit(path)
    engine = GitHubFlowEngine(driver)
    branch = driver.get_current_branch()
    try:
        checks = engine.get_pr_checks()
    except GitCommandError as exc:
        print_error(f"Failed to query PR checks: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    if not checks:
        print_info(f"No PR checks reported yet for branch '{branch}'.")
        return

    console.print(render_pr_checks_table(branch, checks))


@flow_app.command("logs")
def flow_logs_command(
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional output path to save the AI failure diagnostic report.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Step 4b: Fetch failed GitHub Actions logs and save AI diagnostic report."""
    driver = _get_driver_or_exit(path)
    engine = GitHubFlowEngine(driver)
    try:
        report_md = engine.fetch_ci_failure_logs(output_file=output)
    except (RuntimeError, GitCommandError) as exc:
        print_error(f"Failed to retrieve CI failure logs: {exc}")
        raise typer.Exit(code=1)

    console.print(report_md)
    saved_path = (
        Path(output).resolve()
        if output
        else (driver.repo_path / ".phantom-git" / "last-ci-failure.md").resolve()
    )
    if saved_path.exists():
        print_info(f"Saved AI diagnostic report to '{saved_path}'.")


@flow_app.command("merge")
def flow_merge_command(
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Enable GitHub auto-merge when checks turn green.",
    ),
    keep_branch: bool = typer.Option(
        False,
        "--keep-branch",
        help="Keep remote feature branch after squash merge.",
    ),
    base: Optional[str] = typer.Option(
        None,
        "--base",
        "-b",
        help="Base branch to return to after merging (defaults to 'staging' if present, else 'main').",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Step 5: Squash-merge green PR into base branch, delete branch, and sync local repo."""
    driver = _get_driver_or_exit(path)
    engine = GitHubFlowEngine(driver)
    resolved_base = base or engine.resolve_default_base_branch()
    try:
        engine.squash_and_merge(
            auto_merge=auto,
            delete_branch=not keep_branch,
            base_branch=resolved_base,
        )
    except (ValueError, RuntimeError) as exc:
        print_error(str(exc), title="Squash & Merge Blocked")
        raise typer.Exit(code=1)
    except GitCommandError as exc:
        print_error(f"PR merge failed: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    print_success(f"Step 5 complete: PR squash-merged and returned cleanly to '{resolved_base}'.")


@flow_app.command("promote")
def flow_promote_command(
    watch: bool = typer.Option(
        False,
        "--watch",
        help="Watch GitHub Actions checks on the promotion PR.",
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Enable GitHub auto-merge when checks turn green.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Flow B: Promote persistent 'staging' branch to 'main' via a standard merge commit."""
    driver = _get_driver_or_exit(path)
    engine = GitHubFlowEngine(driver)
    try:
        res = engine.promote_staging_to_main(watch_checks=watch, auto_merge=auto)
    except (ValueError, RuntimeError) as exc:
        print_error(str(exc), title="Staging Promotion Blocked")
        raise typer.Exit(code=1)
    except GitCommandError as exc:
        print_error(f"Staging promotion failed: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    pr_url = res.get("pr_url") or ""
    if auto:
        print_success(f"Auto-merge enabled for promotion PR (staging -> main). {pr_url}".strip())
    else:
        print_success(f"Promoted 'staging' -> 'main' via standard merge commit! {pr_url}".strip())


# ============================================================================
# Environment & Secrets Hygiene Commands (`pgit env`)
# ============================================================================


@env_app.command("sync")
def env_sync_command(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target repository path (defaults to current directory).",
    ),
) -> None:
    """Scan .env* and source code to sync missing safe placeholders into .env.example."""
    target_dir = (path or Path.cwd()).resolve()
    if not target_dir.exists():
        print_error(f"Path '{target_dir}' does not exist.", title="Path Not Found")
        raise typer.Exit(code=1)

    report = sync_env_example(target_dir)
    if report.added_keys:
        print_success(
            f"Updated '.env.example' with {len(report.added_keys)} new key(s): "
            f"{', '.join(report.added_keys)}"
        )
    else:
        print_info(
            f"'.env.example' is already up to date ({len(report.discovered_keys)} key(s) tracked)."
        )


@env_app.command("set")
def env_set_command(
    key: str = typer.Argument(
        ..., help="Environment variable / secret name (e.g. 'OPENAI_API_KEY')."
    ),
    value: str = typer.Argument(..., help="Secret or variable value."),
    env_name: str = typer.Option(
        "staging",
        "--env",
        "-e",
        help="Target GitHub Environment: 'staging', 'production', or 'repo'.",
    ),
    variable: bool = typer.Option(
        False,
        "--variable",
        help="Store as non-sensitive Actions Variable instead of encrypted Secret.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path (defaults to current directory).",
    ),
) -> None:
    """Provision a GitHub Environment secret or variable via `gh`."""
    driver = _get_driver_or_exit(path)
    try:
        set_github_env_secret(
            driver,
            key=key,
            value=value,
            environment=env_name,
            is_variable=variable,
        )
    except ValueError as exc:
        print_error(str(exc), title="Invalid Environment Argument")
        raise typer.Exit(code=1)
    except GitCommandError as exc:
        print_error(f"Failed to set GitHub secret/variable: {exc.stderr or str(exc)}")
        raise typer.Exit(code=1)

    kind = "variable" if variable else "secret"
    print_success(f"Set GitHub {kind} '[bold cyan]{key}[/bold cyan]' in '{env_name}'.")


# ============================================================================
# GitHub Account Authentication & Repositories (`pgit auth`)
# ============================================================================


@auth_app.command("status")
def auth_status_command(
    hostname: str = typer.Option(
        "github.com",
        "--hostname",
        help="GitHub hostname (default: github.com).",
    ),
) -> None:
    """Display the currently authenticated GitHub account status."""
    mgr = GitHubAuthManager()
    status = mgr.get_status(hostname=hostname)
    if status.authenticated:
        scopes_str = ", ".join(status.scopes) if status.scopes else "default"
        body = (
            f"[bold green]Authenticated[/bold green] as [bold cyan]@{status.username or 'unknown'}[/bold cyan]\n"
            f"Host: [white]{status.host}[/white] | Protocol: [white]{status.protocol}[/white]\n"
            f"Scopes: [dim]{scopes_str}[/dim]"
        )
        console.print(create_panel(body, title="GitHub Account Status", border_style="green"))
    else:
        detail = status.raw_output or "Not logged into GitHub. Run 'pgit auth login' to connect."
        console.print(
            create_panel(
                f"[bold yellow]Not signed in[/bold yellow]\n[dim]{detail}[/dim]",
                title="GitHub Account Status",
                border_style="yellow",
            )
        )


@auth_app.command("login")
def auth_login_command(
    token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        help="Personal Access Token (PAT) for non-interactive sign-in.",
    ),
    web: bool = typer.Option(
        False,
        "--web",
        "-w",
        help="Authenticate interactively via GitHub browser OAuth device flow.",
    ),
    hostname: str = typer.Option(
        "github.com",
        "--hostname",
        help="GitHub hostname (default: github.com).",
    ),
    protocol: str = typer.Option(
        "https",
        "--protocol",
        help="Git operations protocol ('https' or 'ssh').",
    ),
) -> None:
    """Sign into a GitHub account through Phantom Git (via PAT or browser OAuth)."""
    mgr = GitHubAuthManager()
    if token is not None:
        try:
            status = mgr.login_with_token(
                token=token,
                hostname=hostname,
                git_protocol=protocol,
            )
        except (ValueError, GitCommandError) as exc:
            print_error(f"GitHub login failed: {exc}")
            raise typer.Exit(code=1)

        if status.authenticated:
            print_success(f"Signed in to {hostname} as @{status.username or 'GitHub user'}.")
        else:
            print_warning(
                "Token submitted, but GitHub status did not report active authentication."
            )
        return

    import subprocess

    gh_bin = find_gh_binary()
    print_info(f"Launching GitHub browser authentication for {hostname}...")
    proc = subprocess.run(
        [
            gh_bin,
            "auth",
            "login",
            "--hostname",
            hostname,
            "--git-protocol",
            protocol,
            "--web",
            "-s",
            "repo,workflow,read:org",
        ],
        check=False,
    )
    if proc.returncode != 0:
        print_error("Interactive GitHub web login did not complete successfully.")
        raise typer.Exit(code=proc.returncode or 1)

    mgr.run_gh(["auth", "setup-git", "--hostname", hostname], check=False)
    status = mgr.get_status(hostname=hostname)
    if status.authenticated:
        print_success(f"Signed in to {hostname} as @{status.username or 'GitHub user'}.")
    else:
        print_info("GitHub CLI login completed.")


@auth_app.command("logout")
def auth_logout_command(
    hostname: str = typer.Option(
        "github.com",
        "--hostname",
        help="GitHub hostname (default: github.com).",
    ),
) -> None:
    """Sign out of the connected GitHub account."""
    mgr = GitHubAuthManager()
    res = mgr.logout(hostname=hostname)
    if res.success:
        print_success(f"Logged out from {hostname}.")
    else:
        print_warning(res.stderr or res.stdout or f"Could not log out from {hostname}.")


@auth_app.command("repos")
def auth_repos_command(
    workspace: Optional[Path] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Local parent workspace to match cloned repositories against.",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum number of repositories to fetch from GitHub.",
    ),
) -> None:
    """List repositories available on the connected GitHub account."""
    mgr = GitHubAuthManager()
    ws = Path(workspace).resolve() if workspace else Path.cwd().parent.resolve()
    try:
        repos = mgr.list_repos(workspace_path=ws, limit=limit)
    except (GitCommandError, RuntimeError) as exc:
        print_error(f"Failed to list GitHub repositories: {exc}")
        raise typer.Exit(code=1)

    if not repos:
        print_info("No repositories found on the connected GitHub account.")
        return

    table = Table(
        title="Connected GitHub Repositories",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_header=True,
    )
    table.add_column("Repository", style="bold white", no_wrap=True)
    table.add_column("Visibility", justify="center", no_wrap=True)
    table.add_column("Default Branch", style="cyan", no_wrap=True)
    table.add_column("Local Clone", style="green", overflow="fold")
    table.add_column("URL", style="dim", overflow="fold")

    for r in repos:
        vis = "[yellow]private[/yellow]" if r.is_private else "[green]public[/green]"
        local = r.local_path or "[dim]remote only[/dim]"
        table.add_row(r.full_name, vis, r.default_branch, local, r.url)
    console.print(table)


# ============================================================================
# Interactive Mouse-Enabled Lazygit-Style TUI (`pgit tui` / `pgit ui`)
# ============================================================================


def _launch_tui(path: Optional[Path], workspace: Optional[Path]) -> None:
    from git_manager.tui import run_tui

    run_tui(repo_path=path, workspace_path=workspace)


@app.command("tui")
def tui_command(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target repository path (defaults to current directory).",
    ),
    workspace: Optional[Path] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Multi-repo parent workspace directory for the Archive Hub tab.",
    ),
) -> None:
    """Launch the Phantom Git mouse-enabled Lazygit-style TUI."""
    _launch_tui(path, workspace)


@app.command("ui")
def ui_command(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target repository path (defaults to current directory).",
    ),
    workspace: Optional[Path] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Multi-repo parent workspace directory for the Archive Hub tab.",
    ),
) -> None:
    """Alias for 'pgit tui' — launch the interactive Purple & Neon TUI."""
    _launch_tui(path, workspace)


if __name__ == "__main__":
    app()
