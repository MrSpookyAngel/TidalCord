import os
from pathlib import Path


class LRUCache:
    def __init__(self, cache_dir: str, max_size: int = 5 * 1024**3):
        self.cache_dir = Path(cache_dir)
        self.max_size = max_size
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_size(self) -> int:
        return sum(f.stat().st_size for f in self.cache_dir.glob("**/*") if f.is_file())

    def evict_if_needed(self):
        while self.get_cache_size() > self.max_size:
            files = list(self.cache_dir.glob("**/*"))
            lru_file = min(files, key=lambda f: f.stat().st_atime) if files else None
            if lru_file:
                lru_file.unlink()

    def add(self, key: str, data_stream: bytes):
        file_path = self.cache_dir / key
        with file_path.open("wb") as f:
            for chunk in data_stream:
                if chunk:
                    f.write(chunk)
        self.evict_if_needed()

    def get(self, key: str) -> Path:
        file_path = self.cache_dir / key
        if file_path.exists():
            os.utime(file_path, None)
            return file_path
        return None
