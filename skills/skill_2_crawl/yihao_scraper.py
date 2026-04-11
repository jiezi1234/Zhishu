"""
114挂号网爬虫实现
使用Playwright进行浏览器自动化，BeautifulSoup解析HTML
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import random
import time

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)


class YiHaoWebScraper:
    """114挂号网网页爬虫"""

    def __init__(self):
        self.base_url = "https://www.114ygk.com"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def init_browser(self):
        """初始化浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available")
            return False

        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()

            # 设置随机User-Agent
            await self.page.set_extra_http_headers({
                "User-Agent": random.choice(self.user_agents)
            })

            logger.info("Browser initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False

    async def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")

    async def fetch_hospitals(self, city: str = "北京") -> List[Dict]:
        """
        从114挂号网获取医院列表

        Args:
            city: 城市名称

        Returns:
            医院列表
        """
        if not await self.init_browser():
            return []

        try:
            # 访问114挂号网
            logger.info(f"Fetching hospitals from 114 for {city}")
            await self.page.goto(f"{self.base_url}/", wait_until="networkidle")

            # 随机延迟，避免被检测为爬虫
            await asyncio.sleep(random.uniform(1, 3))

            # 获取页面内容
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # 解析医院列表（这里需要根据实际网页结构调整）
            hospitals = self._parse_hospitals(soup, city)

            logger.info(f"Found {len(hospitals)} hospitals")
            return hospitals

        except Exception as e:
            logger.error(f"Error fetching hospitals: {e}")
            return []
        finally:
            await self.close_browser()

    async def fetch_available_slots(self, hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
        """
        从114挂号网获取可用号源

        Args:
            hospital_id: 医院ID
            department: 科室名称
            date_range: 日期范围 (start_date, end_date)

        Returns:
            可用号源列表
        """
        if not await self.init_browser():
            return []

        try:
            logger.info(f"Fetching slots for {hospital_id}/{department}")

            # 访问医院详情页
            hospital_url = f"{self.base_url}/yiyuan/{hospital_id}/"
            await self.page.goto(hospital_url, wait_until="networkidle")

            # 随机延迟
            await asyncio.sleep(random.uniform(1, 3))

            # 获取页面内容
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # 解析号源信息
            slots = self._parse_slots(soup, hospital_id, department, date_range)

            logger.info(f"Found {len(slots)} available slots")
            return slots

        except Exception as e:
            logger.error(f"Error fetching slots: {e}")
            return []
        finally:
            await self.close_browser()

    def _parse_hospitals(self, soup: BeautifulSoup, city: str) -> List[Dict]:
        """
        解析医院列表HTML

        注意：这是一个模板实现，需要根据实际网页结构调整选择器
        """
        hospitals = []

        try:
            # 这里需要根据114挂号网的实际HTML结构调整
            # 示例选择器（需要实际测试）
            hospital_items = soup.find_all('div', class_='hospital-item')

            for item in hospital_items:
                try:
                    # 提取医院信息
                    name_elem = item.find('h3', class_='hospital-name')
                    id_elem = item.find('a', class_='hospital-link')
                    address_elem = item.find('p', class_='hospital-address')

                    if name_elem and id_elem:
                        hospital = {
                            "hospital_id": id_elem.get('data-id', ''),
                            "hospital_name": name_elem.get_text(strip=True),
                            "address": address_elem.get_text(strip=True) if address_elem else "",
                            "phone": "",  # 需要从详情页获取
                            "departments": [],  # 需要从详情页获取
                            "distance_km": 0,  # 需要根据用户位置计算
                            "source": "114挂号网"
                        }
                        hospitals.append(hospital)
                except Exception as e:
                    logger.warning(f"Error parsing hospital item: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing hospitals: {e}")

        return hospitals

    def _parse_slots(self, soup: BeautifulSoup, hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
        """
        解析号源信息HTML

        注意：这是一个模板实现，需要根据实际网页结构调整选择器
        """
        slots = []

        try:
            # 这里需要根据114挂号网的实际HTML结构调整
            # 示例选择器（需要实际测试）
            slot_items = soup.find_all('div', class_='slot-item')

            for item in slot_items:
                try:
                    # 提取号源信息
                    doctor_elem = item.find('span', class_='doctor-name')
                    time_elem = item.find('span', class_='appointment-time')
                    fee_elem = item.find('span', class_='fee')

                    if doctor_elem and time_elem:
                        slot = {
                            "slot_id": f"{hospital_id}_{int(time.time())}",
                            "hospital_id": hospital_id,
                            "doctor_name": doctor_elem.get_text(strip=True),
                            "doctor_title": "医生",  # 需要从详情页获取
                            "appointment_time": time_elem.get_text(strip=True),
                            "total_cost": int(fee_elem.get_text(strip=True).replace('元', '')) if fee_elem else 0,
                            "queue_estimate_min": 30,  # 需要从页面获取
                            "source": "114挂号网"
                        }
                        slots.append(slot)
                except Exception as e:
                    logger.warning(f"Error parsing slot item: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing slots: {e}")

        return slots


# 同步包装函数
def fetch_hospitals_sync(city: str = "北京") -> List[Dict]:
    """同步获取医院列表"""
    scraper = YiHaoWebScraper()
    try:
        return asyncio.run(scraper.fetch_hospitals(city))
    except Exception as e:
        logger.error(f"Error in fetch_hospitals_sync: {e}")
        return []


def fetch_slots_sync(hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
    """同步获取号源"""
    scraper = YiHaoWebScraper()
    try:
        return asyncio.run(scraper.fetch_available_slots(hospital_id, department, date_range))
    except Exception as e:
        logger.error(f"Error in fetch_slots_sync: {e}")
        return []


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    # 测试获取医院列表
    print("Testing hospital fetching...")
    hospitals = fetch_hospitals_sync("北京")
    print(f"Found {len(hospitals)} hospitals")

    # 测试获取号源
    if hospitals:
        hospital_id = hospitals[0].get("hospital_id")
        print(f"\nTesting slot fetching for {hospital_id}...")
        slots = fetch_slots_sync(hospital_id, "骨科", (None, None))
        print(f"Found {len(slots)} slots")
