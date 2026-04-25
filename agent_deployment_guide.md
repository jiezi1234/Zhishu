# 智枢 HealthPath Agent 部署指南（给 Agent）

本文档面向接手部署任务的 agent。目标是：在一台新机器上把本项目部署为可运行的 AutoClaw skill，并能完成最小验证。

## 1. 项目定位

- 项目类型：Python AutoClaw skill 集合
- 主 skill：`healthpath-agent`
- 主入口：`main_skill.execute`
- 信息入口：`main_skill.get_info`
- 子 skill：
  - `healthpath-intent-understanding`
  - `healthpath-symptom-triage`
  - `healthpath-hospital-matcher`
  - `healthpath-registration-fetcher`
  - `healthpath-itinerary-builder`
  - `baidu-ai-map`（底层地图能力说明）

主流程是 5 步：意图理解、症状分诊、医院匹配、挂号链接、路线规划与 PDF 生成。`main_skill.py` 会把 5 个子 skill 的目录插入 `sys.path` 后直接导入对应模块。

## 2. 依赖统计

### 2.1 Python 与系统依赖

- Python：项目声明 `Python 3.9+`。部署建议优先使用 Python 3.10-3.12；当前工作区曾在 Python 3.13.12 下检查过，但部分 ML 依赖在 3.13 上可能更挑 wheel。
- 操作系统：Windows 友好；PDF 中文字体优先使用 `C:\Windows\Fonts\simhei.ttf`、`msyh.ttc`、`simsun.ttc`。Linux/macOS 也可运行，但如无中文字体，PDF 生成会降级为文本内容写入目标文件。
- 可选命令：`curl`，主要给 `baidu-ai-map` 文档和手动 API 验证使用。

### 2.2 运行时依赖（来自 requirements.txt）

必须安装：

```text
requests>=2.31.0
python-dotenv>=1.0.0
sentence-transformers>=3.0.0
numpy>=1.24.0
reportlab>=4.0.0
openpyxl>=3.1.0
```

可选增强：

```text
selenium>=4.0.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

开发/验证：

```text
pytest>=7.0.0
black>=23.0.0
flake8>=6.0.0
mypy>=1.0.0
```

### 2.3 爬虫/数据采集依赖（来自 requirements-crawler.txt）

```text
playwright>=1.40.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
requests>=2.31.0
```

仅在执行网页采集或爬虫脚本时需要；普通本地演示和 PDF 生成不强制需要 Playwright。

### 2.4 实际代码导入的第三方包

- `requests`：DeepSeek、百度地图 Agent Plan、医院搜索
- `python-dotenv`：读取 `.env`
- `sentence_transformers`、`numpy`：症状/意图语义匹配
- `reportlab`：PDF 生成
- `openpyxl`：requirements 声明，当前主链路未直接使用，保留给 Excel 输出扩展
- `beautifulsoup4`、`lxml`、`selenium`、`playwright`：采集/解析增强链路
- `pytest`：测试

### 2.5 本仓库自带的 `lib/` 目录

`lib/` 内有部分 vendored 包：`requests 2.33.1`、`reportlab 4.4.10`、`openpyxl 3.1.5`、`lxml 6.0.2`、`beautifulsoup4 4.14.3`、`pillow 12.2.0` 等。

注意：不要把 `lib/` 当成完整虚拟环境。它不包含 `sentence-transformers`、`torch`、`transformers` 等语义模型依赖。标准部署仍应使用 `pip install -r requirements.txt`。

## 3. 环境变量

复制 `.env.example` 为 `.env`，按需填写：

```powershell
Copy-Item .env.example .env
```

核心变量：

```text
BAIDU_MAP_AUTH_TOKEN=
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
OUTPUT_DIR=output
AUTOCLAW_WORKSPACE=C:\Users\Administrator\.openclaw-autoclaw
HF_ENDPOINT=https://hf-mirror.com
ST_MODEL=BAAI/bge-small-zh-v1.5
```

部署判断：

- 没有 `BAIDU_MAP_AUTH_TOKEN`：医院匹配和路线规划会降级，本地数据主要覆盖北京，路线为估算。
- 没有 `DEEPSEEK_API_KEY`：`parse_intent(..., use_deepseek=True)` 会请求失败后降级到本地语义/规则解析；可运行，但第一次本地语义解析需要加载/下载 sentence-transformers 模型。
- 没有 HuggingFace 模型缓存：首次语义匹配会下载 `BAAI/bge-small-zh-v1.5`。国内环境建议保留 `HF_ENDPOINT=https://hf-mirror.com`。

不要把真实 token 写进文档、提交记录或聊天输出。展示时只显示前 4 位加 `****`。

