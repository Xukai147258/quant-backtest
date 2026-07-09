# automation/executor.py
import asyncio
import logging
import requests
import aiohttp
from automation.config import Config

logger = logging.getLogger(__name__)


class GLMExecutor:
    """GLM API executor with async HTTP (aiohttp), retry, backoff, and fallback."""

    RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, config: Config,
                 max_retries: int = 3,
                 base_delay: float = 2.0,
                 backoff_factor: float = 2.0,
                 fallback_models: list = None,
                 concurrent_limit: int = 10):
        self.config = config
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.fallback_models = fallback_models or []
        self.total_calls = 0
        self.total_errors = 0
        self.concurrent_limit = concurrent_limit
        self._session = None
        self._async_session = None

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            })
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=4, pool_maxsize=8, max_retries=0)
            self._session.mount("https://", adapter)
            self._session.mount("http://", adapter)
        return self._session

    @property
    def async_session(self) -> aiohttp.ClientSession:
        if self._async_session is None or self._async_session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.concurrent_limit,
                limit_per_host=self.concurrent_limit,
                ttl_dns_cache=300,
                force_close=False,
            )
            timeout = aiohttp.ClientTimeout(total=120, connect=10, sock_read=120)
            self._async_session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._async_session

    async def close_async(self):
        if self._async_session and not self._async_session.closed:
            await self._async_session.close()
            self._async_session = None

    def build_messages(self, instruction, context=""):
        parts = []
        if context:
            parts.append(f"Context:\n{context}")
        parts.append(f"Task:\n{instruction}")
        return [{"role": "user", "content": "\n\n".join(parts)}]

    def execute(self, messages, max_tokens=4096, timeout=120):
        return asyncio.run(self.execute_async(messages, max_tokens, timeout))

    async def execute_async(self, messages, max_tokens=4096, timeout=120):
        models_to_try = [self.config.model] + self.fallback_models
        last_error = None
        url = f"{self.config.api_base}/chat/completions"
        payload_template = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.3}

        for model in models_to_try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    self.total_calls += 1
                    payload = {**payload_template, "model": model}

                    async with self.async_session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            return await resp.json()

                        text = await resp.text()

                        if resp.status in self.RETRYABLE_STATUSES:
                            delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
                            logger.warning(
                                f"Retry {attempt}/{self.max_retries} model {model}: "
                                f"HTTP {resp.status}, wait {delay:.1f}s")
                            await asyncio.sleep(delay)
                            last_error = resp.status
                            continue

                        error_msg = f"HTTP {resp.status}: {text[:200]}"
                        logger.error(f"Non-retryable API error: {error_msg}")
                        self.total_errors += 1
                        return {"error": error_msg, "success": False}

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
                    logger.warning(f"Client error attempt {attempt}/{self.max_retries}: {e}, wait {delay:.1f}s")
                    await asyncio.sleep(delay)
                    last_error = str(e)
                    continue

                except Exception as e:
                    self.total_errors += 1
                    logger.error(f"Unexpected error: {e}")
                    return {"error": str(e), "success": False}

            logger.warning(f"All retries exhausted for model {model}")

        err_msg = f"All models failed after retries, last error: {last_error}"
        logger.error(err_msg)
        self.total_errors += 1
        return {"error": err_msg, "success": False}

    def estimate_cost(self, instruction, expected_output_tokens=500):
        input_tokens = len(instruction) // 4
        total_tokens = input_tokens + expected_output_tokens
        return max(1, total_tokens // 1000 + 1)

    def get_stats(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_errors": self.total_errors,
            "error_rate": round(self.total_errors / max(self.total_calls, 1) * 100, 1),
        }
