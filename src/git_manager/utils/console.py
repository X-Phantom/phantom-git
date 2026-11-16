"""
Rich console configuration and terminal UI output helpers.
Provides consistent styling and non-interactive fallbacks for both humans and AI agents.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional, Sequence

# Windows UTF-8 console output hardening
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from git_manager.core.models import (
    CIPillarStatus,
    CIPreFlightReport,
    PRCheckItem,
    RepoHealth,
    RepoHealthStatus,
    RepoStatus,
    SyncReport,
    SyncStatus,
)

# Semantic color theme for Phantom Git (Purple & Neon company palette)
CUSTOM_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "highlight": "bold magenta",
        "branch": "cyan",
        "hash": "dim white",
        "clean": "green",
        "dirty": "yellow",
        "diverged": "red",
        "brand": "bold #9D4EDD",
        "neon_purple": "bold #E040FB",
        "neon_pink": "bold #FF2A85",
        "neon_cyan": "bold #00F5D4",
        "neon_green": "bold #00FF87",
    }
)

# Global singleton consoles
console = Console(theme=CUSTOM_THEME)
err_console = Console(stderr=True, theme=CUSTOM_THEME)


def _safe_glyph(symbol: str, fallback: str) -> str:
    """Return symbol if encodable by sys.stdout, else fallback safely."""
    try:
        enc = sys.stdout.encoding or "utf-8"
        symbol.encode(enc)
        return symbol
    except Exception:
        return fallback


# Safe console symbols with cp1252 fallbacks
SYM_SUCCESS = _safe_glyph("✔", "+")
SYM_ERROR = _safe_glyph("✘", "x")
SYM_WARN = _safe_glyph("⚠", "!")
SYM_INFO = _safe_glyph("ℹ", "i")


def is_interactive() -> bool:
    """Return True if the current environment is an interactive TTY."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def print_header(title: str, subtitle: Optional[str] = None) -> None:
    """Print a stylized header banner."""
    panel = Panel(
        f"[bold white]{title}[/bold white]" + (f"\n[dim]{subtitle}[/dim]" if subtitle else ""),
        border_style="cyan",
        box=box.ROUNDED,
        expand=False,
    )
    console.print(panel)


def print_success(message: str, title: Optional[str] = None) -> None:
    """Print a success message with green styling."""
    sym = _safe_glyph(SYM_SUCCESS, "+")
    prefix = f"[success]{sym} {title + ': ' if title else ''}[/success]"
    console.print(f"{prefix}{message}")


def print_error(message: str, title: Optional[str] = None) -> None:
    """Print an error message to stderr with red styling."""
    sym = _safe_glyph(SYM_ERROR, "x")
    prefix = f"[error]{sym} {title + ': ' if title else ''}[/error]"
    err_console.print(f"{prefix}{message}")


def print_warning(message: str, title: Optional[str] = None) -> None:
    """Print a warning message with yellow styling."""
    sym = _safe_glyph(SYM_WARN, "!")
    prefix = f"[warning]{sym} {title + ': ' if title else ''}[/warning]"
    console.print(f"{prefix}{message}")


def print_info(message: str, title: Optional[str] = None) -> None:
    """Print an informational message with cyan styling."""
    sym = _safe_glyph(SYM_INFO, "i")
    prefix = f"[info]{sym} {title + ': ' if title else ''}[/info]"
    console.print(f"{prefix}{message}")


def create_panel(
    content: Any,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    border_style: str = "cyan",
) -> Panel:
    """Create a standardized Rich Panel container."""
    return Panel(
        content,
        title=title,
        subtitle=subtitle,
        border_style=border_style,
        expand=False,
        padding=(0, 1),
    )


def create_table(
    title: Optional[str] = None,
    columns: Optional[list[str]] = None,
    border_style: str = "cyan",
) -> Table:
    """Create a standardized Rich Table."""
    table = Table(
        title=title,
        border_style=border_style,
        header_style="bold cyan",
        show_edge=True,
    )
    if columns:
        for col in columns:
            table.add_column(col)
    return table


