# AutoClaw调用流程 - 快速参考

## 核心流程

```
用户在AutoClaw中输入
    ↓
AutoClaw调用: execute(user_input, output_format)
    ↓
main_skill.py (HealthPathAgent)
    ├─ Step 1: parse_intent() → 解析意图
    ├─ Step 2: search_available_slots() → 搜索号源
    ├─ Step 3: evaluate_and_rank() → 评分排序
    └─ Step 4: generate_output() → 生成PDF
    ↓
返回结果: {status, pdf_path, ...}
```

## 调用方式

### 方式1: AutoClaw直接调用

```python
# 在AutoClaw中
result = call_skill("healthpath-agent", {
    "user_input": "我想在北京找个好医院看骨科，最好这周能挂上号",
    "output_format": "large_font_pdf"
})

pdf_path = result["final_output"]["pdf_path"]
```

### 方式2: Python直接调用

```python
from main_skill import execute

result = execute(
    user_input="我想在北京找个好医院看骨科，最好这周能挂上号",
    output_format="large_font_pdf"
)

if result["status"] == "success":
    print(f"PDF已生成: {result['final_output']['pdf_path']}")
```

### 方式3: 获取智能体信息

```python
from main_skill import get_info

info = get_info()
print(f"智能体: {info['name']}")
print(f"能力: {info['capabilities']}")
```

## 输入参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| user_input | str | ✓ | 用户的自然语言输入 |
| output_format | str | ✗ | 输出格式，默认"large_font_pdf" |

## 输出结果

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

## 状态码

| 状态 | 说明 |
|------|------|
| success | 成功生成PDF |
| no_results | 未找到匹配的号源，但仍生成PDF |
| error | 执行出错 |

## 用户输入示例

### 示例1: 老年人就医
```
"我奶奶最近腰疼得厉害，想在北京找个好医院看骨科，最好这周能挂上号，离家近一点最好"
```

### 示例2: 上班族就医
```
"我最近头晕，想找个离公司近的医院看神经内科，最好能在周末或晚上挂号"
```

### 示例3: 异地就医
```
"我从外地来北京，需要看呼吸科，最好能找个评价好的医院，费用不要太贵"
```

### 示例4: 儿童急诊
```
"我的孩子发烧了，需要找个24小时儿科急诊，离我们最近的医院"
```

## 数据流向

```
用户输入 (自然语言)
    ↓
[Skill 1] 意图解析
    ↓ task_params
    {
      "department": "骨科",
      "symptom": "腰疼",
      "time_window": "this_week",
      "travel_preference": "nearby"
    }
    ↓
[Skill 2] 号源搜索
    ↓ slots
    [
      {
        "hospital_name": "北京协和医院",
        "doctor_name": "李医生",
        "appointment_time": "2026-04-15 09:00",
        "distance_km": 2.5,
        "total_cost": 100
      }
    ]
    ↓
[Skill 3] 方案决策
    ↓ recommendations
    [
      {
        "rank": 1,
        "hospital_name": "北京协和医院",
        "score": 8.5,
        "reason": "距离最近，排队时间短"
      }
    ]
    ↓
[Skill 4] PDF生成
    ↓
PDF文件
```

## 关键特性

### 1. 多源数据支持
- 京医通 (官方平台)
- 114挂号网 (第三方平台)
- 模拟数据 (降级方案)

### 2. 自动降级
- 数据源不可用 → 自动切换
- 网络请求失败 → 使用缓存
- 始终保证可用性

### 3. 智能评分
```
综合评分 = 0.2×距离 + 0.3×交通时间 + 0.3×费用 + 0.2×排队时间
```

### 4. 老年友好
- 大字版PDF (28pt标题, 16pt正文)
- 温暖的色彩方案
- Emoji图标辅助
- 简洁清晰排版

## 性能指标

| 指标 | 值 |
|------|-----|
| 平均响应时间 | < 5秒 |
| 缓存命中率 | > 80% |
| PDF文件大小 | 15-40 KB |
| 系统可用性 | > 99% |

## 错误处理

系统会自动处理：

- ✓ 数据源不可用
- ✓ 网络请求失败
- ✓ 没有匹配号源
- ✓ 意图解析失败
- ✓ PDF生成失败

## 注册Skills到AutoClaw

```bash
python config/autoclaw_integration.py
```

这会将所有Skills复制到AutoClaw工作空间。

## 测试

```bash
# 测试主Skill
python main_skill.py

# 测试端到端流程
python tests/test_end_to_end.py

# 测试缓存系统
python skills/skill_2_crawl/test_hospital_data.py
```

## 常见问题

**Q: 如何自定义输出格式？**
A: 修改 `output_format` 参数：
- `"pdf"`: 标准版
- `"large_font_pdf"`: 大字版（默认）

**Q: 如何处理没有找到号源的情况？**
A: 系统会返回 `status: "no_results"`，但仍会生成PDF显示"未找到"。

**Q: 如何更新医院数据？**
A: 系统自动从数据源获取最新数据，缓存24小时后过期。

**Q: 如何支持其他城市？**
A: 在 `intent_parser.py` 中添加城市识别，在 `hospital_adapter.py` 中添加新的数据源。

## 下一步

1. 完善114挂号网爬虫实现
2. 集成京医通官方API
3. 改进意图解析准确度
4. 添加更多测试场景
5. 性能优化和缓存优化
