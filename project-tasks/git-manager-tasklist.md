# Phantom Git (`phantom-git` / `pgit`) Master Implementation Tasklist

> **System Designation**: `Phantom Git` (`phantom-git`, `pgit`, `git-mgr` — Agentic GitHub Flow & Multi-Repo Orchestrator)  
> **Target Workspace**: `c:\Users\Ehtes\OneDrive\Desktop\Project Archive\Git Manager`  
> **Status**: Completed  
> **Created**: 2026-10-29  
> **Updated**: 2026-11-16  
> **Version**: 0.5.0  
> **Architecture Plan Reference**: [`git_management_system_plan.md`](file:///C:/Users/Ehtes/.gemini/antigravity/brain/b79c1051-9c9f-4c90-8c3f-dfdeb3c52295/git_management_system_plan.md)

---

## Executive Vision & Objectives

`git-mgr` is an industry-grade Git automation engine and CLI tool designed specifically for both human developers and autonomous AI agents. It eliminates context pollution, prevents commit degradation, replaces brittle interactive prompts with programmatic APIs, provides instant non-destructive rollbacks via a Git reflog Safety Net, discovers and manages multi-repository ecosystems across `Project Archive`, and scaffolds a standardized 3-Layer Automation Guardrail (Local hooks, Remote CI, and SemVer CD).

### Core Quality Metrics
- **Non-Destructive Guarantee**: Zero data loss. Every mutation is bookmarked in the reflog and snapshot ledger.
- **Strict Conventional Commits**: 100% adherence to `<type>(<scope>): <subject>` format with automated SemVer calculation.
- **AI Agent Friendliness**: Headless, deterministic execution paths for staging, committing, and context switching without interactive tty deadlocks.
- **Multi-Repo Observability**: Fast recursive scanning with visual health indicators for branch divergence, untracked changes, and stashes.

---

## Phase Overview & Progress Tracker

| Phase | Description | Task Count | Status | Completion % |
| :--- | :--- | :---: | :---: | :---: |
| **Phase 1** | Project Foundation & Packaging Setup | 4 | `[x]` Completed | 100% |
| **Phase 2** | Core Git Engine & Driver | 5 | `[x]` Completed | 100% |
| **Phase 3** | Safety Net & Undo Ledger | 5 | `[x]` Completed | 100% |
| **Phase 4** | Branch Hygiene & Conventional Commits Engine | 7 | `[x]` Completed | 100% |
| **Phase 5** | 3-Layer Automation Scaffolder | 7 | `[x]` Completed | 100% |
| **Phase 6** | Multi-Repo Discovery & Health Dashboard | 4 | `[x]` Completed | 100% |
| **Phase 7** | Typer CLI & Rich Terminal Dashboard | 7 | `[x]` Completed | 100% |
| **Phase 8** | Test Suite, QA Quality Gates, & Reality Check | 5 | `[x]` Completed | 100% |
| **Phase 9** | Rebranding to Phantom Git (`phantom-git` / `pgit` / `git-mgr`) | 3 | `[x]` Completed | 100% |
| **Phase 10** | 3-Pillar Local CI Pre-Flight Engine & Templates | 4 | `[x]` Completed | 100% |
| **Phase 11** | 5-Step GitHub Flow Orchestration Engine (`pgit flow`) | 5 | `[x]` Completed | 100% |
| **Phase 12** | Automated Test Suite, Linting & QA Sign-Off | 3 | `[x]` Completed | 100% |
| **Phase 13** | Smart Testing Tiers & Root-Cause CI Classifier | 2 | `[x]` Completed | 100% |
| **Phase 14** | 3-Branch (`feat/* -> staging -> main`) & Promotion Flow | 3 | `[x]` Completed | 100% |
| **Phase 15** | Custom VPS Multi-Env CI/CD & Server Provisioning | 3 | `[x]` Completed | 100% |
| **Phase 16** | AI Agent Instructions (`AGENTS.md`), Env Hygiene & Tests | 4 | `[x]` Completed | 100% |
| **Phase 17** | Textual Dependency & Purple/Neon Theme Foundation | 2 | `[x]` Completed | 100% |
| **Phase 18** | Lazygit 5-Panel Workspace & Modal Dialogs | 3 | `[x]` Completed | 100% |
| **Phase 19** | Flow/CI Center, Archive Hub & VPS/Env TUI Tabs | 3 | `[x]` Completed | 100% |
| **Phase 20** | Headless Textual Pilot Suite & Documentation | 2 | `[x]` Completed | 100% |
| **Phase 21** | Alternate Screen TUI, Lazygit Layout & GitHub Auth (`v0.5.0`) | 4 | `[x]` Completed | 100% |
| **Total** | | **85** | | **100%** |

---

## Phase 1: Project Foundation & Packaging Setup

Focus: Initialize project structure, set up package metadata with PyProject configuration, register CLI entry points, and establish testing harnesses with disposable Git sandbox fixtures.

- [x] **TASK-P1-01: Directory Structure Initialization**
  - **Description**: Establish the full package layout according to the architecture specification under `src/git_manager/` and `tests/`.
  - **Dependencies**: None
  - **Acceptance Criteria**:
    - Directory hierarchy created: `src/git_manager/`, `src/git_manager/core/`, `src/git_manager/scaffold/`, `src/git_manager/scaffold/templates/`, `src/git_manager/multirepo/`, `src/git_manager/utils/`, `tests/`, `project-tasks/`.
    - Every package directory contains an empty `__init__.py` file declaring proper module packaging.
  - **QA Evidence Verification**:
    - Run `Test-Path` on all defined directory paths in PowerShell; all must return `True`.

- [x] **TASK-P1-02: Package Configuration & Dependency Specification (`pyproject.toml`)**
  - **Description**: Author standard `pyproject.toml` with setuptools/hatchling backend, Python >= 3.10 constraint, and dependencies: `typer[all]>=0.9.0`, `rich>=13.0.0`, `pydantic>=2.0.0`, `jinja2>=3.1.0`, `pytest>=7.4.0`, and `pytest-cov`. Register `git-mgr = "git_manager.cli:app"` console script.
  - **Dependencies**: TASK-P1-01
  - **Acceptance Criteria**:
    - Valid `pyproject.toml` exists with clean metadata (name, version, description, authors, dependencies, dev dependencies).
    - Entry point `[project.scripts]` maps `git-mgr` to `git_manager.cli:app`.
  - **QA Evidence Verification**:
    - Parse `pyproject.toml` using `python -m pip install -e . --dry-run` or validation script; no schema errors.

- [x] **TASK-P1-03: Editable Installation & CLI Smoke Verification**
  - **Description**: Install `git-mgr` in editable mode (`pip install -e .`) within current Python environment and verify imports.
  - **Dependencies**: TASK-P1-02
  - **Acceptance Criteria**:
    - `pip install -e .` completes with exit code 0.
    - Python execution `python -c "import git_manager; print(git_manager.__name__)"` outputs `git_manager`.
  - **QA Evidence Verification**:
    - Subprocess execution returns exit code 0 with package name string.

- [x] **TASK-P1-04: Test Harness & Base Fixture Setup (`tests/conftest.py`)**
  - **Description**: Configure pytest test harness with isolated temporary Git repository fixtures (`temp_git_repo`, `dirty_git_repo`, `multi_repo_sandbox`) using `tempfile.TemporaryDirectory` and native git init.
  - **Dependencies**: TASK-P1-03
  - **Acceptance Criteria**:
    - `tests/conftest.py` provides clean disposable git repos with initial commit and configured dummy user (`testuser`, `test@example.com`).
    - Fixture properly tears down directories and handles Windows read-only file locks on `.git/objects`.
  - **QA Evidence Verification**:
    - Run `pytest tests/conftest.py -v` (or a smoke test using fixture) yielding passing setup/teardown.

---

## Phase 2: Core Git Engine & Driver

Focus: Implement robust, typed subprocess execution for Git, status parsing using porcelain v2, environmental sanity checking, and atomic 80/20 Git commands.

- [x] **TASK-P2-01: Low-Level Git Subprocess Runner (`core/git_driver.py`)**
  - **Description**: Implement `GitDriver` class with `run(args, cwd, check=True)` returning typed `GitResult(stdout, stderr, exit_code, success)`. Support timeout, custom environment variables, and typed exception `GitCommandError` containing command line, exit code, and captured stderr.
  - **Dependencies**: TASK-P1-04
  - **Acceptance Criteria**:
    - Non-zero exit codes raise `GitCommandError` when `check=True` and populate descriptive messages.
    - Captures both stdout and stderr with UTF-8 decoding and strip handling.
    - Works reliably on Windows PowerShell environments.
  - **QA Evidence Verification**:
    - Unit test running valid (`git --version`) and invalid (`git invalid-subcmd-xyz`) commands, verifying correct `GitResult` and `GitCommandError`.

- [x] **TASK-P2-02: Git Environment & Capability Detection**
  - **Description**: Add environment validation helpers in `core/git_driver.py`: verify git binary exists on PATH, parse git version (ensure >= 2.23 for `switch`/`restore`), find repository root (`git rev-parse --show-toplevel`), and detect bare repositories.
  - **Dependencies**: TASK-P2-01
  - **Acceptance Criteria**:
    - `get_git_version()` returns a comparable tuple (e.g., `(2, 43, 0)`).
    - `find_repo_root(path)` traverses upward and returns `Path` or `None` if not inside a git repository.
    - Clean error raised when git binary is missing or incompatible.
  - **QA Evidence Verification**:
    - Test `find_repo_root` inside repo fixture and in a non-git temporary folder.

- [x] **TASK-P2-03: Structured Git Status Parser (`core/git_driver.py`)**
  - **Description**: Implement `get_status(repo_path)` parsing `git status --porcelain=v2 --branch`. Parse into Pydantic model `RepoStatus`: `branch_name`, `upstream`, `ahead_count`, `behind_count`, `staged_files` (list of `FileStatus`), `unstaged_files`, `untracked_files`, and `is_clean`.
  - **Dependencies**: TASK-P2-02
  - **Acceptance Criteria**:
    - Correctly parses porcelain v2 format headers (`# branch.oid`, `# branch.head`, `# branch.upstream`, `# branch.ab`).
    - Differentiates staged additions, modifications, deletions, untracked files, and unstaged modifications.
    - Returns `is_clean == True` when working tree and index are pristine.
  - **QA Evidence Verification**:
    - Comprehensive unit test asserting `RepoStatus` fields across clean, untracked, modified, and staged repository states.

- [x] **TASK-P2-04: Basic 80/20 Git Operations Primitives**
  - **Description**: Implement typed high-level operations on `GitDriver`: `stage_files(paths)`, `unstage_files(paths)`, `create_commit(message)`, `switch_branch(name, create=False)`, `stash_save(message, include_untracked=True)`, and `stash_pop(index=0)`.
  - **Dependencies**: TASK-P2-03
  - **Acceptance Criteria**:
    - Stash commands always default to `include_untracked=True` (`-u`) to protect AI-created scratch files.
    - `switch_branch` utilizes `git switch` (with `-c` when `create=True`).
    - Methods return typed result objects.
  - **QA Evidence Verification**:
    - Test staging specific files, committing, creating a branch, stashing untracked files, and popping stash.

- [x] **TASK-P2-05: Unit & Sandbox Tests for Git Driver (`tests/test_git_driver.py`)**
  - **Description**: Write automated tests for all `GitDriver` methods against disposable temporary Git repositories.
  - **Dependencies**: TASK-P2-04
  - **Acceptance Criteria**:
    - 100% method coverage on `core/git_driver.py`.
    - Edge cases tested: committing with empty index, switching to nonexistent branch, stashing in clean working directory.
  - **QA Evidence Verification**:
    - Execute `pytest tests/test_git_driver.py` and produce green test report.

---

## Phase 3: Safety Net & Undo Ledger

Focus: Build the non-destructive safety net using Git reflog, automated pre-mutation bookmarks, working directory stash protection, and instant one-step undo capability.

- [x] **TASK-P3-01: Reflog Parser & State Inspection (`core/safety_net.py`)**
  - **Description**: Implement `parse_reflog(repo_path, limit=20)` parsing `git reflog --format="%gD|%h|%H|%gs"` into list of `ReflogEntry` models: `selector` (e.g. `HEAD@{0}`), `short_sha`, `commit_sha`, `action_type` (commit, rebase, checkout, merge, reset), and `description`.
  - **Dependencies**: TASK-P2-05
  - **Acceptance Criteria**:
    - Accurately splits reflog records and extracts the preceding state and action description.
    - Handles empty reflog or initial commit states gracefully.
  - **QA Evidence Verification**:
    - Unit test verifying parsed reflog entries after a sequence of commits and branch checkouts.

- [x] **TASK-P3-02: Pre-Mutation Snapshot Bookmarking (`core/safety_net.py`)**
  - **Description**: Implement `create_snapshot(repo_path, label, auto_stash=True)`: captures uncommitted work into an annotated safety stash if dirty, and records a lightweight tag or internal ref `refs/git-mgr/snapshots/<timestamp>_<label>`.
  - **Dependencies**: TASK-P3-01
  - **Acceptance Criteria**:
    - Working tree state is saved without destroying current index/unstaged edits unless requested.
    - Snapshot metadata records previous commit SHA, timestamp, label, and stash ref (if created).
    - Snapshots can be listed via `list_snapshots(repo_path)`.
  - **QA Evidence Verification**:
    - Create snapshot on dirty repo; verify snapshot reference and stash record are successfully created.

- [x] **TASK-P3-03: Instant Undo Engine (`core/safety_net.py`)**
  - **Description**: Implement `undo(repo_path, target_ref=None, force=False)`: inspects reflog and snapshot ledger, identifies the state immediately before the last mutation, and executes a non-destructive recovery (`git reset --keep` or `git reset --hard` only with backup bookmark).
  - **Dependencies**: TASK-P3-02
  - **Acceptance Criteria**:
    - Always creates a recovery bookmark before executing any undo, guaranteeing undo itself can be undone.
    - If uncommitted changes exist, safely stashes them before moving HEAD.
    - Successfully reverses accidental commits, bad resets, or accidental branch checkouts.
  - **QA Evidence Verification**:
    - Simulate: commit bad code -> call `undo()` -> verify working tree and HEAD restored to original SHA.

- [x] **TASK-P3-04: Working Directory Stash Guard (`core/safety_net.py`)**
  - **Description**: Implement context manager `guarded_mutation(repo_path, operation_name)` that automatically bookmarks state, captures dirty files, executes a code block, and restores state or reports error if the operation fails.
  - **Dependencies**: TASK-P3-03
  - **Acceptance Criteria**:
    - Protects multi-step operations (e.g. bulk rebase or branch switch) from leaving working tree in corrupt state.
    - Restores stashed work on unexpected exception.
  - **QA Evidence Verification**:
    - Trigger an exception inside `guarded_mutation` and assert original working tree state is preserved.

- [x] **TASK-P3-05: Unit & Integration Tests for Safety Net (`tests/test_safety_net.py`)**
  - **Description**: Author comprehensive automated tests for reflog parsing, snapshot creation, safe rollback, and undo recovery.
  - **Dependencies**: TASK-P3-04
  - **Acceptance Criteria**:
    - All safety net scenarios covered with 100% assertions passing.
    - Verifies zero data loss under simulated failure.
  - **QA Evidence Verification**:
    - Execute `pytest tests/test_safety_net.py` yielding 100% pass rate.

---

## Phase 4: Branch Hygiene & Conventional Commits Engine

Focus: Enforce branch prefix conventions (`feat/`, `fix/`, `chore/`), build Conventional Commit parser and validator, implement diff analysis for auto-commit message suggestion, and compute SemVer increments.

- [x] **TASK-P4-01: Branch Hygiene Validator (`core/branch_hygiene.py`)**
  - **Description**: Implement `validate_branch_name(name)` validating branch against allowed prefixes: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`, `ci/`, `perf/`. Name must follow lowercase alphanumeric slug convention (`^[a-z]+/[a-z0-9._-]+$`). Also implement `format_branch_name(prefix, description)`.
  - **Dependencies**: TASK-P1-04
  - **Acceptance Criteria**:
    - Valid branches (e.g. `feat/user-auth`, `fix/issue-102`) pass validation.
    - Invalid branches (e.g. `my-feature`, `FEAT/Uppercase`, `feat/spaces in name`) fail with helpful validation message.
  - **QA Evidence Verification**:
    - Unit tests asserting positive and negative branch naming test cases.

- [x] **TASK-P4-02: Safe Branch Switcher (`core/branch_hygiene.py`)**
  - **Description**: Implement `switch_or_create(repo_path, branch_name, auto_stash=True)`: validates branch name, checks if branch exists locally or on remote, stashes dirty working directory with label if needed, executes `git switch` or `git switch -c`, and reapplies stash on destination if configured.
  - **Dependencies**: TASK-P4-01, TASK-P2-04
  - **Acceptance Criteria**:
    - Blocks creation of non-compliant branch names unless `--force-name` is passed.
    - Seamlessly transitions between branches with uncommitted work via safe auto-stash.
  - **QA Evidence Verification**:
    - Switch branch with dirty working directory in temp repo, verify clean switch and stash preservation.

- [x] **TASK-P4-03: Conventional Commit Specification Engine (`core/commit_parser.py`)**
  - **Description**: Implement Pydantic model `ConventionalCommit`: `type` (feat, fix, chore, docs, style, refactor, perf, test, build, ci), `scope` (optional), `is_breaking` (bool), `subject` (imperative description), `body` (optional), `breaking_description` (optional). Implement `parse_commit_message(msg)` and `format_commit_message(commit)`.
  - **Dependencies**: TASK-P1-02
  - **Acceptance Criteria**:
    - Accurately parses standard messages (e.g. `feat(auth): add jwt login`, `fix!: drop legacy endpoint`).
    - Validates commit subject starts with lowercase and has no trailing period.
    - Detects breaking change markers (`!` after scope or `BREAKING CHANGE:` footer).
  - **QA Evidence Verification**:
    - Unit tests checking round-trip parsing and formatting of various commit messages.

- [x] **TASK-P4-04: Staged Diff Analyzer & Commit Suggester (`core/commit_parser.py`)**
  - **Description**: Implement `suggest_commit_message(repo_path)`: inspects `git diff --cached`, examines modified file paths, detects dominant pattern (e.g. only `tests/` -> `test`, only `.md` -> `docs`, only `.github/` -> `ci`, only bugfix pattern -> `fix`), and generates a draft `ConventionalCommit`.
  - **Dependencies**: TASK-P4-03, TASK-P2-03
  - **Acceptance Criteria**:
    - Suggests appropriate type and scope based on path heuristics.
    - Returns structured `ConventionalCommit` object with user-editable subject.
    - Handles case where nothing is staged with clear exception.
  - **QA Evidence Verification**:
    - Unit test staging documentation file -> asserts suggested commit starts with `docs:`.

- [x] **TASK-P4-05: SemVer Impact Calculator (`core/commit_parser.py`)**
  - **Description**: Implement `calculate_semver_bump(commits: list[ConventionalCommit]) -> SemVerBump`: calculates highest bump level (`MAJOR`, `MINOR`, `PATCH`, or `NONE`) according to SemVer specification. Also implement `compute_next_version(current_version: str, bump: SemVerBump) -> str`.
  - **Dependencies**: TASK-P4-03
  - **Acceptance Criteria**:
    - `feat` without breaking change returns `MINOR`.
    - `fix`, `perf`, `refactor` returns `PATCH`.
    - Any breaking change (`is_breaking=True`) returns `MAJOR`.
    - Calculates `1.2.3` -> `1.3.0` for Minor, `2.0.0` for Major.
  - **QA Evidence Verification**:
    - Test version transitions for series of mixed commit messages.

- [x] **TASK-P4-06: Linear History & Rebase Automation (`core/linear_history.py`)**
  - **Description**: Implement `sync_linear_rebase(repo_path, remote="origin", branch=None)`: ensures working tree is clean, fetches upstream, and executes `git pull --rebase` to avoid merge commit bubbles. Implement `get_linear_log(repo_path, max_count=15)` to output condensed oneline linear graph.
  - **Dependencies**: TASK-P2-04
  - **Acceptance Criteria**:
    - Aborts rebase if uncommitted changes exist without stashing.
    - Identifies if repo is ahead, behind, or diverged.
    - Returns formatted log output with commit hashes and conventional prefixes.
  - **QA Evidence Verification**:
    - Test linear rebase sync against mock upstream remote in sandbox fixture.

- [x] **TASK-P4-07: Unit Tests for Branch & Commit Engines (`tests/test_commit_parser.py`, `tests/test_branch_hygiene.py`)**
  - **Description**: Comprehensive test suite covering branch hygiene, commit parsing, diff suggestion, SemVer calculation, and linear rebase logic.
  - **Dependencies**: TASK-P4-01, TASK-P4-02, TASK-P4-03, TASK-P4-04, TASK-P4-05, TASK-P4-06
  - **Acceptance Criteria**:
    - All tests pass with zero warnings.
  - **QA Evidence Verification**:
    - Run `pytest tests/test_commit_parser.py tests/test_branch_hygiene.py` with passing results.

---

## Phase 5: 3-Layer Automation Scaffolder

Focus: Implement Jinja2-powered template scaffolding engine injecting Layer 1 (Local hooks & commitlint), Layer 2 (GitHub Actions CI & Gitleaks), Layer 3 (Google Release Please CD), and AI-tailored `.gitignore` files.

- [x] **TASK-P5-01: Template Engine Architecture (`scaffold/engine.py`)**
  - **Description**: Build `TemplateEngine` using Jinja2 with template directory resolution, parameter interpolation, conflict detection (prevent accidental overwriting of existing configs without `--force`), and dry-run rendering mode.
  - **Dependencies**: TASK-P1-02
  - **Acceptance Criteria**:
    - Renders templates with custom variables (project name, author, python version, node version).
    - Detects if destination files exist and prompts/warns unless overwrite flag is set.
    - Dry-run returns file path mapping and generated content without touching disk.
  - **QA Evidence Verification**:
    - Unit test testing render output, dry-run mode, and collision prevention.

- [x] **TASK-P5-02: Layer 1 Local Gatekeeper Templates (`scaffold/templates/layer1/`)**
  - **Description**: Author standard configuration templates: `lefthook.yml` (high-performance git hooks for pre-commit linting and commit-msg commitlint) and fallback `.pre-commit-config.yaml` with secret detection hooks.
  - **Dependencies**: TASK-P5-01
  - **Acceptance Criteria**:
    - `lefthook.yml` configures `pre-commit` hook (linting, secret scan) and `commit-msg` hook (Conventional Commit regex validation).
    - Clean YAML formatting with comments explaining hook rules.
  - **QA Evidence Verification**:
    - Validate generated `lefthook.yml` and `.pre-commit-config.yaml` against YAML schema validator.

- [x] **TASK-P5-03: Layer 2 Remote CI Gatekeeper Templates (`scaffold/templates/layer2/`)**
  - **Description**: Author GitHub Actions workflows: `.github/workflows/ci.yml` (multi-OS/Python test matrix, linting, commitlint verification) and `.github/workflows/security.yml` (Gitleaks automated PR secret scan).
  - **Dependencies**: TASK-P5-01
  - **Acceptance Criteria**:
    - Workflows trigger on PRs targeting `main` and pushes to `main`.
    - Includes Gitleaks action step configured to fail on leaked credentials.
    - Enforces commit message and PR title checking.
  - **QA Evidence Verification**:
    - Validate workflow YAMLs with GitHub Actions schema / YAML linter.

- [x] **TASK-P5-04: Layer 3 Release Please CD Templates (`scaffold/templates/layer3/`)**
  - **Description**: Author Google Release Please workflow `.github/workflows/release-please.yml` and configuration files `release-please-config.json` and `.release-please-manifest.json`.
  - **Dependencies**: TASK-P5-01
  - **Acceptance Criteria**:
    - Configured for python/node release types.
    - Automates changelog generation, version bumping, release PR creation, and GitHub tag publishing upon merge to `main`.
  - **QA Evidence Verification**:
    - Verify JSON and YAML templates parse correctly and contain valid Release Please configuration.

- [x] **TASK-P5-05: AI-Tailored `.gitignore` Templates (`scaffold/templates/gitignore/`)**
  - **Description**: Author comprehensive `.gitignore` template covering Python, Node.js, common OS files, and specifically AI agent scratch directories (`.gemini/`, `.antigravity/`, `brain/`, `scratch/`, `*.prompt.md`, `.env*`, `*.tmp`).
  - **Dependencies**: TASK-P5-01
  - **Acceptance Criteria**:
    - Covers language-specific patterns and agent-specific temporary paths.
    - Prevents accidental committing of AI agent caches, logs, and sandbox files.
  - **QA Evidence Verification**:
    - Unit test checking that `.gitignore` matches agent artifacts and standard build files.

- [x] **TASK-P5-06: GitHub Ruleset Script Generator (`scaffold/ruleset.py`)**
  - **Description**: Implement `generate_ruleset_script(repo_name)`: outputs a ready-to-run GitHub CLI (`gh`) script or JSON payload establishing branch protection on `main` (require squash merge, require status checks, auto-delete branch).
  - **Dependencies**: TASK-P5-01
  - **Acceptance Criteria**:
    - Generates executable PowerShell / Bash script invoking `gh api` to create branch protection ruleset.
    - Clearly documents prerequisites (`gh auth login`).
  - **QA Evidence Verification**:
    - Unit test verifying generated JSON ruleset payload matches GitHub Ruleset API schema.

- [x] **TASK-P5-07: Scaffolder Integration Tests (`tests/test_scaffold.py`)**
  - **Description**: Author test suite verifying full scaffolding injection into a clean temporary repository.
  - **Dependencies**: TASK-P5-02, TASK-P5-03, TASK-P5-04, TASK-P5-05, TASK-P5-06
  - **Acceptance Criteria**:
    - Running scaffolder in test repo writes Layer 1, Layer 2, Layer 3, and `.gitignore` files.
    - Re-running without force raises expected collision exception without modifying files.
  - **QA Evidence Verification**:
    - Execute `pytest tests/test_scaffold.py` with passing results.

---

## Phase 6: Multi-Repo Discovery & Health Dashboard

Focus: Implement recursive repository scanner for `Project Archive`, structured health audits (dirt, stashes, divergence), and safe linear rebase bulk syncing.

- [x] **TASK-P6-01: Multi-Repo Directory Scanner (`multirepo/scanner.py`)**
  - **Description**: Implement `discover_repositories(root_path, max_depth=3)`: efficiently walks directory tree, identifies directories containing a valid `.git` directory, avoids scanning inside `.git` or `node_modules` or `venv`, and returns list of repository `Path`s.
  - **Dependencies**: TASK-P2-02
  - **Acceptance Criteria**:
    - Discovers all top-level and nested project repos up to `max_depth`.
    - Skips ignored directories (`node_modules`, `.venv`, `.git`) for fast performance.
    - Returns sorted list of absolute paths.
  - **QA Evidence Verification**:
    - Create a test folder with multiple git repos at various depths and verify exact discovery list.

- [x] **TASK-P6-02: Repository Health Auditor (`multirepo/health_check.py`)**
  - **Description**: Implement `audit_repository_health(repo_path)` returning `RepoHealth(path, name, current_branch, is_clean, modified_count, untracked_count, stash_count, ahead_count, behind_count, upstream_name, has_remote)`.
  - **Dependencies**: TASK-P6-01, TASK-P2-03
  - **Acceptance Criteria**:
    - Aggregates git status, branch name, remote synchronization, and stash count in a single audit pass.
    - Handles repos with no commits, detached HEAD, or no configured remotes gracefully without crashing.
  - **QA Evidence Verification**:
    - Test health audit across clean, dirty, unpushed, and un-tracked repos.

- [x] **TASK-P6-03: Bulk Linear Rebase Sync (`multirepo/sync.py`)**
  - **Description**: Implement `sync_all_repositories(repos, on_progress=None)`: iterates repositories, verifies each is in clean state on a tracking branch, executes `git pull --rebase`, tracks results (`synced`, `skipped_dirty`, `skipped_no_upstream`, `failed`), and skips dirty repos with warnings rather than aborting.
  - **Dependencies**: TASK-P6-02, TASK-P4-06
  - **Acceptance Criteria**:
    - Dirty repos are never modified and marked as `skipped_dirty`.
    - Repos with upstream divergence safely pull with rebase.
    - Returns structured summary report of all sync actions.
  - **QA Evidence Verification**:
    - Run bulk sync across a multi-repo sandbox with 1 clean repo and 1 dirty repo; verify clean synced, dirty skipped.

- [x] **TASK-P6-04: Multi-Repo Scanner Tests (`tests/test_multirepo.py`)**
  - **Description**: Author automated tests for multi-repo discovery, health checking, and bulk sync behavior.
  - **Dependencies**: TASK-P6-01, TASK-P6-02, TASK-P6-03
  - **Acceptance Criteria**:
    - 100% passing tests for scanner edge cases.
  - **QA Evidence Verification**:
    - Run `pytest tests/test_multirepo.py` with 100% pass rate.

---

## Phase 7: Typer CLI & Rich Terminal Dashboard

Focus: Implement modern Typer CLI interface and Rich-powered interactive terminal formatting (colored tables, status badges, progress spinners, interactive prompts).

- [x] **TASK-P7-01: Rich Terminal Utilities (`utils/console.py`)**
  - **Description**: Create styling helpers using `rich.console.Console`, `rich.table.Table`, `rich.panel.Panel`, and `rich.prompt.Prompt`. Build reusable formatters for `RepoStatus`, `RepoHealth`, commit logs, and warning/error alerts.
  - **Dependencies**: TASK-P1-02
  - **Acceptance Criteria**:
    - Consistent color palette (Green = Clean/Success, Yellow = Warning/Dirty, Red = Diverged/Error, Cyan = Branch/Action).
    - Gracefully handles non-interactive or non-tty environments (disables interactive prompts or uses sane defaults).
  - **QA Evidence Verification**:
    - Run utility script rendering sample tables and panels without exception.

- [x] **TASK-P7-02: CLI Root & Status Command (`src/git_manager/cli.py`)**
  - **Description**: Implement Typer main application with `--version` and `git-mgr status [path]`. Status command renders a comprehensive Rich dashboard of the current repository (current branch, commit SHA, remote tracking, uncommitted files categorized by staged/unstaged/untracked, and stashes).
  - **Dependencies**: TASK-P7-01, TASK-P2-03
  - **Acceptance Criteria**:
    - `git-mgr status` displays formatted status card in the terminal.
    - If executed outside a git repository, outputs a helpful error panel and exits with code 1.
  - **QA Evidence Verification**:
    - Run `git-mgr status` in temporary repo fixture via Typer `CliRunner`.

- [x] **TASK-P7-03: Daily Operations CLI Commands**
  - **Description**: Implement core 80/20 commands:
    - `git-mgr branch <name>`: validate prefix, switch/create branch.
    - `git-mgr commit [--message <m>] [--type <t>] [--scope <s>] [--breaking] [--auto]`: interactive or automated Conventional Commit builder.
    - `git-mgr stash [save|pop|list]`: guaranteed untracked file handling.
    - `git-mgr sync`: pull with rebase after clean check.
  - **Dependencies**: TASK-P7-02, TASK-P4-02, TASK-P4-04
  - **Acceptance Criteria**:
    - `git-mgr branch feat/auth` successfully validates and creates branch.
    - `git-mgr commit --auto` analyzes diff and suggests commit.
    - Rejects invalid branch names or unparseable commit formats.
  - **QA Evidence Verification**:
    - Test daily commands using Typer `CliRunner`.

- [x] **TASK-P7-04: Safety Net CLI Commands**
  - **Description**: Implement recovery commands:
    - `git-mgr snapshot [label]`: create explicit working state bookmark.
    - `git-mgr undo [--force]`: roll back last action using reflog.
    - `git-mgr log-linear [--limit <n>]`: display Rich linear graph.
  - **Dependencies**: TASK-P7-02, TASK-P3-03
  - **Acceptance Criteria**:
    - `git-mgr snapshot "before-refactor"` records snapshot tag.
    - `git-mgr undo` rolls back HEAD safely with confirmation.
    - `git-mgr log-linear` displays clean visual graph.
  - **QA Evidence Verification**:
    - Execute snapshot and undo via `CliRunner` and verify repo state matches expectation.

- [x] **TASK-P7-05: Scaffolding CLI Commands**
  - **Description**: Implement scaffolding commands:
    - `git-mgr scaffold init [--layer <1|2|3|all>] [--force]`: inject templates.
    - `git-mgr scaffold ruleset`: print or export GitHub branch protection script.
  - **Dependencies**: TASK-P7-02, TASK-P5-07
  - **Acceptance Criteria**:
    - `git-mgr scaffold init --layer all` renders all layers into current repo.
    - Informs user of created files with Rich checkmarks.
  - **QA Evidence Verification**:
    - Run `git-mgr scaffold init` in test repo and verify files are created.

- [x] **TASK-P7-06: Multi-Repo CLI Commands**
  - **Description**: Implement multi-repo commands:
    - `git-mgr scan [directory]`: scan directory tree and display Rich table of all discovered repos and health status.
    - `git-mgr sync-all [directory]`: run bulk linear rebase across clean repos with progress bar.
  - **Dependencies**: TASK-P7-02, TASK-P6-03
  - **Acceptance Criteria**:
    - `git-mgr scan` outputs table with columns: Repo, Branch, Dirt, Stashes, Sync State.
    - `git-mgr sync-all` reports clear summary of synced and skipped repositories.
  - **QA Evidence Verification**:
    - Test `git-mgr scan` and `sync-all` via `CliRunner` against mock multi-repo root.

- [x] **TASK-P7-07: CLI End-to-End Command Smoke Tests (`tests/test_cli.py`)**
  - **Description**: Author comprehensive test suite testing Typer CLI invocations for all commands using `typer.testing.CliRunner`.
  - **Dependencies**: TASK-P7-03, TASK-P7-04, TASK-P7-05, TASK-P7-06
  - **Acceptance Criteria**:
    - All subcommands tested for success and failure exits.
    - Proper exit codes (0 for success, 1 for validation or runtime error).
  - **QA Evidence Verification**:
    - Run `pytest tests/test_cli.py` with passing results.

---

## Phase 8: Comprehensive Test Suite, QA Quality Gates, & Production Reality Check

Focus: Execute end-to-end integration tests, code coverage analysis, real-world multi-repo simulations, packaging verification, and final quality gate sign-off.

- [x] **TASK-P8-01: End-to-End Integration Sandbox Suite (`tests/test_e2e_workflow.py`)**
  - **Description**: Implement full end-to-end integration workflow test in disposable temporary sandbox: init repo -> `git-mgr branch feat/login` -> stage files -> `git-mgr commit --auto` -> `git-mgr scaffold init` -> `git-mgr snapshot` -> simulate bad rebase/commit -> `git-mgr undo` -> verify complete restoration.
  - **Dependencies**: Phase 1 through Phase 7
  - **Acceptance Criteria**:
    - Entire lifecycle executes end-to-end without unhandled exceptions.
    - Verifies undo cleanly restores working state after simulated mistake.
  - **QA Evidence Verification**:
    - Run `pytest tests/test_e2e_workflow.py -v` yielding 100% pass (6/6 passing).

- [x] **TASK-P8-02: Code Quality Gates & Test Coverage Audit**
  - **Description**: Run full pytest suite with coverage metrics (`pytest --cov=src/git_manager --cov-report=term-missing`). Verify high coverage across core modules (`git_driver`, `safety_net`, `commit_parser`, `branch_hygiene`).
  - **Dependencies**: TASK-P8-01
  - **Acceptance Criteria**:
    - Core logic coverage exceeds 90%.
    - Zero failing tests, zero unhandled regressions.
  - **QA Evidence Verification**:
    - Output coverage report with zero errors: 207 tests passing, 87% total codebase coverage with core modules exceeding 90%-99%.

- [x] **TASK-P8-03: Multi-Repo Real-World Simulation Test**
  - **Description**: Build automated simulation representing `Project Archive` containing 3 realistic repos (Repo A: clean tracking branch; Repo B: dirty uncommitted files; Repo C: ahead of remote). Run `git-mgr scan` and `git-mgr sync-all`, verifying audit accuracy and safe non-destructive skipping of dirty repos.
  - **Dependencies**: TASK-P8-02
  - **Acceptance Criteria**:
    - Repo A syncs cleanly.
    - Repo B is flagged as dirty and safely skipped without data loss.
    - Repo C reports ahead state accurately.
  - **QA Evidence Verification**:
    - Test asserts exact counts and repository states after bulk operations in `test_multirepo_scan_and_sync_ecosystem`.

- [x] **TASK-P8-04: Standalone Packaging & CLI Binary Verification**
  - **Description**: Test entry point execution directly from terminal: verify `git-mgr --help`, `git-mgr --version`, and subcommands respond properly as a standalone CLI executable.
  - **Dependencies**: TASK-P8-03
  - **Acceptance Criteria**:
    - `git-mgr --help` displays clean Typer command reference with descriptions.
    - Command exit code is 0.
  - **QA Evidence Verification**:
    - PowerShell command `git-mgr --help` and `git-mgr --version` succeed with exit code 0.

- [x] **TASK-P8-05: Final Reality Check & Tasklist Completion Sign-off**
  - **Description**: Execute a comprehensive reality check verifying that all acceptance criteria across all 8 phases are met, documentation is intact, and the system is fully operational.
  - **Dependencies**: TASK-P8-01, TASK-P8-02, TASK-P8-03, TASK-P8-04
  - **Acceptance Criteria**:
    - All 44 tasks in this task list are verified and tracked.
    - `git-mgr` is ready for production use across all user projects.
  - **QA Evidence Verification**:
    - Final QA reality check executed by `testing-reality-checker`: 211/211 pytest regression tests passed, Ruff lint/format checks passed (0 errors across 30 files), standalone CLI invocations verified in PowerShell (`git-mgr --help`, `git-mgr --version`), E2E lifecycle and multi-repo simulations verified, and 100% completion recorded across all 44 tasks.

---

## Phase 9: Rebranding to Phantom Git (`phantom-git` / `pgit` / `git-mgr`)

Focus: Rebrand the tool to Phantom Git (`v0.2.0`) while retaining backward compatibility for `git-mgr`.

- [x] **TASK-P9-01: Package Metadata & Entrypoints (`pyproject.toml`, `__init__.py`)**
  - **Description**: Bump version to `0.2.0`, add `__app_name__ = "Phantom Git"`, and register `phantom-git`, `pgit`, and `git-mgr` CLI entrypoints.
  - **Acceptance Criteria**: `phantom-git`, `pgit`, and `git-mgr` invoke `git_manager.cli:app`.
  - **QA Evidence Verification**: Verified via `pip install -e . --no-deps --no-build-isolation` and `test_package_metadata`.

- [x] **TASK-P9-02: CLI Branding & Version Output (`cli.py`)**
  - **Description**: Update Typer application name, help banner, and `--version` output to display Phantom Git while preserving backward-compatible assertions.
  - **Acceptance Criteria**: `--version` outputs `Phantom Git (phantom-git / pgit / git-mgr) version 0.2.0`.
  - **QA Evidence Verification**: Verified via `test_cli_version`, `test_cli_help`, and CLI execution.

- [x] **TASK-P9-03: Documentation & Foundation Test Updates (`README.md`, `tests/test_foundation.py`)**
  - **Description**: Document Phantom Git, 3-pillar CI pre-flight (`pgit check`), and 5-step GitHub Flow (`pgit flow`) in `README.md`, and update metadata tests.
  - **Acceptance Criteria**: `README.md` covers all new workflows and `test_foundation.py` passes.
  - **QA Evidence Verification**: Verified via `pytest tests/test_foundation.py -v`.

---

## Phase 10: 3-Pillar Local CI Pre-Flight Engine & Templates

Focus: Catch **Code Quality & Type Integrity**, **Unit & Component Tests**, and **Production Standalone Build** errors locally before pushing to GitHub.

- [x] **TASK-P10-01: CI Pre-Flight Data Models (`core/models.py`, `core/__init__.py`)**
  - **Description**: Add `CIPillarStatus`, `CIPillarResult`, `CIPreFlightReport`, `PRCheckItem`, and `GitHubFlowStatus` Pydantic models.
  - **Acceptance Criteria**: Models validate and compute `passed` status accurately.
  - **QA Evidence Verification**: Verified via `tests/test_ci_checks.py`.

- [x] **TASK-P10-02: Local 3-Pillar Pre-Flight Runner (`core/ci_checks.py`)**
  - **Description**: Implement `detect_project_type`, `CIPreFlightRunner`, and `run_ci_preflight` supporting Python (`ruff`, `mypy`, `pytest`, `compileall`) and Node.js (`npm run lint`, `tsc --noEmit`, `npm test`, `npm run build`).
  - **Acceptance Criteria**: Runs all 3 pillars locally and treats pytest exit code 5 safely.
  - **QA Evidence Verification**: Verified via `tests/test_ci_checks.py` including real `compileall` syntax checks.

- [x] **TASK-P10-03: CLI `check` Command & Rich Diagnostic Table (`utils/console.py`, `cli.py`)**
  - **Description**: Add `render_ci_preflight_table` and top-level `pgit check` / `pgit flow check` commands with failure output panels.
  - **Acceptance Criteria**: Exits with code 0 when all 3 pillars pass and code 1 on any pillar failure.
  - **QA Evidence Verification**: Verified via `TestCheckCliCommand` in `tests/test_ci_checks.py`.

- [x] **TASK-P10-04: Upgrade Layer 1, Layer 2, `.gitignore`, and Ruleset Templates**
  - **Description**: Structure `layer2/ci.yml.j2` into the 3 explicit jobs with concurrency cancellation, add `pre-push` protection to `layer1/lefthook.yml.j2`, add `.phantom-git/` to `.gitignore`, and add the 3 status check contexts to `ruleset.py`.
  - **Acceptance Criteria**: Existing scaffold tests pass and new jobs/contexts are present.
  - **QA Evidence Verification**: Verified via `pytest tests/test_scaffold.py -v`.

---

## Phase 11: 5-Step GitHub Flow Orchestration Engine (`pgit flow`)

Focus: Enforce isolated feature-branch development, PR checks, failed CI log capture, and Squash-and-Merge via `gh` CLI.

- [x] **TASK-P11-01: GitHub Flow Engine Core (`core/github_flow.py`)**
  - **Description**: Implement `GitHubFlowEngine` with `run_gh`, `start_feature`, `open_pull_request`, `get_pr_checks`, `fetch_ci_failure_logs`, `squash_and_merge`, and `get_flow_status`.
  - **Acceptance Criteria**: Blocks PR creation and squash-merge on `main`, runs pre-flight checks before pushing PRs, saves AI failure diagnostics to `.phantom-git/last-ci-failure.md`, and returns locally to `main` after merge.
  - **QA Evidence Verification**: Verified via `tests/test_github_flow.py`.

- [x] **TASK-P11-02: PR Check Table Formatter (`utils/console.py`)**
  - **Description**: Implement `render_pr_checks_table` with color-coded check states.
  - **Acceptance Criteria**: Cleanly renders `SUCCESS`, `FAILURE`, `PENDING`, and `SKIPPED` states.
  - **QA Evidence Verification**: Verified via `test_flow_checks_and_logs_cli`.

- [x] **TASK-P11-03: Register `pgit flow` Subcommands (`cli.py`)**
  - **Description**: Add `flow start`, `flow check`, `flow pr`, `flow checks`, `flow logs`, and `flow merge`.
  - **Acceptance Criteria**: All 6 subcommands wired and documented in `pgit flow --help`.
  - **QA Evidence Verification**: Verified via `pgit flow --help` and `tests/test_github_flow.py`.

- [x] **TASK-P11-04: Main Branch Commit Protection (`cli.py`)**
  - **Description**: Add `--strict-flow` option to `commit` to block direct commits on `main`/`master`, and emit a GitHub Flow tip warning by default when committing on `main`.
  - **Acceptance Criteria**: `--strict-flow` exits with code 1 on `main` and succeeds on feature branches.
  - **QA Evidence Verification**: Verified via `test_commit_strict_flow_blocks_main_and_allows_feature`.

- [x] **TASK-P11-05: Safe Feature Branch Preservation (`core/github_flow.py`)**
  - **Description**: Auto-stash uncommitted dirty changes (including untracked files) when switching/syncing base branch during `flow start`.
  - **Acceptance Criteria**: Uncommitted files remain intact on the new feature branch.
  - **QA Evidence Verification**: Verified via `test_start_feature_preserves_dirty_files`.

---

## Phase 12: Automated Test Suite, Linting & QA Sign-Off

Focus: Comprehensive unit/CLI verification, editable installation of `phantom-git`/`pgit`/`git-mgr`, and clean linting/formatting.

- [x] **TASK-P12-01: Author `tests/test_ci_checks.py` and `tests/test_github_flow.py`**
  - **Description**: Create full unit and CLI integration test suites covering all 3 CI pillars and all 5 GitHub Flow steps.
  - **Acceptance Criteria**: 100% pass rate on all new tests.
  - **QA Evidence Verification**: Verified via `pytest` (13/13 in `test_ci_checks.py`, 12/12 in `test_github_flow.py`).

- [x] **TASK-P12-02: Editable Package Installation & CLI Entrypoint Verification**
  - **Description**: Reinstall editable package (`pip install -e . --no-deps --no-build-isolation`) and verify `phantom-git`, `pgit`, and `git-mgr`.
  - **Acceptance Criteria**: `phantom-git --version` and `flow --help` succeed with exit code 0.
  - **QA Evidence Verification**: Executed and verified directly in shell.

- [x] **TASK-P12-03: Final Ruff Formatting, Linting & Regression Verification**
  - **Description**: Run `ruff format`, `ruff check`, and `pytest` across verified test suites.
  - **Acceptance Criteria**: Zero ruff errors and 100% passing tests.
  - **QA Evidence Verification**: Verified with exit code 0.

---

## Phase 13: Smart Testing Tiers & Root-Cause CI Classifier

Focus: Scale CI strictness to project maturity (`prototype`, `production`, `strict`) and classify remote CI errors automatically.

- [x] **TASK-P13-01: Smart Testing Tiers (`prototype`, `production`, `strict`)**
  - **Description**: Add `TestingTier` enum and tiered execution in `ci_checks.py` and `--tier` CLI flags on `pgit check` / `pgit flow check`.
  - **Acceptance Criteria**: `prototype` runs non-blocking lint and skips unit tests while enforcing type/build checks; `strict` runs E2E suites.
  - **QA Evidence Verification**: Verified via `TestSmartTestingTiers` in `tests/test_ci_checks.py`.

- [x] **TASK-P13-02: AI CI Failure Root-Cause Classifier (`classify_ci_failure`)**
  - **Description**: Classify failed GitHub Actions logs into `missing_env_or_secret`, `stale_test_failure`, `type_or_lint_error`, or `build_compilation_error` inside `fetch_ci_failure_logs()`.
  - **Acceptance Criteria**: Diagnostic report includes root cause category, extracted env vars/test files, and recommended AI action.
  - **QA Evidence Verification**: Verified via `test_classify_ci_failure_categories` in `tests/test_github_flow.py`.

---

## Phase 14: 3-Branch (`feat/* -> staging -> main`) & Promotion Flow

Focus: Support staging rehearsal branches, dual-branch rulesets, and non-squashed production promotion.

- [x] **TASK-P14-01: `init_branches` & Auto-Targeting `staging`**
  - **Description**: Add `pgit flow init-branches` and `resolve_default_base_branch()` in `GitHubFlowEngine`, updating `flow start`, `flow pr`, and `flow merge` to target `staging` when present.
  - **Acceptance Criteria**: `staging` created off `main` and auto-selected as base branch.
  - **QA Evidence Verification**: Verified via `test_init_branches_and_auto_target_staging`.

- [x] **TASK-P14-02: Production Promotion Flow (`pgit flow promote`)**
  - **Description**: Implement `promote_staging_to_main()` merging `staging -> main` via standard `--merge` commit (preserving branch sync).
  - **Acceptance Criteria**: PR created `staging -> main` and merged using `--merge` without deleting `staging`.
  - **QA Evidence Verification**: Verified via `test_promote_staging_to_main_uses_merge_commit`.

- [x] **TASK-P14-03: Dual-Branch Protection (`main` + `staging`)**
  - **Description**: Protect `main`, `master`, and `staging` in `commit --strict-flow`, `lefthook.yml.j2`, and `ruleset.py`.
  - **Acceptance Criteria**: Direct commits/pushes to `staging` and `main` blocked under strict flow.
  - **QA Evidence Verification**: Verified via `ruleset.py` assertions and `cli.py` inspection.

---

## Phase 15: Custom VPS Multi-Env CI/CD & Server Provisioning

Focus: Automate custom VPS deployments for Staging (`:3001`) and Production (`:3000`) via GitHub Actions SSH/SCP, PM2/Docker, and Nginx/Caddy.

- [x] **TASK-P15-01: Multi-Environment `ci.yml.j2` Pipeline Upgrade**
  - **Description**: Trigger on `[main, staging]`, support `testing_tier`, `build_strategy` (`github` artifact transfer vs `vps` remote build), `deploy_mode` (`pm2` vs `docker`), and conditional `deploy-staging` / `deploy-production` jobs.
  - **Acceptance Criteria**: Templates render clean GitHub Actions YAML with Staging and Production environments.
  - **QA Evidence Verification**: Verified via `TestLayer2Gatekeepers` in `tests/test_scaffold.py`.

- [x] **TASK-P15-02: VPS Provisioning & Proxy Templates (`scaffold vps`)**
  - **Description**: Author `setup-vps.sh.j2`, `ecosystem.config.cjs.j2`, `docker-compose.vps.yml.j2`, `nginx.conf.j2`, and `Caddyfile.j2`, wired to `ScaffoldEngine.scaffold_vps_configs` and `pgit scaffold vps`.
  - **Acceptance Criteria**: Supports PM2/Docker and Nginx/Caddy combinations.
  - **QA Evidence Verification**: Verified via `test_scaffold_vps_configs_pm2_nginx_and_docker_caddy`.

- [x] **TASK-P15-03: `scaffold init` Multi-Env Flags**
  - **Description**: Add `--tier`, `--deploy-mode`, `--build-strategy`, and `--domain` options to `pgit scaffold init`.
  - **Acceptance Criteria**: All options flow cleanly into Layer 2 and `AGENTS.md` templates.
  - **QA Evidence Verification**: Verified via CLI tests and `ScaffoldEngine`.

---

## Phase 16: AI Agent Instructions (`AGENTS.md`), Env Hygiene & Tests

Focus: Deliver `AGENTS.md`, PR templates, Dependabot, `.env.example` sync, and full QA verification.

- [x] **TASK-P16-01: Agent & Repo Hygiene Scaffolding (`scaffold agents`)**
  - **Description**: Create `AGENTS.md.j2`, `pull_request_template.md.j2`, and `dependabot.yml.j2` with optional `.cursorrules` and `CLAUDE.md` sync, plus `!.env.example` in `.gitignore`.
  - **Acceptance Criteria**: All hygiene templates render and integrate into `scaffold_all`.
  - **QA Evidence Verification**: Verified via `test_scaffold_agent_hygiene_with_ide_sync`.

- [x] **TASK-P16-02: Environment Sync & GitHub Secrets CLI (`pgit env`)**
  - **Description**: Implement `env_manager.py` (`sync_env_example`, `set_github_env_secret`) and `pgit env sync` / `pgit env set`.
  - **Acceptance Criteria**: Appends safe empty `KEY=` placeholders without exposing secret values.
  - **QA Evidence Verification**: Verified via `test_env_sync_and_cli_env_set`.

- [x] **TASK-P16-03: Update Documentation (`README.md`) & Version (`0.3.0`)**
  - **Description**: Bump version to `0.3.0` and document 3-branch flow, VPS deployment, testing tiers, and `pgit env`.
  - **Acceptance Criteria**: Package metadata, CLI `--version`, and `README.md` reflect `0.3.0`.
  - **QA Evidence Verification**: Verified via `test_foundation.py` and CLI output.

- [x] **TASK-P16-04: Final Formatting, Linting & Regression Verification**
  - **Description**: Reinstall editable `0.3.0` package and pass `ruff format`, `ruff check`, and `pytest`.
  - **Acceptance Criteria**: Zero lint/format errors and 100% pass across verification suite.
  - **QA Evidence Verification**: Executed and verified with exit code 0.

---

## Phase 17: Textual Dependency & Purple/Neon Theme Foundation

Focus: Add `textual>=0.80.0`, bump version to `0.4.0`, and establish the Phantom Purple & Neon theme across Rich CLI and Textual TCSS.

- [x] **TASK-P17-01: Install Textual & Bump Version to `0.4.0`**
  - **Description**: Add `textual>=0.80.0` and `[tool.setuptools.package-data]` to `pyproject.toml`, bump version in `__init__.py` and `pyproject.toml`, and update `test_foundation.py`.
  - **Acceptance Criteria**: `textual` imports cleanly and `pgit --version` outputs `0.4.0`.
  - **QA Evidence Verification**: Verified via `test_package_metadata` and `pgit --version`.

- [x] **TASK-P17-02: Company Purple & Neon Theme (`console.py` & `tui/theme.tcss`)**
  - **Description**: Extend `CUSTOM_THEME` in `console.py` and author `src/git_manager/tui/theme.tcss` with deep obsidian void (`#0B0716`), royal purple (`#7B2CBF`), neon magenta (`#E040FB`), cyber cyan (`#00F5D4`), and neon green (`#00FF87`).
  - **Acceptance Criteria**: All focus borders, buttons, panels, and modals reflect Purple & Neon styling cleanly.
  - **QA Evidence Verification**: Verified via `tests/test_tui.py`.

---

## Phase 18: Lazygit 5-Panel Workspace & Modal Dialogs

Focus: Implement the mouse- and keyboard-driven Lazygit 5-panel workspace and interactive dialogs.

- [x] **TASK-P18-01: Interactive Modal Dialogs (`tui/modals.py`)**
  - **Description**: Implement `CommitModal` (with AI diff auto-suggestion), `NewBranchModal`, `SnapshotModal`, and `SecretModal`.
  - **Acceptance Criteria**: Modals handle mouse clicks, Escape cancellation, and validation cleanly.
  - **QA Evidence Verification**: Verified via `test_tui_new_branch_and_commit_modals` and `test_tui_ai_commit_snapshot_undo_and_stash`.

- [x] **TASK-P18-02: Lazygit 5-Panel Left Dock & Live Inspector (`tui/app.py`)**
  - **Description**: Implement Status/Flow, Files (click/Space stage toggle), Branches, Commits, and Stash/Safety Net panels alongside live diff/commit inspection and command activity logging.
  - **Acceptance Criteria**: Highlighting files/commits renders diffs; buttons and hotkeys stage, unstage, commit, stash, snapshot, and undo cleanly.
  - **QA Evidence Verification**: Verified via `test_tui_workspace_panels_and_staging_flow` and `test_tui_ai_commit_snapshot_undo_and_stash`.

- [x] **TASK-P18-03: Input/Modal Hotkey Guard (`check_action`)**
  - **Description**: Prevent single-key shortcuts (`space`, `a`, `c`, `n`, etc.) from intercepting typing when `Input` widgets or `ModalScreen` overlays are active.
  - **Acceptance Criteria**: Typing slugs/labels inside Inputs and modals succeeds without triggering app shortcuts.
  - **QA Evidence Verification**: Verified via modal typing in `tests/test_tui.py`.

---

## Phase 19: Flow/CI Center, Archive Hub & VPS/Env TUI Tabs

Focus: Expose GitHub Flow, 3-pillar CI, Multi-Repo Archive scanning, Custom VPS scaffolding, and `.env` hygiene inside unified TUI tabs.

- [x] **TASK-P19-01: `[F2]` Flow / CI Center (`tab-flow`)**
  - **Description**: Add tier selector (`prototype`, `production`, `strict`), 3-pillar DataTable, PR checks DataTable, and mouse buttons for `init-branches`, `start`, `check`, `pr`, `checks`, `logs`, `merge`, and `promote`.
  - **Acceptance Criteria**: Running checks populates `#table-ci-pillars` cleanly.
  - **QA Evidence Verification**: Verified via `test_tui_flow_ci_tab_and_multirepo_hub`.

- [x] **TASK-P19-02: `[F3]` Multi-Repo Archive Hub (`tab-multirepo`)**
  - **Description**: Scan multi-repo directories into `#table-multirepo`, hot-swap the active TUI repository via `#btn-switch-selected-repo`, and run dry-run/bulk syncs.
  - **Acceptance Criteria**: Selecting a discovered repo and clicking Switch updates `app.repo_path` and refreshes the workspace.
  - **QA Evidence Verification**: Verified via `test_tui_flow_ci_tab_and_multirepo_hub`.

- [x] **TASK-P19-03: `[F4]` DevOps, VPS & Env Manager (`tab-devops`) + CLI Wiring**
  - **Description**: Wire 3-layer scaffolding, Custom VPS config generation, `AGENTS.md`/IDE rules generation, `.env.example` sync, GitHub Secrets modal, and `pgit tui` / `pgit ui` CLI commands.
  - **Acceptance Criteria**: All VPS, Agent, and `.env.example` artifacts are created via TUI button clicks; `pgit tui --help` succeeds.
  - **QA Evidence Verification**: Verified via `test_tui_devops_vps_and_env_tab` and `test_cli_tui_and_ui_help`.

---

## Phase 20: Headless Textual Pilot Suite & Documentation

Focus: Deliver full Pilot test automation, update documentation, format/lint code, and reinstall editable `v0.4.0`.

- [x] **TASK-P20-01: Headless Textual Pilot Test Suite (`tests/test_tui.py`)**
  - **Description**: Author async Textual Pilot tests exercising mouse clicks, keybindings, tabs, modals, and repo switching across all 4 TUI tabs.
  - **Acceptance Criteria**: All Pilot tests pass deterministically.
  - **QA Evidence Verification**: Verified via `pytest tests/test_tui.py -v`.

- [x] **TASK-P20-02: Editable Package Reinstall, Documentation & Final QA**
  - **Description**: Update `README.md`, reinstall `phantom-git 0.4.0`, and verify `ruff format`, `ruff check`, and the regression suite.
  - **Acceptance Criteria**: Zero lint/format errors and 100% passing test suite.
  - **QA Evidence Verification**: Executed and verified with exit code 0.

---

## Phase 21: Alternate Screen TUI, Pure Lazygit Layout & GitHub Auth (`v0.5.0`)

Focus: Launch alternate-screen TUI on bare `pgit` with clean `Ctrl+C` exit, implement the 8-container Lazygit layout (5 left + 3 right + bottom keybindings), add `GitHubAuthManager` & `pgit auth`, and configure the `X-Phantom` GitHub account & repository pipelines.

- [x] **TASK-P21-01: Default `pgit` TUI Launch, Alternate Screen Buffer & `Ctrl+C` Termination**
  - **Description**: Configure `cli.py` (`invoke_without_command=True`) to launch `run_tui(inline=False)` on bare `pgit` and bind `ctrl+c` with `priority=True` across app and modals.
  - **Acceptance Criteria**: Bare `pgit` invokes TUI in alternate screen buffer; `Ctrl+C` exits immediately from any state.

- [x] **TASK-P21-02: Pure Single-Screen Lazygit Layout & Real-Time Command Log**
  - **Description**: Redesign `tui/app.py`, `tui/theme.tcss`, and `tui/modals.py` with `[1]`-`[5]` left containers, `[6]` GitHub Repos + `[0]` CI/Flow + `Command log` right containers, bottom keybindings bar, and `GitDriver` command listener hooks.
  - **Acceptance Criteria**: All 8 containers render with Lazygit border titles, `X of Y` item counters, and live command logging.

- [x] **TASK-P21-03: GitHub CLI Discovery, Auth Manager & `pgit auth` Commands**
  - **Description**: Implement `core/github_auth.py` (`find_gh_binary`, `GitHubAuthManager`) and `pgit auth status|login|logout|repos` plus `GitHubAuthModal`.
  - **Acceptance Criteria**: Unit, CLI, and TUI tests pass for auth parsing, token/web login, repo listing, and publishing.

- [x] **TASK-P21-04: Install `gh` CLI, Authenticate `X-Phantom` & Configure Repo Pipelines via Browser MCP**
  - **Description**: Ensure `gh` CLI is installed and authenticated for `X-Phantom`, push `phantom-git`, and configure Actions permissions, Environments (`staging`, `production`), and merge settings via Browser MCP.
  - **Acceptance Criteria**: `pgit auth status` confirms `X-Phantom`, repo is pushed, and CI pipeline checks run cleanly on GitHub.
  - **QA Evidence Verification**: Verified `gh 2.104.0` installed, `pgit auth status` authenticated as `@X-Phantom`, `pgit check` passed all 3 pillars (`ruff`, `265 pytest`, `compileall`), and `X-Phantom/phantom-git` published & configured via `gh` and Browser MCP.

---

## Task Management Rules & Execution Workflow

1. **State Tracking**: Every task starts as `[ ] Pending`. When work begins on a task, update its marker to `[/] In Progress`. Upon satisfying all Acceptance Criteria and gathering QA evidence, update to `[x] Completed`.
2. **Strict Non-Destructive Operations**: No destructive git command (`git reset --hard`, `git clean -fd`, `git rebase --abort`) may be run without a pre-mutation bookmark created by the Safety Net.
3. **Evidence-Based Progression**: A phase cannot be marked complete until all QA Evidence Verification criteria within that phase are executed and recorded.
4. **Git Isolation During Tests**: All unit and integration tests must run inside disposable temporary directories created via `pytest` fixtures; never touch user git repositories during automated test runs.
