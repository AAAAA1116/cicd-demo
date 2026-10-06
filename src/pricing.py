"""订单定价模块 —— CI/CD 演示项目的业务代码。

业务规则：
  1. 按订单金额分档给基础折扣
  2. 按会员等级叠加额外折扣
  3. 总折扣率封顶 25%
"""

from __future__ import annotations

from dataclasses import dataclass

MEMBER_LEVELS = ("normal", "silver", "gold")
MEMBER_BONUS = {"normal": 0.00, "silver": 0.02, "gold": 0.05}
MAX_DISCOUNT = 0.25


@dataclass(frozen=True)
class Quote:
    """一次报价结果。"""

    subtotal: float
    discount_rate: float
    total: float


def base_discount(subtotal: float) -> float:
    """按订单金额档位返回基础折扣率。"""
    if subtotal < 100:
        return 0.0
    if subtotal < 500:
        return 0.05
    if subtotal < 1000:
        return 0.10
    return 0.20


def discount_rate(subtotal: float, member_level: str = "normal") -> float:
    """计算最终折扣率（基础档位 + 会员加成，封顶 25%）。"""
    if subtotal < 0:
        raise ValueError("subtotal 不能为负数")
    if member_level not in MEMBER_LEVELS:
        raise ValueError(f"未知会员等级: {member_level}")
    return min(base_discount(subtotal) + MEMBER_BONUS[member_level], MAX_DISCOUNT)


def quote(subtotal: float, member_level: str = "normal") -> Quote:
    """生成报价。"""
    rate = discount_rate(subtotal, member_level)
    return Quote(
        subtotal=round(subtotal, 2),
        discount_rate=rate,
        total=round(subtotal * (1 - rate), 2),
    )
