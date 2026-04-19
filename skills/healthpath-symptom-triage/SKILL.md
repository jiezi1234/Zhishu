---
name: healthpath-symptom-triage
description: Triage user symptoms via semantic search over yixue.com knowledge base; calls symptom_triage.py which uses sentence-transformers (BAAI/bge-small-zh-v1.5) to recommend departments, flag emergencies, and generate follow-up questions
metadata:
  openclaw:
    emoji: "🩺"
    platforms: ["Windows", "Linux", "macOS"]
    windows_note: "必须使用脚本方式调用，避免 PowerShell GBK 编码问题"
    requires:
      bins: ["python3"]
      python:
        runtime: ">=3.10"
        packages:
          - name: "sentence-transformers"
            version: ">=3.0.0"
            note: "语义检索核心依赖，首次运行自动从 hf-mirror.com 下载模型（约 90MB），后续离线运行"
          - name: "numpy"
            version: ">=1.24.0"
            note: "向量计算"
      files:
        - path: "skills/healthpath-symptom-triage/yixue_knowledge.json"
---

# symptom_triage — 病情预判与科室推荐

## 职责

接收用户自然语言症状描述，调用 `symptom_triage.py`，通过语义检索知识库 `yixue_knowledge.json`，
输出推荐就诊科室、危急警示和追问列表。

## 何时调用

- 用户描述了身体不适、病症或健康问题时，**优先调用本 skill**
- 在调用 `hospital_matcher` 之前必须先调用本 skill，以确定目标科室
- 若用户已明确说出科室名称，可跳过本 skill 直接进入 `hospital_matcher`

## 实现方式

本 skill 使用 **sentence-transformers 语义检索**，不依赖关键词匹配：

```
用户症状描述
    │
    ▼
detect_emergency()        ← 与 7 条急症场景描述比对，阈值 0.70
    │ 有命中 → 返回 warning_flags，终止流程
    ▼
search_knowledge(k=5)     ← BGE 向量检索 yixue_knowledge.json 59 个条目
    │                        每条索引文本 = route + keywords + content[:150]
    ▼
_deduplicate_by_hierarchy()  ← 子节点分数 ≥ 父节点×0.85 时丢弃父节点
    │
    ▼
route → 科室映射          ← _ROUTE_DEPT 前缀匹配表
    │ 仅命中父节点 → need_more_info=True，触发追问
    ▼
返回结构化结果
```

## 调用方式

### 方式 1：Python 脚本（推荐，避免编码问题）

创建临时脚本 `temp_triage.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'skills/healthpath-symptom-triage')
from symptom_triage import triage

result = triage(
    symptom_text="用户症状描述",
    user_profile={"age_group": "adult"}  # "elderly" | "adult" | "child"
)
print(json.dumps(result, ensure_ascii=False, indent=2))
```

然后执行（**Windows PowerShell 必须用分号分隔，不能用 &&**）：
```powershell
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_triage.py
```

**为什么用脚本？** Windows PowerShell 的 GBK 编码会导致 UnicodeEncodeError，脚本方式可以正确处理 UTF-8 和特殊符号（如 ⚠️）。

**⚠️ PowerShell 语法注意：**
- ❌ 错误：`cd E:\homework\Zhishu && $env:PYTHONIOENCODING='utf-8' && python temp_triage.py`
  - PowerShell 中 `&&` 不是有效的链接符，会导致 ParserError
- ✅ 正确：`cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_triage.py`
  - 用分号 `;` 分隔多条命令
- 或者用 `cmd /c` 包装（支持 `&&`）：`cmd /c "cd E:\homework\Zhishu && set PYTHONIOENCODING=utf-8 && python temp_triage.py"`

### 方式 2：直接 Python 调用（仅限 Linux/macOS）

```python
from symptom_triage import triage

result = triage(
    symptom_text="老人头晕失眠两周了",
    user_profile={"age_group": "elderly"},   # "elderly" | "adult" | "child"
    extra_answers={}
)
```

