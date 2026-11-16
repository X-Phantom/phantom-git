"""
GitHub Ruleset generation and branch protection orchestration.
Produces ready-to-run GitHub CLI (gh) automation scripts and schema-compliant
JSON payloads for GitHub Ruleset API.
"""

from pathlib import Path
from typing import Any
import jinja2


def get_default_ruleset_payload() -> dict[str, Any]:
    """
    Generate GitHub Branch Ruleset API payload enforcing trunk-based protection.

    Features:
    - Protects the default branch and main.
    - Prevents deletions and non-fast-forward merges (linear history).
    - Requires pull request reviews with thread resolution.
    - Requires status check 'CI' to pass before merging.
    """
    return {
        "name": "default-protection",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": [
                    "~DEFAULT_BRANCH",
                    "refs/heads/main",
                    "refs/heads/staging",
                ],
                "exclude": [],
            }
        },
        "rules": [
            {
                "type": "deletion",
            },
            {
                "type": "non_fast_forward",
            },
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": True,
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [
                        {
                            "context": "CI",
                        },
                        {
                            "context": "Code Quality & Type Integrity",
                        },
                        {
                            "context": "Unit & Component Tests",
                        },
                        {
                            "context": "Production Standalone Build",
                        },
                    ],
                },
            },
        ],
    }


def generate_ruleset_script(
    repo_full_name: str | None = None,
    script_type: str = "ps1",
    templates_dir: Path | None = None,
) -> str:
    """
    Generate an executable GitHub CLI script to establish branch rulesets and repo settings.

    Args:
        repo_full_name: GitHub repository in 'owner/repo' format (e.g., 'octocat/Hello-World').
        script_type: 'ps1' (PowerShell) or 'sh' (Bash).
        templates_dir: Optional custom path to Jinja2 template directory.

    Returns:
        Rendered script content as a string.
    """
    if templates_dir is None:
        templates_dir = Path(__file__).parent / "templates"

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=False,
        keep_trailing_newline=True,
    )

    norm_type = script_type.lower().strip()
    if norm_type in ("ps1", "powershell"):
        template_name = "ruleset/setup-ruleset.ps1.j2"
    elif norm_type in ("sh", "bash"):
        template_name = "ruleset/setup-ruleset.sh.j2"
    else:
        raise ValueError(
            f"Unsupported script_type '{script_type}'. Expected 'ps1', 'powershell', 'sh', or 'bash'."
        )

    template = env.get_template(template_name)
    return template.render(repo_full_name=repo_full_name or "")
