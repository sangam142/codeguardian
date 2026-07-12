"""Tests for calculator.py — exercises every public function and class."""
import pytest

from calculator import Calculator, add, divide, multiply, subtract


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2


def test_multiply():
    assert multiply(4, 3) == 12


def test_divide():
    assert divide(10, 2) == 5


def test_divide_by_zero_raises():
    with pytest.raises(ValueError):
        divide(1, 0)


def test_calculator_accumulates_and_resets():
    calc = Calculator()
    assert calc.add(5) == 5
    assert calc.add(3) == 8
    assert calc.reset() == 0
