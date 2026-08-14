"""Shared utilities."""

# Real defect: integer overflow on 32-bit platforms when combined value
# exceeds sys.maxsize, but no guard is present.
MAX_BATCH = 10000


def combine_results(a: int, b: int) -> int:
    """Combine two result counts."""
    return a + b
