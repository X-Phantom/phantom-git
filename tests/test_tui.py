"""
Headless Textual Pilot & Component tests for Phantom Git's Lazygit-style Purple & Neon TUI.
Verifies alternate screen buffer launch, Ctrl+C termination, all 8 Lazygit containers
(5 left + 3 right), bottom keybindings bar, real-time command log, GitHub repo integration,
staging, AI commit, snapshots, undo, stash, modals, and 3-pillar CI runner.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import socket
import pytest
from textual.widgets import Input, OptionList, RichLog
from typer.testing import CliRunner

from git_manager.cli import app as cli_app
from git_manager.core.git_driver import GitDriver
from git_manager.core.github_auth import GitHubAuthManager
from git_manager.core.models import (
    CIPillarResult,
    CIPillarStatus,
    CIPreFlightReport,
    GitHubAccountStatus,
    GitHubRepoItem,
    GitResult,
    TestingTier,
)
from git_manager.tui import app as tui_module
from git_manager.tui.app import PhantomGitApp, run_tui
from git_manager.tui.modals import (
    CommitModal,
    GitHubAuthModal,
    KeybindingsModal,
    NewBranchModal,
    SecretModal,
    SnapshotModal,
)
from tests.conftest import run_git


def _is_loopback_available(timeout: float = 0.25) -> bool:
    """
    Check whether 127.0.0.1 TCP loopback works before calling asyncio.run() on Windows.
    Python's Windows ProactorEventLoop uses socket.socketpair() with an unbounded accept(),
    which deadlocks if the environment blocks loopback TCP sockets.
    """
    lsock: socket.socket | None = None
    csock: socket.socket | None = None
    accepted: socket.socket | None = None
    try:
        lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsock.settimeout(timeout)
        lsock.bind(("127.0.0.1", 0))
        lsock.listen(1)
        _, port = lsock.getsockname()

        csock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        csock.settimeout(timeout)
        csock.connect(("127.0.0.1", port))
        accepted, _ = lsock.accept()
        return True
    except OSError:
        return False
    finally:
        for sock in (accepted, csock, lsock):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


_SKIP_NO_LOOPBACK = pytest.mark.skipif(
    not _is_loopback_available(),
    reason="Windows sandbox blocks 127.0.0.1 TCP loopback required by asyncio socket.socketpair()",
)


def _make_fake_github_auth(repos: list[GitHubRepoItem] | None = None) -> GitHubAuthManager:
    """Build an offline GitHubAuthManager stub for deterministic TUI tests."""

    def _runner(args: list[str], cwd: Path, input_text: str | None, timeout: int) -> GitResult:
        return GitResult(stdout="", stderr="", exit_code=0, success=True, command=["gh", *args])

    mgr = GitHubAuthManager(gh_runner=_runner)
    mgr.get_status = lambda hostname="github.com": GitHubAccountStatus(  # type: ignore[method-assign]
        authenticated=True,
        username="X-Phantom",
        host=hostname,
        protocol="https",
        scopes=["repo", "workflow"],
    )
    mgr.list_repos = lambda workspace_path=None, limit=50: list(repos or [])  # type: ignore[method-assign]
    return mgr


class TestPhantomGitTUIComponents:
    """Fast socket-free unit tests for TUI theme, app initialization, hotkey guards, and modals."""

    def test_tui_theme_css_purple_and_neon_palette(self) -> None:
        css_path = Path(tui_module.__file__).parent / "theme.tcss"
        assert css_path.exists()
        css_text = css_path.read_text(encoding="utf-8")
        for color in ("#0B0716", "#7B2CBF", "#9D4EDD", "#E040FB", "#00F5D4", "#00FF87"):
            assert color in css_text

    def test_tui_app_init_and_hotkey_guards(self, temp_git_repo: Path, monkeypatch) -> None:
        app = PhantomGitApp(repo_path=temp_git_repo, github_auth=_make_fake_github_auth())
        assert app.repo_path == temp_git_repo.resolve()
        assert app.driver is not None
        assert app.safety is not None
        assert app.flow is not None

        binding_keys = {b.key for b in app.BINDINGS}
        for key in (
            "ctrl+c",
            "q",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "0",
            "@",
            "space",
            "a",
            "d",
            "c",
            "A",
            "n",
            "s",
            "Z",
            "u",
            "k",
            "p",
            "m",
            "P",
            "g",
            "R",
            "r",
            "?",
        ):
            assert key in binding_keys

        # Simulate Input focused: single-key actions blocked, quit (Ctrl+C / q) ALWAYS allowed
        monkeypatch.setattr(PhantomGitApp, "screen_stack", property(lambda self: [object()]))
        monkeypatch.setattr(PhantomGitApp, "focused", property(lambda self: Input()))
        assert app.check_action("toggle_stage_selected", ()) is False
        assert app.check_action("open_commit_modal", ()) is False
        assert app.check_action("quit", ()) is True

        # Simulate ModalScreen active (screen_stack > 1): workspace blocked, quit STILL allowed
        monkeypatch.setattr(
            PhantomGitApp, "screen_stack", property(lambda self: [object(), object()])
        )
        assert app.check_action("stage_all", ()) is False
        assert app.check_action("quit", ()) is True

    def test_run_tui_uses_alternate_screen_buffer(self, temp_git_repo: Path, monkeypatch) -> None:
        run_calls: list[dict[str, object]] = []

        def _fake_run(self, **kwargs):
            run_calls.append(kwargs)

        monkeypatch.setattr(PhantomGitApp, "run", _fake_run)
        run_tui(repo_path=temp_git_repo)
        assert len(run_calls) == 1
        assert run_calls[0].get("inline") is False

    def test_tui_modals_instantiation(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        cm = CommitModal(driver)
        assert cm.driver is driver
        assert any((b[0] if isinstance(b, tuple) else b.key) == "ctrl+c" for b in cm.BINDINGS)

        bm = NewBranchModal()
        assert any((b[0] if isinstance(b, tuple) else b.key) == "ctrl+c" for b in bm.BINDINGS)

        sm = SnapshotModal()
        assert ("escape", "cancel", "Cancel") in sm.BINDINGS

        sec = SecretModal()
        assert ("escape", "cancel", "Cancel") in sec.BINDINGS

        gh_modal = GitHubAuthModal(
            status=GitHubAccountStatus(authenticated=True, username="X-Phantom"),
            repo_name="phantom-git",
        )
        assert gh_modal.status.username == "X-Phantom"

        kb_modal = KeybindingsModal()
        assert any((b[0] if isinstance(b, tuple) else b.key) == "ctrl+c" for b in kb_modal.BINDINGS)

    def test_cli_tui_and_ui_help(self) -> None:
        runner = CliRunner()
        r1 = runner.invoke(cli_app, ["tui", "--help"])
        assert r1.exit_code == 0
        assert "Lazygit-style TUI" in r1.output

        r2 = runner.invoke(cli_app, ["ui", "--help"])
        assert r2.exit_code == 0
        assert "Purple & Neon TUI" in r2.output


@_SKIP_NO_LOOPBACK
class TestPhantomGitTUIPilot:
    """End-to-end Textual Pilot tests covering Lazygit layout, hotkeys, GitHub repos, and Ctrl+C."""

    def test_tui_lazygit_layout_and_staging_flow(self, dirty_git_repo: Path) -> None:
        repos = [
            GitHubRepoItem(
                name=dirty_git_repo.name,
                full_name=f"X-Phantom/{dirty_git_repo.name}",
                is_private=False,
                default_branch="main",
                url=f"https://github.com/X-Phantom/{dirty_git_repo.name}",
                local_path=str(dirty_git_repo),
            )
        ]

        async def _run() -> None:
            app = PhantomGitApp(
                repo_path=dirty_git_repo,
                github_auth=_make_fake_github_auth(repos),
            )
            async with app.run_test(size=(160, 50)) as pilot:
                await pilot.pause()

                # Verify all 5 left containers + 3 right containers + bottom keybindings footer
                assert app.query_one("#panel-status").border_title == "[1]-Status"
                assert (
                    app.query_one("#panel-files").border_title
                    == "[2]-Files - Worktrees - Submodules"
                )
                assert (
                    app.query_one("#panel-branches").border_title
                    == "[3]-Local branches - Remotes - Tags"
                )
                assert app.query_one("#panel-commits").border_title == "[4]-Commits - Reflog"
                assert app.query_one("#panel-safety").border_title == "[5]-Stash"
                assert (
                    app.query_one("#panel-github-repos").border_title
                    == "[6]-GitHub Account & Connected Repositories"
                )
                assert (
                    app.query_one("#panel-ci-flow").border_title
                    == "[0]-CI / GitHub Flow Status & Checks"
                )
                assert app.query_one("#panel-command-log").border_title == "Command log"
                assert app.query_one("#lazygit-footer") is not None

                # Verify counters & populated panels
                assert len(app._file_entries) >= 3
                assert "1 of " in str(app.query_one("#panel-files").border_subtitle)
                assert "main" in app._branch_entries
                assert len(app._commit_entries) >= 1
                assert len(app._github_repos) == 1
                assert app.query_one("#panel-github-repos").border_subtitle == "1 of 1"

                # Stage all via 'a' and verify
                await pilot.press("a")
                await pilot.pause()
                status_after_all = GitDriver(dirty_git_repo).get_status()
                assert not status_after_all.unstaged_files
                assert not status_after_all.untracked_files
                assert len(status_after_all.staged_files) >= 2

                # Verify real-time git command logging appeared in #command-log
                cmd_log = app.query_one("#command-log", RichLog)
                log_text = "\n".join(line.text for line in cmd_log.lines)
                assert "git add -A" in log_text

                # Press Space to unstage first staged file
                await pilot.press("space")
                await pilot.pause()
                status_after_toggle = GitDriver(dirty_git_repo).get_status()
                assert len(status_after_toggle.staged_files) < len(status_after_all.staged_files)

        asyncio.run(_run())

    def test_tui_ai_commit_snapshot_undo_stash_and_ctrl_c(self, dirty_git_repo: Path) -> None:
        async def _run() -> None:
            app = PhantomGitApp(
                repo_path=dirty_git_repo,
                github_auth=_make_fake_github_auth(),
            )
            async with app.run_test(size=(160, 50)) as pilot:
                await pilot.pause()
                driver = GitDriver(dirty_git_repo)
                initial_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()

                # 1. Stash -u ('s') and Pop ('Z')
                await pilot.press("s")
                await pilot.pause()
                assert driver.get_status().is_clean is True

                await pilot.press("Z")
                await pilot.pause()
                assert driver.get_status().is_clean is False

                # 2. Snapshot via 'B' modal
                await pilot.press("B")
                await pilot.pause()
                await pilot.click("#snapshot-label-input")
                for ch in "pre-tui":
                    await pilot.press(ch)
                await pilot.click("#btn-save-snapshot")
                await pilot.pause()
                assert any("pre-tui" in b.label for b in app.safety.list_bookmarks())

                # 3. 1-Click AI Auto-Commit ('A')
                await pilot.press("A")
                await pilot.pause()
                new_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()
                assert new_sha != initial_sha

                # 4. Undo commit via 'u'
                await pilot.press("u")
                await pilot.pause()
                reverted_sha = driver.run(["rev-parse", "HEAD"]).stdout.strip()
                assert reverted_sha == initial_sha

                # 5. Ctrl+C cleanly terminates the TUI
                await pilot.press("ctrl+c")
                await pilot.pause()

        asyncio.run(_run())

    def test_tui_new_branch_and_commit_modals(self, temp_git_repo: Path) -> None:
        async def _run() -> None:
            app = PhantomGitApp(
                repo_path=temp_git_repo,
                github_auth=_make_fake_github_auth(),
            )
            async with app.run_test(size=(160, 50)) as pilot:
                await pilot.pause()

                # Open New Branch modal via 'n'
                await pilot.press("n")
                await pilot.pause()
                await pilot.click("#branch-slug-input")
                for ch in "tui-feature":
                    await pilot.press(ch)
                await pilot.click("#btn-create-branch")
                await pilot.pause()

                driver = GitDriver(temp_git_repo)
                assert driver.get_current_branch() == "feat/tui-feature"

                # Stage a new file and use CommitModal ('c') with Auto-Suggest
                (temp_git_repo / "app.py").write_text("print('neon')\n", encoding="utf-8")
                run_git(["add", "app.py"], cwd=temp_git_repo)
                app.refresh_workspace()
                await pilot.pause()

                await pilot.press("c")
                await pilot.pause()
                await pilot.click("#btn-auto-suggest")
                await pilot.pause()
                await pilot.click("#btn-submit-commit")
                await pilot.pause()

                latest_msg = driver.run(["log", "-1", "--format=%s"]).stdout.strip()
                assert latest_msg.startswith("feat")

        asyncio.run(_run())

    def test_tui_ci_check_and_github_repo_switching(
        self,
        multi_repo_sandbox: Path,
        monkeypatch,
    ) -> None:
        alpha = multi_repo_sandbox / "repo-alpha"
        beta = multi_repo_sandbox / "repo-beta"

        fake_report = CIPreFlightReport(
            repo_path=str(alpha),
            project_type="python",
            tier=TestingTier.PRODUCTION,
            pillars=[
                CIPillarResult(
                    name="Code Quality & Type Integrity",
                    status=CIPillarStatus.PASSED,
                    command="ruff check .",
                ),
                CIPillarResult(
                    name="Unit & Component Tests",
                    status=CIPillarStatus.PASSED,
                    command="pytest -q",
                ),
                CIPillarResult(
                    name="Production Standalone Build",
                    status=CIPillarStatus.PASSED,
                    command="compileall -q src",
                ),
            ],
        )
        monkeypatch.setattr(
            "git_manager.tui.app.run_ci_preflight",
            lambda path, tier=TestingTier.PRODUCTION: fake_report,
        )

        gh_repos = [
            GitHubRepoItem(
                name="repo-alpha",
                full_name="X-Phantom/repo-alpha",
                default_branch="main",
                local_path=str(alpha),
            ),
            GitHubRepoItem(
                name="repo-beta",
                full_name="X-Phantom/repo-beta",
                default_branch="main",
                local_path=str(beta),
            ),
        ]

        async def _run() -> None:
            app = PhantomGitApp(
                repo_path=alpha,
                workspace_path=multi_repo_sandbox,
                github_auth=_make_fake_github_auth(gh_repos),
            )
            async with app.run_test(size=(160, 50)) as pilot:
                await pilot.pause()

                # Run 3-pillar CI check via 'k'
                await pilot.press("k")
                await pilot.pause()
                assert app._last_ci_report is not None
                assert app._last_ci_report.passed is True

                # Jump to [6]-GitHub Account & Connected Repositories, select repo-beta, and hot-swap
                await pilot.press("6")
                await pilot.pause()
                repos_list = app.query_one("#github-repos-list", OptionList)
                repos_list.highlighted = 1
                await pilot.press("space")
                await pilot.pause()

                assert app.repo_path.name == "repo-beta"

        asyncio.run(_run())
