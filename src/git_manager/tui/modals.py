"""
Interactive mouse- and keyboard-accessible modal dialogs for Phantom Git TUI.
All modals support Ctrl+C immediate exit and Escape cancellation.
"""

from __future__ import annotations

from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from git_manager.core.branch_hygiene import ALLOWED_BRANCH_PREFIXES, format_branch_name
from git_manager.core.commit_parser import suggest_conventional_commit
from git_manager.core.git_driver import GitDriver
from git_manager.core.models import GitHubAccountStatus

_COMMIT_TYPES = [
    ("feat (New Feature)", "feat"),
    ("fix (Bug Fix)", "fix"),
    ("chore (Maintenance)", "chore"),
    ("docs (Documentation)", "docs"),
    ("refactor (Refactor)", "refactor"),
    ("ci (CI/CD Pipeline)", "ci"),
    ("test (Tests)", "test"),
    ("perf (Performance)", "perf"),
    ("build (Build System)", "build"),
    ("style (Formatting)", "style"),
]

_BRANCH_PREFIXES = [(p, p) for p in ALLOWED_BRANCH_PREFIXES]


class CommitModal(ModalScreen[Optional[dict[str, Any]]]):
    """Modal dialog to compose or AI-suggest a Conventional Commit."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "app.quit", "Quit", show=False, priority=True),
    ]

    def __init__(self, driver: GitDriver) -> None:
        super().__init__()
        self.driver = driver

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Conventional Commit Builder", classes="modal-title")
            yield Label("Type:", classes="field-label")
            yield Select(_COMMIT_TYPES, value="feat", allow_blank=False, id="commit-type-select")
            yield Label("Scope (optional):", classes="field-label")
            yield Input(placeholder="e.g. auth, api, ui", id="commit-scope-input")
            yield Label("Subject (imperative lowercase):", classes="field-label")
            yield Input(placeholder="e.g. add neon login header", id="commit-subject-input")
            yield Checkbox("Breaking change (!)", value=False, id="commit-breaking-check")
            yield Checkbox(
                "Strict GitHub Flow (block direct commits on main/staging)",
                value=True,
                id="commit-strict-check",
            )
            yield Static("", id="commit-modal-status")
            with Horizontal(classes="modal-buttons"):
                yield Button(
                    "Auto-Suggest from Staged Diff",
                    id="btn-auto-suggest",
                    variant="primary",
                )
                yield Button("Commit", id="btn-submit-commit", variant="success")
                yield Button("Cancel", id="btn-cancel-commit")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        status_lbl = self.query_one("#commit-modal-status", Static)

        if btn_id == "btn-cancel-commit":
            self.dismiss(None)
            return

        if btn_id == "btn-auto-suggest":
            try:
                suggested = suggest_conventional_commit(self.driver)
            except ValueError as exc:
                status_lbl.update(f"[#FF0055]{exc}[/#FF0055]")
                return

            self.query_one("#commit-type-select", Select).value = suggested.type
            self.query_one("#commit-scope-input", Input).value = suggested.scope or ""
            self.query_one("#commit-subject-input", Input).value = suggested.subject
            self.query_one("#commit-breaking-check", Checkbox).value = suggested.is_breaking
            status_lbl.update("[#00FF87]Populated suggestion from staged diff.[/#00FF87]")
            return

        if btn_id == "btn-submit-commit":
            subject = self.query_one("#commit-subject-input", Input).value.strip()
            if not subject:
                status_lbl.update("[#FF0055]Commit subject is required.[/#FF0055]")
                return
            ctype = str(self.query_one("#commit-type-select", Select).value)
            scope = self.query_one("#commit-scope-input", Input).value.strip() or None
            is_breaking = self.query_one("#commit-breaking-check", Checkbox).value
            strict_flow = self.query_one("#commit-strict-check", Checkbox).value
            self.dismiss(
                {
                    "type": ctype,
                    "scope": scope,
                    "subject": subject,
                    "is_breaking": is_breaking,
                    "strict_flow": strict_flow,
                }
            )


class NewBranchModal(ModalScreen[Optional[dict[str, Any]]]):
    """Modal dialog to create and switch to a prefixed GitHub Flow branch."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "app.quit", "Quit", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Start Feature / Fix Branch", classes="modal-title")
            yield Label("Prefix:", classes="field-label")
            yield Select(
                _BRANCH_PREFIXES, value="feat/", allow_blank=False, id="branch-prefix-select"
            )
            yield Label("Branch Slug:", classes="field-label")
            yield Input(placeholder="e.g. user-auth or navbar-fix", id="branch-slug-input")
            yield Checkbox(
                "Sync base branch (staging/main) before branching",
                value=True,
                id="branch-sync-base",
            )
            yield Checkbox("Force (bypass prefix validation)", value=False, id="branch-force")
            yield Static("", id="branch-modal-status")
            with Horizontal(classes="modal-buttons"):
                yield Button("Create & Switch", id="btn-create-branch", variant="success")
                yield Button("Cancel", id="btn-cancel-branch")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-cancel-branch":
            self.dismiss(None)
            return

        if btn_id == "btn-create-branch":
            slug = self.query_one("#branch-slug-input", Input).value.strip()
            status_lbl = self.query_one("#branch-modal-status", Static)
            if not slug:
                status_lbl.update("[#FF0055]Branch slug cannot be empty.[/#FF0055]")
                return

            prefix = str(self.query_one("#branch-prefix-select", Select).value).rstrip("/")
            force = self.query_one("#branch-force", Checkbox).value
            if force and "/" in slug:
                branch_name = slug
            else:
                clean_slug = slug
                for allowed in ALLOWED_BRANCH_PREFIXES:
                    if clean_slug.startswith(allowed):
                        clean_slug = clean_slug[len(allowed) :]
                        break
                branch_name = format_branch_name(prefix, clean_slug)

            sync_base = self.query_one("#branch-sync-base", Checkbox).value
            self.dismiss(
                {
                    "branch_name": branch_name,
                    "sync_base": sync_base,
                    "force": force,
                }
            )


