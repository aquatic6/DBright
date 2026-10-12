"""模块③ SQL 生成与执行：基于意图与相关 Schema 生成 SQL，
通过 MCP execute_sql 执行；失败时调用 report_error 反馈给 LLM 纠错，构成「生成—执行—纠错」闭环。"""
from __future__ import annotations

from core.base import Agent, extract_json, load_agent_config

GEN_SYSTEM = """你是 SQL 生成模块。根据用户意图与相关表结构生成 SQLite SQL。
严格只输出 JSON：{"sql": "<只读 SELECT 查询>"}
禁止 INSERT/UPDATE/DELETE/DDL；表名、列名必须与给定 Schema 完全一致。"""

AGENT_DIR = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]


class SQLAgent(Agent):
    def __init__(self, llm, mcp=None):
        super().__init__(llm, mcp, load_agent_config(AGENT_DIR))
        self.max_retry = int(self.config.get("max_retry", 3))

    def _build_prompt(self, intent: dict, relevant_ddl: str) -> str:
        return (
            f"用户原始问题: {intent.get('_question')}\n"
            f"解析后的意图: {intent}\n\n相关表结构:\n{relevant_ddl}"
        )

    def run(self, intent: dict, schema_info: dict) -> dict:
        relevant_ddl = schema_info.get("relevant_ddl", "")
        prompt = self._build_prompt(intent, relevant_ddl)
        history: list[str] = []  # 错误反馈历史，供纠错参考

        for attempt in range(1, self.max_retry + 1):
            # ---- 生成 ----
            user = prompt
            if history:
                user += "\n\n历史错误（请避免重蹈）:\n" + "\n".join(history)
            sql = extract_json(self.llm.chat(GEN_SYSTEM, user)).get("sql", "").strip()
            if not sql:
                history.append("第{}次未输出合法 JSON，请严格输出 {{\"sql\": ...}}".format(attempt))
                continue

            # ---- 执行（MCP 只读） ----
            result = self.mcp.call_tool("execute_sql", {"sql": sql})
            if result.get("ok"):
                return {"ok": True, "sql": sql, "attempts": attempt,
                        "columns": result["columns"], "rows": result["rows"]}

            # ---- 纠错：report_error 反馈，进入下一轮 ----
            feedback = self.mcp.call_tool(
                "report_error", {"sql": sql, "error": result.get("error", "")}
            ).get("feedback", "")
            history.append(f"[第{attempt}次] {feedback}")

        return {"ok": False, "error": f"纠错重试 {self.max_retry} 次仍失败", "history": history}

    @staticmethod
    def name() -> str:
        return "sql-agent"
