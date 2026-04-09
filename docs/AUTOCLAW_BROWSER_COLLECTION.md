# AutoClaw浏览器采集 + Skills数据分析架构

## 核心架构

```
用户输入 (自然语言)
    ↓
AutoClaw主智能体
    ├─ 浏览器自动化采集
    │  ├─ 访问114挂号网
    │  ├─ 访问京医通
    │  ├─ 访问医院官网
    │  └─ 提取HTML/JSON数据
    ↓
main_skill.py (HealthPathAgent)
    ├─ Skill 1: 意图解析 (parse_intent)
    │  └─ 输入: 用户输入
    │  └─ 输出: task_params
    ├─ Skill 2: 数据分析 (analyze_hospital_data)
    │  └─ 输入: AutoClaw采集的HTML/JSON + task_params
    │  └─ 输出: 标准化的slots数据
    ├─ Skill 3: 方案决策 (evaluate_and_rank)
    │  └─ 输入: slots + task_params
    │  └─ 输出: recommendations
    └─ Skill 4: PDF生成 (generate_output)
       └─ 输入: recommendations + task_params
       └─ 输出: PDF文件
    ↓
最终输出 (PDF)
```

## 工作流程详解

### 第一步: AutoClaw浏览器采集

AutoClaw负责浏览器自动化，采集真实数据：

```python
# AutoClaw中的操作
browser = await playwright.chromium.launch()
page = await browser.new_page()

# 访问114挂号网
await page.goto("https://www.114ygk.com/")
html_content = await page.content()

# 或访问京医通
await page.goto("https://www.bjguahao.gov.cn/")
json_data = await page.evaluate("() => window.__data__")

# 返回采集的数据给Skills
return {
    "source": "114ygk",
    "data": html_content,  # 原始HTML
    "format": "html"
}
```

### 第二步: Skill 2 分析采集的数据

Skills接收AutoClaw采集的数据，进行解析和标准化：

```python
def analyze_hospital_data(
    raw_data: Dict,  # AutoClaw采集的原始数据
    task_params: Dict  # Skill 1输出的任务参数
) -> Dict:
    """
    分析AutoClaw采集的医院数据
    
    Args:
        raw_data: {
            "source": "114ygk" | "bjguahao" | "hospital_official",
            "data": "<html>...</html>" | {...json...},
            "format": "html" | "json"
        }
        task_params: {
            "department": "骨科",
            "symptom": "腰疼",
            ...
        }
    
    Returns:
        {
            "slots": [
                {
                    "hospital_name": "北京协和医院",
                    "doctor_name": "李医生",
                    "appointment_time": "2026-04-15 09:00",
                    "distance_km": 2.5,
                    "total_cost": 100,
                    "queue_estimate_min": 30,
                    "source": "114ygk"
                }
            ]
        }
    """
    
    source = raw_data.get("source")
    data = raw_data.get("data")
    format_type = raw_data.get("format")
    
    if format_type == "html":
        # 使用BeautifulSoup解析HTML
        slots = parse_html_data(data, source)
    elif format_type == "json":
        # 直接解析JSON
        slots = parse_json_data(data, source)
    else:
        slots = []
    
    # 过滤和标准化
    slots = filter_and_normalize(slots, task_params)
    
    return {"slots": slots}
```

## 修改后的Skills接口

### Skill 2: 号源搜索 (更新)

**原来的接口**:
```python
def search_available_slots(task_params: dict) -> dict:
    """从模拟数据或本地爬虫获取号源"""
```

**新的接口** (支持AutoClaw采集的数据):
```python
def search_available_slots(
    task_params: dict,
    raw_hospital_data: Optional[Dict] = None  # AutoClaw采集的数据
) -> dict:
    """
    搜索可用号源
    
    Args:
        task_params: 任务参数
        raw_hospital_data: AutoClaw采集的原始数据 (可选)
            {
                "source": "114ygk" | "bjguahao" | "hospital_official",
                "data": "<html>...</html>" | {...json...},
                "format": "html" | "json"
            }
    
    Returns:
        {
            "slots": [...],
            "total_count": 5,
            "data_sources": ["114ygk"],
            "search_timestamp": "2026-04-09T15:00:00"
        }
    """
    
    if raw_hospital_data:
        # 使用AutoClaw采集的数据
        slots = analyze_hospital_data(raw_hospital_data, task_params)
    else:
        # 降级到本地爬虫或模拟数据
        slots = search_available_slots_local(task_params)
    
    return slots
```

## 调用流程

### 方式1: AutoClaw完全控制 (推荐)

```python
# AutoClaw中
# 第一步: 调用Skill 1解析意图
intent_result = call_skill("healthpath-intent-understanding", {
    "user_input": "我想在北京找个好医院看骨科"
})
task_params = intent_result["task_params"]

# 第二步: AutoClaw浏览器采集数据
browser = await playwright.chromium.launch()
page = await browser.new_page()
await page.goto("https://www.114ygk.com/")
html_data = await page.content()

raw_hospital_data = {
    "source": "114ygk",
    "data": html_data,
    "format": "html"
}

# 第三步: 调用Skill 2分析数据
search_result = call_skill("healthpath-hospital-crawler", {
    "task_params": task_params,
    "raw_hospital_data": raw_hospital_data
})

# 第四步: 调用Skill 3决策
decision_result = call_skill("healthpath-decision-engine", {
    "slots": search_result["slots"],
    "task_params": task_params
})

# 第五步: 调用Skill 4生成输出
output_result = call_skill("healthpath-output-generator", {
    "recommendations": decision_result["recommendations"],
    "task_params": task_params
})

# 返回PDF
return output_result["pdf_path"]
```