def format_health_badge(status: RepoHealthStatus | str | None) -> str:
    """
    Format a colored status badge for RepoHealthStatus.
    - CLEAN = green
    - DIRTY = yellow
    - DIVERGED = red bold
    - AHEAD = cyan
    - BEHIND = magenta
    - DETACHED = dark orange
    """
    if status is None:
        return "[dim]UNKNOWN[/dim]"
    st = status.value if isinstance(status, RepoHealthStatus) else str(status).lower()
    if st in ("clean", "healthy"):
        return f"[bold green]{_safe_glyph(SYM_SUCCESS, '+')} CLEAN[/bold green]"
    elif st == "dirty":
        return f"[bold yellow]{_safe_glyph(SYM_WARN, '!')} DIRTY[/bold yellow]"
    elif st == "diverged":
        return f"[bold red]{_safe_glyph(SYM_ERROR, 'x')} DIVERGED[/bold red]"
    elif st == "ahead":
        return "[bold cyan]AHEAD[/bold cyan]"
    elif st == "behind":
        return "[bold magenta]BEHIND[/bold magenta]"
    elif st == "detached":
        return "[bold dark_orange]DETACHED[/bold dark_orange]"
    return f"[bold white]{st.upper()}[/bold white]"


get_status_badge = format_health_badge


def get_commit_type_badge(commit_type: str, is_breaking: bool = False) -> str:
    """Format a styled badge for Conventional Commit types."""
    ctype = commit_type.lower().strip()
    badge_map = {
        "feat": "[bold cyan]feat[/bold cyan]",
        "fix": "[bold green]fix[/bold green]",
        "docs": "[bold blue]docs[/bold blue]",
        "chore": "[dim]chore[/dim]",
        "test": "[yellow]test[/yellow]",
        "refactor": "[magenta]refactor[/magenta]",
        "ci": "[blue]ci[/blue]",
        "perf": "[bold yellow]perf[/bold yellow]",
        "build": "[dim cyan]build[/dim cyan]",
        "style": "[dim magenta]style[/dim magenta]",
    }
    badge = badge_map.get(ctype, f"[white]{ctype}[/white]")
    if is_breaking:
        badge = f"[bold red]!{badge}[/bold red]"
    return badge


def render_repo_status_table(status: RepoStatus) -> Table:
    """
    Generate a rich table for a single repository's status.
    Displays branch, remote, commit sha, stashes, and file breakdowns.
    """
    repo_name = Path(status.repo_path).name or status.repo_path
    table = Table(
        title=f"Repository Status: [bold cyan]{repo_name}[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_header=True,
    )
    table.add_column("Property", style="bold white", no_wrap=True)
    table.add_column("Details", style="white")

    table.add_row("Path", str(status.repo_path))
    table.add_row("Current Branch", f"[bold cyan]{status.branch_name}[/bold cyan]")
    table.add_row(
        "Commit SHA",
        f"[dim]{status.commit_sha[:8] if status.commit_sha else 'None'}[/dim]",
    )
    table.add_row("Upstream Tracking", status.upstream or "[dim]None[/dim]")

    # Ahead / Behind
    ahead_behind_str = f"+{status.ahead_count} / -{status.behind_count}"
    if status.ahead_count > 0 and status.behind_count > 0:
        sync_str = f"[bold red]{ahead_behind_str} (Diverged)[/bold red]"
    elif status.ahead_count > 0:
        sync_str = f"[bold cyan]{ahead_behind_str} (Ahead)[/bold cyan]"
    elif status.behind_count > 0:
        sync_str = f"[bold magenta]{ahead_behind_str} (Behind)[/bold magenta]"
    else:
        sync_str = f"[green]{ahead_behind_str} (Up to date)[/green]"
    table.add_row("Sync State", sync_str)

    table.add_row("Stashes", str(status.stash_count))

    # Health / Clean status
    health_badge = format_health_badge(
        RepoHealthStatus.CLEAN if status.is_clean else RepoHealthStatus.DIRTY
    )
    table.add_row("Health Status", health_badge)

    # File breakdowns
    if status.staged_files:
        staged_items = "\n".join(
            f"[green]{f.staged_status or '+'} {f.path}[/green]" for f in status.staged_files
        )
        table.add_row(f"Staged ({len(status.staged_files)})", staged_items)

    if status.unstaged_files:
        unstaged_items = "\n".join(
            f"[yellow]{f.unstaged_status or 'M'} {f.path}[/yellow]" for f in status.unstaged_files
        )
        table.add_row(f"Unstaged ({len(status.unstaged_files)})", unstaged_items)

    if status.untracked_files:
        untracked_items = "\n".join(f"[red]? {f.path}[/red]" for f in status.untracked_files)
        table.add_row(f"Untracked ({len(status.untracked_files)})", untracked_items)

    if status.is_clean:
        table.add_row("Working Tree", "[green]Working tree is clean.[/green]")

    return table


