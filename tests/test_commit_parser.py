"""
Comprehensive unit and integration tests for Conventional Commits engine,
SemVer calculation, version computation, and staged diff commit suggestion.
"""

from pathlib import Path
import pytest

from git_manager.core.commit_parser import (
    calculate_semver_bump,
    compute_next_version,
    format_commit_message,
    parse_commit_message,
    suggest_commit_message,
    suggest_conventional_commit,
)
from git_manager.core.git_driver import GitDriver
from git_manager.core.models import ConventionalCommit, SemVerBump


class TestParseCommitMessage:
    """Tests for parse_commit_message."""

    def test_parse_simple_header(self) -> None:
        msg = "feat: add user login"
        commit = parse_commit_message(msg)
        assert commit.type == "feat"
        assert commit.scope is None
        assert commit.is_breaking is False
        assert commit.subject == "add user login"
        assert commit.body is None
        assert commit.breaking_description is None
        assert commit.footers == {}

    def test_parse_scoped_header(self) -> None:
        msg = "fix(auth): handle expired jwt token"
        commit = parse_commit_message(msg)
        assert commit.type == "fix"
        assert commit.scope == "auth"
        assert commit.is_breaking is False
        assert commit.subject == "handle expired jwt token"

    def test_parse_breaking_change_exclamation(self) -> None:
        msg = "feat(api)!: migrate to rest v2 endpoints"
        commit = parse_commit_message(msg)
        assert commit.type == "feat"
        assert commit.scope == "api"
        assert commit.is_breaking is True
        assert commit.subject == "migrate to rest v2 endpoints"

    def test_parse_breaking_without_scope(self) -> None:
        msg = "refactor!: overhaul database connection pooling"
        commit = parse_commit_message(msg)
        assert commit.type == "refactor"
        assert commit.scope is None
        assert commit.is_breaking is True
        assert commit.subject == "overhaul database connection pooling"

    def test_parse_multiline_body(self) -> None:
        msg = (
            "feat(cache): implement redis client wrapper\n"
            "\n"
            "This provides distributed caching across all worker processes.\n"
            "Supports TTL expiration and clustering."
        )
        commit = parse_commit_message(msg)
        assert commit.type == "feat"
        assert commit.scope == "cache"
        assert commit.subject == "implement redis client wrapper"
        assert commit.body is not None
        assert "distributed caching" in commit.body
        assert "TTL expiration" in commit.body

    def test_parse_footers_and_breaking_description(self) -> None:
        msg = (
            "fix(core): prevent race condition during worker shutdown\n"
            "\n"
            "Drain active requests before terminating worker processes.\n"
            "\n"
            "BREAKING CHANGE: synchronous shutdown signal is no longer supported\n"
            "Refs: #456\n"
            "Signed-off-by: Dev <dev@example.com>"
        )
        commit = parse_commit_message(msg)
        assert commit.type == "fix"
        assert commit.scope == "core"
        assert commit.is_breaking is True
        assert commit.breaking_description == "synchronous shutdown signal is no longer supported"
        assert commit.footers.get("Refs") == "#456"
        assert commit.footers.get("Signed-off-by") == "Dev <dev@example.com>"

    @pytest.mark.parametrize(
        ("invalid_msg", "expected_match"),
        [
            ("", "cannot be empty"),
            ("   ", "cannot be empty"),
            ("random commit without type", "does not follow Conventional Commits"),
            ("feat: Add login with capital", "must start with a lowercase letter"),
            ("feat: add login with trailing period.", "must not end with a period"),
            ("unknown(scope): invalid type name", "does not follow Conventional Commits"),
        ],
    )
    def test_parse_invalid_messages_raise_error(
        self, invalid_msg: str, expected_match: str
    ) -> None:
        with pytest.raises(ValueError, match=expected_match):
            parse_commit_message(invalid_msg)