## 4. 部署步骤

### 4.1 准备代码

```powershell
git clone <repo-url> Zhishu
Set-Location Zhishu
```

如果是已经解压的代码包，直接进入项目根目录即可。根目录必须包含：

```text
main_skill.py
_meta.json
requirements.txt
skills/
config/
data/
```

### 4.2 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Linux/macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 4.3 安装依赖

普通运行：

```powershell
python -m pip install -r requirements.txt
```

说明：`requirements.txt` 已包含 `reportlab>=4.0.0`，正常执行上面的命令即可安装 PDF 生成依赖。

需要爬虫/网页采集能力：

```powershell
python -m pip install -r requirements-crawler.txt
python -m playwright install
```

如果所在环境网络受限，先准备 Python wheel 缓存或配置内部 PyPI 镜像；不要绕过审批去下载未知脚本。

### 4.4 配置 `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

至少建议配置：

```text
OUTPUT_DIR=output
HF_ENDPOINT=https://hf-mirror.com
```

需要全国医院检索和真实路线时，配置：

```text
BAIDU_MAP_AUTH_TOKEN=<your-token>
```

需要 DeepSeek 意图解析时，配置：

```text
DEEPSEEK_API_KEY=<your-key>
```

### 4.5 注册到 AutoClaw

部署有两层：主 skill 和子 skill。

1. 主 skill `healthpath-agent`

   把项目根目录作为 `healthpath-agent` skill 放入 AutoClaw skills 目录，或使用 AutoClaw 的 bundled skill 机制加载项目根目录。主 skill 的元数据在根目录 `_meta.json`，入口是 `main_skill.execute`。

   典型目标结构：

   ```text
   <AUTOCLAW_WORKSPACE>/skills/healthpath-agent/
     main_skill.py
     _meta.json
     SKILL.md
     skills/
     config/
     data/
     requirements.txt
   ```

2. 子 skill

   项目提供了注册脚本：

   ```powershell
   python config/autoclaw_integration.py
   ```

   该脚本会把 5 个子 skill 的 `SKILL.md`、`_meta.json`、`.py`、`.json` 复制到：

   ```text
   <AUTOCLAW_WORKSPACE>/skills/
   ```

   注意：这个脚本只注册子 skill，不会完整复制根目录主 skill。不要误以为执行它之后 `healthpath-agent` 就一定可用。

3. AutoClaw 配置

   确保平台允许加载：

   ```json
   {
     "skills": {
       "allowBundled": [
         "healthpath-agent",
         "healthpath-intent-understanding",
         "healthpath-symptom-triage",
         "healthpath-hospital-matcher",
         "healthpath-registration-fetcher",
         "healthpath-itinerary-builder",
         "baidu-ai-map"
       ]
     }
   }
   ```

## 5. 验证步骤

### 5.1 基础导入验证

```powershell
python -c "from main_skill import get_info; print(get_info())"
```

预期：输出包含 `HealthPath Agent` 和 5 个 healthpath 子 skill 名称。

### 5.2 本地意图解析验证（不依赖 DeepSeek）

```powershell
python -c "import sys, os; sys.path.insert(0, os.path.join(os.getcwd(), 'skills', 'healthpath-intent-understanding')); from intent_parser import parse_intent; print(parse_intent('最近腰疼，想看骨科，做大字版行程单', use_deepseek=False))"
```

预期：返回 dict，包含 `department`、`output_format`、`timestamp` 等字段。首次执行可能加载或下载语义模型，耗时较长。

### 5.3 主流程分阶段验证

缺少地址时：

```powershell
python -c "from main_skill import execute; print(execute(user_input='最近头晕，想看医生')['status'])"
```

预期：`need_location`、`need_more_info` 或急症相关状态。

医院候选阶段：

```powershell
python -c "from main_skill import execute; r=execute(user_input='最近腰疼，想看骨科', user_location='北京市海淀区'); print(r['status']); print(r.get('final_output'))"
```

预期：通常为 `awaiting_hospital_selection`，并返回候选医院。

完整 PDF 阶段：

```powershell
python -c "from main_skill import execute; r=execute(user_input='最近腰疼，想看骨科', user_location='北京市海淀区', selected_hospital='北京大学第三医院', output_format='pdf'); print(r['status']); print(r.get('final_output'))"
```

预期：`success`，`final_output.pdf_path` 指向生成文件。

### 5.4 测试套件

```powershell
python -m pytest tests/test_integration.py -q
```

注意：

