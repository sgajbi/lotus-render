import threading
from time import sleep

import pytest

from app.services.render_execution import RenderExecutionLimiter


def test_render_execution_limiter_rejects_when_capacity_is_exhausted() -> None:
    limiter = RenderExecutionLimiter(1)

    assert limiter.concurrency_limit == 1
    assert limiter.acquire() is True
    assert limiter.acquire() is False

    limiter.release()
    assert limiter.acquire() is True
    limiter.release()


def test_render_execution_limiter_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="render_execution_concurrency_limit"):
        RenderExecutionLimiter(0)


def test_drain_waits_for_in_flight_renders_and_then_blocks_new_ones() -> None:
    """Shutdown must let a running render finish rather than kill it mid-compile."""

    limiter = RenderExecutionLimiter(2)
    assert limiter.acquire() is True

    def _finish_shortly() -> None:
        sleep(0.05)
        limiter.release()

    worker = threading.Thread(target=_finish_shortly)
    worker.start()
    try:
        assert limiter.drain(timeout_seconds=5.0) is True
    finally:
        worker.join()

    # Slots are deliberately not released: the process is going away.
    assert limiter.acquire() is False


def test_drain_reports_failure_when_a_render_outlives_the_timeout() -> None:
    """A drain that gave up must say so; those jobs are recovered by resubmission."""

    limiter = RenderExecutionLimiter(1)
    assert limiter.acquire() is True

    assert limiter.drain(timeout_seconds=0.01) is False
