---
name: healthpath-symptom-triage
description: Triage user symptoms using local yixue.com knowledge base; agent reads yixue_knowledge.json autonomously to recommend departments, flag emergencies, and generate follow-up questions
metadata:
  openclaw:
    emoji: "🩺"
    requires:
      bins: ["python3"]
      python:
        runtime: ">=3.10"
        packages:
          - name: "requests"
            note: "仅 yixue_scraper.py 爬虫脚本需要，agent 运行时不需要"
            optional: true
          - name: "beautifulsoup4"
            note: "仅 yixue_scraper.py 爬虫脚本需要，agent 运行时不需要"
            optional: true
      files:
        - path: "skills/symptom_triage/yixue_knowledge.json"
          note: "运行时必须存在；首次使用前执行 python skills/symptom_triage/yixue_scraper.py 生成"
---

# symptom_triage — 病情预判与科室推荐

## 职责

接收用户自然语言描述的症状，由 Agent 直接读取本地知识库 `yixue_knowledge.json`，
自主进行语义匹配与判断，输出推荐就诊科室、危急警示和追问列表。

**本 skill 无网络请求、无脚本调用，Agent 自主阅读知识库并推理。**

## 何时调用

- 用户描述了身体不适、病症或健康问题时，**优先调用本 skill**
- 在调用 `hospital_matcher` 之前必须先调用本 skill，以确定目标科室
- 若用户已明确说出科室名称，可跳过本 skill 直接进入 `hospital_matcher`

## 执行流程

### 第一步：读取知识库

```
知识库路径：skills/symptom_triage/yixue_knowledge.json
结构：{ "pages": { "<route>": { "title", "content", "sections", "keywords" } } }
```

根据用户描述的症状，从以下路由中选取**最相关的 1~3 条**页面读取其 `content`：

### 路由索引

```
常见症状辨病
常见症状辨病/发热
常见症状辨病/疼痛
常见症状辨病/疼痛/头痛
常见症状辨病/疼痛/胸痛
常见症状辨病/疼痛/腹痛
常见症状辨病/疼痛/腰背痛
常见症状辨病/水肿
常见症状辨病/咳嗽
常见症状辨病/出血
常见症状辨病/皮肤粘膜出血
常见症状辨病/咯血
常见症状辨病/呕血
常见症状辨病/便血
常见症状辨病/尿血
常见症状辨病/鼻出血
常见症状辨病/恶心与呕吐
常见症状辨病/感觉器官功能异常
常见症状辨病/心悸
神色形态辨病
神色形态辨病/望神
神色形态辨病/望面色、面容
神色形态辨病/发育和营养状态
神色形态辨病/体位和姿态
观察机体局部辨病
观察机体局部辨病/皮肤
观察机体局部辨病/毛发
观察机体局部辨病/头颅
观察机体局部辨病/眉毛
观察机体局部辨病/眼睛
观察机体局部辨病/鼻
观察机体局部辨病/口腔
观察机体局部辨病/颈部
观察机体局部辨病/胸廓形态
观察机体局部辨病/脉搏
观察机体局部辨病/腹部
观察机体局部辨病/脊柱
观察机体局部辨病/四肢形态
观察分泌物排泄物辨病
观察分泌物排泄物辨病/汗液异常
观察分泌物排泄物辨病/小便
观察分泌物排泄物辨病/大便
观察分泌物排泄物辨病/鼻涕
观察分泌物排泄物辨病/痰液
饮食起居辨病
饮食起居辨病/饮食
饮食起居辨病/睡眠
饮食起居辨病/失眠
饮食起居辨病/嗜睡
饮食起居辨病/说话异常
饮食起居辨病/运动异常
妇科疾病
妇科疾病/月经和白带
妇科疾病/乳房
妇科疾病/非经期阴道出血和腹痛
儿童疾病
儿童疾病/全身状态异常
儿童疾病/望机体局部
儿童疾病/常见症状
```

### 第二步：自主分析推理

阅读选中页面后，依据知识库内容对用户症状进行语义理解，**自主判断**以下项目：

| 判断项 | 说明 |
|---|---|
| **危急标志** | 是否出现需立即急诊的征兆（如昏迷、剧烈胸痛、呼吸停止、口角歪斜、抽搐等） |
| **推荐科室** | 按相关度排列，最多 3 个，第一项为主推科室 |
| **信息是否充足** | 症状描述是否足以做出判断 |
| **追问问题** | 若信息不足，生成最多 3 条追问（已知信息的问题跳过） |
| **初步判断** | 用自然语言给出可读的分析结论 |

> Agent 应充分利用知识库中对各症状的鉴别要点、伴随症状、分类描述等进行推理，
> 而非仅做关键词匹配。

### 第三步：输出结构

向调用方（或用户）返回以下内容：

| 字段 | 说明 |
|---|---|
| `recommended_departments` | 推荐科室列表，按优先级排列，取第一项作为主科室 |
| `warning_flags` | 危急征兆提示；**非空时立即告知用户拨打 120** |
| `need_more_info` | 是否需要先向用户追问 |
| `follow_up_questions` | 追问列表，每项含 `id` / `question` |
| `preliminary_diagnosis` | 初步判断，可直接展示给用户 |
| `referenced_routes` | 本次参考的知识库路由列表 |
| `disclaimer` | 固定免责声明（见下方），**每次必须展示** |

## 决策流程

```
读取知识库相关页面
  ├─ 检测危急症状
  │    └─ warning_flags 非空 → 提示急诊/120，终止后续流程
  ├─ 信息不足
  │    └─ need_more_info = true → 向用户追问，带回答后重新判断
  └─ 正常
       └─ 给出 preliminary_diagnosis + recommended_departments
            └─ 取 [0] 作为目标科室，传入 hospital_matcher
```

## 注意事项

- 用户为老年人时，判断文本中应加入老年人专项提示（共病风险、用药注意等）
- 用户为儿童时，优先考虑儿科，并参考「儿童疾病」类路由
- **`disclaimer` 内容每次必须原文展示给用户，不得省略**
- 知识库内容为医学科普，Agent 可据此推理但应保持谨慎，避免过度下结论

## 免责声明（固定文本）

> ⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。如症状严重或突发，请立即拨打 120 或前往最近急诊。
