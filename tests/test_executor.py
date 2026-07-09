import pytest
from automation.executor import GLMExecutor
from automation.config import Config


def test_executor_init():
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    assert executor.config.api_key == "test-key"


def test_fallback_models():
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config, fallback_models=["glm-5.1", "glm-4.9"])
    assert len(executor.fallback_models) == 2


def test_build_messages():
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    messages = executor.build_messages("write a sort algorithm", "Python")
    assert len(messages) == 1
    assert "sort" in messages[0]["content"]


def test_estimate_cost():
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    cost = executor.estimate_cost("short text", 500)
    assert cost == 1


def test_get_stats():
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    stats = executor.get_stats()
    assert stats["total_calls"] == 0
    assert stats["error_rate"] == 0.0


def test_max_retries_default():
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    assert executor.max_retries == 3


def test_session_pool():
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    sess = executor.session
    assert sess is not None
    # Same session on second call
    assert executor.session is sess


@pytest.mark.asyncio
async def test_async_session_init():
    from automation.executor import GLMExecutor
    from automation.config import Config
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    sess = executor.async_session
    assert sess is not None
    assert not sess.closed
    await executor.close_async()
    assert executor._async_session is None or executor._async_session.closed

@pytest.mark.asyncio
async def test_async_concurrent_limit():
    from automation.executor import GLMExecutor
    from automation.config import Config
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config, concurrent_limit=5)
    assert executor.concurrent_limit == 5
    await executor.close_async()

@pytest.mark.asyncio
async def test_async_session_reuse():
    from automation.executor import GLMExecutor
    from automation.config import Config
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    s1 = executor.async_session
    s2 = executor.async_session
    assert s1 is s2
    await executor.close_async()

def test_concurrent_limit_default():
    from automation.executor import GLMExecutor
    from automation.config import Config
    config = Config()
    config.api_key = "test-key"
    executor = GLMExecutor(config)
    assert executor.concurrent_limit == 10
