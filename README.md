# Phantom Git (`phantom-git` / `pgit`) — v0.5.0

> **Agentic GitHub Flow Orchestrator & Multi-Repo Manager** *(backward-compatible alias: `git-mgr`)*  
> *Deterministic version control, 3-pillar local CI pre-flight validation, automated safety nets, Lazygit-style alternate-screen TUI, and the 5-step GitHub Flow loop for human engineers and autonomous AI agents.*

---

## 🌟 Overview

Modern development workflows—especially when powered by autonomous AI agents—demand absolute determinism, zero context pollution, and zero broken GitHub Actions runs. Standard interactive Git CLI workflows often suffer from interactive prompts, direct pushes to `main`, unformatted commit messages, and repeated GitHub CI email alerts for **Code Quality & Type Integrity**, **Unit & Component Tests**, and **Production Standalone Build**.

**Phantom Git** (`phantom-git` / `pgit`) is an industry-grade Git automation platform and CLI designed specifically to provide:
1. **3-Pillar CI Pre-Flight Validator (`pgit check`)**: Runs **Code Quality & Type Integrity**, **Unit & Component Tests**, and **Production Standalone Build** locally before you push, eliminating broken GitHub Actions email alerts.
2. **5-Step GitHub Flow Orchestrator (`pgit flow`)**: Automates isolated feature branching off `main`, AI commits, Pull Request creation, remote CI inspection & AI failure log retrieval, and clean **Squash and Merge**.
3. **The 80/20 Git Core**: High-leverage atomic Git primitives with typed contracts and machine-parseable outputs (`--porcelain=v2`).
4. **Non-Destructive Safety Net**: Automated pre-mutation bookmarks and instant one-step undo using Git reflog and internal snapshot refs.
5. **3-Layer Automation Guardrails**: Scaffolds Layer 1 (Lefthook local hooks + pre-push checks), Layer 2 (3-job GitHub Actions CI + Gitleaks secret detection), and Layer 3 (Google Release Please CD).
6. **Multi-Repo Observability**: Recursive repository discovery and linear rebase synchronization across multi-project workspaces (such as `Project Archive`).

---

## 🔄 The 3-Branch GitHub Flow & Staging Promotion (`pgit flow`)

Instead of committing directly to `main` or `staging`, work in isolated loops:

1. **Initialize Branches (Once)**: `pgit flow init-branches` creates `staging` off `main` and pushes both.
2. **Create a Feature Branch** (`pgit flow start feat/user-auth`): Auto-targets `staging` (if present, else `main`) and switches safely.
3. **Develop, Check & Commit with AI** (`pgit check --tier prototype|production|strict` & `pgit commit --auto`): Validate CI pillars locally matched to your project's maturity.
4. **Open a Pull Request** (`pgit flow pr`): Runs `pgit check`, pushes the feature branch, and opens a PR targeting `staging` (or `main`).
5. **Inspect CI & Root-Cause Repair** (`pgit flow checks` & `pgit flow logs`): View live PR check states or classify failed GitHub Actions logs (`type_or_lint_error`, `stale_test_failure`, `missing_env_or_secret`, `build_compilation_error`) into `.phantom-git/last-ci-failure.md`.
6. **Squash & Merge to Staging** (`pgit flow merge`): Verifies checks are green, squash-merges feature PR into `staging`, and deletes the temporary branch.
7. **Promote Staging to Production (`main`)** (`pgit flow promote`): Opens a PR (`staging` -> `main`) and merges with a standard merge commit (`--merge`) to keep histories aligned and trigger Production VPS deployment.

---

## 🖥️ Custom VPS Multi-Environment Deployment (`pgit scaffold vps`) & Env Hygiene (`pgit env`)

