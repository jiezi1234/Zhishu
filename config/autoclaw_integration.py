"""
AutoClaw Integration Module for HealthPath Agent.
Registers all 4 skills with the AutoClaw framework.
"""

import os
import json
from pathlib import Path


class AutoClawIntegration:
    """Handles integration with AutoClaw framework"""

    def __init__(self, autoclaw_workspace: str = None):
        """
        Initialize AutoClaw integration.

        Args:
            autoclaw_workspace: Path to AutoClaw workspace
        """
        if autoclaw_workspace is None:
            autoclaw_workspace = os.getenv(
                "AUTOCLAW_WORKSPACE",
                "C:\\Users\\Administrator\\.openclaw-autoclaw"
            )

        self.workspace = Path(autoclaw_workspace)
        self.skills_dir = self.workspace / "skills"
        self.project_root = Path(__file__).parent.parent.parent

    def register_skills(self):
        """Register all HealthPath Agent skills with AutoClaw"""

        skills = [
            {
                "name": "healthpath-intent-understanding",
                "source": self.project_root / "skills" / "skill_1_intent",
                "description": "Parse user medical appointment request into structured task parameters"
            },
            {
                "name": "healthpath-hospital-crawler",
                "source": self.project_root / "skills" / "skill_2_crawl",
                "description": "Search and fetch available medical appointment slots from multiple hospitals"
            },
            {
                "name": "healthpath-decision-engine",
                "source": self.project_root / "skills" / "skill_3_decision",
                "description": "Evaluate and rank medical appointment options based on multiple criteria"
            },
            {
                "name": "healthpath-output-generator",
                "source": self.project_root / "skills" / "skill_4_output",
                "description": "Generate formatted output documents (PDF, Excel) with appointment recommendations"
            }
        ]

        for skill in skills:
            self._register_skill(skill)

    def _register_skill(self, skill: dict):
        """Register a single skill with AutoClaw"""

        skill_name = skill["name"]
        source_dir = skill["source"]
        dest_dir = self.skills_dir / skill_name

        # Create destination directory if it doesn't exist
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md
        skill_md = source_dir / "SKILL.md"
        if skill_md.exists():
            with open(skill_md, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(dest_dir / "SKILL.md", 'w', encoding='utf-8') as f:
                f.write(content)

        # Copy _meta.json
        meta_json = source_dir / "_meta.json"
        if meta_json.exists():
            with open(meta_json, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            with open(dest_dir / "_meta.json", 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        # Copy Python scripts
        for py_file in source_dir.glob("*.py"):
            if not py_file.name.startswith("__"):
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(dest_dir / py_file.name, 'w', encoding='utf-8') as f:
                    f.write(content)

        print(f"[OK] Registered skill: {skill_name}")

    def get_skill_status(self):
        """Get status of all registered skills"""

        status = {}
        for skill_dir in self.skills_dir.glob("healthpath-*"):
            skill_name = skill_dir.name
            skill_md = skill_dir / "SKILL.md"
            meta_json = skill_dir / "_meta.json"

            status[skill_name] = {
                "exists": skill_dir.exists(),
                "has_skill_md": skill_md.exists(),
                "has_meta_json": meta_json.exists(),
                "path": str(skill_dir)
            }

        return status


def main():
    """Main entry point for AutoClaw integration"""

    print("=" * 70)
    print("HealthPath Agent - AutoClaw Integration")
    print("=" * 70)
    print()

    integration = AutoClawIntegration()

    print(f"AutoClaw Workspace: {integration.workspace}")
    print(f"Skills Directory: {integration.skills_dir}")
    print()

    print("Registering skills...")
    print("-" * 70)
    integration.register_skills()

    print()
    print("Skill Status:")
    print("-" * 70)
    status = integration.get_skill_status()
    for skill_name, info in status.items():
        print(f"\n{skill_name}:")
        print(f"  Exists: {info['exists']}")
        print(f"  SKILL.md: {info['has_skill_md']}")
        print(f"  _meta.json: {info['has_meta_json']}")
        print(f"  Path: {info['path']}")

    print()
    print("=" * 70)
    print("Integration complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
