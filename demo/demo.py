#!/usr/bin/env python3
"""
HealthPath Agent Demo Script
Demonstrates the complete end-to-end workflow with DeepSeek API integration.
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


def demo_scenario(scenario_name: str, user_input: str):
    """Run a complete demo scenario"""

    print("\n" + "=" * 80)
    print(f"SCENARIO: {scenario_name}")
    print("=" * 80)
    print(f"\nUser Input: {user_input}\n")

    # Step 1: Intent Understanding
    print("[STEP 1] Understanding Intent with DeepSeek API")
    print("-" * 80)
    task_params = parse_intent(user_input, use_deepseek=True)

    print(f"Extracted Parameters:")
    print(f"  - Symptom: {task_params.get('symptom')}")
    print(f"  - Department: {task_params.get('department')}")
    print(f"  - Target City: {task_params.get('target_city')}")
    print(f"  - Time Window: {task_params.get('time_window')}")
    print(f"  - Travel Preference: {task_params.get('travel_preference')}")
    print(f"  - Output Format: {task_params.get('output_format')}")
    if task_params.get('special_requirements'):
        print(f"  - Special Requirements: {task_params.get('special_requirements')}")

    # Step 2: Hospital Search
    print("\n[STEP 2] Searching Available Hospital Slots")
    print("-" * 80)
    search_result = search_available_slots(task_params)
    print(f"Found {search_result['total_count']} available slots")

    if search_result['total_count'] > 0:
        print("\nTop 3 Available Slots:")
        for i, slot in enumerate(search_result['slots'][:3], 1):
            print(f"\n  {i}. {slot['hospital_name']} - {slot['department']}")
            print(f"     Doctor: {slot['doctor_name']} ({slot['doctor_title']})")
            print(f"     Time: {slot['available_time']}")
            print(f"     Fee: {slot['registration_fee']} yuan")
            print(f"     Queue: ~{slot['queue_estimate_min']} minutes")
            print(f"     Distance: {slot['distance_km']} km")

    # Step 3: Decision Engine
    print("\n[STEP 3] Evaluating and Ranking Options")
    print("-" * 80)
    recommendations = evaluate_and_rank(
        search_result['slots'],
        task_params,
        top_n=2
    )

    if recommendations['recommendations']:
        print(f"Generated {len(recommendations['recommendations'])} recommendations:\n")
        for rec in recommendations['recommendations']:
            print(f"  Recommendation #{rec['rank']}:")
            print(f"    Hospital: {rec['hospital_name']}")
            print(f"    Doctor: {rec['doctor_name']} ({rec['doctor_title']})")
            print(f"    Time: {rec['appointment_time']}")
            print(f"    Score: {rec['score']}/10")
            print(f"    Reason: {rec['reason']}")
            print()
    else:
        print("No recommendations available (no matching slots found)")

    # Step 4: Output Generation
    print("[STEP 4] Generating Output Documents")
    print("-" * 80)
    output_result = generate_output(
        recommendations['recommendations'],
        task_params,
        task_params.get('output_format', 'excel')
    )

    if output_result['status'] == 'success':
        print(f"Output Format: {output_result['format']}")
        for file_type, file_path in output_result['files'].items():
            print(f"  - {file_type.upper()}: {os.path.basename(file_path)}")
    else:
        print(f"Error: {output_result.get('error')}")

    print("\n" + "=" * 80)


def main():
    """Run all demo scenarios"""

    print("\n")
    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + "  HealthPath Agent - Complete End-to-End Demo".center(78) + "*")
    print("*" + "  Powered by DeepSeek API for Intent Understanding".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80)

    # Scenario A: Elderly care
    demo_scenario(
        "Scenario A: Elderly Care",
        "老人这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。"
    )

    # Scenario B: Working professional
    demo_scenario(
        "Scenario B: Working Professional",
        "我在南山区上班，只能周末看颈椎，帮我找最近且排队短的医院。"
    )

    # Scenario C: Remote medical travel
    demo_scenario(
        "Scenario C: Remote Medical Travel",
        "下周从赣州去广州看呼吸科，帮我把挂号、车票、住宿一起规划。"
    )

    demo_scenario(
        "Scenario D: ",
        "下周从赣州去广州看呼吸科，帮我把挂号、车票、住宿一起规划。"
    )

    print("\n" + "*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + "  Demo Complete!".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80 + "\n")


if __name__ == "__main__":
    main()
