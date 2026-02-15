"""Thread-safe in-memory mapping store."""

import threading
from uuid import UUID


class MappingStore:
    """Thread-safe store for redaction mappings."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[UUID, dict[str, str]] = {}

    def save(self, mapping_id: UUID, mapping: dict[str, str]) -> None:
        with self._lock:
            self._store[mapping_id] = mapping

    def get(self, mapping_id: UUID) -> dict[str, str] | None:
        with self._lock:
            return self._store.get(mapping_id)

    def delete(self, mapping_id: UUID) -> bool:
        with self._lock:
            return self._store.pop(mapping_id, None) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._store)


mapping_store = MappingStore()
