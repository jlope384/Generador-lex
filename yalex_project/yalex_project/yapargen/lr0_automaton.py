from __future__ import annotations

from dataclasses import dataclass, field

from .grammar import Grammar
from .lr0_items import ItemSet


@dataclass
class LR0Automaton:
    states: list[ItemSet] = field(default_factory=list)
    transitions: dict[tuple[int, str], int] = field(default_factory=dict)
    start_state: int = 0

    @property
    def num_states(self) -> int:
        return len(self.states)


def build_lr0_automaton(grammar: Grammar) -> LR0Automaton:
    raise NotImplementedError
