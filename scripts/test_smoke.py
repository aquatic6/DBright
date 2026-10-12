# -*- coding: utf-8 -*-
"""冒烟测试：验证 MCP 工具链路、只读防护与 JSON 解析（无需本地大模型）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.base import extract_json
from core.mcp_client import MCPClient

mcp = MCPClient("data/demo.db")

s = mcp.call_tool("get_schema", {})
assert s["ok"], s
print("tables:", list(s["schema"].keys()))

r = mcp.call_tool("execute_sql", {
    "sql": "SELECT d.name, COUNT(*) c FROM employees e "
           "JOIN departments d ON e.department_id=d.id "
           "GROUP BY d.name ORDER BY c DESC"})
assert r["ok"], r
print("query rows:", r["rows"])

bad = mcp.call_tool("execute_sql", {"sql": "SELECT * FROM not_exist"})
assert not bad["ok"] and bad["error"]
print("error path:", bad["error"])

fb = mcp.call_tool("report_error", {"sql": bad["sql"], "error": bad["error"]})
assert fb["ok"] and "执行失败" in fb["feedback"]
print("feedback ok")

w = mcp.call_tool("execute_sql", {"sql": "DELETE FROM employees"})
assert not w["ok"], "只读模式应阻止写入！"
print("readonly guard: write blocked ->", w["error"])

j = extract_json('说明文字\n```json\n{"sql": "SELECT 1"}\n```')
assert j == {"sql": "SELECT 1"}, j
print("extract_json ok")

print("\nALL SMOKE TESTS PASSED")
