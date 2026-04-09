# AutoClaw调用Zhishu Agent的完整配置指南

## 问题诊断

当你在AutoClaw中输入"我想在北京找个好医院看骨科，最好这周能挂上号。"时，AutoClaw没有调用Zhishu Agent的Skills，而是自己思考。

**原因**: AutoClaw不知道这个需求应该调用哪些Skills。

---

## 解决方案

### 方案1: 显式告诉AutoClaw调用Skills

在AutoClaw中输入以下命令来显式调用Skills：

```
请使用Zhishu Agent来帮我规划就医方案。
我想在北京找个好医院看骨科，最好这周能挂上号。
```

或者更直接地：

```
调用healthpath-agent来帮我找医院。
我想在北京找个好医院看骨科，最好这周能挂上号。
```

---

### 方案2: 创建AutoClaw的技能配置文件

已为你创建了以下配置文件：

#### 1. `/c/Users/Administrator/.openclaw-autoclaw/skills_index.json`
这个文件告诉AutoClaw有哪些技能组以及何时调用它们。

#### 2. `/c/Users/Administrator/.openclaw-autoclaw/skills/ZHISHU_AGENT_README.md`
这个文件提供了Zhishu Agent的详细说明。

#### 3. `config/skills_manifest.json`
这个文件包含了所有Skills的元数据。

---

### 方案3: 在AutoClaw中创建一个"医疗助手"角色

告诉AutoClaw：

```
我想创建一个医疗助手角色，当用户提到医院、挂号、就医等相关需求时，
自动调用Zhishu Agent的Skills来帮助用户规划就医方案。

相关的Skills有：
- healthpath-intent-understanding: 解析用户意图
- healthpath-hospital-crawler: 搜索号源
- healthpath-decision-engine: 评分排序
- healthpath-output-generator: 生成PDF
```

---

## 🎯 最有效的使用方式

### 方式1: 直接指定使用Zhishu Agent

```
用户: "我想在北京找个好医院看骨科，最好这周能挂上号。
      请使用Zhishu Agent来帮我规划。"

AutoClaw: 
[调用 healthpath-intent-understanding]
[调用 healthpath-hospital-crawler]
[调用 healthpath-decision-engine]
[调用 healthpath-output-generator]

返回: "✅ 已为您生成就医行程单..."
```

### 方式2: 让AutoClaw自动识别

```
用户: "我想在北京找个好医院看骨科，最好这周能挂上号。"

AutoClaw (如果配置正确):
[自动识别这是医疗就诊规划任务]
[自动调用Zhishu Agent]
[执行完整流程]

返回: "✅ 已为您生成就医行程单..."
```

---

## 📋 检查清单

- [ ] Skills已注册到AutoClaw工作空间
- [ ] `skills_index.json` 已创建在 `C:\Users\Administrator\.openclaw-autoclaw\`
- [ ] `ZHISHU_AGENT_README.md` 已创建在 `C:\Users\Administrator\.openclaw-autoclaw\skills\`
- [ ] `skills_manifest.json` 已创建在项目的 `config\` 目录

---

## 🔧 手动配置步骤

如果AutoClaw仍然没有自动调用Skills，请按以下步骤手动配置：

### 步骤1: 验证Skills已注册

```bash
ls C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath*
```

应该看到：
- healthpath-intent-understanding/
- healthpath-hospital-crawler/
- healthpath-decision-engine/
- healthpath-output-generator/

### 步骤2: 检查Skills的SKILL.md

```bash
cat C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath-intent-understanding\SKILL.md
```

应该包含Skills的描述和使用方法。

### 步骤3: 在AutoClaw中测试

在AutoClaw中输入：

```
请调用healthpath-intent-understanding来解析这个需求：
"我想在北京找个好医院看骨科，最好这周能挂上号。"
```

---

## 💡 AutoClaw的技能调用机制

AutoClaw有几种方式来调用Skills：

### 1. 显式调用
```
用户: "调用healthpath-agent来帮我找医院。"
```

### 2. 隐式调用 (基于关键词)
```
用户: "我想找医院看骨科"
AutoClaw: [识别关键词，自动调用相关Skills]
```

### 3. 角色调用 (基于角色定义)
```
用户: "医疗助手，帮我找医院"
AutoClaw: [根据医疗助手角色，调用Zhishu Agent]
```

---

## 🚀 推荐的使用方式

**最简单的方式是显式告诉AutoClaw调用Skills：**

```
用户: "请使用Zhishu Agent来帮我规划就医方案。
      我想在北京找个好医院看骨科，最好这周能挂上号。"

AutoClaw会自动调用所有相关的Skills并返回结果。
```

---

## 📞 如果仍然不工作

1. **检查Skills是否正确注册**
   ```bash
   ls C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath*
   ```

2. **检查SKILL.md是否存在**
   ```bash
   ls C:\Users\Administrator\.openclaw-autoclaw\skills\healthpath-intent-understanding\SKILL.md
   ```

3. **在AutoClaw中显式调用**
   ```
   请调用healthpath-agent
   ```

4. **查看AutoClaw的日志**
   检查AutoClaw是否有错误信息

---

## 📚 相关文档

- **AUTOCLAW_CONVERSATION_GUIDE.md** - 对话式使用指南
- **AUTOCLAW_QUICK_REFERENCE.md** - 快速参考
- **HOW_TO_USE_IN_AUTOCLAW.md** - 完整使用指南

---

**现在你可以在AutoClaw中使用Zhishu Agent了！** 🎉
