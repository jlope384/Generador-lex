"""run_pico_spec_tests.py — valida la gramática PICO contra la suite oficial del SPEC.

El gist del enunciado (``dlp-2026-pico-yalex-definition``, SPEC.md) define 17 casos
de prueba: 8 programas que **deben** parsear y 9 que **deben** fallar, cada uno con
la línea en la que se espera el error. Este script construye la gramática PICO una
sola vez, arma las tablas **SLR(1)** y **LALR(1)** y corre los 17 casos contra
ambas, comprobando que:

* cada programa válido es **ACEPTADO** por SLR y por LALR;
* cada programa inválido es **RECHAZADO** por SLR y por LALR, y el error se reporta
  en la **misma línea** que indica el SPEC.

Sale con código 0 solo si los 17 casos dan exactamente el resultado esperado.

Uso::

    python3 run_pico_spec_tests.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from yalexgen import YALexGenerator
from yapargen.pipeline import analyze
from yapargen.parse_runner import run_parse
from yapargen.yapar_parser import YAParParser
from yapargen.yapar_reader import read_file

from run_yapar import _load_lexer_module, _tokenize

BASE = Path(__file__).resolve().parent
GRAMMAR = BASE / "examples" / "yapar" / "pico.yalp"
LEXER = BASE / "examples" / "yapar" / "pico.yal"
TESTDIR = BASE / "examples" / "yapar" / "inputs" / "pico_spec"

# Casos que DEBEN parsear (Part 3 del SPEC).
VALID = [
    "hello_parse.pico",
    "arithmetic_parse.pico",
    "conditional_parse.pico",
    "loop_parse.pico",
    "macro_with_args_parse.pico",
    "macro_no_args_parse.pico",
    "nested_expr_parse.pico",
    "multi_param_macro_parse.pico",
]

# Casos que DEBEN fallar (Part 4 del SPEC): (archivo, línea esperada del error).
INVALID = [
    ("missing_semicolon.pico", 2),
    ("missing_assign.pico", 1),
    ("when_without_braces.pico", 3),
    ("otherwise_without_when.pico", 2),
    ("bare_macro_call.pico", 4),
    ("empty_macro_body.pico", 2),
    ("repeat_missing_until.pico", 6),
    ("unbalanced_parens.pico", 1),
    ("double_operator.pico", 1),
]

_LINE_RE = re.compile(r"línea (\d+)")


def _error_line(msg):
    m = _LINE_RE.search(msg or "")
    return int(m.group(1)) if m else None


def main() -> int:
    # 1) Gramática + tablas SLR y LALR (una sola vez).
    spec = read_file(GRAMMAR)
    grammar = YAParParser().parse_spec(spec)
    an = analyze(grammar)
    tables = {"SLR": an.table("slr"), "LALR": an.table("lalr")}
    for name, t in tables.items():
        if t.conflicts:
            print(f"ERROR: la tabla {name} tiene conflictos: {t.conflicts}")
            return 1

    # 2) Lexer YALex (generado y cargado una sola vez).
    lexer_py = BASE / "build" / "yapar" / "pico_lexer.py"
    lexer_py.parent.mkdir(parents=True, exist_ok=True)
    YALexGenerator().generate(str(LEXER), str(lexer_py))
    lexer_module = _load_lexer_module(lexer_py)
    ignore = list(spec.ignore)

    def evaluate(path: Path, method: str):
        """Return (accepted: bool, error_message: str|None)."""
        text = path.read_text(encoding="utf-8")
        tokens, lex_err = _tokenize(lexer_module, text, ignore)
        if lex_err:  # error léxico => rechazado a nivel léxico
            return False, lex_err
        res = run_parse(tables[method], tokens, build_tree=False)
        return res.accepted, res.error

    passed = 0
    line_matches = 0

    print("=" * 80)
    print("SUITE OFICIAL DEL SPEC (gist 'dlp-2026-pico-yalex-definition')")
    print("Gramática PICO — verificada con tablas SLR(1) y LALR(1)")
    print("=" * 80)
    print(f"Tablas SLR y LALR construidas SIN conflictos "
          f"({len(an.lr0.states)} estados LR(0)).")
    print(f"{len(VALID)} casos que deben ACEPTAR + {len(INVALID)} casos que deben RECHAZAR.")
    print()

    # 3) Programas válidos.
    print("── Parte 3 del SPEC: programas que DEBEN parsear (esperado: ACEPTA) ──")
    h = f"{'#':>2}  {'archivo':<30}  {'SLR':<9}  {'LALR':<9}  resultado"
    print(h)
    print("-" * len(h))
    for i, name in enumerate(VALID, 1):
        slr_acc, _ = evaluate(TESTDIR / name, "SLR")
        lalr_acc, _ = evaluate(TESTDIR / name, "LALR")
        ok = slr_acc and lalr_acc
        passed += ok
        print(f"{i:>2}  {name:<30}  {'ACEPTA' if slr_acc else 'RECHAZA':<9}  "
              f"{'ACEPTA' if lalr_acc else 'RECHAZA':<9}  {'PASS' if ok else 'FAIL'}")
    print()

    # 4) Programas inválidos.
    print("── Parte 4 del SPEC: programas que DEBEN fallar (esperado: RECHAZA) ──")
    h2 = (f"{'#':>2}  {'archivo':<26}  {'línea esp':>9}  {'línea obt':>9}  "
          f"{'SLR':<9}  {'LALR':<9}  resultado")
    print(h2)
    print("-" * len(h2))
    error_details = []
    for i, (name, exp_line) in enumerate(INVALID, 1):
        slr_acc, slr_err = evaluate(TESTDIR / name, "SLR")
        lalr_acc, _ = evaluate(TESTDIR / name, "LALR")
        slr_rej = not slr_acc
        lalr_rej = not lalr_acc
        got_line = _error_line(slr_err)
        line_ok = got_line == exp_line
        line_matches += line_ok
        ok = slr_rej and lalr_rej and line_ok
        passed += ok
        print(f"{i:>2}  {name:<26}  {exp_line:>9}  {str(got_line):>9}  "
              f"{'RECHAZA' if slr_rej else 'ACEPTA':<9}  "
              f"{'RECHAZA' if lalr_rej else 'ACEPTA':<9}  {'PASS' if ok else 'FAIL'}")
        error_details.append((name, slr_err))
    print()

    # 5) Mensajes de error reales (muestran posición + tokens esperados).
    print("── Mensaje de error que produce el parser para cada caso inválido ──")
    for name, err in error_details:
        print(f"  • {name}:")
        print(f"      {err}")
    print()

    # 6) Resumen.
    total = len(VALID) + len(INVALID)
    print("=" * 80)
    print(f"RESULTADO: {passed}/{total} casos con el veredicto esperado "
          f"(SLR y LALR coinciden).")
    print(f"Líneas de error que coinciden con el SPEC: {line_matches}/{len(INVALID)}.")
    print("=" * 80)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
