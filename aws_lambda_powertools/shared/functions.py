from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator


def slice_dictionary(data: dict, chunk_size: int) -> Generator[dict, None, None]:
    """Yield ``data`` split into consecutive chunks of at most ``chunk_size`` items."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive number of items")
    for i in range(0, len(data), chunk_size):
        yield {key: data[key] for key in itertools.islice(data, i, i + chunk_size)}


def dig(data: dict, path: str) -> object | None:
    """The value at dotted *path* in *data*, or None if any key along it is missing."""
    current: object = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def resolve_max_age(env_value: str | None, default: int) -> int:
    """Cache max-age in seconds from *env_value*, falling back to *default*.

    A value that is not a base-10 integer is ignored and *default* is returned.
    """
    if not env_value:
        return default
    try:
        return int(env_value)
    except ValueError:
        return default
