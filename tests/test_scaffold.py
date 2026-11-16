"""
Unit and integration tests for the 3-Layer Automation Scaffolder.
Tests dry-run rendering, disk creation, collision protection, AI-tailored .gitignore patterns,
Layer 1 hooks, Layer 2 CI/Security, Layer 3 Release Please CD, and GitHub Ruleset automation.
"""

import json
from pathlib import Path
import pytest

from git_manager.scaffold import (
    ScaffoldEngine,
    TemplateEngine,
    ScaffoldCollisionError,
    generate_ruleset_script,
    get_default_ruleset_payload,
)


class TestScaffoldEngineArchitecture:
    """Tests for ScaffoldEngine configuration, aliases, and dry-run safety."""

    def test_engine_init_and_alias(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        assert engine.target_dir == temp_git_repo.resolve()
        assert engine.templates_dir.exists()
        assert engine.dry_run is False
        assert engine.overwrite is False
        assert engine.raise_on_collision is False
        assert TemplateEngine is ScaffoldEngine

    def test_render_template_dry_run(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo, dry_run=True)
        dest, content, created = engine.render_template(
            template_name="gitignore/python.gitignore.j2",
            dest_path=".gitignore",
            context={"ai_tools": True},
        )
        assert not dest.exists()
        assert created is True
        assert ".gemini/" in content
        assert ".gitignore" in engine.manifest.rendered
        assert dest in engine.manifest.created

    def test_render_template_write(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo, dry_run=False)
        dest, content, created = engine.render_template(
            template_name="gitignore/python.gitignore.j2",
            dest_path=".gitignore",
            context={"ai_tools": True},
        )
        assert dest.exists()
        assert created is True
        written_text = dest.read_text(encoding="utf-8")
        assert written_text == content
        assert ".antigravity/" in written_text
        assert dest in engine.manifest.created


class TestLayer1Gatekeepers:
    """Tests for Layer 1 local gatekeepers (Lefthook & pre-commit)."""

    def test_scaffold_layer1_python(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        paths = engine.scaffold_layer1(project_type="python", linter="ruff")

        assert len(paths) == 2
        lefthook_path = temp_git_repo / "lefthook.yml"
        precommit_path = temp_git_repo / ".pre-commit-config.yaml"

        assert lefthook_path.exists()
        assert precommit_path.exists()

        lefthook_content = lefthook_path.read_text(encoding="utf-8")
        # Staged formatting & linting
        assert "ruff check --fix {staged_files}" in lefthook_content
        assert "ruff format {staged_files}" in lefthook_content
        # Secret scanning regexes
        assert "sk-" in lefthook_content
        assert "gh" in lefthook_content
        assert "AIza" in lefthook_content
        assert "PRIVATE KEY" in lefthook_content
        # Conventional Commits regex
        assert "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert" in lefthook_content

        precommit_content = precommit_path.read_text(encoding="utf-8")
        assert "ruff" in precommit_content
        assert "detect-private-key" in precommit_content
        assert "conventional-commit-msg" in precommit_content

    def test_scaffold_layer1_node(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        paths = engine.scaffold_layer1(project_type="node")

        assert len(paths) == 2
        lefthook_content = (temp_git_repo / "lefthook.yml").read_text(encoding="utf-8")
        assert "eslint --fix" in lefthook_content
        assert "prettier --write" in lefthook_content

    def test_scaffold_layer1_selective(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        # Lefthook only
        paths = engine.scaffold_layer1(use_lefthook=True, use_pre_commit=False)
        assert len(paths) == 1
        assert (temp_git_repo / "lefthook.yml").exists()
        assert not (temp_git_repo / ".pre-commit-config.yaml").exists()


class TestLayer2Gatekeepers:
    """Tests for Layer 2 remote CI and security workflows."""

    def test_scaffold_layer2_defaults(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        paths = engine.scaffold_layer2(project_type="python")

        assert len(paths) == 2
        ci_path = temp_git_repo / ".github" / "workflows" / "ci.yml"
        sec_path = temp_git_repo / ".github" / "workflows" / "security.yml"

        assert ci_path.exists()
        assert sec_path.exists()

        ci_content = ci_path.read_text(encoding="utf-8")
        assert "name: CI" in ci_content
        assert "branches: [main, staging]" in ci_content
        assert "ruff check ." in ci_content
        assert "pytest --cov" in ci_content
        assert "${{ matrix.python-version }}" in ci_content
        assert "deploy-staging:" in ci_content
        assert "deploy-production:" in ci_content

        sec_content = sec_path.read_text(encoding="utf-8")
        assert "name: Security & Secret Scan" in sec_content
        assert "fetch-depth: 0" in sec_content
        assert "gitleaks/gitleaks-action@v2" in sec_content

    def test_scaffold_layer2_multi_os(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        engine.scaffold_layer2(
            project_type="python",
            multi_os=True,
            python_versions=["3.11", "3.12"],
        )

        ci_content = (temp_git_repo / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        assert "ubuntu-latest, windows-latest, macos-latest" in ci_content
        assert '"3.11"' in ci_content
        assert '"3.12"' in ci_content


class TestLayer3ReleasePlease:
    """Tests for Layer 3 automated CD with Google Release Please."""

    def test_scaffold_layer3(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        paths = engine.scaffold_layer3(
            package_name="test-package",
            project_type="python",
            initial_version="0.2.0",
        )

        assert len(paths) == 3
        workflow_path = temp_git_repo / ".github" / "workflows" / "release-please.yml"
        config_path = temp_git_repo / "release-please-config.json"
        manifest_path = temp_git_repo / ".release-please-manifest.json"

        assert workflow_path.exists()
        assert config_path.exists()
        assert manifest_path.exists()

        wf_content = workflow_path.read_text(encoding="utf-8")
        assert "release-type: python" in wf_content
        assert "package-name: test-package" in wf_content
        assert "googleapis/release-please-action@v4" in wf_content

        # Validate JSON formatting and contents
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        assert config_data["packages"]["."]["package-name"] == "test-package"
        assert config_data["packages"]["."]["initial-version"] == "0.2.0"
        assert len(config_data["packages"]["."]["changelog-sections"]) >= 4

        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest_data["."] == "0.2.0"


class TestGitignoreScaffolding:
    """Tests for language and AI-agent .gitignore rules."""

    def test_gitignore_python_with_ai(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        path = engine.scaffold_gitignore(project_type="python", ai_tools=True)

        assert path.exists()
        content = path.read_text(encoding="utf-8")

        # Language patterns
        assert "__pycache__/" in content
        assert ".pytest_cache/" in content
        assert ".venv" in content
        assert ".env" in content
        assert "!.env.example" in content

        # AI agent patterns
        assert ".gemini/" in content
        assert ".antigravity/" in content
        assert "brain/" in content
        assert "scratch/" in content
        assert "transcript*.jsonl" in content
        assert "*.prompt.md" in content

    def test_gitignore_python_without_ai(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        path = engine.scaffold_gitignore(project_type="python", ai_tools=False)

        content = path.read_text(encoding="utf-8")
        assert "__pycache__/" in content
        assert ".gemini/" not in content
        assert "brain/" not in content

    def test_gitignore_node(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        path = engine.scaffold_gitignore(project_type="node", ai_tools=True)

        content = path.read_text(encoding="utf-8")
        assert "node_modules/" in content
        assert ".gemini/" in content


class TestCollisionProtection:
    """Tests for conflict detection, preservation of existing files, and overwrite flags."""

    def test_collision_skip_mode(self, temp_git_repo: Path):
        custom_file = temp_git_repo / "lefthook.yml"
        custom_file.write_text("custom: content", encoding="utf-8")

        engine = ScaffoldEngine(target_dir=temp_git_repo, overwrite=False, raise_on_collision=False)
        paths = engine.scaffold_layer1(use_pre_commit=False)

        assert len(paths) == 1
        # Original file must be preserved intact
        assert custom_file.read_text(encoding="utf-8") == "custom: content"
        assert custom_file in engine.manifest.skipped
        assert custom_file not in engine.manifest.created

    def test_collision_raise_mode(self, temp_git_repo: Path):
        custom_file = temp_git_repo / "lefthook.yml"
        custom_file.write_text("custom: content", encoding="utf-8")

        engine = ScaffoldEngine(target_dir=temp_git_repo, overwrite=False, raise_on_collision=True)
        with pytest.raises(ScaffoldCollisionError) as exc_info:
            engine.scaffold_layer1(use_pre_commit=False)

        assert "already exists" in str(exc_info.value)
        assert issubclass(ScaffoldCollisionError, FileExistsError)
        assert custom_file.read_text(encoding="utf-8") == "custom: content"

    def test_collision_overwrite_mode(self, temp_git_repo: Path):
        custom_file = temp_git_repo / "lefthook.yml"
        custom_file.write_text("custom: content", encoding="utf-8")

        engine = ScaffoldEngine(target_dir=temp_git_repo, overwrite=True)
        engine.scaffold_layer1(use_pre_commit=False)

        # File must be overwritten with new template output
        assert custom_file.read_text(encoding="utf-8") != "custom: content"
        assert "ruff" in custom_file.read_text(encoding="utf-8")
        assert custom_file in engine.manifest.created
        assert custom_file not in engine.manifest.skipped


class TestScaffoldAllOrchestration:
    """Tests for comprehensive 3-layer initialization in a single call."""

    def test_scaffold_all(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        result = engine.scaffold_all(
            project_name="my-cool-agent",
            project_type="python",
        )

        assert "layer1" in result
        assert "layer2" in result
        assert "layer3" in result
        assert "gitignore" in result
        assert "manifest" in result

        # Verify all files exist
        assert (temp_git_repo / "lefthook.yml").exists()
        assert (temp_git_repo / ".pre-commit-config.yaml").exists()
        assert (temp_git_repo / ".github" / "workflows" / "ci.yml").exists()
        assert (temp_git_repo / ".github" / "workflows" / "security.yml").exists()
        assert (temp_git_repo / ".github" / "workflows" / "release-please.yml").exists()
        assert (temp_git_repo / "release-please-config.json").exists()
        assert (temp_git_repo / ".release-please-manifest.json").exists()
        assert (temp_git_repo / ".gitignore").exists()

        manifest_dict = engine.manifest.to_dict()
        assert len(manifest_dict["created"]) >= 8
        assert len(manifest_dict["skipped"]) == 0
        assert len(manifest_dict["rendered"]) >= 8


class TestGitHubRulesetAutomation:
    """Tests for GitHub Branch Ruleset script generation and payload schemas."""

    def test_ruleset_powershell_script(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        script = engine.generate_ruleset_script(repo_full_name="org/repo", script_type="ps1")

        assert "org/repo" in script
        assert "default-protection" in script
        assert "rulesets" in script
        assert "allow_squash_merge=true" in script
        assert "delete_branch_on_merge=true" in script

    def test_ruleset_bash_script(self, temp_git_repo: Path):
        script = generate_ruleset_script(repo_full_name="octocat/Hello-World", script_type="sh")

        assert "#!/usr/bin/env bash" in script
        assert "octocat/Hello-World" in script
        assert "gh api" in script
        assert "default-protection" in script

    def test_ruleset_unsupported_script_type(self):
        with pytest.raises(ValueError):
            generate_ruleset_script(repo_full_name="org/repo", script_type="batch")

    def test_ruleset_payload_schema(self, temp_git_repo: Path):
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        payload_engine = engine.get_ruleset_payload()
        payload = get_default_ruleset_payload()

        assert payload_engine == payload
        assert payload["name"] == "default-protection"
        assert payload["target"] == "branch"
        assert payload["enforcement"] == "active"
        assert "refs/heads/main" in payload["conditions"]["ref_name"]["include"]
        assert "refs/heads/staging" in payload["conditions"]["ref_name"]["include"]

        rule_types = [r["type"] for r in payload["rules"]]
        assert "deletion" in rule_types
        assert "non_fast_forward" in rule_types
        assert "pull_request" in rule_types
        assert "required_status_checks" in rule_types

        # Verify CI context
        status_rule = next(r for r in payload["rules"] if r["type"] == "required_status_checks")
        assert status_rule["parameters"]["required_status_checks"][0]["context"] == "CI"


class TestAgentHygieneAndVPSScaffolding:
    """Tests for AGENTS.md, PR template, Dependabot, and custom VPS deployment configs."""

    def test_scaffold_agent_hygiene_with_ide_sync(self, temp_git_repo: Path) -> None:
        engine = ScaffoldEngine(target_dir=temp_git_repo)
        paths = engine.scaffold_agent_hygiene(
            project_name="phantom-webapp",
            project_type="node",
            testing_tier="prototype",
            deploy_mode="pm2",
            domain="phantomlabs.dev",
            sync_cursor_claude=True,
        )
        assert len(paths) == 5
        assert (temp_git_repo / "AGENTS.md").exists()
        assert (temp_git_repo / ".github" / "pull_request_template.md").exists()
        assert (temp_git_repo / ".github" / "dependabot.yml").exists()
        assert (temp_git_repo / ".cursorrules").exists()
        assert (temp_git_repo / "CLAUDE.md").exists()

        agents_txt = (temp_git_repo / "AGENTS.md").read_text(encoding="utf-8")
        assert "phantom-webapp" in agents_txt
        assert "pgit check --tier prototype" in agents_txt
        assert "staging.phantomlabs.dev" in agents_txt

        dep_txt = (temp_git_repo / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        assert 'package-ecosystem: "npm"' in dep_txt

    def test_scaffold_vps_configs_pm2_nginx_and_docker_caddy(self, tmp_path: Path) -> None:
        pm2_dir = tmp_path / "pm2_repo"
        pm2_dir.mkdir()
        eng1 = ScaffoldEngine(target_dir=pm2_dir)
        p1 = eng1.scaffold_vps_configs(
            app_name="my-saas",
            project_type="node",
            deploy_mode="pm2",
            proxy_type="nginx",
            domain="mysaas.io",
        )
        assert len(p1) == 3
        assert (pm2_dir / "deploy" / "vps" / "setup-vps.sh").exists()
        assert (pm2_dir / "deploy" / "vps" / "ecosystem.config.cjs").exists()
        assert (pm2_dir / "deploy" / "vps" / "nginx.conf").exists()
        eco = (pm2_dir / "deploy" / "vps" / "ecosystem.config.cjs").read_text(encoding="utf-8")
        assert "my-saas-staging" in eco
        assert "3001" in eco
        assert "my-saas-prod" in eco
        assert "3000" in eco
        nginx = (pm2_dir / "deploy" / "vps" / "nginx.conf").read_text(encoding="utf-8")
        assert "server_name mysaas.io;" in nginx
        assert "server_name staging.mysaas.io;" in nginx

        docker_dir = tmp_path / "docker_repo"
        docker_dir.mkdir()
        eng2 = ScaffoldEngine(target_dir=docker_dir)
        p2 = eng2.scaffold_vps_configs(
            app_name="api-core",
            project_type="python",
            deploy_mode="docker",
            proxy_type="caddy",
            domain="apicore.dev",
        )
        assert len(p2) == 3
        assert (docker_dir / "deploy" / "vps" / "docker-compose.vps.yml").exists()
        assert (docker_dir / "deploy" / "vps" / "Caddyfile").exists()
        caddy = (docker_dir / "deploy" / "vps" / "Caddyfile").read_text(encoding="utf-8")
        assert "apicore.dev" in caddy
        assert "staging.apicore.dev" in caddy
