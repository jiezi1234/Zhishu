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

### 方式 1：Python 脚本（推荐，避免编码问题）

创建临时脚本 `temp_itinerary.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'skills/healthpath-itinerary-builder')
from itinerary_builder import build

result = build(
    user_location     = "北京市朝阳区望京街道",
    hospital_name     = "北京协和医院",
    hospital_address  = "北京市东城区帅府园1号",
    department        = "神经内科",
    registration_info = {
        "hospital_name": "北京协和医院",
        "official_url": "https://www.pumch.ac.cn/",
        "from_cache": True,
        "timestamp": "2026-04-18T10:00:00"
    },
    appointment_time  = "2026-04-16 09:00",
    output_format     = "large_font_pdf",
    user_profile      = {"age_group": "elderly"},
)
print(json.dumps(result, ensure_ascii=False, indent=2))
```

然后执行（**Windows PowerShell 必须用分号分隔，不能用 &&**）：
```powershell
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_itinerary.py
```

**为什么用脚本？** Windows PowerShell 的 GBK 编码会导致 UnicodeEncodeError，脚本方式可以正确处理 UTF-8 中文输出。

**⚠️ PowerShell 语法注意：**
- ❌ 错误：`cd E:\homework\Zhishu && $env:PYTHONIOENCODING='utf-8' && python temp_itinerary.py`
  - PowerShell 中 `&&` 不是有效的链接符，会导致 ParserError
- ✅ 正确：`cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_itinerary.py`
  - 用分号 `;` 分隔多条命令
- 或者用 `cmd /c` 包装（支持 `&&`）：`cmd /c "cd E:\homework\Zhishu && set PYTHONIOENCODING=utf-8 && python temp_itinerary.py"`

### 方式 2：直接 Python 调用（仅限 Linux/macOS）

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
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_itinerary.py
```

### Q: 输出乱码或 `UnicodeEncodeError`

**原因：** PowerShell 默认 GBK 编码，Python 输出 UTF-8 中文时冲突。

**解决：** 
1. 确保脚本中有 `sys.stdout.reconfigure(encoding='utf-8')`
2. 确保 JSON 输出用 `ensure_ascii=False`
3. 执行前设置 `$env:PYTHONIOENCODING='utf-8'`

### Q: PDF 中文显示为方框或乱码

**原因：** 系统缺少中文字体或 reportlab 未找到字体文件。

**解决：** 
- 确保 Windows 系统字体目录（`C:\Windows\Fonts`）包含 `simhei.ttf` / `msyh.ttc` / `simsun.ttc`
- 或手动指定字体路径（需修改 `itinerary_builder.py` 中的字体查找逻辑）
- 降级方案：使用 `output_format="pdf"` 生成标准版（字体更小，兼容性更好）

### Q: 生成的是 .txt 文件而不是 PDF

**原因：** `reportlab` 库未安装，系统自动降级。

**解决：** 
- 安装 reportlab：`pip install reportlab`
- 或接受 .txt 输出（功能完整，仅格式不同）

### Q: 路线规划显示"仅供参考"

**原因：** 百度地图 MCP 不可用，使用粗估距离和时间。

**解决：** 
- 设置 `BAIDU_MAP_AUTH_TOKEN` 环境变量启用精确路线规划
- 粗估路线仍可用于初步参考，但建议用户以实际导航为准

### Q: 出发时间计算不准确

**原因：** 未传入 `appointment_time` 或路线时间为粗估值。

**解决：** 
- 确保传入准确的 `appointment_time`（ISO 格式，如 "2026-04-16 09:00"）
- 启用百度地图 MCP 获取精确出行时间
- 系统会自动加 30 分钟院内缓冲时间

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
