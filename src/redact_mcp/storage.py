"""Mapping storage backends with TTL support and optional Redis integration."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
import importlib
import importlib.util
from typing import Any, Optional
from uuid import UUID

redis_asyncio = importlib.import_module("redis.asyncio") if importlib.util.find_spec("redis.asyncio") else None  # type: ignore[assignment]


__all__ = [
    "BaseMappingStore",
    "InMemoryMappingStore",
    "RedisMappingStore",
]

logger = logging.getLogger("redact_mcp.storage")


class BaseMappingStore(ABC):
    """Abstract mapping store interface."""

    ttl_seconds: Optional[int]

    @abstractmethod
    async def save(self, mapping_id: UUID, mapping: dict[str, str]) -> None:
        ...

    @abstractmethod
    async def get(self, mapping_id: UUID) -> Optional[dict[str, str]]:
        ...

    @abstractmethod
    async def delete(self, mapping_id: UUID) -> bool:
        ...

    async def count(self) -> int:
        raise NotImplementedError

    async def startup(self) -> None:
        """Hook executed during application startup."""

    async def shutdown(self) -> None:
        """Hook executed during application shutdown."""


class InMemoryMappingStore(BaseMappingStore):
    """Async in-memory mapping store with TTL eviction."""

    def __init__(self, ttl_seconds: Optional[int], cleanup_interval_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._cleanup_interval = cleanup_interval_seconds
        self._lock = asyncio.Lock()
        self._store: dict[UUID, tuple[dict[str, str], Optional[float]]] = {}
        self._cleanup_task: Optional[asyncio.Task[None]] = None

    async def save(self, mapping_id: UUID, mapping: dict[str, str]) -> None:
        expire_at = None
        if self.ttl_seconds is not None:
            expire_at = time.monotonic() + self.ttl_seconds
        async with self._lock:
            self._store[mapping_id] = (dict(mapping), expire_at)

    async def get(self, mapping_id: UUID) -> Optional[dict[str, str]]:
        async with self._lock:
            value = self._store.get(mapping_id)
            if value is None:
                return None
            mapping, expire_at = value
            if expire_at is not None and expire_at < time.monotonic():
                self._store.pop(mapping_id, None)
                return None
            return dict(mapping)

    async def delete(self, mapping_id: UUID) -> bool:
        async with self._lock:
            return self._store.pop(mapping_id, None) is not None

    async def count(self) -> int:
        async with self._lock:
            now = time.monotonic()
            return sum(
                1
                for _, (_, expire_at) in self._store.items()
                if expire_at is None or expire_at > now
            )

    async def startup(self) -> None:
        if self._cleanup_task is None and self.ttl_seconds is not None:
            self._cleanup_task = asyncio.create_task(
                self._cleanup_loop(), name="mapping-store-cleanup"
            )

    async def shutdown(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:  # pragma: no cover - expected
                pass
            self._cleanup_task = None
        async with self._lock:
            self._store.clear()

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval)
                await self._evict_expired()
        except asyncio.CancelledError:  # pragma: no cover - expected
            return

    async def _evict_expired(self) -> None:
        if self.ttl_seconds is None:
            return
        async with self._lock:
            now = time.monotonic()
            expired = [
                key
                for key, (_, expire_at) in self._store.items()
                if expire_at is not None and expire_at < now
            ]
            for key in expired:
                self._store.pop(key, None)
            if expired:
                logger.debug(
                    "Evicted expired mappings", extra={"evicted": len(expired)}
                )


class RedisMappingStore(BaseMappingStore):
    """Redis-backed mapping store with optional TTL enforcement."""

    def __init__(
        self,
        redis_client: Any,
        ttl_seconds: Optional[int],
        namespace: str = "redact_mappings",
    ) -> None:
        if redis_asyncio is None:
            raise RuntimeError("redis dependency is not installed")
        self._redis = redis_client
        self.ttl_seconds = ttl_seconds
        self._namespace = namespace

    def _key(self, mapping_id: UUID) -> str:
        return f"{self._namespace}:{mapping_id}"

    async def save(self, mapping_id: UUID, mapping: dict[str, str]) -> None:
        payload = json.dumps(mapping, separators=(",", ":"))
        key = self._key(mapping_id)
        if self.ttl_seconds is None:
            await self._redis.set(key, payload)
        else:
            await self._redis.set(key, payload, ex=self.ttl_seconds)

    async def get(self, mapping_id: UUID) -> Optional[dict[str, str]]:
        key = self._key(mapping_id)
        payload = await self._redis.get(key)
        if payload is None:
            return None
        return json.loads(payload)

    async def delete(self, mapping_id: UUID) -> bool:
        key = self._key(mapping_id)
        deleted = await self._redis.delete(key)
        return deleted > 0

    async def count(self) -> int:
        cursor = 0
        total = 0
        pattern = f"{self._namespace}:*"
        while True:
            cursor, keys = await self._redis.scan(cursor=cursor, match=pattern, count=200)
            total += len(keys)
            if cursor == 0:
                break
        return total

    async def startup(self) -> None:
        await self._redis.ping()

    async def shutdown(self) -> None:
        await self._redis.close()
