"""Text utilities."""

import re


def slugify(text):
    """Lowercase text, collapsing runs of non-alphanumerics to a single hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
