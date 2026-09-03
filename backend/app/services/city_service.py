"""
城市支持服务
从配置文件动态加载城市支持级别与边界，支持分级提示文案。
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Lock
from app.config import settings
from app.observability.logger import default_logger as logger


class CitySupportService:
    def __init__(self):
        self._lock = Lock()
        self._cache: Dict[str, Any] = {}
        self._mtime: float = -1.0

    def _load_if_needed(self):
        path = Path(settings.CITY_CONFIG_PATH)
        if not path.exists():
            logger.warning(f"城市配置文件不存在: {path}")
            self._cache = {"messages": {}, "cities": {}}
            self._mtime = -1.0
            return

        mtime = path.stat().st_mtime
        if mtime == self._mtime and self._cache:
            return

        with self._lock:
            # double check
            mtime = path.stat().st_mtime
            if mtime == self._mtime and self._cache:
                return
            with open(path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
            self._mtime = mtime
            logger.info(f"城市支持配置已重载: {path}")

    def get_city_meta(self, city: str) -> Dict[str, Any]:
        self._load_if_needed()
        cities = self._cache.get("cities", {})
        city_meta = cities.get(city)
        if city_meta:
            return city_meta
        return {
            "level": "unsupported",
            "bounds": None,
            "message": self.get_level_message("unsupported")
        }

    def get_level_message(self, level: str) -> str:
        self._load_if_needed()
        messages = self._cache.get("messages", {})
        return messages.get(level, "当前城市支持信息暂不可用。")

    def get_city_support_info(self, city: str) -> Dict[str, Any]:
        meta = self.get_city_meta(city)
        level = meta.get("level", "unsupported")
        return {
            "city": city,
            "level": level,
            "message": meta.get("message") or self.get_level_message(level),
            "bounds": meta.get("bounds")
        }

    def get_bounds(self, city: str) -> Optional[Dict[str, float]]:
        meta = self.get_city_meta(city)
        bounds = meta.get("bounds")
        if isinstance(bounds, dict):
            return bounds
        return None

    def list_cities(self) -> Dict[str, Any]:
        self._load_if_needed()
        return self._cache.get("cities", {})


city_support_service = CitySupportService()
