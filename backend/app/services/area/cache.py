"""Lightweight TTL cache with persistent disk fallback for district coverage and address queries."""

import json
import logging
import pathlib
import threading
import time
from typing import Any, Dict, Optional, Tuple

from .models import DistrictCoverageItem

logger = logging.getLogger(__name__)

CACHE_FILE_PATH = pathlib.Path(__file__).parent / ".cache_area.json"


class TTLCache:
    """Thread-safe in-memory cache with TTL and optional file-backed persistence."""

    def __init__(
        self,
        default_ttl_seconds: int = 86400,  # 24 hours default TTL
        max_entries: int = 512,
        disk_file: Optional[pathlib.Path] = CACHE_FILE_PATH,
    ):
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries
        self.disk_file = disk_file
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._load_from_disk()

    @staticmethod
    def make_area_key(lat: float, lon: float, radius_m: float, admin_level: str) -> str:
        """Create normalized cache key for district coverage."""
        return f"area:{round(lat, 4)}:{round(lon, 4)}:{radius_m}:{admin_level}"

    @staticmethod
    def make_addr_key(lat: float, lon: float) -> str:
        """Create normalized cache key for reverse-geocoded address."""
        return f"addr:{round(lat, 4)}:{round(lon, 4)}"

    def _load_from_disk(self) -> None:
        """Load unexpired entries from disk."""
        if not self.disk_file or not self.disk_file.exists():
            return
        try:
            with open(self.disk_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            now = time.time()
            for key, entry in raw_data.items():
                expire_at = entry.get("expire_at", 0)
                if expire_at > now:
                    if key.startswith("area:"):
                        items_raw = entry.get("items", [])
                        reconstructed = [DistrictCoverageItem(**item) for item in items_raw]
                    elif key.startswith("addr:"):
                        reconstructed = entry.get("data", {})
                    else:
                        reconstructed = entry.get("data", entry.get("items", []))
                    self._cache[key] = (expire_at, reconstructed)
        except Exception as e:
            logger.debug("Could not load cache from disk: %s", e)

    def _save_to_disk(self) -> None:
        """Persist unexpired cache entries to disk."""
        if not self.disk_file:
            return
        try:
            now = time.time()
            data_to_save = {}
            for key, (exp, items) in self._cache.items():
                if exp > now:
                    if isinstance(items, dict):
                        data_to_save[key] = {"expire_at": exp, "data": items}
                    elif isinstance(items, list):
                        serializable = [
                            it.to_dict() if hasattr(it, "to_dict") else it for it in items
                        ]
                        data_to_save[key] = {"expire_at": exp, "items": serializable}
                    else:
                        data_to_save[key] = {"expire_at": exp, "data": items}
            with open(self.disk_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False)
        except Exception as e:
            logger.debug("Could not save cache to disk: %s", e)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache if not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expire_at, value = entry
            if time.time() > expire_at:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store a value with an expiration timestamp."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expire_at = time.time() + ttl
        with self._lock:
            # Evict oldest entry if size exceeds max_entries
            if len(self._cache) >= self.max_entries and key not in self._cache:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
            self._cache[key] = (expire_at, value)
            self._save_to_disk()

    def clear(self) -> None:
        """Clear all in-memory entries and delete cache file."""
        with self._lock:
            self._cache.clear()
            if self.disk_file and self.disk_file.exists():
                try:
                    self.disk_file.unlink()
                except Exception as e:
                    logger.debug("Could not delete cache file: %s", e)


# Global query cache instance
query_cache = TTLCache()

