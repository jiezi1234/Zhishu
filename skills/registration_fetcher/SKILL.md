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
