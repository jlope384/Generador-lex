"""High-level orchestration: grammar -> automata -> tables.

A single :func:`analyze` call performs every step of the parser-generator
pipeline and bundles the results in an :class:`Analysis`.  The CLI, the unit
tests and the code generator all go through here so the wiring lives in one
place.
"""

from __future__ import annotations

from dataclasses import dataclass

from .first_follow import compute_first, compute_follow
from .grammar import Grammar
from .lalr_automaton import LALRAutomaton, build_lalr_automaton
from .lalr_table import LALRTable, build_lalr_table
from .lr0_automaton import LR0Automaton, build_lr0_automaton
from .slr_table import SLRTable, build_slr_table


@dataclass
class Analysis:
    """Everything computed for a grammar, ready to print, render or codegen."""

    grammar: Grammar          # original (non-augmented) grammar
    augmented: Grammar        # augmented grammar (S' -> S, with $)
    first: dict[str, set[str]]
    follow: dict[str, set[str]]
    lr0: LR0Automaton
    lalr: LALRAutomaton
    slr_table: SLRTable
    lalr_table: LALRTable

    def table(self, method: str):
        """Return the table for ``"slr"`` or ``"lalr"``."""
        method = method.lower()
        if method == "slr":
            return self.slr_table
        if method == "lalr":
            return self.lalr_table
        raise ValueError(f"unknown parser method {method!r} (use 'slr' or 'lalr')")


def analyze(grammar: Grammar) -> Analysis:
    """Run the full pipeline for *grammar* (the original, non-augmented grammar)."""
    lr0 = build_lr0_automaton(grammar)
    augmented = lr0.grammar
    first = compute_first(augmented)
    follow = compute_follow(augmented, first)
    lalr = build_lalr_automaton(grammar)
    slr_table = build_slr_table(grammar, lr0)
    lalr_table = build_lalr_table(grammar, lalr)
    return Analysis(
        grammar=grammar,
        augmented=augmented,
        first=first,
        follow=follow,
        lr0=lr0,
        lalr=lalr,
        slr_table=slr_table,
        lalr_table=lalr_table,
    )


def format_sets(sets: dict[str, set[str]], symbols: list[str]) -> str:
    """Format FIRST/FOLLOW-style sets for the given symbols."""
    lines = []
    for sym in symbols:
        vals = sorted("ε" if v == "" else v for v in sets.get(sym, set()))
        lines.append(f"  {sym}: {{ {', '.join(vals)} }}")
    return "\n".join(lines)
