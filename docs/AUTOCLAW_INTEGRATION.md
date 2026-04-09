# AutoClaw集成指南

## 概述

本项目已完全集成到AutoClaw框架中。AutoClaw可以直接调用我们的HealthPath Agent来生成医疗就诊PDF。

## 集成架构

```
AutoClaw (主智能体)
    ↓
HealthPath Agent (main_skill.py)
    ↓
    ├─ Skill 1: 意图解析 (intent_parser.py)
    ├─ Skill 2: 号源搜索 (hospital_crawler.py)
    ├─ Skill 3: 方案决策 (decision_engine.py)
    └─ Skill 4: PDF生成 (output_generator.py)
    ↓
PDF文件输出
```

## 快速开始

### 1. 注册Skills到AutoClaw

```bash
python config/autoclaw_integration.py
```

这会将所有Skills复制到AutoClaw工作空间。

### 2. 在AutoClaw中调用

```python
# 在AutoClaw中
result = call_skill("healthpath-agent", {
    "user_input": "我想在北京找个好医院看骨科，最好这周能挂上号",
    "output_format": "large_font_pdf"
})

# 获取PDF路径
pdf_path = result["final_output"]["pdf_path"]
```

### 3. 直接Python调用

```python
from main_skill import execute

result = execute(
    user_input="我想在北京找个好医院看骨科，最好这周能挂上号",
    output_format="large_font_pdf"
)

print(f"PDF: {result['final_output']['pdf_path']}")
```

## 工作流程详解

### 用户输入示例

```
"我奶奶最近腰疼得厉害，想在北京找个好医院看骨科，最好这周能挂上号，离家近一点最好"
```

### 执行流程

#### Step 1: 意图解析
- 提取关键信息：科室、症状、时间、偏好
- 输出：结构化的任务参数

```json
{
  "department": "骨科",
  "symptom": "腰疼",
  "time_window": "this_week",
  "travel_preference": "nearby"
}
```

#### Step 2: 号源搜索
- 从多个数据源搜索可用号源
- 支持的数据源：京医通、114挂号网、模拟数据
- 输出：可用号源列表

```json
{
  "slots": [
    {
      "hospital_name": "北京协和医院",
      "doctor_name": "李医生",
      "appointment_time": "2026-04-15 09:00",
      "distance_km": 2.5,
      "total_cost": 100
    }
  ]
}
```

#### Step 3: 方案决策
- 基于多个维度评分
- 评分公式：0.2×距离 + 0.3×时间 + 0.3×费用 + 0.2×排队
- 输出：排序后的推荐方案

```json
{
  "recommendations": [
    {
      "rank": 1,
      "hospital_name": "北京协和医院",
      "score": 8.5,
      "reason": "距离最近，排队时间短"
    }
  ]
}
```

#### Step 4: PDF生成
- 生成美观的就医行程单
- 支持大字版（老年友好）
- 包含所有必要信息
- 输出：PDF文件

## 输出示例

生成的PDF包含以下内容：

### 1. 最重要的就诊信息
- 去哪个医院
- 看什么科室
- 看哪位医生
- 什么时间去
- 预计排队时间

### 2. 怎么去医院最方便
- 推荐交通方式
- 交通时间预估
- 综合评分和推荐理由

### 3. 出门前检查清单
- 身份证
- 医保卡
- 手机和充电宝
- 钱包

### 4. 特别提醒
- 提前15分钟到达
- 不知道怎么走可以问工作人员

### 5. 推荐方案详细对比
- 所有候选医院的对比表
- 包含排名、医生、时间、费用、排队、距离、评分

### 6. 交通与距离详情
- 每个方案的具体交通信息
- 建议出发时间

### 7. 就医需求摘要
- 科室、症状、时间要求、出行偏好

## 数据源配置

### 京医通 (官方平台)
- 最可靠的数据源
- 需要API密钥
- 配置文件：`config/config.py`

```python
JINGYI_TONG_API_KEY = "your_api_key_here"
```

### 114挂号网 (第三方平台)
- 覆盖面最广
- 使用Playwright爬虫
- 自动反爬虫对策

### 模拟数据 (降级方案)
- 始终可用
- 用于测试和演示
- 确保系统可用性

## 缓存系统

### 缓存策略
- 医院信息：24小时过期
- 号源信息：1小时过期
- 使用SQLite本地存储

### 缓存管理
```python
from skills.skill_2_crawl.cache_manager import get_cache_manager

cache = get_cache_manager()
stats = cache.get_cache_stats()
print(f"缓存统计: {stats}")

# 清空缓存
cache.clear_all()
```

## 错误处理

系统会自动处理以下情况：

| 情况 | 处理方式 |
|------|--------|
| 数据源不可用 | 自动切换到备选源 |
| 网络请求失败 | 使用缓存数据 |
| 没有匹配号源 | 生成"未找到"提示 |
| 意图解析失败 | 返回错误信息 |

## 性能优化

### 缓存命中率
- 首次请求：0%（需要网络请求）
- 后续请求：> 80%（使用缓存）

### 响应时间
- 缓存命中：< 1秒
- 缓存未命中：3-5秒
- 最大响应时间：30秒

### 并发处理
- 支持多个并发请求
- 自动队列管理
- 线程安全

## 测试

### 运行测试
```bash
# 单元测试
python skills/skill_2_crawl/test_hospital_data.py

# 端到端测试
python tests/test_end_to_end.py

# 主Skill测试
python main_skill.py
```

### 测试场景
1. 老年人就医 - 骨科
2. 上班族就医 - 神经内科
3. 异地就医 - 呼吸科
4. 儿童急诊 - 24小时急诊

## 扩展指南

### 添加新的数据源

1. 在 `hospital_adapter.py` 中创建新的Adapter类
2. 继承 `HospitalDataAdapter` 基类
3. 实现 `fetch_hospitals()` 和 `fetch_available_slots()` 方法
4. 在 `HospitalDataManager._init_adapters()` 中注册

### 添加新的评分维度

1. 在 `decision_engine.py` 中修改 `calculate_score()` 函数
2. 调整权重系数
3. 添加新的规范化函数

### 自定义PDF格式

1. 在 `pdf_generator.py` 中修改样式
2. 调整颜色、字体、排版
3. 添加新的内容部分

## 常见问题

### Q: 如何更新医院数据？
A: 系统会自动从数据源获取最新数据。缓存会在24小时后过期。

### Q: 如何处理反爬虫？
A: 系统已实现User-Agent轮换、随机延迟等对策。

### Q: 如何支持多语言？
A: 在 `intent_parser.py` 中添加语言检测和翻译逻辑。

### Q: 如何集成到移动应用？
A: 通过REST API或WebSocket暴露 `execute()` 函数。

## 许可证

MIT License

## 联系方式

如有问题或建议，请联系开发团队。
