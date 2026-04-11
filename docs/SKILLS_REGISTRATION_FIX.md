# Zhishu Agent Skills 注册问题诊断与修复

## 问题诊断

**症状**: AutoClaw无法找到已注册的Zhishu Agent Skills，返回"没找到"错误。

**根本原因**: Skills目录为空，缺少AutoClaw识别Skills所需的元数据文件。

```
C:\Users\Administrator\.openclaw-autoclaw\skills\
├── healthpath-intent-understanding/     ← 空目录 ❌
├── healthpath-hospital-crawler/         ← 空目录 ❌
├── healthpath-decision-engine/          ← 空目录 ❌
└── healthpath-output-generator/         ← 空目录 ❌
```

## 解决方案

### 1. 创建SKILL.md文件

每个Skill目录需要一个`SKILL.md`文件，包含：
- **Frontmatter**: name, description等元数据
- **文档**: Skill的详细说明、使用方法、输入输出示例

**示例格式**:
```markdown
---
name: healthpath-intent-understanding
description: 解析用户的自然语言输入，提取就医需求的结构化参数。
---

# 就医意图解析

[详细文档...]
```

### 2. 创建_meta.json文件

每个Skill目录需要一个`_meta.json`文件，包含：
- `ownerId`: Skill所有者ID
- `slug`: Skill的唯一标识符
- `version`: 版本号
- `publishedAt`: 发布时间戳

**示例格式**:
```json
{
  "ownerId": "zhishu-agent",
  "slug": "healthpath-intent-understanding",
  "version": "1.0.0",
  "publishedAt": 1744156800000
}
```

### 3. 创建主Skill入口

创建`healthpath-agent`作为主入口Skill，用于协调其他4个子Skills。

## 已完成的修复

### ✅ 创建的文件

```
C:\Users\Administrator\.openclaw-autoclaw\skills\
├── healthpath-agent/
│   ├── SKILL.md                    ← 新建
│   └── _meta.json                  ← 新建
├── healthpath-intent-understanding/
│   ├── SKILL.md                    ← 新建
│   └── _meta.json                  ← 新建
├── healthpath-hospital-crawler/
│   ├── SKILL.md                    ← 新建
│   └── _meta.json                  ← 新建
├── healthpath-decision-engine/
│   ├── SKILL.md                    ← 新建
│   └── _meta.json                  ← 新建
└── healthpath-output-generator/
    ├── SKILL.md                    ← 新建
    └── _meta.json                  ← 新建
```

### 📝 SKILL.md文件内容

每个SKILL.md包含：

1. **healthpath-agent** - 主入口，协调所有子Skills
2. **healthpath-intent-understanding** - 意图解析，提取结构化参数
3. **healthpath-hospital-crawler** - 号源搜索，获取医院信息
4. **healthpath-decision-engine** - 方案决策，评分排序
5. **healthpath-output-generator** - PDF生成，输出行程单

### 📋 _meta.json文件内容

所有_meta.json都包含：
- `ownerId`: "zhishu-agent"
- `slug`: 对应的Skill名称
- `version`: "1.0.0"
- `publishedAt`: 1744156800000

## AutoClaw如何识别Skills

AutoClaw的Skill发现机制：

1. **扫描Skills目录** - 查找 `C:\Users\Administrator\.openclaw-autoclaw\skills\` 下的所有目录
2. **检查SKILL.md** - 每个目录必须有SKILL.md文件
3. **解析Frontmatter** - 从SKILL.md的frontmatter提取name和description
4. **验证_meta.json** - 检查_meta.json是否有效
5. **注册Skill** - 将Skill添加到可用列表

## 现在可以做什么

### 在AutoClaw中调用Skills

**方式1: 调用主Skill**
```
调用healthpath-agent来帮我规划就医方案。
我想在北京找个好医院看骨科，最好这周能挂上号。
```

**方式2: 自然语言触发**
```
我想在北京找个好医院看骨科，最好这周能挂上号。
```

**方式3: 调用具体Skill**
```
调用healthpath-intent-understanding来解析这个需求：
"我想在北京找个好医院看骨科"
```

## 工作流程

```
用户输入 (自然语言)
    ↓
AutoClaw识别意图
    ↓
调用healthpath-agent
    ↓
[Skill 1] 意图解析 → 提取参数
    ↓
[Skill 2] 号源搜索 → 获取号源
    ↓
[Skill 3] 方案决策 → 评分排序
    ↓
[Skill 4] PDF生成 → 输出行程单
    ↓
返回结果给用户
```

## 关键要点

### ✅ 必须有的文件

- `SKILL.md` - 包含frontmatter和文档
- `_meta.json` - 包含元数据

### ✅ SKILL.md的Frontmatter格式

```markdown
---
name: skill-name
description: 简短描述。Use when: 使用场景。
---
```

### ✅ _meta.json的格式

```json
{
  "ownerId": "owner-id",
  "slug": "skill-slug",
  "version": "1.0.0",
  "publishedAt": 时间戳
}
```

### ✅ 文件编码

- 必须是UTF-8编码
- 不能有BOM标记

### ✅ 文件权限

- 文件必须可读
- 目录必须可访问

## 如果仍然不工作

### 1. 重启AutoClaw

AutoClaw可能需要重启才能识别新的Skills。

### 2. 验证文件格式

检查SKILL.md是否有正确的frontmatter：
```bash
head -5 "C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath-agent\SKILL.md"
```

应该看到：
```
---
name: healthpath-agent
description: ...
---
```

### 3. 验证JSON格式

检查_meta.json是否是有效的JSON：
```bash
cat "C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath-agent\_meta.json"
```

### 4. 查看AutoClaw日志

检查AutoClaw是否有错误信息，可能会提示具体问题。

## 总结

**问题**: Skills目录为空，缺少SKILL.md和_meta.json

**解决**: 为每个Skill创建SKILL.md和_meta.json文件

**结果**: AutoClaw现在可以识别并调用Zhishu Agent Skills

**下一步**: 在AutoClaw中测试调用Skills，验证工作流程是否正常
