"""Object-oriented convenience wrapper around the LR parsing engine.

:class:`SLRParser` holds a pre-built :class:`~yapargen.slr_table.SLRTable` and
delegates the actual work to :func:`yapargen.parse_runner.run_parse`.  The same
class drives LALR tables too (they share the table interface).
"""

from __future__ import annotations

from typing import Any, List

from .parse_runner import ParseResult, run_parse
from .slr_table import SLRTable


class SLRParser:
    """Drive a parse using a pre-built SLR (or LALR) table."""

    def __init__(self, table: SLRTable) -> None:
        self.table = table

    def parse(self, tokens: List[Any], build_tree: bool = True) -> ParseResult:
        """Parse *tokens*, returning a :class:`ParseResult` (truthy if accepted)."""
        return run_parse(self.table, tokens, build_tree=build_tree)

    def accepts(self, tokens: List[Any]) -> bool:
        """Return ``True`` iff *tokens* form a syntactically valid sentence."""
        return run_parse(self.table, tokens, build_tree=False).accepted
