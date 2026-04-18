#!/usr/bin/env python3
"""Smoke E2E script for healthpath 5-step flow."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main_skill import execute


def run_case(user_input, location=None, hospital=None):
    return execute(
        user_input=user_input,
        user_location=location,
        selected_hospital=hospital,
        user_profile={"age_group": "adult"},
        output_format="pdf",
    )


def main():
    cases = [
        ("我最近头晕，想找医院", None, None),
        ("最近腰疼，想看骨科", "北京市朝阳区", None),
        ("最近腰疼，想看骨科", "北京市朝阳区", "北京大学第三医院"),
    ]

    for idx, (text, loc, hosp) in enumerate(cases, 1):
        res = run_case(text, loc, hosp)
        print(f"\\n=== Case {idx} ===")
        print(json.dumps({
            "status": res.get("status"),
            "follow_up": res.get("follow_up", []),
            "final_output": res.get("final_output", {}),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
