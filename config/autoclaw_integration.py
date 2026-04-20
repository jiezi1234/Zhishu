"""
AutoClaw Integration Module for HealthPath Agent.
Registers the unified 5-step skill chain.
"""

import json
import os
from pathlib import Path


class AutoClawIntegration:
    """Handles integration with AutoClaw framework."""

    def __init__(self, autoclaw_workspace: str = None):
        if autoclaw_workspace is None:
            autoclaw_workspace = os.getenv(
                "AUTOCLAW_WORKSPACE",
                "C:\\Users\\Administrator\\.openclaw-autoclaw",
            )

        self.workspace = Path(autoclaw_workspace)
        self.skills_dir = self.workspace / "skills"
        self.project_root = Path(__file__).parent.parent

    def register_skills(self):
        skills = [
            {
                "name": "healthpath-intent-understanding",
                "source": self.project_root / "skills" / "healthpath-intent-understanding",
            },
            {
                "name": "healthpath-symptom-triage",
                "source": self.project_root / "skills" / "healthpath-symptom-triage",
            },
            {
                "name": "healthpath-hospital-matcher",
                "source": self.project_root / "skills" / "healthpath-hospital-matcher",
            },
            {
                "name": "healthpath-registration-fetcher",
                "source": self.project_root / "skills" / "healthpath-registration-fetcher",
            },
            {
                "name": "healthpath-doctor-schedule",
                "source": self.project_root / "skills" / "healthpath-doctor-schedule",
            },
            {
                "name": "healthpath-itinerary-builder",
                "source": self.project_root / "skills" / "healthpath-itinerary-builder",
            },
        ]

        for skill in skills:
            self._register_skill(skill)

    def _register_skill(self, skill: dict):
        skill_name = skill["name"]
        source_dir = skill["source"]
        dest_dir = self.skills_dir / skill_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        for filename in ["SKILL.md", "_meta.json"]:
            src = source_dir / filename
            if src.exists():
                content = src.read_text(encoding="utf-8")
                (dest_dir / filename).write_text(content, encoding="utf-8")

        for py_file in source_dir.glob("*.py"):
            if not py_file.name.startswith("__"):
                (dest_dir / py_file.name).write_text(
                    py_file.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

        for json_file in source_dir.glob("*.json"):
            if json_file.name != "_meta.json":
                (dest_dir / json_file.name).write_text(
                    json_file.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

        print(f"[OK] Registered skill: {skill_name}")

    def get_skill_status(self):
        status = {}
        for skill_name in [
            "healthpath-intent-understanding",
            "healthpath-symptom-triage",
            "healthpath-hospital-matcher",
            "healthpath-registration-fetcher",
            "healthpath-doctor-schedule",
            "healthpath-itinerary-builder",
        ]:
            skill_dir = self.skills_dir / skill_name
            status[skill_name] = {
                "exists": skill_dir.exists(),
                "has_skill_md": (skill_dir / "SKILL.md").exists(),
                "has_meta_json": (skill_dir / "_meta.json").exists(),
                "path": str(skill_dir),
            }
        return status


def main():
    print("=" * 70)
    print("HealthPath Agent - AutoClaw Integration")
    print("=" * 70)

    integration = AutoClawIntegration()
    print(f"AutoClaw Workspace: {integration.workspace}")
    print(f"Skills Directory: {integration.skills_dir}")

    print("\nRegistering skills...")
    integration.register_skills()

    print("\nSkill Status:")
    status = integration.get_skill_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
