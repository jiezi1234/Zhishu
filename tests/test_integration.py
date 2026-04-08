#!/usr/bin/env python3
"""
End-to-end integration test for HealthPath Agent.
Tests all 4 skills in sequence with sample data.
Now using DeepSeek API for intent understanding.
"""

import sys
import json
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Add skills to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'skill_1_intent'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'skill_2_crawl'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'skill_3_decision'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'skill_4_output'))

from intent_parser import parse_intent
from hospital_crawler import search_available_slots
from decision_engine import evaluate_and_rank
from output_generator import generate_output


def run_end_to_end_test():
    """Run complete end-to-end test"""

    print("=" * 70)
    print("HealthPath Agent - End-to-End Integration Test")
    print("=" * 70)
    print()

    # Test scenarios
    test_scenarios = [
        {
            "name": "场景 A：银发族陪诊",
            "input": "老人这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。"
        },
        {
            "name": "场景 B：职场人夜间/周末就医",
            "input": "我在南山区上班，只能周末看颈椎，帮我找最近且排队短的医院。"
        },
        {
            "name": "场景 C：异地医旅一体化",
            "input": "下周从赣州去广州看呼吸科，帮我把挂号、车票、住宿一起规划。"
        }
    ]

    for scenario in test_scenarios:
        print(f"\n{'=' * 70}")
        print(f"测试：{scenario['name']}")
        print(f"{'=' * 70}")
        print(f"用户输入：{scenario['input']}")
        print()

        try:
            # Skill 1: Intent Understanding (now using DeepSeek API)
            print("[Skill 1] Intent Understanding with DeepSeek API")
            print("-" * 70)
            task_params = parse_intent(scenario['input'], use_deepseek=True)
            print(json.dumps(task_params, ensure_ascii=False, indent=2))
            print()

            # Skill 2: Hospital Crawler
            print("[Skill 2] Hospital Crawler and Slot Standardization")
            print("-" * 70)
            search_result = search_available_slots(task_params)
            print(f"Found {search_result['total_count']} available slots")
            print(json.dumps(search_result, ensure_ascii=False, indent=2)[:500] + "...")
            print()

            # Skill 3: Decision Engine
            print("[Skill 3] Decision Engine with Multi-Criteria Evaluation")
            print("-" * 70)
            recommendations = evaluate_and_rank(
                search_result['slots'],
                task_params,
                top_n=2
            )
            print(json.dumps(recommendations, ensure_ascii=False, indent=2))
            print()

            # Skill 4: Output Generator
            print("[Skill 4] Output Generation")
            print("-" * 70)
            output_result = generate_output(
                recommendations['recommendations'],
                task_params,
                task_params.get('output_format', 'excel')
            )
            print(json.dumps(output_result, ensure_ascii=False, indent=2))
            print()

            print("[PASS] Test passed")

        except Exception as e:
            print(f"[FAIL] 测试失败：{str(e)}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 70)
    print("All tests completed")
    print("=" * 70)


if __name__ == "__main__":
    run_end_to_end_test()
