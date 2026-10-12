# -*- coding: utf-8 -*-
"""轻量中英领域词表：为常见库表/字段名提供中文语义锚点，增强小模型双语检索能力。

仅为高频通用数据库术语的翻译映射，不涉及任何业务数据；未收录的词原样保留。
"""

GLOSSARY: dict[str, str] = {
    # 业务实体
    "order": "订单", "employee": "员工", "staff": "员工", "department": "部门",
    "customer": "客户", "user": "用户", "product": "商品", "category": "分类",
    "brand": "品牌", "supplier": "供应商", "cart": "购物车", "shipment": "发货",
    "payment": "支付", "refund": "退款", "coupon": "优惠券", "review": "评价",
    "wishlist": "收藏", "inventory": "库存", "warehouse": "仓库", "invoice": "发票",
    "tax": "税", "promotion": "促销", "gift": "礼品", "return": "退货",
    "audit": "审计", "log": "日志", "address": "地址", "region": "地区",
    # 度量与字段
    "amount": "金额", "salary": "工资", "wage": "工资", "price": "价格",
    "total": "总额", "quantity": "数量", "stock": "库存", "balance": "余额",
    "discount": "折扣", "fee": "费用", "rating": "评分", "level": "等级",
    # 时间
    "created": "创建", "updated": "更新", "hired": "入职", "registered": "注册",
    "paid": "支付", "shipped": "发货", "delivered": "签收", "valid": "有效",
    "expired": "过期", "used": "使用", "requested": "申请", "issued": "开具",
    "at": "时间", "from": "开始", "to": "截止", "start": "开始", "end": "结束",
    # 通用列
    "name": "名称", "status": "状态", "phone": "电话", "email": "邮箱",
    "content": "内容", "detail": "详情", "reason": "原因", "code": "编码",
    "no": "单号", "id": "编号", "type": "类型", "value": "值", "rate": "费率",
    "manager": "负责人", "actor": "操作人", "action": "操作", "entity": "对象",
    "parent": "父级", "slug": "别名", "sort": "排序", "username": "用户名",
    "contact": "联系人", "country": "国家", "province": "省份", "city": "城市",
    "channel": "渠道", "method": "方式", "carrier": "承运商", "tracking": "物流单号",
    "checked": "勾选", "default": "默认", "locked": "锁定", "is": "是否",
    "purchase": "采购", "items": "明细", "item": "明细", "notifications": "通知",
    "notification": "通知", "sessions": "会话", "session": "会话", "settings": "配置",
    "setting": "配置", "currencies": "货币", "currency": "货币", "logs": "日志",
    "refunds": "退款", "returns": "退货", "coupons": "优惠券", "orders": "订单",
    "employees": "员工", "departments": "部门", "customers": "客户",
    "products": "商品", "categories": "分类", "addresses": "地址",
}


def gloss(identifier: str) -> str:
    """将下划线命名的库表/字段名翻译为「中文锚点」，未收录词原样保留。

    例：purchase_orders -> 采购 订单；created_at -> 创建时间
    """
    parts = identifier.lower().split("_")
    zh = [GLOSSARY.get(p, "") for p in parts]
    return "".join(zh)  # 例：created+at -> 创建时间
