"""LR(1) items and the CLOSURE1 / GOTO1 operations.

An :class:`LR1Item` extends an LR(0) item with a single terminal *lookahead*:
``[A -> α . B β, a]``.  CLOSURE1 adds, for each ``[A -> α . B β, a]``, the items
``[B -> . γ, b]`` for every ``b`` in ``FIRST(β a)`` — this lookahead propagation
is what makes LR(1)/LALR more precise than SLR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .first_follow import first_of_sequence
from .grammar import EPSILON, Production


@dataclass(frozen=True)
class LR1Item:
    """An LR(0) item plus a terminal lookahead."""

    production: Production
    dot: int
    lookahead: str

    def next_symbol(self) -> Optional[str]:
        if self.dot < len(self.production.body):
            return self.production.body[self.dot]
        return None

    def advance(self) -> "LR1Item":
        return LR1Item(self.production, self.dot + 1, self.lookahead)

    def is_complete(self) -> bool:
        return self.dot >= len(self.production.body)

    def core(self) -> tuple[Production, int]:
        """The lookahead-free LR(0) core, used to merge states into LALR."""
        return (self.production, self.dot)

    def __str__(self) -> str:
        body = list(self.production.body)
        body.insert(self.dot, ".")
        rhs = " ".join(body) if body != ["."] else "."
        return f"[{self.production.head} -> {rhs}, {self.lookahead}]"


LR1ItemSet = frozenset  # frozenset[LR1Item]


def closure1(
    items: LR1ItemSet,
    productions_by_head: dict[str, list[Production]],
    first: dict[str, set[str]],
) -> LR1ItemSet:
    """CLOSURE of a set of LR(1) items (Aho, Sethi, Ullman §4.7)."""
    result = set(items)
    changed = True
    while changed:
        changed = False
        for item in list(result):
            b_sym = item.next_symbol()
            if b_sym is None or b_sym not in productions_by_head:
                continue
            # Lookaheads for the new items: FIRST(beta + current lookahead).
            beta = item.production.body[item.dot + 1:]
            la_source = first_of_sequence(beta + (item.lookahead,), first)
            for prod in productions_by_head[b_sym]:
                for la in la_source:
                    if la == EPSILON:
                        continue
                    new_item = LR1Item(prod, 0, la)
                    if new_item not in result:
                        result.add(new_item)
                        changed = True
    return frozenset(result)


def goto1(
    items: LR1ItemSet,
    symbol: str,
    productions_by_head: dict[str, list[Production]],
    first: dict[str, set[str]],
) -> LR1ItemSet:
    """GOTO over LR(1) items: advance the dot past *symbol*, then CLOSURE1."""
    moved = {item.advance() for item in items if item.next_symbol() == symbol}
    return closure1(frozenset(moved), productions_by_head, first)


def merge_lookaheads(item_set: LR1ItemSet) -> list[str]:
    """Compact display: group items by LR(0) core, joining lookaheads.

    Returns lines like ``A -> α.β , a/b`` so a merged LALR state stays readable.
    """
    groups: dict[tuple, set[str]] = {}
    order: list[tuple] = []
    for item in item_set:
        key = item.core()
        if key not in groups:
            groups[key] = set()
            order.append(key)
        groups[key].add(item.lookahead)

    def core_str(prod: Production, dot: int) -> str:
        body = list(prod.body)
        body.insert(dot, ".")
        rhs = " ".join(body) if body != ["."] else "."
        return f"{prod.head} -> {rhs}"

    lines = []
    for prod, dot in order:
        las = "/".join(sorted(groups[(prod, dot)]))
        lines.append(f"{core_str(prod, dot)} , {las}")
    return sorted(lines)
