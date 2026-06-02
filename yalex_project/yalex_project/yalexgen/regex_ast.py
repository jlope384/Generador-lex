from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Optional


class RegexNode:
    pass


@dataclass(frozen=True)
class Epsilon(RegexNode):
    pass


@dataclass(frozen=True)
class EOFMarker(RegexNode):
    pass


@dataclass(frozen=True)
class Literal(RegexNode):
    char: str


@dataclass(frozen=True)
class Charset(RegexNode):
    chars: FrozenSet[str]
    label: Optional[str] = None


@dataclass(frozen=True)
class Concat(RegexNode):
    left: RegexNode
    right: RegexNode


@dataclass(frozen=True)
class UnionNode(RegexNode):
    left: RegexNode
    right: RegexNode


@dataclass(frozen=True)
class Star(RegexNode):
    child: RegexNode


@dataclass(frozen=True)
class Plus(RegexNode):
    child: RegexNode


@dataclass(frozen=True)
class OptionalNode(RegexNode):
    child: RegexNode


@dataclass(frozen=True)
class Tagged(RegexNode):
    """Wrapper used only for visualization of per-rule roots."""
    child: RegexNode
    tag: str


EPSILON = Epsilon()
EOF_NODE = EOFMarker()
