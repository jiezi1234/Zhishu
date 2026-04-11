# Zhishu Agent - 全人群智能就医调度与医旅管家

## 项目概述

智枢(Zhishu)是一个基于 AutoClaw 框架的智能就医调度系统，通过自然语言理解和多目标决策，帮助用户快速找到最优的医院挂号方案，并生成完整的就医行程规划。

## 核心特性

- **一句话输入**：用户只需描述就医需求，系统自动完成全流程
- **跨医院比选**：自动搜索多家医院，综合评估距离、时间、费用、排队等因素
- **智能推荐**：基于用户偏好（距离优先/时间优先/费用优先）生成 Top-N 方案
- **多格式输出**：支持大字版 PDF（老年友好）和标准 Excel 表格
- **医旅一体化**：支持异地就医场景，整合交通、住宿等信息

## 项目结构

```
Zhishu-Agent/
├── skills/                    # 4 个核心 Skill
│   ├── skill_1_intent/        # 意图理解与约束抽取
│   ├── skill_2_crawl/         # 跨院号源巡航与标准化
│   ├── skill_3_decision/      # 医旅协同与多目标决策
│   └── skill_4_output/        # 结果生成与触达
├── data/
│   └── mock/                  # 模拟数据（医院库、号源库）
├── tests/
│   └── test_integration.py    # 端到端集成测试
├── output/                    # 生成的输出文件
└── docs/                      # 文档
```

## 快速开始

### 环境要求

- Python 3.9+
- AutoClaw 框架（已配置）
- DeepSeek API Key

### 在 AutoClaw 中使用

#### 1. 安装 Skill

Zhishu Agent 已作为 AutoClaw Skill 注册。Skills 位置：

```
C:\Users\Administrator\.openclaw-autoclaw\skills\
├── healthpath-agent/              # 主智能体
├── healthpath-intent-understanding/
├── healthpath-hospital-crawler/
├── healthpath-decision-engine/
└── healthpath-output-generator/
```

#### 2. 启动 AutoClaw

打开 AutoClaw 桌面应用或网页版（`http://127.0.0.1:18789`）

#### 3. 调用智能体

在 AutoClaw 聊天框中输入就医需求，例如：

```
调用healthpath-agent，我想在北京找个好医院看骨科，最好这周能挂上号。
```

或直接描述需求（AutoClaw 会自动识别）：

```
我奶奶腰疼，想找个医院看骨科，生成一份大字版的就医行程单。
```

#### 4. 获取结果

AutoClaw 会返回：
- 推荐医院方案（Top-2）
- 就医行程单（PDF 或 Excel）
- 交通和时间建议

### 运行集成测试

```bash
cd project
python tests/test_integration.py
```

## 4 个核心 Skill

### Skill 1: 意图理解与约束抽取

**功能**：解析用户自然语言输入，提取结构化参数

**输入**：用户一句话描述

```
"老人这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。"
```

**输出**：结构化任务 JSON

```json
{
  "symptom": "腰疼",
  "department": "骨科",
  "target_city": "北京",
  "time_window": "this_week",
  "output_format": "large_font_pdf",
  "special_requirements": "large_font"
}
```

### Skill 2: 跨院号源巡航与标准化

**功能**：搜索多家医院的可用号源，标准化数据格式

**输入**：结构化任务参数
**输出**：统一格式的号源列表（包含医院、医生、时间、费用、排队预估等）

### Skill 3: 医旅协同与多目标决策

**功能**：基于多个维度评估和排序方案

**评分维度**：

- 距离（权重 20%）
- 交通时间（权重 30%）
- 费用（权重 30%）
- 排队时间（权重 20%）

**输出**：Top-2 推荐方案，包含推荐理由

### Skill 4: 结果生成与触达

**功能**：生成格式化输出文档

**支持格式**：

- 大字版 PDF（16pt+ 字体，高对比度，老年友好）
- 标准 Excel（多 sheet，包含行程、交通、住宿等）

## 典型使用场景

### 场景 A：银发族陪诊

**在 AutoClaw 中输入：**
```
我奶奶这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。
```

**AutoClaw 返回：**
- 推荐医院方案（距离、排队时间、费用综合评分）
- 大字版 PDF 行程单（16pt+ 字体，高对比度）
- 挂号链接和交通建议

### 场景 B：职场人夜间/周末就医

**在 AutoClaw 中输入：**
```
我在南山区上班，只能周末看颈椎，帮我找最近且排队短的医院。
```

**AutoClaw 返回：**
- 距离与时长最优方案
- 周末可挂号的医生列表
- 交通路线和预计时间

### 场景 C：异地医旅一体化

**在 AutoClaw 中输入：**
```
下周从赣州去广州看呼吸科，帮我把挂号、车票、住宿一起规划。
```

**AutoClaw 返回：**
- 一体化医旅路书 Excel
- 推荐医院和医生
- 交通方案和住宿建议
- 行程提醒

## 运行演示

python demo/demo.py

## 运行测试

python tests/test_integration.py

## 注册 AutoClaw Skills
  
python config/autoclaw_integration.py

## AutoClaw 配置说明

### 配置文件位置

```
C:\Users\Administrator\.openclaw-autoclaw\openclaw.json
```

### 关键配置

```json
{
  "skills": {
    "allowBundled": [
      "healthpath-agent",
      "healthpath-intent-understanding",
      "healthpath-hospital-crawler",
      "healthpath-decision-engine",
      "healthpath-output-generator"
    ]
  },
  "tools": {
    "fs": {
      "workspaceOnly": false
    }
  }
}
```

- `allowBundled`：允许加载的 Skill 列表
- `workspaceOnly: false`：允许 Agent 访问工作区外的文件（包括 Skills 目录）

### 故障排查

**问题：AutoClaw 说"healthpath-agent 不可用"**

解决方案：
1. 确认 `openclaw.json` 中 `allowBundled` 包含 `healthpath-agent`
2. 确认 `workspaceOnly` 设置为 `false`
3. 重启 AutoClaw 应用
4. 检查 Gateway 日志：`~/.openclaw-autoclaw/logs/gateway.log`

## 查看使用指南

cat docs/USAGE_GUIDE.md

## 数据源

### 模拟数据（当前）

- `data/mock/hospitals.json`：北京海淀地区 5 家医院信息
- `data/mock/available_slots.json`：各医院各科室的可用号源

### 真实数据（后期）

- 医院官方 API
- 第三方挂号平台
- 网页爬取（Selenium/Playwright）

## 开发路线图

**第 1 阶段（完成）**：项目框架搭建 + 模拟数据验证
**第 2 阶段**：真实医院数据对接
**第 3 阶段**：演示脚本固化 + 文档完善
**第 4 阶段**：答辩准备

## 技术栈

- **框架**：AutoClaw（智能体执行框架）
- **LLM**：DeepSeek API（意图理解）
- **数据处理**：Python + JSON
- **文档生成**：reportlab（PDF）、openpyxl（Excel）

## 合规与安全

- 本项目仅提供就医信息调度、流程辅助与行程规划
- 不进行医疗诊断，不替代医生判断
- 隐私信息采用最小化采集原则
- 敏感信息提交由用户本人完成

## 下一步

1. 对接真实医院数据源
2. 完善 PDF/Excel 生成逻辑
3. 集成 DeepSeek API 进行真实意图理解
4. 准备演示视频和答辩文档

## 联系方式

项目地址：<https://github.com/jiezi1234/Zhishu.git>
