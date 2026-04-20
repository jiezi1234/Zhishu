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
