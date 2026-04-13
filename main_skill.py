"""
main_skill.py — HealthPath Agent 主入口

协调四个子 Skill 的执行，完成「症状输入 → 就医行程单」全链路：

  symptom_triage       病情预判与科室推荐
  hospital_matcher     附近医院匹配
  registration_fetcher 挂号信息采集
  itinerary_builder    路线规划与行程单生成

AutoClaw 调用方式：
  from main_skill import execute
  result = execute(user_input="老人头晕失眠，在朝阳区望京")

返回结构：
  {
    "status":       "success" | "need_more_info" | "error",
    "steps":        { "triage": {...}, "match": {...}, "registration": {...}, "itinerary": {...} },
    "final_output": { "pdf_path": "...", "depart_time": "..." },
    "follow_up":    [...],   # 若需要追问则非空
    "error":        null | str
  }
"""

import sys
import os
import json
import logging
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Skill 路径注入 ────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
for skill_dir in ["symptom_triage", "hospital_matcher",
                  "registration_fetcher", "itinerary_builder"]:
    sys.path.insert(0, os.path.join(_ROOT, "skills", skill_dir))

from symptom_triage      import triage
from hospital_matcher    import match
from registration_fetcher import fetch
from itinerary_builder   import build


class HealthPathAgent:
    """HealthPath Agent — 智能就医调度智能体"""

    name        = "HealthPath Agent"
    version     = "2.0.0"
    description = "从症状描述到就医行程单的一站式智能就医调度助手"

    # ── 主流程 ────────────────────────────────────────────────────────────

    def execute(self,
                user_input: str,
                user_location: Optional[str] = None,
                selected_hospital: Optional[str] = None,
                extra_answers: Optional[dict] = None,
                output_format: str = "large_font_pdf",
                user_profile: Optional[dict] = None) -> Dict[str, Any]:
        """
        执行完整就医调度流程。

        Parameters
        ----------
        user_input        : 用户自然语言描述（症状/就医需求）
        user_location     : 用户当前地址；若为 None 则在分诊后询问
        selected_hospital : 用户已选择的医院名称；若为 None 则展示候选列表
        extra_answers     : 对分诊追问的回答 {question_id: answer}
        output_format     : "large_font_pdf"（老年版）| "pdf"（标准版）
        user_profile      : {"age_group": "elderly"|"adult"|"child"}

        Returns
        -------
        dict — 见模块级文档
        """
        logger.info(f"[HealthPath] 开始处理: {user_input[:60]}")
        result = {"status": "success", "steps": {}, "final_output": None,
                  "follow_up": [], "error": None}

        try:
            # ── Step 1: 症状分诊 ──────────────────────────────────────
            logger.info("[Step 1] 病情预判 / 科室推荐 ...")
            triage_result = triage(
                symptom_text=user_input,
                user_profile=user_profile,
                extra_answers=extra_answers,
            )
            result["steps"]["triage"] = triage_result

            # 若有危急警示，优先提醒
            if triage_result["warning_flags"]:
                result["status"] = "emergency_warning"
                result["final_output"] = {
                    "warning": triage_result["warning_flags"],
                    "message": "检测到危急症状，建议立即就近急诊或拨打 120！",
                }
                return result

            # 若信息不足，返回追问列表
            if triage_result["need_more_info"]:
                result["status"] = "need_more_info"
                result["follow_up"] = triage_result["follow_up_questions"]
                return result

            departments = triage_result["recommended_departments"]
            logger.info(f"  推荐科室: {departments}")

            # ── Step 2: 需要用户地址 ─────────────────────────────────
            if not user_location:
                result["status"] = "need_location"
                result["follow_up"] = [{
                    "id": "location",
                    "question": "请告诉我您当前的地址或所在区域（如：朝阳区望京街道），以便为您查找附近医院。"
                }]
                result["steps"]["triage"] = triage_result
                return result

            # ── Step 3: 医院匹配 ─────────────────────────────────────
            logger.info("[Step 2] 查找附近医院 ...")
            match_result = match(
                user_location=user_location,
                departments=departments,
                preferences=_extract_preferences(user_input, user_profile),
            )
            result["steps"]["match"] = match_result

            candidates = match_result["candidates"]
            if not candidates:
                result["status"] = "no_hospitals_found"
                result["error"] = "附近未找到符合条件的医院，请尝试放宽条件或修改位置"
                return result

            # 若用户尚未选择医院，返回候选列表供选择
            if not selected_hospital:
                result["status"] = "awaiting_hospital_selection"
                result["final_output"] = {
                    "candidates": candidates,
                    "message": "以下是附近医院候选，请告知您选择哪一家：",
                }
                return result

            # ── Step 4: 挂号信息采集 ─────────────────────────────────
            logger.info(f"[Step 3] 采集挂号信息: {selected_hospital} ...")
            hospital_info = next(
                (h for h in candidates if h["hospital_name"] == selected_hospital),
                {"hospital_name": selected_hospital, "address": "", "yixue_url": ""}
            )
            reg_result = fetch(
                hospital_name=selected_hospital,
                department=departments[0],
                yixue_url=hospital_info.get("yixue_url"),
            )
            result["steps"]["registration"] = reg_result
            logger.info(f"  挂号链接: {reg_result.get('registration_url')}")

            # ── Step 5: 行程单生成（用户表示已挂号后调用）────────────
            logger.info("[Step 4] 生成就医行程单 ...")
            itinerary_result = build(
                user_location=user_location,
                hospital_name=selected_hospital,
                hospital_address=hospital_info.get("address", ""),
                department=departments[0],
                registration_info=reg_result,
                output_format=output_format,
                user_profile=user_profile,
            )
            result["steps"]["itinerary"] = itinerary_result
            result["final_output"]  = {
                "pdf_path":    itinerary_result["pdf_path"],
                "depart_time": itinerary_result["depart_time"],
                "route":       itinerary_result["route_summary"],
                "registration_url": reg_result.get("registration_url"),
            }

            logger.info("✓ 全流程完成")
            return result

        except Exception as e:
            import traceback
            logger.error(f"✗ 执行失败: {e}")
            result["status"] = "error"
            result["error"]  = str(e)
            result["traceback"] = traceback.format_exc()
            return result

    def get_info(self) -> Dict[str, Any]:
        return {
            "name":         self.name,
            "version":      self.version,
            "description":  self.description,
            "skills": [
                "symptom_triage      — 病情预判与科室推荐",
                "hospital_matcher    — 附近医院匹配（CSV + 百度地图）",
                "registration_fetcher — 医院挂号信息采集",
                "itinerary_builder   — 路线规划与 PDF 行程单生成",
            ],
        }


