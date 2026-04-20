# 医生出诊表/号源浏览器查询 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `healthpath-doctor-schedule` skill,基于 AutoClaw 浏览器控制能力(`autoclaw task="..."`)实现"用户指名医生 → 自动去挂号官网抓出诊表+号源 → 打分推荐就诊时间 → 写入 PDF 行程单"的完整链路。遇登录等中断时透传 `session_id`/`tab_id` 让上层恢复。

**Architecture:** 5 步流程 → 6 步。新 skill 拆三文件:`recommender.py`(纯函数打分)、`autoclaw_driver.py`(subprocess 调用与结果解析)、`doctor_schedule.py`(主入口 + 缓存 + 解析)。`main_skill.execute()` 新增 3 个参数与 3 个中间态 status(`awaiting_doctor_selection`/`awaiting_browser_interaction`/`doctor_schedule_fetched`)。出诊表 7 天缓存、号源实时;三层降级保证 autoclaw 失败不阻塞原流程。

**Tech Stack:** Python 3.9+、subprocess、json 文件缓存、pytest、AutoClaw CLI(`autoclaw` 命令)、sentence-transformers(现有,不动)

**Spec:** `docs/superpowers/specs/2026-04-20-doctor-schedule-browser-design.md`

---

## File Structure

**新建(6 个源 + 4 个测试):**
- `skills/healthpath-doctor-schedule/SKILL.md` — 使用说明
- `skills/healthpath-doctor-schedule/_meta.json` — openclaw 元数据
- `skills/healthpath-doctor-schedule/recommender.py` — 推荐打分(纯函数)
- `skills/healthpath-doctor-schedule/autoclaw_driver.py` — autoclaw 命令封装
- `skills/healthpath-doctor-schedule/doctor_schedule.py` — 对外接口 + 缓存 + 解析
- `skills/healthpath-doctor-schedule/schedule_cache.json` — 运行时生成,不提交空壳(放入 `.gitignore`)
- `tests/test_doctor_recommender.py`
- `tests/test_doctor_autoclaw_driver.py`
- `tests/test_doctor_schedule.py`
- `tests/test_intent_parser_doctor_name.py`

**修改:**
- `skills/healthpath-intent-understanding/intent_parser.py` — 新增 `extract_doctor_name()` + 写入返回字段
- `main_skill.py` — `execute()` 签名加 3 参数、状态机加 3 分支
- `skills/healthpath-itinerary-builder/itinerary_builder.py` — `build()` 收 `doctor_schedule` 参数,写入 `task_params` & 在 `nav_steps` 首部加推荐提示
- `SKILL_PREFERENCES.md` — 新增 6 步工作流说明 + doctor-schedule 约束
- `config/autoclaw_integration.py` — 注册清单加 `healthpath-doctor-schedule`
- `tests/test_integration.py` — 加医生流程端到端 case
- `.gitignore` — 忽略 `schedule_cache.json`

---

### Task 1: 推荐打分器(纯函数,TDD)

**Files:**
- Create: `skills/healthpath-doctor-schedule/recommender.py`
- Test: `tests/test_doctor_recommender.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_doctor_recommender.py`:

```python
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-doctor-schedule"
))

from recommender import recommend


def _slot(d, period, remaining, total):
    return {"date": d, "period": period, "remaining": remaining, "total": total}


def test_all_full_returns_warning():
    slots = [_slot("2026-04-22", "上午", 0, 20), _slot("2026-04-23", "下午", 0, 20)]
    r = recommend(slots, today=date(2026, 4, 20))
    assert r["recommendation"] is None
    assert r["alternatives"] == []
    assert "约满" in r["warning"]


def test_sufficient_availability_scores_higher_than_tight():
    slots = [
        _slot("2026-04-22", "上午", 15, 20),  # 充足 0.75
        _slot("2026-04-22", "下午", 1, 20),   # 紧张 0.05 → 过滤
        _slot("2026-04-23", "上午", 5, 20),   # 较充足 0.25
    ]
    r = recommend(slots, today=date(2026, 4, 20))
    assert r["recommendation"]["date"] == "2026-04-22"
    assert r["recommendation"]["period"] == "上午"
    assert "号源充足" in r["recommendation"]["reason"]


def test_weekend_preference_is_respected():
    # 2026-04-25 是周六(date.weekday()==5)
    slots = [
        _slot("2026-04-22", "上午", 10, 20),  # 周三
        _slot("2026-04-25", "上午", 10, 20),  # 周六
    ]
    r = recommend(slots, user_preferences={"time_window": "weekend"},
                  today=date(2026, 4, 20))
    assert r["recommendation"]["date"] == "2026-04-25"


def test_too_far_gets_lower_score_than_sweet_spot():
    slots = [
        _slot("2026-04-22", "上午", 10, 20),  # 2 天后,甜蜜区
        _slot("2026-05-03", "上午", 10, 20),  # 13 天后,远
    ]
    r = recommend(slots, today=date(2026, 4, 20))
    assert r["recommendation"]["date"] == "2026-04-22"


def test_reason_contains_remaining_counts_and_time_preference():
    slots = [_slot("2026-04-22", "上午", 3, 20)]
    r = recommend(slots, user_preferences={"time_window": "this_week"},
                  today=date(2026, 4, 20))
    assert "3/20" in r["recommendation"]["reason"]
    assert "本周" in r["recommendation"]["reason"]


def test_alternatives_limited_to_two():
    slots = [_slot(f"2026-04-{22+i}", "上午", 10, 20) for i in range(5)]
    r = recommend(slots, today=date(2026, 4, 20))
    assert len(r["alternatives"]) == 2
```

- [ ] **Step 2: 验证失败**

Run: `pytest tests/test_doctor_recommender.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'recommender'`

- [ ] **Step 3: 实现 recommender.py**

Create `skills/healthpath-doctor-schedule/recommender.py`:

```python
"""
recommender.py — 就诊时段推荐打分。

维度与权重(总 100 分):
  号源充足度 40 | 时效贴近 30 | 时间偏好 20 | 避开满诊 10(过滤位)
"""

from datetime import date, datetime, timedelta
from typing import Optional


def recommend(
    slots: list,
    user_preferences: Optional[dict] = None,
    today: Optional[date] = None,
) -> dict:
    prefs = user_preferences or {}
    today = today or date.today()

    usable = [s for s in slots if int(s.get("remaining", 0)) > 0]
    if not usable:
        return {
            "recommendation": None,
            "alternatives": [],
            "warning": "未来 14 天该医生号源均已约满,建议改挂同科室其他专家或关注下周放号",
        }

    scored = sorted(
        [(_score(s, prefs, today), s) for s in usable],
        key=lambda x: -x[0],
    )
    top_score, top_slot = scored[0]
    return {
        "recommendation": _with_reason(top_slot, prefs, today),
        "alternatives": [_with_reason(s, prefs, today) for _, s in scored[1:3]],
        "warning": None,
    }


def _score(slot: dict, prefs: dict, today: date) -> float:
    remaining = int(slot.get("remaining", 0))
    total = int(slot.get("total", 1)) or 1
    ratio = remaining / total

    # 维度 1:号源充足度 0-40
    if ratio >= 0.5:
        score_avail = 40
    elif ratio >= 0.2:
        score_avail = 16 + (ratio - 0.2) * (40 - 16) / (0.5 - 0.2)
    else:
        score_avail = 0

    # 维度 2:时效贴近 0-30
    slot_date = _parse_date(slot.get("date", ""))
    if slot_date is None:
        score_time = 15
    else:
        days = (slot_date - today).days
        if days < 0:
            score_time = 0
        elif days == 0:
            score_time = 15
        elif days == 1:
            score_time = 22
        elif 2 <= days <= 5:
            score_time = 30
        elif 6 <= days <= 7:
            score_time = 22
        elif days <= 14:
            score_time = 15
        else:
            score_time = 8

    # 维度 3:时间偏好 0-20
    score_pref = 5
    period = slot.get("period", "")
    if prefs.get("preferred_period") and prefs["preferred_period"] in period:
        score_pref += 10
    tw = prefs.get("time_window", "")
    if tw == "weekend" and slot_date and slot_date.weekday() >= 5:
        score_pref = 20
    elif tw in ("today", "tomorrow") and slot_date:
        want = today if tw == "today" else today + timedelta(days=1)
        if slot_date == want:
            score_pref = 20

    return score_avail + score_time + score_pref


def _with_reason(slot: dict, prefs: dict, today: date) -> dict:
    remaining = int(slot.get("remaining", 0))
    total = int(slot.get("total", 1)) or 1
    ratio = remaining / total

    if ratio >= 0.5:
        avail_desc = f"号源充足(剩 {remaining}/{total})"
    elif ratio >= 0.2:
        avail_desc = f"号源较充足(剩 {remaining}/{total})"
    else:
        avail_desc = f"号源紧张(剩 {remaining}/{total})"

    slot_date = _parse_date(slot.get("date", ""))
    time_desc = ""
    if slot_date is not None:
        days = (slot_date - today).days
        if days == 0:
            time_desc = "就是今天"
        elif days == 1:
            time_desc = "明天"
        else:
            time_desc = f"距今 {days} 天"

    pref_desc = ""
    mapping = {"today": "今天", "tomorrow": "明天", "this_week": "本周",
               "weekend": "周末", "next_week": "下周"}
    want = mapping.get(prefs.get("time_window", ""))
    if want:
        pref_desc = f",符合您'{want}看'的时间偏好"

    parts = [avail_desc]
    if time_desc:
        parts.append(time_desc)
    reason = ",".join(parts) + pref_desc

    return {
        "date": slot.get("date", ""),
        "period": slot.get("period", ""),
        "reason": reason,
    }


def _parse_date(s: str):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    for fmt in ("%m-%d", "%m/%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            return d.replace(year=date.today().year)
        except ValueError:
            continue
    return None
```

- [ ] **Step 4: 验证测试通过**

