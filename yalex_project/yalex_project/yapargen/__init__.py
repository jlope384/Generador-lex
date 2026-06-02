"""YAPar — generador de analizadores sintácticos SLR(1) y LALR(1).

Punto de entrada del paquete.  Las importaciones son perezosas (``__getattr__``)
para evitar ciclos entre los módulos del generador.

Ejemplo rápido::

    from yapargen import YAParParser, analyze, run_parse
    grammar = YAParParser().parse_file("examples/yapar/expr_slr.yalp")
    an = analyze(grammar)
    print(an.slr_table.conflicts)         # []  -> es SLR(1)
    run_parse(an.slr_table, ["SENTENCE", "OR", "SENTENCE"]).accepted  # True
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .grammar import Grammar, Production
    from .pipeline import Analysis, analyze
    from .parse_runner import ParseResult, run_parse
    from .yapar_parser import YAParParser

__all__ = [
    "YAParParser",
    "Grammar",
    "Production",
    "analyze",
    "Analysis",
    "run_parse",
    "ParseResult",
]

_LAZY = {
    "YAParParser": ("yapargen.yapar_parser", "YAParParser"),
    "Grammar": ("yapargen.grammar", "Grammar"),
    "Production": ("yapargen.grammar", "Production"),
    "analyze": ("yapargen.pipeline", "analyze"),
    "Analysis": ("yapargen.pipeline", "Analysis"),
    "run_parse": ("yapargen.parse_runner", "run_parse"),
    "ParseResult": ("yapargen.parse_runner", "ParseResult"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib
        module_name, attr = _LAZY[name]
        return getattr(importlib.import_module(module_name), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
