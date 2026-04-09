# 🚀 Zhishu Agent - AutoClaw调用快速参考

## 📍 项目信息

| 项目 | 信息 |
|------|------|
| **名称** | Zhishu Agent (智枢) |
| **GitHub** | https://github.com/jiezi1234/Zhishu |
| **主Skill** | healthpath-agent |
| **功能** | 智能医疗就诊规划系统 |

## ⚡ 快速开始 (3步)

### 1️⃣ 注册Skills到AutoClaw

```bash
git clone https://github.com/jiezi1234/Zhishu.git
cd Zhishu
python config/autoclaw_integration.py
```

### 2️⃣ 在AutoClaw中调用

```python
result = call_skill("healthpath-agent", {
    "user_input": "我想在北京找个好医院看骨科，最好这周能挂上号",
    "output_format": "large_font_pdf"
})
```

### 3️⃣ 获取结果

```python
pdf_path = result["final_output"]["pdf_path"]
print(f"PDF已生成: {pdf_path}")
```

## 📋 三种调用方式

### 方式1: 主Skill (推荐) ⭐

```python
result = call_skill("healthpath-agent", {
    "user_input": "我想在北京找个好医院看骨科",
    "output_format": "large_font_pdf"
})
```

**优点**: 简单、快速、自动协调所有Skills

---

### 方式2: 逐个调用Skills

```python
# Step 1: 意图解析
intent = call_skill("healthpath-intent-understanding", {
    "user_input": "我想在北京找个好医院看骨科"
})

# Step 2: 号源搜索
search = call_skill("healthpath-hospital-crawler", {
    "task_params": intent["task_params"]
})

# Step 3: 方案决策
decision = call_skill("healthpath-decision-engine", {
    "slots": search["slots"],
    "task_params": intent["task_params"]
})

# Step 4: PDF生成
output = call_skill("healthpath-output-generator", {
    "recommendations": decision["recommendations"],
    "task_params": intent["task_params"]
})
```

**优点**: 细粒度控制、可插入自定义逻辑

---

### 方式3: 使用AutoClaw采集的数据 (最优) ⭐⭐

```python
# AutoClaw采集网页数据
browser = await playwright.chromium.launch()
page = await browser.new_page()
await page.goto("https://www.114ygk.com/")
html_data = await page.content()

# 传递给Skill 2分析
result = call_skill("healthpath-hospital-crawler", {
    "task_params": task_params,
    "raw_hospital_data": {
        "source": "114ygk",
        "data": html_data,
        "format": "html"
    }
})
```

**优点**: 真实数据、最高准确度

---

## 📝 输入参数

### 主Skill参数

```json
{
  "user_input": "用户的自然语言输入",
  "output_format": "large_font_pdf"  // 或 "pdf"
}
```

### 输出格式

- `"large_font_pdf"` - 大字版 (28pt标题, 16pt正文) - 老年友好
- `"pdf"` - 标准版 (20pt标题, 12pt正文)

---

## 📊 返回结果

```json
{
  "status": "success",
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
| `success` | ✅ 成功生成PDF |
| `no_results` | ⚠️ 未找到号源，但仍生成PDF |
| `error` | ❌ 执行出错 |

---

## 🎯 使用示例

### 例1: 老年人就医

```python
result = call_skill("healthpath-agent", {
    "user_input": "我奶奶腰疼，想在北京找个好医院看骨科，最好这周能挂上号",
    "output_format": "large_font_pdf"
})
```

### 例2: 上班族就医

```python
result = call_skill("healthpath-agent", {
    "user_input": "我最近头晕，想找个离公司近的医院看神经内科，最好周末能挂号",
    "output_format": "pdf"
})
```

### 例3: 异地就医

```python
result = call_skill("healthpath-agent", {
    "user_input": "我从外地来北京，需要看呼吸科，最好找个评价好的医院",
    "output_format": "large_font_pdf"
})
```

---

## 🔍 检查Skills是否已注册

```bash
# 查看AutoClaw工作空间
ls C:\Users\Administrator\.openclaw-autoclaw\skills\

# 应该看到这些文件夹:
# - healthpath-intent-understanding/
# - healthpath-hospital-crawler/
# - healthpath-decision-engine/
# - healthpath-output-generator/
```

---

## 🧪 本地测试

```bash
# 测试主Skill
python main_skill.py

# 测试完整流程
python tests/test_end_to_end.py

# 测试缓存系统
python skills/skill_2_crawl/test_hospital_data.py
```

---

## 📚 详细文档

| 文档 | 内容 |
|------|------|
| **HOW_TO_USE_IN_AUTOCLAW.md** | 完整使用指南 |
| **AUTOCLAW_QUICK_START.md** | 快速参考 |
| **AUTOCLAW_INTEGRATION.md** | 集成指南 |
| **AUTOCLAW_BROWSER_COLLECTION.md** | 浏览器采集架构 |
| **SKILL.md** | 主Skill文档 |

---

## ⚙️ 配置

### 依赖安装

```bash
pip install -r requirements-crawler.txt
```

### 注册Skills

```bash
python config/autoclaw_integration.py
```

### 更新Skills

```bash
# 修改代码后，重新运行注册脚本
python config/autoclaw_integration.py
```

---

## 🐛 常见问题

**Q: Skill没有被识别？**
A: 运行 `python config/autoclaw_integration.py` 重新注册

**Q: 如何查看执行日志？**
A: 检查返回结果中的 `steps` 字段

**Q: 如何处理没有找到号源？**
A: 系统会返回 `status: "no_results"`，但仍生成PDF

**Q: 如何使用真实数据？**
A: 使用方式3，让AutoClaw采集网页数据

---

## 🎉 现在你可以开始了！

```python
# 在AutoClaw中执行这行代码
result = call_skill("healthpath-agent", {
    "user_input": "我想在北京找个好医院看骨科",
    "output_format": "large_font_pdf"
})

print(f"✅ PDF已生成: {result['final_output']['pdf_path']}")
```

---

## 📞 获取帮助

- **GitHub**: https://github.com/jiezi1234/Zhishu
- **文档**: docs/HOW_TO_USE_IN_AUTOCLAW.md
- **示例**: tests/test_end_to_end.py

---

**祝你使用愉快！** 🚀