* **Multi-Environment VPS Scaffolding**: Run `pgit scaffold vps --deploy-mode pm2|docker --proxy nginx|caddy --domain yourdomain.com` to generate `deploy/vps/` provisioning scripts, PM2/Docker configs (`staging` on `:3001`, `prod` on `:3000`), and Nginx/Caddy reverse proxies.
* **AI Agent & Repo Hygiene**: `pgit scaffold agents --cursor-claude` creates `AGENTS.md`, `.github/pull_request_template.md`, `.github/dependabot.yml`, `.cursorrules`, and `CLAUDE.md`.
* **Environment Variable Hygiene**:
  * `pgit env sync`: Discovers keys across `.env*` and source files and appends safe empty placeholders (`KEY=`) to `.env.example` (never ignored via `!.env.example`).
  * `pgit env set KEY VALUE --env staging|production`: Provisions GitHub Environment secrets or variables via `gh`.

---

## 🏗️ System Architecture

```
                    ┌────────────────────────────┐
                    │      Developer / AI        │
                    │         Agent CLI          │
                    └─────────────┬──────────────┘
                                  │
                 ┌────────────────▼────────────────┐
                 │       Typer & Rich CLI          │
                 │  (`phantom-git` / `pgit`)       │
                 └────────────────┬────────────────┘
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    │                             │                             │
┌───▼───────────┐         ┌───────▼─────────┐           ┌───────▼───────────┐
│  Core & Flow  │         │   Safety Net    │           │ Multi-Repo Engine │
│ ───────────── │         │ ─────────────── │           │ ───────────────── │
│ • GitDriver   │         │ • Reflog Parser │           │ • Scanner         │
│ • 3-Pillar CI │         │ • Snapshot Reg  │           │ • Health Auditor  │
│ • GitHub Flow │         │ • Safe Undo     │           │ • Linear Sync     │
│ • Commit Gen  │         │ • Auto-Stash    │           │                   │
└───┬───────────┘         └───────┬─────────┘           └───────┬───────────┘
    │                             │                             │
    └─────────────────────────────┼─────────────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Native Git 2.23+ & gh CLI │
                    │   (Porcelain Subprocess)   │
                    └────────────────────────────┘
```

---

## 🛡️ The Three-Layer Guardrail Architecture

Phantom Git standardizes engineering workflows through a defense-in-depth model:

| Layer | Component | Execution Point | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **Layer 1** | **Local Gatekeeper** | Pre-commit / Commit-msg / Pre-push | Lefthook hooks, linting, secret detection, commitlint, 3-pillar pre-flight, main push protection |
| **Layer 2** | **Remote CI Gatekeeper** | GitHub Actions (PR & Push) | **Code Quality & Type Integrity**, **Unit & Component Tests**, **Production Standalone Build**, Gitleaks |
| **Layer 3** | **Release & Delivery** | Google Release Please | SemVer tag computation, changelog generation, release PRs |

---

## 📦 Installation & Setup

### Requirements
- Python `>= 3.10`
- Git `>= 2.23`
- GitHub CLI (`gh`) authenticated via `gh auth login` (for `pgit flow pr/checks/logs/merge`)

### Development Installation
Install in editable mode with development dependencies:

```bash
git clone <repo-url>
cd "Git Manager"
pip install -e .
```

Verify installation:

```bash
phantom-git --version
pgit --version
```

---

## 🚀 Quick Command Reference

