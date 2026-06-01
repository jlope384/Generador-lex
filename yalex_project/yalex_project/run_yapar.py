"""YAPar — generador de analizadores sintácticos SLR(1) y LALR(1).

Uso típico (al estilo del enunciado ``yapar parser.yalp -l lexer.yal -o ...``)::

    python3 run_yapar.py examples/yapar/expr_slr.yalp \
        -l examples/yapar/expr.yal \
        -i examples/yapar/inputs/accept_or.txt \
        --parser both

Flujo completo:

1. lee la gramática ``.yalp`` y construye el objeto :class:`Grammar`;
2. (opcional ``-l``) ejecuta YALex para generar el lexer y verifica el contrato
   de tokens YALex/YAPar;
3. calcula gramática aumentada, FIRST, FOLLOW, autómata LR(0) y autómata LALR(1);
4. construye las tablas SLR(1) y/o LALR(1) e informa conflictos;
5. genera imágenes del autómata y un parser autónomo (``codegen``);
6. (opcional ``-i``) tokeniza el archivo de entrada con el lexer y lo parsea,
   mostrando la traza paso a paso y aceptando/rechazando la cadena.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import List, Optional

from yapargen.codegen import generate_parser
from yapargen.diagnostics import report_conflicts
from yapargen.grammar import END_MARKER
from yapargen.parse_runner import format_trace, run_parse
from yapargen.pipeline import analyze, format_sets
from yapargen.slr_table import format_table
from yapargen.token_contract import validate_token_contract
from yapargen.visualize import render_automaton, render_parse_tree
from yapargen.yapar_parser import YAParGrammarError, YAParParser
from yapargen.yapar_reader import YAParReadError, read_file


# ── helpers ─────────────────────────────────────────────────────────────────
def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _yalex_token_names(yalex_spec) -> List[str]:
    """Token type names a YALexSpec can emit (the lexer's terminal vocabulary)."""
    from yalexgen.action_parser import parse_action
    return sorted({
        parse_action(e.action_text).token_name
        for e in yalex_spec.entries
        if parse_action(e.action_text).token_name
    })


def _load_lexer_module(lexer_py: Path) -> ModuleType:
    """Import a YALex-generated lexer module from its file path.

    The module is registered in ``sys.modules`` *before* execution: the lexer
    defines a ``@dataclass`` whose annotations dataclasses resolves through
    ``sys.modules[cls.__module__]`` (a Python 3.9 requirement).
    """
    name = "yalex_generated_lexer"
    spec = importlib.util.spec_from_file_location(name, lexer_py)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _tokenize(lexer_module: ModuleType, text: str, ignore: List[str]):
    """Run the lexer over *text*; return (tokens, error_or_None).

    Tokens whose type is in *ignore* are dropped (the ``IGNORE`` directive).
    """
    ignore_set = set(ignore)
    tokens = []
    try:
        for tok in lexer_module.Lexer(text).tokenize():
            if tok.type not in ignore_set:
                tokens.append(tok)
    except getattr(lexer_module, "LexicalError", Exception) as exc:
        return tokens, str(exc)
    except StopIteration:
        pass
    return tokens, None


# ── main ──────────────────────────────────────────────────────────────────────
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_yapar",
        description="YAPar — generador de analizadores sintácticos SLR(1) y LALR(1).",
    )
    parser.add_argument("grammar", help="Archivo de gramática .yalp / .yapar")
    parser.add_argument("-l", "--yalex", metavar="FILE",
                        help="Archivo .yal del lexer (habilita el flujo YALex+YAPar)")
    parser.add_argument("-i", "--input", metavar="FILE",
                        help="Archivo de cadenas a analizar sintácticamente")
    parser.add_argument("-o", "--output", default="build/yapar", metavar="DIR",
                        help="Directorio de salida (por defecto: build/yapar)")
    parser.add_argument("--parser", choices=("slr", "lalr", "both"), default="both",
                        help="Método de tabla a construir (por defecto: both)")
    parser.add_argument("--no-graph", action="store_true",
                        help="No generar imágenes PNG (solo .dot y texto)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Mostrar detalle de cada paso")
    args = parser.parse_args(argv)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.grammar).stem
    methods = ["slr", "lalr"] if args.parser == "both" else [args.parser]

    # ── 1. leer + parsear gramática ─────────────────────────────────────────
    gpath = Path(args.grammar)
    if not gpath.exists():
        print(f"error: no se encontró el archivo de gramática: {gpath}", file=sys.stderr)
        return 1
    try:
        spec = read_file(gpath)
        grammar = YAParParser().parse_spec(spec)
    except (YAParReadError, YAParGrammarError) as exc:
        print(f"error: gramática inválida — {exc}", file=sys.stderr)
        return 1

    _section(f"Gramática: {gpath.name}")
    print(f"Tokens declarados : {', '.join(spec.tokens) or '(ninguno)'}")
    print(f"Tokens ignorados  : {', '.join(spec.ignore) or '(ninguno)'}")
    print(f"No-terminales     : {', '.join(sorted(grammar.non_terminals))}")
    print(f"Símbolo inicial   : {grammar.start}")
    print("Producciones:")
    for i, p in enumerate(grammar.productions):
        print(f"  R{i+1}: {p}")

    # ── 2. YALex (opcional) ──────────────────────────────────────────────────
    lexer_module = None
    if args.yalex:
        ypath = Path(args.yalex)
        if not ypath.exists():
            print(f"error: no se encontró el .yal: {ypath}", file=sys.stderr)
            return 1
        _section(f"YALex: {ypath.name}")
        try:
            from yalexgen import YALexGenerator
            lexer_py = out_dir / f"{ypath.stem}_lexer.py"
            artifacts = YALexGenerator().generate(str(ypath), str(lexer_py))
            print(f"Lexer generado: {lexer_py}  "
                  f"({artifacts.dfa_state_count} estados DFA tras minimización)")
            lexer_module = _load_lexer_module(lexer_py)
            yalex_tokens = _yalex_token_names(artifacts.spec)
            warnings = validate_token_contract(yalex_tokens, spec)
            print(f"YALex emite   : {', '.join(yalex_tokens) or '(ninguno)'}")
            print(f"YAPar espera  : {', '.join(spec.tokens) or '(ninguno)'}")
            if warnings:
                print(f"Advertencias de contrato ({len(warnings)}):")
                for w in warnings:
                    print(f"  {w}")
            else:
                print("Contrato OK: los conjuntos de tokens son consistentes.")
        except Exception as exc:
            print(f"error: falló la generación del lexer — {exc}", file=sys.stderr)
            return 1

    # ── 3. análisis (autómatas + tablas) ─────────────────────────────────────
    an = analyze(grammar)

    _section("Gramática aumentada")
    for i, p in enumerate(an.augmented.productions):
        tag = "  (aceptación)" if i == 0 else ""
        print(f"  ({i}) {p}{tag}")

    _section("FIRST / FOLLOW")
    nts = [nt for nt in an.augmented.ordered_symbols()
           if nt in an.augmented.non_terminals and nt != an.augmented.start]
    print("FIRST:")
    print(format_sets(an.first, nts))
    print("FOLLOW:")
    print(format_sets(an.follow, nts))

    _section(f"Autómata LR(0) — {len(an.lr0.states)} estados")
    from yapargen.visualize import automaton_to_text
    print(automaton_to_text(an.lr0, f"Autómata LR(0) — {stem}"))

    if not args.no_graph:
        arts = render_automaton(an.lr0, out_dir / f"{stem}_lr0.png",
                                title=f"Autómata LR(0) — {stem}")
        print("Imágenes/representaciones del autómata LR(0):")
        for k, v in arts.items():
            print(f"  {k}: {v}")
        if "lalr" in methods:
            la = render_automaton(an.lalr, out_dir / f"{stem}_lalr.png",
                                  title=f"Autómata LALR(1) — {stem}")
            print("Autómata LALR(1):")
            for k, v in la.items():
                print(f"  {k}: {v}")

    # ── 4. tablas + conflictos ───────────────────────────────────────────────
    exit_code = 0
    for method in methods:
        table = an.table(method)
        _section(f"Tabla {method.upper()}(1)")
        print(format_table(table))
        print()
        report_conflicts(table.conflicts, an.augmented)
        if table.conflicts:
            exit_code = 2

        # ── 5. parser autónomo ───────────────────────────────────────────────
        parser_py = out_dir / f"{stem}_{method}_parser.py"
        generate_parser(table, parser_py)
        print(f"Parser autónomo generado: {parser_py}")

        # ── 6. analizar la entrada (opcional) ────────────────────────────────
        if args.input:
            ipath = Path(args.input)
            if not ipath.exists():
                print(f"error: no se encontró el archivo de entrada: {ipath}",
                      file=sys.stderr)
                return 1
            _section(f"Análisis sintáctico ({method.upper()}) de {ipath.name}")
            tokens = _read_input_tokens(ipath, lexer_module, spec.ignore, grammar)
            if tokens is None:
                exit_code = 1
                continue
            shown = " ".join(t.type if hasattr(t, "type") else str(t) for t in tokens)
            print(f"Tokens: {shown} {END_MARKER}")
            result = run_parse(table, tokens)
            print()
            print(format_trace(result))
            if result.accepted and result.tree is not None and not args.no_graph:
                tree_png = out_dir / f"{stem}_{method}_tree.png"
                try:
                    render_parse_tree(result.tree, tree_png)
                    print(f"Árbol de parseo: {tree_png}")
                except Exception:
                    pass
            if not result.accepted:
                exit_code = 1

    _section("Listo")
    print(f"Artefactos en: {out_dir}/")
    return exit_code


def _read_input_tokens(ipath: Path, lexer_module, ignore: List[str], grammar):
    """Return the token list for *ipath*, or None on a lexical/contract error.

    With a lexer (``-l``) the file is tokenised by the YALex-generated lexer;
    otherwise the file is treated as whitespace-separated terminal names.
    """
    text = ipath.read_text(encoding="utf-8")
    if lexer_module is not None:
        tokens, err = _tokenize(lexer_module, text, ignore)
        if err:
            print(f"Error léxico: {err}", file=sys.stderr)
            return None
        return tokens
    # No lexer: split on whitespace, validate against declared terminals.
    names = text.split()
    unknown = [n for n in names if n not in grammar.terminals]
    if unknown:
        print(f"Error: símbolos no declarados como token: {', '.join(sorted(set(unknown)))}",
              file=sys.stderr)
        return None
    return names


if __name__ == "__main__":
    raise SystemExit(main())
