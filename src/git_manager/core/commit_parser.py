"""
Conventional Commits 1.0.0 parser, validator, diff analyzer, and SemVer engine.
Enforces standard commit specifications, generates automated suggestions from staged diffs,
and deterministically calculates semantic version bumps.
"""

from __future__ import annotations

import re
from pathlib import Path

from git_manager.core.git_driver import GitDriver
from git_manager.core.models import ConventionalCommit, SemVerBump

# Conventional Commits 1.0.0 header regex:
# type(scope)!: subject
COMMIT_HEADER_REGEX = re.compile(
    r"^(?P<type>feat|fix|chore|docs|refactor|ci|test|perf|style|build)"
    r"(?:\((?P<scope>[a-zA-Z0-9_\-\.\/]+)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<description>.+)$"
)

FOOTER_REGEX = re.compile(
    r"^(?P<token>BREAKING CHANGE|BREAKING-CHANGE|[a-zA-Z0-9-]+)(?::\s*|\s+#)(?P<val>.+)$"
)

DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc", ".markdown"}
DOC_STEMS = {"readme", "license", "contributing", "changelog", "authors", "code_of_conduct"}
CI_PATHS = {
    ".github/",
    ".gitlab-ci.yml",
    ".pre-commit-config.yaml",
    "lefthook.yml",
    ".circleci/",
    "dockerfile",
    "docker-compose",
}
CONFIG_FILES = {
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "requirements.txt",
    "cargo.toml",
    "setup.cfg",
    "setup.py",
    ".gitignore",
    ".editorconfig",
    "tsconfig.json",
}
TEST_PATTERNS = {"tests/", "test_", "_test.py", ".spec.", ".test.", "conftest.py"}


def parse_commit_message(msg: str) -> ConventionalCommit:
    """
    Parse and validate a Conventional Commits 1.0.0 message.

    Args:
        msg: Raw commit message string (single-line or multi-line)

    Returns:
        Structured ConventionalCommit model

    Raises:
        ValueError: If commit message violates format standards (casing, trailing period, invalid type)
    """
    if not isinstance(msg, str) or not msg.strip():
        raise ValueError("Commit message cannot be empty.")

    lines = msg.strip().splitlines()
    header = lines[0].strip()

    match = COMMIT_HEADER_REGEX.match(header)
    if not match:
        raise ValueError(
            f"Commit message header does not follow Conventional Commits format: '{header}'\n"
            "Expected format: <type>(<scope>): <subject> or <type>: <subject>"
        )

    commit_type = match.group("type")
    scope = match.group("scope")
    is_breaking = match.group("breaking") == "!"
    subject = match.group("description").strip()

    # Hygiene rule: subject must start with lowercase letter or number, never uppercase
    if subject and subject[0].isupper():
        raise ValueError(f"Commit subject must start with a lowercase letter: '{subject}'")

    # Hygiene rule: subject must not end with a trailing period
    if subject.endswith("."):
        raise ValueError(f"Commit subject must not end with a period: '{subject}'")

    body_paragraphs: list[str] = []
    breaking_description: str | None = None
    footers: dict[str, str] = {}

    if len(lines) > 1:
        # Process remaining lines after header
        raw_body_lines = lines[1:]
        # Group lines into blocks separated by blank lines
        blocks: list[list[str]] = []
        current_block: list[str] = []

        for line in raw_body_lines:
            if not line.strip():
                if current_block:
                    blocks.append(current_block)
                    current_block = []
            else:
                current_block.append(line.strip())
        if current_block:
            blocks.append(current_block)

        # Distinguish between body blocks and footer blocks
        for block in blocks:
            # Check if block is composed of footers
            is_footer_block = False
            first_line = block[0]
            footer_match = FOOTER_REGEX.match(first_line)

            if footer_match:
                is_footer_block = True
                curr_key = footer_match.group("token")
                curr_val = footer_match.group("val").strip()

                if curr_key in ("BREAKING CHANGE", "BREAKING-CHANGE"):
                    is_breaking = True
                    breaking_description = curr_val
                else:
                    footers[curr_key] = curr_val

                # Process any additional lines in this footer block
                for sub_line in block[1:]:
                    sub_match = FOOTER_REGEX.match(sub_line)
                    if sub_match:
                        k = sub_match.group("token")
                        v = sub_match.group("val").strip()
                        if k in ("BREAKING CHANGE", "BREAKING-CHANGE"):
                            is_breaking = True
                            breaking_description = v
                        else:
                            footers[k] = v
                    else:
                        # Continuation line for the previous footer
                        if breaking_description and curr_key in (
                            "BREAKING CHANGE",
                            "BREAKING-CHANGE",
                        ):
                            breaking_description += f" {sub_line}"
                        elif curr_key in footers:
                            footers[curr_key] += f" {sub_line}"

            if not is_footer_block:
                # Ordinary body block
                body_paragraphs.append("\n".join(block))

    body = "\n\n".join(body_paragraphs) if body_paragraphs else None

    return ConventionalCommit(
        type=commit_type,
        scope=scope,
        is_breaking=is_breaking,
        subject=subject,
        body=body,
        breaking_description=breaking_description,
        footers=footers,
    )