```bash
# Launch the Lazygit-style Purple & Neon interactive TUI directly (alternate screen buffer, Ctrl+C to quit)
pgit                                      # or: pgit tui / pgit ui --workspace "C:\...\Project Archive"

# Authenticate Phantom Git with your GitHub account & inspect connected repos
pgit auth login --web                     # Browser OAuth device login (or: --token <PAT>)
pgit auth status                          # Verify authenticated GitHub account
pgit auth repos                           # List connected GitHub repositories

# Run the 3-pillar local CI pre-flight checks before pushing
pgit check --tier production              # Supports: prototype | production | strict

# 3-Branch GitHub Flow & Staging -> Main Promotion
pgit flow init-branches                   # Create & push staging branch off main
pgit flow start feat/payment-gateway      # Step 1: Sync staging/main & branch off
pgit check                                # Step 2a: Validate Quality, Tests, Build locally
pgit commit --auto --strict-flow          # Step 2b: Stage-analyzed Conventional Commit
pgit flow pr                              # Step 3: Push & open PR targeting staging/main
pgit flow checks                          # Step 4a: Inspect remote GitHub Actions checks
pgit flow logs                            # Step 4b: Classify failed CI logs for AI repair
pgit flow merge                           # Step 5: Squash-merge feature PR & clean up
pgit flow promote                         # Flow B: Merge staging -> main (--merge)

# Environment Hygiene & Custom VPS Scaffolding
pgit env sync                             # Safely sync discovered keys into .env.example
pgit env set OPENAI_API_KEY sk-... --env staging
pgit scaffold vps --deploy-mode pm2 --proxy nginx --domain example.com
pgit scaffold agents --cursor-claude      # Generate AGENTS.md, PR template, Dependabot

# Repository & Multi-Repo Dashboards
pgit status                               # Rich single-repo status dashboard
pgit scan                                 # Multi-repo health table across workspace
pgit sync-all                             # Safely rebase-sync all clean repositories

# Safety Net & 3-Layer Scaffolding
pgit snapshot "before-refactor"           # Pre-mutation safety bookmark
pgit undo                                 # Reversible rollback via reflog
pgit scaffold init                        # Deploy Layer 1/2/3 guardrails & AI .gitignore
```

---

## 🎨 Interactive Lazygit-Style TUI (`pgit` / `pgit tui` / `pgit ui`)

Running `pgit` directly launches the unified, **mouse- and keyboard-enabled** Terminal UI inside the terminal's **alternate screen buffer** (hiding scrollback history until exited cleanly via `Ctrl+C` or `q`), styled in **Phantom Purple & Neon** (`#0B0716`, `#7B2CBF`, `#E040FB`, `#00F5D4`, `#00FF87`):

```bash
pgit
# Or point at a specific repo & Project Archive parent folder:
pgit --path "C:\path\to\repo" --workspace "C:\Users\Ehtes\OneDrive\Desktop\Project Archive"
```

### Single-Screen Lazygit Layout & Keybindings
* **Left Column**:
  * `[1]` **Status**: Repository, current branch, ahead/behind, and connected `@github` user
  * `[2]` **Files - Worktrees - Submodules**: Staged/unstaged/untracked status (`Space` / Click to toggle stage/unstage, `a` stage all, `d` discard)
  * `[3]` **Local branches - Remotes - Tags**: Local branches (`Space` / Click to switch, `n` new prefixed branch modal)
  * `[4]` **Commits - Reflog**: Recent commits (`c` Conventional Commit modal with AI diff suggester, `A` 1-click AI auto-commit)
  * `[5]` **Stash**: Stashes (`s` save `-u`, `Z` pop) and Safety Net bookmarks (`B` snapshot, `u` / `D` undo via reflog)
* **Right Column**:
  * `[6]` **GitHub Account & Connected Repositories**: Shows signed-in GitHub account (`g` to sign in / publish repo, `R` to refresh, `Space`/`Enter` to open local clone or clone remote repo)
  * `[0]` **CI / GitHub Flow Status & Checks**: Live 3-pillar pre-flight summary (`k`), remote PR checks (`f`), failed CI logs (`l`), PR creation (`p`), Squash & Merge (`m`), Promote `staging -> main` (`P`), and live `git diff` / commit diff inspector
  * **Command log**: Real-time log of every `git` and `gh` command executed (`@` to focus/hide)
* **Bottom Bar**: Essential navigation & action keybindings (`?` for full keybindings modal, `q` / `Ctrl+C` to quit).

---

## 🤖 AI Agent Integration Guide (Headless CLI vs Interactive TUI)

Phantom Git separates **Human Interactive Mode** from **Autonomous AI Agent Mode** so coding agents (Codex, Claude Code, Cursor, Antigravity, etc.) never hang on TTY prompts or block on interactive TUI screens:

