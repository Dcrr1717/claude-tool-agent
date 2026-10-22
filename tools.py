"""The agent's three custom tools.

Design notes
------------
Each tool is split in two:

* a **pure function** (``_calculate``, ``_number_tool``, ``_lookup``) that holds
  all the logic, validates its inputs, and raises ``ValueError`` on bad input.
  These are import-safe and unit-tested in ``tests/test_tools.py`` with no API
  key and no network.
* a thin ``@beta_tool`` **wrapper** that the Anthropic SDK tool runner calls.
  The wrapper catches errors, records the call into ``trace`` for the readable
  CLI trace, and always returns a *string* to the model (never raises), marking
  failures with an ``Error:`` prefix so the model can recover or explain.

Why this shape: the ``@beta_tool`` decorator builds each tool's JSON schema from
the wrapper's signature and docstring, so the wrapper signatures stay minimal
and fully typed, while the testable logic lives in plain functions.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import sympy
from anthropic import beta_tool
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

import trace as trace_mod

# --------------------------------------------------------------------------- #
# Tool 1: safe exact-math evaluator (SymPy, never eval)                        #
# --------------------------------------------------------------------------- #

# Preferred aliases / constants exposed to the parser via ``local_dict`` (these
# override SymPy's defaults, e.g. mapping lowercase ``e`` and ``ln``). The real
# security boundary is the character whitelist below, which rejects quotes,
# brackets, attribute access and dunder tricks before parsing begins, so the
# parser only ever sees SymPy function/number syntax - we never touch ``eval``.
_ALLOWED_NAMES = {
    "pi": sympy.pi,
    "E": sympy.E,
    "e": sympy.E,
    "I": sympy.I,
    "oo": sympy.oo,
    "sqrt": sympy.sqrt,
    "cbrt": sympy.cbrt,
    "root": sympy.root,
    "exp": sympy.exp,
    "log": sympy.log,
    "ln": sympy.log,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "asin": sympy.asin,
    "acos": sympy.acos,
    "atan": sympy.atan,
    "sinh": sympy.sinh,
    "cosh": sympy.cosh,
    "tanh": sympy.tanh,
    "Abs": sympy.Abs,
    "abs": sympy.Abs,
    "factorial": sympy.factorial,
    "binomial": sympy.binomial,
    "gcd": sympy.gcd,
    "lcm": sympy.lcm,
    "Rational": sympy.Rational,
    "floor": sympy.floor,
    "ceiling": sympy.ceiling,
}

# Characters we allow in an incoming expression. Notably excludes ``_`` (blocks
# dunder names), ``[`` ``]`` ``{`` ``}`` ``:`` ``;`` ``=`` ``@`` and quotes.
_EXPR_WHITELIST = re.compile(r"^[0-9a-zA-Z+\-*/().,^%!\s]+$")

_PARSE_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)


def _calculate(expression: str) -> str:
    """Evaluate a math expression exactly with SymPy. Raises ValueError on bad input."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression must be a non-empty string.")
    expr = expression.strip()
    if len(expr) > 500:
        raise ValueError("expression is too long (max 500 characters).")
    if "__" in expr:
        raise ValueError("expression contains a forbidden token ('__').")
    if not _EXPR_WHITELIST.match(expr):
        raise ValueError(
            "expression contains characters that are not allowed. Use numbers, "
            "the operators + - * / ** %, parentheses, and known functions such "
            "as sqrt, sin, log, factorial, pi, e."
        )

    try:
        result = parse_expr(
            expr,
            local_dict=_ALLOWED_NAMES,
            transformations=_PARSE_TRANSFORMS,
            evaluate=True,
        )
    except Exception as exc:  # noqa: BLE001 - surface any parse failure cleanly
        raise ValueError(f"could not parse the expression: {exc}") from exc

    # If the result still has free symbols, it was not a pure number; return the
    # simplified symbolic form so the model knows a variable was involved.
    if getattr(result, "free_symbols", set()):
        return f"Simplified (symbolic): {sympy.simplify(result)}"

    exact = sympy.simplify(result)
    exact_str = str(exact)

    # A rational result (including integers) is complete on its own - the exact
    # fraction says everything, so we skip the noisy decimal expansion.
    if exact.is_rational:
        return f"Result: {exact_str}"

    # Irrational / transcendental numeric value: show the exact closed form and
    # a decimal approximation, which is the genuinely useful extra information.
    try:
        approx_str = str(sympy.N(result, 15))
    except Exception:  # noqa: BLE001
        return f"Exact: {exact_str}"
    return f"Exact: {exact_str}  |  Decimal (15 s.f.): {approx_str}"


@beta_tool
def calculate(expression: str) -> str:
    """Evaluate an arithmetic or symbolic math expression exactly, without floating-point error.

    Uses SymPy (not Python's eval), so it is safe and gives exact results for
    fractions, radicals and constants. Supports + - * / ** (power) % parentheses,
    and functions such as sqrt, cbrt, exp, log/ln, sin, cos, tan, factorial,
    binomial, gcd, lcm, Rational, plus the constants pi and e. Returns the exact
    simplified value and, when it differs, a 15-significant-figure decimal.

    Args:
        expression: The math expression to evaluate, e.g. "2/7 + 3/14",
            "sqrt(50)", "sin(pi/4)", or "factorial(12)".
    """
    try:
        output = _calculate(expression)
    except ValueError as exc:
        msg = f"Error: {exc}"
        trace_mod.active().record("calculate", {"expression": expression}, msg, ok=False)
        return msg
    trace_mod.active().record("calculate", {"expression": expression}, output, ok=True)
    return output