Run: `pytest tests/test_doctor_recommender.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add skills/healthpath-doctor-schedule/recommender.py tests/test_doctor_recommender.py
git commit -m "feat(doctor-schedule): 添加就诊时段推荐打分器

纯函数,按号源充足度(40)+时效贴近(30)+时间偏好(20)加权打分,
全满返回 warning,推荐 + 最多 2 个备选。"
```

---

### Task 2: autoclaw 命令封装(mock subprocess)

**Files:**
- Create: `skills/healthpath-doctor-schedule/autoclaw_driver.py`
- Test: `tests/test_doctor_autoclaw_driver.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_doctor_autoclaw_driver.py`:

```python
import os
import sys
import subprocess
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-doctor-schedule"
))

import autoclaw_driver
from autoclaw_driver import (
    run_browser_task, _sanitize_task, _build_command,
    _extract_result_path, _extract_interact_prompt,
    _extract_session_id, _extract_tab_id,
)


def test_sanitize_task_replaces_double_quotes_with_single():
    out = _sanitize_task('打开"协和"官网')
    assert '"' not in out
    assert "'协和'" in out


def test_sanitize_task_rejects_newline():
    import pytest
    with pytest.raises(ValueError):
        _sanitize_task("line1\nline2")


def test_build_command_only_task():
    cmd = _build_command("打开A", None, None, None)
    assert cmd == 'autoclaw task="打开A"'


def test_build_command_with_session_keys():
    cmd = _build_command("继续操作", None, "sid-1", "42")
    assert "session_id=\"sid-1\"" in cmd
    assert "tab_id=\"42\"" in cmd
    assert "start_url" not in cmd


def test_extract_result_path():
    path = _extract_result_path("Result: /tmp/browser_result_abc.md\n")
    assert path == "/tmp/browser_result_abc.md"


def test_extract_interact_prompt():
    md = "...\n[INTERACT_REQUIRED] 请登录协和官网\n\n其他"
    assert "请登录协和官网" in _extract_interact_prompt(md)


def test_extract_session_and_tab():
    md = "session_id=aaaa-bbbb-cccc-dddd-eeee1234 tabId=17"
    assert _extract_session_id(md) == "aaaa-bbbb-cccc-dddd-eeee1234"
    assert _extract_tab_id(md) == "17"


def test_run_browser_task_not_available(monkeypatch):
    monkeypatch.setattr(autoclaw_driver, "_is_available", lambda: False)
    r = run_browser_task("抓数据")
    assert r["status"] == "not_available"


def test_run_browser_task_success_path(tmp_path, monkeypatch):
    # autoclaw 可用
    monkeypatch.setattr(autoclaw_driver, "_is_available", lambda: True)
    # mock subprocess.run 返回 Result: 指针
    result_file = tmp_path / "browser_result_abc.md"
    result_file.write_text(
        "session_id=abc-123-456-789-aaaabbbb\n"
        "tabId=5\n\n"
        "## 操作结果\n王立凡 主任医师 头痛、脑血管病",
        encoding="utf-8",
    )
    mock_proc = MagicMock(
        stdout=f"Result: {result_file}\n", returncode=0,
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_proc)
    r = run_browser_task("打开协和官网找神经内科专家")
    assert r["status"] == "success"
    assert r["session_id"] == "abc-123-456-789-aaaabbbb"
    assert r["tab_id"] == "5"
    assert "王立凡" in r["observation"]


def test_run_browser_task_interact_required(tmp_path, monkeypatch):
    monkeypatch.setattr(autoclaw_driver, "_is_available", lambda: True)
    result_file = tmp_path / "browser_result_xyz.md"
    result_file.write_text(
        "session_id=xyz-xyz-xyz-xyz-xyz000000000\n"
        "tabId=9\n\n"
        "[INTERACT_REQUIRED] 协和官网要求登录,请手动完成登录后告诉我继续\n",
        encoding="utf-8",
    )
    mock_proc = MagicMock(stdout=f"Result: {result_file}\n", returncode=0)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_proc)
    r = run_browser_task("打开协和官网")
    assert r["status"] == "interact_required"
    assert "登录" in r["interact_prompt"]


def test_run_browser_task_timeout(monkeypatch):
    monkeypatch.setattr(autoclaw_driver, "_is_available", lambda: True)
    def _raise(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="autoclaw", timeout=1)
    monkeypatch.setattr(subprocess, "run", _raise)
    r = run_browser_task("长任务", timeout_sec=1)
    assert r["status"] == "timeout"
```

- [ ] **Step 2: 验证失败**

Run: `pytest tests/test_doctor_autoclaw_driver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autoclaw_driver'`

- [ ] **Step 3: 实现 autoclaw_driver.py**

Create `skills/healthpath-doctor-schedule/autoclaw_driver.py`:

```python
"""
autoclaw_driver.py — AutoClaw 浏览器任务调用封装。

遵循 ~/.openclaw-autoclaw/skills/autoglm-browser-agent/SKILL.md 硬规则:
  - task 用户原话,不改写不扩写
  - task 值内部禁止双引号(自动替换为单引号)
  - 命令单行,禁止换行符
  - 结果通过 stdout 的 "Result: <path>" 指针 → Read 文件,不用 process poll
  - 绝不在同一流程里自动重试
  - 一次调用超时上限 5 分钟(autoclaw 原生 2 小时太长)
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_AUTOCLAW_HOME = Path.home() / ".openclaw-autoclaw"
_SESSION_POOL = _AUTOCLAW_HOME / "session_pool.json"


def run_browser_task(
    task: str,
    start_url: Optional[str] = None,
    session_id: Optional[str] = None,
    tab_id: Optional[str] = None,
    timeout_sec: int = 300,
) -> dict:
    """
    Returns dict with keys:
      status: "success" | "interact_required" | "timeout" | "error" | "not_available"
      session_id, tab_id: str | None
      observation: str (md 文本,base64 截图已剥离)
      structured: dict (占位,上层解析)
      interact_prompt: str (仅 interact_required)
      screenshots: list[str] (md 里截图路径)
      error: str | None
    """
    if not _is_available():
        return _pack(status="not_available",
                     error="autoclaw 命令不可用或 ~/.openclaw-autoclaw 不存在")

    safe_task = _sanitize_task(task)
    cmd = _build_command(safe_task, start_url, session_id, tab_id)
    logger.info("[autoclaw_driver] 执行: %s", cmd[:200])

    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True,
            encoding="utf-8", errors="replace",
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return _pack(status="timeout", session_id=session_id, tab_id=tab_id,
                     error=f"autoclaw 超时 ({timeout_sec}s)")
    except FileNotFoundError:
        return _pack(status="not_available", error="autoclaw 不可执行")

    result_path = _extract_result_path(proc.stdout or "") or _fallback_latest_result()
    if not result_path or not os.path.exists(result_path):
        return _pack(status="error", session_id=session_id, tab_id=tab_id,
                     observation=proc.stdout or "",
                     error=f"找不到 autoclaw 结果文件 (rc={proc.returncode})")

    with open(result_path, "r", encoding="utf-8") as f:
        md = f.read()

    out_session = _extract_session_id(md) or session_id
    out_tab = _extract_tab_id(md) or tab_id
    interact = _extract_interact_prompt(md)
    screenshots = _extract_screenshot_paths(md)
    clean = _strip_screenshot_payload(md)

    if interact:
        return _pack(status="interact_required",
                     session_id=out_session, tab_id=out_tab,
                     observation=clean, interact_prompt=interact,
                     screenshots=screenshots)
    return _pack(status="success",
                 session_id=out_session, tab_id=out_tab,
                 observation=clean, screenshots=screenshots)


def _pack(*, status, session_id=None, tab_id=None, observation="",
          interact_prompt="", screenshots=None, error=None):
    return {
        "status": status,
        "session_id": session_id,
        "tab_id": tab_id,
        "observation": observation,
        "structured": {},
        "interact_prompt": interact_prompt,
        "screenshots": screenshots or [],
        "error": error,
    }


def _is_available() -> bool:
    return bool(shutil.which("autoclaw")) and _AUTOCLAW_HOME.exists()


def _sanitize_task(task: str) -> str:
    if not task or not isinstance(task, str):
        raise ValueError("task 必须是非空字符串")
    if "\n" in task or "\r" in task:
        raise ValueError("task 禁止包含换行")
    return (task.replace('"', "'")
                .replace("\u201c", "'")
                .replace("\u201d", "'"))


def _build_command(task: str, start_url: Optional[str],
                   session_id: Optional[str], tab_id: Optional[str]) -> str:
    parts = [f'autoclaw task="{task}"']
    if start_url:
        parts.append(f'start_url="{start_url}"')
    if session_id:
        parts.append(f'session_id="{session_id}"')
    if tab_id:
        parts.append(f'tab_id="{tab_id}"')
    return " ".join(parts)


def _extract_result_path(stdout: str) -> str:
    m = re.search(r"Result:\s*(\S+)", stdout)
    if not m:
        return ""
    path = m.group(1).strip()
    return os.path.expanduser(path) if path.startswith("~") else path


def _fallback_latest_result() -> str:
    if not _SESSION_POOL.exists():
        return ""
    try:
        with open(_SESSION_POOL, "r", encoding="utf-8") as f:
            pool = json.load(f)
    except Exception:
        return ""
    sessions = pool.get("sessions") or {}
    if not sessions:
        return ""
    latest_sid = max(
        sessions.items(),
        key=lambda kv: kv[1].get("updated_at", ""),
    )[0]
    p = _AUTOCLAW_HOME / f"browser_result_{latest_sid}.md"
    return str(p) if p.exists() else ""


def _extract_session_id(md: str) -> Optional[str]:
    m = re.search(r"session_id[=:]\s*([A-Za-z0-9\-]{12,})", md)
    return m.group(1) if m else None


def _extract_tab_id(md: str) -> Optional[str]:
    m = re.search(r"tab[_]?[iI]d[=:]\s*(\d+)", md)
    return m.group(1) if m else None


def _extract_interact_prompt(md: str) -> Optional[str]:
    m = re.search(r"\[INTERACT_REQUIRED\]\s*(.+?)(?:\n\n|\n\[|\Z)",
                  md, re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_screenshot_paths(md: str) -> list:
    return re.findall(r"!\[[^\]]*\]\(([^)]+\.(?:png|jpg|jpeg))\)", md)


def _strip_screenshot_payload(md: str) -> str:
    return re.sub(r"data:image/[^)]+", "<image_base64_stripped>", md)
```