render_repo_status = render_repo_status_table


def render_multirepo_table(
    health_list: Sequence[RepoHealth],
    title: str = "Multi-Repo Health Dashboard",
) -> Table:
    """
    Generate a formatted table for multi-repo health status.
    Columns: Repository, Branch, Status, Changes, Stashes, Sync, Recommendation.
    """
    table = Table(
        title=f"[bold]{title}[/bold]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_header=True,
    )
    table.add_column("Repository", style="bold white", no_wrap=True)
    table.add_column("Branch", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Working Tree", justify="center")
    table.add_column("Stashes", justify="right")
    table.add_column("Sync (Upstream)", justify="center")
    table.add_column("Recommendation", style="dim")

    for h in health_list:
        badge = format_health_badge(h.status)
        dirt_str = (
            "[green]Clean[/green]"
            if h.is_clean
            else f"[yellow]Mod: {h.modified_count}, Untracked: {h.untracked_count}[/yellow]"
        )

        sync_str = f"+{h.ahead_count}/-{h.behind_count}" if h.has_remote else "[dim]No Remote[/dim]"
        if h.ahead_count > 0 and h.behind_count > 0:
            sync_str = f"[bold red]{sync_str}[/bold red]"
        elif h.ahead_count > 0:
            sync_str = f"[cyan]{sync_str}[/cyan]"
        elif h.behind_count > 0:
            sync_str = f"[magenta]{sync_str}[/magenta]"

        table.add_row(
            h.name,
            h.current_branch,
            badge,
            dirt_str,
            str(h.stash_count),
            sync_str,
            h.recommendation or "",
        )

    return table


def render_sync_summary_table(
    report: SyncReport,
    title: str = "Multi-Repo Sync Summary Report",
) -> Table:
    """
    Generate a summary table of bulk linear rebase sync operations across repositories.
    """
    table = Table(
        title=f"[bold]{title}[/bold]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_header=True,
        caption=(
            f"Total: {report.total} | Synced: [bold green]{report.synced}[/bold green] | "
            f"Up to date: [green]{report.up_to_date}[/green] | "
            f"Skipped: [yellow]{report.skipped}[/yellow] | "
            f"Failed: [bold red]{report.failed}[/bold red]"
        ),
    )
    table.add_column("Repository", style="bold white", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Details", style="white")

    for rec in report.records:
        repo_name = Path(rec.repo_path).name or rec.repo_path
        st = rec.status
        if st == SyncStatus.SYNCED:
            st_str = "[bold green]SYNCED[/bold green]"
        elif st in (SyncStatus.ALREADY_UP_TO_DATE, SyncStatus.UP_TO_DATE):
            st_str = "[green]UP TO DATE[/green]"
        elif st == SyncStatus.SKIPPED_DIRTY:
            st_str = "[bold yellow]SKIPPED (DIRTY)[/bold yellow]"
        elif st in (SyncStatus.SKIPPED_NO_UPSTREAM, SyncStatus.NO_UPSTREAM):
            st_str = "[magenta]SKIPPED (NO UPSTREAM)[/magenta]"
        elif st in (SyncStatus.SKIPPED_DIVERGED, SyncStatus.DIVERGED):
            st_str = "[bold red]SKIPPED (DIVERGED)[/bold red]"
        elif st == SyncStatus.FAILED:
            st_str = "[bold red]FAILED[/bold red]"
        else:
            st_str = f"[white]{st.value}[/white]"

        table.add_row(repo_name, st_str, rec.message)

    return table


def render_linear_log(
    commits: Sequence[dict[str, Any]],
    title: str = "Linear Commit History",
) -> Table:
    """
    Generate a formatted table representing a condensed linear commit log graph.
    """
    table = Table(
        title=f"[bold]{title}[/bold]",
        box=box.SIMPLE_HEAVY,
        border_style="cyan",
        header_style="bold cyan",
        show_header=True,
    )
    table.add_column("Hash", style="dim cyan", width=9, no_wrap=True)
    table.add_column("Type", justify="center", width=10)
    table.add_column("Decorations", style="bold yellow")
    table.add_column("Subject", style="white", no_wrap=True)
    table.add_column("Author", style="dim")
    table.add_column("Date", style="dim")

    for c in commits:
        short_hash = c.get("short_hash") or c.get("hash", "")[:7]
        ctype = c.get("commit_type", "other")
        type_badge = get_commit_type_badge(ctype)
        decorations = c.get("decorations", "")
        subject = c.get("subject", "")
        author = c.get("author", "")
        rel_date = c.get("relative_date", "")

        table.add_row(
            short_hash,
            type_badge,
            decorations,
            subject,
            author,
            rel_date,
        )

    return table


def render_ci_preflight_table(report: CIPreFlightReport) -> Table:
    """
    Generate a formatted table showing results for all 3 CI Pre-Flight pillars.
    """
    repo_name = Path(report.repo_path).name or report.repo_path
    overall = "[bold green]PASSED[/bold green]" if report.passed else "[bold red]FAILED[/bold red]"
    table = Table(
        title="[bold]Phantom Git — 3-Pillar CI Pre-Flight Report[/bold]",
        box=box.ROUNDED,
        border_style="cyan" if report.passed else "red",
        header_style="bold cyan",
        show_header=True,
        caption=f"Repository: {repo_name} ({report.project_type}) | Overall: {overall}",
    )
    table.add_column("Pillar", style="bold white", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Duration", justify="right", style="dim", no_wrap=True)
    table.add_column("Command / Details", style="white")

    for pillar in report.pillars:
        if pillar.status == CIPillarStatus.PASSED:
            st_badge = f"[bold green]{_safe_glyph('✔', '+')} PASSED[/bold green]"
        elif pillar.status == CIPillarStatus.FAILED:
            st_badge = f"[bold red]{_safe_glyph('✘', 'x')} FAILED[/bold red]"
        else:
            st_badge = "[yellow]- SKIPPED[/yellow]"

        dur_str = f"{pillar.duration_seconds:.2f}s"
        detail_lines: list[str] = []
        if pillar.command:
            detail_lines.append(f"[dim]$ {pillar.command}[/dim]")
        if pillar.output:
            first_line = pillar.output.strip().splitlines()[0]
            if len(first_line) > 100:
                first_line = first_line[:97] + "..."
            detail_lines.append(first_line)

        table.add_row(
            pillar.name,
            st_badge,
            dur_str,
            "\n".join(detail_lines) or "-",
        )

    return table


def render_pr_checks_table(branch: str, checks: Sequence[PRCheckItem]) -> Table:
    """
    Generate a formatted table displaying remote GitHub Actions PR check statuses.
    """
    table = Table(
        title=f"[bold]Pull Request CI Checks ([cyan]{branch}[/cyan])[/bold]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_header=True,
    )
    table.add_column("Check", style="bold white")
    table.add_column("State", justify="center", no_wrap=True)
    table.add_column("Link", style="dim")

    for item in checks:
        state_up = item.state.upper()
        if state_up in ("SUCCESS", "PASS"):
            st_str = f"[bold green]{state_up}[/bold green]"
        elif state_up in ("FAILURE", "FAIL", "ERROR", "CANCELLED", "TIMED_OUT"):
            st_str = f"[bold red]{state_up}[/bold red]"
        elif state_up in ("SKIPPED", "NEUTRAL"):
            st_str = f"[dim]{state_up}[/dim]"
        else:
            st_str = f"[bold yellow]{state_up}[/bold yellow]"

        table.add_row(item.name, st_str, item.link or "-")

    return table