class TestFormatCommitMessage:
    """Tests for format_commit_message."""

    def test_format_roundtrip_simple(self) -> None:
        commit = ConventionalCommit(
            type="feat",
            scope="auth",
            subject="add oauth2 provider",
        )
        formatted = format_commit_message(commit)
        assert formatted == "feat(auth): add oauth2 provider"

        # Verify it can be parsed back
        reparsed = parse_commit_message(formatted)
        assert reparsed.type == "feat"
        assert reparsed.scope == "auth"
        assert reparsed.subject == "add oauth2 provider"

    def test_format_roundtrip_breaking(self) -> None:
        commit = ConventionalCommit(
            type="fix",
            scope="api",
            is_breaking=True,
            subject="drop legacy v1 payload schema",
            breaking_description="v1 payload schema is deprecated",
            footers={"Closes": "#101"},
        )
        formatted = format_commit_message(commit)
        assert "fix(api)!: drop legacy v1 payload schema" in formatted
        assert "BREAKING CHANGE: v1 payload schema is deprecated" in formatted
        assert "Closes: #101" in formatted


class TestSemVerBumpCalculation:
    """Tests for calculate_semver_bump and compute_next_version."""

    def test_bump_major_from_exclamation(self) -> None:
        commits = [
            "feat: add feature 1",
            "feat(api)!: breaking change endpoint",
            "fix: bugfix",
        ]
        bump = calculate_semver_bump(commits)
        assert bump == SemVerBump.MAJOR

    def test_bump_major_from_breaking_footer(self) -> None:
        commit = ConventionalCommit(
            type="fix",
            subject="update schema",
            breaking_description="database field renamed",
        )
        bump = calculate_semver_bump([commit])
        assert bump == SemVerBump.MAJOR

    def test_bump_minor_from_feat(self) -> None:
        commits = [
            "feat: new awesome feature",
            "fix: small patch",
            "docs: update installation",
        ]
        bump = calculate_semver_bump(commits)
        assert bump == SemVerBump.MINOR

    def test_bump_patch_from_fix(self) -> None:
        commits = [
            "fix: resolve timeout",
            "docs: fix typo",
            "chore: bump dependencies",
        ]
        bump = calculate_semver_bump(commits)
        assert bump == SemVerBump.PATCH

    def test_bump_patch_from_perf_and_refactor(self) -> None:
        assert calculate_semver_bump(["perf: optimize query"]) == SemVerBump.PATCH
        assert calculate_semver_bump(["refactor: extract class"]) == SemVerBump.PATCH

    def test_bump_none_for_maintenance_only(self) -> None:
        commits = [
            "docs: update readme",
            "chore: clean temp files",
            "ci: add coverage report",
            "test: add unit test",
        ]
        bump = calculate_semver_bump(commits)
        assert bump == SemVerBump.NONE

    def test_bump_empty_commits(self) -> None:
        assert calculate_semver_bump([]) == SemVerBump.NONE

    @pytest.mark.parametrize(
        ("current", "bump", "expected"),
        [
            ("1.0.0", SemVerBump.MAJOR, "2.0.0"),
            ("1.2.3", SemVerBump.MINOR, "1.3.0"),
            ("1.2.3", SemVerBump.PATCH, "1.2.4"),
            ("1.2.3", SemVerBump.NONE, "1.2.3"),
            ("v2.5.1", SemVerBump.MAJOR, "v3.0.0"),
            ("v0.9.4", SemVerBump.MINOR, "v0.10.0"),
            ("v1.0.0", SemVerBump.PATCH, "v1.0.1"),
        ],
    )
    def test_compute_next_version(self, current: str, bump: SemVerBump, expected: str) -> None:
        result = compute_next_version(current, bump)
        assert result == expected

    def test_compute_next_version_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid semantic version string"):
            compute_next_version("invalid-semver", SemVerBump.PATCH)


