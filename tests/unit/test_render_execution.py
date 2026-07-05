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
