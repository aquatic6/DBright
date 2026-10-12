# -*- coding: utf-8 -*-
"""Schema 向量检索测试：验证 Embedding 相似度召回相关表（首次运行需下载约 100MB 模型）。"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schema_vector_store import SchemaVectorStore

DB = Path(__file__).parent.parent / "data" / "demo.db"

# 模拟 MCP get_schema 的输出
conn = sqlite3.connect(DB)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
schema = {t: {"columns": [dict(zip(["cid", "name", "type", "notnull", "dflt_value", "pk"], c))
                          for c in conn.execute(f'PRAGMA table_info("{t}")')]}
          for t in tables}
conn.close()

store = SchemaVectorStore()
store.build_or_load(schema)          # 首次构建索引
store.build_or_load(schema)          # 第二次应命中本地缓存

CASES = [
    ("每个部门有多少人？按人数降序", {"departments", "employees"}),
    ("订单金额最高的员工是谁？", {"orders", "employees"}),
    ("2024年每个月的订单总金额趋势", {"orders"}),
]

ok = True
for q, expect in CASES:
    top = store.search(q, top_k=3)
    hit = bool(expect & set(top))
    ok &= hit
    print(f"[{'PASS' if hit else 'FAIL'}] {q}\n       top3={top} 期望命中={sorted(expect)}")

assert ok, "存在召回失败的用例"
print("\nSCHEMA VECTOR RETRIEVAL TESTS PASSED")
