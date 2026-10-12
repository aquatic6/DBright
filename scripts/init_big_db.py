# -*- coding: utf-8 -*-
"""生成 30 表规模的演示库 data/big.db：3 张核心表(与 demo.db 同构) + 27 张电商域干扰表，
用于在更接近真实规模的 Schema 上压测向量检索 recall。"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "big.db"

# 27 张电商域干扰表（表名 + 列定义）
DISTRACTORS = {
    "products": "id INTEGER PRIMARY KEY, sku TEXT, name TEXT, category_id INTEGER, brand_id INTEGER, price REAL, stock INTEGER, status TEXT, created_at TEXT",
    "categories": "id INTEGER PRIMARY KEY, parent_id INTEGER, name TEXT, slug TEXT, sort_order INTEGER",
    "brands": "id INTEGER PRIMARY KEY, name TEXT, country TEXT, logo_url TEXT",
    "suppliers": "id INTEGER PRIMARY KEY, name TEXT, contact TEXT, phone TEXT, level TEXT",
    "customers": "id INTEGER PRIMARY KEY, username TEXT, email TEXT, phone TEXT, registered_at TEXT, level TEXT",
    "customer_addresses": "id INTEGER PRIMARY KEY, customer_id INTEGER, province TEXT, city TEXT, detail TEXT, is_default INTEGER",
    "carts": "id INTEGER PRIMARY KEY, customer_id INTEGER, status TEXT, created_at TEXT",
    "cart_items": "id INTEGER PRIMARY KEY, cart_id INTEGER, product_id INTEGER, quantity INTEGER, checked_at TEXT",
    "shipments": "id INTEGER PRIMARY KEY, order_ref TEXT, carrier TEXT, tracking_no TEXT, shipped_at TEXT, delivered_at TEXT",
    "payments": "id INTEGER PRIMARY KEY, order_ref TEXT, channel TEXT, amount REAL, paid_at TEXT, status TEXT",
    "refunds": "id INTEGER PRIMARY KEY, payment_id INTEGER, amount REAL, reason TEXT, refunded_at TEXT",
    "coupons": "id INTEGER PRIMARY KEY, code TEXT, discount_type TEXT, discount_value REAL, valid_from TEXT, valid_to TEXT",
    "customer_coupons": "id INTEGER PRIMARY KEY, customer_id INTEGER, coupon_id INTEGER, used_at TEXT",
    "reviews": "id INTEGER PRIMARY KEY, product_id INTEGER, customer_id INTEGER, rating INTEGER, content TEXT, created_at TEXT",
    "wishlists": "id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER, created_at TEXT",
    "inventory": "id INTEGER PRIMARY KEY, product_id INTEGER, warehouse_id INTEGER, quantity INTEGER, locked INTEGER",
    "warehouses": "id INTEGER PRIMARY KEY, name TEXT, city TEXT, manager TEXT",
    "purchase_orders": "id INTEGER PRIMARY KEY, supplier_id INTEGER, total REAL, status TEXT, created_at TEXT",
    "purchase_items": "id INTEGER PRIMARY KEY, po_id INTEGER, product_id INTEGER, quantity INTEGER, unit_price REAL",
    "invoices": "id INTEGER PRIMARY KEY, invoice_no TEXT, order_ref TEXT, amount REAL, tax REAL, issued_at TEXT",
    "invoice_items": "id INTEGER PRIMARY KEY, invoice_id INTEGER, item_name TEXT, quantity INTEGER, unit_price REAL",
    "tax_rates": "id INTEGER PRIMARY KEY, region TEXT, category TEXT, rate REAL",
    "shipping_methods": "id INTEGER PRIMARY KEY, name TEXT, base_fee REAL, per_kg_fee REAL",
    "promotions": "id INTEGER PRIMARY KEY, title TEXT, start_at TEXT, end_at TEXT, rule TEXT",
    "gift_cards": "id INTEGER PRIMARY KEY, card_no TEXT, balance REAL, expired_at TEXT",
    "returns": "id INTEGER PRIMARY KEY, order_ref TEXT, reason TEXT, status TEXT, requested_at TEXT",
    "return_items": "id INTEGER PRIMARY KEY, return_id INTEGER, product_id INTEGER, quantity INTEGER",
    "audit_logs": "id INTEGER PRIMARY KEY, actor TEXT, action TEXT, entity TEXT, created_at TEXT",
}

# 核心 3 表（与 demo.db 同构，保证 EVAL_SET 与评测脚本通用）
CORE = {
    "departments": "id INTEGER PRIMARY KEY, name TEXT NOT NULL",
    "employees": "id INTEGER PRIMARY KEY, name TEXT NOT NULL, department_id INTEGER, salary REAL, hired_at TEXT",
    "orders": "id INTEGER PRIMARY KEY, employee_id INTEGER, amount REAL, created_at TEXT",
}


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    random.seed(7)
    for name, ddl in {**DISTRACTORS, **CORE}.items():
        conn.execute(f"CREATE TABLE {name} ({ddl})")
        cols = [c.strip().split()[0] for c in ddl.split(",")]
        # 每张表灌入少量行，贴近真实库
        placeholders = ",".join("?" for _ in cols)
        for i in range(1, 21):
            conn.execute(f"INSERT INTO {name} VALUES ({placeholders})",
                         tuple(i if j == 0 else f"{name[:3]}_{i}_{j}" for j in range(len(cols))))
    conn.commit()
    conn.close()
    print(f"大规模演示库已生成: {DB_PATH}  ({len(CORE) + len(DISTRACTORS)} 张表)")


if __name__ == "__main__":
    main()
