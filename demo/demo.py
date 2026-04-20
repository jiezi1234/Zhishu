"""
demo.py — 智枢 演示脚本

展示完整的就医调度全链路，适合答辩现场使用。

运行方式：
  python demo/demo.py
"""

import sys
import os
import io

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from main_skill import execute
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保在项目根目录运行此脚本：python demo/demo.py")
    sys.exit(1)


def print_separator(title=""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
    else:
        print('-'*70)


def demo_scenario_a():
    """场景 A：老人头晕失眠（演示多轮对话流程）"""
    print_separator("场景 A：老人头晕失眠（多轮对话）")
    
    # 第一轮：只有症状，无位置
    print("\n[用户] 老人头晕失眠两周了")
    result = execute(
        user_input="老人头晕失眠两周了",
        user_profile={"age_group": "elderly"},
    )
    
    print(f"[状态] {result['status']}")
    if result['status'] == 'need_location':
        print(f"[系统] {result['follow_up'][0]['question']}")
    
    # 第二轮：补充位置
    print("\n[用户] 我在北京市朝阳区望京街道")
    result = execute(
        user_input="老人头晕失眠两周了",
        user_location="北京市朝阳区望京街道",
        user_profile={"age_group": "elderly"},
    )
    
    print(f"[状态] {result['status']}")
    if result['status'] == 'awaiting_hospital_selection':
        candidates = result['final_output']['candidates']
        print(f"[系统] 找到 {len(candidates)} 家医院候选：")
        for i, h in enumerate(candidates[:3], 1):
            print(f"  {i}. {h['hospital_name']} - {h.get('distance_km', '?')} km")
    
    # 第三轮：选择医院
    print("\n[用户] 就去北京协和医院吧")
    result = execute(
        user_input="老人头晕失眠两周了",
        user_location="北京市朝阳区望京街道",
        selected_hospital="北京协和医院",
        user_profile={"age_group": "elderly"},
        output_format="large_font_pdf",
    )
    
    print(f"[状态] {result['status']}")
    if result['status'] == 'success':
        pdf_path = result['final_output']['pdf_path']
        print(f"✅ 行程单已生成: {pdf_path}")
        print(f"   出发时间: {result['final_output']['depart_time']}")
        print(f"   挂号链接: {result['final_output'].get('registration_url', '未获取')}")


def demo_scenario_b():
    """场景 B：腰疼骨科（一次完成）"""
    print_separator("场景 B：腰疼骨科（一次完成）")
    
    print("\n[用户] 最近腰疼，想看骨科，这周能挂上最好，我在北京朝阳区望京")
    result = execute(
        user_input="最近腰疼，想看骨科，这周能挂上最好",
        user_location="北京市朝阳区望京街道",
        selected_hospital="北京协和医院",
        output_format="large_font_pdf",
        user_profile={"age_group": "adult"},
    )
    
    print(f"[状态] {result['status']}")
    
    if result['status'] == 'success':
        pdf_path = result['final_output']['pdf_path']
        print(f"✅ 行程单已生成: {pdf_path}")
        print(f"   出发时间: {result['final_output']['depart_time']}")
        print(f"   路线: {result['final_output']['route']}")
    elif result['status'] == 'error':
        print(f"❌ 错误: {result['error']}")
    else:
        print(f"⚠️  状态: {result['status']}")
        if result.get('follow_up'):
            print(f"   追问: {result['follow_up'][0]['question']}")


def main():
    """主函数"""
    print("\n" + "="*70)
    print("  智枢——基于长链路协同的全人群医旅调度智能体 演示")
    print("="*70)
    print("\n本演示展示完整的就医调度全链路：")
    print("  症状分诊 → 医院匹配 → 挂号链接 → 路线规划 → PDF 行程单")
    print()
    
    try:
        # 场景 A：多轮对话
        demo_scenario_a()
        
        # 场景 B：一次完成
        demo_scenario_b()
        
        print_separator()
        print("\n✅ 演示完成！")
        print("\n生成的 PDF 文件位于项目根目录的 output/ 文件夹中。")
        print("可使用 PDF 阅读器打开查看就医行程单。\n")
        
    except Exception as e:
        import traceback
        print(f"\n❌ 演示过程中出现错误:")
        print(f"   {e}")
        print("\n详细错误信息:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
