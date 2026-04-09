# 在AutoClaw中调用Zhishu Agent - 完整指南

## 📍 项目地址

**GitHub**: https://github.com/jiezi1234/Zhishu

## 🔧 第一步: 注册Skills到AutoClaw

### 1.1 克隆项目

```bash
git clone https://github.com/jiezi1234/Zhishu.git
cd Zhishu
```

### 1.2 运行注册脚本

```bash
python config/autoclaw_integration.py
```

这会将所有Skills复制到AutoClaw工作空间：
```
C:\Users\Administrator\.openclaw-autoclaw\skills\
├── healthpath-intent-understanding/
├── healthpath-hospital-crawler/
├── healthpath-decision-engine/
└── healthpath-output-generator/
```

## 🚀 第二步: 在AutoClaw中调用

### 方式1: 调用主Skill (推荐)

在AutoClaw中直接调用主Skill，它会自动协调所有子Skill：

```python
# AutoClaw中的代码
result = call_skill("healthpath-agent", {
    "user_input": "我想在北京找个好医院看骨科，最好这周能挂上号",
    "output_format": "large_font_pdf"
})

# 获取生成的PDF
pdf_path = result["final_output"]["pdf_path"]
print(f"PDF已生成: {pdf_path}")
```

### 方式2: 逐个调用Skills

如果需要更细粒度的控制，可以逐个调用Skills：

```python
# Step 1: 意图解析
intent_result = call_skill("healthpath-intent-understanding", {
    "user_input": "我想在北京找个好医院看骨科，最好这周能挂上号"
})
task_params = intent_result["task_params"]

# Step 2: 号源搜索
search_result = call_skill("healthpath-hospital-crawler", {
    "task_params": task_params
})
slots = search_result["slots"]

# Step 3: 方案决策
decision_result = call_skill("healthpath-decision-engine", {
    "slots": slots,
    "task_params": task_params
})
recommendations = decision_result["recommendations"]

# Step 4: PDF生成
output_result = call_skill("healthpath-output-generator", {
    "recommendations": recommendations,
    "task_params": task_params,
    "output_format": "large_font_pdf"
})

pdf_path = output_result["files"]["pdf"]
```

### 方式3: 使用AutoClaw采集的数据 (最优)

让AutoClaw采集真实网页数据，然后传给Skills分析：

```python
# Step 1: 解析意图
intent_result = call_skill("healthpath-intent-understanding", {
    "user_input": "我想在北京找个好医院看骨科"
})
task_params = intent_result["task_params"]

# Step 2: AutoClaw浏览器采集数据
browser = await playwright.chromium.launch()
page = await browser.new_page()
await page.goto("https://www.114ygk.com/")
html_data = await page.content()

raw_hospital_data = {
    "source": "114ygk",
    "data": html_data,
    "format": "html"
}

# Step 3: 传递采集的数据给Skill 2分析
search_result = call_skill("healthpath-hospital-crawler", {
    "task_params": task_params,
    "raw_hospital_data": raw_hospital_data
})

# Step 4-5: 继续后续流程...
```

## 📝 输入参数说明

### 主Skill参数

```json
{
  "user_input": "用户的自然语言输入",
  "output_format": "large_font_pdf 或 pdf"
}
```

### 各Skill参数

**Skill 1 - 意图解析**:
```json
{
  "user_input": "我想在北京找个好医院看骨科，最好这周能挂上号"
}
```

**Skill 2 - 号源搜索**:
```json
{
  "task_params": {
    "department": "骨科",
    "symptom": "腰疼",
    "time_window": "this_week",
    "travel_preference": "nearby"
  },
  "raw_hospital_data": {  // 可选，AutoClaw采集的数据
    "source": "114ygk",
    "data": "<html>...</html>",
    "format": "html"
  }
}
```

**Skill 3 - 方案决策**:
```json
{
  "slots": [...],
  "task_params": {...}
}
```

**Skill 4 - PDF生成**:
```json
{
  "recommendations": [...],
  "task_params": {...},
  "output_format": "large_font_pdf"
}
```

## 📊 输出结果说明

### 主Skill返回结果

```json
{
  "status": "success",
  "steps": {
    "intent_parsing": {...},
    "hospital_search": {...},
    "decision_ranking": {...},
    "output_generation": {...}
  },
  "final_output": {
    "success": true,
    "pdf_path": "/path/to/appointment_itinerary_*.pdf",
    "file_size_kb": 35.2
  },
  "error": null
}
```