class SnapshotModal(ModalScreen[Optional[str]]):
    """Modal dialog to create a named safety bookmark."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "app.quit", "Quit", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Create Safety Snapshot Bookmark", classes="modal-title")
            yield Label("Snapshot Label:", classes="field-label")
            yield Input(placeholder="e.g. before-ai-refactor", id="snapshot-label-input")
            with Horizontal(classes="modal-buttons"):
                yield Button("Save Snapshot", id="btn-save-snapshot", variant="primary")
                yield Button("Cancel", id="btn-cancel-snapshot")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-snapshot":
            self.dismiss(None)
            return
        if event.button.id == "btn-save-snapshot":
            label = self.query_one("#snapshot-label-input", Input).value.strip()
            self.dismiss(label or "manual-snapshot")


class SecretModal(ModalScreen[Optional[dict[str, Any]]]):
    """Modal dialog to set a GitHub Environment secret or variable via gh CLI."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "app.quit", "Quit", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Label("Provision GitHub Environment Secret / Variable", classes="modal-title")
            yield Label("Key Name:", classes="field-label")
            yield Input(placeholder="e.g. OPENAI_API_KEY", id="secret-key-input")
            yield Label("Value:", classes="field-label")
            yield Input(placeholder="Enter value...", password=True, id="secret-value-input")
            yield Label("Target Environment:", classes="field-label")
            yield Select(
                [
                    ("staging", "staging"),
                    ("production", "production"),
                    ("repo (Repository-wide)", "repo"),
                ],
                value="staging",
                allow_blank=False,
                id="secret-env-select",
            )
            yield Checkbox(
                "Store as non-sensitive Variable (instead of encrypted Secret)",
                value=False,
                id="secret-is-var",
            )
            yield Static("", id="secret-modal-status")
            with Horizontal(classes="modal-buttons"):
                yield Button("Set Secret", id="btn-save-secret", variant="success")
                yield Button("Cancel", id="btn-cancel-secret")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-secret":
            self.dismiss(None)
            return
        if event.button.id == "btn-save-secret":
            key = self.query_one("#secret-key-input", Input).value.strip()
            value = self.query_one("#secret-value-input", Input).value
            status_lbl = self.query_one("#secret-modal-status", Static)
            if not key:
                status_lbl.update("[#FF0055]Key name is required.[/#FF0055]")
                return
            env_name = str(self.query_one("#secret-env-select", Select).value)
            is_var = self.query_one("#secret-is-var", Checkbox).value
            self.dismiss(
                {
                    "key": key,
                    "value": value,
                    "environment": env_name,
                    "is_variable": is_var,
                }
            )


