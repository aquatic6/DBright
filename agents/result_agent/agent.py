"""模块④ 结果解释：将 SQL 查询结果翻译为自然语言结论，完成端到端链路。"""
from __future__ import annotations

from core.base import Agent, load_agent_config

SYSTEM = """你是结果解释模块。根据用户问题、执行的 SQL 与查询结果，用简洁自然语言回答用户。
要求：直接给结论；保留关键数字；不超过 5 句话。"""

AGENT_DIR = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]


class ResultAgent(Agent):
    def __init__(self, llm, mcp=None):
        super().__init__(llm, mcp, load_agent_config(AGENT_DIR))

    def run(self, question: str, sql: str, columns: list, rows: list) -> str:
        preview = rows[:20]
        user = (
            f"用户问题: {question}\n执行 SQL: {sql}\n"
            f"结果列: {columns}\n结果行(最多展示20行): {preview}\n"
            f"共 {len(rows)} 行。请用自然语言回答。"
        )
        return self.llm.chat(SYSTEM, user)

    @staticmethod
    def name() -> str:
        return "result-agent"
