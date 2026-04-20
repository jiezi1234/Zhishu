# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Identity Override for AutoClaw Workspace

**IMPORTANT**: When working in this AutoClaw workspace, you are operating as the **智枢 (Zhishu) HealthPath Agent**, not as Claude. This workspace has its own identity defined in `SOUL.md` and `AGENTS.md`. Read and follow those files for your identity, tone, and behavior in this context.

This identity override applies ONLY within this workspace. Outside this workspace, you remain Claude by Anthropic.

---

## Project Overview

**智枢** — 基于长链路协同的全人群医旅调度智能体。A Python-based intelligent medical appointment scheduling system deployed as an AutoClaw skill. Users describe medical needs in natural language; the system produces ranked hospital recommendations and a formatted itinerary (PDF).

AutoClaw runs at `http://127.0.0.1:18789`. The skill is invoked via `from main_skill import execute`.

## Commands

```bash
# Quick smoke test of the main agent (unified 5-step hierarchy, v3.0.0)
python main_skill.py

# Run integration tests
python tests/test_integration.py
# Or a single test via pytest:
pytest tests/test_integration.py::test_execute_full_flow_generates_output -v

# Run end-to-end smoke test
python tests/test_end_to_end.py

# Run demo
python demo/demo.py

# Verify PDF output renders correctly (parses a generated PDF)
python demo/parse_pdf.py

# Register / re-register skills with AutoClaw
python config/autoclaw_integration.py

# Lint / format / type check
flake8 .
black .
mypy .
```

## Architecture

The system now uses a **single unified 6-step hierarchy** orchestrated by `main_skill.py`.

| Directory | Module | Role |
|---|---|---|
| `skills/healthpath-intent-understanding/` | `intent_parser.parse_intent()` | 意图结构化(含 `doctor_name` 抽取) |
| `skills/healthpath-symptom-triage/` | `symptom_triage.triage()` | 症状分诊 / 科室推荐 |
| `skills/healthpath-hospital-matcher/` | `hospital_matcher.match()` | 附近医院匹配 (CSV + Baidu Map) |
| `skills/healthpath-registration-fetcher/` | `registration_fetcher.fetch()` | 医院官网/挂号链接采集 |
| `skills/healthpath-doctor-schedule/` | `doctor_schedule.list_experts()` / `fetch_doctor_schedule()` | AutoClaw 浏览器抓医生出诊表+号源,按评分推荐就诊时段 |
| `skills/healthpath-itinerary-builder/` | `itinerary_builder.build()` | 路线规划 + PDF 行程单生成(含医生与推荐信息) |

**Entry point**: `execute(user_input, user_location=None, selected_hospital=None, selected_doctor=None, browser_resume=None, confirmed_appointment=None, extra_answers=None, output_format="large_font_pdf", user_profile=None)` returns:

```python
{
  "status":       "success"
                | "need_more_info" | "need_location"
                | "awaiting_hospital_selection"
                | "awaiting_doctor_selection"            # 新
                | "awaiting_browser_interaction"         # 新
                | "doctor_schedule_fetched"              # 新
                | "doctor_not_found"                     # 新
                | "schedule_fetched_but_full"            # 新
                | "emergency_warning" | "error",
  "steps":        {"triage": {...}, "match": {...}, "registration": {...}, "doctor_schedule": {...}, "itinerary": {...}},
  "final_output": {"pdf_path": "...", "depart_time": "...", "route": "...", "registration_url": "...", "doctor": {...}, "recommendation": {...}},
  "follow_up":    [...],   # non-empty when status requires user input
  "error":        null | str
}
```

The flow is **conversational and stateful** — `execute()` returns early to ask for location (`need_location`), hospital selection (`awaiting_hospital_selection`), doctor selection (`awaiting_doctor_selection`), browser interaction (`awaiting_browser_interaction`), or recommendation confirmation (`doctor_schedule_fetched`), expecting a follow-up call with user answers.

