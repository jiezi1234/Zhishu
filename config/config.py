import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration management for HealthPath Agent"""

    # DeepSeek API Configuration
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-cef4d7205b2e4ba29f8052f52e192c80")
    DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # AutoClaw Configuration
    AUTOCLAW_WORKSPACE = os.getenv("AUTOCLAW_WORKSPACE", "C:\\Users\\Administrator\\.openclaw-autoclaw")

    # Data paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MOCK_DATA_DIR = os.path.join(BASE_DIR, "data", "mock")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    @staticmethod
    def get_deepseek_config():
        """Get DeepSeek API configuration"""
        return {
            "api_key": Config.DEEPSEEK_API_KEY,
            "base_url": Config.DEEPSEEK_API_BASE,
            "model": Config.DEEPSEEK_MODEL
        }
