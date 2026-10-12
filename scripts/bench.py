# -*- coding: utf-8 -*-
"""DBright 量化基准测试。

Part A（无需 LLM，直接可跑）:
  - Schema 向量检索 recall@k 与检索延迟
  - 向量索引构建耗时与索引体积

Part B（需本地 Ollama，加 --llm 参数）:
  - NL→SQL 执行准确率（execution accuracy，对比标准 SQL 的结果集）
  - 端到端延迟（意图理解→Schema 检索→SQL 生成执行→结果解释）

用法:
  python scripts/bench.py            # 仅 Part A
  python scripts/bench.py --llm      # Part A + Part B（需 ollama serve 且已 pull 模型）
"""
from __future__ import annotations

import argparse
import statistics
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB = ROOT / "data" / "demo.db"  # 可通过 --db 覆盖（如 data/big.db）

# (问题, 标准 SQL, 检索必需表) —— 覆盖 单表/多表 JOIN/聚合/筛选/排序 等典型场景
EVAL_SET = [
    ("每个部门有多少人？", "SELECT d.name, COUNT(*) FROM employees e JOIN departments d ON e.department_id=d.id GROUP BY d.name", {"departments", "employees"}),
    ("技术部的员工平均工资是多少？", "SELECT AVG(e.salary) FROM employees e JOIN departments d ON e.department_id=d.id WHERE d.name='技术部'", {"departments", "employees"}),
    ("订单总金额最高的员工是谁？", "SELECT e.name FROM employees e JOIN orders o ON o.employee_id=e.id GROUP BY e.id ORDER BY SUM(o.amount) DESC LIMIT 1", {"employees", "orders"}),
    ("2024年一共有多少笔订单？", "SELECT COUNT(*) FROM orders WHERE created_at LIKE '2024%'", {"orders"}),
    ("薪资超过20万的员工有多少人？", "SELECT COUNT(*) FROM employees WHERE salary>20", {"employees"}),
    ("每个员工的订单总金额，按金额从高到低排", "SELECT e.name, SUM(o.amount) FROM employees e JOIN orders o ON o.employee_id=e.id GROUP BY e.id ORDER BY SUM(o.amount) DESC", {"employees", "orders"}),
    ("人事部有哪些员工？", "SELECT e.name FROM employees e JOIN departments d ON e.department_id=d.id WHERE d.name='人事部'", {"departments", "employees"}),
    ("订单金额超过3000元的订单有多少笔？", "SELECT COUNT(*) FROM orders WHERE amount>3000", {"orders"}),
    ("2024年5月的订单总金额是多少？", "SELECT SUM(amount) FROM orders WHERE created_at BETWEEN '2024-05-01' AND '2024-05-31'", {"orders"}),
    ("入职最早的员工是谁？", "SELECT name FROM employees ORDER BY hired_at ASC LIMIT 1", {"employees"}),
    ("平均每个员工有多少笔订单？", "SELECT COUNT(*)*1.0/COUNT(DISTINCT employee_id) FROM orders", {"orders"}),
    ("哪个部门的员工平均薪资最高？", "SELECT d.name FROM employees e JOIN departments d ON e.department_id=d.id GROUP BY d.name ORDER BY AVG(e.salary) DESC LIMIT 1", {"departments", "employees"}),
    ("订单金额在100到500元之间的订单有多少笔？", "SELECT COUNT(*) FROM orders WHERE amount BETWEEN 100 AND 500", {"orders"}),
    ("每个部门在2024年的订单总金额分别是多少？", "SELECT d.name, SUM(o.amount) FROM orders o JOIN employees e ON o.employee_id=e.id JOIN departments d ON e.department_id=d.id WHERE o.created_at LIKE '2024%' GROUP BY d.name", {"departments", "employees", "orders"}),
    ("工资最高的员工在哪个部门？", "SELECT d.name FROM employees e JOIN departments d ON e.department_id=d.id ORDER BY e.salary DESC LIMIT 1", {"departments", "employees"}),
]


def get_schema(db: Path = DB) -> dict:
    conn = sqlite3.connect(db)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    schema = {t: {"columns": [dict(zip(["cid", "name", "type", "notnull", "dflt_value", "pk"], c))
                              for c in conn.execute(f'PRAGMA table_info("{t}")')]}
              for t in tables}
    conn.close()
    return schema


def run_sql(sql: str, db: Path = DB):
    """只读执行，返回排序后的结果集（用于 execution accuracy 对比）。"""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = sorted(conn.execute(sql).fetchall(), key=str)
        # 浮点结果四舍五入到 2 位，消除聚合精度差异
        return [[round(c, 2) if isinstance(c, float) else c for c in r] for r in rows]
    finally:
        conn.close()


