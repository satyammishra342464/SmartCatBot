"""The pure calculator tool (no client/IO) — sanity that core is importable and safe."""
from core.calculator import calculate


def test_basic_arithmetic():
    assert calculate("100 - 25")["result"] == 75
    assert calculate("2 ** 10")["result"] == 1024


def test_reinsurance_payout_expression():
    # 40M loss on a 100 xs 25 layer -> min(max(40-25,0),100) = 15
    assert calculate("min(max(40 - 25, 0), 100)")["result"] == 15


def test_rejects_unsafe_input():
    out = calculate("__import__('os').system('echo hi')")
    assert "error" in out
