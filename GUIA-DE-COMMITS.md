# Guía de commits — Proyecto YALex + YAPar

El proyecto se dividió en **6 etapas**. Como somos **3 integrantes** y cada uno
debe hacer **mínimo 2 commits**, el reparto es **2 commits por persona**:

| # | Etapa | Responsable | Carné |
|---|-------|-------------|-------|
| 1 | YALex (fix) + parser de gramática `.yalp` | **Ian Cumes** | 23236 |
| 2 | FIRST, FOLLOW, CLOSURE y GOTO | **Javier Cifuentes** | 23079 |
| 3 | Autómata LR(0) + visualización | **Javier López** | 28415 |
| 4 | Tabla SLR(1) + motor de parseo + diagnóstico | **Ian Cumes** | 23236 |
| 5 | LALR(1): items LR(1), autómata y tabla | **Javier Cifuentes** | 23079 |
| 6 | Integración CLI, codegen, pruebas y reporte PDF | **Javier López** | 28415 |

> Reparto: **Ian** → commits 1 y 4 · **Javier Cifuentes** → 2 y 5 · **Javier López** → 3 y 6.

## Cómo están organizadas las carpetas

- El proyecto vive en `yalex_project/yalex_project/` (estado **final**, ya terminado).
- En `entregas-por-etapa/` hay **una copia del proyecto por cada etapa**
  (`etapa-1-...`, … `etapa-6-...`), tal como quedó al terminar esa etapa. Son
  **material de referencia** para revisar el avance; están en `.gitignore` y no
  se commitean.
- Los commits se hacen **desde el árbol de trabajo** (que ya tiene todo el código
  final) usando `git add` de los archivos de cada etapa, en orden. Así cada
  commit "añade" exactamente el trabajo de su etapa y queda un historial
  incremental y limpio.

> **Importante:** ya está todo programado y probado. Esta guía es solo para que
> cada quien **haga sus commits**. No es necesario reescribir código.

## Antes de empezar

```bash
cd /ruta/al/repo/Generador-lex
git status          # debe verse el árbol con los archivos modificados/nuevos
```

Cada persona, en su turno, ejecuta el bloque de **su** commit. Lo ideal es que
cada quien commitee desde su propia máquina (su `git config user.name/email`).
Si una sola persona va a registrar todo, puede añadir
`--author="Nombre <correo>"` a cada `git commit` (ver al final).

---

## Commit 1 — Etapa 1 · Ian Cumes
**YALex (fix de codificación) + lectura/parseo de la gramática `.yalp`.**

```bash
git add yalex_project/yalex_project/yalexgen/generator.py \
        yalex_project/yalex_project/yapargen/grammar.py \
        yalex_project/yalex_project/yapargen/yapar_parser.py \
        yalex_project/yalex_project/examples/yapar/ \
        yalex_project/yalex_project/build/pico_lexer.py \
        yalex_project/yalex_project/build/arnold_lexer.py \
        yalex_project/yalex_project/build/pico_ast.png \
        yalex_project/yalex_project/build/arnold_ast.png

git commit -m "feat: parser de gramatica .yalp y fix de codificacion en YALex

- yapargen/grammar.py: modelo Grammar/Production y aumentacion (S' -> S, \$).
- yapargen/yapar_parser.py: parsea producciones a Grammar y valida errores
  gramaticales (terminal no declarado, no-terminal sin definir, etc.).
- yalexgen/generator.py: emite tablas con ascii() para que el lexer generado
  sea ASCII puro y no rompa el tokenizador de Python.
- examples/yapar: gramaticas de ejemplo (SLR canonica, punteros, epsilon,
  LR(1)-no-LALR, IGNORE) con sus lexers y archivos de entrada."
```

## Commit 2 — Etapa 2 · Javier Cifuentes
**FIRST, FOLLOW, CLOSURE y GOTO.**

```bash
git add yalex_project/yalex_project/yapargen/first_follow.py \
        yalex_project/yalex_project/yapargen/lr0_items.py

git commit -m "feat: FIRST, FOLLOW, CLOSURE y GOTO

- first_follow.py: calculo por punto fijo de FIRST y FOLLOW (+ FIRST de una
  secuencia de simbolos).
- lr0_items.py: item LR(0) con punto, operaciones CLOSURE y GOTO."
```

## Commit 3 — Etapa 3 · Javier López
**Autómata LR(0) y su visualización.**

