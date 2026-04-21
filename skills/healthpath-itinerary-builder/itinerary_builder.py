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
import re
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_ROOT          = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SKILL_DIR     = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR     = os.path.join(_ROOT, "output")                           # PDF 输出目录
HISTORY_PATH   = os.path.join(_SKILL_DIR, "user_history.json")          # 就医历史记录（本 skill 私有）

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
          user_profile: Optional[dict] = None,
          doctor_schedule: Optional[dict] = None) -> dict:
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

    # 4.5 医生 & 推荐注入 ─────────────────────────────────────────────
    if doctor_schedule:
        doctor = doctor_schedule.get("doctor") or {}
        rec = doctor_schedule.get("recommendation")
        warning = doctor_schedule.get("warning")
        if doctor.get("name"):
            doctor_line = f"【医生】{doctor['name']}"
            if doctor.get("title"):
                doctor_line += f" ({doctor['title']})"
            if doctor.get("specialty"):
                doctor_line += f",擅长:{doctor['specialty']}"
            nav_steps.insert(0, doctor_line)
        if rec:
            rec_line = f"【建议就诊】{rec.get('date', '')} {rec.get('period', '')}"
            if rec.get("reason"):
                rec_line += f" — {rec['reason']}"
            nav_steps.insert(1 if doctor.get("name") else 0, rec_line)
        if warning:
            nav_steps.insert(0, f"【提示】{warning}")

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
        doctor_schedule=doctor_schedule,
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

