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
