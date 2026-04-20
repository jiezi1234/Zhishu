# 设计文档:基于 AutoClaw 浏览器控制的医生出诊表与号源查询

- **日期**:2026-04-20
- **作者**:智枢 HealthPath Agent
- **状态**:待用户审阅 → 实施
- **相关文件**:
  - `main_skill.py`(扩展 `execute()` 签名与状态机)
  - `skills/healthpath-intent-understanding/intent_parser.py`(扩展 `doctor_name` 抽取)
  - `skills/healthpath-doctor-schedule/`(**新建**)
  - `skills/healthpath-itinerary-builder/itinerary_builder.py`(PDF 内容扩展)
  - `SKILL_PREFERENCES.md`(新增约束)

---

## 1. 目标与动机

当前 HealthPath 挂号流程止步于"返回医院官网 URL",用户仍需自行进入官网查找医生、比对出诊时间、判断号源是否充足。本次工作引入 AutoClaw 浏览器控制能力(`autoglm-browser-agent`),使得当用户指明需要挂**某医院某位专家**的号时,系统能自动访问挂号官网,读取该医生的出诊表与剩余号源,给出合适的就诊日期与时间建议。

**最终交付给用户的形态**:
- 在 PDF 行程单里多出"推荐就诊日期/时段 + 原因"一段
- 浏览器窗口保持打开,用户按推荐去挂号页面完成最后一步(登录、选号、支付)
- 遇到登录等阻断时,系统显式把中断态上抛,由用户在本机浏览器里完成后继续流程

**明确不在范围内**:
- 全自动登录、选号、支付(涉及支付凭证,风险不可控)
- 跨院推荐同科室备选医生(下一版本再做)
- 抢号与号源变化通知(非"调度智能体"应做之事)
- 适配微信/小程序挂号入口(浏览器无法打开小程序)

---

## 2. 流程变化与状态机

现有 5 步流程 → 新 6 步:

```
[1] intent-understanding   ← 扩展:多提取 doctor_name
[2] symptom-triage
[3] hospital-matcher
[4] registration-fetcher   ← 仍负责拿到挂号入口 URL
[5] doctor-schedule        ← 新增 skill
[6] itinerary-builder      ← 扩展:PDF 多印医生与推荐时间
```

### 新增 status 值(共 3 个)

| status | 触发条件 | 上层 agent 该做的事 |
|---|---|---|
| `awaiting_doctor_selection` | 用户未指名医生 & autoclaw 成功抓到该科室专家列表 | 把 `experts` 列表展示给用户,下一轮 `execute(..., selected_doctor=...)` |
| `awaiting_browser_interaction` | autoclaw 返回 `[INTERACT_REQUIRED]`(登录/验证码/敏感确认) | 转述 `interact_prompt`,用户在本机浏览器完成后 `execute(..., browser_resume={session_id, tab_id, user_action})` |
| `doctor_schedule_fetched` | 成功取到出诊表+号源+推荐 | 把推荐时段展示给用户,用户确认后 `execute(..., confirmed_appointment={date, time_slot})`,再生成 PDF |

此外复用现有错误态 `error`、`doctor_not_found`(新增)、`schedule_fetched_but_full`(新增)。

### `execute()` 签名扩展(向后兼容)

```python
def execute(
    user_input: str,
    user_location: Optional[str] = None,
    selected_hospital: Optional[str] = None,
    selected_doctor: Optional[str] = None,            # 新
    browser_resume: Optional[dict] = None,            # 新 {session_id, tab_id, user_action}
    confirmed_appointment: Optional[dict] = None,     # 新 {date, time_slot}
    extra_answers: Optional[dict] = None,
    output_format: str = "large_font_pdf",
    user_profile: Optional[dict] = None,
) -> Dict[str, Any]
```

所有新增参数默认 `None`,原有调用方可无改动继续使用。

**新增参数字段结构**:

```python
browser_resume = {
    "session_id": "xxxxxxxx-xxxx-...",     # 必填,上一轮返回的 session_id
    "tab_id": "123",                         # 必填,上一轮返回的 tab_id
    "user_action": "login_done"              # 枚举:"login_done" | "captcha_done" | "approve" | "reject"
                  | "自由文本",              #   或自由文本,如 "已选择某家三甲医院的验证"
}

confirmed_appointment = {
    "date": "2026-04-22",                    # ISO 日期
    "time_slot": "上午",                      # "上午" | "下午" | 具体 "HH:MM-HH:MM"
}
```

### 典型多轮对话

```
Turn 1:用户输入 "给我挂协和医院神经内科的号"
  → intent 无 doctor_name → hospital_matcher 返回候选
  → status='awaiting_hospital_selection'
Turn 2:用户选 "北京协和医院"
  → registration-fetcher 返回 official_url
  → doctor-schedule.list_experts 启动 autoclaw,抓神经内科专家列表
  → 若遇登录:status='awaiting_browser_interaction',返回 session_id/tab_id/prompt
  → 否则:status='awaiting_doctor_selection',返回 experts[]
Turn 3:用户选 "王立凡"
  → doctor-schedule.fetch_doctor_schedule 启动 autoclaw,抓出诊表+号源
  → 生成推荐
  → status='doctor_schedule_fetched',返回 schedule + recommendation
Turn 4:用户确认推荐的就诊时段
  → step 6 itinerary-builder 生成 PDF
  → status='success',final_output 含 pdf_path
```

---

## 3. 新 skill `healthpath-doctor-schedule` 接口

### 目录结构

```
skills/healthpath-doctor-schedule/
├── SKILL.md
├── _meta.json
├── doctor_schedule.py     # 对外接口
├── autoclaw_driver.py     # autoclaw 命令封装
├── recommender.py         # 推荐算法
└── schedule_cache.json    # 出诊表缓存(运行时生成)
```

### 脚本 vs Agent 职责划分

| 执行者 | 职责 |
|---|---|
| **脚本** | 发起 autoclaw 调用 → 解析结果文件 → 维护缓存 → 跑推荐算法 → 返回结构化 dict |
| **Agent / main_skill** | 把中间态(`awaiting_*`)转述给用户,收集回复后再次调用脚本 |

### 对外接口(3 个函数)

#### `list_experts(hospital_name, department, registration_url) -> dict`

用户未指名医生时调用,让 autoclaw 去官网抓该科室专家列表。

返回字段:
```python
{
    "status": "success" | "awaiting_browser_interaction" | "error",
    "experts": [
        {
            "name": "王立凡",
            "title": "主任医师",
            "specialty": "头痛、脑血管病",
            "profile_url": "...",   # 可选,若能从页面取得
        },
        ...
    ],
    "browser_session": {"session_id": "...", "tab_id": "..."},   # 仅中断态
    "interact_prompt": "...",                                     # 仅中断态
    "error": None | str,
}
```

#### `fetch_doctor_schedule(hospital_name, doctor_name, registration_url, user_preferences=None, browser_resume=None) -> dict`

抓某医生的出诊表 + 实时号源 + 生成推荐。

返回字段:
```python
{
    "status": "success"
            | "awaiting_browser_interaction"
            | "doctor_not_found"
            | "schedule_fetched_but_full"
            | "error",
    "schedule": {
        "doctor": {"name": "王立凡", "title": "主任医师", "specialty": "..."},
        "weekly_pattern": [
            {"weekday": "周一上午", "shift": "专家门诊"},
            {"weekday": "周三下午", "shift": "特需门诊"},
        ],
        "slots": [
            {"date": "2026-04-22", "period": "上午", "remaining": 3, "total": 20},
            ...
        ],
        "data_timestamp": "2026-04-20T10:30:00",
        "from_cache": {"weekly_pattern": True, "slots": False},
    },
    "recommendation": {
        "date": "2026-04-22",
        "period": "上午",
        "reason": "号源较充足(剩 3/20),距今 2 天,符合您'本周看'的时间偏好",
        "alternatives": [
            {"date": "2026-04-24", "period": "上午", "reason": "..."},
        ],
    },
    "warning": None | str,         # 全满时有文案
    "browser_session": {...},      # 仅中断态
    "interact_prompt": "...",      # 仅中断态
    "error": None | str,
}
```

