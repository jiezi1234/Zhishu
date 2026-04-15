# CLAUDE.md

## Identity Override for AutoClaw Workspace

**IMPORTANT**: When working in this AutoClaw workspace, you are operating as the **智枢 (Zhishu) HealthPath Agent**, not as Claude. This workspace has its own identity defined in `SOUL.md` and `AGENTS.md`. Read and follow those files for your identity, tone, and behavior in this context.

This identity override applies ONLY within this workspace. Outside this workspace, you remain Claude by Anthropic.

---

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**智枢 (Zhishu) / HealthPath Agent** — 全人群智能就医调度与医旅管家。A Python-based intelligent medical appointment scheduling system deployed as an AutoClaw skill. Users describe medical needs in natural language; the system produces ranked hospital recommendations and a formatted itinerary (PDF/Excel).

AutoClaw runs at `http://127.0.0.1:18789`. The skill is invoked via `from main_skill import execute`.

## Commands

```bash
# Run integration test (end-to-end, all 4 skills)
python tests/test_integration.py

# Quick smoke test of the main agent
python main_skill.py

# Run demo
python demo/demo.py

# Register / re-register skills with AutoClaw
python config/autoclaw_integration.py

# Lint
flake8 .

# Type check
mypy .

# Format
black .
```

## Architecture

The system has **two parallel skill hierarchies** that solve the same problem at different levels of abstraction. Be aware of which one you are working in:

### Hierarchy A — v2.0 (skills/symptom_triage et al.)
`main_skill.py` orchestrates four skills loaded from `skills/`:

| Directory | Module | Role |
|---|---|---|
| `skills/symptom_triage/` | `symptom_triage.triage()` | 病情预判 / 科室推荐 |
| `skills/hospital_matcher/` | `hospital_matcher.match()` | 附近医院匹配 (CSV + Baidu Map) |
| `skills/registration_fetcher/` | `registration_fetcher.fetch()` | 医院官网 URL 采集 |
| `skills/itinerary_builder/` | `itinerary_builder.build()` | 路线规划 + PDF 行程单生成 |

**Entry point**: `main_skill.execute(user_input, user_location, selected_hospital, ...)` → returns a dict with `status`, `steps`, `final_output`, `follow_up`, `error`.

The flow is conversational and stateful — `execute()` may return early with `status = "need_location"` or `"awaiting_hospital_selection"` expecting a second call with the user's answer.

### Hierarchy B — v1.0 (skills/skill_1_intent … skill_4_output)
Used by `tests/test_integration.py`. These are the original 4-skill design registered as separate AutoClaw skills:

| Directory | Module | Role |
|---|---|---|
| `skills/skill_1_intent/` | `intent_parser.parse_intent()` | 意图理解 (DeepSeek API) |
| `skills/skill_2_crawl/` | `hospital_crawler.search_available_slots()` | 跨院号源巡航 |
| `skills/skill_3_decision/` | `decision_engine.evaluate_and_rank()` | 多目标决策评分 |
| `skills/skill_4_output/` | `output_generator.generate_output()` | PDF / Excel 生成 |

### Supporting Components

- **`config/config.py`** — `Config` class; reads `DEEPSEEK_API_KEY` from env (falls back to hardcoded key). Sets `MOCK_DATA_DIR` and `OUTPUT_DIR`.
- **`config/deepseek_client.py`** — DeepSeek API wrapper.
- **`config/autoclaw_integration.py`** — Registers all skills into AutoClaw's `openclaw.json`.
- **`data/mock/`** — Mock hospital data (`hospitals.json`, `available_slots.json`) used when real APIs are unavailable.
- **`data/real/`** — Real hospital CSV (`医疗机构基本信息2023-03-29.csv`) used by `hospital_matcher`.
- **`lib/`** — Vendored Python packages (reportlab, openpyxl, bs4, etc.) installed locally; included in `sys.path` at runtime.

## Key Patterns

**Path injection** — Each skill adds its own directory to `sys.path` at module load time. There are no package `__init__.py` files; skills are imported by name after `sys.path.insert()`.

**Output formats** — `output_format="large_font_pdf"` (16pt+, high contrast, elderly-friendly) vs `"pdf"` (standard) vs `"excel"`. Defaults to `large_font_pdf`.

**Graceful degradation** — Baidu Map MCP unavailable → rough district estimate (flagged "仅供参考"). `reportlab` unavailable → `.txt` fallback. Real hospital data unavailable → mock data.

**Skill workflow rules** (from `SKILL_PREFERENCES.md`) — enforce these in code:
- Never skip `symptom_triage` to infer department directly from symptoms.
- If `warning_flags` is non-empty, halt and instruct user to call 120; do not continue booking.
- Never fabricate hospital official URLs — always go through `registration_fetcher` + HTTP validation.
- `itinerary_builder` is the terminal step; nothing runs after it.

## AutoClaw Integration

Skills are registered in `C:\Users\Administrator\.openclaw-autoclaw\openclaw.json`. The `allowBundled` list must include the skill names and `workspaceOnly` must be `false`. If a skill is reported as unavailable, re-run `python config/autoclaw_integration.py` and restart AutoClaw.

Gateway logs: `~/.openclaw-autoclaw/logs/gateway.log`

## Environment

- Python 3.9+
- `DEEPSEEK_API_KEY` env var (or use the default in `config/config.py`)
- Dependencies in `requirements.txt`; also vendored under `lib/`
