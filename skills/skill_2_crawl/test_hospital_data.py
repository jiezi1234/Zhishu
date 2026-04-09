"""
测试真实医院数据采集系统
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from hospital_adapter import HospitalDataManager
from cache_manager import get_cache_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_hospital_data_manager():
    """测试医院数据管理器"""
    print("\n" + "="*60)
    print("测试医院数据管理器")
    print("="*60)

    manager = HospitalDataManager()

    # 测试1: 获取医院列表
    print("\n[测试1] 获取医院列表...")
    hospitals = manager.fetch_hospitals("北京")
    print(f"✓ 获取到 {len(hospitals)} 家医院")
    if hospitals:
        print(f"  第一家医院: {hospitals[0].get('hospital_name')}")
        print(f"  数据来源: {hospitals[0].get('source', 'unknown')}")

    # 测试2: 获取号源
    if hospitals:
        print("\n[测试2] 获取号源...")
        hospital_id = hospitals[0].get("hospital_id")
        slots = manager.fetch_available_slots(hospital_id, "骨科", (None, None))
        print(f"✓ 获取到 {len(slots)} 个号源")
        if slots:
            print(f"  第一个号源: {slots[0].get('doctor_name')} - {slots[0].get('appointment_time')}")

    # 测试3: 缓存测试
    print("\n[测试3] 缓存测试...")
    print("  第一次获取医院列表...")
    hospitals1 = manager.fetch_hospitals("北京")
    print(f"  ✓ 获取到 {len(hospitals1)} 家医院")

    print("  第二次获取医院列表（应该从缓存获取）...")
    hospitals2 = manager.fetch_hospitals("北京")
    print(f"  ✓ 获取到 {len(hospitals2)} 家医院")

    # 测试4: 缓存统计
    print("\n[测试4] 缓存统计...")
    cache = get_cache_manager()
    stats = cache.get_cache_stats()
    print(f"  缓存统计: {stats}")

    # 测试5: 可用数据源
    print("\n[测试5] 可用数据源...")
    adapters = manager.get_available_adapters()
    print(f"  可用数据源: {', '.join(adapters)}")

    print("\n" + "="*60)
    print("所有测试完成！")
    print("="*60)


def test_cache_manager():
    """测试缓存管理器"""
    print("\n" + "="*60)
    print("测试缓存管理器")
    print("="*60)

    cache = get_cache_manager()

    # 测试数据
    test_hospitals = [
        {
            "hospital_id": "test_001",
            "hospital_name": "测试医院1",
            "address": "北京市朝阳区",
            "phone": "010-12345678",
            "departments": ["骨科", "内科"],
            "distance_km": 2.5
        }
    ]

    test_slots = [
        {
            "slot_id": "slot_001",
            "hospital_id": "test_001",
            "doctor_name": "李医生",
            "doctor_title": "主任医师",
            "appointment_time": "2026-04-15 09:00",
            "total_cost": 100,
            "queue_estimate_min": 30
        }
    ]

    # 测试1: 缓存医院
    print("\n[测试1] 缓存医院...")
    cache.set_hospitals("北京", test_hospitals)
    retrieved = cache.get_hospitals("北京")
    print(f"✓ 缓存和检索成功: {len(retrieved)} 家医院")

    # 测试2: 缓存号源
    print("\n[测试2] 缓存号源...")
    cache.set_slots("test_001", "骨科", test_slots)
    retrieved = cache.get_slots("test_001", "骨科")
    print(f"✓ 缓存和检索成功: {len(retrieved)} 个号源")

    # 测试3: 缓存统计
    print("\n[测试3] 缓存统计...")
    stats = cache.get_cache_stats()
    print(f"  缓存统计: {stats}")

    print("\n" + "="*60)
    print("缓存测试完成！")
    print("="*60)


if __name__ == "__main__":
    print("\n开始测试真实医院数据采集系统...\n")

    try:
        test_cache_manager()
        test_hospital_data_manager()
        print("\n✓ 所有测试通过！")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