- [ ] **Step 4: 验证测试通过**

Run: `pytest tests/test_doctor_autoclaw_driver.py -v`
Expected: 10 passed

- [ ] **Step 5: 提交**

```bash
git add skills/healthpath-doctor-schedule/autoclaw_driver.py tests/test_doctor_autoclaw_driver.py
git commit -m "feat(doctor-schedule): 添加 autoclaw 浏览器任务调用封装

用 subprocess 调 autoclaw CLI,5 分钟超时,
解析 stdout 的 Result 指针 → Read md 文件 → 抽 session_id/tab_id/INTERACT。
遵循 autoglm-browser-agent SKILL 硬规则:不重试、单行命令、禁双引号。"
```

---

### Task 3: `list_experts` + `schedule_cache.json` 忽略配置

**Files:**
- Modify: `skills/healthpath-doctor-schedule/doctor_schedule.py`(此 task 只实现 `list_experts` 与缓存工具 + 解析器骨架,下一 task 实现 fetch_doctor_schedule)
- Modify: `.gitignore`
- Test: `tests/test_doctor_schedule.py`(本 task 只加 list_experts 相关 case)

- [ ] **Step 1: 在 `.gitignore` 末尾追加 cache 文件**

Edit `.gitignore`:

```
# Appended for doctor-schedule skill
skills/healthpath-doctor-schedule/schedule_cache.json
```

- [ ] **Step 2: 写失败测试**

Create `tests/test_doctor_schedule.py`:

```python
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-doctor-schedule"
))

import doctor_schedule
from doctor_schedule import list_experts


def _fake_driver_result(status="success", observation="", interact=None,
                        session="sid-1", tab="7"):
    return {
        "status": status,
        "session_id": session,
        "tab_id": tab,
        "observation": observation,
        "structured": {},
        "interact_prompt": interact or "",
        "screenshots": [],
        "error": None,
    }


def test_list_experts_happy_parses_from_observation(monkeypatch):
    fake_md = (
        "神经内科出诊专家:\n"
        "王立凡 主任医师 头痛、脑血管病\n"
        "李晓红 副主任医师 癫痫、睡眠障碍\n"
        "赵卫国 主治医师 头晕、头痛\n"
    )
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation=fake_md))
    r = list_experts("北京协和医院", "神经内科",
                     "https://www.pumch.cn/guahao")
    assert r["status"] == "success"
    names = [e["name"] for e in r["experts"]]
    assert "王立凡" in names and "李晓红" in names and "赵卫国" in names
    first = next(e for e in r["experts"] if e["name"] == "王立凡")
    assert first["title"] == "主任医师"
    assert "头痛" in first["specialty"]


def test_list_experts_passes_through_interact(monkeypatch):
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(
                            status="interact_required",
                            interact="协和官网要求登录"))
    r = list_experts("北京协和医院", "神经内科",
                     "https://www.pumch.cn/guahao")
    assert r["status"] == "awaiting_browser_interaction"
    assert r["browser_session"]["session_id"] == "sid-1"
    assert "登录" in r["interact_prompt"]


def test_list_experts_driver_unavailable_returns_error(monkeypatch):
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(
                            status="not_available",
                            session=None, tab=None) | {"error": "autoclaw 不可用"})
    r = list_experts("北京协和医院", "神经内科",
                     "https://www.pumch.cn/guahao")
    assert r["status"] == "error"
    assert "不可用" in r["error"]


def test_list_experts_rejects_empty_url():
    r = list_experts("北京协和医院", "神经内科", "")
    assert r["status"] == "error"
    assert "registration_url" in r["error"]


def test_list_experts_resume_prefixes_task(monkeypatch):
    captured = {}

    def _spy(**kw):
        captured["task"] = kw["task"]
        captured["session_id"] = kw.get("session_id")
        captured["tab_id"] = kw.get("tab_id")
        return _fake_driver_result(observation="王立凡 主任医师 某专长")

    monkeypatch.setattr(doctor_schedule, "run_browser_task", _spy)
    r = list_experts("北京协和医院", "神经内科",
                     "https://www.pumch.cn/guahao",
                     browser_resume={"session_id": "sid-X",
                                     "tab_id": "9",
                                     "user_action": "login_done"})
    assert r["status"] == "success"
    assert captured["session_id"] == "sid-X"
    assert captured["tab_id"] == "9"
    assert captured["task"].startswith("用户已完成登录北京协和医院官网。")
```

- [ ] **Step 3: 验证失败**

Run: `pytest tests/test_doctor_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doctor_schedule'`

- [ ] **Step 4: 实现 doctor_schedule.py 的 list_experts + 公共工具**

Create `skills/healthpath-doctor-schedule/doctor_schedule.py`:

```python
"""
doctor_schedule.py — 医生出诊表与号源查询主模块。

对外三个 dict:
  list_experts(hospital_name, department, registration_url, browser_resume=None)
  fetch_doctor_schedule(hospital_name, doctor_name, registration_url,
                        user_preferences=None, browser_resume=None)

约束:
  - registration_url 必须来自 registration_fetcher,本模块不自查
  - 一次调用内最多触发 1 次 autoclaw
  - 缓存 weekly_pattern 7 天;不缓存 slots
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Optional

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)

from autoclaw_driver import run_browser_task
from recommender import recommend

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(_SKILL_DIR, "schedule_cache.json")
CACHE_TTL_DAYS = 7

TASK_LIST_EXPERTS = (
    "打开{registration_url},进入{department}科室介绍页,"
    "列出该科室所有出诊专家,每位专家给出姓名、职称(主任医师/副主任医师/主治医师)、"
    "擅长领域简介,最多10位。以清单形式输出。"
)

TASK_FETCH_SCHEDULE = (
    "打开{registration_url},搜索医生'{doctor_name}',"
    "进入其个人主页,读取未来14天的出诊排班表,"
    "每个时段标注'剩余号数/总号数'。以结构化列表输出,每行格式:"
    "日期|时段(上午/下午)|剩余/总数。"
)


def list_experts(
    hospital_name: str,
    department: str,
    registration_url: str,
    browser_resume: Optional[dict] = None,
) -> dict:
    if not registration_url:
        return _err("experts", "registration_url 为空,请先调用 registration-fetcher")

    task = TASK_LIST_EXPERTS.format(
        registration_url=registration_url, department=department)

    sid = tid = None
    if browser_resume:
        sid = browser_resume.get("session_id")
        tid = browser_resume.get("tab_id")
        task = _resume_prefix(browser_resume, hospital_name) + task

    driver = run_browser_task(
        task=task,
        start_url=registration_url if not sid else None,
        session_id=sid, tab_id=tid,
    )

    if driver["status"] == "not_available":
        return _err("experts", driver.get("error") or "autoclaw 不可用")
    if driver["status"] == "timeout":
        return _err("experts", driver.get("error") or "autoclaw 超时")
    if driver["status"] == "error":
        return _err("experts", driver.get("error") or "autoclaw 返回错误")

    if driver["status"] == "interact_required":
        return {
            "status": "awaiting_browser_interaction",
            "experts": [],
            "browser_session": {
                "session_id": driver["session_id"],
                "tab_id": driver["tab_id"],
            },
            "interact_prompt": driver.get("interact_prompt", ""),
            "error": None,
        }

    experts = _parse_experts(driver["observation"])
    return {"status": "success", "experts": experts, "error": None}


# ── 解析器(规则式,若 autoclaw 输出变化可迭代) ─────────────────────

_TITLE_RE = r"(主任医师|副主任医师|主治医师|医师)"


def _parse_experts(md: str) -> list:
    """
    从自由文本抽取专家。接受类似:
      "王立凡 主任医师 头痛、脑血管病"
      "王立凡,主任医师,头痛"
      "- 王立凡 主任医师:头痛"
    """
    pattern = re.compile(
        r"([\u4e00-\u9fa5]{2,4})\s*[,、\|:： \t]+"
        rf"{_TITLE_RE}\s*[,、\|:： \t]+"
        r"([^\n]+)"
    )
    experts = []
    seen = set()
    for m in pattern.finditer(md):
        name = m.group(1)
        if name in seen or name in {"主任", "医生", "大夫", "专家"}:
            continue
        seen.add(name)
        experts.append({
            "name": name,
            "title": m.group(2),
            "specialty": m.group(3).strip()[:60],
            "profile_url": "",
        })
        if len(experts) >= 10:
            break
    return experts


# ── 恢复前缀 ─────────────────────────────────────────────────────

def _resume_prefix(browser_resume: dict, hospital_name: str) -> str:
    action = browser_resume.get("user_action", "")
    if action == "login_done":
        return f"用户已完成登录{hospital_name}官网。"
    if action == "captcha_done":
        return "用户已完成验证码。"
    if action == "approve":
        return "用户已同意上述敏感操作,请直接完成该操作。"
    if action == "reject":
        return "用户已拒绝上述操作,请直接跳过该操作。"
    if action:
        return f"用户反馈:{action}。"
    return ""


# ── 统一错误结构 ─────────────────────────────────────────────────

def _err(kind: str, msg: str) -> dict:
    """kind='experts' 返回 experts 结构;kind='schedule' 返回 schedule 结构。"""
    base = {"status": "error", "error": msg}
    if kind == "experts":
        base["experts"] = []
    else:
        base["schedule"] = None
        base["recommendation"] = None
        base["warning"] = None
    return base
```

- [ ] **Step 5: 验证测试通过**

Run: `pytest tests/test_doctor_schedule.py -v`
Expected: 5 passed

- [ ] **Step 6: 提交**

