---
name: healthpath-hospital-matcher
description: Match and recommend nearby hospitals based on user location and target department using local Beijing medical institution data
metadata:
  openclaw:
    emoji: "🏨"
    requires:
      bins: ["python3"]
      python:
        runtime: ">=3.10"
        packages: []
      env_optional: ["BAIDU_MAP_AUTH_TOKEN"]
---

# hospital_matcher — 附近医院匹配与推荐

## 职责

根据用户位置和目标科室，从本地 4311 条北京医疗机构数据中筛选、排序候选医院，
并通过百度地图 MCP 计算实际出行距离和时间。

## 数据来源

| 文件 | 说明 |
|---|---|
| `skills/hospital_matcher/hospitals.json` | 预处理后的主数据（csv_to_json.py 生成），含 `by_district` / `by_name` / `all` 三种索引 |
| `skills/hospital_matcher/blacklist.json` | 用户标记的屏蔽医院，运行时自动过滤（不存在时忽略） |
| `skills/registration_fetcher/hospital_info.json` | registration_fetcher 写入的挂号缓存，本 skill 只读 |

> `hospitals.json` 已纳入版本控制，其余 JSON 为运行时生成的私有缓存。

## 何时调用

- 已通过 `symptom_triage` 确定目标科室后调用
- 用户询问"附近哪家医院可以看 XX"、"推荐医院"等时调用

## 调用方式

```python
from skills.hospital_matcher.hospital_matcher import match

result = match(
    user_location = "北京市朝阳区望京街道",   # 必填：用户当前地址
    departments   = ["神经内科", "耳鼻喉科"],  # 必填：来自 symptom_triage
    preferences   = {
        "max_distance_km":  10,        # 最大距离，默认 15
        "hospital_level":   "三甲",    # 三甲 | 二甲 | 不限（默认）
        "travel_mode":      "transit", # transit | driving | walking
    },
    top_n = 5,   # 返回候选数，默认 5
)
```

## 输出字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `candidates` | `list[dict]` | 按优先级排序的候选医院，详见下表 |
| `total_before_filter` | `int` | 过滤前总医院数 |
| `filtered_by_blacklist` | `int` | 因黑名单过滤的数量 |
| `data_sources` | `list[str]` | 实际使用的数据源（含条数） |
| `timestamp` | `str` | ISO 格式时间戳 |

### candidates 每项字段

| 字段 | 说明 |
|---|---|
| `hospital_name` | 医院全称 |
| `level` | 等级：三甲 / 三乙 / 三级 / 二甲 / 二级 / 一甲 / 一级 / 其他 |
| `level_rank` | 等级数值（1=三甲，值越小越优，用于排序） |
| `district` | 医保区划（如"朝阳区"） |
| `address` | 主地址 |
| `distance_km` | 距用户位置的估算距离（百度 MCP 可用时为真实值） |
| `travel_time_min` | 预计出行时间（分钟） |
| `yixue_url` | 医疗百科页面，传给 `registration_fetcher` 使用 |
| `distance_is_estimated` | `bool` | `true` 时距离为按行政区分档的粗估值（同区 4 km / 相邻区 9 km / 跨区 15 km），非精确路线距离 |
| `map_route_url` | 百度地图路线直达链接 |

## 典型决策流程

```
symptom_triage → 得到 departments
  └─ match(user_location, departments, preferences)
       └─ 取 candidates[0] 作为首选医院
            ├─ 将 hospital_name / address / yixue_url 传给 registration_fetcher
            └─ 将全部 candidates 展示给用户供选择
```

## 注意事项

- **百度地图 MCP 不可用时**距离按行政区分档粗估（同区 4 km / 相邻区 9 km / 跨区 15 km），`distance_is_estimated: true` 且 `data_sources` 中出现 "距离估算-按行政区分档" 字样；此时向用户展示距离时应注明"仅供参考"
- `hospital_level = "三甲"` 过滤后若结果为 0，会自动放宽至全部等级
- 黑名单写入请调用本 skill 的 `add_to_blacklist(hospital_name, reason)` 函数，不要直接操作 JSON 文件
