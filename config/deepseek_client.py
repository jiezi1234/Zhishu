import json
import requests
import os
from typing import Dict, Optional


class Config:
    """Configuration management for HealthPath Agent"""

    # DeepSeek API Configuration
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    @staticmethod
    def get_deepseek_config():
        """Get DeepSeek API configuration"""
        return {
            "api_key": Config.DEEPSEEK_API_KEY,
            "base_url": Config.DEEPSEEK_API_BASE,
            "model": Config.DEEPSEEK_MODEL
        }


class DeepSeekClient:
    """Client for DeepSeek API calls"""

    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.base_url = Config.DEEPSEEK_API_BASE
        self.model = Config.DEEPSEEK_MODEL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def call_api(self, messages: list, temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        """
        Call DeepSeek API with messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Response text or None if error
        """
        try:
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"DeepSeek API Error: {str(e)}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Response parsing error: {str(e)}")
            return None

    def extract_intent(self, user_input: str) -> Optional[Dict]:
        """
        Extract intent from user input using DeepSeek.

        Args:
            user_input: Natural language user request

        Returns:
            Structured intent JSON or None if error
        """

        system_prompt = """You are a medical appointment scheduling assistant.
Extract the following information from user input and return ONLY a valid JSON object (no markdown, no extra text):
{
  "symptom": "the medical symptom or complaint",
  "department": "the medical department (e.g., 骨科, 呼吸科, 心内科, 神经内科, 消化科, 内分泌科)",
  "target_city": "the target city (default: 北京)",
  "time_window": "time preference (this_week, next_week, today, tomorrow, two_days, weekend)",
  "budget": null or maximum acceptable fee in yuan,
  "travel_preference": "nearby, fast, cheap, or balanced",
  "is_remote": true/false if it's a remote appointment,
  "output_format": "large_font_pdf, pdf, or excel",
  "special_requirements": "any special needs like large_font, accessible, medical_insurance"
}

Return ONLY the JSON object, no other text."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]

        response = self.call_api(messages, temperature=0.3, max_tokens=500)

        if not response:
            return None

        try:
            # Clean response - remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            intent = json.loads(response)
            return intent
        except json.JSONDecodeError as e:
            print(f"Failed to parse intent JSON: {str(e)}")
            print(f"Response was: {response}")
            return None


if __name__ == "__main__":
    # Test the client
    client = DeepSeekClient()

    test_inputs = [
        "老人这两天腰疼，帮我找本周可挂上的骨科号，并做一份大字版行程单。",
        "我在南山区上班，只能周末看颈椎，帮我找最近且排队短的医院。",
        "下周从赣州去广州看呼吸科，帮我把挂号、车票、住宿一起规划。"
    ]

    for test_input in test_inputs:
        print(f"\n输入：{test_input}")
        print("-" * 70)
        intent = client.extract_intent(test_input)
        if intent:
            print(json.dumps(intent, ensure_ascii=False, indent=2))
        else:
            print("Failed to extract intent")