- 测试会生成 `_generated_test/` 输出。
- 语义模型未缓存时，测试可能触发模型下载。
- 没有 `BAIDU_MAP_AUTH_TOKEN` 时路线应降级为估算，相关测试会删除该 env 来验证降级路径。

## 6. 数据与输出目录

输入数据：

- `skills/healthpath-symptom-triage/yixue_knowledge.json`：症状知识库、归一化、科室映射
- `skills/healthpath-hospital-matcher/hospitals.json`：本地医院库
- `data/医疗机构基本信息2023-03-29.csv`：本地 CSV 降级数据
- `skills/healthpath-registration-fetcher/hospital_info.json`：医院官网/挂号链接缓存

运行输出：

- `output/`：默认 PDF 输出目录
- `_generated_test/`：测试输出目录
- `skills/healthpath-itinerary-builder/user_history.json`：就医历史缓存
- `skills/healthpath-hospital-matcher/blacklist.json`：运行时可能创建的医院黑名单

如果部署环境不允许写入项目目录，设置：

```text
OUTPUT_DIR=<writable-output-dir>
```

并确认 AutoClaw 运行用户对该目录有写权限。

## 7. 常见故障与处理

### 7.1 `ModuleNotFoundError: intent_parser` 或其他子模块

确认从项目根目录运行，或主 skill 包含完整 `skills/` 子目录。`main_skill.py` 依赖相对项目根目录注入子 skill 路径。

### 7.2 `ModuleNotFoundError: sentence_transformers`

安装运行时依赖：

```powershell
python -m pip install -r requirements.txt
```

不要只依赖仓库自带 `lib/`，其中没有完整 ML 依赖。

### 7.3 首次运行卡在模型加载

这是 `BAAI/bge-small-zh-v1.5` 首次下载/初始化。处理方式：

- 配置 `HF_ENDPOINT=https://hf-mirror.com`
- 预先在联网环境运行一次本地意图解析
- 或把 HuggingFace 缓存目录随部署包一起迁移，并设置 `HF_HOME`

### 7.4 PDF 不是正常 PDF 或中文乱码

检查：

- 是否安装 `reportlab`
- 可先运行 `python -c "import reportlab; print(reportlab.Version)"` 验证当前解释器下确实可导入
- Windows 字体是否存在：`simhei.ttf`、`msyh.ttc` 或 `simsun.ttc`
- 非 Windows 环境需要补充中文字体支持，或修改 `pdf_generator.register_chinese_fonts()` 增加字体路径

### 7.5 AutoClaw 找不到 `healthpath-agent`

只运行 `python config/autoclaw_integration.py` 不够。该脚本只复制 5 个子 skill。必须把项目根目录作为主 skill `healthpath-agent` 安装/加载，并确保 `_meta.json` 可被 AutoClaw 读取。

### 7.6 医院候选为空

检查：

- 用户位置是否明确到城市/区
- 没有百度 token 时，本地降级数据主要面向北京
- `skills/healthpath-hospital-matcher/hospitals.json` 是否存在
- `preferences.max_distance_km` 是否过小

### 7.7 挂号链接为空

逻辑会先查 `hospital_info.json` 缓存，再访问 yixue.com，再尝试搜索/域名猜测。离线环境下只能依赖缓存。部署给演示环境时，应提前补齐重点医院缓存。

## 8. Agent 部署执行清单

1. 确认 Python 版本和虚拟环境。
2. 安装 `requirements.txt`；如需采集再安装 `requirements-crawler.txt` 和 Playwright 浏览器。
3. 创建 `.env`，配置 `OUTPUT_DIR`、`HF_ENDPOINT`，按需求配置百度和 DeepSeek token。
4. 预热语义模型：运行一次 `parse_intent(..., use_deepseek=False)`。
5. 把项目根目录注册/复制为 AutoClaw 主 skill `healthpath-agent`。
6. 运行 `python config/autoclaw_integration.py` 注册 5 个子 skill。
7. 检查 AutoClaw 配置允许加载主 skill 和子 skill。
8. 运行 `get_info`、缺地址流程、候选医院流程、完整 PDF 流程四项验证。
9. 记录生成的 PDF 路径、使用的数据源、是否走了百度地图/本地降级。
10. 如部署失败，先看模块导入、env、模型缓存、写权限，再看外部 API token。

## 9. 最小可运行判定

满足以下条件即可认为部署成功：

- `from main_skill import get_info` 成功
- `execute(user_input=..., user_location=...)` 能返回医院候选或明确追问
- 传入 `selected_hospital` 后状态为 `success`
- `final_output.pdf_path` 对应文件存在且大小大于 0
- 没有百度 token 时能明确显示/记录降级路线；有百度 token 时能返回真实路线来源
