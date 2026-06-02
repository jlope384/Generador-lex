# Guía del proyecto y de la presentación — YALex + YAPar

> Generador de analizadores **léxicos** (YALex) y **sintácticos** (YAPar) con
> tablas de parseo **SLR(1)** y **LALR(1)**. CC3071 — Diseño de Lenguajes de
> Programación, UVG.
> Integrantes: **Ian Cumes (23236)**, **Javier Cifuentes (23079)**, **Javier López (28415)**.

Esta guía sirve para **entender, usar y presentar** el proyecto. Está pensada
para que cualquiera del equipo pueda explicarlo y hacer la demo en clase.

---

## 0. Índice

1. [¿Qué hace el proyecto? (visión general)](#1-qué-hace-el-proyecto-visión-general)
2. [Conceptos clave (para defender en clase)](#2-conceptos-clave-para-defender-en-clase)
3. [Cómo funciona por dentro (arquitectura)](#3-cómo-funciona-por-dentro-arquitectura)
4. [Cómo se usa (manual)](#4-cómo-se-usa-manual)
5. [Cómo interpretar la salida](#5-cómo-interpretar-la-salida)
6. [Por qué confiamos en que es correcto (validación)](#6-por-qué-confiamos-en-que-es-correcto-validación)
7. [Guion de demostración en vivo](#7-guion-de-demostración-en-vivo)
8. [Preguntas probables del profesor (y respuestas)](#8-preguntas-probables-del-profesor-y-respuestas)
9. [Checklist antes de presentar](#9-checklist-antes-de-presentar)

---

## 1. ¿Qué hace el proyecto? (visión general)

Cuando un compilador lee código fuente, lo procesa en dos fases:

1. **Análisis léxico** — parte el texto en *tokens* (palabras del lenguaje:
   identificadores, números, operadores…). Lo hace el **lexer**, que genera
   **YALex** a partir de expresiones regulares (`.yal`).
2. **Análisis sintáctico** — verifica que esos tokens formen frases válidas
   según una *gramática* (¿está bien construida la expresión?). Lo hace el
   **parser**, que genera **YAPar** a partir de una gramática (`.yalp`).

```
  texto fuente ──YALex──▶ tokens ──YAPar──▶ ¿es válido sintácticamente? (sí/no + por qué)
```

**Analogía:** YALex reconoce las *palabras*; YAPar revisa la *gramática* de la
oración. "El gato come" tiene palabras válidas (léxico OK) y estructura válida
(sintaxis OK). "Come gato el el" tiene palabras válidas pero mala estructura
(error sintáctico).

Nuestro YAPar construye **dos tipos de analizador** ascendente, **SLR(1)** y
**LALR(1)**, y permite compararlos.

---

## 2. Conceptos clave (para defender en clase)

| Término | Qué es | Ejemplo en nuestra gramática |
|---|---|---|
| **Token / Terminal** | Símbolo atómico que produce el lexer | `SENTENCE`, `AND`, `LBRACKET` |
| **No-terminal** | Variable de la gramática (se reescribe) | `s`, `p`, `q` |
| **Producción** | Regla `cabeza → cuerpo` | `s → s AND p` |
| **Gramática aumentada** | Se añade `S' → S` para tener un único estado de aceptación | `s' → s` |
| **ε (epsilon)** | Producción vacía | `ep → ε` |

### Análisis ascendente (bottom-up)
El parser lee tokens de izquierda a derecha y mantiene una **pila**. En cada paso
elige entre:
- **shift (desplazar):** mete el token de entrada en la pila.
- **reduce (reducir):** reconoce que la cima de la pila es el cuerpo de una
  producción `A → β` y lo reemplaza por `A` (esto reconstruye el árbol "de abajo
  hacia arriba"). A `β` se le llama **handle** (mango).
- **accept:** la entrada completa se redujo al símbolo inicial.

### Autómata LR(0)
- Un **item LR(0)** es una producción con un punto que marca lo ya leído:
  `s → s · AND p`.
- **CLOSURE(I):** si el punto está antes de un no-terminal `B`, se añaden las
  producciones `B → ·γ` (porque podríamos empezar a reconocer una `B` aquí).
- **GOTO(I, X):** mueve el punto sobre el símbolo `X` y vuelve a cerrar.
- El **autómata LR(0)** es el conjunto de todos esos estados (conjuntos de items)
  conectados por GOTO. Sus estados son las "situaciones" posibles del parser.

### FIRST y FOLLOW
- **FIRST(α):** terminales con los que puede *empezar* lo derivable de α.
- **FOLLOW(A):** terminales que pueden aparecer *justo después* de `A`.
- Sirven para decidir **cuándo reducir**.

### SLR(1) vs LALR(1)
Ambos usan los mismos estados del autómata LR(0). La diferencia es **cuándo
reducen** `A → β`:
- **SLR(1):** reduce si el siguiente token está en **FOLLOW(A)** (global, poco
  preciso).
- **LALR(1):** cada item lleva un **lookahead** propio; reduce solo ante ese
  lookahead (preciso). Se obtiene construyendo el autómata **LR(1)** y
  **fusionando** los estados con el mismo núcleo LR(0).

### Conflictos
Cuando una celda de la tabla pediría dos acciones:
- **shift/reduce:** se puede desplazar o reducir (ej. *dangling else*).
- **reduce/reduce:** dos reducciones posibles.
Si hay conflictos, la gramática **no** es de ese tipo. Nuestro generador los
**reporta** (no los esconde) y, si hay que seguir, resuelve al estilo *yacc*
(prefiere shift; en reduce/reduce, la producción de menor número).

### La jerarquía SLR ⊂ LALR ⊂ LR(1)
Cada método acepta más gramáticas que el anterior. Lo demostramos con ejemplos
reales (ver §7): la gramática de **punteros** es LALR pero **no** SLR; la
gramática **Dragon 4.49** es LR(1) pero **no** LALR.

---

## 3. Cómo funciona por dentro (arquitectura)

```
  .yal  ──YALex (yalexgen/)──▶  lexer.py  ──Lexer(text).tokenize()──▶ [Token...]
                                                                          │
  .yalp ──YAPar (yapargen/)──▶ Grammar ─▶ aumentar ─▶ FIRST / FOLLOW       │
                                  │                                        │
                                  ├─▶ Autómata LR(0)   ─▶ Tabla SLR(1)      │
                                  └─▶ Autómata LALR(1) ─▶ Tabla LALR(1)     │
                                                                          ▼
              [Token...] ─▶ Motor de parseo (shift/reduce) ─▶ ACEPTA / RECHAZA
                                                          (+ traza, árbol, errores)
```

**Contrato YALex ↔ YAPar:** el lexer expone `Lexer(text).tokenize()`, que
entrega objetos `Token(type, lexeme, line, column)`. YAPar usa `token.type` como
terminal de la gramática. Los nombres de `%token` en el `.yalp` deben coincidir
con los `return TOKEN` del `.yal` (lo verifica el "contrato de tokens").

### Módulos (`yapargen/`)

| Módulo | Responsabilidad | Etapa |
|---|---|---|
| `yapar_reader.py` | Lee `%token`, `IGNORE`, separador `%%` | (base) |
| `yapar_parser.py` | Producciones → `Grammar`; valida errores gramaticales | 1 |
| `grammar.py` | `Production`, `Grammar`, aumentación, orden de símbolos | 1 |
| `first_follow.py` | FIRST, FOLLOW (punto fijo) | 2 |
| `lr0_items.py` | Item LR(0), CLOSURE, GOTO | 2 |
| `lr0_automaton.py` | Colección canónica LR(0) (BFS) | 3 |
| `visualize.py` | Render del autómata (`.dot`/`.png`/texto) y del árbol | 3 |
| `slr_table.py` | Tabla SLR(1) (usa FOLLOW) + impresión | 4 |
| `parse_runner.py` / `slr_parser.py` | Motor shift/reduce + traza | 4 |
| `diagnostics.py` | Reporte de conflictos | 4 |
| `lr1_items.py` | Item LR(1), CLOSURE1, GOTO1 | 5 |
| `lalr_automaton.py` | LR(1) canónico + fusión de núcleos → LALR | 5 |
| `lalr_table.py` | Tabla LALR(1) (lookahead del item) | 5 |
| `codegen.py` | Emite un parser `.py` autónomo | 6 |
| `pipeline.py` | Orquesta todo (`analyze`) | 6 |
| `token_contract.py` | Valida YALex ↔ YAPar | (base) |

---

## 4. Cómo se usa (manual)

### Instalación
```bash
cd yalex_project/yalex_project
python3 -m pip install --user -r requirements.txt   # matplotlib, reportlab
```

### YALex (analizador léxico)
```bash
python3 run_generator.py examples/pico/pico.yal -o build/pico_lexer.py --graph build/pico_ast.png
python3 build/pico_lexer.py examples/pico/hello.pico --with-lexeme
```

### YAPar (analizador sintáctico) — comando principal
```bash
python3 run_yapar.py  GRAMÁTICA.yalp  [-l LEXER.yal]  [-i ENTRADA]  [opciones]
```

| Opción | Significado |
|---|---|
| `-l, --yalex FILE` | Lexer `.yal`: activa el flujo completo (tokeniza la entrada) |
| `-i, --input FILE` | Archivo de cadenas a analizar sintácticamente |
| `-o, --output DIR` | Carpeta de salida (por defecto `build/yapar`) |
| `--parser {slr,lalr,both}` | Qué tabla construir (por defecto `both`) |
| `--no-graph` | No generar PNG (solo `.dot` y `.txt`) |
| `-v, --verbose` | Detalle por paso |

**Ejemplo completo (lexer + gramática + cadena):**
```bash
python3 run_yapar.py examples/yapar/expr_slr.yalp \
    -l examples/yapar/expr.yal \
    -i examples/yapar/inputs/accept_or.txt --parser both
```

**Sin lexer** (la entrada se interpreta como nombres de token separados por espacios):
```bash
python3 run_yapar.py examples/yapar/expr_slr.yalp --parser slr
echo "SENTENCE OR SENTENCE" | python3 build/yapar/expr_slr_slr_parser.py
```

### Códigos de salida de `run_yapar.py`
- `0` — todo bien (y si hubo `-i`, la cadena fue **aceptada**).
- `1` — error (archivo no existe, gramática inválida, error léxico, o cadena **rechazada**).
- `2` — la tabla tiene **conflictos** (la gramática no es de ese tipo).

### Ejemplos incluidos (`examples/yapar/`)

| Gramática | Lexer | Demuestra |
|---|---|---|
| `expr_slr.yalp` | `expr.yal` | Gramática SLR canónica de la actividad (oráculo) |
| `ptr_lalr.yalp` | `ptr.yal` | **LALR sí, SLR no** (conflicto shift/reduce) |
| `lr1_not_lalr.yalp` | — | **LR(1) sí, LALR no** (conflicto reduce/reduce) |
| `expr_eps.yalp` | `arith.yal` | Producciones **epsilon** (nullable) |
| `expr_ignore.yalp` | `expr_ws.yal` | Directiva **IGNORE** (el parser descarta `WS`) |

### Regenerar el informe PDF
```bash
python3 tools/build_report.py        # -> docs/Informe_YALex_YAPar.pdf
```

### Pruebas
```bash
python3 -m unittest discover -s tests   # 12 YALex + 39 YAPar
python3 run_smoke_tests.py              # flujo end-to-end de ambos
```

---

## 5. Cómo interpretar la salida

Al correr `run_yapar.py` se imprime, en orden:

1. **Gramática**: tokens, no-terminales, símbolo inicial y producciones numeradas
   `R1..Rn`.
2. **Contrato YALex/YAPar** (si hay `-l`): qué emite el lexer vs. qué espera la
   gramática.
3. **Gramática aumentada**: con `s' → s` (la regla `(0)` = aceptación).
4. **FIRST / FOLLOW** de cada no-terminal.
5. **Autómata LR(0)**: cada estado `Ii` con sus items y transiciones `--X--> Ij`.
   Se guardan imágenes `*_lr0.dot/.png/.txt`.
6. **Tabla SLR(1) y/o LALR(1)**: columnas = terminales (ACTION) + no-terminales
   (GOTO). Celdas:
   - `sN` = *shift* e ir al estado N.
   - `rN` = *reduce* por la regla N.
   - `acc` = *accept*.
   - vacío = error.
7. **Conflictos** (si los hay).
8. **Análisis de la cadena** (si hay `-i`): tabla **Stack | Input | Acción** paso
   a paso, y `CADENA ACEPTADA ✓` o `CADENA RECHAZADA ✗` con el mensaje de error
   (token inesperado, posición y tokens esperados).

---

## 6. Por qué confiamos en que es correcto (validación)

- **Oráculo manual:** el equipo resolvió a mano la actividad *"Construcción del
  Autómata LR(0)"* (gramática `s→s∧p|p; p→p∨q|q; q→[s]|sentence`). El programa
  reproduce **idénticamente**: los **12 estados** I0–I11, FIRST/FOLLOW, la tabla
  SLR **celda por celda** y la **traza** de `sentence ∨ sentence` (s5, r6, r4,
  s7, s5, r6, r3, r2, accept).
- **51 pruebas automáticas** (12 YALex + 39 YAPar) cubren gramática, FIRST/FOLLOW,
  autómata, tablas, parseo, LALR, epsilon, conflictos y el CLI.
- **Jerarquía verificada:** `ptr_lalr` (LALR no SLR) y `lr1_not_lalr`
  (LR(1) no LALR) salen exactamente como predice la teoría.
- **FIRST/FOLLOW de la gramática con epsilon** coinciden con los del libro de
  texto (Aho, Sethi, Ullman).

---

## 7. Guion de demostración en vivo

> Sugerencia: tener una terminal lista en `yalex_project/yalex_project/`.

**Demo 1 — Flujo SLR completo (el oráculo).** "Esta es la misma gramática que
resolvimos a mano; el programa saca lo mismo."
```bash
python3 run_yapar.py examples/yapar/expr_slr.yalp -l examples/yapar/expr.yal \
    -i examples/yapar/inputs/accept_or.txt --parser slr
```
Mostrar: gramática aumentada → FIRST/FOLLOW → autómata (abrir
`build/yapar/expr_slr_lr0.png`) → tabla SLR → **traza** que termina en `accept`.

**Demo 2 — SLR vs LALR (la diferencia "genial").**
```bash
python3 run_yapar.py examples/yapar/ptr_lalr.yalp -l examples/yapar/ptr.yal \
    -i examples/yapar/inputs/ptr_deref.txt --parser both
```
Señalar: **SLR reporta 1 conflicto shift/reduce** sobre `=`; **LALR: 0
conflictos** y acepta `* id = id`. "LALR usa lookaheads precisos."

**Demo 3 — El límite de LALR.**
```bash
python3 run_yapar.py examples/yapar/lr1_not_lalr.yalp --parser lalr --no-graph
```
"Esta gramática es LR(1) pero no LALR: al fusionar núcleos aparece un
reduce/reduce. Así se ve la jerarquía SLR ⊂ LALR ⊂ LR(1)."

**Demo 4 — Producciones epsilon.**
```bash
python3 run_yapar.py examples/yapar/expr_eps.yalp -l examples/yapar/arith.yal \
    -i examples/yapar/inputs/eps_paren.txt --parser slr
```
"Maneja gramáticas con producciones vacías; FIRST(ep) incluye ε."

**Demo 5 — Errores.**
```bash
# Error sintáctico (cadena mal formada):
python3 run_yapar.py examples/yapar/expr_slr.yalp -l examples/yapar/expr.yal \
    -i examples/yapar/inputs/reject_two.txt --parser slr
# Error gramatical (terminal sin declarar):
printf '%%token A\n%%%%\ns: A Z ;\n' > /tmp/mala.yalp
python3 run_yapar.py /tmp/mala.yalp --no-graph
```
Mostrar el mensaje con **posición** (línea/columna) y **tokens esperados**.

---

## 8. Preguntas probables del profesor (y respuestas)

**¿Por qué SLR y LALR tienen el mismo número de estados?**
Porque ambos parten del autómata **LR(0)**. LALR construye LR(1) y luego
**fusiona** los estados con el mismo núcleo LR(0), así que vuelve al tamaño de
LR(0); solo cambian los *lookaheads*.

**¿Cuál es la diferencia esencial entre SLR y LALR?**
*Cuándo reducen.* SLR reduce `A→β` ante todo **FOLLOW(A)** (global). LALR reduce
solo ante el **lookahead específico** de ese item en ese estado (local, más
preciso). Por eso LALR acepta gramáticas que SLR rechaza (ej. punteros).

**¿Cómo manejan las producciones epsilon?**
Una producción `A → ε` da un item `A → ·` que ya está *completo* (el punto al
final), así que genera una reducción. En FIRST/FOLLOW, ε se propaga: si todo el
cuerpo es anulable, ε entra en FIRST. Lo probamos con la gramática de
expresiones clásica (`ep`, `tp` anulables).

**¿Cómo detectan y resuelven conflictos?**
Al llenar la tabla, si una celda ya tiene una acción distinta, se registra el
conflicto (shift/reduce o reduce/reduce) con su estado y símbolo. Para poder
continuar se resuelve estilo *yacc*: shift sobre reduce, y en reduce/reduce la
producción de menor número. Pero **se reporta**: si hay conflictos, la gramática
no es de ese tipo.

**¿Por qué la numeración de estados coincide con la del documento hecho a mano?**
El recorrido (BFS) visita los símbolos en un orden determinista: primero los
no-terminales por orden de definición, luego los terminales por primera
aparición. Eso reproduce exactamente I0, I1, … del documento.

**¿Qué pasa si la gramática es ambigua?**
Aparecen conflictos en la tabla (ej. *dangling else* → shift/reduce). El
programa lo reporta. Con la resolución estilo yacc todavía produce un parser
utilizable, pero avisa.

**¿Cómo se conecta YALex con YAPar?**
YAPar importa el `lexer.py` generado, llama `Lexer(texto).tokenize()` y usa el
`.type` de cada `Token` como terminal. La directiva `IGNORE` descarta tokens
(p. ej. espacios) antes de parsear. El "contrato de tokens" verifica que los
nombres coincidan.

**¿Qué es un *handle*?**
El cuerpo de una producción que está en la cima de la pila y que toca reducir;
es la porción que el parser "reconoce" en ese paso.

**¿Generan código del parser?**
Sí: `codegen.py` emite un `.py` autónomo (sin dependencias del paquete) que
embebe las tablas ACTION/GOTO y el motor; se puede usar junto al lexer.

---

## 9. Checklist antes de presentar

- [ ] `python3 -m pip install --user -r requirements.txt`
- [ ] `python3 -m unittest discover -s tests` → **OK** (51 pruebas)
- [ ] `python3 run_smoke_tests.py` → sale `exit 0`
- [ ] Tener abiertas las imágenes `build/yapar/expr_slr_lr0.png` y
      `expr_slr_lalr.png`.
- [ ] Tener el informe `docs/Informe_YALex_YAPar.pdf` a la mano.
- [ ] Repasar §7 (guion) y §8 (preguntas).
- [ ] Repartir quién explica qué (sugerencia: léxico → Ian, autómata/tablas →
      Cifuentes, SLR vs LALR y demo → López).
