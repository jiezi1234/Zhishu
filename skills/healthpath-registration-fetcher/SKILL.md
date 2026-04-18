---
name: healthpath-registration-fetcher
description: Fetch hospital official website URL from local cache or yixue.com; URL validation and fallback web search are handled by the agent
metadata:
  openclaw:
    emoji: "🔗"
    requires:
      bins: ["python3"]
      python:
        runtime: ">=3.10"
        packages: []
---

# registration_fetcher — 医院官网 URL 采集

## 职责划分

| 执行者 | 职责 |
|---|---|
| **本脚本** | 查本地缓存 → 访问 yixue.com 解析官网 URL → 返回结果 |
| **Agent** | 验证 URL 可用性 → 网络搜索兜底 → 调用 `save_to_cache()` 写入缓存 |

脚本本身**不做任何 URL 验证或网络搜索**。

---

## 调用流程

```
Agent 调用 fetch(hospital_name)
  │
  ├─ 命中缓存（永久有效）→ 直接返回 official_url，from_cache=True
  │
  └─ 缓存未命中
       └─ 访问 https://www.yixue.com/<hospital_name>
            解析 <b>医院网站</b> 字段中的 href
            └─ 返回 official_url（可能为空字符串）

Agent 收到结果后：
  ├─ official_url 非空
  │    ├─ 验证 URL 可访问（HTTP < 400）
  │    │    ├─ 可访问 → 调用 save_to_cache(hospital_name, official_url)，完成
  │    │    └─ 不可访问 → 执行"网搜修正"流程（见下文）
  │    
  └─ official_url 为空字符串 → 直接执行"网搜修正"流程

网搜修正流程：
  使用 WebSearch 搜索 "<hospital_name> 官方网站"
  找到可信的官方域名后 → 调用 save_to_cache(hospital_name, new_url)
  若无法确认 → 向用户说明，建议拨打医院电话
```

---

## 脚本 API

### `fetch(hospital_name: str) -> dict`

查缓存 + 解析 yixue.com，返回官网 URL。

### 方式 1：Python 脚本（推荐，避免编码问题）

创建临时脚本 `temp_fetcher.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'skills/healthpath-registration-fetcher')
from registration_fetcher import fetch

result = fetch("北京协和医院")
print(json.dumps(result, ensure_ascii=False, indent=2))
```

然后执行（**Windows PowerShell 必须用分号分隔，不能用 &&**）：
```powershell
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_fetcher.py
```

**为什么用脚本？** Windows PowerShell 的 GBK 编码会导致 UnicodeEncodeError，脚本方式可以正确处理 UTF-8 中文输出。

**⚠️ PowerShell 语法注意：**
- ❌ 错误：`cd E:\homework\Zhishu && $env:PYTHONIOENCODING='utf-8' && python temp_fetcher.py`
  - PowerShell 中 `&&` 不是有效的链接符，会导致 ParserError
- ✅ 正确：`cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_fetcher.py`
  - 用分号 `;` 分隔多条命令
- 或者用 `cmd /c` 包装（支持 `&&`）：`cmd /c "cd E:\homework\Zhishu && set PYTHONIOENCODING=utf-8 && python temp_fetcher.py"`

### 方式 2：直接 Python 调用（仅限 Linux/macOS���

```python
from skills.registration_fetcher.registration_fetcher import fetch

result = fetch("北京协和医院")
```

**返回字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `hospital_name` | `str` | 同输入 |
| `official_url` | `str` | 官方网站 URL；无法获取时为 `""` |
| `from_cache` | `bool` | `True` = 来自本地缓存 |
| `timestamp` | `str` | ISO 格式时间戳 |

---

### `save_to_cache(hospital_name: str, official_url: str) -> None`

Agent 验证 URL 可用后调用，将结果永久写入缓存。

### 方式 1：Python 脚本（推荐）

创建临时脚本 `temp_save_cache.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'skills/healthpath-registration-fetcher')
from registration_fetcher import save_to_cache

save_to_cache("北京协和医院", "https://www.pumch.ac.cn/")
print("缓存已保存")
```

然后执行：
```powershell
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_save_cache.py
```

### 方式 2：直接 Python 调用（仅限 Linux/macOS）

```python
from skills.registration_fetcher.registration_fetcher import save_to_cache

save_to_cache("北京协和医院", "https://www.pumch.ac.cn/")
```

---

## yixue.com 解析规则

目标页面：`https://www.yixue.com/<hospital_name>`

匹配的 HTML 结构：