**中断恢复**:两个函数都接收 `browser_resume` 参数,不单独暴露 resume 函数,避免接口膨胀。

---

## 4. autoclaw 调用封装与中断恢复

### `autoclaw_driver.run_browser_task(...)`

```python
def run_browser_task(
    task: str,
    start_url: Optional[str] = None,
    session_id: Optional[str] = None,
    tab_id: Optional[str] = None,
    timeout_sec: int = 300,   # 5 分钟上限(不用原生 2 小时)
) -> dict
```

返回:
```python
{
    "status": "success" | "interact_required" | "timeout" | "error",
    "session_id": "...",
    "tab_id": "...",
    "observation": "...",           # 结果 md 原文(去截图 base64)
    "structured": {...},            # 从 observation 抽到的结构化数据
    "interact_prompt": "...",       # 仅 interact_required
    "screenshots": [path, ...],     # md 文件里的截图路径(可选)
    "error": None | str,
}
```

### 内部流程

1. 构造 shell 命令,**单行、无 `\n`、task 原文不改写**:
   ```
   autoclaw task="..." start_url="..." session_id="..." tab_id="..."
   ```
2. `subprocess.run(cmd, timeout=timeout_sec, shell=True, capture_output=True, encoding='utf-8')`
3. 从 stdout 提取 `Result: <path>` 指针。**不用 process poll**。
4. 读取结果 md 文件,解析:
   - `session_id=` / `tabId=` 正则捕获
   - `[INTERACT_REQUIRED]` 标记 → `status='interact_required'`,`interact_prompt` 取标记后一段
   - 截图 markdown 路径保留,但内容不入返回(省 token)
5. **fallback**:stdout 丢失 → 读 `~/.openclaw-autoclaw/session_pool.json` 取最新 `session_id`,再读 `browser_result_{session_id}.md`

### 遵循的硬规则(来自 `autoglm-browser-agent` SKILL.md)

- `task` 参数里禁止双引号(遇到就替换成单引号)
- 一次调用返回后**绝不在同一流程里自动重试**(重试交由上层用户明确再触发)
- 命令**单行**,拼接时用 `shlex.join`(或等价方式)并检查无换行
- 每次调用前读 `session_pool.json`,按 SKILL.md 判断是否带 `session_id`/`tab_id`:
  - **同域名新任务** → 带 `session_id` + `tab_id`,不带 `start_url`
  - **不同域名或首次** → 不带 session,只带 `start_url`
  - **中断恢复** → 三个全带(`session_id` + `tab_id` + 原 `start_url`)

### 中断恢复的 task 改写规则

在 `doctor_schedule.py`(而非 driver)里做,因为需要"知道原任务是什么"。

| 中断类型 | 恢复时 task 前缀 |
|---|---|
| 登录 | `"用户已完成登录{hospital_name}官网。"` + 原任务剩余部分 |
| 验证码 | `"用户已完成验证码。"` + 原任务剩余部分 |
| 敏感确认 | `"用户已同意<具体操作>,请直接完成该操作。"` + 原任务剩余部分 |

### 两个 autoclaw task 模板

```python
TASK_LIST_EXPERTS = (
    "打开{registration_url},进入{department}科室介绍页,"
    "列出该科室所有出诊专家,返回每位的姓名、职称(主任/副主任/主治)、"
    "擅长领域简介,最多10位。以表格形式输出。"
)

TASK_FETCH_SCHEDULE = (
    "打开{registration_url},搜索医生'{doctor_name}',"
    "进入其个人主页,读取未来14天的出诊排班表,"
    "每个时段标注'剩余号数/总号数'。以结构化列表输出。"
)
```

