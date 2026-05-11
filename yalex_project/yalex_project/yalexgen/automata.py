from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from .regex_ast import Charset, Concat, EOFMarker, Epsilon, Literal, OptionalNode, Plus, RegexNode, Star, Tagged, UnionNode

EOF_SENTINEL = "<EOF>"


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


@dataclass
class DFA:
    start: int
    transitions: Dict[int, Dict[str, int]]
    accepts: Dict[int, int]  # dfa_state -> chosen rule index


@dataclass(frozen=True)
class _AcceptMarker(RegexNode):
    rule_index: int


@dataclass
class _DirectInfo:
    nullable: bool
    firstpos: FrozenSet[int]
    lastpos: FrozenSet[int]


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


class DirectDFACompiler:
    def __init__(self):
        self.followpos: Dict[int, Set[int]] = {}
        self.position_symbols: Dict[int, FrozenSet[str]] = {}
        self.accept_positions: Dict[int, int] = {}
        self._next_pos = 1

    def compile(self, rule_asts: List[RegexNode], alphabet: Iterable[str]) -> DFA:
        if not rule_asts:
            raise ValueError("At least one regex rule is required for direct DFA construction")

        root = self._augment_rules(rule_asts)
        info = self._analyze(root)
        alpha = list(alphabet)

        start_set = info.firstpos
        state_map: Dict[FrozenSet[int], int] = {start_set: 0}
        transitions: Dict[int, Dict[str, int]] = {}
        accepts: Dict[int, int] = {}
        unmarked: List[FrozenSet[int]] = [start_set]

        acc = self._accept_rule_of(start_set)
        if acc is not None:
            accepts[0] = acc

        while unmarked:
            current = unmarked.pop(0)
            current_id = state_map[current]
            transitions[current_id] = {}
            for ch in alpha:
                nxt: Set[int] = set()
                for pos in current:
                    if ch in self.position_symbols.get(pos, frozenset()):
                        nxt.update(self.followpos.get(pos, set()))
                next_set = frozenset(nxt)
                if not next_set:
                    continue
                if next_set not in state_map:
                    new_id = len(state_map)
                    state_map[next_set] = new_id
                    unmarked.append(next_set)
                    acc = self._accept_rule_of(next_set)
                    if acc is not None:
                        accepts[new_id] = acc
                transitions[current_id][ch] = state_map[next_set]

        return DFA(start=0, transitions=transitions, accepts=accepts)

    def _augment_rules(self, rule_asts: List[RegexNode]) -> RegexNode:
        augmented: List[RegexNode] = [
            Concat(ast, _AcceptMarker(rule_index=idx))
            for idx, ast in enumerate(rule_asts)
        ]
        root = augmented[0]
        for nxt in augmented[1:]:
            root = UnionNode(root, nxt)
        return root

    def _new_position(self, symbols: FrozenSet[str], accept_rule: Optional[int] = None) -> int:
        pos = self._next_pos
        self._next_pos += 1
        self.followpos[pos] = set()
        self.position_symbols[pos] = symbols
        if accept_rule is not None:
            self.accept_positions[pos] = accept_rule
        return pos

    def _analyze(self, node: RegexNode) -> _DirectInfo:
        if isinstance(node, Epsilon):
            return _DirectInfo(nullable=True, firstpos=frozenset(), lastpos=frozenset())
        if isinstance(node, Literal):
            pos = self._new_position(frozenset({node.char}))
            return _DirectInfo(nullable=False, firstpos=frozenset({pos}), lastpos=frozenset({pos}))
        if isinstance(node, EOFMarker):
            pos = self._new_position(frozenset({EOF_SENTINEL}))
            return _DirectInfo(nullable=False, firstpos=frozenset({pos}), lastpos=frozenset({pos}))
        if isinstance(node, Charset):
            pos = self._new_position(node.chars)
            return _DirectInfo(nullable=False, firstpos=frozenset({pos}), lastpos=frozenset({pos}))
        if isinstance(node, _AcceptMarker):
            pos = self._new_position(frozenset(), accept_rule=node.rule_index)
            return _DirectInfo(nullable=False, firstpos=frozenset({pos}), lastpos=frozenset({pos}))
        if isinstance(node, Tagged):
            return self._analyze(node.child)
        if isinstance(node, Concat):
            left = self._analyze(node.left)
            right = self._analyze(node.right)
            for pos in left.lastpos:
                self.followpos[pos].update(right.firstpos)
            firstpos = set(left.firstpos)
            if left.nullable:
                firstpos.update(right.firstpos)
            lastpos = set(right.lastpos)
            if right.nullable:
                lastpos.update(left.lastpos)
            return _DirectInfo(
                nullable=left.nullable and right.nullable,
                firstpos=frozenset(firstpos),
                lastpos=frozenset(lastpos),
            )
        if isinstance(node, UnionNode):
            left = self._analyze(node.left)
            right = self._analyze(node.right)
            return _DirectInfo(
                nullable=left.nullable or right.nullable,
                firstpos=frozenset(set(left.firstpos).union(right.firstpos)),
                lastpos=frozenset(set(left.lastpos).union(right.lastpos)),
            )
        if isinstance(node, Star):
            child = self._analyze(node.child)
            for pos in child.lastpos:
                self.followpos[pos].update(child.firstpos)
            return _DirectInfo(nullable=True, firstpos=child.firstpos, lastpos=child.lastpos)
        if isinstance(node, Plus):
            child = self._analyze(node.child)
            for pos in child.lastpos:
                self.followpos[pos].update(child.firstpos)
            return _DirectInfo(nullable=child.nullable, firstpos=child.firstpos, lastpos=child.lastpos)
        if isinstance(node, OptionalNode):
            child = self._analyze(node.child)
            return _DirectInfo(nullable=True, firstpos=child.firstpos, lastpos=child.lastpos)
        raise TypeError(f'Unsupported regex node for direct DFA construction: {type(node)!r}')

    def _accept_rule_of(self, positions: FrozenSet[int]) -> Optional[int]:
        rules = [self.accept_positions[pos] for pos in positions if pos in self.accept_positions]
        return min(rules) if rules else None


def regexes_to_direct_dfa(rule_asts: List[RegexNode], alphabet: Iterable[str]) -> DFA:
    return DirectDFACompiler().compile(rule_asts, alphabet)


def minimize_dfa(dfa: DFA, alphabet: Iterable[str]) -> DFA:
    alpha = list(alphabet)
    states = _all_dfa_states(dfa)
    if not states:
        return DFA(start=0, transitions={0: {}}, accepts={})

    dead_state = max(states) + 1
    complete_states = set(states)
    complete_states.add(dead_state)

    partitions: List[Set[int]] = []
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
        refined: List[Set[int]] = []
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
        for idx, group in enumerate(partitions)
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


def _all_dfa_states(dfa: DFA) -> Set[int]:
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