```bash
git add skills/healthpath-doctor-schedule/doctor_schedule.py tests/test_doctor_schedule.py .gitignore
git commit -m "feat(doctor-schedule): 实现 list_experts 与专家解析

新 skill doctor_schedule.py 主文件骨架 + list_experts 接口:
  - 调 autoclaw 抓科室专家列表
  - 正则解析专家姓名/职称/擅长
  - 中断态透传 session_id/tab_id
  - browser_resume 前缀改写遵循 autoglm INTERACT Flow 规则"
```

---

### Task 4: `fetch_doctor_schedule` + 缓存

**Files:**
- Modify: `skills/healthpath-doctor-schedule/doctor_schedule.py`(追加 fetch_doctor_schedule + 缓存 + 更多解析器)
- Test: `tests/test_doctor_schedule.py`(追加 fetch 相关 case)

- [ ] **Step 1: 追加失败测试**

Append to `tests/test_doctor_schedule.py`:

```python
from doctor_schedule import fetch_doctor_schedule, _save_cache, _load_cache, CACHE_PATH
from datetime import date


def _fake_schedule_md():
    return (
        "王立凡 主任医师\n"
        "擅长:头痛、脑血管病\n"
        "出诊:周一上午 专家门诊,周三下午 特需门诊\n"
        "排班:\n"
        "2026-04-22|上午|3/20\n"
        "2026-04-23|下午|0/20\n"
        "2026-04-25|上午|10/20\n"
    )


def test_fetch_schedule_success_parses_all_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation=_fake_schedule_md()))
    r = fetch_doctor_schedule("北京协和医院", "王立凡",
                              "https://www.pumch.cn/guahao",
                              user_preferences={"time_window": "this_week"})
    assert r["status"] == "success"
    assert r["schedule"]["doctor"]["name"] == "王立凡"
    assert r["schedule"]["doctor"]["title"] == "主任医师"
    assert len(r["schedule"]["weekly_pattern"]) >= 1
    assert len(r["schedule"]["slots"]) == 3
    assert r["recommendation"] is not None
    assert r["schedule"]["from_cache"]["slots"] is False


def test_fetch_schedule_doctor_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation="无此医生"))
    r = fetch_doctor_schedule("北京协和医院", "张不存在",
                              "https://www.pumch.cn/guahao")
    assert r["status"] == "doctor_not_found"
    assert r["schedule"] is None
    assert "未找到" in r["error"]


def test_fetch_schedule_all_booked_returns_warning(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    full_md = (
        "王立凡 主任医师\n"
        "2026-04-22|上午|0/20\n"
        "2026-04-23|下午|0/20\n"
    )
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation=full_md))
    r = fetch_doctor_schedule("北京协和医院", "王立凡",
                              "https://www.pumch.cn/guahao")
    assert r["status"] == "schedule_fetched_but_full"
    assert r["recommendation"] is None
    assert r["warning"] and "约满" in r["warning"]


def test_fetch_schedule_cache_hit_when_pattern_missing_in_new_fetch(
    monkeypatch, tmp_path
):
    """抓取失败拿不到 weekly_pattern 时,回退到 cache。"""
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    # 先手动写一条缓存
    _save_cache("北京协和医院", "王立凡",
                {"name": "王立凡", "title": "主任医师", "specialty": "头痛"},
                [{"weekday": "周一上午", "shift": "专家门诊"}])
    # 这次抓取的 md 不含出诊模式,但有号源
    md_no_pattern = "王立凡 主任医师\n2026-04-22|上午|5/20\n"
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(observation=md_no_pattern))
    r = fetch_doctor_schedule("北京协和医院", "王立凡",
                              "https://www.pumch.cn/guahao")
    assert r["status"] == "success"
    assert r["schedule"]["from_cache"]["weekly_pattern"] is True
    assert len(r["schedule"]["weekly_pattern"]) == 1


def test_fetch_schedule_interact_required(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(doctor_schedule, "run_browser_task",
                        lambda **kw: _fake_driver_result(
                            status="interact_required",
                            interact="请完成短信验证码"))
    r = fetch_doctor_schedule("北京协和医院", "王立凡",
                              "https://www.pumch.cn/guahao")
    assert r["status"] == "awaiting_browser_interaction"
    assert r["browser_session"]["session_id"] == "sid-1"


def test_fetch_schedule_rejects_empty_params():
    r1 = fetch_doctor_schedule("", "王立凡", "https://x")
    assert r1["status"] == "error"
    r2 = fetch_doctor_schedule("协和", "", "https://x")
    assert r2["status"] == "error"
    r3 = fetch_doctor_schedule("协和", "王立凡", "")
    assert r3["status"] == "error"


def test_cache_expires_after_7_days(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    _save_cache("X医院", "某医生",
                {"name": "某", "title": "主任医师", "specialty": ""},
                [{"weekday": "周一上午", "shift": "专家门诊"}])
    # 手动把时间戳改为 8 天前
    import json
    with open(tmp_path / "cache.json", encoding="utf-8") as f:
        c = json.load(f)
    c["X医院::某医生"]["weekly_pattern_cached_at"] = (
        datetime.now() - timedelta(days=8)
    ).isoformat()
    with open(tmp_path / "cache.json", "w", encoding="utf-8") as f:
        json.dump(c, f)
    assert _load_cache("X医院", "某医生") is None
```

Also add this import at top of test file if missing:

```python
from datetime import datetime, timedelta
```

- [ ] **Step 2: 验证失败**

Run: `pytest tests/test_doctor_schedule.py -v`
Expected: 7 new tests FAIL — `ImportError: cannot import name 'fetch_doctor_schedule'`

- [ ] **Step 3: 扩展 doctor_schedule.py**

Append to `skills/healthpath-doctor-schedule/doctor_schedule.py`(在 `list_experts` 之后、`_parse_experts` 之前):

```python
def fetch_doctor_schedule(
    hospital_name: str,
    doctor_name: str,
    registration_url: str,
    user_preferences: Optional[dict] = None,
    browser_resume: Optional[dict] = None,
) -> dict:
    if not hospital_name:
        return _err("schedule", "hospital_name 为空")
    if not doctor_name:
        return _err("schedule", "doctor_name 为空")
    if not registration_url:
        return _err("schedule", "registration_url 为空,请先调用 registration-fetcher")

    cached = _load_cache(hospital_name, doctor_name)

    task = TASK_FETCH_SCHEDULE.format(
        registration_url=registration_url, doctor_name=doctor_name)

    sid = tid = None
    if browser_resume:
        sid = browser_resume.get("session_id")
        tid = browser_resume.get("tab_id")
        task = _resume_prefix(browser_resume, hospital_name) + task

    driver = run_browser_task(
        task=task,
        start_url=registration_url if not sid else None,
        session_id=sid, tab_id=tid,
    )

    if driver["status"] in ("not_available", "timeout", "error"):
        return _err("schedule", driver.get("error") or "autoclaw 不可用")

    if driver["status"] == "interact_required":
        return {
            "status": "awaiting_browser_interaction",
            "schedule": None,
            "recommendation": None,
            "warning": None,
            "error": None,
            "browser_session": {
                "session_id": driver["session_id"],
                "tab_id": driver["tab_id"],
            },
            "interact_prompt": driver.get("interact_prompt", ""),
        }

    obs = driver["observation"]
    doctor_meta = _parse_doctor_meta(obs, doctor_name)
    if doctor_meta is None:
        return {
            "status": "doctor_not_found",
            "schedule": None,
            "recommendation": None,
            "warning": None,
            "error": f"在当前页面未找到医生'{doctor_name}',请确认姓名是否正确或改走专家列表分支",
        }

    weekly_pattern = _parse_weekly_pattern(obs)
    slots = _parse_slots(obs)

    from_cache_pattern = False
    if not weekly_pattern and cached:
        weekly_pattern = cached.get("weekly_pattern", [])
        from_cache_pattern = True
    elif weekly_pattern:
        _save_cache(hospital_name, doctor_name, doctor_meta, weekly_pattern)

    rec = recommend(slots, user_preferences=user_preferences)

    schedule = {
        "doctor": doctor_meta,
        "weekly_pattern": weekly_pattern,
        "slots": slots,
        "data_timestamp": datetime.now().isoformat(),
        "from_cache": {"weekly_pattern": from_cache_pattern, "slots": False},
    }

    if rec["recommendation"] is None:
        return {
            "status": "schedule_fetched_but_full",
            "schedule": schedule,
            "recommendation": None,
            "warning": rec["warning"],
            "error": None,
        }

    return {
        "status": "success",
        "schedule": schedule,
        "recommendation": rec["recommendation"],
        "alternatives": rec["alternatives"],
        "warning": None,
        "error": None,
    }


# ── 解析器(续) ───────────────────────────────────────────────────

def _parse_doctor_meta(md: str, doctor_name: str) -> Optional[dict]:
    if doctor_name not in md:
        return None
    title_m = re.search(
        rf"{re.escape(doctor_name)}\s*[,、\|:： \t]*{_TITLE_RE}", md)
    title = title_m.group(1) if title_m else "医师"
    spec_m = re.search(
        rf"{re.escape(doctor_name)}[\s\S]{{0,80}}?(?:擅长|专长)[::]\s*([^\n]+)",
        md)
    specialty = spec_m.group(1).strip()[:80] if spec_m else ""
    return {"name": doctor_name, "title": title, "specialty": specialty}


def _parse_weekly_pattern(md: str) -> list:
    pattern = []
    wk = re.compile(
        r"(周[一二三四五六日])\s*(上午|下午)\s*[:： ]?\s*([^\n,。;;]{0,20})"
    )
    for m in wk.finditer(md):
        pattern.append({
            "weekday": f"{m.group(1)}{m.group(2)}",
            "shift": m.group(3).strip() or "门诊",
        })
    return pattern


def _parse_slots(md: str) -> list:
    slots = []
    slot_re = re.compile(
        r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[-/]\d{1,2})"
        r"\s*[\|\s,]+\s*(上午|下午|全天)"
        r"\s*[\|\s,]+\s*(\d+)\s*[/／]\s*(\d+)"
    )
    for m in slot_re.finditer(md):
        d = m.group(1)
        if "-" in d and len(d.split("-")) == 2:
            d = f"{datetime.now().year}-{d}"
        elif "/" in d and len(d.split("/")) == 2:
            parts = d.split("/")
            d = f"{datetime.now().year}-{parts[0]}-{parts[1]}"
        slots.append({
            "date": d,
            "period": m.group(2),
            "remaining": int(m.group(3)),
            "total": int(m.group(4)),
        })
    return slots


# ── 缓存 ─────────────────────────────────────────────────────────

def _load_cache(hospital_name: str, doctor_name: str) -> Optional[dict]:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        return None
    entry = cache.get(f"{hospital_name}::{doctor_name}")
    if not entry:
        return None
    try:
        cached_at = datetime.fromisoformat(entry.get("weekly_pattern_cached_at", ""))
    except Exception:
        return None
    if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
        return None
    return entry


def _save_cache(hospital_name: str, doctor_name: str,
                doctor_meta: dict, weekly_pattern: list) -> None:
    cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    cache[f"{hospital_name}::{doctor_name}"] = {
        "doctor_meta": doctor_meta,
        "weekly_pattern": weekly_pattern,
        "weekly_pattern_cached_at": datetime.now().isoformat(),
        "weekly_pattern_ttl_days": CACHE_TTL_DAYS,
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 验证测试通过**

Run: `pytest tests/test_doctor_schedule.py -v`
Expected: 12 passed(原 5 + 新 7)

- [ ] **Step 5: 提交**

```bash
git add skills/healthpath-doctor-schedule/doctor_schedule.py tests/test_doctor_schedule.py
git commit -m "feat(doctor-schedule): 实现 fetch_doctor_schedule 与分层缓存

  - 调 autoclaw 抓医生主页,解析职称/擅长/周排班/号源表
  - weekly_pattern 7 天 JSON 缓存,slots 始终实时
  - 中断态透传,doctor_not_found/全满态独立返回
  - 沿用 recommender 模块计算推荐"
