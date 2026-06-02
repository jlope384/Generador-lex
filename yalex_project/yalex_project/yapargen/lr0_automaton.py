"""Construction of the LR(0) automaton (the canonical collection of item sets).

``build_lr0_automaton`` augments the grammar, seeds the start state with
``CLOSURE({S' -> . S})`` and grows the collection breadth-first, recording a
``GOTO`` transition for every (state, symbol) pair.  The BFS order combined with
:meth:`Grammar.ordered_symbols` yields a stable ``I0, I1, ...`` numbering.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .grammar import Grammar
from .lr0_items import ItemSet, LR0Item, closure, goto


@dataclass
class LR0Automaton:
    """A deterministic automaton over LR(0) item sets.

    Attributes:
        states:      List of item sets; ``states[i]`` is state ``Ii``.
        transitions: ``(state_index, symbol) -> state_index`` GOTO table.
        start_state: Index of the initial state (always 0).
        grammar:     The **augmented** grammar the automaton was built from
                     (downstream table builders read FOLLOW/productions from it).
    """

    states: list[ItemSet] = field(default_factory=list)
    transitions: dict[tuple[int, str], int] = field(default_factory=dict)
    start_state: int = 0
    grammar: Grammar = None  # type: ignore[assignment]

    def goto_of(self, state: int, symbol: str):
        """Convenience accessor for the GOTO table (``None`` when absent)."""
        return self.transitions.get((state, symbol))


def build_lr0_automaton(grammar: Grammar) -> LR0Automaton:
    """Build the LR(0) automaton for *grammar*.

    *grammar* is the original (non-augmented) grammar; it is augmented here so
    the automaton owns a single, canonical augmented grammar.
    """
    aug = grammar.augment()
    pbh = aug.productions_by_head()
    symbols = aug.ordered_symbols()

    start = closure(frozenset({LR0Item(aug.productions[0], 0)}), pbh)
    states: list[ItemSet] = [start]
    index: dict[ItemSet, int] = {start: 0}
    transitions: dict[tuple[int, str], int] = {}

    queue: deque[int] = deque([0])
    while queue:
        i = queue.popleft()
        current = states[i]
        for sym in symbols:
            target = goto(current, sym, pbh)
            if not target:
                continue
            j = index.get(target)
            if j is None:
                j = len(states)
                index[target] = j
                states.append(target)
                queue.append(j)
            transitions[(i, sym)] = j

    return LR0Automaton(
        states=states,
        transitions=transitions,
        start_state=0,
        grammar=aug,
    )
