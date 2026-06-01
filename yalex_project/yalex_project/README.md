# YALex Generator Project (Python)

Proyecto base para generar analizadores léxicos desde archivos `.yal`.

## Qué incluye

- Parser de archivos YALex
- Parser de expresiones regulares del subconjunto pedido
- Construcción directa `regexp -> DFA`
- Construcción alternativa `regexp -> NFA -> DFA` por Thompson
- Minimización del DFA generado
- Generación de un lexer en Python
- Graficación del árbol de expresión en PNG
- Ejemplos para `PICO` y `ArnoldC`

## Estructura

- `run_generator.py`: CLI principal
- `yalexgen/yalex_parser.py`: parser del archivo `.yal`
- `yalexgen/regex_parser.py`: parser de regex YALex
- `yalexgen/dfa.py`: estructura DFA, símbolo EOF y minimización
- `yalexgen/direct_dfa.py`: construcción directa `regexp -> DFA`
- `yalexgen/thompson.py`: construcción `regexp -> NFA -> DFA`
- `yalexgen/automata.py`: fachada compatible que reexporta los módulos de autómatas
- `yalexgen/generator.py`: emite el lexer Python
- `yalexgen/visualize.py`: genera la imagen del árbol
- `examples/`: ejemplos `.yal` y archivos de entrada

## Casos de prueba incluidos

- `examples/pico/`: incluye todos los casos exitosos y de error documentados en `Temp/SPEC.md`
- `examples/arnoldc/`: incluye todos los casos exitosos y de error documentados en `Temp/SPEC-ARNOLDC.md`
- `tests/test_yalex_generator.py`: valida automaticamente ambos `.yal` contra esos ejemplos

## Cómo correrlo

```bash
cd yalex_project
python3 run_generator.py examples/pico/pico.yal -o build/pico_lexer.py --graph build/pico_ast.png
python3 build/pico_lexer.py examples/pico/hello.pico --with-lexeme
```

El método principal es la construcción directa del DFA. El comando anterior usa
`--method direct` por defecto. Para indicarlo explícitamente:

```bash
python3 run_generator.py examples/pico/pico.yal -o build/pico_lexer.py --graph build/pico_ast.png --method direct
```

Para generar usando Thompson como método alternativo:

```bash
python3 run_generator.py examples/pico/pico.yal -o build/pico_lexer.py --graph build/pico_ast.png --method thompson
```

Para ArnoldC:

```bash
python3 -c "from yalexgen.generator import YALexGenerator; g=YALexGenerator(); g.generate('examples/arnoldc/arnoldc.yal','build/arnold_lexer.py','build/arnold_ast.png', method='direct')"
python3 build/arnold_lexer.py examples/arnoldc/hello.arnoldc --with-lexeme
```

## Pruebas

Smoke test rápido:

```bash
python3 run_smoke_tests.py
```

Batería más completa:

```bash
python3 -m unittest discover -s tests -v
```

## Operadores soportados

- `*`, `+`, `?`, `|`
- concatenación implícita
- conjuntos `[ ... ]`
- conjuntos negados `[^ ... ]`
- diferencia `#` entre conjuntos
- referencias `let ident = regexp`
- literal `eof`
- comodín `_`

`eof` también puede formar parte de expresiones más grandes, por ejemplo
para comentarios de línea que pueden terminar en `\n` o en fin de archivo.

## Acciones soportadas bien

- `return lexbuf`
- `return TOKEN`
- `return TOKEN(lxm)`
- `raise(...)`

Acciones Python arbitrarias también se copian, pero el mejor soporte funcional está en los cuatro patrones anteriores.

## Salida del lexer generado

- imprime tokens a stdout
- `--with-lexeme` imprime token, lexema, línea y columna
- reporta errores léxicos con línea y columna
- rechaza specs con reglas que acepten cadena vacía, para evitar ciclos infinitos

## Nota

El archivo generado es suficientemente general para specs tipo PICO y ArnoldC, incluyendo keywords largas, prioridad por orden de reglas y regla de lexema más largo. Ambos métodos construyen un DFA minimizado antes de emitir el lexer Python.

---

# YAPar — Generador de Analizadores Sintácticos (SLR(1) y LALR(1))

YAPar toma una gramática libre de contexto en formato `.yalp` y, junto con el
lexer de YALex, construye un analizador sintáctico ascendente. Implementa **dos
métodos completos**: **SLR(1)** y **LALR(1)**.

## Qué incluye

- Lectura del archivo `.yalp` (`%token`, `IGNORE`, separador `%%`, producciones).
- Construcción de la **gramática aumentada** (`S' -> S`).
- Cálculo de **FIRST**, **FOLLOW**, **CLOSURE** y **GOTO**.
- Construcción del **autómata LR(0)** (colección canónica de items).
- Construcción del **autómata LALR(1)** (colección LR(1) + fusión de núcleos).
- **Tabla de parseo SLR(1)** y **tabla LALR(1)** (ACTION + GOTO) con detección
  de conflictos shift/reduce y reduce/reduce.
