"""Row ordering.

RKIK house style: a TK opens with the informative rows that describe what the Contracting
Authority wants -- purpose, intended use, scope -- before any testable requirement. So the
sort key is (informative block first, then category order, then original order).

The same rule is applied to both study arms, so the order of rows in an exported file
carries no signal about which arm produced it.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from app.categories import category_order, normalise_key


class HasOrdering(Protocol):
    classification: str
    category: str


def sort_key(row: Any, order_index: dict[str, int], position: int) -> tuple[int, int, int]:
    is_informative = 0 if getattr(row, "classification", "M") == "I" else 1
    key = normalise_key(getattr(row, "category", "") or "")
    return (is_informative, order_index.get(key, len(order_index)), position)


def order_rows(rows: Sequence[Any], headings: list[str]) -> list[Any]:
    """Return the rows in TK order. Does not mutate the input sequence."""
    index = category_order([getattr(r, "category", "") or "" for r in rows], headings)
    decorated = [(sort_key(row, index, position), row) for position, row in enumerate(rows)]
    decorated.sort(key=lambda pair: pair[0])
    return [row for _, row in decorated]


def renumber(rows: Sequence[Any], start: int = 0) -> None:
    """Write the sequence position back onto each row's `order` attribute."""
    for position, row in enumerate(rows, start=start):
        row.order = position
