"""
Phantom Git v0.5.0 — Pure Lazygit-Style Single-Screen Mouse & Keyboard TUI.
Runs in the terminal's alternate screen buffer and terminates cleanly on Ctrl+C / q.

Layout:
- Left Column:
  [1]-Status
  [2]-Files - Worktrees - Submodules
  [3]-Local branches - Remotes - Tags
  [4]-Commits - Reflog
  [5]-Stash
- Right Column:
  [6]-GitHub Account & Connected Repositories
  [0]-CI / GitHub Flow Status & Checks (plus Live Diff Inspector)
  Command log
- Bottom Footer:
  Essential keybindings for navigation & actions + version
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
import threading
from typing import Any, Optional

from rich.syntax import Syntax
from rich.table import Table
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from git_manager import __version__
from git_manager.core.branch_hygiene import BranchManager
from git_manager.core.ci_checks import detect_project_type, run_ci_preflight
from git_manager.core.commit_parser import suggest_conventional_commit
from git_manager.core.env_manager import set_github_env_secret
from git_manager.core.git_driver import GitDriver, find_repo_root
from git_manager.core.github_auth import GitHubAuthManager, find_gh_binary
from git_manager.core.github_flow import PROTECTED_BRANCHES, GitHubFlowEngine
from git_manager.core.models import (
    CIPillarStatus,
    CIPreFlightReport,
    ConventionalCommit,
    FileStatus,
    GitCommandError,
    GitHubAccountStatus,
    GitHubRepoItem,
    TestingTier,
)
from git_manager.core.safety_net import SafetyNet
from git_manager.scaffold.engine import ScaffoldEngine
from git_manager.tui.modals import (
    CommitModal,
    GitHubAuthModal,
    KeybindingsModal,
    NewBranchModal,
    SecretModal,
    SnapshotModal,
)


def _author_initials(author_name: str) -> str:
    """Return a compact 2-character author badge for the Lazygit commits panel."""
    cleaned = (author_name or "").strip()
    if not cleaned:
        return "??"
    parts = [p for p in cleaned.replace("-", " ").split() if p]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    return cleaned[:2].capitalize()


class PhantomGitApp(App[None]):
    """Unified single-screen Lazygit-style TUI for Phantom Git."""

    CSS_PATH = "theme.tcss"
    TITLE = f"Phantom Git v{__version__}"
    ENABLE_COMMAND_PALETTE = True

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("q", "quit", "Quit"),
        Binding("1", "focus_panel('status')", "Status", show=False),
        Binding("2", "focus_panel('files')", "Files", show=False),
        Binding("3", "focus_panel('branches')", "Branches", show=False),
        Binding("4", "focus_panel('commits')", "Commits", show=False),
        Binding("5", "focus_panel('safety')", "Stash", show=False),
        Binding("6", "focus_panel('github')", "GitHub", show=False),
        Binding("0", "focus_panel('ci')", "CI/Flow", show=False),
        Binding("@", "toggle_command_log", "CmdLog", show=False),
        Binding("space", "primary_space_action", "Stage/Select"),
        Binding("a", "stage_all", "Stage All"),
        Binding("d", "discard_selected_file", "Discard"),
        Binding("c", "open_commit_modal", "Commit"),
        Binding("A", "ai_auto_commit", "AI Commit"),
        Binding("n", "open_new_branch_modal", "Branch"),
        Binding("s", "stash_save", "Stash"),
        Binding("Z", "stash_pop", "Pop"),
        Binding("B", "open_snapshot_modal", "Snapshot"),
        Binding("u", "undo_last", "Undo"),
        Binding("D", "undo_last", "Undo"),
        Binding("k", "run_ci_checks", "Check"),
        Binding("p", "flow_open_pr", "PR"),
        Binding("f", "flow_refresh_pr_checks", "Checks"),
        Binding("l", "flow_diagnose_logs", "Logs"),
        Binding("m", "flow_merge_pr", "Merge"),
        Binding("P", "flow_promote", "Promote"),
        Binding("g", "open_github_auth_modal", "GitHub"),
        Binding("R", "refresh_github_and_workspace", "Refresh GitHub"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("S", "scaffold_guardrails", "Scaffold"),
        Binding("E", "open_secret_modal", "Secret"),
        Binding("?", "open_keybindings_modal", "Keybindings"),
    ]

    def __init__(
        self,
        repo_path: Path | str | None = None,
        workspace_path: Path | str | None = None,
        github_auth: GitHubAuthManager | None = None,
    ) -> None:
        super().__init__()
        start_path = Path(repo_path).resolve() if repo_path else Path.cwd().resolve()
        detected_root = find_repo_root(start_path)
        self.repo_path: Path = detected_root or start_path
        self.workspace_path: Path = (
            Path(workspace_path).resolve() if workspace_path else self.repo_path.parent
        )

        self.driver = GitDriver(self.repo_path)
        self.safety = SafetyNet(self.driver)
        self.flow = GitHubFlowEngine(self.driver)
        self.github_auth = github_auth or GitHubAuthManager()

        self._file_entries: list[FileStatus] = []
        self._branch_entries: list[str] = []
        self._commit_entries: list[dict[str, Any]] = []
        self._safety_entries: list[dict[str, Any]] = []
        self._github_repos: list[GitHubRepoItem] = []
        self._github_status = GitHubAccountStatus()
        self._last_ci_report: CIPreFlightReport | None = None
        self._command_listener_registered = False

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        """Keep Ctrl+C / quit always active; guard single-key bindings in modals/inputs."""
        if action == "quit":
            return True
        if len(self.screen_stack) > 1:
            return False
        if action in (
            "focus_panel",
            "toggle_command_log",
            "primary_space_action",
            "toggle_stage_selected",
            "stage_all",
            "discard_selected_file",
            "open_commit_modal",
            "ai_auto_commit",
            "open_new_branch_modal",
            "stash_save",
            "stash_pop",
            "open_snapshot_modal",
            "undo_last",
            "run_ci_checks",
            "flow_open_pr",
            "flow_refresh_pr_checks",
            "flow_diagnose_logs",
            "flow_merge_pr",
            "flow_promote",
            "open_github_auth_modal",
            "refresh_github_and_workspace",
            "refresh_all",
            "scaffold_guardrails",
            "open_secret_modal",
            "open_keybindings_modal",
        ) and isinstance(self.focused, Input):
            return False
        return True

    def compose(self) -> ComposeResult:
        with Horizontal(id="workspace-grid"):
            # ================================================================
            # Left Column: [1]-Status, [2]-Files, [3]-Branches, [4]-Commits, [5]-Stash
            # ================================================================
            with Vertical(id="left-dock"):
                with Vertical(id="panel-status", classes="lazygit-panel"):
                    yield Static("Loading...", id="status-summary")

                with Vertical(id="panel-files", classes="lazygit-panel"):
                    yield OptionList(id="files-list")

                with Vertical(id="panel-branches", classes="lazygit-panel"):
                    yield OptionList(id="branches-list")

                with Vertical(id="panel-commits", classes="lazygit-panel"):
                    yield OptionList(id="commits-list")

                with Vertical(id="panel-safety", classes="lazygit-panel"):
                    yield OptionList(id="safety-list")

            # ================================================================
            # Right Column (3 Larger Containers in Exact Order):
            # 1. [6]-GitHub Account & Connected Repositories
            # 2. [0]-CI / GitHub Flow Status & Checks (+ Live Diff Inspector)
            # 3. Command log
            # ================================================================
            with Vertical(id="right-main"):
                with Vertical(id="panel-github-repos", classes="lazygit-panel"):
                    yield Static("Checking GitHub authentication...", id="github-account-bar")
                    yield OptionList(id="github-repos-list")

                with Vertical(id="panel-ci-flow", classes="lazygit-panel"):
                    yield Static("Loading CI & Flow status...", id="ci-flow-summary")
                    yield RichLog(id="inspector-view", markup=True, wrap=True)

                with Vertical(id="panel-command-log", classes="lazygit-panel"):
                    yield RichLog(id="command-log", markup=True, wrap=True)

        # Bottom Single-Line Lazygit Keybindings Footer
        with Horizontal(id="lazygit-footer"):
            yield Static(
                "[#00F5D4]Stage: <space> | Commit: c | Stash: s | Discard: d | Undo: u | "
                "Branch: n | Check: k | PR: p | GitHub: g | Keybindings: ?[/]",
                id="footer-keybindings",
            )
            yield Static(f"[bold #E040FB]Phantom Git {__version__}[/]", id="footer-version")

    def on_mount(self) -> None:
        """Set Lazygit border titles, start command logging, and populate all panels."""
        self.query_one("#panel-status", Vertical).border_title = "[1]-Status"
        self.query_one("#panel-files", Vertical).border_title = "[2]-Files - Worktrees - Submodules"
        self.query_one(
            "#panel-branches", Vertical
        ).border_title = "[3]-Local branches - Remotes - Tags"
        self.query_one("#panel-commits", Vertical).border_title = "[4]-Commits - Reflog"
        self.query_one("#panel-safety", Vertical).border_title = "[5]-Stash"

        self.query_one(
            "#panel-github-repos", Vertical
        ).border_title = "[6]-GitHub Account & Connected Repositories"
        self.query_one(
            "#panel-ci-flow", Vertical
        ).border_title = "[0]-CI / GitHub Flow Status & Checks"
        self.query_one("#panel-command-log", Vertical).border_title = "Command log"

        cmd_log = self.query_one("#command-log", RichLog)
        cmd_log.write("[#00F5D4]You can hide/focus this panel by pressing '@'[/]")
        cmd_log.write(
            "[dim #E0AAFF]Tip: Press '?' for all keybindings or 'g' to sign into GitHub.[/]"
        )

        GitDriver.add_command_listener(self._on_git_command)
        self._command_listener_registered = True

        self.refresh_workspace()
        self.refresh_github_state()
        self.query_one("#files-list", OptionList).focus()

    def on_unmount(self) -> None:
        if self._command_listener_registered:
            GitDriver.remove_command_listener(self._on_git_command)
            self._command_listener_registered = False

    # ------------------------------------------------------------------------
    # Logging, Counter Badges & Inspector Helpers
    # ------------------------------------------------------------------------

    def _on_git_command(self, command_str: str) -> None:
        """Real-time observer callback invoked on every git/gh subprocess call."""
        if not self.is_running:
            return
        if threading.current_thread() is threading.main_thread():
            self._write_command_entry(f"[#E0AAFF]  {command_str}[/]")
        else:
            try:
                self.call_from_thread(self._write_command_entry, f"[#E0AAFF]  {command_str}[/]")
            except Exception:
                pass

    def _write_command_entry(self, rendered: str) -> None:
        try:
            self.query_one("#command-log", RichLog).write(rendered)
        except NoMatches:
            pass

    def _log_activity(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._write_command_entry(f"[dim]{ts}[/dim] {message}")

    def _write_inspector(self, content: Any) -> None:
        try:
            inspector = self.query_one("#inspector-view", RichLog)
            inspector.clear()
            inspector.write(content)
        except NoMatches:
            pass

    def _update_counter(self, panel_id: str, index: int | None, total: int) -> None:
        try:
            panel = self.query_one(f"#{panel_id}", Vertical)
        except NoMatches:
            return
        if total <= 0:
            panel.border_subtitle = "0 of 0"
        else:
            pos = 1 if index is None or index < 0 else min(index + 1, total)
            panel.border_subtitle = f"{pos} of {total}"

    def _update_ci_flow_summary(
        self,
        branch_name: str,
        base_branch: str,
        pr_info: str = "Press 'p' to open PR or 'f' to fetch checks",
    ) -> None:
        if self._last_ci_report is not None:
            pillar_bits: list[str] = []
            for p in self._last_ci_report.pillars:
                short = p.name.split()[0]
                if p.status == CIPillarStatus.PASSED:
                    pillar_bits.append(f"[#00FF87]✔ {short}[/]")
                elif p.status == CIPillarStatus.FAILED:
                    pillar_bits.append(f"[#FF0055]✘ {short}[/]")
                else:
                    pillar_bits.append(f"[#FFD60A]○ {short}[/]")
            ci_line = "  ".join(pillar_bits)
        else:
            ci_line = "[dim]3-Pillar CI: not run yet (press 'k' to run local check)[/dim]"

        text = (
            f"[bold #00F5D4]Flow:[/] [#E040FB]{branch_name}[/] → [bold]{base_branch}[/]  |  "
            f"[dim]{pr_info}[/dim]\n"
            f"{ci_line}"
        )
        try:
            self.query_one("#ci-flow-summary", Static).update(text)
        except NoMatches:
            pass

    def _refresh_status_banner(self) -> None:
        status_widget = self.query_one("#status-summary", Static)
        gh_tag = (
            f"[#00FF87]@{self._github_status.username}[/]"
            if self._github_status.authenticated and self._github_status.username
            else "[#FFD60A]@offline[/]"
        )
        if not find_repo_root(self.repo_path):
            status_widget.update(
                f"[#FF0055]✘ {self.repo_path.name}[/] → [dim]not a git repo[/]  {gh_tag}"
            )
            return

        try:
            st = self.driver.get_status()
            icon = "[#00FF87]✔[/]" if st.is_clean else "[#FFD60A]●[/]"
            ab = f" [dim]+{st.ahead_count}/-{st.behind_count}[/dim]" if st.upstream else ""
            status_widget.update(
                f"{icon} [bold #00F5D4]{self.repo_path.name}[/] → "
                f"[bold #E040FB]{st.branch_name}[/]{ab}  {gh_tag}"
            )
        except Exception as exc:
            status_widget.update(f"[#FF0055]✘ Error: {exc}[/]")

    def _switch_repo_context(self, new_path: Path) -> None:
        resolved = Path(new_path).resolve()
        self.repo_path = find_repo_root(resolved) or resolved
        self.driver = GitDriver(self.repo_path)
        self.safety = SafetyNet(self.driver)
        self.flow = GitHubFlowEngine(self.driver)
        self._last_ci_report = None
        self.refresh_workspace()

    # ------------------------------------------------------------------------
    # Workspace & GitHub State Refreshers
    # ------------------------------------------------------------------------

    def refresh_workspace(self) -> None:
        """Reload all 5 left Lazygit panels and the CI/Flow inspector."""
        files_list = self.query_one("#files-list", OptionList)
        branches_list = self.query_one("#branches-list", OptionList)
        commits_list = self.query_one("#commits-list", OptionList)
        safety_list = self.query_one("#safety-list", OptionList)

        files_list.clear_options()
        branches_list.clear_options()
        commits_list.clear_options()
        safety_list.clear_options()

        self._file_entries = []
        self._branch_entries = []
        self._commit_entries = []
        self._safety_entries = []

        self._refresh_status_banner()

        if not find_repo_root(self.repo_path):
            self._update_counter("panel-files", None, 0)
            self._update_counter("panel-branches", None, 0)
            self._update_counter("panel-commits", None, 0)
            self._update_counter("panel-safety", None, 0)
            self._update_ci_flow_summary("none", "main", "Not inside a Git repository")
            self._write_inspector(
                f"[#FFD60A]Directory '{self.repo_path}' is not a Git repository.[/]\n"
                "Select a repository in [6]-GitHub Account & Connected Repositories or initialize Git."
            )
            return

        # 1 & 2. Files & Flow summary
        try:
            status = self.driver.get_status()
            base_branch = self.flow.resolve_default_base_branch()
            self._update_ci_flow_summary(status.branch_name, base_branch)

            merged_files: dict[str, FileStatus] = {}
            for f in status.staged_files + status.unstaged_files + status.untracked_files:
                if f.path in merged_files:
                    prev = merged_files[f.path]
                    merged_files[f.path] = FileStatus(
                        path=f.path,
                        staged_status=prev.staged_status or f.staged_status,
                        unstaged_status=prev.unstaged_status or f.unstaged_status,
                        is_untracked=prev.is_untracked or f.is_untracked,
                    )
                else:
                    merged_files[f.path] = f

            self._file_entries = list(merged_files.values())
            for idx, f in enumerate(self._file_entries):
                if f.is_untracked:
                    prefix = "[#FF0055]??[/]"
                elif f.staged_status and f.unstaged_status:
                    prefix = f"[#00FF87]{f.staged_status}[/][#FFD60A]{f.unstaged_status}[/]"
                elif f.staged_status:
                    prefix = f"[#00FF87]{f.staged_status} [/]"
                else:
                    prefix = f" [#FFD60A]{f.unstaged_status or 'M'}[/]"
                files_list.add_option(Option(f"{prefix} {f.path}", id=f"file-{idx}"))

            if not self._file_entries:
                files_list.add_option(Option("[#00FF87](working tree clean)[/]", disabled=True))
                self._update_counter("panel-files", None, 0)
                self._write_inspector(
                    "[#00FF87]Working tree clean.[/]\n"
                    "Press [bold]k[/] for 3-pillar CI check, [bold]n[/] for new branch, or [bold]g[/] for GitHub."
                )
            else:
                files_list.highlighted = 0
                self._update_counter("panel-files", 0, len(self._file_entries))
                self._show_file_diff(self._file_entries[0])
        except Exception as exc:
            self._log_activity(f"[#FF0055]Status refresh error: {exc}[/]")

        # 3. Branches
        try:
            bm = BranchManager(self.driver, self.safety)
            branches = bm.list_branches()
            local_branches = [b for b in branches if not b.get("is_remote")]
            current_idx = 0
            for idx, b in enumerate(local_branches):
                bname = str(b["name"])
                self._branch_entries.append(bname)
                is_cur = bool(b.get("is_current"))
                if is_cur:
                    current_idx = idx
                marker = "[bold #00FF87]*[/bold #00FF87]" if is_cur else " "
                check_mark = " [#00FF87]✔[/]" if is_cur else ""
                style = "[bold #00F5D4]" if is_cur else "[#E0AAFF]"
                end_style = "[/bold #00F5D4]" if is_cur else "[/#E0AAFF]"
                branches_list.add_option(
                    Option(f"{marker} {style}{bname}{end_style}{check_mark}", id=f"branch-{idx}")
                )
            if self._branch_entries:
                branches_list.highlighted = current_idx
                self._update_counter("panel-branches", current_idx, len(self._branch_entries))
            else:
                self._update_counter("panel-branches", None, 0)
        except Exception as exc:
            branches_list.add_option(Option(f"[#FF0055]Error: {exc}[/]", disabled=True))
            self._update_counter("panel-branches", None, 0)

        # 4. Commits
        try:
            commits = self.driver.get_log(max_count=15)
            self._commit_entries = commits
            for idx, c in enumerate(commits):
                sha = c.get("short_hash") or str(c.get("hash", ""))[:7]
                initials = _author_initials(str(c.get("author_name", "")))
                subj = str(c.get("subject", ""))
                commits_list.add_option(
                    Option(
                        f"[#00FF87]{sha}[/] [#E040FB]{initials}[/] [dim]○[/dim] {subj}",
                        id=f"commit-{idx}",
                    )
                )
            if self._commit_entries:
                commits_list.highlighted = 0
                self._update_counter("panel-commits", 0, len(self._commit_entries))
            else:
                commits_list.add_option(Option("[dim](no commits yet)[/dim]", disabled=True))
                self._update_counter("panel-commits", None, 0)
        except Exception:
            commits_list.add_option(Option("[dim](no commits yet)[/dim]", disabled=True))
            self._update_counter("panel-commits", None, 0)

        # 5. Stash & Safety Bookmarks
        try:
            stashes = self.driver.stash_list()
            for idx, st in enumerate(stashes):
                self._safety_entries.append(
                    {"kind": "stash", "ref": f"stash@{{{idx}}}", "text": st}
                )
                safety_list.add_option(Option(f"[#FFD60A]{st}[/]", id=f"safety-stash-{idx}"))
            bookmarks = self.safety.list_bookmarks()
            for idx, bm_item in enumerate(bookmarks[:8]):
                self._safety_entries.append(
                    {
                        "kind": "bookmark",
                        "ref": bm_item.tag_or_ref,
                        "sha": bm_item.commit_sha,
                        "label": bm_item.label,
                    }
                )
                safety_list.add_option(
                    Option(
                        f"[#00F5D4]◆ {bm_item.label}[/] [dim]({bm_item.commit_sha[:7]})[/dim]",
                        id=f"safety-bm-{idx}",
                    )
                )
            if not self._safety_entries:
                safety_list.add_option(
                    Option("[dim](no stashes or bookmarks)[/dim]", disabled=True)
                )
                self._update_counter("panel-safety", None, 0)
            else:
                safety_list.highlighted = 0
                self._update_counter("panel-safety", 0, len(self._safety_entries))
        except Exception:
            self._update_counter("panel-safety", None, 0)

    def refresh_github_state(self) -> None:
        """Refresh connected GitHub account info and repositories in panel [6]."""
        account_bar = self.query_one("#github-account-bar", Static)
        repos_list = self.query_one("#github-repos-list", OptionList)
        repos_list.clear_options()
        self._github_repos = []

        try:
            self._github_status = self.github_auth.get_status()
        except Exception:
            self._github_status = GitHubAccountStatus(authenticated=False)

        self._refresh_status_banner()

        if not self._github_status.authenticated:
            account_bar.update(
                "[#FFD60A]⚠ Not signed into GitHub[/] — press [bold #00F5D4]g[/] to sign in "
                "or [bold #00F5D4]R[/] to refresh"
            )
            repos_list.add_option(
                Option(
                    "[dim]Connect your GitHub account ('g') to view & switch repositories.[/dim]",
                    disabled=True,
                )
            )
            self._update_counter("panel-github-repos", None, 0)
            return

        user = self._github_status.username or "GitHub"
        try:
            self._github_repos = self.github_auth.list_repos(
                workspace_path=self.workspace_path, limit=50
            )
            account_bar.update(
                f"[#00FF87]✔ Connected as @{user}[/] • "
                f"[#00F5D4]{len(self._github_repos)} repo(s)[/] "
                "[dim](Enter/Space: open or clone • g: auth/publish • R: refresh)[/dim]"
            )
            for idx, repo in enumerate(self._github_repos):
                vis = "[#FFD60A]private[/]" if repo.is_private else "[#00FF87]public [/]"
                loc = "[#00F5D4]✔ local[/]" if repo.local_path else "[dim]☁ remote[/dim]"
                repos_list.add_option(
                    Option(
                        f"{vis} [bold]{repo.full_name}[/] [dim]({repo.default_branch})[/dim] {loc}",
                        id=f"gh-repo-{idx}",
                    )
                )
            if self._github_repos:
                repos_list.highlighted = 0
                self._update_counter("panel-github-repos", 0, len(self._github_repos))
            else:
                repos_list.add_option(
                    Option("[dim](no repositories found on GitHub account)[/dim]", disabled=True)
                )
                self._update_counter("panel-github-repos", None, 0)
        except Exception as exc:
            account_bar.update(f"[#00FF87]✔ @{user}[/] • [#FF0055]Repo fetch error: {exc}[/]")
            repos_list.add_option(
                Option("[#FFD60A]Could not list GitHub repositories.[/]", disabled=True)
            )
            self._update_counter("panel-github-repos", None, 0)

    # ------------------------------------------------------------------------
    # Selection & Diff Helpers
    # ------------------------------------------------------------------------

    def _get_selected_file(self) -> Optional[FileStatus]:
        files_list = self.query_one("#files-list", OptionList)
        idx = files_list.highlighted
        if idx is not None and 0 <= idx < len(self._file_entries):
            return self._file_entries[idx]
        if len(self._file_entries) == 1:
            return self._file_entries[0]
        return None

    def _get_selected_branch(self) -> Optional[str]:
        branches_list = self.query_one("#branches-list", OptionList)
        idx = branches_list.highlighted
        if idx is not None and 0 <= idx < len(self._branch_entries):
            return self._branch_entries[idx]
        return None

    def _get_selected_github_repo(self) -> Optional[GitHubRepoItem]:
        repos_list = self.query_one("#github-repos-list", OptionList)
        idx = repos_list.highlighted
        if idx is not None and 0 <= idx < len(self._github_repos):
            return self._github_repos[idx]
        return None

    def _show_file_diff(self, file_entry: FileStatus) -> None:
        if file_entry.is_untracked:
            fpath = self.repo_path / file_entry.path
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")[:4000]
                self._write_inspector(Syntax(content, "text", theme="monokai", line_numbers=True))
            except OSError as exc:
                self._write_inspector(f"[#FF0055]Could not preview '{file_entry.path}': {exc}[/]")
            return

        parts: list[str] = []
        staged_res = self.driver.run(["diff", "--cached", "--", file_entry.path], check=False)
        if staged_res.stdout.strip():
            parts.append("=== STAGED CHANGES ===\n" + staged_res.stdout.strip())
        unstaged_res = self.driver.run(["diff", "--", file_entry.path], check=False)
        if unstaged_res.stdout.strip():
            parts.append("=== UNSTAGED CHANGES ===\n" + unstaged_res.stdout.strip())
        diff_text = "\n\n".join(parts) or f"(No textual diff for {file_entry.path})"
        self._write_inspector(Syntax(diff_text[:8000], "diff", theme="monokai"))

    # ------------------------------------------------------------------------
    # OptionList Highlight / Selection Handlers
    # ------------------------------------------------------------------------

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        list_id = event.option_list.id
        idx = event.option_index
        if list_id == "files-list" and 0 <= idx < len(self._file_entries):
            self._update_counter("panel-files", idx, len(self._file_entries))
            self._show_file_diff(self._file_entries[idx])
        elif list_id == "branches-list" and 0 <= idx < len(self._branch_entries):
            self._update_counter("panel-branches", idx, len(self._branch_entries))
        elif list_id == "commits-list" and 0 <= idx < len(self._commit_entries):
            self._update_counter("panel-commits", idx, len(self._commit_entries))
            sha = str(self._commit_entries[idx].get("hash", ""))
            if sha:
                res = self.driver.run(["show", "--stat", "-p", sha], check=False)
                self._write_inspector(
                    Syntax((res.stdout or res.stderr)[:8000], "diff", theme="monokai")
                )
        elif list_id == "safety-list" and 0 <= idx < len(self._safety_entries):
            self._update_counter("panel-safety", idx, len(self._safety_entries))
        elif list_id == "github-repos-list" and 0 <= idx < len(self._github_repos):
            self._update_counter("panel-github-repos", idx, len(self._github_repos))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        list_id = event.option_list.id
        idx = event.option_index
        if list_id == "files-list" and 0 <= idx < len(self._file_entries):
            self._toggle_file_stage(self._file_entries[idx])
        elif list_id == "branches-list" and 0 <= idx < len(self._branch_entries):
            self._switch_to_branch(self._branch_entries[idx])
        elif list_id == "github-repos-list" and 0 <= idx < len(self._github_repos):
            self._open_or_clone_github_repo(self._github_repos[idx])

    # ------------------------------------------------------------------------
    # Panel Navigation & Actions
    # ------------------------------------------------------------------------

    def action_focus_panel(self, target: str) -> None:
        widget_map = {
            "status": "#panel-status",
            "files": "#files-list",
            "branches": "#branches-list",
            "commits": "#commits-list",
            "safety": "#safety-list",
            "github": "#github-repos-list",
            "ci": "#inspector-view",
        }
        selector = widget_map.get(target)
        if selector:
            if target == "status":
                self.query_one("#files-list", OptionList).focus()
                return
            self.query_one(selector).focus()

    def action_toggle_command_log(self) -> None:
        panel = self.query_one("#panel-command-log", Vertical)
        cmd_log = self.query_one("#command-log", RichLog)
        if not panel.display:
            panel.display = True
            cmd_log.focus()
        elif self.focused is cmd_log:
            panel.display = False
            self.query_one("#files-list", OptionList).focus()
        else:
            cmd_log.focus()

    def action_primary_space_action(self) -> None:
        focused = self.focused
        if focused is not None and focused.id == "branches-list":
            branch = self._get_selected_branch()
            if branch:
                self._switch_to_branch(branch)
            return
        if focused is not None and focused.id == "github-repos-list":
            repo = self._get_selected_github_repo()
            if repo:
                self._open_or_clone_github_repo(repo)
            return
        self.action_toggle_stage_selected()

    def action_refresh_all(self) -> None:
        self.refresh_workspace()
        self._log_activity("[#00F5D4]Workspace refreshed.[/]")

    def action_refresh_github_and_workspace(self) -> None:
        self.refresh_workspace()
        self.refresh_github_state()
        self._log_activity("[#00F5D4]Refreshed workspace and GitHub repositories.[/]")

    # ------------------------------------------------------------------------
    # Core Workspace Operations
    # ------------------------------------------------------------------------

    def _toggle_file_stage(self, file_entry: FileStatus) -> None:
        try:
            if (
                file_entry.is_staged
                and not file_entry.unstaged_status
                and not file_entry.is_untracked
            ):
                self.driver.unstage([file_entry.path])
                self._log_activity(f"[#FFD60A]Unstaged[/] {file_entry.path}")
            else:
                self.driver.stage([file_entry.path])
                self._log_activity(f"[#00FF87]Staged[/] {file_entry.path}")
            self.refresh_workspace()
        except GitCommandError as exc:
            self._log_activity(f"[#FF0055]Stage toggle failed: {exc.stderr or exc}[/]")

    def action_toggle_stage_selected(self) -> None:
        entry = self._get_selected_file()
        if not entry:
            self._log_activity("[#FFD60A]No modified or untracked file selected.[/]")
            return
        self._toggle_file_stage(entry)

    def action_stage_all(self) -> None:
        try:
            self.driver.stage(None)
            self._log_activity("[#00FF87]Staged all modified and untracked files.[/]")
            self.refresh_workspace()
        except GitCommandError as exc:
            self._log_activity(f"[#FF0055]Stage all failed: {exc.stderr or exc}[/]")

    def action_discard_selected_file(self) -> None:
        entry = self._get_selected_file()
        if not entry:
            self._log_activity("[#FFD60A]Select a file first to discard changes.[/]")
            return
        try:
            if entry.is_untracked:
                target = self.repo_path / entry.path
                if target.is_file():
                    target.unlink()
            else:
                if entry.is_staged:
                    self.driver.unstage([entry.path])
                self.driver.restore([entry.path], staged=False)
            self._log_activity(f"[#FF0055]Discarded changes in[/] {entry.path}")
            self.refresh_workspace()
        except Exception as exc:
            self._log_activity(f"[#FF0055]Discard failed: {exc}[/]")

    def _switch_to_branch(self, branch_name: str) -> None:
        try:
            bm = BranchManager(self.driver, self.safety)
            bm.switch(branch_name, auto_stash=True)
            self._log_activity(f"[#00F5D4]Switched to branch[/] [bold]{branch_name}[/bold]")
            self.refresh_workspace()
        except (ValueError, GitCommandError) as exc:
            self._log_activity(f"[#FF0055]Switch failed: {exc}[/]")

    def action_open_new_branch_modal(self) -> None:
        def _on_close(result: Optional[dict[str, Any]]) -> None:
            if not result:
                return
            try:
                self.flow.start_feature(
                    branch_name=result["branch_name"],
                    sync_base=result["sync_base"],
                    force=result["force"],
                )
                self._log_activity(
                    f"[#00FF87]Created & switched to[/] [bold]{result['branch_name']}[/bold]"
                )
                self.refresh_workspace()
            except (ValueError, GitCommandError) as exc:
                self._log_activity(f"[#FF0055]Branch creation failed: {exc}[/]")

        self.push_screen(NewBranchModal(), callback=_on_close)

    def action_open_commit_modal(self) -> None:
        def _on_close(result: Optional[dict[str, Any]]) -> None:
            if not result:
                return
            cur_branch = self.driver.get_current_branch()
            if result["strict_flow"] and cur_branch in PROTECTED_BRANCHES:
                self._log_activity(
                    f"[#FF0055]Strict flow blocked direct commit on '{cur_branch}'. Press 'n' first.[/]"
                )
                return
            try:
                commit_obj = ConventionalCommit(
                    type=result["type"],
                    scope=result["scope"],
                    is_breaking=result["is_breaking"],
                    subject=result["subject"],
                )
                msg = commit_obj.format_message()
                sha = self.driver.commit(msg)
                self._log_activity(
                    f"[#00FF87]Committed[/] [#E040FB]{sha[:7]}[/] {msg.splitlines()[0]}"
                )
                self.refresh_workspace()
            except GitCommandError as exc:
                self._log_activity(f"[#FF0055]Commit failed: {exc.stderr or exc}[/]")

        self.push_screen(CommitModal(self.driver), callback=_on_close)

    def action_ai_auto_commit(self) -> None:
        try:
            status = self.driver.get_status()
            if not status.staged_files and (status.unstaged_files or status.untracked_files):
                self.driver.stage(None)
            suggested = suggest_conventional_commit(self.driver)
            msg = suggested.format_message()
            sha = self.driver.commit(msg)
            self._log_activity(
                f"[#00FF87]AI Committed[/] [#E040FB]{sha[:7]}[/] {msg.splitlines()[0]}"
            )
            self.refresh_workspace()
        except (ValueError, GitCommandError) as exc:
            self._log_activity(f"[#FF0055]AI Auto-Commit failed: {exc}[/]")

    def action_open_snapshot_modal(self) -> None:
        def _on_close(label: Optional[str]) -> None:
            if not label:
                return
            try:
                bm = self.safety.create_bookmark(label, include_untracked=True)
                self._log_activity(f"[#00F5D4]Saved snapshot[/] '{bm.label}' ({bm.commit_sha[:7]})")
                self.refresh_workspace()
            except GitCommandError as exc:
                self._log_activity(f"[#FF0055]Snapshot failed: {exc}[/]")

        self.push_screen(SnapshotModal(), callback=_on_close)

    def action_undo_last(self) -> None:
        try:
            res = self.safety.undo(steps=1, force=True)
            self._log_activity(f"[#FFD60A]Undo complete:[/] {res.output or 'reverted 1 step'}")
            self.refresh_workspace()
        except (ValueError, GitCommandError) as exc:
            self._log_activity(f"[#FF0055]Undo failed: {exc}[/]")

    def action_stash_save(self) -> None:
        try:
            saved = self.driver.stash_save("phantom-git tui stash", include_untracked=True)
            if saved:
                self._log_activity("[#FFD60A]Saved uncommitted & untracked files to stash.[/]")
            else:
                self._log_activity("[dim]Working tree clean — nothing to stash.[/dim]")
            self.refresh_workspace()
        except GitCommandError as exc:
            self._log_activity(f"[#FF0055]Stash save failed: {exc}[/]")

    def action_stash_pop(self) -> None:
        try:
            popped = self.driver.stash_pop(0)
            if popped:
                self._log_activity("[#00FF87]Popped latest stash.[/]")
            else:
                self._log_activity("[dim]No stashes available to pop.[/dim]")
            self.refresh_workspace()
        except GitCommandError as exc:
            self._log_activity(f"[#FF0055]Stash pop failed: {exc}[/]")

    # ------------------------------------------------------------------------
    # GitHub Account & Repository Actions
    # ------------------------------------------------------------------------

    def _open_or_clone_github_repo(self, repo: GitHubRepoItem) -> None:
        if repo.local_path and Path(repo.local_path).exists():
            target = Path(repo.local_path)
            self._switch_repo_context(target)
            self._log_activity(f"[#00FF87]Switched active repository to[/] [bold]{target.name}[/]")
            return

        try:
            dest = self.github_auth.clone_repo(repo.full_name, self.workspace_path)
            self._log_activity(f"[#00FF87]Cloned {repo.full_name}[/] -> {dest}")
            self._switch_repo_context(dest)
            self.refresh_github_state()
        except Exception as exc:
            self._log_activity(f"[#FF0055]Clone failed for {repo.full_name}: {exc}[/]")

    def action_open_github_auth_modal(self) -> None:
        def _on_close(res: Optional[dict[str, Any]]) -> None:
            if not res:
                return
            action = res.get("action")
            if action == "token_login":
                try:
                    status = self.github_auth.login_with_token(res["token"])
                    self._github_status = status
                    self._log_activity(
                        f"[#00FF87]Signed into GitHub as @{status.username or 'user'}[/]"
                    )
                    self.refresh_github_state()
                except Exception as exc:
                    self._log_activity(f"[#FF0055]GitHub login failed: {exc}[/]")
            elif action == "web_login":
                try:
                    gh_bin = find_gh_binary()
                    with self.suspend():
                        subprocess.run(
                            [
                                gh_bin,
                                "auth",
                                "login",
                                "--hostname",
                                "github.com",
                                "--git-protocol",
                                "https",
                                "--web",
                                "-s",
                                "repo,workflow,read:org",
                            ],
                            check=False,
                        )
                    self.github_auth.run_gh(["auth", "setup-git", "--hostname", "github.com"])
                    self.refresh_github_state()
                    if self._github_status.authenticated:
                        self._log_activity(
                            f"[#00FF87]Signed into GitHub as @{self._github_status.username}[/]"
                        )
                except Exception as exc:
                    self._log_activity(f"[#FF0055]GitHub browser login failed: {exc}[/]")
            elif action == "logout":
                self.github_auth.logout()
                self._log_activity("[#FFD60A]Signed out of GitHub.[/]")
                self.refresh_github_state()
            elif action == "publish":
                try:
                    url = self.github_auth.publish_repo(
                        self.driver, private=bool(res.get("private", False))
                    )
                    self._log_activity(f"[#00FF87]Published repository to[/] {url}")
                    self.refresh_github_state()
                except Exception as exc:
                    self._log_activity(f"[#FF0055]Publish failed: {exc}[/]")

        self.push_screen(
            GitHubAuthModal(status=self._github_status, repo_name=self.repo_path.name),
            callback=_on_close,
        )

    # ------------------------------------------------------------------------
    # 3-Pillar CI Pre-Flight & GitHub Flow Actions
    # ------------------------------------------------------------------------

    def action_run_ci_checks(self) -> None:
        report = run_ci_preflight(self.repo_path, tier=TestingTier.PRODUCTION)
        self._last_ci_report = report

        branch = self.driver.get_current_branch() if find_repo_root(self.repo_path) else "none"
        base = self.flow.resolve_default_base_branch() if find_repo_root(self.repo_path) else "main"
        self._update_ci_flow_summary(
            branch,
            base,
            pr_info="3-Pillar CI PASSED" if report.passed else "3-Pillar CI FAILED",
        )

        table = Table(title="3-Pillar Local CI Pre-Flight", expand=True)
        table.add_column("Pillar", style="bold cyan")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Command")

        inspector = self.query_one("#inspector-view", RichLog)
        inspector.clear()
        for p in report.pillars:
            if p.status == CIPillarStatus.PASSED:
                st = "[bold #00FF87]PASSED[/]"
            elif p.status == CIPillarStatus.FAILED:
                st = "[bold #FF0055]FAILED[/]"
            else:
                st = "[#FFD60A]SKIPPED[/]"
            table.add_row(p.name, st, f"{p.duration_seconds:.2f}s", p.command or "-")

        inspector.write(table)
        for p in report.pillars:
            if p.status == CIPillarStatus.FAILED and p.output:
                inspector.write(f"[bold #FF0055]=== {p.name} ===[/]\n{p.output}")

        if report.passed:
            self._log_activity("[#00FF87]3-Pillar CI Check (production) PASSED.[/]")
        else:
            self._log_activity("[#FF0055]3-Pillar CI Check (production) FAILED.[/]")

    def action_flow_open_pr(self) -> None:
        try:
            res = self.flow.open_pull_request(run_checks=True)
            msg = res.stdout.strip() or "Pull Request created."
            self._write_inspector(f"[bold #00FF87]PR Created:[/] {msg}")
            self._log_activity(f"[#00FF87]Opened PR: {msg}[/]")
        except Exception as exc:
            self._write_inspector(f"[bold #FF0055]Open PR blocked/failed:[/] {exc}")
            self._log_activity(f"[#FF0055]Open PR failed: {exc}[/]")

    def action_flow_refresh_pr_checks(self) -> None:
        try:
            checks = self.flow.get_pr_checks()
            branch = self.driver.get_current_branch()
            base = self.flow.resolve_default_base_branch()
            self._update_ci_flow_summary(branch, base, pr_info=f"{len(checks)} remote PR check(s)")
            table = Table(title=f"GitHub Actions PR Checks ({branch})", expand=True)
            table.add_column("Check", style="bold cyan")
            table.add_column("State", justify="center")
            table.add_column("Link", style="dim")
            for c in checks:
                table.add_row(c.name, c.state, c.link or "-")
            self._write_inspector(table)
            self._log_activity(f"[#00F5D4]Loaded {len(checks)} PR check(s).[/]")
        except Exception as exc:
            self._write_inspector(f"[#FF0055]Failed to fetch PR checks: {exc}[/]")
            self._log_activity(f"[#FF0055]PR checks error: {exc}[/]")

    def action_flow_diagnose_logs(self) -> None:
        try:
            report_md = self.flow.fetch_ci_failure_logs()
            self._write_inspector(report_md)
            self._log_activity(
                "[#FFD60A]Saved AI CI diagnostic report to .phantom-git/last-ci-failure.md[/]"
            )
        except Exception as exc:
            self._write_inspector(f"[#FF0055]Could not retrieve CI logs: {exc}[/]")
            self._log_activity(f"[#FF0055]CI log fetch failed: {exc}[/]")

    def action_flow_merge_pr(self) -> None:
        try:
            self.flow.squash_and_merge()
            msg = "Squash-merged PR and returned cleanly to base branch."
            self._write_inspector(f"[bold #00FF87]{msg}[/]")
            self._log_activity(f"[#00FF87]{msg}[/]")
            self.refresh_workspace()
        except Exception as exc:
            self._write_inspector(f"[#FF0055]Squash & merge blocked: {exc}[/]")
            self._log_activity(f"[#FF0055]Merge failed: {exc}[/]")

    def action_flow_promote(self) -> None:
        try:
            out = self.flow.promote_staging_to_main()
            msg = f"Promoted staging -> main via --merge ({out.get('pr_url') or 'merged'})."
            self._write_inspector(f"[bold #00FF87]{msg}[/]")
            self._log_activity(f"[#00FF87]{msg}[/]")
            self.refresh_workspace()
        except Exception as exc:
            self._write_inspector(f"[#FF0055]Promotion blocked: {exc}[/]")
            self._log_activity(f"[#FF0055]Promote failed: {exc}[/]")

    def action_scaffold_guardrails(self) -> None:
        try:
            ptype = detect_project_type(self.repo_path)
            engine = ScaffoldEngine(target_dir=self.repo_path, overwrite=False)
            engine.scaffold_all(
                project_name=self.repo_path.name,
                project_type=ptype,
                testing_tier="production",
            )
            created_count = len(engine.manifest.created)
            skipped_count = len(engine.manifest.skipped)
            self._write_inspector(
                f"[bold #00FF87]Scaffolded 3-layer guardrails ({ptype}):[/] "
                f"{created_count} created, {skipped_count} skipped."
            )
            self._log_activity(
                f"[#00FF87]Scaffolded {created_count} guardrail file(s) ({ptype}).[/]"
            )
            self.refresh_workspace()
        except Exception as exc:
            self._log_activity(f"[#FF0055]Scaffold failed: {exc}[/]")

    def action_open_secret_modal(self) -> None:
        def _on_close(res: Optional[dict[str, Any]]) -> None:
            if not res:
                return
            try:
                set_github_env_secret(
                    self.driver,
                    key=res["key"],
                    value=res["value"],
                    environment=res["environment"],
                    is_variable=res["is_variable"],
                )
                kind = "variable" if res["is_variable"] else "secret"
                self._log_activity(
                    f"[#00FF87]Set GitHub {kind} '{res['key']}' in '{res['environment']}'.[/]"
                )
            except (ValueError, GitCommandError) as exc:
                self._log_activity(f"[#FF0055]Secret update failed: {exc}[/]")

        self.push_screen(SecretModal(), callback=_on_close)

    def action_open_keybindings_modal(self) -> None:
        self.push_screen(KeybindingsModal())


def run_tui(
    repo_path: Path | str | None = None,
    workspace_path: Path | str | None = None,
) -> None:
    """Launch the Phantom Git mouse-enabled Textual TUI in the alternate screen buffer."""
    app = PhantomGitApp(repo_path=repo_path, workspace_path=workspace_path)
    try:
        app.run(inline=False)
    except KeyboardInterrupt:
        pass
