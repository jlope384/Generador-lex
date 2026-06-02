"""Conflict diagnostics for the parse-table builders.

A :class:`Conflict` records a single ACTION cell that was assigned two
incompatible actions (shift/reduce or reduce/reduce).  :func:`format_conflict`
turns it into a human-readable line and :func:`report_conflicts` prints a block
of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Conflict:
    """An ACTION-table cell with two competing actions.

    Attributes:
        state:    Index of the automaton state (table row).
        symbol:   The terminal (table column) where the clash happens.
        existing: The action already stored in the cell.
        incoming: The action that clashed with it.
        kind:     ``"shift/reduce"`` or ``"reduce/reduce"``.
    """

    state: int
    symbol: str
    existing: object
    incoming: object
    kind: str


def _action_str(action, grammar=None) -> str:
    """Describe an action tuple ``(kind, value)`` for a message."""
    if not isinstance(action, tuple):
        return str(action)
    kind, value = action
    if kind == "shift":
        return f"shift -> I{value}"
    if kind == "reduce":
        if grammar is not None:
            n = grammar.production_index().get(value)
            if n is not None:
                return f"reduce r{n} ({value})"
        return f"reduce ({value})"
    if kind == "accept":
        return "accept"
    return str(action)


def format_conflict(conflict: Conflict, grammar=None) -> str:
    """Return a one-line description of *conflict*."""
    return (
        f"[{conflict.kind}] estado I{conflict.state}, símbolo '{conflict.symbol}': "
        f"{_action_str(conflict.existing, grammar)} vs "
        f"{_action_str(conflict.incoming, grammar)}"
    )


def report_conflicts(conflicts: list, grammar=None) -> None:
    """Print every conflict (accepts :class:`Conflict` objects or strings)."""
    if not conflicts:
        print("Sin conflictos: la gramática es compatible con el método elegido.")
        return
    print(f"Se detectaron {len(conflicts)} conflicto(s):")
    for c in conflicts:
        print("  " + (c if isinstance(c, str) else format_conflict(c, grammar)))
