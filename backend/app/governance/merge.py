"""Order-preserving deduplication shared by the rule table and the aggregator."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from app.intake.schema import Obligation


def unique[T](items: Iterable[T], key: Callable[[T], object]) -> list[T]:
    """Keep the first occurrence of each ``key(item)``, in input order."""
    seen: set[object] = set()
    kept: list[T] = []
    for item in items:
        item_key = key(item)
        if item_key not in seen:
            seen.add(item_key)
            kept.append(item)
    return kept


def identity[T](item: T) -> T:
    return item


def obligation_key(item: Obligation) -> tuple[str, str, str | None, str | None]:
    return (item.framework, item.text, item.reference, item.role)
