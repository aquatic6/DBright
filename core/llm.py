"""本地 LLM 客户端：通过 OpenAI 兼容接口连接本地 Ollama，全程离线推理。"""
from __future__ import annotations

from openai import OpenAI


class LocalLLM:
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.0):
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=120)
        self.model = model
        self.temperature = temperature

    def chat(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""
