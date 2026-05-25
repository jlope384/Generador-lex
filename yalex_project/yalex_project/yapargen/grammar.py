from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Production:
    head: str
    body: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.body)

    def __repr__(self) -> str:
        body_str = ' '.join(self.body) if self.body else 'ε'
        return f"{self.head} -> {body_str}"


@dataclass
class Grammar:
    terminals: set[str] = field(default_factory=set)
    non_terminals: set[str] = field(default_factory=set)
    productions: list[Production] = field(default_factory=list)
    start: str = ""

    def add_production(self, head: str, body: tuple[str, ...]) -> Production:
        prod = Production(head, body)
        self.productions.append(prod)
        self.non_terminals.add(head)
        return prod

    def augment(self) -> Grammar:
        raise NotImplementedError
