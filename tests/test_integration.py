#!/usr/bin/env python3
"""
End-to-end integration test for HealthPath Agent.
Tests all 4 skills in sequence with sample data.
"""

import sys
import json
import os

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
            # Skill 1: Intent Understanding
            print("【Skill 1】意图理解与约束抽取")
            print("-" * 70)
            task_params = parse_intent(scenario['input'])
            print(json.dumps(task_params, ensure_ascii=False, indent=2))
            print()

            # Skill 2: Hospital Crawler
            print("【Skill 2】跨院号源巡航与标准化")
            print("-" * 70)
            search_result = search_available_slots(task_params)
            print(f"找到 {search_result['total_count']} 个可用号源")
            print(json.dumps(search_result, ensure_ascii=False, indent=2)[:500] + "...")
            print()

            # Skill 3: Decision Engine
            print("【Skill 3】医旅协同与多目标决策")
            print("-" * 70)
            recommendations = evaluate_and_rank(
                search_result['slots'],
                task_params,
                top_n=2
            )
            print(json.dumps(recommendations, ensure_ascii=False, indent=2))
            print()

            # Skill 4: Output Generator
            print("【Skill 4】结果生成与触达")
            print("-" * 70)
            output_result = generate_output(
                recommendations['recommendations'],
                task_params,
                task_params.get('output_format', 'excel')
            )
            print(json.dumps(output_result, ensure_ascii=False, indent=2))
            print()

            print("[PASS] 测试通过")

        except Exception as e:
            print(f"[FAIL] 测试失败：{str(e)}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 70)
    print("所有测试完成")
    print("=" * 70)


if __name__ == "__main__":
    run_end_to_end_test()
