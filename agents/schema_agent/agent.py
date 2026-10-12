"""模块② Schema 检索：调用 MCP get_schema 获取库表结构，并基于意图裁剪相关表，控制 Prompt 长度。"""
from __future__ import annotations

from core.base import Agent, load_agent_config

SYSTEM = """你是 Schema 检索模块。根据用户意图从完整表结构中选出相关表，并输出这些表的 DDL。
只输出相关表的建表语句（CREATE TABLE ...;），不要输出解释。"""

AGENT_DIR = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]


class SchemaAgent(Agent):
    def __init__(self, llm, mcp=None):
        super().__init__(llm, mcp, load_agent_config(AGENT_DIR))

    def run(self, intent: dict) -> dict:
        # 1) 通过 MCP 工具检索完整 Schema
        full = self.mcp.call_tool("get_schema", {})
        if not full.get("ok"):
            return {"ok": False, "error": f"get_schema 失败: {full.get('error')}"}
        schema = full["schema"]

        # 2) 基于意图让 LLM 裁剪相关表（Schema RAG 的轻量实现）
        user = (
            f"用户意图: {intent}\n\n完整表结构:\n"
            + "\n".join(f"- {t}: " + ", ".join(c["name"] for c in v["columns"]) for t, v in schema.items())
            + "\n\n请输出相关表的完整建表语句。"
        )
        ddl = self.llm.chat(SYSTEM, user)
        return {"ok": True, "schema": schema, "relevant_ddl": ddl}

    @staticmethod
    def name() -> str:
        return "schema-agent"
