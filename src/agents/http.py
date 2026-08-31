"""OpenAI 兼容端点。"""

from __future__ import annotations

import httpx

from src.agents.provider import LLMProvider, MockLLMProvider


class OpenAICompatProvider(LLMProvider):
    def __init__(self, base_url: str, model: str, api_key: str, max_retries: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=120)

    def chat(self, messages: list[dict], temperature: float = 0.6, max_tokens: int = 800) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_err: Exception | None = None
        for _ in range(self.max_retries):
            try:
                resp = self._client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                last_err = e
        raise RuntimeError(f"顾问调用失败: {last_err}")

    def name(self) -> str:
        return self.model


def make_provider(advisor) -> LLMProvider:
    name = advisor.provider
    if name == "mock":
        return MockLLMProvider("先看财政和要塞。英法德还在摩洛哥和巴尔干对峙，没有打到本国边境。中立要靠照会和设防，不是靠口头保证。")
    if name not in advisor.presets:
        raise ValueError(f"未知顾问接口 {name}")
    ep = advisor.presets[name]
    return OpenAICompatProvider(ep.base_url, ep.model, ep.api_key, ep.max_retries)
