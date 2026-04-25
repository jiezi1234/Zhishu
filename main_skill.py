"""
main_skill.py — 智枢——基于长链路协同的全人群医旅调度智能体 主入口

统一 6 步流程：
  1) healthpath-intent-understanding
  2) healthpath-symptom-triage（用户已明确科室可跳过）
  3) healthpath-hospital-matcher
  4) healthpath-registration-fetcher
  5) healthpath-doctor-schedule（autoclaw 抓医生出诊表+号源,推荐就诊时段）
  6) healthpath-itinerary-builder
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
    "healthpath-doctor-schedule",
    "healthpath-itinerary-builder",
]:
    sys.path.insert(0, os.path.join(_ROOT, "skills", skill_dir))

from intent_parser import parse_intent
from symptom_triage import triage
from hospital_matcher import match
from registration_fetcher import fetch
import doctor_schedule as doctor_schedule_mod
from itinerary_builder import build


class HealthPathAgent:
    name = "智枢"
    display_name = "智枢"
    version = "3.0.0"
    description = "基于长链路协同的全人群医旅调度智能体"

    def execute(
        self,
        user_input: str,
        user_location: Optional[str] = None,
        selected_hospital: Optional[str] = None,
        selected_doctor: Optional[str] = None,
        browser_resume: Optional[dict] = None,
        confirmed_appointment: Optional[dict] = None,
        extra_answers: Optional[dict] = None,
        output_format: str = "large_font_pdf",
        user_profile: Optional[dict] = None,
    ) -> Dict[str, Any]:
        logger.info("[HealthPath] processing: %s", user_input[:80])
        result: Dict[str, Any] = {
            "status": "success",
            "steps": {},
            "final_output": None,
            "follow_up": [],
            "error": None,
        }

        try:
            # Step 1: intent understanding
            intent_result = parse_intent(user_input, use_deepseek=True)
            result["steps"]["intent"] = intent_result

            explicit_dept = (intent_result or {}).get("department", "")
            has_explicit_dept = bool(
                explicit_dept and explicit_dept not in {"未指定", "unknown", "unspecified"}
            )

            # 自动回填：用户在原文已说出位置,无需再问
            if not user_location:
                loc_from_intent = (intent_result or {}).get("user_location", "")
                if loc_from_intent:
                    user_location = loc_from_intent
                    logger.info("[智枢] 从 intent 自动回填 user_location: %s", user_location)

            intent_target_hospital = (intent_result or {}).get("target_hospital", "") or ""

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
                    "disclaimer": "以上仅供参考，不替代执业医师诊断。",
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
                        "message": "检测到急症信号，请立即前往急诊或拨打120。",
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
                        "question": "请告诉我您当前所在区域（如：北京市海淀区），以便推荐附近医院。",
                    }
                ]
                return result

            # Step 3: hospital matching
            match_result = match(
                user_location=user_location,
                departments=departments,
                preferences=_extract_preferences(user_input, user_profile),
            )
            result["steps"]["match"] = match_result
            candidates = match_result.get("candidates", [])

            if not candidates:
                result["status"] = "no_hospitals_found"
                result["error"] = "附近未找到符合条件的医院，请调整条件后重试。"
                return result

            if not selected_hospital:
                # 原文已指定医院,且在候选中 → 自动选
                if intent_target_hospital:
                    for cand in candidates:
                        name = cand.get("hospital_name", "")
                        if (name == intent_target_hospital
                                or intent_target_hospital in name
                                or name in intent_target_hospital):
                            selected_hospital = name
                            logger.info(
                                "[智枢] 从 intent 自动选择医院: %s", selected_hospital
                            )
                            break

                if not selected_hospital:
                    result["status"] = "awaiting_hospital_selection"
                    msg = "以下是附近医院候选，请告知您选择哪一家："
                    if intent_target_hospital:
                        msg = (
                            f"您提到的「{intent_target_hospital}」未出现在本次匹配的附近医院列表中，"
                            "请从以下候选里选择，或告诉我扩大搜索范围："
                        )
                    result["final_output"] = {
                        "candidates": candidates,
                        "message": msg,
                    }
                    return result

            # Step 4: registration info
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

            # Step 5: 医生出诊表 + 号源 + 推荐
            doctor_name = (
                selected_doctor
                or (intent_result or {}).get("doctor_name", "")
            )
            registration_url = (
                reg_result.get("registration_url")
                or reg_result.get("official_url")
                or ""
            )
            user_prefs_for_rec = {
                "time_window": (intent_result or {}).get("time_window", ""),
                "preferred_period": "",
            }

            doctor_step_result = None

            if registration_url:
                if doctor_name:
                    doctor_step_result = doctor_schedule_mod.fetch_doctor_schedule(
                        hospital_name=selected_hospital,
                        doctor_name=doctor_name,
                        registration_url=registration_url,
                        user_preferences=user_prefs_for_rec,
                        browser_resume=browser_resume,
                    )
                else:
                    doctor_step_result = doctor_schedule_mod.list_experts(
                        hospital_name=selected_hospital,
                        department=departments[0],
                        registration_url=registration_url,
                        browser_resume=browser_resume,
                    )

            if doctor_step_result is not None:
                result["steps"]["doctor_schedule"] = doctor_step_result
                ds_status = doctor_step_result.get("status")

                if ds_status == "awaiting_browser_interaction":
                    result["status"] = "awaiting_browser_interaction"
                    result["final_output"] = {
                        "browser_session": doctor_step_result.get("browser_session"),
                        "interact_prompt": doctor_step_result.get("interact_prompt", ""),
                    }
                    result["follow_up"] = [{
                        "id": "browser_interaction",
                        "question": doctor_step_result.get("interact_prompt", "")
                                    or "浏览器窗口里有一个待操作项,请完成后告诉我继续",
                    }]
                    return result

                if ds_status == "success" and "experts" in doctor_step_result:
                    result["status"] = "awaiting_doctor_selection"
                    result["final_output"] = {
                        "experts": doctor_step_result["experts"],
                        "message": "以下是该科室出诊专家,请告诉我选择哪一位:",
                    }
                    return result

                if ds_status == "schedule_fetched_but_full":
                    result["status"] = "schedule_fetched_but_full"
                    result["warning"] = doctor_step_result.get("warning", "")

                if ds_status == "doctor_not_found":
                    result["status"] = "doctor_not_found"
                    result["follow_up"] = [{
                        "id": "doctor_name_clarify",
                        "question": doctor_step_result.get("error", "未找到该医生,请确认姓名"),
                    }]
                    return result

                if (ds_status == "success"
                        and doctor_step_result.get("schedule") is not None
                        and not confirmed_appointment):
                    result["status"] = "doctor_schedule_fetched"
                    result["final_output"] = {
                        "schedule": doctor_step_result.get("schedule"),
                        "recommendation": doctor_step_result.get("recommendation"),
                        "alternatives": doctor_step_result.get("alternatives", []),
                        "message": "已获取医生出诊表与号源,请确认推荐的就诊时间或选择备选",
                    }
                    return result

            # Step 6: 行程单生成
            appointment_time = None
            if confirmed_appointment:
                date_s = confirmed_appointment.get("date", "")
                slot_s = confirmed_appointment.get("time_slot", "")
                if date_s and slot_s:
                    time_map = {"上午": "09:00", "下午": "14:00"}
                    hhmm = time_map.get(slot_s, slot_s)
                    appointment_time = f"{date_s} {hhmm}"

            doctor_ctx = None
            if doctor_step_result and doctor_step_result.get("status") in (
                "success", "schedule_fetched_but_full"
            ):
                doctor_ctx = {
                    "doctor": (doctor_step_result.get("schedule") or {}).get("doctor"),
                    "recommendation": doctor_step_result.get("recommendation"),
                    "warning": doctor_step_result.get("warning"),
                }

            itinerary_result = build(
                user_location=user_location,
                hospital_name=selected_hospital,
                hospital_address=hospital_info.get("address", ""),
                department=departments[0],
                registration_info=reg_result,
                appointment_time=appointment_time,
                output_format=output_format,
                user_profile=user_profile,
                doctor_schedule=doctor_ctx,
            )
            result["steps"]["itinerary"] = itinerary_result
            result["final_output"] = {
                "pdf_path": itinerary_result.get("pdf_path", ""),
                "depart_time": itinerary_result.get("depart_time", ""),
                "route": itinerary_result.get("route_summary", {}),
                "registration_url": reg_result.get("registration_url", ""),
                "doctor": (doctor_ctx or {}).get("doctor"),
                "recommendation": (doctor_ctx or {}).get("recommendation"),
            }
            return result

        except Exception as e:
            import traceback

            logger.error("[HealthPath] execution failed: %s", e)
            result["status"] = "error"
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            return result

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "skills": [
                "healthpath-intent-understanding",
                "healthpath-symptom-triage",
                "healthpath-hospital-matcher",
                "healthpath-registration-fetcher",
                "healthpath-doctor-schedule",
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
