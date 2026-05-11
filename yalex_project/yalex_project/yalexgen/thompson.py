from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from .dfa import DFA, EOF_SENTINEL
from .regex_ast import Charset, Concat, EOFMarker, Epsilon, Literal, OptionalNode, Plus, RegexNode, Star, UnionNode


@dataclass
class NFAState:
    id: int
    eps: Set[int] = field(default_factory=set)
    trans: List[Tuple[FrozenSet[str], int]] = field(default_factory=list)
    accept_rule: Optional[int] = None


@dataclass
class NFAFragment:
    start: int
    end: int


@dataclass
class NFA:
    states: Dict[int, NFAState]
    start: int


class ThompsonCompiler:
    def __init__(self):
        self.states: Dict[int, NFAState] = {}
        self._next_id = 0

    def new_state(self) -> int:
        sid = self._next_id
        self._next_id += 1
        self.states[sid] = NFAState(id=sid)
        return sid

    def compile(self, node: RegexNode) -> NFAFragment:
        if isinstance(node, Epsilon):
            s = self.new_state()
            e = self.new_state()
            self.states[s].eps.add(e)
            return NFAFragment(s, e)
        if isinstance(node, Literal):
            s = self.new_state()
            e = self.new_state()
            self.states[s].trans.append((frozenset({node.char}), e))
            return NFAFragment(s, e)
        if isinstance(node, EOFMarker):
            s = self.new_state()
            e = self.new_state()
            self.states[s].trans.append((frozenset({EOF_SENTINEL}), e))
            return NFAFragment(s, e)
        if isinstance(node, Charset):
            s = self.new_state()
            e = self.new_state()
            self.states[s].trans.append((node.chars, e))
            return NFAFragment(s, e)
        if isinstance(node, Concat):
            left = self.compile(node.left)
            right = self.compile(node.right)
            self.states[left.end].eps.add(right.start)
            return NFAFragment(left.start, right.end)
        if isinstance(node, UnionNode):
            s = self.new_state()
            e = self.new_state()
            left = self.compile(node.left)
            right = self.compile(node.right)
            self.states[s].eps.update({left.start, right.start})
            self.states[left.end].eps.add(e)
            self.states[right.end].eps.add(e)
            return NFAFragment(s, e)
        if isinstance(node, Star):
            s = self.new_state()
            e = self.new_state()
            child = self.compile(node.child)
            self.states[s].eps.update({child.start, e})
            self.states[child.end].eps.update({child.start, e})
            return NFAFragment(s, e)
        if isinstance(node, Plus):
            child = self.compile(node.child)
            s = self.new_state()
            e = self.new_state()
            self.states[s].eps.add(child.start)
            self.states[child.end].eps.update({child.start, e})
            return NFAFragment(s, e)
        if isinstance(node, OptionalNode):
            s = self.new_state()
            e = self.new_state()
            child = self.compile(node.child)
            self.states[s].eps.update({child.start, e})
            self.states[child.end].eps.add(e)
            return NFAFragment(s, e)
        raise TypeError(f'Unsupported regex node for Thompson construction: {type(node)!r}')


def combine_rule_nfas(rule_asts: List[RegexNode]) -> NFA:
    compiler = ThompsonCompiler()
    start = compiler.new_state()
    for idx, ast in enumerate(rule_asts):
        frag = compiler.compile(ast)
        compiler.states[start].eps.add(frag.start)
        compiler.states[frag.end].accept_rule = idx
    return NFA(states=compiler.states, start=start)


def epsilon_closure(nfa: NFA, state_ids: Iterable[int]) -> FrozenSet[int]:
    stack = list(state_ids)
    closure = set(stack)
    while stack:
        sid = stack.pop()
        for nxt in nfa.states[sid].eps:
            if nxt not in closure:
                closure.add(nxt)
                stack.append(nxt)
    return frozenset(closure)


def move(nfa: NFA, states: Iterable[int], ch: str) -> FrozenSet[int]:
    out: Set[int] = set()
    for sid in states:
        for charset, tgt in nfa.states[sid].trans:
            if ch in charset:
                out.add(tgt)
    return frozenset(out)


def nfa_to_dfa(nfa: NFA, alphabet: Iterable[str]) -> DFA:
    alpha = list(alphabet)
    start_set = epsilon_closure(nfa, [nfa.start])
    state_map: Dict[FrozenSet[int], int] = {start_set: 0}
    transitions: Dict[int, Dict[str, int]] = {}
    accepts: Dict[int, int] = {}
    unmarked: List[FrozenSet[int]] = [start_set]

    def accept_rule_of(stateset: FrozenSet[int]) -> Optional[int]:
        rules = [nfa.states[sid].accept_rule for sid in stateset if nfa.states[sid].accept_rule is not None]
        return min(rules) if rules else None

    acc = accept_rule_of(start_set)
    if acc is not None:
        accepts[0] = acc

    while unmarked:
        current = unmarked.pop(0)
        current_id = state_map[current]
        transitions[current_id] = {}
        for ch in alpha:
            nxt = epsilon_closure(nfa, move(nfa, current, ch))
            if not nxt:
                continue
            if nxt not in state_map:
                new_id = len(state_map)
                state_map[nxt] = new_id
                unmarked.append(nxt)
                acc = accept_rule_of(nxt)
                if acc is not None:
                    accepts[new_id] = acc
            transitions[current_id][ch] = state_map[nxt]
    return DFA(start=0, transitions=transitions, accepts=accepts)
