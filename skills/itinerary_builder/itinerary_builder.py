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
    生成 PDF 行程单。
    优先使用 reportlab（需安装），降级为纯文本文件。
    """
    filename = f"itinerary_{timestamp}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    large_font = (output_format == "large_font_pdf")

    try:
        _generate_pdf_reportlab(
            filepath=filepath,
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
            large_font=large_font,
        )
        logger.info(f"[itinerary_builder] PDF 生成成功: {filepath}")
    except Exception as e:
        logger.warning(f"[itinerary_builder] reportlab 生成失败: {e}，降级为文本")
        filepath = filepath.replace(".pdf", ".txt")
        _generate_text_fallback(
            filepath, hospital_name, department,
            registration_info, appointment_time, route,
            depart_time, checklist, nav_steps, age_group
        )

    return filepath


def _generate_pdf_reportlab(filepath, hospital_name, hospital_address,
                             department, registration_info, appointment_time,
                             route, depart_time, checklist, nav_steps,
                             age_group, large_font):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # 中文字体注册
    font_name = _register_chinese_font()

    # 字号
    if large_font:
        T, H, N, S = 26, 18, 16, 13
    else:
        T, H, N, S = 18, 14, 12, 10

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            rightMargin=0.6*inch, leftMargin=0.6*inch,
                            topMargin=0.8*inch, bottomMargin=0.8*inch)

    def style(name, size, color="#333333", align=TA_LEFT, bold=False):
        return ParagraphStyle(name, fontName=font_name, fontSize=size,
                              textColor=colors.HexColor(color),
                              spaceAfter=8, leading=size+5, alignment=align)

    title_s   = style("Title",   T,  "#FF6B6B", TA_CENTER)
    heading_s = style("Heading", H,  "#FF6B6B")
    normal_s  = style("Normal",  N)
    small_s   = style("Small",   S,  "#666666")

    elems = []
    icon = "👵" if age_group == "elderly" else ("🚀" if age_group == "adult" else "🚑")
    elems.append(Paragraph(f"{icon} 就医行程单", title_s))
    elems.append(Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", small_s))
    elems.append(Spacer(1, 0.1*inch))

    # 就诊核心信息
    elems.append(Paragraph("🏥 就诊信息", heading_s))
    reg = registration_info or {}
    info_rows = [
        ["医院",   hospital_name],
        ["科室",   department],
        ["地址",   hospital_address or "请以医院官网为准"],
        ["预约时间", appointment_time or "请自行确认"],
        ["挂号平台", reg.get("registration_platform", "—")],
        ["挂号链接", reg.get("registration_url", "—")],
        ["挂号注意", reg.get("booking_note", "—")],
    ]
    tbl = Table(info_rows, colWidths=[1.4*inch, 4.2*inch])
    tbl.setStyle(TableStyle([
        ("FONT",        (0,0), (-1,-1), font_name, N),
        ("TEXTCOLOR",   (0,0), (0,-1),  colors.HexColor("#FF6B6B")),
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("LINEBELOW",   (0,0), (-1,-1), 0.4, colors.HexColor("#EEEEEE")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING",  (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ]))
    elems.append(tbl)
    elems.append(Spacer(1, 0.15*inch))

    # 出行信息
    elems.append(Paragraph("🚗 出行方案", heading_s))
    elems.append(Paragraph(
        f"建议出发时间：{depart_time}  |  预计用时：{route['duration_min']} 分钟  |  "
        f"距离：{route['distance_km']} km  |  方式：{route['mode']}",
        normal_s
    ))
    elems.append(Paragraph(f"路线导航：{route['map_url']}", small_s))
    if route.get("description"):
        elems.append(Paragraph(route["description"], normal_s))
    elems.append(Spacer(1, 0.15*inch))

    # 携带清单
    elems.append(Paragraph("🎒 出门前请确认", heading_s))
    elems.append(Paragraph("(可以照着打个勾 ✅)", small_s))
    for item_dict in checklist:
        note = f"  — {item_dict['note']}" if item_dict["note"] else ""
        elems.append(Paragraph(f"[ ] {item_dict['item']}{note}", normal_s))
    elems.append(Spacer(1, 0.15*inch))

    # 院内导引
    elems.append(Paragraph("🚶 到了医院怎么走", heading_s))
    for step in nav_steps:
        elems.append(Paragraph(step, normal_s))
    elems.append(Spacer(1, 0.15*inch))

    # 免责
    elems.append(Paragraph(
        "❤️ 祝您就医顺利！本行程单仅供参考，具体挂号与就诊以医院官方为准。",
        small_s
    ))

    doc.build(elems)


def _register_chinese_font() -> str:
    """注册中文字体，返回字体名称"""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        paths = [
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simsun.ttc",
        ]
        for path in paths:
            if os.path.exists(path):
                name = os.path.splitext(os.path.basename(path))[0].upper()
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    return name
                except Exception:
                    continue
    except Exception:
        pass
    return "Helvetica"


def _generate_text_fallback(filepath, hospital_name, department,
                             registration_info, appointment_time, route,
                             depart_time, checklist, nav_steps, age_group):
    """reportlab 不可用时输出纯文本行程单"""
    reg = registration_info or {}
    lines = [
        "=" * 60,
        f"  就医行程单  ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
        "=" * 60,
        "",
        "【就诊信息】",
        f"  医院：{hospital_name}",
        f"  科室：{department}",
        f"  预约时间：{appointment_time or '请自行确认'}",
        f"  挂号平台：{reg.get('registration_platform', '—')}",
        f"  挂号链接：{reg.get('registration_url', '—')}",
        f"  注意事项：{reg.get('booking_note', '—')}",
        "",
        "【出行方案】",
        f"  建议出发：{depart_time}",
        f"  预计时间：{route['duration_min']} 分钟",
        f"  导航链接：{route['map_url']}",
        "",
        "【出门前请确认】",
    ]
    for item_dict in checklist:
        note = f"（{item_dict['note']}）" if item_dict["note"] else ""
        lines.append(f"  [ ] {item_dict['item']}{note}")
    lines += ["", "【院内导引】"]
    for step in nav_steps:
        lines.append(f"  {step}")
    lines += [
        "",
        "=" * 60,
        "祝您就医顺利！本行程单仅供参考，具体挂号与就诊以医院官方为准。",
        "=" * 60,
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


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
