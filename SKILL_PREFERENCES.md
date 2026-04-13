# SKILL_PREFERENCES.md — HealthPath Skill 使用指南

> 本文件是 `AGENTS.md` 的补充，专项说明 HealthPath 医疗预约工作流中五个 skill 的使用场景、调用顺序与边界。
> Agent 在处理任何医疗相关任务时，**必须先阅读本文件**。

---

## 一、标准工作流（五步顺序）

```
用户自然语言输入
      │
      ▼
[1] healthpath-intent-understanding   ← 解析意图，提取结构化参数
      │
      ▼
[2] healthpath-symptom-triage         ← 根据症状推荐科室（用户已明确科室时可跳过）
      │
      ▼
[3] healthpath-hospital-matcher       ← 匹配附近医院候选列表
      │
      ▼
[4] healthpath-registration-fetcher   ← 获取用户选定医院的官网 URL
      │
      ▼
[5] healthpath-itinerary-builder      ← 生成完整就医行程单（PDF）
```

---

## 二、各 Skill 使用场景

### [1] healthpath-intent-understanding
**触发条件：** 用户用自然语言提出就医需求，需要提取结构化参数时。  
**输出：** `symptom`、`department`、`target_city`、`time_window`、`budget`、`output_format` 等字段。  
**跳过条件：** 用户直接给出结构化参数（如已明确说"我要去骨科"且提供了所有必要信息）。

---

### [2] healthpath-symptom-triage
**触发条件：** 用户描述了身体症状，但**尚未确定就诊科室**时。  
**输出：** 推荐科室列表（取第一项作为主科室）、危急警示、追问列表。  
**跳过条件：** 用户已明确说出目标科室（如"我要挂骨科"），直接进入 hospital-matcher。  
**强制规则：**
- `warning_flags` 非空时，**立即告知用户拨打 120**，终止后续挂号流程。
- 每次必须原文展示免责声明，不得省略。

---

### [3] healthpath-hospital-matcher
**触发条件：** 已确定目标科室，需要从本地北京医疗机构数据中筛选附近医院时。  
**输入依赖：** 来自 symptom-triage 的 `departments`，或用户直接指定的科室。  
**输出：** 按距离+级别加权排序的候选医院列表（默认 Top 5）。  
**注意：**
- 距离优先调用百度地图 MCP（需 `BAIDU_MAP_AUTH_TOKEN`），不可用时自动降级为行政区粗估，展示时需注明"仅供参考"。
- `hospital_level = "三甲"` 过滤后若结果为空，自动放宽至全部等级，无需询问用户。

---

### [4] healthpath-registration-fetcher
**触发条件：** 用户已从候选列表中**选定具体医院**后，需要获取官网 URL 时。  
**输入依赖：** 用户选定的 `hospital_name`。  
**输出：** `official_url`（来自本地缓存或 yixue.com 解析）。  
**Agent 后续职责（脚本本身不做）：**
1. 验证 `official_url` 是否可访问（HTTP < 400）。
2. 验证失败或返回空字符串时，用 WebSearch 搜索 `"<医院名>" 官方网站` 兜底。
3. 确认可用后调用 `save_to_cache()` 写入缓存。

---

### [5] healthpath-itinerary-builder
**触发条件：** 已获取 `registration_fetcher` 的返回值，且用户已确认就诊计划，需要生成行程单时。  
**输入依赖：** `hospital_matcher` 的医院信息 + `registration_fetcher` 的挂号信息 + 用户的出发地和预约时间。  
**输出：** PDF 行程单文件路径（未安装 `reportlab` 时降级为 `.txt`，功能完整）。  
**本 skill 是流程终态**，不应在其输出基础上再调用其他 skill。

---

## 三、决策速查表

| 用户说的话 | 起点 skill |
|---|---|
| "我最近腰疼，帮我找医院" | [1] intent-understanding |
| "帮我找骨科医院" | [3] hospital-matcher（已知科室，跳过 triage） |
| "我胸口剧烈疼痛" | [2] symptom-triage（检测危急，可能终止流程） |
| "就去协和吧，帮我查挂号" | [4] registration-fetcher |
| "帮我生成行程单" | [5] itinerary-builder（需确认已有前序输出） |

---

## 四、禁止做法

- ❌ **不要跳过 symptom-triage**，直接根据症状描述推测科室并调用 hospital-matcher。
- ❌ **不要在 warning_flags 非空时继续挂号流程**，必须先提示急诊/120。
- ❌ **不要自行编造医院官网 URL**，必须经过 registration-fetcher + 验证流程。
- ❌ **不要将未验证的 `official_url` 直接展示给用户**，必须先确认可访问性。
- ❌ **不要直接操作 `blacklist.json`**，用 `hospital_matcher.add_to_blacklist()` 接口。
- ❌ **不要在 itinerary-builder 之后再调用其他 skill**，它是终态。