def _geocode(address: str, token: str) -> Optional[dict]:
    """地理编码：地址字符串 → {lat, lng, name, address}。失败返回 None。"""
    import requests
    url = "https://api.map.baidu.com/agent_plan/v1/geocoding"
    try:
        resp = requests.get(
            url,
            params={"address": address},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result") or {}
        loc = result.get("location") or {}
        
        geo_data = {}
        if loc.get("lat") and loc.get("lng"):
            geo_data = {"lat": loc["lat"], "lng": loc["lng"]}
            
            # 提取更详尽的信息以增强后面 direction API 的匹配度
            poi_list = data.get("poi_infos", [])
            if poi_list:
                first_poi = poi_list[0]
                geo_data["name"] = first_poi.get("name")
                geo_data["address"] = first_poi.get("formatted_address")
            elif result.get("level"):
                # 如果是地址级别解析
                geo_data["address"] = address # 兜底
                
            return geo_data
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[itinerary_builder] 地理编码失败: {e}")
    return None

def _plan_route(origin: str, dest: str, token: str = None, depth: int = 0) -> dict:
    """
    调用百度地图 Agent Plan API 获取真实的路线规划。
    """
    import os
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    
    # 默认值（降级）
    dist_est = 5.0
    fallback = {
        "mode":         "建议路线",
        "distance_km":  f"{dist_est:.1f}",
        "duration_min": int(dist_est * 4),
        "description":  f"请使用手机导航前往 {dest}",
        "map_url":      _map_url(origin, dest),
        "source":       "估算",
    }
    
    if depth > 1:
        return fallback

    if not token:
        token = os.getenv("BAIDU_MAP_AUTH_TOKEN")
    
    if not token:
        import logging
        logging.getLogger(__name__).warning("No BAIDU_MAP_AUTH_TOKEN found, using fallback route.")
        return fallback

    try:
        url = "https://api.map.baidu.com/agent_plan/v1/direction"
        headers = {"Authorization": f"Bearer {token}"}
        
        # 尝试地理编码 origin 和 dest 以获得精准坐标和名称
        origin_geo = _geocode(origin, token)
        dest_geo = _geocode(dest, token)
        
        # 使用地理编码后的精准名称作为请求（如果有）
        precise_origin = f"{origin_geo['name']}({origin_geo['address']})" if origin_geo and origin_geo.get('name') else origin
        precise_dest = f"{dest_geo['name']}({dest_geo['address']})" if dest_geo and dest_geo.get('name') else dest
        
        # location 提示优先给起点
        loc_str = f"{origin_geo['lat']},{origin_geo['lng']}" if origin_geo else "23.1291,113.2644"
        
        # 优化请求
        data = {
            "user_raw_request": f"帮我从{precise_origin}去{precise_dest}，请提供详细的公交或地铁换乘方案",
            "location": loc_str
        }
        res = requests.post(url, headers=headers, data=data, timeout=10)
        if res.status_code == 200:
            res_data = res.json()
            if res_data.get("status") == 0 and "result" in res_data:
                result_obj = res_data["result"]
                ans = result_obj.get("answer", "")
                
                # 若遇到 POI 澄清 (gptmodel_poi_clarify)
                if result_obj.get("answer_type") == "gptmodel_poi_clarify":
                    pois = result_obj.get("poi_clarify_data", {}).get("data", [])
                    if pois:
                        p = pois[0]
                        info = p.get("info", {})
                        name = info.get("name", "")
                        addr = info.get("address", "")
                        # 构造更精确的名称
                        recursive_name = f"{name}({addr})" if addr else name
                        
                        # 记录距离作为最后底线
                        dist_val = p.get("route", {}).get("distance_local", 0)
                        if dist_val > 0:
                            fallback["distance_km"] = f"{dist_val/1000.0:.1f}"
                            fallback["description"] = f"预计距离大约 {dist_val/1000.0:.1f} 公里，由于位置重名较多，请在手机打开导航详情。"

                        # 递归尝试
                        if name and name != origin:
                            return _plan_route(origin, recursive_name, token, depth + 1)
                        else:
                            return _plan_route(recursive_name, dest, token, depth + 1)

                # 解析 navigation_data 中的详细步骤
                if "navigation_data" in result_obj:
                    nav_data = result_obj["navigation_data"]
                    
                    # 优先看公交方案，过滤掉纯骑行/长距离步行（对病患不友善）
                    best_route = None
                    for key in ["public_routes", "driving_routes", "walking_routes", "cycling_routes", "routes"]:
                        if key in nav_data and nav_data[key]:
                            candidate_routes = nav_data[key]
                            for r in candidate_routes:
                                # 检查是否有公交/地铁步骤 (vehicle_info type 为 3)
                                has_transit = False
                                for leg in r.get("steps", []):
                                    steps_to_check = leg if isinstance(leg, list) else [leg]
                                    for s in steps_to_check:
                                        v_info = s.get("vehicle_info", {})
                                        v_detail = v_info.get("detail", {}) if isinstance(v_info, dict) else {}
                                        v_type = v_info.get("type") if isinstance(v_info, dict) else None
                                        
                                        # 必须是 transit 类型且有线路名称，或者指令包含公交/地铁关键词
                                        if v_type == 3 and isinstance(v_detail, dict) and v_detail.get("name"):
                                            has_transit = True
                                            break
                                        if any(k in s.get("instructions", "") for k in ["公交", "地铁", "乘坐", "换乘", "站"]):
                                            has_transit = True
                                            break
                                    if has_transit: break
                                if has_transit:
                                    best_route = r
                                    break
                            
                            if not best_route:
                                best_route = candidate_routes[0]
                            break
                            
                    if best_route:
                        total_dist = best_route.get("distance", 0) / 1000.0
                        total_dur = best_route.get("duration", 0) // 60
                        
                        instructions = []
                        raw_steps = best_route.get("steps", [])
                        normalized_steps = []
                        for leg in raw_steps:
                            if isinstance(leg, list):
                                if not leg:
                                    continue
                                step = leg[0]
                            else:
                                step = leg

                            if isinstance(step, dict):
                                normalized_steps.append(step)

                        for idx, step in enumerate(normalized_steps):
                            next_step = normalized_steps[idx + 1] if idx + 1 < len(normalized_steps) else None

                            inst = step.get("instructions", "").strip()
                            v_info = step.get("vehicle_info", {})
                            detail = v_info.get("detail") if isinstance(v_info, dict) else None
                            
                            if detail and isinstance(detail, dict):
                                if len(inst) < 5:
                                    line_name = detail.get("name", "")
                                    on_station = detail.get("on_station", "")
                                    stop_num = detail.get("stop_num", 0)
                                    if line_name and on_station:
                                        inst = f"在 {on_station} 乘坐 {line_name} (经过{stop_num}站)"
                            
                            if not inst:
                                road = step.get("road_name")
                                dist = step.get("distance")
                                if road and road != "无名路":
                                    inst = f"沿 {road} 前行 {dist}米" if dist else f"进入 {road}"
                                elif dist:
                                    inst = f"前行 {dist}米"

                            inst = _augment_route_instruction(
                                inst=inst,
                                step=step,
                                next_step=next_step,
                                is_last=(idx == len(normalized_steps) - 1),
                                final_destination=dest,
                            )

                            if inst:
                                instructions.append(inst)
                        
                        ans_detail = ""
                        if instructions:
                            unique_inst = []
                            for i in instructions:
                                if not unique_inst or i != unique_inst[-1]:
                                    unique_inst.append(i)
                            ans_detail = " -> ".join(unique_inst)
                        else:
                            ans_detail = nav_data.get("info", {}).get("tts_tips", "") or ans
                            
                        if not ans_detail:
                            ans_detail = f"建议行程 {total_dist:.1f} 公里，预计 {total_dur} 分钟。"

                        # 智能识别交通方式
                        travel_mode = _detect_travel_mode(ans_detail, best_route)

                        return {
                            "mode":         travel_mode,
                            "distance_km":  f"{total_dist:.1f}",
                            "duration_min": total_dur,
                            "description":  ans_detail,
                            "map_url":      _map_url(origin, dest),
                            "source":       "百度地图MCP",
                        }
                        
                if ans:
                    return {
                        "mode":         "建议路线",
                        "distance_km":  "", 
                        "duration_min": "",
                        "description":  ans,
                        "map_url":      _map_url(origin, dest),
                        "source":       "百度地图MCP",
                    }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Baidu Map API error: {e}")
        
    return fallback


def _detect_travel_mode(description: str, route_data: dict) -> str:
    """
    从路线描述和路线数据中智能识别交通方式。

    优先级：地铁 > 公交 > 打车/驾车 > 步行
    """
    import re

    desc_lower = description.lower()

    # 检查是否包含地铁
    if "地铁" in description or "号线" in description:
        # 提取地铁线路
        lines = re.findall(r'(\d+号线|[一二三四五六七八九十]+号线)', description)
        if lines:
            return f"地铁（{lines[0]}等）"
        return "地铁"

    # 检查是否包含公交
    if "公交" in description or "路公交" in description or re.search(r'\d+路', description):
        return "公交"

    # 检查是否为打车/驾车
    if any(kw in description for kw in ["打车", "驾车", "开车", "自驾"]):
        return "打车/驾车"

    # 检查步行距离
    if "步行" in description:
        # 如果主要是步行（距离较短）
        steps = route_data.get("steps", []) if isinstance(route_data, dict) else []
        if steps:
            # 检查是否大部分是步行
            walk_count = sum(1 for s in steps if isinstance(s, dict) and "步行" in s.get("instructions", ""))
            if walk_count > len(steps) * 0.7:  # 70%以上是步行
                return "步行"

    # 默认返回公共交通
    return "公共交通"


def _augment_route_instruction(inst: str, step: dict, next_step: Optional[dict],
                               is_last: bool, final_destination: str) -> str:
    """给步行/骑行等非公交步骤补充目的地，提升可读性。"""
    if not inst:
        return inst

    # 公交地铁步骤一般已包含上下车信息，不做改写
    if "乘坐" in inst or "站" in inst and "经过" in inst:
        return inst

    # 已包含“到”则不重复拼接
    if "到" in inst:
        return inst

    # 仅增强非公交移动步骤
    movable = ("步行", "骑行", "前行", "沿 ")
    if not any(inst.startswith(prefix) for prefix in movable):
        return inst

    target = _guess_step_target(step, next_step, is_last, final_destination)
    if not target:
        target = "下一换乘点" if not is_last else "目的地"

    # 统一把“前行/沿路前行”改成“步行xx到xxx”
    if inst.startswith("前行") or inst.startswith("沿 "):
        dist_text = _extract_distance_text(step, inst)
        return f"步行{dist_text}到{target}" if dist_text else f"步行到{target}"

    # 步行/骑行补尾部目的地
    return f"{inst}到{target}"


def _extract_distance_text(step: dict, inst: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)?)(公里|米)", inst)
    if m:
        return m.group(0)
    dist = step.get("distance")
    if isinstance(dist, (int, float)) and dist > 0:
        if dist >= 1000:
            return f"{dist / 1000:.1f}公里"
        return f"{int(dist)}米"
    return ""


