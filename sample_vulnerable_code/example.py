"""
A small arithmetic module used as CodeGuardian's "clean code" sample —
documented, tested, no secrets, no complexity red flags. Contrast with
sample_vulnerable_code, which is intentionally broken.
"""


def add(a, b):
    """Return the sum of a and b."""
    return a + b


def subtract(a, b):
    """Return a minus b."""
    return a - b


def multiply(a, b):
    """Return the product of a and b."""
    return a * b


def divide(a, b):
    """Return a divided by b.

    Raises:
        ValueError: if b is zero.
    """
    if b == 0:
        raise ValueError("cannot divide by zero")
    return a / b


class Calculator:
    """A stateful calculator that accumulates a running total."""

    def __init__(self, start=0):
        """Initialize the running total to `start`."""
        self.total = start

    def add(self, value):
        """Add `value` to the running total and return the new total."""
        self.total += value
        return self.total

    def reset(self):
        """Reset the running total to zero and return it."""
        self.total = 0
        return self.total