### 方式2: 混合模式 (AutoClaw + Skills协作)

```python
# AutoClaw中
result = call_skill("healthpath-agent", {
    "user_input": "我想在北京找个好医院看骨科",
    "enable_browser_collection": True,  # 启用浏览器采集
    "data_sources": ["114ygk", "bjguahao"]  # 指定数据源
})

# main_skill.py内部会:
# 1. 调用Skill 1解析意图
# 2. 请求AutoClaw采集数据
# 3. 调用Skill 2分析数据
# 4. 调用Skill 3决策
# 5. 调用Skill 4生成输出
```

## 数据流示例

### 输入: AutoClaw采集的HTML

```html
<div class="hospital-item">
    <h3>北京协和医院</h3>
    <div class="doctor">李医生 - 主任医师</div>
    <div class="time">2026-04-15 09:00</div>
    <div class="fee">100元</div>
    <div class="queue">30分钟</div>
</div>
```

### 处理: Skill 2解析

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html_data, 'html.parser')
items = soup.find_all('div', class_='hospital-item')

slots = []
for item in items:
    slot = {
        "hospital_name": item.find('h3').text,
        "doctor_name": item.find('div', class_='doctor').text.split(' - ')[0],
        "doctor_title": item.find('div', class_='doctor').text.split(' - ')[1],
        "appointment_time": item.find('div', class_='time').text,
        "total_cost": int(item.find('div', class_='fee').text.replace('元', '')),
        "queue_estimate_min": int(item.find('div', class_='queue').text.replace('分钟', '')),
        "source": "114ygk"
    }
    slots.append(slot)
```

### 输出: 标准化的slots

```json
{
    "slots": [
        {
            "hospital_name": "北京协和医院",
            "doctor_name": "李医生",
            "doctor_title": "主任医师",
            "appointment_time": "2026-04-15 09:00",
            "total_cost": 100,
            "queue_estimate_min": 30,
            "source": "114ygk"
        }
    ]
}
```

## 实现步骤

### 1. 更新Skill 2接口

```python
# skills/skill_2_crawl/hospital_crawler.py

def search_available_slots(
    task_params: dict,
    raw_hospital_data: Optional[Dict] = None
) -> dict:
    """支持AutoClaw采集的数据"""
    
    if raw_hospital_data:
        # 分析AutoClaw采集的数据
        slots = analyze_hospital_data(raw_hospital_data, task_params)
    else:
        # 降级到本地方案
        slots = search_available_slots_local(task_params)
    
    return {
        "slots": slots,
        "total_count": len(slots),
        "search_timestamp": datetime.now().isoformat()
    }


def analyze_hospital_data(raw_data: Dict, task_params: Dict) -> list:
    """分析AutoClaw采集的医院数据"""
    
    source = raw_data.get("source")
    data = raw_data.get("data")
    format_type = raw_data.get("format")
    
    if format_type == "html":
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(data, 'html.parser')
        
        if source == "114ygk":
            slots = parse_114ygk_html(soup)
        elif source == "bjguahao":
            slots = parse_bjguahao_html(soup)
        else:
            slots = []
    
    elif format_type == "json":
        if source == "114ygk":
            slots = parse_114ygk_json(data)
        elif source == "bjguahao":
            slots = parse_bjguahao_json(data)
        else:
            slots = []
    
    else:
        slots = []
    
    return slots
```

### 2. 更新main_skill.py

```python
def execute(
    user_input: str,
    output_format: str = "large_font_pdf",
    raw_hospital_data: Optional[Dict] = None  # AutoClaw采集的数据
) -> Dict[str, Any]:
    """
    执行完整的医疗就诊规划流程
    
    Args:
        user_input: 用户输入
        output_format: 输出格式
        raw_hospital_data: AutoClaw采集的原始数据 (可选)
    """
    
    # ... 前面的代码 ...
    
    # Step 2: 号源搜索 (支持AutoClaw采集的数据)
    search_result = self._step2_search_slots(
        task_params,
        raw_hospital_data  # 传递AutoClaw采集的数据
    )
    
    # ... 后面的代码 ...
```

### 3. 更新SKILL.md文档

在每个Skill的SKILL.md中说明:
- 支持AutoClaw采集的数据格式
- 数据源的优先级
- 如何处理不同格式的数据

## 优势

1. **分离关注点**
   - AutoClaw: 浏览器自动化、网页采集
   - Skills: 数据分析、决策、输出

2. **灵活性**
   - Skills可以处理多种数据源
   - 支持本地爬虫和AutoClaw采集的混合

3. **可维护性**
   - 数据采集逻辑集中在AutoClaw
   - 数据分析逻辑集中在Skills
   - 易于测试和调试

4. **可扩展性**
   - 轻松添加新的数据源
   - 轻松添加新的解析器
   - 轻松添加新的分析逻辑

## 测试

```python
# 测试Skill 2接收AutoClaw采集的数据

raw_data = {
    "source": "114ygk",
    "data": "<html>...</html>",
    "format": "html"
}

task_params = {
    "department": "骨科",
    "symptom": "腰疼"
}

result = search_available_slots(task_params, raw_data)
assert len(result["slots"]) > 0
```

## 总结

这个架构充分利用了AutoClaw的浏览器自动化能力和我们Skills的数据分析能力，实现了真正的智能化医疗就诊规划系统。