def _guess_step_target(step: dict, next_step: Optional[dict], is_last: bool, final_destination: str) -> str:
    # 先看当前 step 是否有明确终点字段
    for k in ("end_name", "end_poi_name", "destination", "arrive_name", "to_name"):
        v = step.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # 再尝试直接从当前文案里提取终点名
    target_from_inst = _extract_target_from_instruction(step.get("instructions", ""))
    if target_from_inst:
        return target_from_inst

    # 再尝试从下一段公交信息中推断“前往上车站”
    if next_step and isinstance(next_step, dict):
        v_info = next_step.get("vehicle_info", {})
        detail = v_info.get("detail", {}) if isinstance(v_info, dict) else {}
        on_station = detail.get("on_station") if isinstance(detail, dict) else ""
        if isinstance(on_station, str) and on_station.strip():
            return on_station.strip()

        # 非公交下一段也继续向前追一个明确地点，避免出现“下一换乘点”
        next_target = _guess_step_target(
            step=next_step,
            next_step=None,
            is_last=is_last,
            final_destination=final_destination,
        )
        if next_target:
            return next_target

    # 最后一段默认到目的地
    if is_last and final_destination:
        return final_destination
    return final_destination or ""


def _extract_target_from_instruction(inst: str) -> str:
    if not inst:
        return ""

    patterns = [
        r"到([^->，。]+?站)",
        r"到([^->，。]+?(?:医院|门诊部|大厦|广场|园区|校区|中心|目的地))",
    ]
    for pattern in patterns:
        m = re.search(pattern, inst)
        if m:
            return m.group(1).strip()
    return ""


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
    """生成院内导引步骤（详细版，包含具体分析）"""
    platform  = reg_info.get("registration_platform", "医院系统")
    reg_url   = reg_info.get("registration_url", "")

    steps = [
        f"【取号】进入{hospital_name}大厅，前往1楼「人工挂号/收费窗口」或自助机，出示医保卡并说明已在{platform}预约，领取号条。如未预约，现场挂号需排队约15-30分钟。",
        f"【找科室】按门诊楼导引牌，找到【{department}候诊区】。大型三甲医院通常在2-3楼设专科门诊，部分医院{department}可能在独立楼层，建议到达后询问导医台。",
        f"【签到候诊】在{department}护士台或自助签到机完成签到（需刷医保卡或扫码），然后坐等屏幕叫号。高峰时段（8:00-10:00）候诊时间较长，建议提前30分钟到达。",
        "【就诊】医生叫到您的名字后进入诊室，将携带的检查报告、既往病历一并交给医生。就诊时长通常5-15分钟，请提前整理好症状描述和想咨询的问题。",
        "【缴费/检查】根据医生开具的处方或检查单，按导引牌前往缴费窗口（或使用手机支付），然后到相应科室完成检查项目。抽血化验通常在1楼检验科，影像检查（X光/CT/MRI）在放射科，需提前预约时间段。",
        "【取药/复诊】缴费后凭处方到药房取药（门诊药房通常在1楼），如需复诊请在护士台预约下次就诊时间。慢性病患者可咨询是否支持线上复诊和药品配送。",
    ]

    if reg_url:
        steps.insert(0, f"【提前准备】如尚未挂号，请访问 {reg_url} 完成预约。建议提前1-3天预约，热门专家号需提前7天抢号。")

    return steps


