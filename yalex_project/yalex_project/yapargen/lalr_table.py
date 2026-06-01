"""LALR(1) parse-table construction from the merged LR(1) automaton.

Identical in structure to the SLR builder, with one crucial difference: a
complete item ``[A -> α ., a]`` triggers a reduce **only on its own lookahead
``a``**, not on the whole of ``FOLLOW(A)``.  These tighter lookaheads are what
let LALR(1) accept grammars that are not SLR(1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, Union

from .diagnostics import Conflict, format_conflict
from .grammar import END_MARKER, Grammar, Production
from .lalr_automaton import LALRAutomaton

# Same action shape as the SLR table.
Action = Tuple[str, Union[int, Production, None]]


@dataclass
class LALRTable:
    """ACTION / GOTO tables for an LALR(1) parser.

    Shares its public shape with :class:`~yapargen.slr_table.SLRTable`, so the
    same parsing engine, formatter and code generator handle both.
    """

    action: dict[tuple[int, str], Action] = field(default_factory=dict)
    goto: dict[tuple[int, str], int] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    grammar: Optional[Grammar] = None
    kind: str = "LALR"

    @property
    def is_conflict_free(self) -> bool:
        return not self.conflicts


def build_lalr_table(grammar: Grammar, automaton: LALRAutomaton) -> LALRTable:
    """Build the LALR(1) ACTION/GOTO table for *automaton*."""
    aug = automaton.grammar
    table = LALRTable(grammar=aug, kind="LALR")
    conflicts: list[Conflict] = []

    def set_action(state: int, terminal: str, act: Action) -> None:
        key = (state, terminal)
        existing = table.action.get(key)
        if existing is not None and existing != act:
            kind = _conflict_kind(existing, act)
            conflicts.append(Conflict(state, terminal, existing, act, kind))
            if existing[0] == "shift":
                return
            if act[0] != "shift" and _rule_no(aug, existing) <= _rule_no(aug, act):
                return
        table.action[key] = act

    for i, item_set in enumerate(automaton.states):
        for item in item_set:
            nxt = item.next_symbol()
            if nxt is not None and nxt in aug.terminals:
                j = automaton.transitions.get((i, nxt))
                if j is not None:
                    set_action(i, nxt, ("shift", j))
            elif nxt is None:
                # Complete item: accept on S', else reduce on THIS item's lookahead.
                if item.production.head == aug.start:
                    if item.lookahead == END_MARKER:
                        set_action(i, END_MARKER, ("accept", None))
                else:
                    set_action(i, item.lookahead, ("reduce", item.production))
        for nt in aug.non_terminals:
            j = automaton.transitions.get((i, nt))
            if j is not None:
                table.goto[(i, nt)] = j

    table.conflicts = [format_conflict(c, aug) for c in conflicts]
    return table


def _rule_no(grammar: Grammar, action: Action) -> int:
    if action[0] == "reduce":
        return grammar.production_index().get(action[1], 1 << 30)
    return 1 << 30


def _conflict_kind(a: Action, b: Action) -> str:
    kinds = {a[0], b[0]}
    if "shift" in kinds and "reduce" in kinds:
        return "shift/reduce"
    if kinds == {"reduce"}:
        return "reduce/reduce"
    return "conflicto"