class TestDiffAnalyzerAndSuggester:
    """Integration tests for staged diff conventional commit suggestion."""

    def test_suggest_no_staged_changes_raises_error(self, temp_git_repo: Path) -> None:
        driver = GitDriver(temp_git_repo)
        with pytest.raises(ValueError, match="No staged changes found"):
            suggest_conventional_commit(driver)

    def test_suggest_docs_commit(self, temp_git_repo: Path) -> None:
        doc_file = temp_git_repo / "docs" / "architecture.md"
        doc_file.parent.mkdir(parents=True, exist_ok=True)
        doc_file.write_text("# Architecture Guide", encoding="utf-8")

        driver = GitDriver(temp_git_repo)
        driver.stage(["docs/architecture.md"])

        suggestion = suggest_conventional_commit(driver)
        assert suggestion.type == "docs"
        assert suggestion.subject.startswith("update")
        # Ensure subject starts with lowercase and has no trailing period
        assert suggestion.subject[0].islower()
        assert not suggestion.subject.endswith(".")

    def test_suggest_tests_commit(self, temp_git_repo: Path) -> None:
        test_file = temp_git_repo / "tests" / "test_auth.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_dummy(): pass", encoding="utf-8")

        driver = GitDriver(temp_git_repo)
        driver.stage(["tests/test_auth.py"])

        suggestion = suggest_conventional_commit(driver)
        assert suggestion.type == "test"
        assert suggestion.subject[0].islower()
        assert not suggestion.subject.endswith(".")

    def test_suggest_ci_commit(self, temp_git_repo: Path) -> None:
        ci_file = temp_git_repo / ".github" / "workflows" / "ci.yml"
        ci_file.parent.mkdir(parents=True, exist_ok=True)
        ci_file.write_text("name: CI\non: push", encoding="utf-8")

        driver = GitDriver(temp_git_repo)
        driver.stage([".github/workflows/ci.yml"])

        suggestion = suggest_conventional_commit(driver)
        assert suggestion.type == "ci"
        assert suggestion.subject[0].islower()
        assert not suggestion.subject.endswith(".")

    def test_suggest_chore_commit(self, temp_git_repo: Path) -> None:
        toml_file = temp_git_repo / "pyproject.toml"
        toml_file.write_text("[project]\nname = 'test-pkg'", encoding="utf-8")

        driver = GitDriver(temp_git_repo)
        driver.stage(["pyproject.toml"])

        suggestion = suggest_conventional_commit(driver)
        assert suggestion.type == "chore"
        assert suggestion.subject[0].islower()
        assert not suggestion.subject.endswith(".")

    def test_suggest_feat_with_scope(self, temp_git_repo: Path) -> None:
        code_file = temp_git_repo / "src" / "git_manager" / "core" / "new_feature.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("class Feature:\n    pass\n", encoding="utf-8")

        driver = GitDriver(temp_git_repo)
        driver.stage(["src/git_manager/core/new_feature.py"])

        suggestion = suggest_conventional_commit(driver)
        assert suggestion.type == "feat"
        assert suggestion.scope == "core"
        assert suggestion.subject[0].islower()
        assert not suggestion.subject.endswith(".")

    def test_suggest_fix_commit(self, temp_git_repo: Path) -> None:
        code_file = temp_git_repo / "src" / "git_manager" / "core" / "bugfix.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text(
            "# fix: resolve unexpected exception\ndef patch(): pass", encoding="utf-8"
        )

        driver = GitDriver(temp_git_repo)
        driver.stage(["src/git_manager/core/bugfix.py"])

        suggestion = suggest_conventional_commit(driver)
        assert suggestion.type == "fix"
        assert suggestion.subject[0].islower()
        assert not suggestion.subject.endswith(".")

    def test_suggest_commit_message_helper(self, temp_git_repo: Path) -> None:
        readme = temp_git_repo / "README.md"
        readme.write_text("# Updated Documentation", encoding="utf-8")

        driver = GitDriver(temp_git_repo)
        driver.stage(["README.md"])

        suggestion = suggest_commit_message(temp_git_repo)
        assert suggestion.type == "docs"
        assert suggestion.subject[0].islower()