```

---

### Task 5: 新 skill 的 SKILL.md 和 _meta.json

**Files:**
- Create: `skills/healthpath-doctor-schedule/SKILL.md`
- Create: `skills/healthpath-doctor-schedule/_meta.json`

- [ ] **Step 1: 写 _meta.json**

Create `skills/healthpath-doctor-schedule/_meta.json`:

```json
{
  "ownerId": "healthpath-agent",
  "slug": "healthpath-doctor-schedule",
  "version": "1.0.0",
  "publishedAt": 1777000000000
}
```

- [ ] **Step 2: 写 SKILL.md**

Create `skills/healthpath-doctor-schedule/SKILL.md`:

````markdown
---
name: healthpath-doctor-schedule
description: 通过 AutoClaw 浏览器控制能力,抓取医生出诊表与实时号源,按评分推荐就诊时间。依赖 registration-fetcher 提供的挂号入口 URL。
metadata:
  openclaw:
    emoji: "🩺"
    requires:
      bins: ["python3", "autoclaw"]
      python:
        runtime: ">=3.9"
        packages: []
---

# doctor_schedule — 医生出诊表 / 号源查询 & 推荐

## 职责划分

| 执行者 | 职责 |
|---|---|
| **本脚本** | 调 autoclaw → 解析结果 → 维护 7 天出诊表缓存 → 跑推荐算法 |
| **Agent** | 转述中间态(专家列表选择、登录/验证码)给用户,收集答复后再次调用 |

## 对外接口

### `list_experts(hospital_name, department, registration_url, browser_resume=None) -> dict`

当用户未指名医生时调用,抓取该科室专家列表供用户挑选。

返回字段:
- `status`: `"success"` | `"awaiting_browser_interaction"` | `"error"`
- `experts`: `[{"name", "title", "specialty", "profile_url"}, ...]`(最多 10 位)
- `browser_session`, `interact_prompt`(仅 awaiting 态)
- `error`

### `fetch_doctor_schedule(hospital_name, doctor_name, registration_url, user_preferences=None, browser_resume=None) -> dict`

抓某医生未来 14 天出诊表 + 号源,并按评分给出推荐。

返回字段:
- `status`: `"success"` | `"awaiting_browser_interaction"` | `"doctor_not_found"` | `"schedule_fetched_but_full"` | `"error"`
- `schedule`: `{doctor, weekly_pattern, slots, data_timestamp, from_cache}`
- `recommendation`: `{date, period, reason}`
- `alternatives`: 最多 2 个备选
- `warning`: 全满时的提示文案
- `browser_session`, `interact_prompt`(仅 awaiting 态)
- `error`

### `browser_resume` 字段规范

```python
{
    "session_id": str,              # 上轮返回的
    "tab_id": str,                   # 上轮返回的
    "user_action": "login_done"      # 枚举或自由文本
                 | "captcha_done"
                 | "approve"
                 | "reject"
                 | "<自由文本>",
}
```

## 缓存

- 文件:`skills/healthpath-doctor-schedule/schedule_cache.json`(已入 .gitignore)
- 键:`"{hospital_name}::{doctor_name}"`
- 只缓存 `doctor_meta` + `weekly_pattern`,TTL 7 天
- **号源 `slots` 不缓存**,每次实时抓

## 推荐算法

按号源充足度(40)+ 时效贴近(30)+ 时间偏好(20)+ 避开满诊(10 过滤位)加权。
见 `recommender.py` 源码,纯函数易测。

## 硬约束(违反即为任务失败)

1. `registration_url` **只能**从 `registration_fetcher.fetch()` 的结果来,本 skill 不做网络搜索,不猜域名
2. 一次对话内最多触发 1 次 autoclaw(autoglm-browser-agent 原则)
3. `task` 参数不改写用户原话,模板填充后禁双引号、禁换行
4. 不缓存 `slots`,每次实时
5. `session_id`/`tab_id` 只透传,不写入本地缓存

## Python 调用示例(Windows 注意编码)

```powershell
cd D:\xuexi\competition\计算机设计大赛\project; $env:PYTHONIOENCODING='utf-8'; python -c "
import sys, json
sys.path.insert(0, 'skills/healthpath-doctor-schedule')
from doctor_schedule import fetch_doctor_schedule
r = fetch_doctor_schedule('北京协和医院', '王立凡', 'https://www.pumch.cn/guahao')
print(json.dumps(r, ensure_ascii=False, indent=2))
"
```

## 常见问题

### Q: autoclaw 不可用怎么办?
A: 脚本自动降级:返回 `status='error'`,上层 `main_skill` 会跳过本步骤,仍生成 PDF,只是 PDF 里没有具体推荐时段,只有官网 URL。

### Q: 医生姓名没抓到?
A: 返回 `status='doctor_not_found'`。agent 应提示用户确认姓名,或改走 `list_experts` 流程。

### Q: 号源已全满?
A: 返回 `status='schedule_fetched_but_full'` + `warning` 文案。agent 应向用户展示 warning,并建议改挂同科室其他专家或关注下周放号。
````

- [ ] **Step 3: 验证文件格式**

Run:
```bash
python -c "import json; json.load(open('skills/healthpath-doctor-schedule/_meta.json'))"
```
Expected: 无输出(JSON 合法)

- [ ] **Step 4: 提交**

```bash
git add skills/healthpath-doctor-schedule/SKILL.md skills/healthpath-doctor-schedule/_meta.json
git commit -m "docs(doctor-schedule): 新 skill 的 SKILL.md 与元数据

说明 list_experts/fetch_doctor_schedule 接口、缓存/推荐策略、
浏览器调用硬约束、Windows 编码注意事项。"
```

---

### Task 6: intent_parser 扩展 `doctor_name` 抽取

**Files:**
- Modify: `skills/healthpath-intent-understanding/intent_parser.py`
- Test: `tests/test_intent_parser_doctor_name.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_intent_parser_doctor_name.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-intent-understanding"
))

from intent_parser import extract_doctor_name, parse_intent


def test_extract_explicit_doctor_with_keyword():
    assert extract_doctor_name("我要挂协和医院王立凡医生的号") == "王立凡"
    assert extract_doctor_name("挂张铁柱主任的号") == "张铁柱"
    assert extract_doctor_name("找李小红大夫看看") == "李小红"


def test_extract_returns_empty_when_no_doctor():
    assert extract_doctor_name("最近头疼,想看神经内科") == ""
    assert extract_doctor_name("帮我找北京协和医院的号") == ""


def test_extract_skips_stopwords():
    # "医生" 本身不是名字
    assert extract_doctor_name("我要找个医生看看") == ""
    # "专家" 也不应该当人名
    assert extract_doctor_name("找个专家看看") == ""


def test_extract_skips_hospital_and_dept_names():
    # 协和/神经内科 不应被当成人名(含"医院""科")
    assert extract_doctor_name("协和医院神经内科的号") == ""


def test_parse_intent_returns_doctor_name_field():
    r = parse_intent("我要挂协和医院王立凡医生的号", use_deepseek=False)
    assert r["doctor_name"] == "王立凡"


def test_parse_intent_doctor_empty_when_unspecified():
    r = parse_intent("最近头疼想看神经内科", use_deepseek=False)
    assert r["doctor_name"] == ""
```

- [ ] **Step 2: 验证失败**

Run: `pytest tests/test_intent_parser_doctor_name.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_doctor_name'`

- [ ] **Step 3: 在 intent_parser.py 里加 `extract_doctor_name` 并接入 parse_intent**

Edit `skills/healthpath-intent-understanding/intent_parser.py`:

**3a. 在文件末尾(`if __name__ == "__main__":` 之前)追加 `extract_doctor_name`**:

