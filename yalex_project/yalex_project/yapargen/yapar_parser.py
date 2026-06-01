"""Parse the *PRODUCCIONES* section of a ``.yalp`` file into a :class:`Grammar`.

The token section (``%token`` / ``IGNORE`` / ``%%``) is handled by
:mod:`yapargen.yapar_reader`, which yields a :class:`YAParSpec`.  This module
takes that spec and turns ``spec.raw_productions`` into a fully validated
:class:`~yapargen.grammar.Grammar`.

Production syntax (per *Consideraciones de YAPar*)::

    head:
        sym sym sym
      | sym sym
      | TOKEN
    ;

* ``head`` and lowercase symbols are **non-terminals** (production names).
* UPPERCASE symbols are **terminals** and must be declared with ``%token``.
* Alternatives are separated by ``|``; an empty alternative is an epsilon rule.
* A production ends with ``;``.
* The start symbol is the head of the **first** production.

Grammatical errors (undeclared terminals, undefined non-terminals, malformed
blocks, …) raise :exc:`YAParGrammarError`.
"""

from __future__ import annotations

import re
from pathlib import Path

from .grammar import Grammar
from .token_contract import YAParSpec
from .yapar_reader import read_file, read_string

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class YAParGrammarError(ValueError):
    """Raised when the production section is malformed or inconsistent."""


class YAParParser:
    """Parse a ``.yalp`` grammar file and return a :class:`Grammar` object."""

    def parse_file(self, path: str | Path) -> Grammar:
        """Read *path* and build the grammar from its production section."""
        return self.parse_spec(read_file(path))

    def parse_string(self, src: str) -> Grammar:
        """Build the grammar from the raw text of a ``.yalp`` file."""
        return self.parse_spec(read_string(src))

    # The real work happens here so callers that already hold a YAParSpec
    # (e.g. run_yapar.py, which reads it for the summary) need not re-parse.
    def parse_spec(self, spec: YAParSpec) -> Grammar:
        """Build and validate a grammar from an already-read :class:`YAParSpec`."""
        declared_tokens = set(spec.tokens)
        ignored = set(spec.ignore)

        blocks = self._split_blocks(spec.raw_productions)
        if not blocks:
            raise YAParGrammarError(
                "no productions found after the '%%' separator"
            )

        grammar = Grammar()
        # First pass: collect every head so we know the full non-terminal set
        # before validating the symbols used inside the bodies.
        heads: list[str] = []
        parsed: list[tuple[str, list[tuple[str, ...]]]] = []
        for head, body_text in blocks:
            if not _IDENT.fullmatch(head):
                raise YAParGrammarError(f"invalid production name: {head!r}")
            if head != head.lower():
                raise YAParGrammarError(
                    f"production (non-terminal) names must be lowercase: {head!r}"
                )
            alts = self._split_alternatives(body_text, head)
            heads.append(head)
            parsed.append((head, alts))

        non_terminals = set(heads)

        # Second pass: classify symbols and register productions.
        used_terminals: set[str] = set()
        for head, alts in parsed:
            for alt in alts:
                body: list[str] = []
                for sym in alt:
                    kind = self._classify(sym, declared_tokens, non_terminals, head)
                    if kind == "terminal":
                        used_terminals.add(sym)
                    body.append(sym)
                grammar.add_production(head, tuple(body))

        grammar.terminals = used_terminals
        grammar.non_terminals = non_terminals
        grammar.start = heads[0]

        self._validate(grammar, declared_tokens, ignored)
        # Expose the originating spec for downstream consumers (runtime/codegen).
        self.spec = spec
        self.ignore = list(spec.ignore)
        return grammar

    # ── lexing the production section ───────────────────────────────────────
    @staticmethod
    def _split_blocks(raw: str) -> list[tuple[str, str]]:
        """Split the raw production text into ``(head, body)`` blocks.

        Blocks are terminated by ``;``.  Each block must contain exactly one
        ``:`` separating the head from the alternatives.
        """
        # Collapse the whole section; ';' terminates a production, so split on it.
        text = raw.strip()
        if not text:
            return []

        blocks: list[tuple[str, str]] = []
        for chunk in text.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if ":" not in chunk:
                raise YAParGrammarError(
                    f"production block missing ':' -> {chunk[:60]!r}"
                )
            head, _, body = chunk.partition(":")
            blocks.append((head.strip(), body.strip()))
        return blocks

    @staticmethod
    def _split_alternatives(body_text: str, head: str) -> list[tuple[str, ...]]:
        """Split a production body on ``|`` into a list of symbol tuples."""
        alts: list[tuple[str, ...]] = []
        for piece in body_text.split("|"):
            symbols = tuple(piece.split())
            alts.append(symbols)  # empty tuple == epsilon
        if not alts:
            raise YAParGrammarError(f"production {head!r} has no alternatives")
        return alts

    @staticmethod
    def _classify(
        sym: str,
        declared_tokens: set[str],
        non_terminals: set[str],
        head: str,
    ) -> str:
        """Return ``"terminal"`` or ``"non-terminal"`` for *sym*, or raise."""
        if not _IDENT.fullmatch(sym):
            raise YAParGrammarError(
                f"invalid symbol {sym!r} in production {head!r}"
            )
        if sym in non_terminals:
            return "non-terminal"
        if sym in declared_tokens:
            return "terminal"
        # Unknown symbol — give a case-aware diagnostic.
        if sym == sym.upper():
            raise YAParGrammarError(
                f"terminal {sym!r} used in production {head!r} is not declared "
                f"with %token"
            )
        raise YAParGrammarError(
            f"non-terminal {sym!r} used in production {head!r} is never defined"
        )

    # ── semantic validation ─────────────────────────────────────────────────
    @staticmethod
    def _validate(grammar: Grammar, declared_tokens: set[str], ignored: set[str]) -> None:
        """Run grammar-level sanity checks, raising on hard errors."""
        # Every non-terminal must have at least one production.
        for nt in grammar.non_terminals:
            if not grammar.productions_for(nt):
                raise YAParGrammarError(f"non-terminal {nt!r} has no production")

        # The start symbol must be defined.
        if grammar.start not in grammar.non_terminals:
            raise YAParGrammarError(
                f"start symbol {grammar.start!r} has no production"
            )
