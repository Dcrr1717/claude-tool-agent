"""Unit tests for the pure tool logic.

These run without an API key and without network access: they exercise the
``_calculate`` / ``_number_tool`` / ``_lookup`` functions directly, which is
where all validation and computation live. Run with:  pytest -q
"""

import sys
from pathlib import Path

import pytest

# Make the project root importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _calculate, _lookup, _number_tool  # noqa: E402


# --------------------------- calculate ------------------------------------- #

def test_calculate_exact_fraction():
    # 2/7 + 3/14 = 4/14 + 3/14 = 7/14 = 1/2
    assert _calculate("2/7 + 3/14") == "Result: 1/2"


def test_calculate_radical_has_exact_and_decimal():
    out = _calculate("sqrt(50)")
    assert "2*sqrt(2)" in out or "5*sqrt(2)" in out  # sympy renders 5*sqrt(2)
    assert "Decimal" in out


def test_calculate_factorial_function():
    assert "479001600" in _calculate("factorial(12)")


def test_calculate_rejects_dunder():
    with pytest.raises(ValueError):
        _calculate("__import__('os')")


def test_calculate_rejects_disallowed_chars():
    with pytest.raises(ValueError):
        _calculate("x = 5")  # '=' is not whitelisted


def test_calculate_rejects_empty():
    with pytest.raises(ValueError):
        _calculate("   ")


# --------------------------- number_tool ----------------------------------- #

def test_number_gcd():
    assert _number_tool("gcd", 561, 357) == "gcd(561, 357) = 51"


def test_number_lcm():
    assert _number_tool("lcm", 4, 6) == "lcm(4, 6) = 12"


def test_number_factorial():
    assert _number_tool("factorial", 5) == "5! = 120"


def test_number_factorial_too_large():
    with pytest.raises(ValueError):
        _number_tool("factorial", 5000)


def test_number_is_prime_carmichael():
    # 561 is the smallest Carmichael number - composite, not prime.
    assert _number_tool("is_prime", 561) == "is_prime(561) = False"


def test_number_prime_factorization():
    assert _number_tool("prime_factorization", 561) == "561 = 3 * 11 * 17"


def test_number_to_base():
    assert _number_tool("to_base", 255, 16) == "255 in base 16 = ff"


def test_number_to_base_rejects_bad_base():
    with pytest.raises(ValueError):
        _number_tool("to_base", 10, 99)


def test_number_unknown_operation():
    with pytest.raises(ValueError):
        _number_tool("sqrt", 9)


# --------------------------- lookup ---------------------------------------- #

def test_lookup_by_alias():
    out = _lookup("Euler's number")
    assert "Euler's number" in out
    assert "2.718281828" in out


def test_lookup_by_concept():
    assert "Carmichael" in _lookup("carmichael number")


def test_lookup_miss_lists_contents():
    out = _lookup("quaternion")
    assert "No entry found" in out


def test_lookup_rejects_empty():
    with pytest.raises(ValueError):
        _lookup("")
