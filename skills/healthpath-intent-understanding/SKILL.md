---
name: healthpath-intent-understanding
description: Parse user medical appointment request into structured task parameters; symptom and department extracted via semantic search (sentence-transformers), time/budget/format via rule-based parsing
metadata:
  openclaw:
    emoji: "🏥"
    requires:
      bins: ["python3"]
      python:
        runtime: ">=3.10"
        packages:
          - name: "sentence-transformers"
            version: ">=3.0.0"
            note: "语义提取 symptom / department，与 symptom-triage skill 共享同一模型实例"
          - name: "numpy"
            version: ">=1.24.0"
---

# intent_understanding — 用户意图结构化

## 职责

接收用户自然语言就医请求，解析为结构化任务参数，供下游 skill（`symptom_triage`、`hospital_matcher` 等）使用。

## 何时调用

- 流程入口第一步，用户输入原始文本后立即调用
- 若 DeepSeek API 可用，优先使用 API 解析（精度更高）
- API 不可用时自动降级为本地解析

## 实现方式

```
用户输入
    │
    ├─ use_deepseek=True → DeepSeek API → 结构化 JSON（主路径）
    │
    └─ 降级/离线 → 本地解析（次路径）
           │
           ├─ symptom + department → semantic_matcher.search_knowledge()
           │    一次检索同时得到两个字段：
           │    · symptom   = 命中 route 的末级节点名（如"腰背痛"）
           │    · department = route → 科室映射（与 symptom_triage 同一张表）
           │
           ├─ time_window   → 关键词规则（今天/明天/本周/下周/周末）
           ├─ budget        → 正则（数字 + 块/元/千/万）
           ├─ travel_preference → 关键词规则（最近/快/便宜）
           ├─ output_format → 关键词规则（大字/老人/excel/pdf）
           └─ special_requirements → 关键词规则（大字/无障碍/医保）
```

> `time_window`、`budget` 等结构化偏好字段保留规则提取，语义匹配对这类字段反而不稳定。

## 调用方式

```python
from intent_parser import parse_intent

task = parse_intent(
    user_input="老人这两天腰疼，帮我找本周可挂上的骨科号，做大字版行程单",
    use_deepseek=True   # False 强制走本地解析
)
```

## 输出结构

```json
{
  "symptom":              "腰背痛",
  "department":           "骨科",
  "target_city":          "北京",
  "time_window":          "this_week",
  "budget":               null,
  "travel_preference":    "balanced",
  "is_remote":            false,
  "output_format":        "large_font_pdf",
  "special_requirements": "large_font",
  "timestamp":            "2026-04-18T10:00:00"
}
```

| 字段 | 取值说明 |
|---|---|
| `time_window` | `today` / `tomorrow` / `two_days` / `this_week` / `next_week` / `weekend` |
| `travel_preference` | `nearby` / `fast` / `cheap` / `balanced` |
| `output_format` | `large_font_pdf` / `pdf` / `excel` |
| `is_remote` | 用户提到「异地」「外地」时为 `true` |

## 依赖说明

- `semantic_matcher`（`config/semantic_matcher.py`）与 `symptom_triage` skill **共享同一模型单例**，同进程内不重复加载
- 模型缓存、镜像源配置见 `healthpath-symptom-triage` SKILL.md
