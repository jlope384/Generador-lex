from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Set

from .dfa import DFA, EOF_SENTINEL
from .regex_ast import Charset, Concat, EOFMarker, Epsilon, Literal, OptionalNode, Plus, RegexNode, Star, Tagged, UnionNode


@dataclass(frozen=True)
class _AcceptMarker(RegexNode):
    rule_index: int


@dataclass
class _DirectInfo:
    nullable: bool
    firstpos: FrozenSet[int]
    lastpos: FrozenSet[int]


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