模板**纯自然语、无双引号**。用户原始需求中的额外约束(如"周末的号")由 `doctor_schedule.py` 原样追加到 task 末尾。

---

## 5. 缓存策略

### 文件

`skills/healthpath-doctor-schedule/schedule_cache.json`(JSON,风格对齐 `registration_fetcher/hospital_info.json`)。

### 结构

```json
{
  "北京协和医院::王立凡": {
    "doctor_meta": {
      "name": "王立凡",
      "title": "主任医师",
      "specialty": "头痛、脑血管病"
    },
    "weekly_pattern": [
      {"weekday": "周一上午", "shift": "专家门诊"},
      {"weekday": "周三下午", "shift": "特需门诊"}
    ],
    "weekly_pattern_cached_at": "2026-04-20T10:30:00",
    "weekly_pattern_ttl_days": 7
  }
}
```

- **键**: `"{hospital_name}::{doctor_name}"`(`::` 分隔,避免医生重名跨院冲突)
- **只缓存** `doctor_meta` + `weekly_pattern`(半静态,7 天 TTL)
- **不缓存** `slots`(剩余号源)— 每次实时从 autoclaw 抓
- TTL 过期 → 整个 entry 删除,下次重新抓

### 命中逻辑

```
fetch_doctor_schedule 调用:
  1. 读 cache
  2. 命中且未过期 → weekly_pattern 从缓存取,只跑一次 autoclaw 抓 slots(task 更短,通常 30 秒)
  3. 未命中或过期 → 跑一次 autoclaw 抓全量(pattern + slots),成功后写回缓存
  4. 返回 from_cache 字段明示来源
```

### 强制规则

- **严禁缓存 `slots`**(号源实时,缓存必误导)
- `session_id`/`tab_id` **仅在返回字段里透传**,不写入缓存

---

## 6. 推荐算法(`recommender.py`)

### 输入

- `slots: [{date, period, remaining, total}, ...]`(已按日期升序)
- `user_preferences: {time_window, weekend_only, preferred_period, ...}`(来自 `intent_parser`)

### 评分维度

每个 slot 打 0-100 分,加权求和:

| 维度 | 权重 | 规则 |
|---|---|---|
| **号源充足度** | 40 | `remaining/total`:≥0.5 记 40 分,0.2-0.5 线性映射到 16-40 分,<0.2 计 0,=0 直接过滤(不进入排序) |
| **时效贴近** | 30 | 距今 2-5 天最高;1 天(可能来不及)、7+ 天(太远)分数递减 |
| **时间偏好** | 20 | `time_window=weekend` → 周六/日加满分;`preferred_period=上午` → 上午加满分 |
| **避开满诊** | 10 | 纯过滤位,`remaining=0` 直接剔除 |

### 输出

- 按总分降序
- 第 1 个作为 `recommendation`
- 第 2-3 个作为 `alternatives`

### `reason` 字段(模板化,中文,用户友好)

```
"号源较充足(剩 3/20),距今 2 天,符合您'本周看'的时间偏好"
```

### 全部满诊

- `recommendation = None`
- `alternatives = []`
- `warning = "未来 14 天该医生号源均已约满,建议改挂同科室其他专家或关注下周放号"`
- main_skill 据此显式提示用户,而非静默返回空

---

## 7. 降级路径

对齐现有三层降级风格(Baidu Map 不可用 → rough 估算;reportlab 不可用 → .txt):

| 层级 | 触发 | 降级行为 |
|---|---|---|
| **L1 autoclaw 不可用** | 以下任一满足:①`shutil.which("autoclaw")` 为 `None` ②`~/.openclaw-autoclaw` 目录不存在 ③`subprocess.run` 抛 `FileNotFoundError` / `TimeoutExpired`(5 分钟超时) | 跳过 doctor-schedule,`status='success'` 但 `doctor_schedule=None`;PDF 里只写"请到 {registration_url} 自行查找 {doctor_name} 的号源";流程不中断 |
| **L2 官网抓取失败** | autoclaw 返回 error / 结果里找不到医生 / 医生名拼写不符 | 返回 `status='doctor_not_found'`,附建议("是否医生名有误?"),让 agent 请用户确认或改走专家列表分支 |
| **L3 号源全满** | 推荐算法 `recommendation=None` | `status='schedule_fetched_but_full'`,附 `warning`,itinerary 仍生成,PDF 里印提示"近 14 天已满,建议下周再查" |

