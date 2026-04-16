import os
from dotenv import load_dotenv

# 从项目根目录的 .env 文件加载环境变量
# 复制 .env.example 为 .env 并按需填写
load_dotenv()


class Config:
    """HealthPath Agent 运行配置"""

    # AutoClaw 工作区路径
    AUTOCLAW_WORKSPACE = os.getenv(
        "AUTOCLAW_WORKSPACE",
        r"C:\Users\Administrator\.openclaw-autoclaw"
    )

    # 百度地图 Agent Plan Token（有则启用全国医院搜索 + 精确路线；无则降级到本地北京数据）
    # 申请地址：https://lbs.baidu.com/apiconsole/agentplan
    BAIDU_MAP_AUTH_TOKEN = os.getenv("BAIDU_MAP_AUTH_TOKEN", "")

    # 项目路径
    BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    OUTPUT_DIR    = os.getenv("OUTPUT_DIR", os.path.join(BASE_DIR, "output"))
    MOCK_DATA_DIR = os.path.join(BASE_DIR, "data", "mock")

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
