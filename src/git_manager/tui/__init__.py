"""Interactive Lazygit-style Purple & Neon TUI package for Phantom Git."""

from git_manager.tui.app import PhantomGitApp, run_tui
from git_manager.tui.modals import (
    CommitModal,
    GitHubAuthModal,
    KeybindingsModal,
    NewBranchModal,
    SecretModal,
    SnapshotModal,
)

__all__ = [
    "CommitModal",
    "GitHubAuthModal",
    "KeybindingsModal",
    "NewBranchModal",
    "PhantomGitApp",
    "SecretModal",
    "SnapshotModal",
    "run_tui",
]
