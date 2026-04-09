---
name: healthpath-hospital-crawler
description: Search and fetch available medical appointment slots from multiple hospitals based on department and time constraints
metadata: {"openclaw": {"emoji": "🏨", "requires": {"bins": ["python3"]}}}
---

# HealthPath Hospital Crawler Skill

## When to Use

After intent understanding extracts the appointment requirements, this skill searches for available appointment slots across multiple hospitals that match the criteria.

## What It Does

1. **Hospital Selection**: Filters hospitals by location and distance
2. **Slot Retrieval**: Fetches available appointment slots for the requested department
3. **Data Standardization**: Normalizes data from different sources into unified format
4. **Filtering**: Applies time window and other constraints
5. **Ranking**: Sorts results by relevance

## Input

### 方式1: 仅使用任务参数 (本地爬虫/模拟数据)

```json
{
  "department": "骨科",
  "target_city": "北京",
  "time_window": "this_week",
  "travel_preference": "nearby"
}
```

### 方式2: 接收AutoClaw采集的数据 (推荐)

```json
{
  "task_params": {
    "department": "骨科",
    "target_city": "北京",
    "time_window": "this_week",
    "travel_preference": "nearby"
  },
  "raw_hospital_data": {
    "source": "114ygk",
    "data": "<html>...</html>",
    "format": "html"
  }
}
```

其中 `raw_hospital_data` 可以是:
- **source**: "114ygk" | "bjguahao" | "hospital_official"
- **data**: HTML字符串或JSON对象
- **format**: "html" | "json"

## Output

```json
{
  "slots": [
    {
      "hospital_id": "hospital_001",
      "hospital_name": "北京协和医院",
      "department": "骨科",
      "doctor_name": "张医生",
      "doctor_title": "主任医师",
      "available_time": "2026-04-15 09:00",
      "registration_fee": 100,
      "queue_estimate_min": 30,
      "distance_km": 2.5,
      "travel_time_min": 15
    }
  ],
  "total_count": 6,
  "search_timestamp": "2026-04-08T10:30:00"
}
```

## How It Works

1. Receives structured task parameters from Skill 1
2. Queries hospital database for matching hospitals
3. Fetches available slots (from mock data or real APIs)
4. Standardizes all data to unified format
5. Applies filters and sorting
6. Returns ranked list of available slots

## Data Sources

### 优先级顺序

1. **AutoClaw采集的数据** (最优)
   - 真实网页数据
   - 由AutoClaw浏览器采集
   - 格式: HTML或JSON

2. **114挂号网爬虫** (备选)
   - 本地Playwright爬虫
   - 自动反爬虫对策
   - 格式: HTML

3. **模拟数据** (降级)
   - 始终可用
   - 用于测试和演示
   - 格式: JSON

### 如何使用AutoClaw采集的数据

1. **AutoClaw浏览器采集**
   ```python
   browser = await playwright.chromium.launch()
   page = await browser.new_page()
   await page.goto("https://www.114ygk.com/")
   html_data = await page.content()
   ```

2. **传递给Skill 2**
   ```python
   result = call_skill("healthpath-hospital-crawler", {
       "task_params": task_params,
       "raw_hospital_data": {
           "source": "114ygk",
           "data": html_data,
           "format": "html"
       }
   })
   ```

3. **Skill 2分析数据**
   - 使用BeautifulSoup解析HTML
   - 提取医院、医生、时间、费用等信息
   - 标准化为统一格式
   - 返回slots列表

## Error Handling

- If no slots found, suggests alternative departments or time windows
- Handles API timeouts with retry logic
- Logs all failed requests for debugging

## References

See `scripts/hospital_crawler.py` for implementation details.
