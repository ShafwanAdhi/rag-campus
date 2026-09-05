from collections import OrderedDict
from threading import Lock
from typing import Any, Hashable, Optional


class LRUCache:
    def __init__(self, max_entries: int = 256):
        self.max_entries = max(max_entries, 1)
        self._items: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Hashable) -> Optional[Any]:
        with self._lock:
            if key not in self._items:
                self.misses += 1
                return None

            value = self._items.pop(key)
            self._items[key] = value
            self.hits += 1
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            if key in self._items:
                self._items.pop(key)

            self._items[key] = value

            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def stats(self) -> dict:
        with self._lock:
            return {
                "entries": len(self._items),
                "max_entries": self.max_entries,
                "hits": self.hits,
                "misses": self.misses,
            }
