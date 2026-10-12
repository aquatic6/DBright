"""MoFA 风格的 Agent 基类：每个模块即一个 Agent，配置与逻辑分离。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_agent_config(agent_dir: str | Path) -> dict:
    """加载 agents/<name>/agent_config.yml。"""
    path = Path(agent_dir) / "agent_config.yml"
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


class Agent:
    """Agent 基类：持有 LLM 客户端与 MCP 工具客户端，子类实现 run()。"""

    def __init__(self, llm, mcp=None, config: dict | None = None):
        self.llm = llm          # core.llm.LocalLLM
        self.mcp = mcp          # core.mcp_client.MCPClient，可为 None
        self.config = config or {}

    def run(self, *args, **kwargs) -> Any:  # pragma: no cover
        raise NotImplementedError

    # ---- 工具方法 ----
    def ask_json(self, system: str, user: str) -> dict:
        """请求 LLM 并解析严格 JSON 输出，解析失败时返回空 dict。"""
        text = self.llm.chat(system=system, user=user)
        return extract_json(text)

    @staticmethod
    def name() -> str:
        return "base-agent"


def extract_json(text: str) -> dict:
    """从模型输出中提取第一个 JSON 对象（容忍 ```json 代码块包裹）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    start, depth = -1, 0
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}