def format_commit_message(commit: ConventionalCommit) -> str:
    """
    Format a ConventionalCommit model into a standardized commit message string.

    Args:
        commit: ConventionalCommit model instance

    Returns:
        Formatted commit message string
    """
    return commit.format_message()


def calculate_semver_bump(
    commits: list[ConventionalCommit] | list[str],
) -> SemVerBump:
    """
    Calculate semantic version increment level (MAJOR, MINOR, PATCH, or NONE)
    from a collection of Conventional Commits.

    Rules:
    - Any breaking change ('!' or 'BREAKING CHANGE:') -> MAJOR
    - Any 'feat' commit -> MINOR
    - Any 'fix', 'perf', or 'refactor' commit -> PATCH
    - Non-code or maintenance changes ('chore', 'docs', 'ci', 'test', 'style', 'build') -> NONE

    Args:
        commits: List of ConventionalCommit instances or raw commit strings

    Returns:
        SemVerBump enum member
    """
    if not commits:
        return SemVerBump.NONE

    parsed: list[ConventionalCommit] = []
    for item in commits:
        if isinstance(item, ConventionalCommit):
            parsed.append(item)
        elif isinstance(item, str):
            try:
                parsed.append(parse_commit_message(item))
            except ValueError:
                # Fallback: simple regex scan for breaking markers and commit type
                match = COMMIT_HEADER_REGEX.match(item.strip().splitlines()[0])
                if match:
                    parsed.append(
                        ConventionalCommit(
                            type=match.group("type"),
                            scope=match.group("scope"),
                            is_breaking=(
                                match.group("breaking") == "!" or "BREAKING CHANGE:" in item
                            ),
                            subject=match.group("description"),
                        )
                    )

    # 1. Any breaking change triggers MAJOR bump
    for c in parsed:
        if c.is_breaking or c.breaking_description:
            return SemVerBump.MAJOR

    # 2. Any feature triggers MINOR bump
    for c in parsed:
        if c.type.lower() == "feat":
            return SemVerBump.MINOR

    # 3. Fixes, performance improvements, and refactors trigger PATCH bump
    for c in parsed:
        if c.type.lower() in ("fix", "perf", "refactor"):
            return SemVerBump.PATCH

    return SemVerBump.NONE


def compute_next_version(current_version: str, bump: SemVerBump) -> str:
    """
    Compute the next semantic version string given the current version and bump level.

    Args:
        current_version: SemVer string (e.g. '1.2.3' or 'v1.2.3')
        bump: SemVerBump enum (MAJOR, MINOR, PATCH, NONE)

    Returns:
        Updated SemVer string (e.g. '1.3.0')
    """
    raw_ver = current_version.strip()
    has_v = raw_ver.startswith("v")
    clean_ver = raw_ver.lstrip("v")

    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", clean_ver)
    if not match:
        raise ValueError(f"Invalid semantic version string: '{current_version}'")

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))

    if bump == SemVerBump.MAJOR:
        major += 1
        minor = 0
        patch = 0
    elif bump == SemVerBump.MINOR:
        minor += 1
        patch = 0
    elif bump == SemVerBump.PATCH:
        patch += 1
    elif bump == SemVerBump.NONE:
        pass

    new_ver = f"{major}.{minor}.{patch}"
    return f"v{new_ver}" if has_v else new_ver