# --------------------------------------------------------------------------- #
# Tool 2: integer / number-theory utility                                      #
# --------------------------------------------------------------------------- #

_NUMBER_OPS = {"gcd", "lcm", "factorial", "is_prime", "prime_factorization", "to_base"}
_FACTORIAL_MAX = 1000
_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def _to_base(value: int, base: int) -> str:
    if not 2 <= base <= 36:
        raise ValueError("base must be between 2 and 36.")
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    n = abs(value)
    digits = []
    while n:
        n, rem = divmod(n, base)
        digits.append(_DIGITS[rem])
    return sign + "".join(reversed(digits))


def _number_tool(operation: str, a: int, b: int = 0) -> str:
    """Integer utility logic. Raises ValueError on bad input."""
    if operation not in _NUMBER_OPS:
        raise ValueError(
            f"unknown operation '{operation}'. Valid operations: "
            + ", ".join(sorted(_NUMBER_OPS))
            + "."
        )
    if not isinstance(a, int) or not isinstance(b, int):
        raise ValueError("a and b must be integers.")

    if operation == "gcd":
        return f"gcd({a}, {b}) = {math.gcd(a, b)}"
    if operation == "lcm":
        return f"lcm({a}, {b}) = {math.lcm(a, b)}"
    if operation == "factorial":
        if a < 0:
            raise ValueError("factorial is undefined for negative numbers.")
        if a > _FACTORIAL_MAX:
            raise ValueError(f"factorial argument too large (max {_FACTORIAL_MAX}).")
        return f"{a}! = {math.factorial(a)}"
    if operation == "is_prime":
        return f"is_prime({a}) = {bool(sympy.isprime(a))}"
    if operation == "prime_factorization":
        if a < 2:
            raise ValueError("prime_factorization needs an integer >= 2.")
        factors = sympy.factorint(a)  # {prime: exponent}
        pretty = " * ".join(
            f"{p}^{e}" if e > 1 else f"{p}" for p, e in sorted(factors.items())
        )
        return f"{a} = {pretty}"
    # operation == "to_base"
    return f"{a} in base {b} = {_to_base(a, b)}"


@beta_tool
def number_tool(operation: str, a: int, b: int = 0) -> str:
    """Exact integer and number-theory utility for whole numbers.

    Args:
        operation: Which operation to perform. One of:
            - "gcd": greatest common divisor of a and b.
            - "lcm": least common multiple of a and b.
            - "factorial": a! (a must be between 0 and 1000).
            - "is_prime": whether a is a prime number.
            - "prime_factorization": prime factorisation of a (a >= 2).
            - "to_base": write a (given in base 10) in base b, where b is 2-36.
        a: The primary integer operand.
        b: The secondary operand: the second number for "gcd"/"lcm", or the
            target base for "to_base". Ignored by the unary operations.
    """
    args = {"operation": operation, "a": a, "b": b}
    try:
        output = _number_tool(operation, a, b)
    except ValueError as exc:
        msg = f"Error: {exc}"
        trace_mod.active().record("number_tool", args, msg, ok=False)
        return msg
    trace_mod.active().record("number_tool", args, output, ok=True)
    return output


# --------------------------------------------------------------------------- #
# Tool 3: grounded lookup over a tiny local JSON knowledge base                #
# --------------------------------------------------------------------------- #

_KNOWLEDGE_PATH = Path(__file__).with_name("knowledge.json")


def _load_knowledge() -> list[dict]:
    with _KNOWLEDGE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("entries", [])


def _lookup(query: str) -> str:
    """Search the local knowledge base. Raises ValueError on bad input."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    q = query.strip().lower()
    entries = _load_knowledge()

    # Rank entries: exact id/alias match beats a substring match in name/aliases,
    # which beats a substring match in the summary.
    scored: list[tuple[int, dict]] = []
    for entry in entries:
        haystack_aliases = [entry["id"].lower()] + [a.lower() for a in entry.get("aliases", [])]
        name = entry.get("name", "").lower()
        summary = entry.get("summary", "").lower()
        if q in haystack_aliases or q == name:
            score = 3
        elif any(q in alias for alias in haystack_aliases) or q in name:
            score = 2
        elif q in summary:
            score = 1
        else:
            score = 0
        if score:
            scored.append((score, entry))

    if not scored:
        return (
            f"No entry found for '{query}'. The knowledge base covers: "
            + ", ".join(e.get("name", e["id"]) for e in entries)
            + "."
        )

    scored.sort(key=lambda pair: pair[0], reverse=True)
    lines = []
    for _, entry in scored[:3]:
        lines.append(
            f"- {entry.get('name')} [{entry.get('category')}]"
            f" | value: {entry.get('value')}\n  {entry.get('summary')}"
        )
    return "Knowledge base match(es):\n" + "\n".join(lines)


@beta_tool
def knowledge_lookup(query: str) -> str:
    """Look up a fact in the local knowledge base of math constants and concepts.

    Use this to ground factual claims (values of constants, definitions of
    concepts) instead of relying on memory. Returns up to three matching
    entries, each with its category, stored value and a short summary. If
    nothing matches, it lists what the knowledge base contains.

    Args:
        query: The term to look up, e.g. "Euler's number", "golden ratio",
            "Carmichael number", or "prime".
    """
    try:
        output = _lookup(query)
    except ValueError as exc:
        msg = f"Error: {exc}"
        trace_mod.active().record("knowledge_lookup", {"query": query}, msg, ok=False)
        return msg
    trace_mod.active().record("knowledge_lookup", {"query": query}, output, ok=True)
    return output


# All tools, in the order presented to the model.
TOOLS = [calculate, number_tool, knowledge_lookup]
