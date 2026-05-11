from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set, Tuple

EOF_SENTINEL = "<EOF>"


@dataclass
class DFA:
    start: int
    transitions: Dict[int, Dict[str, int]]
    accepts: Dict[int, int]  # dfa_state -> chosen rule index


def minimize_dfa(dfa: DFA, alphabet: Iterable[str]) -> DFA:
    alpha = list(alphabet)
    states = _all_dfa_states(dfa)
    if not states:
        return DFA(start=0, transitions={0: {}}, accepts={})

    dead_state = max(states) + 1
    complete_states = set(states)
    complete_states.add(dead_state)

    partitions: list[set[int]] = []
    non_accepts = {state for state in complete_states if state not in dfa.accepts}
    if non_accepts:
        partitions.append(non_accepts)
    for rule in sorted(set(dfa.accepts.values())):
        group = {state for state, accept_rule in dfa.accepts.items() if accept_rule == rule}
        if group:
            partitions.append(group)

    while True:
        class_of = {
            state: idx
            for idx, group in enumerate(partitions)
            for state in group
        }
        refined: list[set[int]] = []
        changed = False
        for group in partitions:
            buckets: Dict[Tuple[Optional[int], Tuple[int, ...]], Set[int]] = {}
            for state in group:
                signature = (
                    dfa.accepts.get(state),
                    tuple(class_of[_complete_transition(dfa, state, ch, dead_state)] for ch in alpha),
                )
                buckets.setdefault(signature, set()).add(state)
            refined.extend(buckets.values())
            if len(buckets) > 1:
                changed = True
        partitions = refined
        if not changed:
            break

    class_of = {
        state: idx
        for idx, group in enumerate(partitions)
        for state in group
    }
    reject_class = class_of[dead_state]
    start_class = class_of[dfa.start]

    output_classes = [
        idx
        for idx, _ in enumerate(partitions)
        if idx != reject_class or start_class == reject_class
    ]
    ordered_classes = [start_class] + [idx for idx in output_classes if idx != start_class]
    class_to_new = {class_idx: idx for idx, class_idx in enumerate(ordered_classes)}

    transitions: Dict[int, Dict[str, int]] = {idx: {} for idx in class_to_new.values()}
    accepts: Dict[int, int] = {}

    for class_idx in ordered_classes:
        new_state = class_to_new[class_idx]
        group = partitions[class_idx]
        real_states = sorted(state for state in group if state != dead_state)
        if not real_states:
            continue
        representative = real_states[0]
        if representative in dfa.accepts:
            accepts[new_state] = dfa.accepts[representative]
        for ch in alpha:
            target = _complete_transition(dfa, representative, ch, dead_state)
            target_class = class_of[target]
            if target_class == reject_class:
                continue
            transitions[new_state][ch] = class_to_new[target_class]

    return DFA(start=0, transitions=transitions, accepts=accepts)


def _all_dfa_states(dfa: DFA) -> set[int]:
    states = {dfa.start}
    states.update(dfa.transitions.keys())
    states.update(dfa.accepts.keys())
    for trans in dfa.transitions.values():
        states.update(trans.values())
    return states


def _complete_transition(dfa: DFA, state: int, ch: str, dead_state: int) -> int:
    if state == dead_state:
        return dead_state
    return dfa.transitions.get(state, {}).get(ch, dead_state)
