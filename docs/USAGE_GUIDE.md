# HealthPath Agent - 使用指南

## 快速开始

### 1. 环境配置

```bash
# 设置 DeepSeek API Key
export DEEPSEEK_API_KEY="sk-"

# 设置 AutoClaw 工作空间（可选）
export AUTOCLAW_WORKSPACE="C:\Users\Administrator\.openclaw-autoclaw"
```

### 2. 运行演示

```bash
cd project
python demo/demo.py
```

### 3. 运行集成测试

```bash
python tests/test_integration.py
```

## 项目结构详解

### Skills 目录

每个 Skill 包含：

- `SKILL.md` - Skill 定义和文档
- `_meta.json` - Skill 元数据
- `*.py` - 实现代码

### 数据目录

- `data/mock/` - 模拟数据（医院库、号源库）
- `data/real/` - 真实数据（后期）

### 输出目录

- `output/` - 生成的 PDF/Excel 文件

## 4 个核心 Skill 详解

### Skill 1: 意图理解与约束抽取

**文件**：`skills/skill_1_intent/`

**功能**：使用 DeepSeek API 解析用户自然语言输入

**关键代码**：

```python
from intent_parser import parse_intent

# 使用 DeepSeek API
task_params = parse_intent(user_input, use_deepseek=True)

# 或使用规则解析（备选）
task_params = parse_intent(user_input, use_deepseek=False)
```

**输出参数**：

- `symptom` - 症状
- `department` - 科室
- `target_city` - 目标城市
- `time_window` - 时间窗口
- `budget` - 预算
- `travel_preference` - 出行偏好
- `is_remote` - 是否异地
- `output_format` - 输出格式
- `special_requirements` - 特殊需求

### Skill 2: 跨院号源巡航与标准化

**文件**：`skills/skill_2_crawl/`

**功能**：搜索多家医院的可用号源

**关键代码**：

```python
from hospital_crawler import search_available_slots

search_result = search_available_slots(task_params)
# 返回：
# {
#   "slots": [...],
#   "total_count": 4,
#   "search_timestamp": "2026-04-08T..."
# }
```

**数据源**：

- 当前：模拟数据 (`data/mock/available_slots.json`)
- 后期：真实医院 API、网页爬取

### Skill 3: 医旅协同与多目标决策

**文件**：`skills/skill_3_decision/`

**功能**：评估和排序方案

**关键代码**：

```python
from decision_engine import evaluate_and_rank

recommendations = evaluate_and_rank(
    slots=search_result['slots'],
    task_params=task_params,
    top_n=2
)
```

**评分算法**：

```
score = 0.2 * distance_score + 0.3 * time_score + 0.3 * cost_score + 0.2 * queue_score
```

### Skill 4: 结果生成与触达

**文件**：`skills/skill_4_output/`

**功能**：生成 PDF/Excel 输出文档

**关键代码**：

```python
from output_generator import generate_output

output_result = generate_output(
    recommendations=recommendations['recommendations'],
    task_params=task_params,
    output_format='large_font_pdf'  # 或 'excel'
)
```

**支持格式**：

- `large_font_pdf` - 大字版 PDF（老年友好）
- `pdf` - 标准 PDF
- `excel` - Excel 表格

## DeepSeek API 集成

### 配置

```python
from config.deepseek_client import DeepSeekClient

client = DeepSeekClient()
intent = client.extract_intent(user_input)
```

### API 参数

- `api_key` - DeepSeek API Key
- `base_url` - API 端点（默认：<https://api.deepseek.com/v1）>
- `model` - 模型名称（默认：deepseek-chat）

### 错误处理

如果 DeepSeek API 调用失败，自动回退到规则解析：

```python
# 自动回退
task_params = parse_intent(user_input, use_deepseek=True)

# 手动回退
task_params = parse_intent(user_input, use_deepseek=False)
```

## AutoClaw 集成

### 注册 Skills

```bash
python config/autoclaw_integration.py
```

这会将所有 4 个 Skill 复制到 AutoClaw 工作空间。

### Skill 位置

注册后，Skills 位置：

```
C:\Users\Administrator\.openclaw-autoclaw\skills\
├── healthpath-intent-understanding\
├── healthpath-hospital-crawler\
├── healthpath-decision-engine\
└── healthpath-output-generator\
```

## 典型工作流

### 完整端到端流程

```python
import sys
sys.path.insert(0, '.')

from skills.skill_1_intent.intent_parser import parse_intent
from skills.skill_2_crawl.hospital_crawler import search_available_slots
from skills.skill_3_decision.decision_engine import evaluate_and_rank
from skills.skill_4_output.output_generator import generate_output

# Step 1: 意图理解
user_input = "老人这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。"
task_params = parse_intent(user_input, use_deepseek=True)

# Step 2: 号源搜索
search_result = search_available_slots(task_params)

# Step 3: 方案决策
recommendations = evaluate_and_rank(
    search_result['slots'],
    task_params,
    top_n=2
)

# Step 4: 输出生成
output_result = generate_output(
    recommendations['recommendations'],
    task_params,
    task_params.get('output_format', 'excel')
)

print(f"Generated: {output_result['files']}")
```

## 扩展指南

### 添加新的医院数据源

1. 在 `data/mock/hospitals.json` 中添加医院信息
2. 在 `data/mock/available_slots.json` 中添加号源数据
3. 或在 `skills/skill_2_crawl/hospital_crawler.py` 中添加新的数据源适配器

### 自定义评分算法

编辑 `skills/skill_3_decision/decision_engine.py` 中的 `calculate_score()` 函数：

```python
def calculate_score(slot: Dict, preference: str) -> float:
    # 修改权重
    weights = {"distance": 0.3, "travel_time": 0.2, "cost": 0.3, "queue": 0.2}
    # ...
```

### 自定义输出格式

在 `skills/skill_4_output/` 中添加新的生成器：

- `pdf_generator.py` - PDF 生成
- `excel_generator.py` - Excel 生成
- 可添加：`word_generator.py`、`html_generator.py` 等

## 常见问题

### Q: DeepSeek API 调用失败怎么办？

A: 系统会自动回退到规则解析。检查：

1. API Key 是否正确
2. 网络连接是否正常
3. API 配额是否充足

### Q: 如何添加更多医院？

A: 编辑 `data/mock/hospitals.json` 和 `data/mock/available_slots.json`，或对接真实医院 API。

### Q: 如何修改推荐算法？

A: 编辑 `skills/skill_3_decision/decision_engine.py` 中的评分权重和排序逻辑。

### Q: 如何生成其他格式的输出？

A: 在 `skills/skill_4_output/` 中添加新的生成器模块。

## 性能优化

### 缓存医院数据

```python
# 在 hospital_crawler.py 中添加缓存
import functools

@functools.lru_cache(maxsize=128)
def load_hospitals():
    # ...
```

### 并行搜索多家医院

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(fetch_slots, hospital) for hospital in hospitals]
    results = [f.result() for f in futures]
```

## 部署建议

### 本地部署

```bash
# 安装依赖
pip install requests reportlab openpyxl

# 运行演示
python demo/demo.py
```

### AutoClaw 集成部署

```bash
# 注册 Skills
python config/autoclaw_integration.py

# 启动 AutoClaw
# 在 AutoClaw 中调用 Skill
```

## 联系方式

项目地址：<https://github.com/jiezi1234/Zhishu.git>

有问题或建议，欢迎提交 Issue 或 Pull Request。
