"""模块① 意图理解：将自然语言问题解析为结构化意图，供下游 Schema 检索与 SQL 生成使用。"""
from __future__ import annotations

from core.base import Agent, load_agent_config

SYSTEM = """你是数据库问答系统的意图理解模块。将用户问题解析为 JSON：
{"intent": "<查询目标描述>", "metrics": [<要计算的指标>], "dimensions": [<分组维度>],
 "filters": [<筛选条件>], "order_by": "<排序要求或无>", "limit": <数字或无>}
只输出 JSON，不要输出其他内容。"""

AGENT_DIR = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]


class IntentAgent(Agent):
    def __init__(self, llm, mcp=None):
        super().__init__(llm, mcp, load_agent_config(AGENT_DIR))

    def run(self, user_question: str) -> dict:
        intent = self.ask_json(SYSTEM, user_question)
        intent["_question"] = user_question  # 保留原文供下游使用
        return intent

    @staticmethod
    def name() -> str:
        return "intent-agent"