```python
# ── 医生姓名抽取(规则式) ─────────────────────────────────────────

_DOCTOR_STOPWORDS = {
    "我", "您", "他", "她", "医生", "大夫", "专家", "某某", "主任",
    "主任医师", "副主任医师", "主治医师", "医师",
}


def extract_doctor_name(text: str) -> str:
    """
    从用户文本抽取医生姓名(规则式)。

    支持:
        "挂 X 医生的号" / "X 主任" / "找 X 大夫"
    只接受 2-4 字汉字,排除含'医院/科'的词。
    """
    patterns = [
        r"挂\s*([\u4e00-\u9fa5]{2,4})\s*(?:医生|大夫|主任|副主任|的号)",
        r"找\s*([\u4e00-\u9fa5]{2,4})\s*(?:医生|大夫|主任|副主任)",
        r"([\u4e00-\u9fa5]{2,4})\s*(?:医生|大夫|主任医师|副主任医师)的号",
    ]
    for p in patterns:
        m = re.search(p, text)
        if not m:
            continue
        name = m.group(1)
        if name in _DOCTOR_STOPWORDS:
            continue
        if "医院" in name or "科" in name:
            continue
        return name
    return ""
```

**3b. 在 `parse_intent` 函数里,把 `doctor_name` 写入返回 dict**:

找到 `parse_intent(...)` 函数中本地解析分支(`_extract_symptom_and_dept` 调用之后、`task = {...}` 字面量),在 `task` 的字典里新增 `"doctor_name"` 字段:

```python
    task = {
        "symptom":              symptom,
        "department":           department,
        "doctor_name":          extract_doctor_name(user_input),   # ← 新增行
        "target_city":          "北京",
        "time_window":          extract_time_window(user_input),
        ...
```

同时在 `if use_deepseek:` 分支里,DeepSeek 返回的 task 里也补上:

```python
    if use_deepseek:
        client = DeepSeekClient()
        task = client.extract_intent(user_input)
        if task:
            task.setdefault("timestamp", datetime.now().isoformat())
            task.setdefault("doctor_name", extract_doctor_name(user_input))   # ← 新增
            return task
```

- [ ] **Step 4: 验证测试通过**

Run: `pytest tests/test_intent_parser_doctor_name.py -v`
Expected: 6 passed

回归原有 intent_parser 测试(如果有的话):

Run: `pytest tests/ -k "intent" -v`
Expected: 全部原测试仍通过

- [ ] **Step 5: 提交**

```bash
git add skills/healthpath-intent-understanding/intent_parser.py tests/test_intent_parser_doctor_name.py
git commit -m "feat(intent): 新增 doctor_name 字段与规则式抽取

支持'挂 X 医生/主任/大夫的号'等常见口语;
排除停用词和包含医院/科的词,避免误抽。
DeepSeek 与本地规则两个分支都会填充 doctor_name。"
```

---

### Task 7: `main_skill.execute()` 签名扩展 + 状态机分支

**Files:**
- Modify: `main_skill.py`
- Test: (延至 Task 10 的集成测试统一测)

- [ ] **Step 1: 读现有 main_skill.py 的 execute()**

Run: `head -170 main_skill.py`(或 `Read` 工具)
确认当前 `execute` 在拿到 `reg_result` 后直接进 `itinerary_builder.build(...)`,这里正是新 step 5 `doctor-schedule` 要插入的位置。

- [ ] **Step 2: 修改 `sys.path` 注入,加入新 skill 目录**

Edit `main_skill.py:22-32`:

```python
_ROOT = os.path.dirname(os.path.abspath(__file__))
for skill_dir in [
    "healthpath-intent-understanding",
    "healthpath-symptom-triage",
    "healthpath-hospital-matcher",
    "healthpath-registration-fetcher",
    "healthpath-doctor-schedule",          # ← 新增
    "healthpath-itinerary-builder",
]:
    sys.path.insert(0, os.path.join(_ROOT, "skills", skill_dir))

from intent_parser import parse_intent
from symptom_triage import triage
from hospital_matcher import match
from registration_fetcher import fetch
import doctor_schedule as doctor_schedule_mod   # ← 新增
from itinerary_builder import build
```

- [ ] **Step 3: 修改 `execute()` 签名,加 3 个参数**

Edit `main_skill.py` 的 `HealthPathAgent.execute` 签名与文档:

```python
    def execute(
        self,
        user_input: str,
        user_location: Optional[str] = None,
        selected_hospital: Optional[str] = None,
        selected_doctor: Optional[str] = None,          # 新
        browser_resume: Optional[dict] = None,          # 新
        confirmed_appointment: Optional[dict] = None,   # 新
        extra_answers: Optional[dict] = None,
        output_format: str = "large_font_pdf",
        user_profile: Optional[dict] = None,
    ) -> Dict[str, Any]:
```

- [ ] **Step 4: 在 reg_result 之后、itinerary.build 之前,插入 doctor-schedule 分支**

找到 `main_skill.py` 约 140-160 行,当前代码是:
```python
            reg_result = fetch(...)
            result["steps"]["registration"] = reg_result

            # Step 5: 行程单生成   ← 原来
            itinerary_result = build(...)
```

替换为(整段):

```python
            reg_result = fetch(
                hospital_name=selected_hospital,
                department=departments[0],
                user_location=user_location,
                yixue_url=hospital_info.get("yixue_url", ""),
            )
            result["steps"]["registration"] = reg_result

            # Step 5: 医生出诊表 + 号源 + 推荐
            doctor_name = (
                selected_doctor
                or (intent_result or {}).get("doctor_name", "")
            )
            registration_url = (
                reg_result.get("registration_url")
                or reg_result.get("official_url")
                or ""
            )
            user_prefs_for_rec = {
                "time_window": (intent_result or {}).get("time_window", ""),
                "preferred_period": "",
            }

            doctor_step_result = None

            if registration_url:
                if doctor_name:
                    doctor_step_result = doctor_schedule_mod.fetch_doctor_schedule(
                        hospital_name=selected_hospital,
                        doctor_name=doctor_name,
                        registration_url=registration_url,
                        user_preferences=user_prefs_for_rec,
                        browser_resume=browser_resume,
                    )
                else:
                    doctor_step_result = doctor_schedule_mod.list_experts(
                        hospital_name=selected_hospital,
                        department=departments[0],
                        registration_url=registration_url,
                        browser_resume=browser_resume,
                    )

            if doctor_step_result is not None:
                result["steps"]["doctor_schedule"] = doctor_step_result
                status = doctor_step_result.get("status")

                # 中断态:透传给上层
                if status == "awaiting_browser_interaction":
                    result["status"] = "awaiting_browser_interaction"
                    result["final_output"] = {
                        "browser_session": doctor_step_result.get("browser_session"),
                        "interact_prompt": doctor_step_result.get("interact_prompt", ""),
                    }
                    result["follow_up"] = [{
                        "id": "browser_interaction",
                        "question": doctor_step_result.get("interact_prompt", "")
                                    or "浏览器窗口里有一个待操作项,请完成后告诉我继续",
                    }]
                    return result

                # 没指名医生:返回专家列表
                if status == "success" and "experts" in doctor_step_result:
                    result["status"] = "awaiting_doctor_selection"
                    result["final_output"] = {
                        "experts": doctor_step_result["experts"],
                        "message": "以下是该科室出诊专家,请告诉我选择哪一位:",
                    }
                    return result

                # 全满:给 warning,但继续生成 PDF(只写官网让用户自己再看)
                if status == "schedule_fetched_but_full":
                    result["status"] = "schedule_fetched_but_full"
                    result["warning"] = doctor_step_result.get("warning", "")

                # 找不到该医生:返回提示,由 agent 请用户澄清
                if status == "doctor_not_found":
                    result["status"] = "doctor_not_found"
                    result["follow_up"] = [{
                        "id": "doctor_name_clarify",
                        "question": doctor_step_result.get("error", "未找到该医生,请确认姓名"),
                    }]
                    return result

                # success 且包含 schedule/recommendation 且用户尚未确认:
                if (status == "success"
                        and doctor_step_result.get("schedule") is not None
                        and not confirmed_appointment):
                    result["status"] = "doctor_schedule_fetched"
                    result["final_output"] = {
                        "schedule": doctor_step_result.get("schedule"),
                        "recommendation": doctor_step_result.get("recommendation"),
                        "alternatives": doctor_step_result.get("alternatives", []),
                        "message": "已获取医生出诊表与号源,请确认推荐的就诊时间或选择备选",
                    }
                    return result

            # Step 6: 行程单生成(若到这里,说明 doctor_schedule 已失败/跳过/或用户已确认推荐)
            appointment_time = None
            if confirmed_appointment:
                date_s = confirmed_appointment.get("date", "")
                slot_s = confirmed_appointment.get("time_slot", "")
                if date_s and slot_s:
                    time_map = {"上午": "09:00", "下午": "14:00"}
                    hhmm = time_map.get(slot_s, slot_s)
                    appointment_time = f"{date_s} {hhmm}"

            doctor_ctx = None
            if doctor_step_result and doctor_step_result.get("status") in (
                "success", "schedule_fetched_but_full"
            ):
                doctor_ctx = {
                    "doctor": (doctor_step_result.get("schedule") or {}).get("doctor"),
                    "recommendation": doctor_step_result.get("recommendation"),
                    "warning": doctor_step_result.get("warning"),
                }

            itinerary_result = build(
                user_location=user_location,
                hospital_name=selected_hospital,
                hospital_address=hospital_info.get("address", ""),
                department=departments[0],
                registration_info=reg_result,
                appointment_time=appointment_time,
                output_format=output_format,
                user_profile=user_profile,
                doctor_schedule=doctor_ctx,   # ← 新参数,由 Task 8 加到 build 签名
            )
            result["steps"]["itinerary"] = itinerary_result
            result["final_output"] = {
                "pdf_path": itinerary_result.get("pdf_path", ""),
                "depart_time": itinerary_result.get("depart_time", ""),
                "route": itinerary_result.get("route_summary", {}),
                "registration_url": reg_result.get("registration_url", ""),
                "doctor": (doctor_ctx or {}).get("doctor"),
                "recommendation": (doctor_ctx or {}).get("recommendation"),
            }
            return result
```