def part_a(db: Path = DB, top_k: int = 3, n_latency: int = 10) -> dict:
    from core.schema_vector_store import SchemaVectorStore

    schema = get_schema(db)
    # --- 索引构建耗时（强制冷构建，隔离本地缓存） ---
    with tempfile.TemporaryDirectory() as tmp:
        store = SchemaVectorStore(cache_dir=tmp)
        t0 = time.perf_counter()
        store.build_or_load(schema)
        build_ms = (time.perf_counter() - t0) * 1000

    # --- 正式索引（走本地缓存） ---
    store = SchemaVectorStore()
    store.build_or_load(schema)

    # --- recall@k ---
    strict = 0  # 必需表全部被召回
    loose = 0   # 至少命中一张必需表
    for q, _, need in EVAL_SET:
        top = set(store.search(q, top_k=top_k))
        strict += need <= top
        loose += bool(need & top)
    n = len(EVAL_SET)

    # --- 检索延迟 ---
    q0 = EVAL_SET[0][0]
    lat = []
    for _ in range(n_latency):
        t0 = time.perf_counter()
        store.search(q0, top_k=top_k)
        lat.append((time.perf_counter() - t0) * 1000)

    # 只统计当前 Schema 对应的索引文件（缓存目录可能含其他库的索引）
    index_file = store.cache_dir / f"{SchemaVectorStore._schema_hash(schema)}.pkl"
    index_kb = index_file.stat().st_size / 1024

    return {"recall_strict": strict / n, "recall_loose": loose / n, "n": n,
            "build_ms": build_ms, "search_ms_avg": statistics.mean(lat),
            "index_kb": index_kb, "n_tables": len(schema)}


def part_b() -> dict | None:
    try:
        from run import LocalDBAgent  # 复用端到端流水线
        agent = LocalDBAgent()
        agent.ask("连通性测试：有多少员工？")  # 触发模型加载，不计入统计
    except Exception as e:
        print(f"[Part B] 本地 LLM 不可用，跳过（需 ollama serve 且已 pull 模型）: {e}")
        return None

    gold_results = {i: run_sql(sql) for i, (_, sql, _) in enumerate(EVAL_SET)}
    acc, latencies, attempts = 0, [], []
    for i, (q, _, _) in enumerate(EVAL_SET):
        t0 = time.perf_counter()
        r = agent.ask(q)
        latencies.append((time.perf_counter() - t0) * 1000)
        if not r.get("ok"):
            attempts.append(0)
            continue
        attempts.append(r["attempts"])
        try:
            acc += run_sql(r["sql"]) == gold_results[i]
        except sqlite3.Error:
            pass
    return {"exec_acc": acc / len(EVAL_SET), "n": len(EVAL_SET),
            "e2e_ms_avg": statistics.mean(latencies), "e2e_ms_p50": statistics.median(latencies),
            "attempts_avg": statistics.mean(attempts)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="运行 Part B（需本地 Ollama）")
    ap.add_argument("--db", default=str(DB), help="评测数据库路径（默认 data/demo.db）")
    ap.add_argument("--top-k", type=int, default=3, help="召回表数量 k（默认 3）")
    args = ap.parse_args()
    db = Path(args.db)
    assert db.exists(), f"数据库不存在: {db}"

    a = part_a(db, top_k=args.top_k)
    k = args.top_k
    print(f"== Part A: Schema 向量检索（无需 LLM, {db.name}, top_k={k}） ==")
    print(f"  库表规模            : {a['n_tables']} 张表")
    print(f"  向量索引构建耗时    : {a['build_ms']:.0f} ms")
    print(f"  向量索引体积        : {a['index_kb']:.1f} KB")
    print(f"  检索延迟(单次 top{k}) : {a['search_ms_avg']:.1f} ms")
    print(f"  recall@{k} (严格)     : {a['recall_strict']:.0%}  ({a['n']} 题)")
    print(f"  recall@{k} (宽松)     : {a['recall_loose']:.0%}")

    if args.llm:
        b = part_b()
        if b:
            print("\n== Part B: NL→SQL 端到端（本地 Ollama） ==")
            print(f"  执行准确率          : {b['exec_acc']:.0%}  ({b['n']} 题)")
            print(f"  端到端延迟 avg/p50  : {b['e2e_ms_avg']:.0f} / {b['e2e_ms_p50']:.0f} ms")
            print(f"  纠错重试次数 avg    : {b['attempts_avg']:.2f}")


if __name__ == "__main__":
    main()
