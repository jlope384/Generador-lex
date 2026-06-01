"""Context-free grammar model for YAPar.

A :class:`Grammar` is the in-memory representation of the *PRODUCCIONES*
section of a ``.yalp`` file once the token section has already been read by
:mod:`yapargen.yapar_reader`.  Terminals are the uppercase token names declared
with ``%token``; non-terminals are the lowercase production names.

Two sentinels are used throughout the parser-generator:

* :data:`EPSILON` (the empty string) marks the empty production body / the
  empty string in FIRST sets.
* :data:`END_MARKER` (``"$"``) is the synthetic end-of-input terminal added by
  :meth:`Grammar.augment`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Sentinels shared by every module in the package.
EPSILON = ""          # empty production body / epsilon in FIRST sets
END_MARKER = "$"       # end-of-input terminal in the augmented grammar


@dataclass(frozen=True)
class Production:
    """A single grammar rule ``head -> body``.

    ``body`` is a tuple of symbol names (terminals or non-terminals).  An empty
    tuple represents an epsilon production (``head -> ε``).  The class is frozen
    and hashable so productions can live inside the frozensets that make up
    LR item sets.
    """

    head: str
    body: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.body)

    def is_epsilon(self) -> bool:
        return len(self.body) == 0

    def __str__(self) -> str:
        rhs = " ".join(self.body) if self.body else "ε"
        return f"{self.head} -> {rhs}"


@dataclass
class Grammar:
    """A context-free grammar.

    Attributes:
        terminals:     Set of terminal symbols (uppercase token names, plus
                       :data:`END_MARKER` once augmented).
        non_terminals: Set of non-terminal symbols (lowercase production names).
        productions:   Ordered list of :class:`Production`.  Order matters: it
                       fixes the rule numbers (``R1``, ``R2`` ...) shown in the
                       parse table and the priority used to break reduce/reduce
                       conflicts.
        start:         The start symbol (head of the first production, or the
                       augmented start ``S'`` after :meth:`augment`).
    """

    terminals: set[str] = field(default_factory=set)
    non_terminals: set[str] = field(default_factory=set)
    productions: list[Production] = field(default_factory=list)
    start: str = ""

    # ── construction helpers ───────────────────────────────────────────────
    def add_production(self, head: str, body: tuple[str, ...]) -> Production:
        """Append a production and register its head as a non-terminal."""
        p = Production(head, tuple(body))
        self.productions.append(p)
        self.non_terminals.add(head)
        if not self.start:
            self.start = head
        return p

    # ── queries ────────────────────────────────────────────────────────────
    def symbols(self) -> set[str]:
        """All grammar symbols (terminals ∪ non-terminals)."""
        return self.terminals | self.non_terminals

    def is_terminal(self, symbol: str) -> bool:
        return symbol in self.terminals

    def is_non_terminal(self, symbol: str) -> bool:
        return symbol in self.non_terminals

    def productions_for(self, head: str) -> list[Production]:
        """Every production whose left-hand side is *head*."""
        return [p for p in self.productions if p.head == head]

    def productions_by_head(self) -> dict[str, list[Production]]:
        """Map each non-terminal to the list of its productions."""
        table: dict[str, list[Production]] = {nt: [] for nt in self.non_terminals}
        for p in self.productions:
            table.setdefault(p.head, []).append(p)
        return table

    def production_index(self) -> dict[Production, int]:
        """Map each production to its position in :attr:`productions`."""
        return {p: i for i, p in enumerate(self.productions)}

    def ordered_symbols(self) -> list[str]:
        """A deterministic symbol order: non-terminals (by first appearance as a
        head) then terminals (by first appearance in a body).

        Iterating GOTO over this order during a BFS of the item sets reproduces
        a stable, reviewer-friendly state numbering (``I0``, ``I1`` ...).
        ``END_MARKER`` is intentionally excluded — it never labels a transition.
        """
        seen: set[str] = set()
        ordered: list[str] = []
        for p in self.productions:
            if p.head not in seen:
                seen.add(p.head)
                ordered.append(p.head)
        for p in self.productions:
            for sym in p.body:
                if sym in self.terminals and sym not in seen:
                    seen.add(sym)
                    ordered.append(sym)
        return ordered

    # ── augmentation ────────────────────────────────────────────────────────
    def augment(self) -> "Grammar":
        """Return a new grammar with a fresh start production ``S' -> S``.

        The augmented grammar adds:

        * a unique start symbol (``start`` plus one or more ``'``) whose single
          production points at the original start symbol, and
        * the :data:`END_MARKER` terminal.

        The original grammar is left untouched.  The augmented production is
        always ``productions[0]`` — reducing by it means *accept*.
        """
        if not self.start:
            raise ValueError("cannot augment a grammar without a start symbol")

        new_start = self.start + "'"
        while new_start in self.non_terminals or new_start in self.terminals:
            new_start += "'"

        aug = Grammar(
            terminals=set(self.terminals) | {END_MARKER},
            non_terminals=set(self.non_terminals) | {new_start},
            productions=[Production(new_start, (self.start,))] + list(self.productions),
            start=new_start,
        )
        return aug

    def __str__(self) -> str:
        lines = [f"start = {self.start}"]
        for i, p in enumerate(self.productions):
            lines.append(f"  ({i}) {p}")
        return "\n".join(lines)