# ── PDF 生成 ──────────────────────────────────────────────────────────────

def _generate_pdf(hospital_name, hospital_address, department,
                  registration_info, appointment_time, route,
                  depart_time, checklist, nav_steps,
                  age_group, output_format, timestamp,
                  doctor_schedule=None) -> str:
    """
    生成 PDF 行程单，调用当前目录下的 pdf_generator.py。
    """
    from pdf_generator import generate_pdf_document

    filename = f"itinerary_{timestamp}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    large_font = (output_format == "large_font_pdf")

    reg = registration_info or {}
    ds = doctor_schedule or {}
    ds_doctor = ds.get("doctor") or {}
    ds_rec = ds.get("recommendation") or {}

    # doctor_schedule 优先,否则从 registration_info 兜底
    rec_doctor_name  = ds_doctor.get("name")  or reg.get("doctor_name", "")
    rec_doctor_title = ds_doctor.get("title") or reg.get("doctor_title", "")

    # 就诊时间:优先用显式 appointment_time;缺省时用推荐的 date+period
    rec_appointment = appointment_time or ""
    if not rec_appointment and ds_rec.get("date"):
        rec_appointment = f"{ds_rec['date']} {ds_rec.get('period', '')}".strip()

    recommendations = [{
        "rank":                 1,
        "hospital_name":        hospital_name,
        "doctor_name":          rec_doctor_name,
        "doctor_title":         rec_doctor_title,
        "doctor_specialty":     ds_doctor.get("specialty", ""),
        "appointment_time":     rec_appointment,
        "total_cost":           reg.get("total_cost", 0),
        "total_travel_time_min": route.get("duration_min", 30),
        "distance_km":          route.get("distance_km", 0),
        "queue_estimate_min":   reg.get("queue_estimate_min", 30),
        "score":                reg.get("score", 0),
        "reason":               ds_rec.get("reason", "") or route.get("description", ""),
    }]
    task_params = {
        "department":           department,
        "symptom":              reg.get("symptom", ""),
        "time_window":          appointment_time or "",
        "travel_preference":    route.get("mode", ""),
        # 路线规划
        "route_mode":           route.get("mode", ""),
        "route_duration_min":   str(route.get("duration_min", "")),
        "route_distance_km":    str(route.get("distance_km", "")),
        "route_description":    route.get("description", ""),
        "route_map_url":        route.get("map_url", ""),
        "depart_time":          depart_time,
        # 挂号信息
        "registration_url":     reg.get("registration_url", ""),
        "registration_platform": reg.get("registration_platform", ""),
        "booking_note":         reg.get("booking_note", ""),
        "hospital_address":     hospital_address or "",
        # 院内导引
        "nav_steps":            nav_steps,
        # 出行清单（按年龄定制）
        "checklist":            checklist,
        # 医生与推荐(pdf_generator 可选读取)
        "doctor_name":          ds_doctor.get("name", ""),
        "doctor_title":         ds_doctor.get("title", ""),
        "doctor_specialty":     ds_doctor.get("specialty", ""),
        "recommended_date":     ds_rec.get("date", ""),
        "recommended_period":   ds_rec.get("period", ""),
        "recommendation_reason": ds_rec.get("reason", ""),
    }

    generate_pdf_document(recommendations, task_params, filepath, large_font=large_font)
    logger.info(f"[itinerary_builder] PDF 生成成功: {filepath}")
    return filepath


# ── 历史记录 ──────────────────────────────────────────────────────────────

def _save_history(hospital_name, hospital_address, department,
                  registration_info, route) -> None:
    """将本次就医信息写入 skills/itinerary_builder/user_history.json"""
    try:
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
    except Exception as e:
        logger.warning("[itinerary_builder] 写入历史失败，已忽略: %s", e)


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
