# AutoClaw中使用Zhishu Agent - 快速测试指南

## ✅ 已完成的配置

所有Skills已正确注册到AutoClaw工作空间：

```
C:\Users\Administrator\.openclaw-autoclaw\skills\
├── healthpath-agent/                    ← 主入口
│   ├── SKILL.md
│   └── _meta.json
├── healthpath-intent-understanding/     ← 意图解析
│   ├── SKILL.md
│   └── _meta.json
├── healthpath-hospital-crawler/         ← 号源搜索
│   ├── SKILL.md
│   └── _meta.json
├── healthpath-decision-engine/          ← 方案决策
│   ├── SKILL.md
│   └── _meta.json
└── healthpath-output-generator/         ← PDF生成
    ├── SKILL.md
    └── _meta.json
```

## 🚀 在AutoClaw中测试

### 方式1: 直接调用主Skill

在AutoClaw中输入：

```
调用healthpath-agent来帮我规划就医方案。
我想在北京找个好医院看骨科，最好这周能挂上号。
```

或者更简洁的方式：

```
我想在北京找个好医院看骨科，最好这周能挂上号。
```

### 方式2: 指定具体的Skill

如果需要只执行某个步骤，可以直接调用：

```
调用healthpath-intent-understanding来解析这个需求：
"我想在北京找个好医院看骨科，最好这周能挂上号。"
```

## 📋 测试用例

### 测试1: 基本需求
```
我想在北京找个好医院看骨科
```

**预期结果**: AutoClaw识别科室和城市，调用Skills搜索号源

### 测试2: 带时间要求
```
我想这周在北京找个医院看神经内科
```

**预期结果**: 识别时间窗口，搜索本周可挂号的医院

### 测试3: 完整需求
```
我奶奶最近腰疼得厉害，想在北京找个好医院看骨科，最好这周能挂上号，离家近一点最好，生成一份大字版的就医行程单。
```

**预期结果**: 
- 解析所有参数（科室、症状、城市、时间、距离偏好、格式）
- 搜索号源
- 评分排序
- 生成大字版PDF

### 测试4: 异地就医
```
我从外地来北京，需要看呼吸科，最好能找个评价好的医院。
```

**预期结果**: 识别异地就医需求，优先推荐评分高的医院

## 🔍 验证Skills是否被识别

### 方法1: 在AutoClaw中查看可用Skills

在AutoClaw中输入：
```
列出所有可用的Skills
```

应该能看到 `healthpath-agent` 和相关的Skills。

### 方法2: 检查文件结构

验证所有文件都已创建：

```bash
# 检查healthpath-agent
ls -la "C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath-agent"

# 应该看到:
# SKILL.md
# _meta.json
```

### 方法3: 查看SKILL.md格式

检查SKILL.md是否有正确的frontmatter：

```bash
head -5 "C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath-agent\SKILL.md"

# 应该看到:
# ---
# name: healthpath-agent
# description: ...
# ---
```

## 🔧 如果AutoClaw仍然找不到Skills

### 步骤1: 重启AutoClaw

有时AutoClaw需要重启才能识别新注册的Skills。

### 步骤2: 清除缓存

AutoClaw可能缓存了Skills列表，尝试清除缓存：

```bash
# 查看AutoClaw的缓存目录
ls -la "C:\Users\Administrator\.openclaw-autoclaw"

# 如果有缓存文件，可以删除它们让AutoClaw重新扫描
```

### 步骤3: 验证_meta.json格式

检查_meta.json是否有正确的JSON格式：

```bash
cat "C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath-agent\_meta.json"

# 应该看到:
# {
#   "ownerId": "zhishu-agent",
#   "slug": "healthpath-agent",
#   "version": "1.0.0",
#   "publishedAt": 1744156800000
# }
```

## 📊 预期的工作流程

当用户在AutoClaw中输入就医需求时：

```
用户: "我想在北京找个好医院看骨科，最好这周能挂上号。"
     ↓
AutoClaw: [识别这是医疗就诊规划任务]
     ↓
AutoClaw: [调用 healthpath-agent]
     ↓
[Skill 1] healthpath-intent-understanding
  输入: "我想在北京找个好医院看骨科，最好这周能挂上号。"
  输出: {department: "骨科", city: "北京", time_window: "this_week"}
     ↓
[Skill 2] healthpath-hospital-crawler
  输入: 任务参数
  输出: 可用号源列表
     ↓
[Skill 3] healthpath-decision-engine
  输入: 号源列表
  输出: 排序后的推荐方案
     ↓
[Skill 4] healthpath-output-generator
  输入: 推荐方案
  输出: PDF文件
     ↓
AutoClaw: "✅ 已为您生成就医行程单"
返回: PDF文件链接
```

## 💡 常见问题

### Q: AutoClaw说"没找到"怎么办？

A: 这通常是因为：
1. Skills的SKILL.md或_meta.json格式不正确
2. AutoClaw需要重启
3. Skills目录结构不对

**解决方案**:
- 检查SKILL.md是否有正确的frontmatter (---name: ... ---)
- 检查_meta.json是否是有效的JSON
- 重启AutoClaw

### Q: 如何验证Skills已正确注册？

A: 在AutoClaw中输入：
```
调用healthpath-agent
```

如果AutoClaw能识别这个Skill，说明注册成功。

### Q: 可以只调用某个Skill吗？

A: 可以。例如只调用意图解析：
```
调用healthpath-intent-understanding来解析这个需求：
"我想在北京找个好医院看骨科"
```

### Q: 如何自定义输出格式？

A: 在需求中指定格式：
```
生成一份大字版的就医行程单
生成一份详细版的行程单
生成一份简洁版的行程单
```

## 📞 获取帮助

如果Skills仍然无法工作，检查：

1. **SKILL.md格式** - 必须有frontmatter
2. **_meta.json格式** - 必须是有效JSON
3. **文件编码** - 应该是UTF-8
4. **文件权限** - 应该可读
5. **AutoClaw版本** - 确保是最新版本

---

**现在可以在AutoClaw中使用Zhishu Agent了！** 🎉
