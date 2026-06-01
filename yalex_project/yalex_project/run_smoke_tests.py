from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str]) -> int:
    print('$', ' '.join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    print()
    return proc.returncode


def expect(cmd: list[str], expected: int) -> int:
    code = run(cmd)
    if code != expected:
        print(f'Expected exit code {expected}, got {code}')
        return 1
    return 0


def main() -> int:
    code = 0
    # ── YALex (analizador léxico) ──────────────────────────────────────────
    code |= expect([sys.executable, 'run_generator.py', 'examples/pico/pico.yal', '-o', 'build/pico_lexer.py', '--graph', 'build/pico_ast.png'], 0)
    code |= expect([sys.executable, 'build/pico_lexer.py', 'examples/pico/hello.pico', '--with-lexeme'], 0)
    code |= expect([sys.executable, 'build/pico_lexer.py', 'examples/pico/bad_string.pico'], 1)
    code |= expect([sys.executable, 'run_generator.py', 'examples/arnoldc/arnoldc.yal', '-o', 'build/arnold_lexer.py', '--graph', 'build/arnold_ast.png'], 0)
    code |= expect([sys.executable, 'build/arnold_lexer.py', 'examples/arnoldc/variables.arnoldc'], 0)
    code |= expect([sys.executable, 'build/arnold_lexer.py', 'examples/arnoldc/hash_comment.arnoldc'], 1)

    # ── YAPar (analizador sintáctico SLR(1) / LALR(1)) ─────────────────────
    # Gramática SLR canónica: cadena válida -> exit 0, cadena inválida -> exit 1.
    code |= expect([sys.executable, 'run_yapar.py', 'examples/yapar/expr_slr.yalp',
                    '-l', 'examples/yapar/expr.yal',
                    '-i', 'examples/yapar/inputs/accept_or.txt',
                    '--parser', 'both', '--no-graph'], 0)
    code |= expect([sys.executable, 'run_yapar.py', 'examples/yapar/expr_slr.yalp',
                    '-l', 'examples/yapar/expr.yal',
                    '-i', 'examples/yapar/inputs/reject_two.txt',
                    '--parser', 'slr', '--no-graph'], 1)
    # Gramática de punteros: LALR acepta lo que SLR no puede (conflicto -> exit 2).
    code |= expect([sys.executable, 'run_yapar.py', 'examples/yapar/ptr_lalr.yalp',
                    '-l', 'examples/yapar/ptr.yal',
                    '-i', 'examples/yapar/inputs/ptr_deref.txt',
                    '--parser', 'lalr', '--no-graph'], 0)
    # Gramática con producciones-epsilon (nullable): cadena válida -> exit 0.
    code |= expect([sys.executable, 'run_yapar.py', 'examples/yapar/expr_eps.yalp',
                    '-l', 'examples/yapar/arith.yal',
                    '-i', 'examples/yapar/inputs/eps_sum_prod.txt',
                    '--parser', 'both', '--no-graph'], 0)
    # Directiva IGNORE: el lexer emite WS y el parser lo descarta -> exit 0.
    code |= expect([sys.executable, 'run_yapar.py', 'examples/yapar/expr_ignore.yalp',
                    '-l', 'examples/yapar/expr_ws.yal',
                    '-i', 'examples/yapar/inputs/accept_or.txt',
                    '--parser', 'slr', '--no-graph'], 0)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
