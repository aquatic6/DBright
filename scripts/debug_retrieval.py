# -*- coding: utf-8 -*-
"""诊断：查看各问题在 31 表库上的 top-k 召回情况。"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.schema_vector_store import SchemaVectorStore

db = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/big.db")
conn = sqlite3.connect(db)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
schema = {t: {"columns": [dict(zip(["cid", "name", "type", "notnull", "dflt_value", "pk"], c))
                          for c in conn.execute(f'PRAGMA table_info("{t}")')]} for t in tables}
conn.close()

s = SchemaVectorStore()
s.build_or_load(schema)

CASES = [
    ("每个部门有多少人？", "departments, employees"),
    ("技术部的员工平均工资是多少？", "departments, employees"),
    ("订单总金额最高的员工是谁？", "employees, orders"),
    ("2024年一共有多少笔订单？", "orders"),
    ("薪资超过20万的员工有多少人？", "employees"),
    ("每个员工的订单总金额，按金额从高到低排", "employees, orders"),
    ("人事部有哪些员工？", "departments, employees"),
    ("订单金额超过3000元的订单有多少笔？", "orders"),
    ("2024年5月的订单总金额是多少？", "orders"),
    ("入职最早的员工是谁？", "employees"),
    ("平均每个员工有多少笔订单？", "orders"),
    ("哪个部门的员工平均薪资最高？", "departments, employees"),
    ("订单金额在100到500元之间的订单有多少笔？", "orders"),
    ("每个部门在2024年的订单总金额分别是多少？", "departments, employees, orders"),
    ("工资最高的员工在哪个部门？", "departments, employees"),
]

for q, need in CASES:
    top8 = s.search(q, top_k=8)
    ok3 = all(t in top8[:3] for t in [x.strip() for x in need.split(",")])
    mark = "OK " if ok3 else "MISS"
    print(f"[{mark}] {q}")
    print(f"       need=[{need}] top3={top8[:3]}")
    if not ok3:
        print(f"       top8={top8}")
