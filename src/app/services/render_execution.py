from __future__ import annotations

import threading
from time import monotonic


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

    def drain(self, *, timeout_seconds: float) -> bool:
        """Wait for in-flight renders to finish by taking every execution slot.

        Called on shutdown so a rolling deploy does not kill a worker mid-render and leave
        its job at 'rendering' (issue #105). The slots are deliberately not released: the
        process is going away, and nothing further may start.

        Returns False if the timeout elapsed with renders still running, which the caller
        reports rather than hides -- those jobs will be recovered by resubmission once
        they go stale.
        """
        deadline = monotonic() + timeout_seconds
        for _ in range(self._concurrency_limit):
            remaining = max(0.0, deadline - monotonic())
            if not self._semaphore.acquire(timeout=remaining):
                return False
        return True
