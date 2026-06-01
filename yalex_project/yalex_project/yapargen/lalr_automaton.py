"""LALR(1) automaton construction by *core merging*.

The implementation follows the most transparent textbook route:

1. build the **canonical LR(1) collection** (CLOSURE1 / GOTO1 over a BFS), then
2. **merge** any states sharing the same LR(0) core (their items modulo the
   lookahead), unioning the lookaheads.

The result has exactly as many states as the LR(0) automaton, but each reduce
item carries a precise lookahead set — the defining property of LALR(1).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .first_follow import compute_first
from .grammar import Grammar
from .lr1_items import LR1Item, LR1ItemSet, closure1, goto1


@dataclass
class LALRAutomaton:
    """LALR(1) automaton (LR(0)-sized, with merged lookaheads).

    Attributes:
        states:      Merged LR(1) item sets; ``states[i]`` is state ``Ii``.
        transitions: ``(state, symbol) -> state`` GOTO table.
        start_state: Index of the initial state (always 0).
        grammar:     The augmented grammar the automaton was built from.
    """

    states: list[LR1ItemSet] = field(default_factory=list)
    transitions: dict[tuple[int, str], int] = field(default_factory=dict)
    start_state: int = 0
    grammar: Grammar = None  # type: ignore[assignment]

    def goto_of(self, state: int, symbol: str):
        return self.transitions.get((state, symbol))


def _core(item_set: LR1ItemSet) -> frozenset:
    """The lookahead-free LR(0) core of an LR(1) item set."""
    return frozenset(item.core() for item in item_set)


def build_canonical_lr1(grammar: Grammar):
    """Build the canonical LR(1) collection; returns (aug, states, transitions)."""
    aug = grammar.augment()
    pbh = aug.productions_by_head()
    first = compute_first(aug)
    symbols = aug.ordered_symbols()

    from .grammar import END_MARKER
    start = closure1(
        frozenset({LR1Item(aug.productions[0], 0, END_MARKER)}), pbh, first
    )
    states: list[LR1ItemSet] = [start]
    index: dict[LR1ItemSet, int] = {start: 0}
    transitions: dict[tuple[int, str], int] = {}

    queue: deque[int] = deque([0])
    while queue:
        i = queue.popleft()
        current = states[i]
        for sym in symbols:
            target = goto1(current, sym, pbh, first)
            if not target:
                continue
            j = index.get(target)
            if j is None:
                j = len(states)
                index[target] = j
                states.append(target)
                queue.append(j)
            transitions[(i, sym)] = j

    return aug, states, transitions


def build_lalr_automaton(grammar: Grammar) -> LALRAutomaton:
    """Build the LALR(1) automaton for *grammar* (original, non-augmented)."""
    aug, lr1_states, lr1_transitions = build_canonical_lr1(grammar)

    # Group LR(1) states by their LR(0) core, preserving first-seen order so the
    # start state stays at index 0 and numbering is stable.
    core_to_merged: dict[frozenset, int] = {}
    merged_members: list[list[int]] = []
    old_to_new: dict[int, int] = {}
    for old_idx, state in enumerate(lr1_states):
        core = _core(state)
        new_idx = core_to_merged.get(core)
        if new_idx is None:
            new_idx = len(merged_members)
            core_to_merged[core] = new_idx
            merged_members.append([])
        old_to_new[old_idx] = new_idx
        merged_members[new_idx].append(old_idx)

    # Merge the item sets (union of lookaheads within a shared core).
    merged_states: list[LR1ItemSet] = []
    for members in merged_members:
        union: set[LR1Item] = set()
        for old_idx in members:
            union |= set(lr1_states[old_idx])
        merged_states.append(frozenset(union))

    # Remap transitions; merging is consistent so this is well-defined.
    transitions: dict[tuple[int, str], int] = {}
    for (i, sym), j in lr1_transitions.items():
        transitions[(old_to_new[i], sym)] = old_to_new[j]

    return LALRAutomaton(
        states=merged_states,
        transitions=transitions,
        start_state=old_to_new[0],
        grammar=aug,
    )
