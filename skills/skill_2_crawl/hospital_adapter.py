"""
Hospital data adapter framework for fetching real hospital information.
Supports multiple data sources with fallback mechanism.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class HospitalDataAdapter(ABC):
    """Base class for hospital data adapters"""

    def __init__(self, name: str):
        self.name = name
        self.is_available = True

    @abstractmethod
    def fetch_hospitals(self, city: str = "北京") -> List[Dict]:
        """
        Fetch hospital list from data source.

        Returns:
            List of hospital dicts with keys:
            - hospital_id: unique identifier
            - hospital_name: hospital name
            - address: hospital address
            - phone: hospital phone
            - departments: list of departments
            - distance_km: distance from user (if available)
        """
        pass

    @abstractmethod
    def fetch_available_slots(self, hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
        """
        Fetch available appointment slots.

        Args:
            hospital_id: hospital identifier
            department: department name
            date_range: (start_date, end_date) tuple

        Returns:
            List of slot dicts with keys:
            - slot_id: unique identifier
            - hospital_id: hospital identifier
            - doctor_name: doctor name
            - doctor_title: doctor title
            - appointment_time: appointment datetime
            - total_cost: appointment fee
            - queue_estimate_min: estimated queue time
        """
        pass

    def get_hospitals(self, city: str = "北京") -> Optional[List[Dict]]:
        """Wrapper with error handling"""
        try:
            if not self.is_available:
                return None
            return self.fetch_hospitals(city)
        except Exception as e:
            logger.error(f"Error fetching hospitals from {self.name}: {e}")
            self.is_available = False
            return None

    def get_available_slots(self, hospital_id: str, department: str, date_range: tuple) -> Optional[List[Dict]]:
        """Wrapper with error handling"""
        try:
            if not self.is_available:
                return None
            return self.fetch_available_slots(hospital_id, department, date_range)
        except Exception as e:
            logger.error(f"Error fetching slots from {self.name}: {e}")
            self.is_available = False
            return None


class JingYiTongAdapter(HospitalDataAdapter):
    """
    Adapter for 京医通 (Beijing Official Medical Appointment Platform)

    Official government platform with API support.
    Most reliable and stable data source.
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("京医通")
        self.api_key = api_key
        self.base_url = "https://www.bjguahao.gov.cn/api"

        if not api_key:
            logger.warning("京医通 API key not provided, adapter will be unavailable")
            self.is_available = False

    def fetch_hospitals(self, city: str = "北京") -> List[Dict]:
        """Fetch hospitals from 京医通 API"""
        if not self.is_available:
            return []

        # TODO: Implement actual API call
        # This requires official API documentation and credentials
        logger.info("Fetching hospitals from 京医通")
        return []

    def fetch_available_slots(self, hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
        """Fetch available slots from 京医通 API"""
        if not self.is_available:
            return []

        # TODO: Implement actual API call
        logger.info(f"Fetching slots from 京医通 for {hospital_id}/{department}")
        return []


class YiHaoAdapter(HospitalDataAdapter):
    """
    Adapter for 114挂号网 (114 Appointment Platform)

    Largest appointment platform in Beijing.
    Covers most tier-1 and tier-2 hospitals.
    """

    def __init__(self):
        super().__init__("114挂号网")
        self.base_url = "https://www.114ygk.com"
        # Note: 114 doesn't have official API, requires web scraping

    def fetch_hospitals(self, city: str = "北京") -> List[Dict]:
        """Fetch hospitals from 114 platform"""
        # TODO: Implement web scraping with Playwright
        logger.info("Fetching hospitals from 114挂号网")
        return []

    def fetch_available_slots(self, hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
        """Fetch available slots from 114 platform"""
        # TODO: Implement web scraping with Playwright
        logger.info(f"Fetching slots from 114挂号网 for {hospital_id}/{department}")
        return []


class MockDataAdapter(HospitalDataAdapter):
    """
    Fallback adapter using mock data.
    Used when real data sources are unavailable.
    """

    def __init__(self):
        super().__init__("模拟数据")
        self.is_available = True

    def fetch_hospitals(self, city: str = "北京") -> List[Dict]:
        """Return mock hospital data"""
        return [
            {
                "hospital_id": "bxh_001",
                "hospital_name": "北京协和医院",
                "address": "北京市东城区帅府园1号",
                "phone": "010-65296114",
                "departments": ["神经内科", "骨科", "心内科"],
                "distance_km": 2.5
            },
            {
                "hospital_id": "bjdx_001",
                "hospital_name": "北京大学第一医院",
                "address": "北京市西城区西什库街8号",
                "phone": "010-83572211",
                "departments": ["神经内科", "骨科", "呼吸科"],
                "distance_km": 3.2
            },
            {
                "hospital_id": "bjsy_001",
                "hospital_name": "北京市第一中心医院",
                "address": "北京市朝阳区南新园1号",
                "phone": "010-85951122",
                "departments": ["神经内科", "骨科", "消化科"],
                "distance_km": 4.1
            }
        ]

    def fetch_available_slots(self, hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
        """Return mock appointment slots"""
        return [
            {
                "slot_id": "slot_001",
                "hospital_id": hospital_id,
                "doctor_name": "李医生",
                "doctor_title": "主任医师",
                "appointment_time": "2026-04-15 09:00",
                "total_cost": 100,
                "queue_estimate_min": 30
            },
            {
                "slot_id": "slot_002",
                "hospital_id": hospital_id,
                "doctor_name": "王医生",
                "doctor_title": "副主任医师",
                "appointment_time": "2026-04-15 14:00",
                "total_cost": 80,
                "queue_estimate_min": 20
            }
        ]


class HospitalDataManager:
    """
    Manager for multiple hospital data adapters.
    Implements fallback mechanism and caching.
    """

    def __init__(self):
        self.adapters: List[HospitalDataAdapter] = []
        self._init_adapters()

    def _init_adapters(self):
        """Initialize adapters in priority order"""
        # Priority 1: 京医通 (official, most reliable)
        # Note: Requires API key from environment or config
        jyt_adapter = JingYiTongAdapter(api_key=None)  # TODO: Get from config
        if jyt_adapter.is_available:
            self.adapters.append(jyt_adapter)

        # Priority 2: 114挂号网 (largest platform)
        self.adapters.append(YiHaoAdapter())

        # Priority 3: Mock data (fallback)
        self.adapters.append(MockDataAdapter())

    def fetch_hospitals(self, city: str = "北京") -> List[Dict]:
        """
        Fetch hospitals from available adapters.
        Returns data from first successful adapter.
        """
        for adapter in self.adapters:
            hospitals = adapter.get_hospitals(city)
            if hospitals:
                logger.info(f"Successfully fetched hospitals from {adapter.name}")
                return hospitals

        logger.warning("All adapters failed, returning empty list")
        return []

    def fetch_available_slots(self, hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
        """
        Fetch available slots from available adapters.
        Returns data from first successful adapter.
        """
        for adapter in self.adapters:
            slots = adapter.get_available_slots(hospital_id, department, date_range)
            if slots:
                logger.info(f"Successfully fetched slots from {adapter.name}")
                return slots

        logger.warning("All adapters failed, returning empty list")
        return []

    def get_available_adapters(self) -> List[str]:
        """Get list of currently available adapters"""
        return [adapter.name for adapter in self.adapters if adapter.is_available]
