"""端到端入口：意图理解 → Schema 检索 → SQL 生成与执行(纠错闭环) → 结果解释。

用法:
  python scripts/init_demo_db.py   # 首次运行先生成演示库
  python run.py                    # 进入交互式问答，输入 exit 退出
"""
from __future__ import annotations

import time
from pathlib import Path

import yaml

from agents.intent_agent.agent import IntentAgent
from agents.result_agent.agent import ResultAgent
from agents.schema_agent.agent import SchemaAgent
from agents.sql_agent.agent import SQLAgent
from core.llm import LocalLLM
from core.mcp_client import MCPClient

ROOT = Path(__file__).parent
CONFIG = yaml.safe_load((ROOT / "config" / "agent_config.yml").read_text(encoding="utf-8"))


class LocalDBAgent:
    """端侧离线数据库智能体：MoFA 四模块流水线编排。"""

    def __init__(self):
        llm_cfg, db_cfg = CONFIG["llm"], CONFIG["database"]
        llm = LocalLLM(llm_cfg["base_url"], llm_cfg["api_key"],
                       llm_cfg["model"], llm_cfg.get("temperature", 0.0))
        mcp = MCPClient(ROOT / db_cfg["path"])
        # 四个 MoFA 模块
        self.intent_agent = IntentAgent(llm, mcp)
        self.schema_agent = SchemaAgent(llm, mcp)
        self.sql_agent = SQLAgent(llm, mcp)
        self.result_agent = ResultAgent(llm, mcp)

    def ask(self, question: str) -> dict:
        t0 = time.time()
        # ① 意图理解
        intent = self.intent_agent.run(question)
        # ② Schema 检索
        schema_info = self.schema_agent.run(intent)
        if not schema_info.get("ok"):
            return {"ok": False, "answer": f"Schema 检索失败: {schema_info.get('error')}"}
        # ③ SQL 生成与执行（生成—执行—纠错闭环）
        exec_result = self.sql_agent.run(intent, schema_info)
        if not exec_result.get("ok"):
            return {"ok": False, "answer": f"SQL 执行失败: {exec_result.get('error')}"}
        # ④ 结果解释
        answer = self.result_agent.run(
            question, exec_result["sql"], exec_result["columns"], exec_result["rows"])
        return {"ok": True, "answer": answer, "sql": exec_result["sql"],
                "attempts": exec_result["attempts"], "elapsed_ms": int((time.time() - t0) * 1000)}


def main() -> None:
    agent = LocalDBAgent()
    print("DBright 已就绪（端侧离线运行，数据不出端）。输入 exit 退出。\n")
    while True:
        try:
            q = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in {"exit", "quit"}:
            break
        r = agent.ask(q)
        if r["ok"]:
            print(f"Agent > {r['answer']}")
            print(f"       (SQL: {r['sql']} | 纠错重试: {r['attempts']} 次 | 耗时: {r['elapsed_ms']}ms)\n")
        else:
            print(f"Agent > 出错了：{r['answer']}\n")


if __name__ == "__main__":
    main()
