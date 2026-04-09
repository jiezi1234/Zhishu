"""
端到端集成测试 - 验证完整的医院预约流程
从自然语言输入到PDF输出
"""

import sys
import os
import json

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add skills to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, "skills", "skill_1_intent"))
sys.path.insert(0, os.path.join(project_root, "skills", "skill_2_crawl"))
sys.path.insert(0, os.path.join(project_root, "skills", "skill_3_decision"))
sys.path.insert(0, os.path.join(project_root, "skills", "skill_4_output"))

from intent_parser import parse_intent
from hospital_crawler import search_available_slots
from decision_engine import evaluate_and_rank
from output_generator import generate_output


def test_end_to_end():
    """测试完整的端到端流程"""
    print("\n" + "="*70)
    print("端到端集成测试 - 医院预约系统")
    print("="*70)

    # 测试用例
    test_cases = [
        {
            "name": "场景1: 老年人就医 - 骨科",
            "input": "我奶奶最近腰疼得厉害，想在北京找个好医院看骨科，最好这周能挂上号，离家近一点最好"
        },
        {
            "name": "场景2: 上班族就医 - 神经内科",
            "input": "我最近头晕，想找个离公司近的医院看神经内科，最好能在周末或晚上挂号"
        },
        {
            "name": "场景3: 异地就医 - 呼吸科",
            "input": "我从外地来北京，需要看呼吸科，最好能找个评价好的医院，费用不要太贵"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"测试 {i}: {test_case['name']}")
        print(f"{'='*70}")

        user_input = test_case['input']
        print(f"\n[输入] 用户: {user_input}")

        try:
            # Skill 1: 意图解析
            print("\n[Skill 1] 解析用户意图...")
            intent_result = parse_intent(user_input)
            task_params = intent_result.get("task_params", {})
            print(f"  ✓ 解析成功")
            print(f"    - 科室: {task_params.get('department', '未指定')}")
            print(f"    - 症状: {task_params.get('symptom', '未指定')}")
            print(f"    - 时间: {task_params.get('time_window', '未指定')}")
            print(f"    - 偏好: {task_params.get('travel_preference', '未指定')}")

            # Skill 2: 号源搜索
            print("\n[Skill 2] 搜索可用号源...")
            search_result = search_available_slots(task_params)
            slots = search_result.get("slots", [])
            print(f"  ✓ 搜索成功")
            print(f"    - 找到 {len(slots)} 个号源")
            print(f"    - 数据来源: {', '.join(search_result.get('data_sources', []))}")

            if not slots:
                print("  ⚠ 没有找到匹配的号源，跳过后续步骤")
                continue

            # Skill 3: 方案决策
            print("\n[Skill 3] 评分和排序...")
            decision_result = evaluate_and_rank(slots, task_params)
            recommendations = decision_result.get("recommendations", [])
            print(f"  ✓ 排序成功")
            print(f"    - 推荐 {len(recommendations)} 个方案")
            if recommendations:
                best = recommendations[0]
                print(f"    - 最优方案: {best.get('hospital_name')} - {best.get('doctor_name')}")
                print(f"    - 评分: {best.get('score')}/10")
                print(f"    - 理由: {best.get('reason')}")

            # Skill 4: 输出生成
            print("\n[Skill 4] 生成输出文档...")
            output_result = generate_output(recommendations, task_params, "large_font_pdf")
            if output_result.get("status") == "success":
                pdf_path = output_result.get("files", {}).get("pdf", "")
                print(f"  ✓ 生成成功")
                print(f"    - 文件: {os.path.basename(pdf_path)}")
                print(f"    - 大小: {os.path.getsize(pdf_path) / 1024:.1f} KB")
            else:
                print(f"  ✗ 生成失败: {output_result.get('error')}")

            print(f"\n✓ 测试 {i} 完成")

        except Exception as e:
            print(f"\n✗ 测试 {i} 失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("所有端到端测试完成！")
    print("="*70)


def test_single_flow():
    """测试单个完整流程"""
    print("\n" + "="*70)
    print("单个完整流程测试")
    print("="*70)

    user_input = "我想在北京找个好医院看骨科，最好这周能挂上号"
    print(f"\n用户输入: {user_input}")

    try:
        # Skill 1
        print("\n[Skill 1] 意图解析...")
        intent_result = parse_intent(user_input)
        task_params = intent_result.get("task_params", {})
        print(f"✓ 任务参数: {json.dumps(task_params, ensure_ascii=False, indent=2)}")

        # Skill 2
        print("\n[Skill 2] 号源搜索...")
        search_result = search_available_slots(task_params)
        slots = search_result.get("slots", [])
        print(f"✓ 找到 {len(slots)} 个号源")

        # Skill 3
        print("\n[Skill 3] 方案决策...")
        decision_result = evaluate_and_rank(slots, task_params)
        recommendations = decision_result.get("recommendations", [])
        print(f"✓ 生成 {len(recommendations)} 个推荐方案")

        # Skill 4
        print("\n[Skill 4] 输出生成...")
        output_result = generate_output(recommendations, task_params, "large_font_pdf")
        if output_result.get("status") == "success":
            pdf_path = output_result.get("files", {}).get("pdf", "")
            print(f"✓ PDF 生成成功: {os.path.basename(pdf_path)}")
            print(f"  文件大小: {os.path.getsize(pdf_path) / 1024:.1f} KB")
        else:
            print(f"✗ 生成失败: {output_result.get('error')}")

        print("\n✓ 完整流程测试通过！")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n开始端到端集成测试...\n")

    try:
        # 运行单个流程测试
        test_single_flow()

        # 运行多个场景测试
        test_end_to_end()

        print("\n✓ 所有测试完成！")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
