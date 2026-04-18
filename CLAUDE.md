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
# Quick smoke test of the main agent (v2.0 hierarchy)
python main_skill.py

# Run integration tests (unified 5-step hierarchy)
python tests/test_integration.py

# Run end-to-end smoke test
python tests/test_end_to_end.py

# Run demo
python demo/demo.py

# Register / re-register skills with AutoClaw
python config/autoclaw_integration.py

# Lint / format / type check
flake8 .
black .
mypy .
```

## Architecture

The system now uses a **single unified 5-step hierarchy** orchestrated by `main_skill.py`.

| Directory | Module | Role |
|---|---|---|
| `skills/healthpath-intent-understanding/` | `intent_parser.parse_intent()` | 意图结构化 |
| `skills/healthpath-symptom-triage/` | `symptom_triage.triage()` | 症状分诊 / 科室推荐 |
| `skills/healthpath-hospital-matcher/` | `hospital_matcher.match()` | 附近医院匹配 (CSV + Baidu Map) |
| `skills/healthpath-registration-fetcher/` | `registration_fetcher.fetch()` | 医院官网/挂号链接采集 |
| `skills/healthpath-itinerary-builder/` | `itinerary_builder.build()` | 路线规划 + PDF 行程单生成 |

**Entry point**: `execute(user_input, user_location=None, selected_hospital=None, extra_answers=None, output_format="large_font_pdf", user_profile=None)` returns:

```python
{
  "status":       "success" | "need_more_info" | "need_location" | "awaiting_hospital_selection" | "emergency_warning" | "error",
  "steps":        {"triage": {...}, "match": {...}, "registration": {...}, "itinerary": {...}},
  "final_output": {"pdf_path": "...", "depart_time": "...", "route": "...", "registration_url": "..."},
  "follow_up":    [...],   # non-empty when status requires user input
  "error":        null | str
}
```

The flow is **conversational and stateful** — `execute()` returns early to ask for location (`need_location`) or hospital selection (`awaiting_hospital_selection`), expecting a follow-up call with user answers.

### Supporting Components

- **`config/config.py`** — `Config` class; reads `BAIDU_MAP_AUTH_TOKEN` and `OUTPUT_DIR` from env. `BASE_DIR` / `OUTPUT_DIR` / `MOCK_DATA_DIR` paths all derived here.
- **`config/deepseek_client.py`** — DeepSeek API wrapper (optional; current main flow defaults to rule-based intent parsing).
- **`config/autoclaw_integration.py`** — Registers all skills into AutoClaw's `openclaw.json`.
- **`data/mock/`** — Mock hospital data (`hospitals.json`, `available_slots.json`) used when real APIs are unavailable.
- **`data/医疗机构基本信息2023-03-29.csv`** — Real Beijing hospital CSV (4,311 entries) used by `hospital_matcher` as the primary data source.
- **`cache/`** — SQLite `hospital_cache.db` for registration URL caching; managed by `registration_fetcher` via `save_to_cache()`.
- **`lib/`** — Vendored Python packages (reportlab, openpyxl, bs4, lxml, requests, etc.) added to `sys.path` at runtime. Import from here when system packages are unavailable.
- **`skills/baidu-ai-map/`** — Baidu Map MCP skill; consulted by `hospital_matcher` for precise distances and by `itinerary_builder` for routing.

## Key Patterns

**Path injection** — Each skill inserts its own directory into `sys.path[0]` at module load. No `__init__.py` files anywhere. Import modules by bare name after the insert.

**Output formats** — `output_format="large_font_pdf"` (28pt titles, 16pt body, high contrast, elderly-friendly) | `"pdf"` (standard). Default is `large_font_pdf`.

**Graceful degradation (three layers)**:
1. Baidu Map MCP unavailable → rough district-level distance estimate, flagged "仅供参考"
2. `reportlab` unavailable → `.txt` fallback (full content preserved)
3. Real hospital data unavailable → `data/mock/` data

**Preference extraction** — `_extract_preferences()` in `main_skill.py` sets `hospital_level`, `max_distance_km`, and `travel_mode` from the user's text and `user_profile.age_group`.

**Hospital blacklist** — Use `hospital_matcher.add_to_blacklist()` API; never edit `blacklist.json` directly.

## Skill Workflow Rules (from `SKILL_PREFERENCES.md`)

These are hard constraints — enforce them in code, never bypass:

- If `triage_result["warning_flags"]` is non-empty → set `status = "emergency_warning"`, instruct user to call 120, and **return immediately** without continuing the booking flow.
- Never infer department directly from symptoms — always call `symptom_triage` first (skip only if department is already explicit in user input).
- Never fabricate hospital official URLs — always use `registration_fetcher.fetch()` then validate HTTP < 400, then call `save_to_cache()`.
- Never present an unvalidated `official_url` to the user.
- `itinerary_builder` is the terminal step — no skill runs after it.
- PDF generation is mandatory at step 5; do not ask the user if they want it.

## Environment

- Python 3.9+
- `BAIDU_MAP_AUTH_TOKEN` env var — enables full-country hospital search and precise routing (without it, falls back to local Beijing CSV + district estimates)
- `DEEPSEEK_API_KEY` env var — optional for DeepSeek-based intent extraction
- `OUTPUT_DIR` env var (if not set, itinerary output defaults to `_generated/` under project root)
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

