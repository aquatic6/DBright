"""sqlite-tools MCP Server：将数据库工具封装为模型可调用的 MCP 接口。

工具列表：
  · get_schema     表结构检索：返回全部表/列/主外键信息
  · execute_sql    SQL 执行：以只读模式(mode=ro)执行查询，杜绝写入
  · report_error   错误反馈：格式化执行错误，供 LLM 纠错重试
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sqlite-tools")

# 由 main() 注入，避免全局状态
_DB_PATH: Path = Path("data/demo.db")


def _connect() -> sqlite3.Connection:
    """只读模式打开 SQLite：file:xxx?mode=ro，从机制上保证数据不被修改。"""
    uri = f"file:{_DB_PATH.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def get_schema() -> dict:
    """检索数据库表结构：表名、列名、类型、主键与外键。"""
    conn = _connect()
    try:
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        schema = {}
        for t in tables:
            cols = [dict(r) for r in conn.execute(f'PRAGMA table_info("{t}")')]
            fks = [dict(r) for r in conn.execute(f'PRAGMA foreign_key_list("{t}")')]
            schema[t] = {"columns": cols, "foreign_keys": fks}
        return {"ok": True, "schema": schema}
    finally:
        conn.close()


@mcp.tool()
def execute_sql(sql: str) -> dict:
    """以只读模式执行 SQL 查询，返回列名与行数据；出错时返回错误信息。"""
    try:
        conn = _connect()
        try:
            cur = conn.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
            return {"ok": True, "columns": cols, "rows": rows, "row_count": len(rows)}
        finally:
            conn.close()
    except sqlite3.Error as e:
        return {"ok": False, "error": str(e), "sql": sql}


@mcp.tool()
def report_error(sql: str, error: str) -> dict:
    """错误反馈：将执行错误格式化为给 LLM 的纠错提示。"""
    return {
        "ok": True,
        "feedback": (
            f"上一次生成的 SQL 执行失败。\nSQL: {sql}\n错误: {error}\n"
            "请检查：1) 表名/列名拼写是否与 Schema 一致；"
            "2) 聚合与 GROUP BY 是否匹配；3) 日期/字符串格式是否正确；"
            "4) 是否使用了只读查询（禁止 INSERT/UPDATE/DELETE/DDL）。"
        ),
    }


def main() -> None:
    global _DB_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="SQLite 数据库文件路径")
    args = parser.parse_args()
    _DB_PATH = Path(args.db)
    mcp.run()  # 以 stdio 方式运行，供 MCP 客户端连接


if __name__ == "__main__":
    main()