def suggest_conventional_commit(driver: GitDriver) -> ConventionalCommit:
    """
    Inspect staged repository changes and heuristically suggest a Conventional Commit.

    Analyzes:
    - 'git diff --cached --name-status' for file paths and change types
    - 'git diff --cached' for keywords and modification context
    - Common directory paths for scope extraction

    Args:
        driver: GitDriver connected to the repository

    Returns:
        A drafted ConventionalCommit candidate

    Raises:
        ValueError: If no staged changes exist
    """
    diff_name_res = driver.run(["diff", "--cached", "--name-status"], check=True)
    lines = [ln.strip() for ln in diff_name_res.stdout.splitlines() if ln.strip()]

    if not lines:
        raise ValueError("No staged changes found to analyze for commit suggestion.")

    staged_items: list[tuple[str, str]] = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) >= 2:
            status_code = parts[0]
            # In case of renames (R100 old new), target path is parts[2] or parts[1]
            path_str = parts[-1]
            staged_items.append((status_code, path_str))

    paths = [item[1] for item in staged_items]

    # Heuristic categorization flags
    all_docs = True
    all_tests = True
    all_ci = True
    all_config = True

    for p in paths:
        p_lower = p.lower().replace("\\", "/")
        path_obj = Path(p_lower)

        is_doc = (
            path_obj.suffix in DOC_EXTENSIONS
            or "docs/" in p_lower
            or any(stem in path_obj.stem for stem in DOC_STEMS)
        )
        if not is_doc:
            all_docs = False

        is_test = any(pat in p_lower for pat in TEST_PATTERNS)
        if not is_test:
            all_tests = False

        is_ci = any(pat in p_lower for pat in CI_PATHS)
        if not is_ci:
            all_ci = False

        is_config = path_obj.name in CONFIG_FILES or any(
            cfg in p_lower for cfg in (".github", ".vscode", "docker")
        )
        if not is_config:
            all_config = False

    # Extract scope from directory hierarchy
    scope: str | None = None
    candidate_scopes: list[str] = []

    for p in paths:
        norm_p = p.replace("\\", "/")
        parts = norm_p.split("/")
        if len(parts) > 1:
            if parts[0] == "src" and len(parts) > 2:
                # e.g., src/git_manager/core/... -> core
                candidate_scopes.append(parts[2])
            elif parts[0] == "tests":
                candidate_scopes.append("tests")
            elif parts[0] == "docs":
                candidate_scopes.append("docs")
            else:
                candidate_scopes.append(parts[0])

    if candidate_scopes:
        # Select most frequent candidate scope
        scope = max(set(candidate_scopes), key=candidate_scopes.count)

    # Determine commit type and subject
    if all_docs:
        commit_type = "docs"
        subject = f"update {scope} documentation" if scope else "update documentation"
    elif all_tests:
        commit_type = "test"
        subject = f"add tests for {scope}" if scope else "update test suite"
    elif all_ci:
        commit_type = "ci"
        subject = "update continuous integration workflows"
    elif all_config:
        commit_type = "chore"
        subject = "update configuration and dependencies"
    else:
        # Check diff content for bugfix keywords
        diff_full = driver.run(["diff", "--cached"], check=False)
        diff_text = diff_full.stdout.lower()
        bug_keywords = ("fix", "bug", "patch", "issue", "resolve", "defect", "repair", "error")
        is_fix = any(kw in diff_text for kw in bug_keywords) or any(
            any(kw in p.lower() for kw in bug_keywords) for p in paths
        )

        if is_fix:
            commit_type = "fix"
            subject = f"resolve issue in {scope}" if scope else "resolve issue"
        else:
            commit_type = "feat"
            subject = f"implement updates in {scope}" if scope else "implement updates"

    return ConventionalCommit(
        type=commit_type,
        scope=scope,
        is_breaking=False,
        subject=subject,
    )


def suggest_commit_message(
    repo_path: Path | str | None = None,
) -> ConventionalCommit:
    """
    Convenience function matching TASK-P4-04:
    Analyzes staged diff in repo_path and returns suggested ConventionalCommit.
    """
    driver = GitDriver(repo_path)
    return suggest_conventional_commit(driver)