**核心原则**:**不得因本 skill 失败让整条流程崩溃**。registration_fetcher 已拿到 URL 是用户的最低可接受交付物。

---

## 8. 与现有硬约束的一致性

对齐 `SKILL_PREFERENCES.md` 禁令:

- ✅ **不自行编造 URL** — `registration_url` 只能从 `registration_fetcher.fetch()` 结果来,本 skill 不做网络搜索、不猜域名
- ✅ **warning_flags 非空立即终止** — 在 Step 2 已处理,不重复校验
- ✅ **itinerary 仍是终态** — 本 skill 输出经 main_skill 整合后喂给 Step 6
- ✅ **PDF 是默认输出,不询问** — doctor_schedule 结果附加到 PDF,不改变 mandatory 性

### 新增硬约束(写入 `SKILL_PREFERENCES.md` + 本 skill SKILL.md)

1. **autoclaw 调用一次对话最多 1 次** — 遵循 autoglm-browser-agent 规则,同一轮不重试
2. **task 参数用户原话不改写** — 模板填充时校验无双引号、无换行、无多余约束
3. **禁止缓存实时号源** — `slots` 字段每次实时抓,缓存命中时也要重新抓 slots
4. **session_id/tab_id 透传而非存本地** — 仅在 `browser_session` 字段里传出,由 agent/调用方持有,不写入 cache

---

## 9. 测试策略

新增 `tests/test_doctor_schedule.py`,涵盖:

```
test_list_experts_happy_path             # mock autoclaw_driver,验证结构
test_list_experts_interact_required      # 模拟登录中断态透传
test_fetch_schedule_cache_hit            # 命中 weekly_pattern 缓存,仅跑 slots
test_fetch_schedule_cache_miss           # miss → 抓全量 → 写回缓存
test_recommender_full_booked             # 全满 → warning
test_recommender_weekend_preference      # 用户要周末 → 命中周六推荐
test_main_skill_doctor_flow_integration  # main_skill 端到端,autoclaw 用 fake driver
```

**fake driver**:`autoclaw_driver.run_browser_task` 在测试里 monkeypatch 为固定 dict,避免真跑浏览器。

---

## 10. 范围外(明确不做)

- 全自动登录、自动选号、自动支付
- 跨院推荐同科室备选医生
- 实时号源变化通知/抢号
- 适配非北京医院网站的特化规则(依赖 autoclaw 自然语义覆盖)
- 微信/小程序挂号入口
- 异步任务队列与 poll 接口(方案 B 被否决)

---

## 11. 实施次序(供 writing-plans 参考)

1. 新 skill 骨架:`skills/healthpath-doctor-schedule/{SKILL.md, _meta.json, doctor_schedule.py, autoclaw_driver.py, recommender.py}`
2. `autoclaw_driver.py`:先写核心调用 + 结果解析,配 fake 模式便于测试
3. `recommender.py`:纯函数,易测
4. `doctor_schedule.py`:串起 driver + cache + recommender + 中断恢复
5. `intent_parser.py`:扩展 `doctor_name` 字段
6. `main_skill.py`:扩展 `execute()` 签名、状态机分支、参数透传
7. `itinerary_builder.py`:PDF 模板里加医生 + 推荐时段段落
8. `SKILL_PREFERENCES.md`:补充新约束
9. `config/autoclaw_integration.py`:在技能注册清单中加入 `healthpath-doctor-schedule`
10. 测试:`tests/test_doctor_schedule.py` + 扩展 `tests/test_integration.py`
11. 手动端到端:在真 autoclaw 环境跑一遍"协和神经内科王立凡"案例