| Mode | Entrypoint | Intended User | Behavior |
| :--- | :--- | :--- | :--- |
| **Human Interactive Mode** | `pgit` (or `pgit tui` / `pgit ui`) | Human developers | Enters alternate screen buffer with full mouse/keyboard Lazygit TUI; terminates cleanly on `Ctrl+C` or `q`. |
| **Autonomous AI Agent Mode** | `pgit <subcommand> ...` | AI coding agents & CI | Strictly headless, deterministic, `GIT_TERMINAL_PROMPT=0` & `GH_PROMPT_DISABLED=1`, machine-readable outputs and exit codes (`0`/`1`). |

> **Important for AI Agents**: Never invoke bare `pgit` without a subcommand inside an automated shell — it launches the alternate-screen TUI and waits for interactive input.

### Autonomous AI Agent Execution Loop

1. **Verify GitHub Authentication & Repository State**:
   ```bash
   pgit auth status            # Confirm active @username, protocol, and token scopes
   pgit auth repos             # List GitHub repos and matched local clones
   pgit status                 # Structured working tree, staged/unstaged/untracked state
   ```
2. **Create a Pre-Mutation Safety Bookmark & Feature Branch**:
   ```bash
   pgit snapshot "before-task" # Captures dirty state safely under refs/git-mgr/bookmarks/
   pgit flow start feat/<slug> # Syncs staging/main and creates a compliant prefixed branch
   ```
3. **Verify 3-Pillar CI Locally & Commit Atomically**:
   ```bash
   pgit check --tier production
   git add -A
   pgit commit --auto --strict-flow
   ```
4. **Open Pull Request, Inspect Remote CI, Self-Heal, & Merge**:
   ```bash
   pgit flow pr                # Runs local 3-pillar check, pushes branch, opens PR
   pgit flow checks            # Inspects remote GitHub Actions PR check states
   pgit flow logs              # On failure: writes root-cause report to .phantom-git/last-ci-failure.md
   pgit flow merge             # On green checks: squash-merges PR & cleans up branch
   pgit flow promote           # Optional release flow: merges staging -> main (--merge)
   ```
5. **Scaffold AI Agent Instructions Into Any Repo**:
   ```bash
   pgit scaffold agents --project-name my-app --project-type python --tier production --cursor-claude --overwrite
   ```
   Generates synchronized `AGENTS.md`, `.cursorrules`, `CLAUDE.md`, `.github/pull_request_template.md`, and `.github/dependabot.yml`.

---

## 📋 Complete CLI Subcommand Reference

| Command Group | Subcommands / Flags | Purpose |
| :--- | :--- | :--- |
| **TUI** | `pgit`, `pgit tui`, `pgit ui` (`-p`, `-w`) | Launch alternate-screen Lazygit TUI (`Ctrl+C` or `q` to quit) |
| **GitHub Auth** | `pgit auth status`, `login` (`--token` / `--web`), `logout`, `repos` | Connect GitHub account, configure Git credentials, list/match repos |
| **GitHub Flow** | `pgit flow init-branches`, `start`, `check`, `pr`, `checks`, `logs`, `merge`, `promote` | End-to-end 3-branch (`feat/* -> staging -> main`) orchestration |
| **Pre-Flight CI** | `pgit check --tier prototype\|production\|strict` | Run Quality/Types, Unit Tests, and Standalone Build locally |
| **Core Git & Safety** | `pgit status`, `branch`, `branches`, `commit` (`--auto`, `--strict-flow`), `stash`, `sync`, `snapshot`, `undo`, `log-linear` | Deterministic 80/20 Git primitives and reflog rollback |
| **Multi-Repo** | `pgit scan [dir]`, `pgit sync-all [dir]` (`--dry-run`, `--force`) | Recursive repo discovery, health audit, and safe rebase sync |
| **Scaffolding & Env** | `pgit scaffold init\|vps\|agents\|ruleset`, `pgit env sync\|set` | Layer 1/2/3 guardrails, VPS configs, agent rules, `.env.example` & secrets |

---

## 🧪 Testing & Verification

The test harness runs in complete isolation using disposable Git sandboxes:

```bash
# Run test suite
pytest

# Run tests with code coverage metrics
pytest --cov=src/git_manager --cov-report=term-missing
```

---

## 📄 License

MIT License. Designed and maintained for modern engineering teams and AI-augmented environments.
