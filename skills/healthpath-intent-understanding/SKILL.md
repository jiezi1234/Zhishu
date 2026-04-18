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

### 方式 1：Python 脚本（推荐，避免编码问题）

创建临时脚本 `temp_intent.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'skills/healthpath-intent-understanding')
from intent_parser import parse_intent

result = parse_intent(
    user_input="老人这两天腰疼，帮我找本周可挂上的骨科号，做大字版行程单",
    use_deepseek=True   # False 强制走本地解析
)
print(json.dumps(result, ensure_ascii=False, indent=2))
```

然后执行（**Windows PowerShell 必须用分号分隔，不能用 &&**）：
```powershell
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_intent.py
```

**为什么用脚本？** Windows PowerShell 的 GBK 编码会导致 UnicodeEncodeError，脚本方式可以正确处理 UTF-8 中文输出。

**⚠️ PowerShell 语法注意：**
- ❌ 错误：`cd E:\homework\Zhishu && $env:PYTHONIOENCODING='utf-8' && python temp_intent.py`
  - PowerShell 中 `&&` 不是有效的链接符，会导致 ParserError
- ✅ 正确：`cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_intent.py`
  - 用分号 `;` 分隔多条命令
- 或者用 `cmd /c` 包装（支持 `&&`）：`cmd /c "cd E:\homework\Zhishu && set PYTHONIOENCODING=utf-8 && python temp_intent.py"`

### 方式 2：直接 Python 调用（仅限 Linux/macOS）

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

## 编码与平台兼容性

**Windows 特殊处理（必须）：**
- PowerShell 默认 GBK 编码，直接运行 Python 会导致 `UnicodeEncodeError`
- 解决方案：**必须使用脚本方式**（见"调用方式"第一部分）
- 脚本中设置 `PYTHONIOENCODING='utf-8'` 和 `sys.stdout.reconfigure(encoding='utf-8')`
- 输出 JSON 时使用 `ensure_ascii=False` 保留中文

**Linux/macOS：** 可直接调用，无需额外处理

## 常见问题

### Q: 执行时出现 `ParserError` 或 `InvalidEndOfLine`

**原因：** PowerShell 不支持 `&&` 链接符。

**解决：** 用分号 `;` 替代：
```powershell
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_intent.py
```

### Q: 输出乱码或 `UnicodeEncodeError`

**原因：** PowerShell 默认 GBK 编码，Python 输出 UTF-8 中文时冲突。

**解决：** 
1. 确保脚本中有 `sys.stdout.reconfigure(encoding='utf-8')`
2. 确保 JSON 输出用 `ensure_ascii=False`
3. 执行前设置 `$env:PYTHONIOENCODING='utf-8'`

### Q: 模型首次下载很慢

**原因：** 首次运行需从 HuggingFace 下载 90MB 模型（与 symptom-triage 共享）。

**解决：** 
- 确保网络连接正常
- 模型会缓存到 `~/.cache/huggingface/hub/`，后续运行秒速加载
- 可通过 `HF_ENDPOINT` 环境变量切换镜像源

### Q: DeepSeek API 调用失败

**原因：** 未设置 `DEEPSEEK_API_KEY` 环境变量或 API 配额不足。

**解决：** 
- 系统会自动降级为本地解析，功能完整
- 若需使用 API，在 `.env` 文件中配置 `DEEPSEEK_API_KEY`
