from __future__ import annotations

import argparse
import sys
from pathlib import Path

from yapargen.yapar_reader import YAParReadError, read_file
from yapargen.token_contract import validate_token_contract


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_summary(spec, source_path: Path) -> str:
    token_count = len(spec.tokens)
    ignore_count = len(spec.ignore)
    prod_lines = [l for l in spec.raw_productions.splitlines() if l.strip()]

    lines = [
        f"Source      : {source_path}",
        f"Tokens      : {token_count}  ->  {', '.join(spec.tokens) if spec.tokens else '(none)'}",
        f"Ignore      : {ignore_count}  ->  {', '.join(spec.ignore) if spec.ignore else '(none)'}",
        f"Productions : {len(prod_lines)} non-empty line(s)",
    ]
    return "\n".join(lines)


def _yalex_token_names(yalex_spec) -> list[str]:
    """Return the sorted list of token type names a YALexSpec can emit."""
    from yalexgen.action_parser import parse_action
    names = sorted({
        parse_action(e.action_text).token_name
        for e in yalex_spec.entries
        if parse_action(e.action_text).token_name
    })
    return names


def _build_contract_section(yalex_tokens: list[str], yapar_spec) -> str:
    warnings = validate_token_contract(yalex_tokens, yapar_spec)
    lines = [
        "",
        "--- YALex / YAPar contract ---",
        f"YALex emits  : {', '.join(yalex_tokens) if yalex_tokens else '(none)'}",
        f"YAPar expects: {', '.join(yapar_spec.tokens) if yapar_spec.tokens else '(none)'}",
    ]
    if warnings:
        lines.append(f"Warnings ({len(warnings)}):")
        lines.extend(f"  {w}" for w in warnings)
    else:
        lines.append("Contract OK: token sets are consistent.")
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_yapar",
        description="YAPar — parser-generator front-end",
    )
    parser.add_argument(
        "-p", "--yapar",
        required=True,
        metavar="FILE",
        help="Path to the .yapar or .yalp grammar file",
    )
    parser.add_argument(
        "-l", "--yalex",
        metavar="FILE",
        help="Path to the .yal lexer specification (enables YALex+YAPar flow)",
    )
    parser.add_argument(
        "-i", "--input",
        metavar="FILE",
        help="Path to a source file to process through the pipeline",
    )
    parser.add_argument(
        "-o", "--output",
        default="build",
        metavar="DIR",
        help="Output directory (default: build/)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print each processing step",
    )
    args = parser.parse_args()

    # Precompute total steps so verbose labels are accurate.
    _total = (
        4                              # base: validate, read, summarise, write
        + (2 if args.yalex else 0)     # validate .yal + run generator
        + (1 if args.input else 0)     # read input file
        + (1 if args.yalex else 0)     # contract check (needs the generator)
    )
    _step = 0

    def log(msg: str) -> None:
        nonlocal _step
        _step += 1
        if args.verbose:
            print(f"[{_step}/{_total}] {msg}")

    output_dir = Path(args.output)

    # ── 1. Validate .yapar ────────────────────────────────────────────────────
    yapar_path = Path(args.yapar)
    log(f"Checking .yapar file: {yapar_path}")
    if not yapar_path.exists():
        print(f"error: file not found: {yapar_path}", file=sys.stderr)
        return 1
    if yapar_path.suffix not in {".yapar", ".yalp"}:
        print(
            f"warning: unexpected extension '{yapar_path.suffix}' "
            f"(expected .yapar or .yalp)",
            file=sys.stderr,
        )

    # ── 2. Read .yapar ────────────────────────────────────────────────────────
    log(f"Reading grammar: {yapar_path}")
    try:
        spec = read_file(yapar_path)
    except YAParReadError as exc:
        print(f"error: invalid grammar -- {exc}", file=sys.stderr)
        return 1

    # ── 3. Build and print summary ────────────────────────────────────────────
    log("Building grammar summary")
    summary = _build_summary(spec, yapar_path)
    print(summary)

    # ── 4. Write base output ──────────────────────────────────────────────────
    log(f"Writing output to: {output_dir}/")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "yapar_summary.txt"
    # Keep summary open for appending contract info later.
    summary_lines: list[str] = [summary]

    summary_path.write_text(summary + "\n", encoding="utf-8")
    if args.verbose:
        print(f"      Saved: {summary_path}")

    # ── 5+6. YALex integration (optional) ────────────────────────────────────
    yalex_tokens: list[str] = []

    if args.yalex:
        yalex_path = Path(args.yalex)
        log(f"Validating .yal file: {yalex_path}")
        if not yalex_path.exists():
            print(f"error: .yal file not found: {yalex_path}", file=sys.stderr)
            return 1

        log(f"Running YALex generator on: {yalex_path}")
        try:
            from yalexgen import YALexGenerator
            lexer_out = output_dir / f"{yalex_path.stem}_lexer.py"
            artifacts = YALexGenerator().generate(str(yalex_path), str(lexer_out))
            yalex_tokens = _yalex_token_names(artifacts.spec)
            print(
                f"YALex: generated {lexer_out.name} "
                f"({artifacts.dfa_state_count} DFA states after minimization)"
            )
        except Exception as exc:
            print(f"error: YALex generation failed -- {exc}", file=sys.stderr)
            return 1

    # ── Next. Read input file (optional) ─────────────────────────────────────
    if args.input:
        input_path = Path(args.input)
        log(f"Reading input file: {input_path}")
        if not input_path.exists():
            print(f"error: input file not found: {input_path}", file=sys.stderr)
            return 1
        input_text = input_path.read_text(encoding="utf-8")
        preview = input_text[:200].replace("\n", " ")
        if len(input_text) > 200:
            preview += " ..."
        print(f"Entrada a procesar: {preview}")

    # ── Next. Contract check (requires --yalex) ───────────────────────────────
    if args.yalex:
        log("Checking YALex / YAPar token contract")
        contract = _build_contract_section(yalex_tokens, spec)
        print(contract)

        # Append contract to the summary file.
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(contract + "\n")

    # ── Final messages ────────────────────────────────────────────────────────
    print("YAPar: procesamiento completado.")
    if args.yalex or args.input:
        print("Flujo completo listo. Parser runtime pendiente de implementacion.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
