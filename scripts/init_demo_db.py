"""初始化演示数据库 data/demo.db：departments / employees / orders 三张表。"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "demo.db"

DDL = """
CREATE TABLE departments (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE employees (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    department_id INTEGER REFERENCES departments(id),
    salary        REAL,
    hired_at      TEXT
);
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    amount      REAL,
    created_at  TEXT
);
"""

DEPTS = ["技术部", "运营部", "人事部"]
SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨"


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)
    random.seed(42)

    for i, d in enumerate(DEPTS, 1):
        conn.execute("INSERT INTO departments VALUES (?, ?)", (i, d))

    emp_ids = []
    for i in range(1, 24):
        dept = random.choices([1, 2, 3], weights=[5, 3, 1])[0]
        name = random.choice(SURNAMES) + random.choice(["伟", "芳", "娜", "敏", "静", "磊"])
        conn.execute(
            "INSERT INTO employees VALUES (?, ?, ?, ?, ?)",
            (i, name, dept, round(random.uniform(6, 40), 1),
             f"20{random.randint(18, 25)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"),
        )
        emp_ids.append(i)

    for i in range(1, 101):
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            (i, random.choice(emp_ids), round(random.uniform(10, 5000), 2),
             f"202{random.randint(3, 5)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"),
        )

    conn.commit()
    conn.close()
    print(f"演示数据库已生成: {DB_PATH}  (3 部门 / 23 员工 / 100 订单)")


if __name__ == "__main__":
    main()
