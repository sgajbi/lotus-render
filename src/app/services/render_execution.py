from __future__ import annotations

import threading


class RenderExecutionLimiter:
    def __init__(self, concurrency_limit: int) -> None:
        if concurrency_limit < 1:
            raise ValueError("render_execution_concurrency_limit must be positive")
        self._concurrency_limit = concurrency_limit
        self._semaphore = threading.BoundedSemaphore(concurrency_limit)

    @property
    def concurrency_limit(self) -> int:
        return self._concurrency_limit

    def acquire(self) -> bool:
        return self._semaphore.acquire(blocking=False)

    def release(self) -> None:
        self._semaphore.release()
