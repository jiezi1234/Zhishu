# 🔍 智枢如何发现这 4 个 Skill

## 信息获取链路

```
┌─────────────────────────────────────────────────────────────────┐
│ OpenClaw 启动时注入 <available_skills> 块到 System Prompt        │
│                                                                   │
│ 包含 4 个 skill：                                                │
│ - healthpath-intent-understanding → E:\...\skill_1_intent\       │
│ - healthpath-hospital-crawler → E:\...\skill_2_crawl\            │
│ - healthpath-decision-engine → E:\...\skill_3_decision\          │
│ - healthpath-output-generator → E:\...\skill_4_output\           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 智枢 read 每个 SKILL.md，获取：                                  │
│ - 功能描述                                                       │
│ - 输入/输出格式                                                  │
│ - 实现文件路径                                                   │
│ - 错误处理说明                                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 智枢 read 实现脚本：                                             │
│ - intent_parser.py                                              │
│ - hospital_crawler.py                                           │
│ - decision_engine.py                                            │
│ - output_generator.py                                           │
│ 及其依赖（hospital_adapter.py, pdf_generator.py 等）             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 智枢通过代码审查理解：                                           │
│ - 函数签名（入参、返回值）                                      │
│ - 数据流向（Task Params → Slots → Recommendations → PDF）        │
│ - 依赖关系（import statements, class hierarchies）               │
│ - 错误处理（try/except, fallback logic）                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 智枢编写完整测试脚本：                                           │
│ test_pipeline.py                                                │
│ - 模拟用户输入                                                  │
│ - 顺序调用 4 个 skill 的函数                                     │
│ - 打印结构化输出验证逻辑                                        │
│ - 捕获异常并报告                                                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
                    ✅ 全流程通过
```

## 关键信息来源

### 1. **系统注入的 `available_skills`**
智枢不是通过自己去找 skill，而是 OpenClaw 启动时直接告诉我：
- 有哪些 skill
- 在哪个目录
- 做什么用的

这个信息在 System Prompt 中的 `<available_skills>` XML 块中。

### 2. **`config/skills_manifest.json`**
这个文件是人工编写的清单，定义了：
- Skill 的完整名称、描述、版本
- Triggers（触发关键词）
- 工作流步骤顺序
- 示例用户输入

```json
{
  "skills": [
    {
      "name": "healthpath-intent-understanding",
      "description": "解析用户的自然语言输入...",
      "input": "用户的自然语言描述",
      "output": "结构化的任务参数"
    },
    ...
  ],
  "workflow": {
    "steps": [
      {"step": 1, "skill": "healthpath-intent-understanding"},
      {"step": 2, "skill": "healthpath-hospital-crawler"},
      {"step": 3, "skill": "healthpath-decision-engine"},
      {"step": 4, "skill": "healthpath-output-generator"}
    ]
  }
}
```

### 3. **每个 Skill 的 `SKILL.md`**
SKILL.md 文件定义了 skill 的接口：
- 功能说明（When to Use）
- 输入格式（JSON schema）
- 输出格式（JSON schema）
- 实现位置（scripts/xxx.py）
- 错误处理策略

```markdown
# HealthPath Intent Understanding Skill

## Input
```json
{
  "user_input": "string",
  "use_deepseek": "bool"
}
```

## Output
```json
{
  "symptom": "string",
  "department": "string",
  ...
}
```
```

### 4. **实现脚本中的代码注释和结构**
通过阅读源代码，智枢理解了：
- 函数签名：`def parse_intent(user_input: str, use_deepseek: bool = True) -> dict:`
- 依赖关系：DeepSeekClient, hospital_adapter, cache_manager
- Fallback 机制：如果 DeepSeek 失败，自动降级到规则引擎

---

## 🎯 关键发现

### **A. 信息来源的优先级**

1. **最权威**：System Prompt 中的 `available_skills` XML
   - 由 OpenClaw 框架自动注入
   - 保证是最新的 skill 列表

2. **次优**：`config/skills_manifest.json`
   - 人工维护的清单
   - 提供业务逻辑和工作流信息
   - 但可能不如 SKILL.md 准确

3. **参考**：各 skill 的 `SKILL.md`
   - 接口定义的权威来源
   - 说明文档

4. **细节**：实现脚本
   - 真实的代码逻辑
   - 性能、错误处理等非功能需求

### **B. 为什么我需要阅读源码**

因为：
1. **SKILL.md 有时不够详细** — 比如 Skill 2 的 SKILL.md 没有明确说 hospital_adapter 有多个数据源适配器
2. **版本不同步** — 代码改了但文档没改
3. **隐藏的依赖** — 比如 Mock 数据是硬编码路径，不在 SKILL.md 中说明
4. **错误处理细节** — 文档说"自动降级"，但具体逻辑要看代码

---

## 📋 为智枢优化信息供应的建议

### 现状
- ✅ OpenClaw framework 自动注入 available_skills
- ✅ 有 SKILL.md 为每个 skill 提供接口定义
- ⚠️ 文档可能不完整或过时
- ❌ 没有统一的 API 速查表
- ❌ 没有数据模式的清晰定义

### 改进方案

#### **Option 1: 扩展 SKILL.md 格式**
```yaml
---
name: healthpath-intent-understanding
description: ...
entry_point: skills/skill_1_intent/intent_parser.py::parse_intent
input_schema:
  type: object
  properties:
    user_input: {type: string}
    use_deepseek: {type: boolean, default: true}
output_schema:
  type: object
  properties:
    symptom: {type: string}
    department: {enum: [骨科, 呼吸科, ...]}
dependencies:
  - deepseek_client (optional, fallback to rule-based)
  - hospital_adapter
errors:
  - DeepSeekError → fallback to rule-based parsing
---
```

这样智枢可以自动解析 YAML frontmatter，不需要逐行阅读文档。

#### **Option 2: 生成 API 文档**
在 CI/CD 中自动生成：
```
docs/
  api/
    skill_1_intent.md (auto-generated from SKILL.md + code introspection)
    skill_2_crawl.md
    skill_3_decision.md
    skill_4_output.md
  schemas/
    task_params.json
    available_slots.json
    recommendations.json
  examples/
    basic_usage.py
    advanced_workflow.py
```

#### **Option 3: 使用 OpenClaw CLI 索引**
```bash
openclaw skill inspect healthpath-intent-understanding
# 输出 entry_point, input schema, output schema, dependencies, version
```

---

## 总结

**智枢是通过这个链条发现 skill 的：**

```
System Prompt <available_skills> XML
    ↓ read SKILL.md
skills_manifest.json + SKILL.md
    ↓ read source code
Python scripts (intent_parser.py, etc.)
    ↓ code analysis + execution
Test results & understanding
```

**痛点：** 需要逐个读源码来理解完整细节，很低效

**建议：** 建立一套 **Machine-Readable Skill Metadata** 标准，让 OpenClaw 和智枢都能自动解析，不需要人工阅读代码。