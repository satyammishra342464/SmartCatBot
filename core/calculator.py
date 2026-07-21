"""Safe arithmetic evaluator for the agent's calculate tool (AST-based, no eval)."""
from __future__ import annotations

import ast
import math
import operator as op

_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

_FUNCS = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval_node(a) for a in node.args])
    raise ValueError(f"unsupported expression element: {ast.dump(node)[:80]}")


def calculate(expression: str) -> dict:
    """Evaluate an arithmetic expression like '(40e6 - 25e6) * 0.75' safely."""
    import re

    # Strip only thousands-separator commas (1,000,000) — not argument commas in min(a, b).
    cleaned = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", expression)
    cleaned = cleaned.replace("$", "").strip()
    try:
        result = _eval_node(ast.parse(cleaned, mode="eval"))
        return {"expression": cleaned, "result": result}
    except Exception as exc:
        return {"expression": cleaned, "error": f"cannot evaluate: {exc}"}
