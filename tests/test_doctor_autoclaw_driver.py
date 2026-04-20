import os
import sys
import subprocess
from unittest.mock import MagicMock

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
    assert 'session_id="sid-1"' in cmd
    assert 'tab_id="42"' in cmd
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
    monkeypatch.setattr(autoclaw_driver, "_is_available", lambda: True)
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
