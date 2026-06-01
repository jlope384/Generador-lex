"""SLR(1) parse-table construction from an LR(0) automaton.

The SLR(1) method (Aho, Sethi, Ullman, Algorithm 4.46) reuses the LR(0) item
sets and resolves *where to reduce* with the FOLLOW set of the reduced
non-terminal:

* shift on terminals that label a GOTO edge,
* reduce ``A -> α`` on every terminal in ``FOLLOW(A)``,
* accept on ``$`` for the item ``S' -> S .``.

Conflicts (two different actions for the same cell) are recorded rather than
silently overwritten, so the tool can report grammars that are not SLR(1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, Union

from .diagnostics import Conflict, format_conflict
from .first_follow import compute_first, compute_follow
from .grammar import END_MARKER, Grammar, Production
from .lr0_automaton import LR0Automaton

# An action is one of:
#   ("shift",  state_index:int)
#   ("reduce", Production)
#   ("accept", None)
Action = Tuple[str, Union[int, Production, None]]


@dataclass
class SLRTable:
    """ACTION / GOTO tables for an SLR(1) parser.

    Attributes:
        action:    ``(state, terminal) -> Action``.
        goto:      ``(state, non-terminal) -> state``.
        conflicts: Human-readable conflict descriptions (empty ⇒ grammar is
                   SLR(1)).
        grammar:   The augmented grammar (for rule numbering / display).
        kind:      ``"SLR"`` — handy when a table is passed around generically.
    """

    action: dict[tuple[int, str], Action] = field(default_factory=dict)
    goto: dict[tuple[int, str], int] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    grammar: Optional[Grammar] = None
    kind: str = "SLR"

    @property
    def is_conflict_free(self) -> bool:
        return not self.conflicts


def build_slr_table(grammar: Grammar, automaton: LR0Automaton) -> SLRTable:
    """Build the SLR(1) ACTION/GOTO table for *automaton*.

    *grammar* may be the original grammar; the augmented grammar carried by the
    automaton (``automaton.grammar``) is the authoritative source for FOLLOW and
    rule numbering.
    """
    aug = automaton.grammar
    first = compute_first(aug)
    follow = compute_follow(aug, first)

    table = SLRTable(grammar=aug, kind="SLR")
    conflicts: list[Conflict] = []

    def set_action(state: int, terminal: str, act: Action) -> None:
        key = (state, terminal)
        existing = table.action.get(key)
        if existing is not None and existing != act:
            kind = _conflict_kind(existing, act)
            conflicts.append(Conflict(state, terminal, existing, act, kind))
            # Keep the shift (yacc-style: prefer shift over reduce); for
            # reduce/reduce keep the earlier (lower-numbered) production.
            if existing[0] == "shift":
                return
            if act[0] != "shift" and _rule_no(aug, existing) <= _rule_no(aug, act):
                return
        table.action[key] = act

    for i, item_set in enumerate(automaton.states):
        for item in item_set:
            nxt = item.next_symbol()
            if nxt is not None and nxt in aug.terminals:
                # shift
                j = automaton.transitions.get((i, nxt))
                if j is not None:
                    set_action(i, nxt, ("shift", j))
            elif nxt is None:
                # complete item -> reduce or accept
                if item.production.head == aug.start:
                    set_action(i, END_MARKER, ("accept", None))
                else:
                    for terminal in follow[item.production.head]:
                        set_action(i, terminal, ("reduce", item.production))
        # GOTO for non-terminals
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


# ── pretty printing (shared by SLR and LALR tables) ─────────────────────────
def format_table(table: SLRTable, automaton: Optional[LR0Automaton] = None) -> str:
    """Render an ACTION/GOTO table as an aligned text grid (yacc-like).

    Works for any table object exposing ``action``, ``goto`` and ``grammar``
    (both :class:`SLRTable` and ``LALRTable`` qualify).
    """
    grammar = table.grammar
    n_states = 1 + max(
        [s for (s, _t) in table.action] + [s for (s, _n) in table.goto] + [0]
    )
    prod_index = grammar.production_index()

    terminals = [t for t in grammar.ordered_symbols() if t in grammar.terminals]
    terminals.append(END_MARKER)
    non_terminals = [
        nt for nt in grammar.ordered_symbols() if nt in grammar.non_terminals
    ]
    # The augmented start never appears as a GOTO target column; drop it.
    non_terminals = [nt for nt in non_terminals if nt != grammar.start]

    def cell(state: int, sym: str) -> str:
        if sym in grammar.terminals or sym == END_MARKER:
            act = table.action.get((state, sym))
            if act is None:
                return ""
            if act[0] == "shift":
                return f"s{act[1]}"
            if act[0] == "reduce":
                return f"r{prod_index[act[1]]}"
            if act[0] == "accept":
                return "acc"
        else:
            j = table.goto.get((state, sym))
            return str(j) if j is not None else ""
        return ""

    headers = ["Estado"] + terminals + non_terminals
    rows = [headers]
    for s in range(n_states):
        rows.append([str(s)] + [cell(s, sym) for sym in terminals + non_terminals])

    widths = [max(len(r[c]) for r in rows) for c in range(len(headers))]
    sep = "-+-".join("-" * w for w in widths)
    out = []
    title = f"Tabla de parseo {table.kind}(1)"
    out.append(title)
    out.append("=" * len(title))
    out.append(" | ".join(h.center(widths[c]) for c, h in enumerate(rows[0])))
    out.append(sep)
    for r in rows[1:]:
        out.append(" | ".join(v.center(widths[c]) for c, v in enumerate(r)))

    # Legend of rule numbers.
    out.append("")
    out.append("Reglas (r#):")
    for k, p in enumerate(grammar.productions):
        tag = "accept (S' -> S)" if k == 0 else f"r{k}"
        out.append(f"  {tag}: {p}")
    return "\n".join(out)