# ── 偏好提取辅助 ──────────────────────────────────────────────────────────

def _extract_preferences(text: str, profile: Optional[dict]) -> dict:
    """从用户输入提取出行/医院偏好"""
    prefs = {"hospital_level": "三甲", "max_distance_km": 15}
    if "最近" in text or "近的" in text:
        prefs["max_distance_km"] = 8
    if "周末" in text:
        prefs["time_window"] = "weekend"
    if profile and profile.get("age_group") == "elderly":
        prefs["max_distance_km"] = 10  # 老年人不宜走太远
    return prefs


# ── 全局单例 & 公开接口 ───────────────────────────────────────────────────

_agent: Optional[HealthPathAgent] = None


def _get_agent() -> HealthPathAgent:
    global _agent
    if _agent is None:
        _agent = HealthPathAgent()
    return _agent


def execute(user_input: str, **kwargs) -> Dict[str, Any]:
    """
    AutoClaw 调用的主入口。

    常用 kwargs:
      user_location     str   用户地址
      selected_hospital str   用户选定的医院名称
      extra_answers     dict  对追问的回答
      output_format     str   "large_font_pdf" | "pdf"
      user_profile      dict  {"age_group": "elderly"|"adult"|"child"}
    """
    return _get_agent().execute(user_input=user_input, **kwargs)


def get_info() -> Dict[str, Any]:
    return _get_agent().get_info()


# ── CLI 快速测试 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  HealthPath Agent v2.0 — 快速测试")
    print("=" * 65)

    agent = HealthPathAgent()
    info  = agent.get_info()
    print(f"\n{info['name']} v{info['version']}")
    for s in info["skills"]:
        print(f"  · {s}")

    # ── 场景 A：老年人头晕 ────────────────────────────────────────────
    print("\n\n── 场景 A：老年人头晕 ──")
    r = agent.execute(
        user_input="老人头晕失眠两周了，有时耳鸣",
        user_profile={"age_group": "elderly"},
    )
    print(f"状态: {r['status']}")
    if r["status"] == "need_location":
        print("追问:", r["follow_up"][0]["question"])

    # ── 场景 B：完整流程 ──────────────────────────────────────────────
    print("\n\n── 场景 B：完整流程（含位置+选院）──")
    r2 = agent.execute(
        user_input="最近腰疼，想看骨科，这周能挂上最好",
        user_location="北京市朝阳区望京街道",
        selected_hospital="北京协和医院",
        output_format="large_font_pdf",
        user_profile={"age_group": "adult"},
    )
    print(f"状态: {r2['status']}")
    if r2.get("final_output"):
        fo = r2["final_output"]
        if "pdf_path" in fo:
            print(f"PDF: {fo['pdf_path']}")
            print(f"出发时间: {fo['depart_time']}")
            print(f"挂号链接: {fo['registration_url']}")

    print("\n" + "=" * 65)