## 输出结构

| 字段 | 说明 |
|---|---|
| `recommended_departments` | 推荐科室列表，按相关度排列，取 `[0]` 作为主科室传入 `hospital_matcher` |
| `warning_flags` | 危急征兆提示；**非空时立即告知用户拨打 120，终止挂号流程** |
| `need_more_info` | 是否需要向用户追问 |
| `follow_up_questions` | 追问列表，每项含 `id` / `question` |
| `preliminary_diagnosis` | 初步判断，可直接展示给用户 |
| `referenced_routes` | 本次命中的知识库 route 列表 |
| `disclaimer` | 固定免责声明，**每次必须展示** |

> ⚠️ **请审查分诊结果是否合理，不合理则自动修正科室。若追问后用户表示说不清楚，或者3轮追问后能无法判断，根据人群直接推荐：普通人建议优先就诊【全科】儿童建议优先就诊【儿科全科】，老年人建议优先就诊【老年病科】，孕妇建议优先就诊【妇产科】**

## 决策流程

```
detect_emergency()
  └─ 命中（score ≥ 0.70）→ warning_flags 非空，提示急诊/120，立即返回

输入过短（< 5字）
  └─ need_more_info=True，追问症状详情

search_knowledge()
  ├─ 无命中（score < 0.40）→ need_more_info=True，追问部位/性质
  ├─ 仅命中父节点          → need_more_info=True，追问部位/性质
  └─ 命中叶子节点          → 返回科室推荐 + preliminary_diagnosis
```

## 依赖与模型缓存

- **模型**：`BAAI/bge-small-zh-v1.5`（约 90MB），缓存于 `~/.cache/huggingface/hub/`
- **首次运行**：自动从 `hf-mirror.com` 下载，需要联网
- **后续运行**：检测到本地缓存后自动设置 `TRANSFORMERS_OFFLINE=1`，完全离线，秒速加载
- **镜像源**：代码内置默认值 `hf-mirror.com`，可通过环境变量 `HF_ENDPOINT` 覆盖

## 注意事项

### 编码与平台兼容性

**Windows 特殊处理（必须）：**
- PowerShell 默认 GBK 编码，直接运行 Python 会导致 `UnicodeEncodeError`
- 解决方案：**必须使用脚本方式**（见"调用方式"第一部分）
- 脚本中设置 `PYTHONIOENCODING='utf-8'` 和 `sys.stdout.reconfigure(encoding='utf-8')`
- 输出 JSON 时使用 `ensure_ascii=False` 保留中文和特殊符号

**Linux/macOS：** 可直接调用，无需额外处理

### 用户信息处理

- 用户为老年人（`age_group=elderly`）时，判断文本加入老年人专项提示
- 用户为儿童（`age_group=child`）时，科室列表置顶儿科
- `disclaimer` 内容每次必须原文展示给用户，不得省略

## 常见问题

### Q: 执行时出现 `ParserError` 或 `InvalidEndOfLine`

**原因：** PowerShell 不支持 `&&` 链接符。

**解决：** 用分号 `;` 替代：
```powershell
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_triage.py
```

### Q: 输出乱码或 `UnicodeEncodeError`

**原因：** PowerShell 默认 GBK 编码，Python 输出 UTF-8 中文时冲突。

**解决：** 
1. 确保脚本中有 `sys.stdout.reconfigure(encoding='utf-8')`
2. 确保 JSON 输出用 `ensure_ascii=False`
3. 执行前设置 `$env:PYTHONIOENCODING='utf-8'`

### Q: 模型首次下载很慢

**原因：** 首次运行需从 HuggingFace 下载 90MB 模型。

**解决：** 
- 确保网络连接正常
- 模型会缓存到 `~/.cache/huggingface/hub/`，后续运行秒速加载
- 可通过 `HF_ENDPOINT` 环境变量切换镜像源

## 免责声明（固定文本）

> ⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。如症状严重或突发，请立即拨打 120 或前往最近急诊。