class GitHubAuthModal(ModalScreen[Optional[dict[str, Any]]]):
    """Modal dialog to sign into GitHub or publish the active repository."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "app.quit", "Quit", show=False, priority=True),
    ]

    def __init__(
        self,
        status: GitHubAccountStatus | None = None,
        repo_name: str = "",
    ) -> None:
        super().__init__()
        self.status = status or GitHubAccountStatus()
        self.repo_name = repo_name

    def compose(self) -> ComposeResult:
        if self.status.authenticated:
            scopes = ", ".join(self.status.scopes) if self.status.scopes else "default"
            banner = (
                f"[#00FF87]✔ Connected as @{self.status.username or 'GitHub user'}[/] "
                f"[dim]({self.status.host} • scopes: {scopes})[/dim]"
            )
        else:
            banner = "[#FFD60A]⚠ Not signed into GitHub. Sign in via PAT or Browser OAuth.[/]"

        with Vertical(classes="modal-container"):
            yield Label("GitHub Account & Repository Connection", classes="modal-title")
            yield Static(banner, id="github-auth-banner")
            yield Label("Personal Access Token (classic/fine-grained):", classes="field-label")
            yield Input(
                placeholder="ghp_... or github_pat_...",
                password=True,
                id="github-token-input",
            )
            yield Checkbox(
                f"Private repository when publishing '{self.repo_name or 'current repo'}'",
                value=False,
                id="github-private-check",
            )
            yield Static("", id="github-modal-status")
            with Horizontal(classes="modal-buttons"):
                yield Button("Sign In with Token", id="btn-github-token-login", variant="success")
                yield Button("Sign In via Browser", id="btn-github-web-login", variant="primary")
                yield Button("Publish / Push Repo", id="btn-github-publish", variant="primary")
                yield Button("Disconnect", id="btn-github-logout", variant="error")
                yield Button("Cancel", id="btn-github-cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        status_lbl = self.query_one("#github-modal-status", Static)

        if btn_id == "btn-github-cancel":
            self.dismiss(None)
            return
        if btn_id == "btn-github-web-login":
            self.dismiss({"action": "web_login"})
            return
        if btn_id == "btn-github-logout":
            self.dismiss({"action": "logout"})
            return
        if btn_id == "btn-github-publish":
            is_private = self.query_one("#github-private-check", Checkbox).value
            self.dismiss({"action": "publish", "private": is_private})
            return
        if btn_id == "btn-github-token-login":
            token = self.query_one("#github-token-input", Input).value.strip()
            if not token:
                status_lbl.update(
                    "[#FF0055]Enter a GitHub token or click 'Sign In via Browser'.[/#FF0055]"
                )
                return
            self.dismiss({"action": "token_login", "token": token})


class KeybindingsModal(ModalScreen[None]):
    """Lazygit-style interactive keybindings reference modal."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("?", "close", "Close"),
        ("q", "close", "Close"),
        Binding("ctrl+c", "app.quit", "Quit", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        help_text = (
            "[bold #00F5D4]Navigation & Panels[/]\n"
            "  [bold #00FF87]1..5[/]         Focus Left Panels (Status, Files, Branches, Commits, Stash)\n"
            "  [bold #00FF87]6 / 0 / @[/]    Focus Right Panels (GitHub Repos / CI & Flow / Command Log)\n"
            "  [bold #00FF87]Tab / ↑↓[/]     Cycle panels or move selection cursor\n"
            "\n"
            "[bold #00F5D4]Files, Branches & Commits[/]\n"
            "  [bold #00FF87]Space / Enter[/] Stage/Unstage file, Switch branch, or Open/Clone GitHub repo\n"
            "  [bold #00FF87]a / d[/]        Stage all files / Discard selected file changes\n"
            "  [bold #00FF87]c / A[/]        Open Conventional Commit modal / 1-Click AI Auto-Commit\n"
            "  [bold #00FF87]n / s / Z[/]    Create new Flow branch / Stash -u / Pop latest stash\n"
            "  [bold #00FF87]B / u / D[/]    Create safety snapshot / Undo last reflog step\n"
            "\n"
            "[bold #00F5D4]GitHub Account, CI & Flow Pipelines[/]\n"
            "  [bold #00FF87]g / R / r[/]    GitHub Auth & Publish modal / Refresh Repos / Refresh Workspace\n"
            "  [bold #00FF87]k / p / f / l[/] 3-Pillar CI Check / Open PR / Fetch PR Checks / CI Failure Logs\n"
            "  [bold #00FF87]m / P / S / E[/] Squash & Merge PR / Promote staging->main / Scaffold / Set Secret\n"
            "  [bold #00FF87]? / q / Ctrl+C[/] Toggle Keybindings / Quit Phantom Git"
        )
        with Vertical(classes="modal-container"):
            yield Label("Phantom Git Keybindings (?)", classes="modal-title")
            yield Static(help_text, id="keybindings-text")
            with Horizontal(classes="modal-buttons"):
                yield Button("Close", id="btn-close-keybindings", variant="primary")

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-keybindings":
            self.dismiss(None)