- [ ] **Step 5: 同步更新 `get_info()` 的 skills 列表**

Edit `main_skill.py` 里 `HealthPathAgent.get_info()` 的返回:

```python
            "skills": [
                "healthpath-intent-understanding",
                "healthpath-symptom-triage",
                "healthpath-hospital-matcher",
                "healthpath-registration-fetcher",
                "healthpath-doctor-schedule",   # ← 新增
                "healthpath-itinerary-builder",
                "baidu-ai-map(底层地图能力)",
            ],
```

- [ ] **Step 6: 快速烟雾测试 execute() 旧路径仍不崩**

Run: `python -c "
import sys, os
os.environ['PYTHONIOENCODING']='utf-8'
sys.stdout.reconfigure(encoding='utf-8')
from main_skill import execute, get_info
print(get_info()['skills'])
r = execute(user_input='最近头晕,想看医生')
print(r['status'])
"`

Expected: 打印的 skills 列表包含 `healthpath-doctor-schedule`;`r['status']` 是 `need_location`/`need_more_info`/`emergency_warning` 之一(不是 `error`)。

- [ ] **Step 7: 提交**

```bash
git add main_skill.py
git commit -m "feat(main_skill): 集成 doctor-schedule 为 step 5,扩展 execute() 状态机

新增参数:selected_doctor, browser_resume, confirmed_appointment
新增 status 分支:awaiting_doctor_selection / awaiting_browser_interaction /
doctor_schedule_fetched / doctor_not_found / schedule_fetched_but_full

流程变化:
  用户未指名医生 → list_experts → 返回专家列表等选
  用户已指名医生 → fetch_doctor_schedule → 返回推荐等确认
  已 confirmed_appointment → 继续 Step 6 生成 PDF(携带医生与推荐上下文)

对旧调用方(无新参数)完全向后兼容;autoclaw 不可用时流程不中断,仍生成 PDF。"
```

---

### Task 8: itinerary_builder 接收 doctor_schedule 并写入 PDF

**Files:**
- Modify: `skills/healthpath-itinerary-builder/itinerary_builder.py`
- Test: 下一 task 集成测试覆盖

- [ ] **Step 1: 扩展 `build()` 签名与文档注释**

Edit `skills/healthpath-itinerary-builder/itinerary_builder.py:78-85`:

```python
def build(user_location: str,
          hospital_name: str,
          hospital_address: str,
          department: str,
          registration_info: dict,
          appointment_time: Optional[str] = None,
          output_format: str = "large_font_pdf",
          user_profile: Optional[dict] = None,
          doctor_schedule: Optional[dict] = None) -> dict:    # ← 新增
```

同步更新模块 docstring(约第 12-30 行),在参数列表中加入:

```
  doctor_schedule  dict  {"doctor": {...}, "recommendation": {...}, "warning": str} | None
```

- [ ] **Step 2: 在 `_build_nav_steps` 之后、`_generate_pdf` 之前,把 doctor 信息注入 `nav_steps` 首部**

找到 `itinerary_builder.py` 中 `build()` 函数里构造 `nav_steps` 的位置(约第 109 行):

```python
    # 4. 院内导引 ─────────────────────────────────────────────────────
    nav_steps = _build_nav_steps(hospital_name, department, registration_info)

    # 4.5 医生 & 推荐注入(新)
    if doctor_schedule:
        doctor = doctor_schedule.get("doctor") or {}
        rec = doctor_schedule.get("recommendation")
        warning = doctor_schedule.get("warning")
        if doctor.get("name"):
            doctor_line = f"【医生】{doctor['name']}"
            if doctor.get("title"):
                doctor_line += f" ({doctor['title']})"
            if doctor.get("specialty"):
                doctor_line += f",擅长:{doctor['specialty']}"
            nav_steps.insert(0, doctor_line)
        if rec:
            rec_line = f"【建议就诊】{rec.get('date', '')} {rec.get('period', '')}"
            if rec.get("reason"):
                rec_line += f" — {rec['reason']}"
            nav_steps.insert(1 if doctor.get("name") else 0, rec_line)
        if warning:
            nav_steps.insert(0, f"【提示】{warning}")
```

- [ ] **Step 3: 把 doctor & recommendation 追加到 `task_params`,方便 pdf_generator 未来渲染专段(向后兼容)**

找到 `_generate_pdf` 函数里构造 `task_params` 的字典(约 609-631 行),在末尾(紧贴 `}` 之前)追加:

```python
        # 医生与推荐(新,pdf_generator 可选读取)
        "doctor_name":              (doctor_schedule or {}).get("doctor", {}).get("name", "") if doctor_schedule else "",
        "doctor_title":             (doctor_schedule or {}).get("doctor", {}).get("title", "") if doctor_schedule else "",
        "doctor_specialty":         (doctor_schedule or {}).get("doctor", {}).get("specialty", "") if doctor_schedule else "",
        "recommended_date":         (doctor_schedule or {}).get("recommendation", {}).get("date", "") if doctor_schedule and doctor_schedule.get("recommendation") else "",
        "recommended_period":       (doctor_schedule or {}).get("recommendation", {}).get("period", "") if doctor_schedule and doctor_schedule.get("recommendation") else "",
        "recommendation_reason":    (doctor_schedule or {}).get("recommendation", {}).get("reason", "") if doctor_schedule and doctor_schedule.get("recommendation") else "",
```

(说明:`_generate_pdf` 本身不需要改签名,因为它原本就接 `registration_info`;这里从新参数 `doctor_schedule` 取数据需要把参数传进来。)

**同步修改 `_generate_pdf` 签名与 `build()` 里的调用**:

把 `_generate_pdf` 的签名(约 582-585 行)改为:
```python
def _generate_pdf(hospital_name, hospital_address, department,
                  registration_info, appointment_time, route,
                  depart_time, checklist, nav_steps,
                  age_group, output_format, timestamp,
                  doctor_schedule=None):   # ← 新增
```

把 `build()` 里调用 `_generate_pdf` 的地方(约 113-126 行)加上 `doctor_schedule=doctor_schedule`:

```python
    pdf_path = _generate_pdf(
        hospital_name=hospital_name,
        hospital_address=hospital_address,
        department=department,
        registration_info=registration_info,
        appointment_time=appointment_time,
        route=route,
        depart_time=depart_time,
        checklist=checklist,
        nav_steps=nav_steps,
        age_group=age_group,
        output_format=output_format,
        timestamp=timestamp,
        doctor_schedule=doctor_schedule,   # ← 新增
    )
```

- [ ] **Step 4: 手动烟雾测试,生成一份 PDF**

Run:
```powershell
cd "D:\xuexi\competition\计算机设计大赛\project"; $env:PYTHONIOENCODING='utf-8'; python -c "
import sys
sys.path.insert(0, 'skills/healthpath-itinerary-builder')
from itinerary_builder import build
r = build(
    user_location='北京市朝阳区望京街道',
    hospital_name='北京协和医院',
    hospital_address='北京市东城区帅府园1号',
    department='神经内科',
    registration_info={'registration_url': 'https://www.pumch.cn/', 'registration_platform': '医院官网'},
    appointment_time='2026-04-22 09:00',
    output_format='pdf',
    user_profile={'age_group': 'adult'},
    doctor_schedule={
        'doctor': {'name': '王立凡', 'title': '主任医师', 'specialty': '头痛、脑血管病'},
        'recommendation': {'date': '2026-04-22', 'period': '上午', 'reason': '号源较充足(剩 3/20),距今 2 天'},
        'warning': None,
    },
)
print('PDF:', r['pdf_path'])
print('Nav steps (前 3 条):')
for s in r['nav_steps'][:3]:
    print(' ', s)
"
```

Expected:
- 输出 PDF 路径
- 前三行 `nav_steps` 里包含 `【医生】王立凡 (主任医师)...` 和 `【建议就诊】2026-04-22 上午 — ...`

- [ ] **Step 5: 提交**

```bash
git add skills/healthpath-itinerary-builder/itinerary_builder.py
git commit -m "feat(itinerary): 将医生与推荐就诊时段注入行程单

build() 新增 doctor_schedule 参数(可选):
  - 医生与推荐以 '[医生]'/'[建议就诊]' 段落插入 nav_steps 首部
  - doctor_name/doctor_title/recommended_date 等字段加入 task_params,
    pdf_generator 后续可选用于独立渲染章节
  - 向后兼容:不传该参数行为同旧版"
```

---

### Task 9: SKILL_PREFERENCES 与 autoclaw_integration 注册

**Files:**
- Modify: `SKILL_PREFERENCES.md`
- Modify: `config/autoclaw_integration.py`

- [ ] **Step 1: 更新 SKILL_PREFERENCES.md 流程图与新 skill 说明**

Edit `SKILL_PREFERENCES.md`:

**1a. 更新第一节的流程图(约 22-39 行),把 5 步改 6 步:**

```
用户自然语言输入
      │
      ▼
[1] healthpath-intent-understanding   ← 解析意图,提取结构化参数(含 doctor_name)
      │
      ▼
[2] healthpath-symptom-triage         ← 根据症状推荐科室(用户已明确科室时可跳过)
      │
      ▼
[3] healthpath-hospital-matcher       ← 匹配附近医院候选列表
      │
      ▼
[4] healthpath-registration-fetcher   ← 获取用户选定医院的官网 URL
      │
      ▼
[5] healthpath-doctor-schedule        ← 抓医生出诊表+号源,按评分推荐就诊时段
      │
      ▼
[6] healthpath-itinerary-builder      ← 生成完整就医行程单(PDF,含医生与推荐)
```

**1b. 在"[4] healthpath-registration-fetcher"小节之后、"[5] healthpath-itinerary-builder" 之前(原来的 [5] 变成新的 [6]),插入新 skill 的说明章节:**