- **Motor de parseo** dirigido por tabla con **traza paso a paso**
  (stack / input / acción), aceptación/rechazo y **árbol de parseo**.
- **Errores sintácticos** con posición (línea/columna) y tokens esperados, y
  **errores gramaticales** (terminal no declarado, no-terminal sin definir…).
- **Visualización** del autómata: `.dot` (Graphviz), `.png` (matplotlib) y `.txt`.
- **Generación de un parser autónomo** (`codegen`) sin dependencias de `yapargen`.

## Estructura (`yapargen/`)

- `yapar_reader.py`: lee tokens/`IGNORE`/`%%` y el texto de producciones.
- `yapar_parser.py`: parsea las producciones a un objeto `Grammar` (valida errores gramaticales).
- `grammar.py`: `Production`, `Grammar`, aumentación, símbolos ordenados.
- `first_follow.py`: FIRST, FOLLOW y FIRST de secuencias.
- `lr0_items.py`: item LR(0), CLOSURE y GOTO.
- `lr1_items.py`: item LR(1), CLOSURE1 y GOTO1 (lookaheads).
- `lr0_automaton.py`: construcción del autómata LR(0).
- `lalr_automaton.py`: colección LR(1) canónica y fusión de núcleos → LALR(1).
- `slr_table.py` / `lalr_table.py`: tablas ACTION/GOTO y formato de impresión.
- `parse_runner.py` / `slr_parser.py`: motor de parseo y traza.
- `diagnostics.py`: reporte de conflictos.
- `visualize.py`: render del autómata y del árbol de parseo.
- `codegen.py`: emite un parser Python autónomo.
- `pipeline.py`: orquesta todo (`analyze`).
- `token_contract.py`: valida el contrato de tokens YALex ↔ YAPar.

## Formato `.yalp`

```
/* comentarios con */ /* */
%token AND OR
%token LBRACKET RBRACKET SENTENCE
IGNORE WS          /* opcional: tokens que el parser ignora */
%%
s:  s AND p | p ;          /* minúsculas = no-terminales            */
p:  p OR q  | q ;          /* MAYÚSCULAS = terminales (tokens YALex) */
q:  LBRACKET s RBRACKET | SENTENCE ;
```

El símbolo inicial es la **primera** producción. Los nombres de token deben
coincidir con los que produce el lexer de YALex (`-l`).

## Cómo correrlo

Flujo completo (lexer + parser + análisis de una cadena), al estilo del enunciado
`yapar parser.yalp -l lexer.yal -o ...`:

```bash
python3 run_yapar.py examples/yapar/expr_slr.yalp \
    -l examples/yapar/expr.yal \
    -i examples/yapar/inputs/accept_or.txt \
    --parser both
```

Opciones:

- `--parser {slr,lalr,both}`: método de tabla (por defecto `both`).
- `-o DIR`: carpeta de salida (por defecto `build/yapar`).
- `--no-graph`: no generar PNG (solo `.dot` y `.txt`).
- `-v`: detalle por paso.

Sin lexer, la entrada se interpreta como nombres de token separados por espacios:

```bash
python3 run_yapar.py examples/yapar/expr_slr.yalp --parser slr
```

El parser autónomo generado también se puede usar solo:

```bash
echo "SENTENCE OR SENTENCE" | python3 build/yapar/expr_slr_slr_parser.py
```

## Ejemplos incluidos

- `examples/yapar/expr_slr.yalp` + `expr.yal`: **gramática SLR canónica** de la
  actividad (`S -> S∧P | P`, `P -> P∨Q | Q`, `Q -> [S] | sentence`). Reproduce
  exactamente el autómata LR(0) de 12 estados, la tabla SLR y la traza de
  `sentence ∨ sentence` del documento de referencia.
- `examples/yapar/ptr_lalr.yalp` + `ptr.yal`: **gramática de punteros**
  (`S -> L=R | R`, `L -> *R | id`, `R -> L`), el ejemplo clásico que **es
  LALR(1) pero NO SLR(1)**: SLR genera un conflicto shift/reduce sobre `=` y
  LALR lo resuelve.

## SLR(1) vs LALR(1)

| | SLR(1) | LALR(1) |
|---|---|---|
| Estados | = LR(0) | = LR(0) |
| Lookahead de reduce | `FOLLOW(A)` (global) | lookahead del item (preciso) |
| Gramática `expr_slr` | sin conflictos | sin conflictos (idéntica) |
| Gramática `ptr_lalr` | **1 conflicto** shift/reduce | **0 conflictos** |

## Pruebas

```bash
python3 -m unittest tests.test_yapar -v   # 24 pruebas YAPar
python3 run_smoke_tests.py                 # YALex + YAPar end-to-end
```
