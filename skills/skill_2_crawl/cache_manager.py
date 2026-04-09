"""
缓存管理器 - 缓存医院和号源信息，减少网络请求
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """使用SQLite的缓存管理器"""

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "cache"
            )

        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        self.db_path = os.path.join(cache_dir, "hospital_cache.db")
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 医院缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospitals (
                    id TEXT PRIMARY KEY,
                    city TEXT,
                    data TEXT,
                    created_at TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)

            # 号源缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS slots (
                    id TEXT PRIMARY KEY,
                    hospital_id TEXT,
                    department TEXT,
                    data TEXT,
                    created_at TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)

            conn.commit()
            conn.close()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def get_hospitals(self, city: str) -> Optional[List[Dict]]:
        """获取缓存的医院列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM hospitals
                WHERE city = ? AND expires_at > ?
                LIMIT 1
            """, (city, datetime.now().isoformat()))

            result = cursor.fetchone()
            conn.close()

            if result:
                logger.info(f"Cache hit for hospitals in {city}")
                return json.loads(result[0])
            else:
                logger.info(f"Cache miss for hospitals in {city}")
                return None

        except Exception as e:
            logger.error(f"Error getting hospitals from cache: {e}")
            return None

    def set_hospitals(self, city: str, hospitals: List[Dict], ttl_hours: int = 24):
        """缓存医院列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cache_id = f"hospitals_{city}"
            now = datetime.now()
            expires_at = now + timedelta(hours=ttl_hours)

            cursor.execute("""
                INSERT OR REPLACE INTO hospitals (id, city, data, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (cache_id, city, json.dumps(hospitals), now.isoformat(), expires_at.isoformat()))

            conn.commit()
            conn.close()
            logger.info(f"Cached {len(hospitals)} hospitals for {city}")

        except Exception as e:
            logger.error(f"Error caching hospitals: {e}")

    def get_slots(self, hospital_id: str, department: str) -> Optional[List[Dict]]:
        """获取缓存的号源"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM slots
                WHERE hospital_id = ? AND department = ? AND expires_at > ?
                LIMIT 1
            """, (hospital_id, department, datetime.now().isoformat()))

            result = cursor.fetchone()
            conn.close()

            if result:
                logger.info(f"Cache hit for slots in {hospital_id}/{department}")
                return json.loads(result[0])
            else:
                logger.info(f"Cache miss for slots in {hospital_id}/{department}")
                return None

        except Exception as e:
            logger.error(f"Error getting slots from cache: {e}")
            return None

    def set_slots(self, hospital_id: str, department: str, slots: List[Dict], ttl_hours: int = 1):
        """缓存号源"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cache_id = f"slots_{hospital_id}_{department}"
            now = datetime.now()
            expires_at = now + timedelta(hours=ttl_hours)

            cursor.execute("""
                INSERT OR REPLACE INTO slots (id, hospital_id, department, data, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cache_id, hospital_id, department, json.dumps(slots), now.isoformat(), expires_at.isoformat()))

            conn.commit()
            conn.close()
            logger.info(f"Cached {len(slots)} slots for {hospital_id}/{department}")

        except Exception as e:
            logger.error(f"Error caching slots: {e}")

    def clear_expired(self):
        """清理过期缓存"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            cursor.execute("DELETE FROM hospitals WHERE expires_at < ?", (now,))
            cursor.execute("DELETE FROM slots WHERE expires_at < ?", (now,))

            conn.commit()
            deleted = cursor.rowcount
            conn.close()

            logger.info(f"Cleared {deleted} expired cache entries")

        except Exception as e:
            logger.error(f"Error clearing expired cache: {e}")

    def clear_all(self):
        """清空所有缓存"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM hospitals")
            cursor.execute("DELETE FROM slots")

            conn.commit()
            conn.close()
            logger.info("Cleared all cache")

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM hospitals")
            hospital_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM slots")
            slot_count = cursor.fetchone()[0]

            conn.close()

            return {
                "hospitals": hospital_count,
                "slots": slot_count,
                "total": hospital_count + slot_count
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# 全局缓存实例
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
