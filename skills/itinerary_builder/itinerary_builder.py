"""
itinerary_builder.py — 路线规划与就医行程单生成

职责：
  1. 调用百度地图 MCP 规划出行路线（驾车/公交/步行）
  2. 计算建议出发时间（含院内签到缓冲）
  3. 用 GLM 生成个性化携带物品清单和院内导引步骤
  4. 输出 PDF 行程单（大字版/标准版），保存至项目根目录 output/
  5. 将本次就医信息持久化到 skills/itinerary_builder/user_history.json
  6. 处理用户的黑名单请求（调用 hospital_matcher.add_to_blacklist）

输入 (task_params):
  user_location       str   用户出发地
  hospital_name       str   目标医院
  hospital_address    str   医院地址
  department          str   科室
  registration_info   dict  来自 registration_fetcher 的挂号信息
  appointment_time    str   预约时间，如 "2026-04-16 09:00"（可选）
  output_format       str   "large_font_pdf" | "pdf"
  user_profile        dict  {"age_group": "elderly"|"adult"|"child"}

输出 dict:
  pdf_path      str    生成的 PDF 文件绝对路径
  depart_time   str    建议出发时间
  route_summary dict   路线摘要（方式、距离、时间）
  checklist     list   携带物品清单
  nav_steps     list   院内导引步骤
  saved_to_history bool 是否已写入用户历史
  timestamp     str
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_ROOT          = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILL_DIR     = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR     = os.path.join(_ROOT, "output")                       # PDF 输出（项目级共享目录）
HISTORY_PATH   = os.path.join(_SKILL_DIR, "user_history.json")       # 就医历史记录（本 skill 私有）

# ── 携带物品清单模板 ──────────────────────────────────────────────────────
BASE_CHECKLIST = [
    ("身份证", "千万别忘了"),
    ("医保卡 / 社保卡", ""),
    ("手机 & 充电宝", ""),
    ("钱包 / 支付宝", ""),
]

ELDERLY_EXTRA = [
    ("老花镜", ""),
    ("既往病历 / 检查报告", "带最近一次的"),
]

CHILD_EXTRA = [
    ("宝宝就诊卡 / 医保卡", ""),
    ("退烧药", "美林/泰诺林，体温超38.5℃出发前可先喂一次"),
    ("宝宝水壶", "装满温水"),
    ("备用衣物和纸尿裤", "各备一套/2片"),
    ("安抚玩具", "缓解就诊恐惧"),
]

DEPT_EXTRA_CHECKLIST = {
    "骨科":     [("影像检查片子", "带上次拍的 X 光/CT 片，装好别折叠")],
    "神经内科": [("最近做过的 MRI/CT 报告", "如有请带上")],
    "呼吸科":   [("肺功能检查报告", "如有请带上")],
    "心内科":   [("心电图报告", "如有请带上"), ("血压记录", "建议带近期血压记录本")],
    "消化科":   [("胃镜/肠镜报告", "如有请带上"), ("大便常规结果", "如有")],
    "内分泌科": [("血糖监测记录", "带上最近一周的血糖数值")],
    "眼科":     [("原有眼镜", "带上目前戴的眼镜")],
}


def build(user_location: str,
          hospital_name: str,
          hospital_address: str,
          department: str,
          registration_info: dict,
          appointment_time: Optional[str] = None,
          output_format: str = "large_font_pdf",
          user_profile: Optional[dict] = None) -> dict:
    """
    构建完整的就医行程单并生成 PDF。

    Returns
    -------
    dict — 见模块级文档
    """
    user_profile = user_profile or {}
    age_group    = user_profile.get("age_group", "adult")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    logger.info(f"[itinerary_builder] 生成行程单: {hospital_name} / {department}")

    # 1. 路线规划 ─────────────────────────────────────────────────────
    route = _plan_route(user_location, hospital_address or hospital_name)

    # 2. 推算出发时间 ─────────────────────────────────────────────────
    depart_time = _calc_depart_time(appointment_time, route["duration_min"])

    # 3. 个性化清单 ───────────────────────────────────────────────────
    checklist = _build_checklist(age_group, department)

    # 4. 院内导引 ─────────────────────────────────────────────────────
    nav_steps = _build_nav_steps(hospital_name, department, registration_info)

    # 5. 生成 PDF ──────────────────────────────────────────────────────
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path   = _generate_pdf(
        hospital_name=hospital_name,
        hospital_address=hospital_address,
        department=department,
        registration_info=registration_info,
        appointment_time=appointment_time,
        route=route,
        depart_time=depart_time,
        checklist=checklist,
        nav_steps=nav_steps,
        age_group=age_group,
        output_format=output_format,
        timestamp=timestamp,
    )

    # 6. 持久化历史 ───────────────────────────────────────────────────
    _save_history(hospital_name, hospital_address, department, registration_info, route)

    return {
        "pdf_path":         pdf_path,
        "depart_time":      depart_time,
        "route_summary":    route,
        "checklist":        checklist,
        "nav_steps":        nav_steps,
        "saved_to_history": True,
        "timestamp":        datetime.now().isoformat(),
    }


# ── 路线规划 ──────────────────────────────────────────────────────────────

def _plan_route(origin: str, dest: str) -> dict:
    """
    调用百度地图 MCP。若不可用，返回估算值+地图链接。
    """
    import urllib.parse

    try:
        from baidu_map_mcp import route as baidu_route  # type: ignore
        r = baidu_route(origin=origin, destination=dest, mode="transit")
        return {
            "mode":         "公共交通",
            "distance_km":  r.get("distance_km", 0),
            "duration_min": r.get("duration_min", 30),
            "description":  r.get("description", ""),
            "map_url":      _map_url(origin, dest),
            "source":       "百度地图MCP",
        }
    except Exception:
        pass

    # 降级：仅提供地图链接
    dist_est = 5.0
    return {
        "mode":         "公共交通（建议）",
        "distance_km":  dist_est,
        "duration_min": int(dist_est * 4),
        "description":  f"请使用手机导航前往 {dest}",
        "map_url":      _map_url(origin, dest),
        "source":       "估算",
    }


def _map_url(origin: str, dest: str) -> str:
    import urllib.parse
    o = urllib.parse.quote(origin)
    d = urllib.parse.quote(dest)
    return f"https://map.baidu.com/dir/?origin={o}&destination={d}&mode=transit"


def _calc_depart_time(appointment_time: Optional[str], travel_min: int) -> str:
    """计算建议出发时间：就诊时间 - 出行时间 - 30分钟缓冲"""
    if not appointment_time:
        return "建议就诊前 " + str(travel_min + 30) + " 分钟出发"
    try:
        appt = datetime.fromisoformat(appointment_time)
        depart = appt - timedelta(minutes=travel_min + 30)
        return depart.strftime("%m月%d日 %H:%M 出发")
    except Exception:
        return f"建议就诊前 {travel_min + 30} 分钟出发"


# ── 清单与导引 ────────────────────────────────────────────────────────────

def _build_checklist(age_group: str, department: str) -> list:
    """生成携带物品清单（含老幼特殊项和科室特殊项）"""
    items = list(BASE_CHECKLIST)

    if age_group == "elderly":
        items.extend(ELDERLY_EXTRA)
    elif age_group == "child":
        items.extend(CHILD_EXTRA)

    if department in DEPT_EXTRA_CHECKLIST:
        items.extend(DEPT_EXTRA_CHECKLIST[department])

    return [{"item": item, "note": note} for item, note in items]


def _build_nav_steps(hospital_name: str, department: str, reg_info: dict) -> list:
    """生成院内导引步骤（通用模板，后续可接入医院官网地图）"""
    platform  = reg_info.get("registration_platform", "医院系统")
    reg_url   = reg_info.get("registration_url", "")

    steps = [
        f"第一步【取号】：进入医院大厅，前往 1 楼「人工挂号/收费窗口」，出示医保卡并说明已在{platform}预约，领取号条。",
        f"第二步【找科室】：按门诊楼导引牌，找到【{department}候诊区】，通常在 2-3 楼。",
        "第三步【签到候诊】：在科室护士台或自助签到机完成签到，然后坐等屏幕叫号。",
        "第四步【就诊】：医生叫到您的名字后进入诊室，将携带的检查报告一并交给医生。",
        "第五步【缴费/检查】：根据医生开具的处方或检查单，按导引牌完成缴费和检查项目。",
    ]

    if reg_url:
        steps.insert(0, f"提前准备：如尚未挂号，请访问 {reg_url} 完成预约。")

    return steps


# ── PDF 生成 ──────────────────────────────────────────────────────────────

def _generate_pdf(hospital_name, hospital_address, department,
                  registration_info, appointment_time, route,
                  depart_time, checklist, nav_steps,
                  age_group, output_format, timestamp) -> str:
    """
    生成 PDF 行程单，调用 skill_4_output/pdf_generator.py 新版卡片风生成器。
    """
    import sys
    skill4_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "skill_4_output")
    if skill4_dir not in sys.path:
        sys.path.insert(0, skill4_dir)

    from pdf_generator import generate_pdf_document

    filename = f"itinerary_{timestamp}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    large_font = (output_format == "large_font_pdf")

    reg = registration_info or {}
    recommendations = [{
        "rank":                 1,
        "hospital_name":        hospital_name,
        "doctor_name":          reg.get("doctor_name", ""),
        "doctor_title":         reg.get("doctor_title", ""),
        "appointment_time":     appointment_time or "",
        "total_cost":           reg.get("total_cost", 0),
        "total_travel_time_min": route.get("duration_min", 30),
        "distance_km":          route.get("distance_km", 0),
        "queue_estimate_min":   reg.get("queue_estimate_min", 30),
        "score":                reg.get("score", 0),
        "reason":               route.get("description", ""),
    }]
    task_params = {
        "department":        department,
        "symptom":           reg.get("symptom", ""),
        "time_window":       appointment_time or "",
        "travel_preference": route.get("mode", ""),
    }

    generate_pdf_document(recommendations, task_params, filepath, large_font=large_font)
    logger.info(f"[itinerary_builder] PDF 生成成功: {filepath}")
    return filepath


# ── 历史记录 ──────────────────────────────────────────────────────────────

def _save_history(hospital_name, hospital_address, department,
                  registration_info, route) -> None:
    """将本次就医信息写入 skills/itinerary_builder/user_history.json"""
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    history = {}
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass

    reg = registration_info or {}
    history[hospital_name] = {
        "hospital_name":    hospital_name,
        "address":          hospital_address,
        "department":       department,
        "official_url":     reg.get("official_url", ""),
        "registration_url": reg.get("registration_url", ""),
        "platform":         reg.get("registration_platform", ""),
        "route_map_url":    route.get("map_url", ""),
        "last_visit":       datetime.now().isoformat(),
    }

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info(f"[itinerary_builder] 已写入历史: {hospital_name}")


# ── 便捷入口 ──────────────────────────────────────────────────────────────

def run(user_location: str, hospital_name: str, department: str,
        registration_info: dict, **kwargs) -> dict:
    """AutoClaw / GLM 调用的统一入口"""
    return build(
        user_location=user_location,
        hospital_name=hospital_name,
        hospital_address=kwargs.get("hospital_address", ""),
        department=department,
        registration_info=registration_info,
        appointment_time=kwargs.get("appointment_time"),
        output_format=kwargs.get("output_format", "large_font_pdf"),
        user_profile=kwargs.get("user_profile"),
    )


if __name__ == "__main__":
    import json as _json
    result = build(
        user_location="北京市朝阳区望京街道",
        hospital_name="北京协和医院",
        hospital_address="北京市东城区帅府园1号",
        department="神经内科",
        registration_info={
            "registration_url":      "https://www.bjguahao.gov.cn/hp/appoint/10.htm",
            "registration_platform": "京医通",
            "booking_note":          "周一00:00放号",
            "fee_range":             "普通号9元",
        },
        appointment_time="2026-04-16 09:00",
        output_format="large_font_pdf",
        user_profile={"age_group": "elderly"},
    )
    print(_json.dumps({k: v for k, v in result.items() if k != "nav_steps"}, ensure_ascii=False, indent=2))
    print(f"\n院内导引：")
    for s in result["nav_steps"]:
        print(f"  {s}")