```bash
git add yalex_project/yalex_project/yapargen/lr0_automaton.py \
        yalex_project/yalex_project/yapargen/visualize.py

git commit -m "feat: construccion del automata LR(0) y visualizacion

- lr0_automaton.py: coleccion canonica de items LR(0) por BFS con numeracion
  de estados estable (I0..In) y tabla de transiciones GOTO.
- visualize.py: render del automata a .dot (Graphviz), .png (matplotlib) y
  texto; tambien dibuja el arbol de parseo."
```

## Commit 4 — Etapa 4 · Ian Cumes
**Tabla SLR(1), motor de parseo y diagnóstico de conflictos.**

```bash
git add yalex_project/yalex_project/yapargen/slr_table.py \
        yalex_project/yalex_project/yapargen/diagnostics.py \
        yalex_project/yalex_project/yapargen/parse_runner.py \
        yalex_project/yalex_project/yapargen/slr_parser.py

git commit -m "feat: tabla SLR(1), motor de parseo y diagnostico

- slr_table.py: ACTION/GOTO SLR(1) usando FOLLOW; deteccion de conflictos
  shift/reduce y reduce/reduce; impresion de la tabla.
- parse_runner.py / slr_parser.py: motor shift/reduce con traza paso a paso
  (stack/input/accion), arbol de parseo y errores con posicion.
- diagnostics.py: reporte legible de conflictos."
```

## Commit 5 — Etapa 5 · Javier Cifuentes
**LALR(1): items LR(1), autómata y tabla.**

```bash
git add yalex_project/yalex_project/yapargen/lr1_items.py \
        yalex_project/yalex_project/yapargen/lalr_automaton.py \
        yalex_project/yalex_project/yapargen/lalr_table.py

git commit -m "feat: parser LALR(1) por fusion de nucleos

- lr1_items.py: item LR(1) con lookahead, CLOSURE1 y GOTO1.
- lalr_automaton.py: coleccion LR(1) canonica y fusion de estados con el mismo
  nucleo LR(0) (mismo numero de estados que LR(0), con lookaheads precisos).
- lalr_table.py: ACTION/GOTO LALR(1) (reduce solo ante el lookahead del item)."
```

## Commit 6 — Etapa 6 · Javier López
**Integración CLI, generación de parser, pruebas y reporte PDF.**

```bash
git add yalex_project/yalex_project/yapargen/codegen.py \
        yalex_project/yalex_project/yapargen/pipeline.py \
        yalex_project/yalex_project/yapargen/__init__.py \
        yalex_project/yalex_project/run_yapar.py \
        yalex_project/yalex_project/run_smoke_tests.py \
        yalex_project/yalex_project/README.md \
        yalex_project/yalex_project/requirements.txt \
        yalex_project/yalex_project/tests/test_yapar.py \
        yalex_project/yalex_project/tools/build_report.py \
        yalex_project/yalex_project/docs/Informe_YALex_YAPar.pdf \
        yalex_project/yalex_project/GUIA-DEL-PROYECTO.md \
        .gitignore

git commit -m "feat: integracion CLI YALex+YAPar, codegen, pruebas y reporte

- run_yapar.py: flujo completo .yalp (+ -l lexer.yal, -i entrada) con SLR/LALR,
  trazas, imagenes y parser autonomo; pipeline.py orquesta el analisis.
- codegen.py: emite un parser .py autonomo (sin dependencias de yapargen).
- tests/test_yapar.py: 39 pruebas (gramatica, FIRST/FOLLOW, automata, tablas,
  parseo, LALR, epsilon, conflictos, CLI, codegen).
- tools/build_report.py + docs/Informe_YALex_YAPar.pdf: informe tecnico.
- GUIA-DEL-PROYECTO.md: guia de uso y de presentacion."
```

---

## Verificación final (tras los 6 commits)

```bash
cd yalex_project/yalex_project
python3 -m unittest discover -s tests      # 51 pruebas (12 YALex + 39 YAPar) -> OK
python3 run_smoke_tests.py                  # YALex + YAPar end-to-end -> exit 0
git log --oneline -6                        # los 6 commits, en orden
```

## Opcional — registrar el autor de cada commit

Si una sola persona registra todos los commits, añada el autor real a cada uno:

```bash
git commit --author="Ian Cumes <ianrodrigocumes@gmail.com>" -m "..."   # commits 1 y 4
git commit --author="Javier Cifuentes <CORREO>" -m "..."               # commits 2 y 5
git commit --author="Javier López <CORREO>" -m "..."                   # commits 3 y 6
```

(Reemplace `CORREO` por el correo real de cada integrante.)