### 状态码

| 状态 | 说明 |
|------|------|
| success | 成功生成PDF |
| no_results | 未找到号源，但仍生成PDF |
| error | 执行出错 |

## 🎯 使用示例

### 示例1: 老年人就医

```python
result = call_skill("healthpath-agent", {
    "user_input": "我奶奶最近腰疼得厉害，想在北京找个好医院看骨科，最好这周能挂上号，离家近一点最好",
    "output_format": "large_font_pdf"
})

if result["status"] == "success":
    pdf_path = result["final_output"]["pdf_path"]
    print(f"✓ 已为您生成就医行程单: {pdf_path}")
else:
    print(f"✗ 生成失败: {result['error']}")
```

### 示例2: 上班族就医

```python
result = call_skill("healthpath-agent", {
    "user_input": "我最近头晕，想找个离公司近的医院看神经内科，最好能在周末或晚上挂号",
    "output_format": "pdf"
})
```

### 示例3: 异地就医

```python
result = call_skill("healthpath-agent", {
    "user_input": "我从外地来北京，需要看呼吸科，最好能找个评价好的医院，费用不要太贵",
    "output_format": "large_font_pdf"
})
```

## 🔄 完整的AutoClaw工作流程

```
用户在AutoClaw中输入
    ↓
AutoClaw调用 call_skill("healthpath-agent", {...})
    ↓
main_skill.py (HealthPathAgent)
    ├─ Skill 1: 意图解析
    ├─ Skill 2: 号源搜索 (可接收AutoClaw采集的数据)
    ├─ Skill 3: 方案决策
    └─ Skill 4: PDF生成
    ↓
返回PDF路径和执行详情
    ↓
AutoClaw获取PDF并返回给用户
```

## 📋 配置检查清单

- [ ] 项目已克隆到本地
- [ ] 运行了 `python config/autoclaw_integration.py`
- [ ] Skills已复制到AutoClaw工作空间
- [ ] AutoClaw可以识别 "healthpath-agent" Skill
- [ ] 已安装依赖: `pip install -r requirements-crawler.txt`

## 🧪 测试调用

### 本地测试

```bash
# 测试主Skill
python main_skill.py

# 测试端到端流程
python tests/test_end_to_end.py

# 测试缓存系统
python skills/skill_2_crawl/test_hospital_data.py
```

### AutoClaw中测试

```python
# 在AutoClaw中执行
result = call_skill("healthpath-agent", {
    "user_input": "我想在北京找个好医院看骨科",
    "output_format": "large_font_pdf"
})

print(result)
```

## 🐛 常见问题

### Q: 如何查看Skill是否已注册？

A: 检查AutoClaw工作空间：
```bash
ls C:\Users\Administrator\.openclaw-autoclaw\skills\
```

应该看到：
- healthpath-intent-understanding/
- healthpath-hospital-crawler/
- healthpath-decision-engine/
- healthpath-output-generator/

### Q: 如何更新Skill？

A: 重新运行注册脚本：
```bash
python config/autoclaw_integration.py
```

### Q: 如何处理没有找到号源的情况？

A: 系统会返回 `status: "no_results"`，但仍会生成PDF显示"未找到"。

### Q: 如何使用AutoClaw采集的数据？

A: 参考"方式3: 使用AutoClaw采集的数据"部分。

### Q: 如何自定义输出格式？

A: 修改 `output_format` 参数：
- `"pdf"`: 标准版
- `"large_font_pdf"`: 大字版（默认）

## 📚 相关文档

- **AUTOCLAW_QUICK_START.md** - 快速参考
- **AUTOCLAW_INTEGRATION.md** - 完整集成指南
- **AUTOCLAW_BROWSER_COLLECTION.md** - 浏览器采集架构
- **SKILL.md** - 主Skill文档

## 🔗 快速链接

- **GitHub**: https://github.com/jiezi1234/Zhishu
- **主Skill**: main_skill.py
- **配置脚本**: config/autoclaw_integration.py
- **测试脚本**: tests/test_end_to_end.py

---

**现在你可以在AutoClaw中调用Zhishu Agent了！** 🎉

有任何问题，请参考相关文档或查看GitHub仓库。