### Supporting Components

- **`config/config.py`** — `Config` class; reads `BAIDU_MAP_AUTH_TOKEN` and `OUTPUT_DIR` from env. `BASE_DIR` / `OUTPUT_DIR` (defaults to `<project>/output/`) / `MOCK_DATA_DIR` paths all derived here.
- **`config/deepseek_client.py`** — DeepSeek API wrapper (optional; current main flow defaults to rule-based intent parsing).
- **`config/semantic_matcher.py`** — Semantic similarity engine backing symptom triage and intent understanding. Uses `sentence-transformers` with `BAAI/bge-small-zh-v1.5` (~90MB; override via `ST_MODEL`). Model downloads through `HF_ENDPOINT` (defaults to `hf-mirror.com` for CN users).
- **`config/autoclaw_integration.py`** — Registers all skills into AutoClaw's `openclaw.json`.
- **`skills/healthpath-doctor-schedule/autoclaw_driver.py`** — Wraps `subprocess` calls to the `autoclaw` CLI. 5-minute timeout. Parses `Result: <path>` pointer → reads MD file → extracts `session_id`/`tab_id`/`[INTERACT_REQUIRED]` prompts. Strictly enforces `autoglm-browser-agent` SKILL rules: no auto-retry, single-line command, double-quote sanitization.
- **`skills/healthpath-doctor-schedule/recommender.py`** — Pure-function scoring. 维度与权重:号源充足度 40 / 时效贴近 30 / 时间偏好 20 / 避开满诊 10(过滤位)。
- **`skills/healthpath-doctor-schedule/schedule_cache.json`** — 医生出诊表缓存(`doctor_meta` + `weekly_pattern`),键为 `"{hospital_name}::{doctor_name}"`,TTL 7 天。**`slots` 绝不缓存**,每次实时抓。
- **`data/mock/`** — Mock hospital data (`hospitals.json`, `available_slots.json`) used when real APIs are unavailable.
- **`data/医疗机构基本信息2023-03-29.csv`** — Real Beijing hospital CSV (4,311 entries) used by `hospital_matcher` as the primary data source.
- **`cache/`** — SQLite `hospital_cache.db` for registration URL caching; managed by `registration_fetcher` via `save_to_cache()`.
- **`lib/`** — Vendored Python packages (reportlab, openpyxl, bs4, lxml, requests, etc.) added to `sys.path` at runtime. Import from here when system packages are unavailable.
- **`skills/baidu-ai-map/`** — Baidu Map MCP skill; consulted by `hospital_matcher` for precise distances and by `itinerary_builder` for routing.
- **`~/.openclaw-autoclaw/skills/autoglm-browser-agent/`** — AutoClaw 的浏览器控制 skill;`doctor-schedule` 通过 shell 调用 `autoclaw task="..."` 命令触发它。

## Key Patterns

**Path injection** — Each skill inserts its own directory into `sys.path[0]` at module load. No `__init__.py` files anywhere. Import modules by bare name after the insert.

**Output formats** — `output_format="large_font_pdf"` (28pt titles, 16pt body, high contrast, elderly-friendly) | `"pdf"` (standard). Default is `large_font_pdf`.

**Graceful degradation (four layers)**:
1. Baidu Map MCP unavailable → rough district-level distance estimate, flagged "仅供参考"
2. `reportlab` unavailable → `.txt` fallback (full content preserved)
3. Real hospital data unavailable → `data/mock/` data
4. **AutoClaw CLI unavailable / 5 分钟超时** → doctor-schedule step 静默跳过(Step 5 → Step 6 直接继续),PDF 里只印官网 URL,不印推荐时段

**Preference extraction** — `_extract_preferences()` in `main_skill.py` sets `hospital_level`, `max_distance_km`, and `travel_mode` from the user's text and `user_profile.age_group`.

