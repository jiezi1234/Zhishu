"""
HealthPath Agent - Main Skill for AutoClaw Integration
协调所有子Skill的执行，从用户输入到PDF生成的完整流程
"""

import sys
import os
import json
from typing import Dict, Any
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加Skills路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, "skills", "skill_1_intent"))
sys.path.insert(0, os.path.join(project_root, "skills", "skill_2_crawl"))
sys.path.insert(0, os.path.join(project_root, "skills", "skill_3_decision"))
sys.path.insert(0, os.path.join(project_root, "skills", "skill_4_output"))

# 导入各个Skill
from intent_parser import parse_intent
from hospital_crawler import search_available_slots
from decision_engine import evaluate_and_rank
from output_generator import generate_output


class HealthPathAgent:
    """HealthPath Agent - 医疗就诊路线规划智能体"""

    def __init__(self):
        self.name = "HealthPath Agent"
        self.version = "1.0.0"
        self.description = "智能医疗就诊路线规划系统，帮助用户找到最合适的医院和医生"

    def execute(self, user_input: str, output_format: str = "large_font_pdf") -> Dict[str, Any]:
        """
        执行完整的医疗就诊规划流程

        Args:
            user_input: 用户的自然语言输入
            output_format: 输出格式 ("pdf" 或 "large_font_pdf")

        Returns:
            包含结果的字典
        """
        logger.info(f"开始处理用户输入: {user_input}")

        result = {
            "status": "success",
            "steps": {},
            "final_output": None,
            "error": None
        }

        try:
            # Step 1: 意图解析
            logger.info("[Step 1] 解析用户意图...")
            intent_result = self._step1_parse_intent(user_input)
            if not intent_result["success"]:
                result["status"] = "error"
                result["error"] = intent_result["error"]
                return result

            task_params = intent_result["task_params"]
            result["steps"]["intent_parsing"] = intent_result

            # Step 2: 号源搜索
            logger.info("[Step 2] 搜索可用号源...")
            search_result = self._step2_search_slots(task_params)
            if not search_result["success"]:
                result["status"] = "error"
                result["error"] = search_result["error"]
                return result

            slots = search_result["slots"]
            result["steps"]["hospital_search"] = search_result

            # 检查是否找到号源
            if not slots:
                logger.warning("未找到匹配的号源")
                result["status"] = "no_results"
                result["error"] = "未找到匹配的号源"
                # 仍然生成PDF，但显示"未找到"
                recommendations = []
            else:
                # Step 3: 方案决策
                logger.info("[Step 3] 评分和排序...")
                decision_result = self._step3_rank_recommendations(slots, task_params)
                if not decision_result["success"]:
                    result["status"] = "error"
                    result["error"] = decision_result["error"]
                    return result

                recommendations = decision_result["recommendations"]
                result["steps"]["decision_ranking"] = decision_result

            # Step 4: 输出生成
            logger.info("[Step 4] 生成PDF文档...")
            output_result = self._step4_generate_output(recommendations, task_params, output_format)
            if not output_result["success"]:
                result["status"] = "error"
                result["error"] = output_result["error"]
                return result

            result["final_output"] = output_result
            result["steps"]["output_generation"] = output_result

            logger.info("✓ 流程完成")
            return result

        except Exception as e:
            logger.error(f"✗ 执行失败: {e}")
            result["status"] = "error"
            result["error"] = str(e)
            import traceback
            result["traceback"] = traceback.format_exc()
            return result

    def _step1_parse_intent(self, user_input: str) -> Dict[str, Any]:
        """Step 1: 解析用户意图"""
        try:
            intent_result = parse_intent(user_input)
            task_params = intent_result.get("task_params", {})

            logger.info(f"  科室: {task_params.get('department', '未指定')}")
            logger.info(f"  症状: {task_params.get('symptom', '未指定')}")
            logger.info(f"  时间: {task_params.get('time_window', '未指定')}")
            logger.info(f"  偏好: {task_params.get('travel_preference', '未指定')}")

            return {
                "success": True,
                "task_params": task_params,
                "raw_result": intent_result
            }
        except Exception as e:
            logger.error(f"  意图解析失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _step2_search_slots(self, task_params: Dict) -> Dict[str, Any]:
        """Step 2: 搜索可用号源"""
        try:
            search_result = search_available_slots(task_params)
            slots = search_result.get("slots", [])
            data_sources = search_result.get("data_sources", [])

            logger.info(f"  找到 {len(slots)} 个号源")
            logger.info(f"  数据来源: {', '.join(data_sources)}")

            return {
                "success": True,
                "slots": slots,
                "total_count": len(slots),
                "data_sources": data_sources,
                "raw_result": search_result
            }
        except Exception as e:
            logger.error(f"  号源搜索失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _step3_rank_recommendations(self, slots: list, task_params: Dict) -> Dict[str, Any]:
        """Step 3: 评分和排序"""
        try:
            decision_result = evaluate_and_rank(slots, task_params)
            recommendations = decision_result.get("recommendations", [])

            logger.info(f"  生成 {len(recommendations)} 个推荐方案")
            if recommendations:
                best = recommendations[0]
                logger.info(f"  最优方案: {best.get('hospital_name')} - {best.get('doctor_name')}")
                logger.info(f"  评分: {best.get('score')}/10")

            return {
                "success": True,
                "recommendations": recommendations,
                "count": len(recommendations),
                "raw_result": decision_result
            }
        except Exception as e:
            logger.error(f"  方案决策失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _step4_generate_output(self, recommendations: list, task_params: Dict, output_format: str) -> Dict[str, Any]:
        """Step 4: 生成输出文档"""
        try:
            output_result = generate_output(recommendations, task_params, output_format)

            if output_result.get("status") == "success":
                pdf_path = output_result.get("files", {}).get("pdf", "")
                file_size = os.path.getsize(pdf_path) / 1024 if os.path.exists(pdf_path) else 0

                logger.info(f"  PDF生成成功: {os.path.basename(pdf_path)}")
                logger.info(f"  文件大小: {file_size:.1f} KB")

                return {
                    "success": True,
                    "pdf_path": pdf_path,
                    "file_size_kb": file_size,
                    "raw_result": output_result
                }
            else:
                error = output_result.get("error", "未知错误")
                logger.error(f"  PDF生成失败: {error}")
                return {
                    "success": False,
                    "error": error
                }

        except Exception as e:
            logger.error(f"  输出生成失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_info(self) -> Dict[str, Any]:
        """获取智能体信息"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": [
                "自然语言理解",
                "医院号源搜索",
                "多维度评分排序",
                "PDF文档生成"
            ]
        }


# 全局实例
_agent = None


def get_agent() -> HealthPathAgent:
    """获取全局智能体实例"""
    global _agent
    if _agent is None:
        _agent = HealthPathAgent()
    return _agent


def execute(user_input: str, output_format: str = "large_font_pdf") -> Dict[str, Any]:
    """
    AutoClaw调用的主入口函数

    Args:
        user_input: 用户输入
        output_format: 输出格式

    Returns:
        执行结果
    """
    agent = get_agent()
    return agent.execute(user_input, output_format)


def get_info() -> Dict[str, Any]:
    """获取智能体信息"""
    agent = get_agent()
    return agent.get_info()


if __name__ == "__main__":
    # 测试
    print("\n" + "="*70)
    print("HealthPath Agent - 测试")
    print("="*70 + "\n")

    agent = HealthPathAgent()

    # 显示智能体信息
    info = agent.get_info()
    print(f"智能体: {info['name']}")
    print(f"版本: {info['version']}")
    print(f"描述: {info['description']}")
    print(f"能力: {', '.join(info['capabilities'])}\n")

    # 测试用例
    test_input = "我想在北京找个好医院看骨科，最好这周能挂上号"
    print(f"用户输入: {test_input}\n")

    # 执行
    result = agent.execute(test_input)

    # 显示结果
    print(f"\n执行状态: {result['status']}")
    if result['status'] == 'success':
        output = result.get('final_output', {})
        if output.get('success'):
            print(f"PDF路径: {output.get('pdf_path')}")
            print(f"文件大小: {output.get('file_size_kb'):.1f} KB")
    elif result['status'] == 'error':
        print(f"错误: {result['error']}")
    else:
        print(f"状态: {result['status']}")
        if result.get('error'):
            print(f"信息: {result['error']}")

    print("\n" + "="*70)
