"""
Scaffolding and template automation engine for git-mgr.
Implements 3-Layer automation:
- Layer 1: Local gatekeepers (Lefthook & pre-commit)
- Layer 2: Remote CI & security (GitHub Actions & Gitleaks)
- Layer 3: Automated release CD (Google Release Please)
- Comprehensive AI & developer .gitignore patterns
- GitHub Ruleset branch protection script generator
"""

from git_manager.scaffold.engine import (
    ScaffoldEngine,
    TemplateEngine,
    ScaffoldManifest,
    ScaffoldCollisionError,
)
from git_manager.scaffold.ruleset import (
    generate_ruleset_script,
    get_default_ruleset_payload,
)

__all__ = [
    "ScaffoldEngine",
    "TemplateEngine",
    "ScaffoldManifest",
    "ScaffoldCollisionError",
    "generate_ruleset_script",
    "get_default_ruleset_payload",
]
