"""pricing 模块的单元测试 —— CI 流水线的核心守门员。"""

import pytest

from pricing import MAX_DISCOUNT, discount_rate, quote


@pytest.mark.parametrize(
    "subtotal, expected",
    [
        (0, 0.0),        # 下边界
        (99.99, 0.0),    # 第一档内
        (100, 0.05),     # 第一档边界
        (499.99, 0.05),
        (500, 0.10),     # 第二档边界
        (999.99, 0.10),
        (1000, 0.20),    # 第三档边界
        (50000, 0.20),
    ],
)
def test_base_discount_tiers(subtotal, expected):
    assert discount_rate(subtotal, "normal") == pytest.approx(expected)


@pytest.mark.parametrize(
    "level, bonus",
    [("normal", 0.0), ("silver", 0.02), ("gold", 0.05)],
)
def test_member_bonus(level, bonus):
    assert discount_rate(200, level) == pytest.approx(0.05 + bonus)


def test_discount_is_capped():
    """黄金会员 + 大额订单 = 0.20 + 0.05，正好触顶。"""
    assert discount_rate(1000, "gold") == MAX_DISCOUNT


def test_quote_total():
    q = quote(200, "silver")  # 200 * (1 - 0.07) = 186.0
    assert q.subtotal == 200
    assert q.discount_rate == pytest.approx(0.07)
    assert q.total == pytest.approx(186.0)


def test_negative_subtotal_rejected():
    with pytest.raises(ValueError):
        discount_rate(-1)


def test_unknown_member_level_rejected():
    with pytest.raises(ValueError):
        discount_rate(100, "diamond")
