from __future__ import annotations

import argparse
from pathlib import Path

from yalexgen import YALexGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description='YALex -> Python lexer generator')
    parser.add_argument('yal_file', help='Input .yal file')
    parser.add_argument('-o', '--output', required=True, help='Output generated Python lexer')
    parser.add_argument('--graph', help='Path to save expression tree PNG')
    parser.add_argument(
        '--method',
        choices=('direct', 'thompson'),
        default='direct',
        help='DFA construction method. Defaults to direct; Thompson is kept as an alternative.',
    )
    args = parser.parse_args()

    gen = YALexGenerator()
    artifacts = gen.generate(args.yal_file, args.output, graph_path=args.graph, method=args.method)
    print(f'Generated lexer: {artifacts.python_path}')
    print(f'Expression tree: {artifacts.graph_path}')
    print(f'Method: {artifacts.method}')
    print(f'DFA states before minimization: {artifacts.dfa_state_count_before_minimization}')
    print(f'DFA states after minimization: {artifacts.dfa_state_count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
