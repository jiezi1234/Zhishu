---
name: healthpath-itinerary-builder
description: Generate a printable medical appointment itinerary (PDF or plain text) including route planning, departure time, packing checklist, and in-hospital navigation steps
metadata:
  openclaw:
    emoji: "📋"
    requires:
      bins: ["python3"]
      python:
        runtime: ">=3.10"
        packages:
          - name: "reportlab"
            optional: true
            fallback: "降级为 .txt 纯文本输出，功能完整"
      env_optional: ["BAIDU_MAP_AUTH_TOKEN"]
---

# itinerary_builder — 路线规划与就医行程单生成

## 职责

整合前序 skill 的输出，生成可打印的就医行程单（PDF 或纯文本降级），并持久化本次就医记录。

具体包括：
- 调用百度地图 MCP 规划出行路线
- 按就诊时间推算建议出发时间（出行时长 + 30 分钟院内缓冲）
- 生成个性化携带物品清单（含老幼特殊项、科室特殊项）
- 生成院内导引步骤
- 输出 PDF 行程单（优先大字版），保存至 `output/`
- 将本次就医信息写入 `skills/itinerary_builder/user_history.json`

## 缓存文件（私有，不纳入版本控制）

| 文件 | 说明 |
|---|---|
| `skills/itinerary_builder/user_history.json` | 历史就医记录，以医院名为 key，记录最近一次就诊信息 |

## 何时调用

- 用户已确认目标医院、科室，且已获取挂号信息后，作为**流程最后一步**调用
- 调用前必须已经拿到 `registration_fetcher` 的返回值

## 调用方式

```python
from skills.itinerary_builder.itinerary_builder import build

result = build(
    user_location     = "北京市朝阳区望京街道",   # 必填：用户出发地
    hospital_name     = "北京协和医院",            # 必填：来自 hospital_matcher
    hospital_address  = "北京市东城区帅府园1号",   # 必填：来自 hospital_matcher
    department        = "神经内科",                 # 必填：来自 symptom_triage
    registration_info = { ... },                    # 必填：registration_fetcher 的完整返回值
    appointment_time  = "2026-04-16 09:00",         # 可选：用户预约时间（ISO 格式）
    output_format     = "large_font_pdf",           # 可选：large_font_pdf（默认）| pdf
    user_profile      = {"age_group": "elderly"},   # 可选：elderly | adult | child
)
```

## 输出字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `pdf_path` | `str` | 生成文件的绝对路径（.pdf 或降级为 .txt） |
| `depart_time` | `str` | 建议出发时间，如 "04月16日 08:10 出发" |
| `route_summary` | `dict` | 路线摘要，含 `mode` / `distance_km` / `duration_min` / `map_url` |
| `checklist` | `list[dict]` | 携带物品清单，每项含 `item` / `note` |
| `nav_steps` | `list[str]` | 院内导引步骤文本列表 |
| `saved_to_history` | `bool` | 是否已写入就医历史（正常情况恒为 `true`） |
| `timestamp` | `str` | ISO 格式时间戳 |

## 黑名单操作

用户表示不想再去某医院时，调用 `hospital_matcher` 的黑名单接口（**不要**在本 skill 内直接操作文件）：

```python
from skills.hospital_matcher.hospital_matcher import add_to_blacklist

add_to_blacklist("某医院名称", reason="用户反馈：态度差")
```

## 注意事项

- **PDF 生成**依赖 `reportlab` 库；未安装时自动降级为 `.txt`，功能完整，文件路径后缀变为 `.txt`
- **中文字体**优先使用 `simhei.ttf` / `msyh.ttc` / `simsun.ttc`，均不存在时降级为 Helvetica（中文可能乱码），建议确保 Windows 系统字体目录完整
- `appointment_time` 未传入时，`depart_time` 输出为"建议就诊前 N 分钟出发"的相对描述
- `output/` 目录不存在时自动创建；该目录已在 `.gitignore` 中排除
- 本 skill 是**流程终态**，不应在其输出基础上再调用其他 skill

## 完整调用链示意

```
symptom_triage(症状描述)
  └─ 得到 departments, warning_flags
       └─ hospital_matcher(user_location, departments)
            └─ 得到 candidates，用户选定医院
                 └─ registration_fetcher(hospital_name, department, yixue_url)
                      └─ 得到 registration_info
                           └─ itinerary_builder(...)  ← 本 skill
                                └─ 输出 PDF 行程单
```
