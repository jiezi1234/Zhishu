# 你的 Skill 优先级规则已设置

## 位置
`E:\homework\Zhishu\AGENTS.md` → "Tools" 部分

## 内容概览

已添加了以下规则：

### 医疗任务（最重要）
- ✅ 明确的 4-step 工作流顺序（intent → crawler → decision → output）
- ✅ 禁止做法清单（防止跳步、直接推荐等）

### 其他 skill 优先级
- ✅ 网络搜索：autoglm-websearch > web_fetch
- ✅ 浏览器：browser > autoglm-browser-agent  
- ✅ 文档：feishu-doc > web_fetch

### 学习新 skill 的流程
- ✅ 先读 SKILL.md（避免我再犯"直接读源码"的错误）

## 何时生效
- 下次会话启动时，我会读取更新后的 AGENTS.md
- 即使当前会话也会在下次用到这些 skill 时遵守规则

## 后续改进建议

如果规则继续增加（超过 10 条），可以：
1. 创建独立的 `SKILL_PREFERENCES.md`
2. 在 AGENTS.md 中引用：`详见 SKILL_PREFERENCES.md`

---

想添加更多规则吗？比如：
- 其他 skill 的优先级？
- 特定任务的工作流？
- 禁止做法列表？
