"""
3-Layer Automation Scaffolding Engine for git-mgr.
Powered by Jinja2 to orchestrate Layer 1 (Local Git hooks), Layer 2 (Remote CI),
Layer 3 (Release CD), and AI-tailored .gitignore environments.
"""

from pathlib import Path
from typing import Any
import jinja2
from pydantic import BaseModel, Field

from git_manager.scaffold.ruleset import generate_ruleset_script, get_default_ruleset_payload


class ScaffoldCollisionError(FileExistsError):
    """Raised when scaffolding encounters an existing file and overwrite is False."""

    pass


class ScaffoldManifest(BaseModel):
    """Tracks files created, skipped, and rendered during scaffolding execution."""

    created: list[Path] = Field(default_factory=list)
    skipped: list[Path] = Field(default_factory=list)
    rendered: dict[str, str] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to serializable dictionary."""
        return {
            "created": [str(p) for p in self.created],
            "skipped": [str(p) for p in self.skipped],
            "rendered": self.rendered,
        }


class ScaffoldEngine:
    """
    Core scaffolding and template engine.

    Orchestrates Jinja2 template rendering across Layer 1, Layer 2, Layer 3,
    and repository configuration files with conflict detection and dry-run safety.
    """

    def __init__(
        self,
        target_dir: Path | str,
        templates_dir: Path | str | None = None,
        dry_run: bool = False,
        overwrite: bool = False,
        raise_on_collision: bool = False,
    ):
        """
        Initialize the ScaffoldEngine.

        Args:
            target_dir: Root directory of the repository to scaffold into.
            templates_dir: Optional custom path to templates folder.
            dry_run: If True, renders templates in memory without writing to disk.
            overwrite: If True, overwrites existing files.
            raise_on_collision: If True and overwrite is False, raises ScaffoldCollisionError
                                when a destination file already exists.
        """
        self.target_dir = Path(target_dir).resolve()
        if templates_dir is None:
            self.templates_dir = (Path(__file__).parent / "templates").resolve()
        else:
            self.templates_dir = Path(templates_dir).resolve()

        self.dry_run = dry_run
        self.overwrite = overwrite
        self.raise_on_collision = raise_on_collision
        self.manifest = ScaffoldManifest()

        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)),
            autoescape=False,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def get_template(self, template_name: str) -> jinja2.Template:
        """Load a Jinja2 template by relative path."""
        # Normalize template name to forward slashes for Jinja2
        norm_name = str(template_name).replace("\\", "/")
        return self._env.get_template(norm_name)

    def render_template(
        self,
        template_name: str,
        dest_path: Path | str,
        context: dict[str, Any] | None = None,
        overwrite: bool | None = None,
        raise_on_collision: bool | None = None,
    ) -> tuple[Path, str, bool]:
        """
        Render a Jinja2 template and write (or dry-run) to the destination.

        Args:
            template_name: Relative template path (e.g. 'layer1/lefthook.yml.j2').
            dest_path: Destination path relative to target_dir.
            context: Variables passed to the Jinja2 template.
            overwrite: Overwrite override for this specific file.
            raise_on_collision: Collision error override for this specific file.

        Returns:
            Tuple of (destination Path, rendered content string, written_or_created bool).
        """
        ctx = context or {}
        tmpl = self.get_template(template_name)
        content = tmpl.render(**ctx)

        rel_dest = Path(dest_path)
        if rel_dest.is_absolute():
            target_file = rel_dest.resolve()
            try:
                rel_key = str(target_file.relative_to(self.target_dir)).replace("\\", "/")
            except ValueError:
                rel_key = str(target_file).replace("\\", "/")
        else:
            target_file = (self.target_dir / rel_dest).resolve()
            rel_key = str(rel_dest).replace("\\", "/")

        eff_overwrite = self.overwrite if overwrite is None else overwrite
        eff_raise = self.raise_on_collision if raise_on_collision is None else raise_on_collision

        # Always record rendered output
        self.manifest.rendered[rel_key] = content

        if target_file.exists() and not eff_overwrite:
            if eff_raise:
                raise ScaffoldCollisionError(
                    f"Target file already exists: '{target_file}'. Pass overwrite=True to replace it."
                )
            if target_file not in self.manifest.skipped:
                self.manifest.skipped.append(target_file)
            return target_file, content, False

        if not self.dry_run:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content, encoding="utf-8", newline="\n")

        if target_file not in self.manifest.created:
            self.manifest.created.append(target_file)

        return target_file, content, True

    def scaffold_layer1(
        self,
        project_type: str = "python",
        linter: str = "ruff",
        use_lefthook: bool = True,
        use_pre_commit: bool = True,
        raise_on_collision: bool | None = None,
    ) -> list[Path]:
        """
        Scaffold Layer 1 local gatekeepers (Lefthook and/or pre-commit).

        Configured with:
        - Staged file linting and formatting (ruff for Python, eslint/prettier for Node).
        - Regex secret scanning (OpenAI sk-, GitHub tokens, Google AIza, AWS keys, Private keys).
        - Conventional Commits commit-msg validation.

        Args:
            project_type: 'python' or 'node'.
            linter: 'ruff' (Python) or custom.
            use_lefthook: Whether to scaffold lefthook.yml.
            use_pre_commit: Whether to scaffold .pre-commit-config.yaml.
            raise_on_collision: Override collision behavior.

        Returns:
            List of Path objects for the layer's target files.
        """
        results: list[Path] = []
        context = {
            "project_type": project_type.lower().strip(),
            "linter": linter,
        }

        if use_lefthook:
            path, _, _ = self.render_template(
                template_name="layer1/lefthook.yml.j2",
                dest_path="lefthook.yml",
                context=context,
                raise_on_collision=raise_on_collision,
            )
            results.append(path)

        if use_pre_commit:
            path, _, _ = self.render_template(
                template_name="layer1/pre-commit-config.yaml.j2",
                dest_path=".pre-commit-config.yaml",
                context=context,
                raise_on_collision=raise_on_collision,
            )
            results.append(path)

        return results

    def scaffold_layer2(
        self,
        project_type: str = "python",
        multi_os: bool = False,
        python_versions: list[str] | None = None,
        testing_tier: str = "production",
        enable_vps_deploy: bool = True,
        deploy_mode: str = "pm2",
        build_strategy: str = "github",
        domain: str = "yourdomain.com",
        app_name: str = "app",
        raise_on_collision: bool | None = None,
    ) -> list[Path]:
        """
        Scaffold Layer 2 remote CI, security, and multi-environment VPS deployment workflows.

        Configured with:
        - .github/workflows/ci.yml: 3-pillar validation + optional staging/main VPS deploy jobs.
        - .github/workflows/security.yml: Gitleaks full history secret scanner on PRs/pushes.
        """
        results: list[Path] = []
        context = {
            "project_type": project_type.lower().strip(),
            "multi_os": multi_os,
            "python_versions": python_versions or ["3.10", "3.11", "3.12"],
            "testing_tier": testing_tier.lower().strip(),
            "enable_vps_deploy": enable_vps_deploy,
            "deploy_mode": deploy_mode.lower().strip(),
            "build_strategy": build_strategy.lower().strip(),
            "domain": domain.strip() or "yourdomain.com",
            "app_name": app_name.strip() or "app",
        }

        ci_path, _, _ = self.render_template(
            template_name="layer2/ci.yml.j2",
            dest_path=".github/workflows/ci.yml",
            context=context,
            raise_on_collision=raise_on_collision,
        )
        results.append(ci_path)

        sec_path, _, _ = self.render_template(
            template_name="layer2/security.yml.j2",
            dest_path=".github/workflows/security.yml",
            context=context,
            raise_on_collision=raise_on_collision,
        )
        results.append(sec_path)

        return results

    def scaffold_layer3(
        self,
        package_name: str,
        project_type: str = "python",
        initial_version: str = "0.1.0",
        raise_on_collision: bool | None = None,
    ) -> list[Path]:
        """
        Scaffold Layer 3 automated CD with Google Release Please.

        Configured with:
        - .github/workflows/release-please.yml: Release Please GitHub Action.
        - release-please-config.json: Conventional Commits parsing and changelog configuration.
        - .release-please-manifest.json: Package version tracking manifest.

        Args:
            package_name: Name of package/library.
            project_type: 'python' or 'node'.
            initial_version: Starting SemVer version (default '0.1.0').
            raise_on_collision: Override collision behavior.

        Returns:
            List of Path objects for the release please files.
        """
        results: list[Path] = []
        context = {
            "package_name": package_name,
            "project_type": project_type.lower().strip(),
            "release_type": project_type.lower().strip(),
            "initial_version": initial_version,
        }

        rp_workflow, _, _ = self.render_template(
            template_name="layer3/release-please.yml.j2",
            dest_path=".github/workflows/release-please.yml",
            context=context,
            raise_on_collision=raise_on_collision,
        )
        results.append(rp_workflow)

        rp_config, _, _ = self.render_template(
            template_name="layer3/release-please-config.json.j2",
            dest_path="release-please-config.json",
            context=context,
            raise_on_collision=raise_on_collision,
        )
        results.append(rp_config)

        rp_manifest, _, _ = self.render_template(
            template_name="layer3/release-please-manifest.json.j2",
            dest_path=".release-please-manifest.json",
            context=context,
            raise_on_collision=raise_on_collision,
        )
        results.append(rp_manifest)

        return results

    def scaffold_gitignore(
        self,
        project_type: str = "python",
        ai_tools: bool = True,
        raise_on_collision: bool | None = None,
    ) -> Path:
        """
        Scaffold comprehensive .gitignore including AI-development protection patterns.

        Ignores language artifacts as well as agent artifacts (.gemini/, .antigravity/,
        brain/, scratch/, *.log, transcript*.jsonl, .env*, etc.).

        Args:
            project_type: 'python' or 'node'.
            ai_tools: Include AI agent and scratch directory ignore patterns.
            raise_on_collision: Override collision behavior.

        Returns:
            Path object to .gitignore.
        """
        norm_type = project_type.lower().strip()
        if norm_type in ("node", "javascript", "typescript"):
            tmpl_name = "gitignore/node.gitignore.j2"
        else:
            tmpl_name = "gitignore/python.gitignore.j2"

        context = {"ai_tools": ai_tools}
        path, _, _ = self.render_template(
            template_name=tmpl_name,
            dest_path=".gitignore",
            context=context,
            raise_on_collision=raise_on_collision,
        )
        return path

    def scaffold_agent_hygiene(
        self,
        project_name: str,
        project_type: str = "python",
        testing_tier: str = "production",
        deploy_mode: str = "pm2",
        domain: str = "yourdomain.com",
        sync_cursor_claude: bool = False,
        raise_on_collision: bool | None = None,
    ) -> list[Path]:
        """
        Scaffold AI DevOps instructions (`AGENTS.md`), PR checklist template,
        and Dependabot configuration (plus optional `.cursorrules` and `CLAUDE.md`).
        """
        app_slug = project_name.lower().replace(" ", "-").strip() or "app"
        context = {
            "project_name": project_name,
            "app_name": app_slug,
            "project_type": project_type.lower().strip(),
            "testing_tier": testing_tier.lower().strip(),
            "deploy_mode": deploy_mode.lower().strip(),
            "domain": domain.strip() or "yourdomain.com",
        }

        targets = [
            ("hygiene/AGENTS.md.j2", "AGENTS.md"),
            ("hygiene/pull_request_template.md.j2", ".github/pull_request_template.md"),
            ("hygiene/dependabot.yml.j2", ".github/dependabot.yml"),
        ]
        if sync_cursor_claude:
            targets.extend(
                [
                    ("hygiene/AGENTS.md.j2", ".cursorrules"),
                    ("hygiene/AGENTS.md.j2", "CLAUDE.md"),
                ]
            )

        results: list[Path] = []
        for tmpl_name, dest_rel in targets:
            path, _, _ = self.render_template(
                template_name=tmpl_name,
                dest_path=dest_rel,
                context=context,
                raise_on_collision=raise_on_collision,
            )
            results.append(path)
        return results

    def scaffold_vps_configs(
        self,
        app_name: str,
        project_type: str = "node",
        deploy_mode: str = "pm2",
        proxy_type: str = "nginx",
        domain: str = "yourdomain.com",
        raise_on_collision: bool | None = None,
    ) -> list[Path]:
        """
        Scaffold custom VPS deployment files under `deploy/vps/`:
        - `setup-vps.sh` directory and runtime bootstrapper
        - `ecosystem.config.cjs` (PM2) or `docker-compose.vps.yml` (Docker)
        - `nginx.conf` (Nginx) or `Caddyfile` (Caddy)
        """
        norm_deploy = deploy_mode.lower().strip()
        if norm_deploy not in ("pm2", "docker"):
            raise ValueError(
                f"Unsupported deploy_mode '{deploy_mode}'. Expected 'pm2' or 'docker'."
            )

        norm_proxy = proxy_type.lower().strip()
        if norm_proxy not in ("nginx", "caddy"):
            raise ValueError(f"Unsupported proxy_type '{proxy_type}'. Expected 'nginx' or 'caddy'.")

        app_slug = app_name.lower().replace(" ", "-").strip() or "app"
        context = {
            "app_name": app_slug,
            "project_type": project_type.lower().strip(),
            "deploy_mode": norm_deploy,
            "proxy_type": norm_proxy,
            "domain": domain.strip() or "yourdomain.com",
        }

        targets = [("vps/setup-vps.sh.j2", "deploy/vps/setup-vps.sh")]
        if norm_deploy == "docker":
            targets.append(("vps/docker-compose.vps.yml.j2", "deploy/vps/docker-compose.vps.yml"))
        else:
            targets.append(("vps/ecosystem.config.cjs.j2", "deploy/vps/ecosystem.config.cjs"))

        if norm_proxy == "caddy":
            targets.append(("vps/Caddyfile.j2", "deploy/vps/Caddyfile"))
        else:
            targets.append(("vps/nginx.conf.j2", "deploy/vps/nginx.conf"))

        results: list[Path] = []
        for tmpl_name, dest_rel in targets:
            path, _, _ = self.render_template(
                template_name=tmpl_name,
                dest_path=dest_rel,
                context=context,
                raise_on_collision=raise_on_collision,
            )
            results.append(path)
        return results

    def scaffold_all(
        self,
        project_name: str,
        project_type: str = "python",
        overwrite: bool = False,
        linter: str = "ruff",
        use_lefthook: bool = True,
        use_pre_commit: bool = True,
        ai_tools: bool = True,
        testing_tier: str = "production",
        deploy_mode: str = "pm2",
        build_strategy: str = "github",
        domain: str = "yourdomain.com",
        include_agent_hygiene: bool = True,
        raise_on_collision: bool | None = None,
    ) -> dict[str, Any]:
        """
        Orchestrate full 3-layer initialization, AI `.gitignore`, and agent hygiene files.
        """
        if overwrite:
            self.overwrite = True

        app_slug = project_name.lower().replace(" ", "-").strip() or "app"
        l1 = self.scaffold_layer1(
            project_type=project_type,
            linter=linter,
            use_lefthook=use_lefthook,
            use_pre_commit=use_pre_commit,
            raise_on_collision=raise_on_collision,
        )
        l2 = self.scaffold_layer2(
            project_type=project_type,
            testing_tier=testing_tier,
            deploy_mode=deploy_mode,
            build_strategy=build_strategy,
            domain=domain,
            app_name=app_slug,
            raise_on_collision=raise_on_collision,
        )
        l3 = self.scaffold_layer3(
            package_name=project_name,
            project_type=project_type,
            raise_on_collision=raise_on_collision,
        )
        gi = self.scaffold_gitignore(
            project_type=project_type,
            ai_tools=ai_tools,
            raise_on_collision=raise_on_collision,
        )
        hygiene = (
            self.scaffold_agent_hygiene(
                project_name=project_name,
                project_type=project_type,
                testing_tier=testing_tier,
                deploy_mode=deploy_mode,
                domain=domain,
                raise_on_collision=raise_on_collision,
            )
            if include_agent_hygiene
            else []
        )

        return {
            "layer1": l1,
            "layer2": l2,
            "layer3": l3,
            "gitignore": gi,
            "hygiene": hygiene,
            "manifest": self.manifest,
            "created": self.manifest.created,
            "skipped": self.manifest.skipped,
            "rendered": self.manifest.rendered,
        }

    def get_ruleset_payload(self) -> dict[str, Any]:
        """
        Generate GitHub Branch Ruleset API payload dictionary.

        Returns:
            Dictionary matching GitHub Ruleset API schema.
        """
        return get_default_ruleset_payload()

    def generate_ruleset_script(
        self,
        repo_full_name: str | None = None,
        script_type: str = "ps1",
    ) -> str:
        """
        Generate GitHub CLI script to establish branch protection ruleset.

        Args:
            repo_full_name: Optional 'owner/repo' identifier.
            script_type: 'ps1' (PowerShell) or 'sh' (Bash).

        Returns:
            Rendered script content.
        """
        return generate_ruleset_script(
            repo_full_name=repo_full_name,
            script_type=script_type,
            templates_dir=self.templates_dir,
        )


# Alias for backward and cross-spec compatibility
TemplateEngine = ScaffoldEngine