```markdown
### [5] healthpath-doctor-schedule(新)

**触发条件:** 已从 registration-fetcher 拿到挂号入口 URL 后,需要:
- 用户已指名医生(`intent.doctor_name` 非空或 `selected_doctor` 传入) → 直接抓出诊表
- 用户未指名医生 → 先抓该科室专家列表让用户选

**输入依赖:** 来自 registration-fetcher 的 `registration_url`(或 official_url 兜底)。

**输出:** 
- 成功:`schedule`(出诊表+号源)+ `recommendation`(推荐就诊时段)+ 最多 2 个 `alternatives`
- 全满:`status='schedule_fetched_but_full'`,附 `warning`
- 找不到医生:`status='doctor_not_found'`,由 agent 请用户澄清
- 登录/验证码:`status='awaiting_browser_interaction'`,透传 `browser_session`
- 未选医生:`status='awaiting_doctor_selection'`,返回 `experts` 列表

**强制规则:**
- `registration_url` **只能**从 registration-fetcher 来,本 skill 不自查域名
- 一次对话内最多触发 1 次 autoclaw(不得自动重试)
- autoclaw 不可用时,静默降级:跳过本步,仍生成 PDF(只是 PDF 里无推荐时段)
- 禁止缓存 `slots`(号源实时抓)
- `task` 参数不改写用户原话,模板填充后禁双引号禁换行
```

**1c. 在第三节"决策速查表"后追加一行:**

```markdown
| "挂协和王立凡医生的号" | [4] registration-fetcher → [5] doctor-schedule |
```

**1d. 在第四节"禁止做法"追加三条:**

```markdown
- ❌ **不要在 doctor-schedule 内重试 autoclaw**,一次调用返回即为结果,需重试由用户下一轮主动触发。
- ❌ **不要缓存 `slots` 字段**,号源实时变动,缓存必误导用户。
- ❌ **不要让 doctor-schedule 失败阻塞整个流程**,L1/L2/L3 三层降级均需回退到"官网 URL + 无推荐时段"的 PDF。
```

- [ ] **Step 2: `config/autoclaw_integration.py` 注册新 skill**

Edit `config/autoclaw_integration.py` 的 `register_skills` 方法,在 `healthpath-registration-fetcher` 和 `healthpath-itinerary-builder` 之间插入:

```python
            {
                "name": "healthpath-doctor-schedule",
                "source": self.project_root / "skills" / "healthpath-doctor-schedule",
            },
```

同时在 `get_skill_status` 方法的 skill_name 列表里同位置插入:

```python
            "healthpath-doctor-schedule",
```

- [ ] **Step 3: 验证**

Run: `python config/autoclaw_integration.py`
Expected: 打印 `[OK] Registered skill: healthpath-doctor-schedule`,且 `status` JSON 中该键 `exists=True`。

- [ ] **Step 4: 提交**

```bash
git add SKILL_PREFERENCES.md config/autoclaw_integration.py
git commit -m "docs+config: 把 doctor-schedule 加入工作流与 AutoClaw 注册清单

  - SKILL_PREFERENCES.md: 5 步 → 6 步,新 skill 触发/降级/禁令说明
  - autoclaw_integration.py: register_skills/get_skill_status 同步"
```

---

### Task 10: 集成测试 + 端到端手动验证

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: 在集成测试中追加医生流程 case(仍用 fake driver,避免真跑浏览器)**

Append to `tests/test_integration.py`:

```python
import sys
import os

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-doctor-schedule"
))


def _stub_driver(observation):
    return {
        "status": "success",
        "session_id": "sid-stub",
        "tab_id": "1",
        "observation": observation,
        "structured": {},
        "interact_prompt": "",
        "screenshots": [],
        "error": None,
    }


def test_execute_returns_doctor_schedule_fetched_when_doctor_named(monkeypatch, tmp_path):
    import doctor_schedule
    import itinerary_builder

    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: _stub_driver(
            "王立凡 主任医师\n"
            "擅长:头痛、脑血管病\n"
            "2026-04-22|上午|3/20\n"
            "2026-04-24|下午|5/20\n"
        ),
    )

    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir, exist_ok=True)
    itinerary_builder.OUTPUT_DIR = out_dir

    result = execute(
        user_input="我要挂北京大学第三医院骨科王立凡医生的号",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    assert result["status"] == "doctor_schedule_fetched"
    assert result["final_output"]["recommendation"] is not None
    assert result["final_output"]["recommendation"]["date"] == "2026-04-22"


def test_execute_returns_awaiting_doctor_selection_when_not_named(monkeypatch, tmp_path):
    import doctor_schedule

    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: _stub_driver(
            "骨科专家:\n"
            "王立凡 主任医师 腰椎、脊柱\n"
            "李二 副主任医师 关节、骨折\n"
        ),
    )

    result = execute(
        user_input="帮我找北京大学第三医院骨科",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    assert result["status"] == "awaiting_doctor_selection"
    experts = result["final_output"]["experts"]
    assert any(e["name"] == "王立凡" for e in experts)


def test_execute_final_pdf_contains_doctor_when_confirmed(monkeypatch, tmp_path):
    import doctor_schedule
    import itinerary_builder

    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: _stub_driver(
            "王立凡 主任医师\n"
            "擅长:腰椎\n"
            "2026-04-22|上午|3/20\n"
        ),
    )

    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir, exist_ok=True)
    itinerary_builder.OUTPUT_DIR = out_dir

    result = execute(
        user_input="我要挂北京大学第三医院骨科王立凡医生的号",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        confirmed_appointment={"date": "2026-04-22", "time_slot": "上午"},
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    assert result["status"] == "success"
    pdf_path = result["final_output"]["pdf_path"]
    assert os.path.exists(pdf_path)
    assert result["final_output"]["doctor"]["name"] == "王立凡"


def test_execute_autoclaw_unavailable_still_generates_pdf(monkeypatch, tmp_path):
    """autoclaw 不可用时降级路径:最终仍生成 PDF,只是没有 doctor 上下文。"""
    import doctor_schedule
    import itinerary_builder

    monkeypatch.setattr(doctor_schedule, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        doctor_schedule,
        "run_browser_task",
        lambda **kw: {
            "status": "not_available",
            "session_id": None, "tab_id": None,
            "observation": "", "structured": {}, "interact_prompt": "",
            "screenshots": [], "error": "autoclaw 不可用",
        },
    )

    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir, exist_ok=True)
    itinerary_builder.OUTPUT_DIR = out_dir

    result = execute(
        user_input="我要挂北京大学第三医院骨科王立凡医生的号",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        confirmed_appointment={"date": "2026-04-22", "time_slot": "上午"},
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )
    # 因为 doctor-schedule 降级了,status 不再是 doctor_schedule_fetched 但仍应到 success
    assert result["status"] == "success"
    assert os.path.exists(result["final_output"]["pdf_path"])
```

- [ ] **Step 2: 跑全量测试**

Run: `pytest tests/ -v`
Expected: 所有测试通过(原有 + 本次新增的 27 个 左右)

- [ ] **Step 3: 手动端到端验证(真 autoclaw)**

前提:已装 AutoClaw 且浏览器扩展已启用。

```powershell
cd "D:\xuexi\competition\计算机设计大赛\project"; $env:PYTHONIOENCODING='utf-8'; python -c "
import json
from main_skill import execute

# Turn 1: 指定医院 + 医生
r = execute(
    user_input='我要挂北京协和医院神经内科王立凡医生的号',
    user_location='北京市朝阳区望京街道',
    selected_hospital='北京协和医院',
    user_profile={'age_group': 'adult'},
)
print('Turn 1 status:', r['status'])
print(json.dumps(r.get('final_output'), ensure_ascii=False, indent=2)[:500])
"
```

可能出现的分支:
- `doctor_schedule_fetched`:接着传 `confirmed_appointment` 再跑一次,应返回 `success` 并生成 PDF
- `awaiting_browser_interaction`:屏幕上 Chrome 窗口会提示登录,完成后传 `browser_resume={...}` 恢复
- `doctor_not_found`:说明医生名在协和官网上没匹配到,属于真实场景(可以换"张抒扬"等真存在的协和专家重试)
- `error` 且 `autoclaw 不可用`:说明本机未装 AutoClaw,自动降级,最终仍能生成只带官网 URL 的 PDF

验证通过标准:**至少能走通其中一个分支,无 unhandled exception**。

- [ ] **Step 4: 提交测试**

```bash
git add tests/test_integration.py
git commit -m "test(integration): 覆盖 doctor-schedule 的 4 个典型路径

  - doctor_schedule_fetched(指名医生抓到号源)
  - awaiting_doctor_selection(未指名,抓专家列表)
  - 确认推荐后生成 PDF 并携带医生信息
  - autoclaw 不可用时降级,仍能生成 PDF"
```

- [ ] **Step 5: 最终推送与总结**

```bash
git log --oneline -20
```

Expected: 能看到本次实施的所有 commit(Task 1-10)。

---

## Self-Review 核对

1. **Spec coverage**:
   - Section 2 状态机变化 → Task 7
   - Section 3 skill 接口 → Task 3/4/5
   - Section 4 autoclaw 封装 + 中断恢复 → Task 2/3/4
   - Section 5 缓存 → Task 4
   - Section 6 推荐算法 → Task 1
   - Section 7 降级 → Task 2/3/4(三层分别在 driver/schedule/main_skill)
   - Section 8 硬约束 → Task 5(SKILL.md)+ Task 9(SKILL_PREFERENCES)
   - Section 9 测试策略 → Task 1/2/3/4/6/10
   - Section 10 范围外 → 无 task(不做即为完成)
   - Section 11 实施次序 → 与本计划的 Task 顺序一致
   - 全部 Section 有对应 task,无遗漏。

2. **Placeholder scan**: 已检查,无 TBD/TODO/"similar to Task N",所有 step 都有实际代码或命令。

3. **Type/名称一致性**:
   - `status` 枚举在 Task 3/4/7/10 一致
   - `browser_session` 字典键 `session_id`/`tab_id` 一致
   - 模块导入路径一致(`doctor_schedule`、`autoclaw_driver`、`recommender`)
   - `_err(kind, msg)` 在 Task 3 定义,Task 4 使用方式一致
