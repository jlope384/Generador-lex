"""FIRST and FOLLOW set computation for SLR(1) / LALR(1) construction.

Both functions use the classic fixed-point algorithms (Aho, Sethi, Ullman,
*Compilers: Principles, Techniques, and Tools*, §4.4).  The epsilon symbol is
represented by the empty string :data:`~yapargen.grammar.EPSILON`.
"""

from __future__ import annotations

from .grammar import EPSILON, END_MARKER, Grammar

__all__ = ["compute_first", "compute_follow", "first_of_sequence", "EPSILON"]


def compute_first(grammar: Grammar) -> dict[str, set[str]]:
    """Compute FIRST for every grammar symbol.

    Returns a dict mapping **every** symbol (terminals and non-terminals) to its
    FIRST set.  Each terminal ``t`` maps to ``{t}`` so the result can be fed
    directly to :func:`first_of_sequence`.  ``EPSILON`` appears in the FIRST set
    of any nullable non-terminal.
    """
    first: dict[str, set[str]] = {}

    # FIRST of a terminal is the terminal itself.
    for t in grammar.terminals:
        first[t] = {t}
    for nt in grammar.non_terminals:
        first[nt] = set()

    changed = True
    while changed:
        changed = False
        for prod in grammar.productions:
            head = prod.head
            before = len(first[head])
            if prod.is_epsilon():
                first[head].add(EPSILON)
            else:
                # Add FIRST of the body (treated as a symbol sequence).
                first[head] |= first_of_sequence(prod.body, first)
            if len(first[head]) != before:
                changed = True

    return first


def first_of_sequence(symbols: tuple[str, ...], first: dict[str, set[str]]) -> set[str]:
    """FIRST of a string of grammar symbols ``X1 X2 ... Xn``.

    Adds ``FIRST(X1)`` minus epsilon; if ``X1`` is nullable, continues with
    ``X2`` and so on.  ``EPSILON`` is included only if every symbol in the
    sequence is nullable (or the sequence is empty).
    """
    result: set[str] = set()
    for sym in symbols:
        sym_first = first.get(sym, {sym})
        result |= sym_first - {EPSILON}
        if EPSILON not in sym_first:
            break
    else:
        # Every symbol was nullable (or the sequence was empty).
        result.add(EPSILON)
    return result


def compute_follow(grammar: Grammar, first: dict[str, set[str]]) -> dict[str, set[str]]:
    """Compute FOLLOW for every non-terminal of an (augmented) grammar.

    The start symbol receives :data:`~yapargen.grammar.END_MARKER`.  When called
    on an augmented grammar (``S' -> S``) the end marker propagates to the
    original start symbol as expected.
    """
    follow: dict[str, set[str]] = {nt: set() for nt in grammar.non_terminals}
    follow[grammar.start].add(END_MARKER)

    changed = True
    while changed:
        changed = False
        for prod in grammar.productions:
            for i, sym in enumerate(prod.body):
                if sym not in grammar.non_terminals:
                    continue
                before = len(follow[sym])
                beta = prod.body[i + 1:]
                beta_first = first_of_sequence(beta, first)
                follow[sym] |= beta_first - {EPSILON}
                # If everything after `sym` can vanish, FOLLOW(head) flows in.
                if EPSILON in beta_first:
                    follow[sym] |= follow[prod.head]
                if len(follow[sym]) != before:
                    changed = True

    return follow
