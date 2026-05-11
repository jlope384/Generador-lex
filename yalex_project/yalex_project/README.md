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
- `yalexgen/automata.py`: DFA directo, Thompson + subset construction y minimización
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
