"""LR(0) items and the CLOSURE / GOTO operations.

An :class:`LR0Item` is a production with a dot marking how much of the body has
already been seen, e.g. ``A -> α . B β``.  CLOSURE expands a set of items by
adding the productions of every non-terminal that appears immediately after a
dot; GOTO moves the dot across a single grammar symbol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .grammar import Production


@dataclass(frozen=True)
class LR0Item:
    """A production with a dot position (``dot`` chars into ``production.body``)."""

    production: Production
    dot: int

    def next_symbol(self) -> Optional[str]:
        """Symbol immediately right of the dot, or ``None`` if the dot is at the end."""
        if self.dot < len(self.production.body):
            return self.production.body[self.dot]
        return None

    def advance(self) -> "LR0Item":
        """Return the same item with the dot moved one symbol to the right."""
        return LR0Item(self.production, self.dot + 1)

    def is_complete(self) -> bool:
        """True when the dot is at the end (``A -> α .``) — a reduce item."""
        return self.dot >= len(self.production.body)

    def __str__(self) -> str:
        body = list(self.production.body)
        body.insert(self.dot, ".")
        rhs = " ".join(body) if body != ["."] else "."
        return f"{self.production.head} -> {rhs}"


ItemSet = frozenset  # frozenset[LR0Item]


def closure(items: ItemSet, productions_by_head: dict[str, list[Production]]) -> ItemSet:
    """CLOSURE(I): add ``B -> . γ`` for every ``A -> α . B β`` until stable.

    *productions_by_head* doubles as the non-terminal oracle: a symbol is a
    non-terminal exactly when it is a key of this dict.
    """
    result = set(items)
    worklist = list(items)
    while worklist:
        item = worklist.pop()
        sym = item.next_symbol()
        if sym is None or sym not in productions_by_head:
            continue
        for prod in productions_by_head[sym]:
            new_item = LR0Item(prod, 0)
            if new_item not in result:
                result.add(new_item)
                worklist.append(new_item)
    return frozenset(result)


def goto(items: ItemSet, symbol: str, productions_by_head: dict[str, list[Production]]) -> ItemSet:
    """GOTO(I, X): CLOSURE of every item in *items* with the dot moved over *X*."""
    moved = {
        item.advance()
        for item in items
        if item.next_symbol() == symbol
    }
    return closure(frozenset(moved), productions_by_head)