**Hospital blacklist** — Use `hospital_matcher.add_to_blacklist()` API; never edit `blacklist.json` directly.

**Doctor name extraction** — `intent_parser.extract_doctor_name()` 用触发词("医生/大夫/主任医师/副主任医师/主任")+ 无效姓氏起始字(如"院""挂""的")过滤,支持"挂 X 医生的号"、"找 X 大夫"、"X 主任"等中文口语表达。

**Browser session resume** — 当 doctor-schedule 返回 `awaiting_browser_interaction` 时,上层调用方须保存 `browser_session.session_id` 与 `tab_id`;用户完成登录/验证码后,再次调 `execute(..., browser_resume={session_id, tab_id, user_action})` 恢复。`user_action` 支持 `"login_done"` / `"captcha_done"` / `"approve"` / `"reject"` 或自由文本。

## Skill Workflow Rules (from `SKILL_PREFERENCES.md`)

These are hard constraints — enforce them in code, never bypass:

- If `triage_result["warning_flags"]` is non-empty → set `status = "emergency_warning"`, instruct user to call 120, and **return immediately** without continuing the booking flow.
- Never infer department directly from symptoms — always call `symptom_triage` first (skip only if department is already explicit in user input).
- Never fabricate hospital official URLs — always use `registration_fetcher.fetch()` then validate HTTP < 400, then call `save_to_cache()`.
- Never present an unvalidated `official_url` to the user.
- `itinerary_builder` is the terminal step — no skill runs after it.
- PDF generation is mandatory at step 6; do not ask the user if they want it.
- **doctor-schedule 一次对话最多触发 1 次 autoclaw**,不得自动重试,重试须由用户下一轮主动发起。
- **禁止缓存 `slots` 字段**,号源实时变动,缓存必误导用户。
- **doctor-schedule 失败时必须回退到"官网 URL + 无推荐时段"的 PDF**,不得阻塞整个流程。
- **`registration_url` 只能来自 `registration_fetcher`**,doctor-schedule 不做网络搜索、不猜域名。

## Environment

- Python 3.9+
- `BAIDU_MAP_AUTH_TOKEN` env var — enables full-country hospital search and precise routing (without it, falls back to local Beijing CSV + district estimates)
- `DEEPSEEK_API_KEY` env var — optional for DeepSeek-based intent extraction
- `OUTPUT_DIR` env var — if not set, itinerary output defaults to `<project>/output/`
- `HF_ENDPOINT` env var — HuggingFace mirror for semantic model download; defaults to `hf-mirror.com` (CN-friendly)
- `ST_MODEL` env var — override semantic model (default `BAAI/bge-small-zh-v1.5`; upgrade to `BAAI/bge-base-zh-v1.5` for ~400MB higher-precision variant)
- `autoclaw` CLI — required for Step 5 (doctor-schedule) to actually drive the browser. 装好后浏览器扩展已启用即可;未安装时 doctor-schedule 会静默降级。
- Copy `.env.example` → `.env` and fill in keys before running

## AutoClaw Integration

Skills are registered in `C:\Users\Administrator\.openclaw-autoclaw\openclaw.json`. The `allowBundled` list must include the skill names and `workspaceOnly` must be `false`. If a skill is reported as unavailable, re-run `python config/autoclaw_integration.py` and restart AutoClaw.

Gateway logs: `~/.openclaw-autoclaw/logs/gateway.log`

## Workspace Continuity Files

Read these at session start to understand current state:

- `SOUL.md` — agent identity and behavioral guidelines
- `AGENTS.md` — workspace rules, security policies, memory conventions, heartbeat protocol
- `SKILL_PREFERENCES.md` — HealthPath-specific 5-step workflow, skill trigger conditions, decision table
- `TOOLS.md` — environment-specific tool notes
- `USER.md` — owner identity and preferences
- `memory/YYYY-MM-DD.md` — daily session logs (create `memory/` if needed)

