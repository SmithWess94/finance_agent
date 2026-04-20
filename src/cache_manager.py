import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

class CacheManager:
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "responses.json"
        self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
        else:
            self.cache = {}

    def _save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _get_key(self, message: str) -> str:
        return hashlib.md5(message.encode()).hexdigest()

    def get(self, message: str) -> Optional[str]:
        key = self._get_key(message)
        if key in self.cache:
            entry = self.cache[key]
            # Проверяем, не устаревает ли кэш (30 дней)
            cached_time = datetime.fromisoformat(entry['timestamp'])
            if datetime.now() - cached_time < timedelta(days=30):
                entry['hits'] += 1
                self._save_cache()
                return entry['answer']
            else:
                del self.cache[key]
                self._save_cache()
        return None

    def set(self, message: str, answer: str):
        key = self._get_key(message)
        self.cache[key] = {
            'question': message,
            'answer': answer,
            'timestamp': datetime.now().isoformat(),
            'hits': 1
        }
        self._save_cache()

    def get_stats(self) -> dict:
        total = len(self.cache)
        total_hits = sum(entry.get('hits', 1) for entry in self.cache.values())
        return {
            'total_cached': total,
            'total_hits': total_hits,
            'cache_efficiency': total_hits / (total + 1) if total > 0 else 0
        }
