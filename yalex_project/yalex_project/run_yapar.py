from __future__ import annotations

import argparse
import sys
from pathlib import Path

from yapargen.yapar_reader import YAParReadError, read_file


def _build_summary(spec, source_path: Path) -> str:
    token_count = len(spec.tokens)
    ignore_count = len(spec.ignore)
    prod_lines = [l for l in spec.raw_productions.splitlines() if l.strip()]

    lines = [
        f"Source : {source_path}",
        f"Tokens : {token_count}  ->  {', '.join(spec.tokens) if spec.tokens else '(none)'}",
    ]
    if spec.ignore:
        lines.append(
            f"Ignore : {ignore_count}  ->  {', '.join(spec.ignore)}"
        )
    else:
        lines.append("Ignore : (none)")
    lines.append(f"Productions : {len(prod_lines)} non-empty line(s)")
    return "\n".join(lines)


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

    def log(msg: str) -> None:
        if args.verbose:
            print(msg)

    # ── 1. Validate input file ────────────────────────────────────────────────
    yapar_path = Path(args.yapar)
    log(f"[1/4] Checking input file: {yapar_path}")
    if not yapar_path.exists():
        print(f"error: file not found: {yapar_path}", file=sys.stderr)
        return 1
    if yapar_path.suffix not in {".yapar", ".yalp"}:
        print(
            f"warning: unexpected extension '{yapar_path.suffix}' "
            f"(expected .yapar or .yalp)",
            file=sys.stderr,
        )

    # ── 2. Read .yapar file ───────────────────────────────────────────────────
    log(f"[2/4] Reading grammar: {yapar_path}")
    try:
        spec = read_file(yapar_path)
    except YAParReadError as exc:
        print(f"error: invalid grammar — {exc}", file=sys.stderr)
        return 1

    # ── 3. Print summary ──────────────────────────────────────────────────────
    log("[3/4] Building summary")
    summary = _build_summary(spec, yapar_path)
    print(summary)

    # ── 4. Write output ───────────────────────────────────────────────────────
    output_dir = Path(args.output)
    log(f"[4/4] Writing output to: {output_dir}/")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "yapar_summary.txt"
    summary_path.write_text(summary + "\n", encoding="utf-8")
    log(f"      Saved: {summary_path}")

    print("YAPar: procesamiento completado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
