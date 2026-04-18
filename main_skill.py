"""
main_skill.py — 智枢——基于长链路协同的全人群医旅调度智能体 主入口

统一 5 步流程：
  1) healthpath-intent-understanding
  2) healthpath-symptom-triage（用户已明确科室可跳过）
  3) healthpath-hospital-matcher
  4) healthpath-registration-fetcher
  5) healthpath-itinerary-builder
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.abspath(__file__))
for skill_dir in [
    "healthpath-intent-understanding",
    "healthpath-symptom-triage",
    "healthpath-hospital-matcher",
    "healthpath-registration-fetcher",
    "healthpath-itinerary-builder",
]:
    sys.path.insert(0, os.path.join(_ROOT, "skills", skill_dir))

from intent_parser import parse_intent
from symptom_triage import triage
from hospital_matcher import match
from registration_fetcher import fetch
from itinerary_builder import build


class HealthPathAgent:
    name = "智枢"
    version = "3.0.0"
    description = "基于长链路协同的全人群医旅调度智能体"

    def execute(
        self,
        user_input: str,
        user_location: Optional[str] = None,
        selected_hospital: Optional[str] = None,
        extra_answers: Optional[dict] = None,
        output_format: str = "large_font_pdf",
        user_profile: Optional[dict] = None,
    ) -> Dict[str, Any]:
        logger.info("[智枢] 开始处理: %s", user_input[:80])
        result: Dict[str, Any] = {
            "status": "success",
            "steps": {},
            "final_output": None,
            "follow_up": [],
            "error": None,
        }

        try:
            # Step 1: 意图结构化
            intent_result = parse_intent(user_input, use_deepseek=True)
            result["steps"]["intent"] = intent_result
            explicit_dept = (intent_result or {}).get("department", "")
            has_explicit_dept = bool(explicit_dept and explicit_dept != "未指定")

            # Step 2: 症状分诊（可跳过）
            if has_explicit_dept:
                departments = [explicit_dept]
                result["steps"]["triage"] = {
                    "recommended_departments": departments,
                    "warning_flags": [],
                    "need_more_info": False,
                    "follow_up_questions": [],
                    "preliminary_diagnosis": "用户已明确目标科室，跳过分诊。",
                    "referenced_routes": [],
                    "disclaimer": "⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。如症状严重或突发，请立即拨打 120 或前往最近急诊。",
                }
            else:
                triage_result = triage(
                    symptom_text=user_input,
                    user_profile=user_profile,
                    extra_answers=extra_answers,
                )
                result["steps"]["triage"] = triage_result

                if triage_result.get("warning_flags"):
                    result["status"] = "emergency_warning"
                    result["final_output"] = {
                        "warning": triage_result["warning_flags"],
                        "message": "检测到危急症状，建议立即就近急诊或拨打 120！",
                    }
                    return result

                if triage_result.get("need_more_info"):
                    result["status"] = "need_more_info"
                    result["follow_up"] = triage_result.get("follow_up_questions", [])
                    return result

                departments = triage_result.get("recommended_departments") or ["全科医学科"]

            if not user_location:
                result["status"] = "need_location"
                result["follow_up"] = [
                    {
                        "id": "location",
                        "question": "请告诉我您当前的地址或所在区域（如：朝阳区望京街道），以便为您查找附近医院。",
                    }
                ]
                return result

            # Step 3: 医院匹配
            match_result = match(
                user_location=user_location,
                departments=departments,
                preferences=_extract_preferences(user_input, user_profile),
            )
            result["steps"]["match"] = match_result
            candidates = match_result.get("candidates", [])
            if not candidates:
                result["status"] = "no_hospitals_found"
                result["error"] = "附近未找到符合条件的医院，请尝试放宽条件或修改位置"
                return result

            if not selected_hospital:
                result["status"] = "awaiting_hospital_selection"
                result["final_output"] = {
                    "candidates": candidates,
                    "message": "以下是附近医院候选，请告知您选择哪一家：",
                }
                return result

            # Step 4: 挂号链接
            hospital_info = next(
                (h for h in candidates if h.get("hospital_name") == selected_hospital),
                {"hospital_name": selected_hospital, "address": "", "yixue_url": ""},
            )
            reg_result = fetch(
                hospital_name=selected_hospital,
                department=departments[0],
                user_location=user_location,
                yixue_url=hospital_info.get("yixue_url", ""),
            )
            result["steps"]["registration"] = reg_result

            # Step 5: 行程单生成
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
            result["final_output"] = {
                "pdf_path": itinerary_result.get("pdf_path", ""),
                "depart_time": itinerary_result.get("depart_time", ""),
                "route": itinerary_result.get("route_summary", {}),
                "registration_url": reg_result.get("registration_url", ""),
            }
            return result

        except Exception as e:
            import traceback

            logger.error("[智枢] 执行失败: %s", e)
            result["status"] = "error"
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            return result

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "skills": [
                "healthpath-intent-understanding",
                "healthpath-symptom-triage",
                "healthpath-hospital-matcher",
                "healthpath-registration-fetcher",
                "healthpath-itinerary-builder",
                "baidu-ai-map（底层地图能力）",
            ],
        }


def _extract_preferences(text: str, profile: Optional[dict]) -> dict:
    prefs: dict = {
        "hospital_level": "三甲",
        "max_distance_km": 15,
        "travel_mode": "transit",
    }

    if any(kw in text for kw in ["最近", "近的", "附近", "就近", "离我近", "走路"]):
        prefs["max_distance_km"] = 6
        prefs["travel_mode"] = "walking"
    elif any(kw in text for kw in ["10公里", "10km", "不太远"]):
        prefs["max_distance_km"] = 10

    if any(kw in text for kw in ["开车", "自驾", "驾车"]):
        prefs["travel_mode"] = "driving"
    elif any(kw in text for kw in ["地铁", "公交", "公共交通"]):
        prefs["travel_mode"] = "transit"

    if profile:
        age_group = profile.get("age_group", "adult")
        if age_group == "elderly":
            prefs["max_distance_km"] = min(prefs["max_distance_km"], 10)
        elif age_group == "child":
            prefs["hospital_level"] = "不限"

    return prefs


_agent: Optional[HealthPathAgent] = None


def _get_agent() -> HealthPathAgent:
    global _agent
    if _agent is None:
        _agent = HealthPathAgent()
    return _agent


def execute(user_input: str, **kwargs) -> Dict[str, Any]:
    return _get_agent().execute(user_input=user_input, **kwargs)


def get_info() -> Dict[str, Any]:
    return _get_agent().get_info()