```html
<li>
  <b>医院网站</b>：
  <a rel="nofollow" class="external free" href="http://www.pumch.ac.cn">
    http://www.pumch.ac.cn
  </a>
</li>
```

正则（主）：`<b>医院网站</b>.*?href=["']([^"']+)["']`  
正则（备）：`官方网站.*?href=["']([^"']+)["']`

两者均匹配失败时，返回 `official_url: ""`。

---

## 缓存文件

`skills/registration_fetcher/hospital_info.json`

```json
{
  "北京协和医院": {
    "official_url": "https://www.pumch.ac.cn/",
    "timestamp": "2026-04-13T10:00:00.000000"
  }
}
```

- 缓存永久有效，无过期限制
- 仅 Agent 确认 URL 可访问后方可写入，脚本本身不写缓存

---

## Agent 操作指引

### 收到 `official_url` 非空时

1. **验证**：对该 URL 发起 HEAD 或 GET 请求，检查响应状态码是否 < 400
2. **成功**：调用 `save_to_cache(hospital_name, official_url)`，向用户展示官网链接
3. **失败**：进入下一步网搜修正

### 收到 `official_url` 为空，或 URL 验证失败时

1. 使用 **WebSearch** 搜索：`"<hospital_name>" 官方网站`
2. 从结果中识别可信官方域名（排除百科、广告、聚合平台等）
3. 对候选 URL 再次验证可访问性
4. 验证通过 → 调用 `save_to_cache(hospital_name, verified_url)`
5. 无法确认 → 向用户说明情况，建议通过医院官方电话或现场咨询

### 向用户展示

- 展示经验证的 `official_url` 并提示用户在官网上查找预约挂号入口
- 若 URL 经过网搜修正，注明"官网地址已通过网络搜索确认，建议就诊前再次核实"
- 若最终无法获取，建议用户拨打医院总机或现场挂号

---

## 注意事项

- yixue.com 页面可能因网络或反爬原因访问失败，此时 `official_url` 返回 `""`，Agent 应直接进入网搜流程
- 缓存写入仅在 Agent 确认 URL 真实可达后执行，避免缓存无效地址
- 不同医院的 yixue.com 页面结构基本一致，但部分冷门医院可能无词条，需依赖网搜

## 编码与平台兼容性

**Windows 特殊处理（必须）：**
- PowerShell 默认 GBK 编码，直接运行 Python 会导致 `UnicodeEncodeError`
- 解决方案：**必须使用脚本方式**（见"脚本 API"部分）
- 脚本中设置 `PYTHONIOENCODING='utf-8'` 和 `sys.stdout.reconfigure(encoding='utf-8')`
- 输出 JSON 时使用 `ensure_ascii=False` 保留中文

**Linux/macOS：** 可直接调用，无需额外处理

## 常见问题

### Q: 执行时出现 `ParserError` 或 `InvalidEndOfLine`

**原因：** PowerShell 不支持 `&&` 链接符。

**解决：** 用分号 `;` 替代：
```powershell
cd E:\homework\Zhishu; $env:PYTHONIOENCODING='utf-8'; python temp_fetcher.py
```

### Q: 输出乱码或 `UnicodeEncodeError`

**原因：** PowerShell 默认 GBK 编码，Python 输出 UTF-8 中文时冲突。

**解决：** 
1. 确保脚本中有 `sys.stdout.reconfigure(encoding='utf-8')`
2. 确保 JSON 输出用 `ensure_ascii=False`
3. 执行前设置 `$env:PYTHONIOENCODING='utf-8'`

### Q: `official_url` 返回空字符串

**原因：** yixue.com 页面无该医院词条，或页面结构变化。

**解决：** 
- Agent 应自动进入网搜修正流程
- 使用 WebSearch 搜索 `"<hospital_name> 官方网站"`
- 验证 URL 可访问后调用 `save_to_cache()` 写入缓存

### Q: 缓存的 URL 失效了

**原因：** 医院官网域名变更或网站下线。

**解决：** 
- 手动删除 `skills/healthpath-registration-fetcher/hospital_info.json` 中对应条目
- 或直接调用 `save_to_cache()` 覆盖旧 URL
- 下次调用 `fetch()` 会重新解析 yixue.com

### Q: yixue.com 访问超时

**原因：** 网络问题或反爬限制。

**解决：** 
- `fetch()` 会返回 `official_url: ""`
- Agent 应直接跳过 yixue.com，进入网搜流程
- 考虑添加重试机制或更换网络环境
