"""Genera el informe PDF del proyecto YALex + YAPar.

El informe es *dinámico*: las tablas, trazas, conjuntos FIRST/FOLLOW, ejemplos de
CLOSURE/GOTO, la fusión de núcleos LALR y los diagramas se obtienen ejecutando el
propio generador (``analyze``), de modo que el PDF siempre refleja la salida real
del programa.  Requiere ``reportlab`` y ``matplotlib``.

    python3 tools/build_report.py            # -> docs/Informe_YALex_YAPar.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, ListFlowable, ListItem, PageBreak,
    Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from yapargen.grammar import END_MARKER
from yapargen.lalr_automaton import build_canonical_lr1
from yapargen.lr1_items import LR1Item, merge_lookaheads
from yapargen.pipeline import analyze, format_sets
from yapargen.parse_runner import format_trace, run_parse
from yapargen.slr_table import format_table
from yapargen.visualize import automaton_to_text, render_automaton, render_parse_tree
from yapargen.yapar_parser import YAParParser

ASSETS = ROOT / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

INTEGRANTES = [
    ("Ian Cumes", "23236"),
    ("Javier Cifuentes", "23079"),
    ("Javier López", "28415"),
]

REPO_URL = "https://github.com/jlope384/Generador-lex"
VIDEO_URL = "https://drive.google.com/drive/folders/16mCpZSuuPGhA4c89ACrT-Dv8gn2OexDx"


# ── estilos ───────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=colors.HexColor("#1a5276"), spaceBefore=14, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor("#21618c"), fontSize=12, spaceBefore=9, spaceAfter=3)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], alignment=TA_JUSTIFY, fontSize=10, leading=14, spaceAfter=6)
CODE = ParagraphStyle("Code", parent=styles["Code"], fontSize=7.0, leading=8.4, backColor=colors.HexColor("#f4f6f7"), borderPadding=4, textColor=colors.HexColor("#212f3d"))
PSE = ParagraphStyle("Pse", parent=styles["Code"], fontSize=7.6, leading=9.4, backColor=colors.HexColor("#fbeee6"), borderPadding=5, textColor=colors.HexColor("#212f3d"))
CAP = ParagraphStyle("Cap", parent=styles["Italic"], fontSize=8.5, alignment=TA_CENTER, textColor=colors.HexColor("#555"), spaceAfter=10)
TITLE = ParagraphStyle("Title2", parent=styles["Title"], fontSize=24, textColor=colors.HexColor("#154360"))
SUB = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=13, alignment=TA_CENTER, textColor=colors.HexColor("#21618c"))
CENTER = ParagraphStyle("Center", parent=styles["Normal"], alignment=TA_CENTER, fontSize=11, leading=16)


def P(text, style=BODY):
    return Paragraph(text, style)


def bullets(items, style=BODY):
    return ListFlowable([ListItem(P(t, style), leftIndent=10) for t in items],
                        bulletType="bullet", start="•", leftIndent=12)


def code_block(text, style=CODE):
    return Preformatted(text, style)


def pseudo(title, text):
    return KeepTogether([P(f"<b>{title}</b>", H2), Preformatted(text, PSE)])


def fit_image(path: Path, max_w=6.6 * inch, max_h=7.4 * inch):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    ratio = min(max_w / w, max_h / h)
    return Image(str(path), width=w * ratio, height=h * ratio)


def figure(path: Path, caption: str, max_w=6.6 * inch, max_h=7.2 * inch):
    return KeepTogether([fit_image(path, max_w, max_h), P(caption, CAP)])


def state_box(title, lines):
    """Una caja tipo 'estado de autómata' para los ejemplos paso a paso."""
    body = title + "\n" + "\n".join(lines)
    t = Table([[Preformatted(body, CODE)]], colWidths=[3.0 * inch])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#2e86c1")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eaf2f8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


# ── contenido ───────────────────────────────────────────────────────────────
def build():
    expr = analyze(YAParParser().parse_file(ROOT / "examples/yapar/expr_slr.yalp"))
    ptr = analyze(YAParParser().parse_file(ROOT / "examples/yapar/ptr_lalr.yalp"))
    eps = analyze(YAParParser().parse_file(ROOT / "examples/yapar/expr_eps.yalp"))
    lr1 = analyze(YAParParser().parse_file(ROOT / "examples/yapar/lr1_not_lalr.yalp"))

    render_automaton(expr.lr0, ASSETS / "expr_lr0.png", "Autómata LR(0) — gramática SLR")
    render_automaton(expr.lalr, ASSETS / "expr_lalr.png", "Autómata LALR(1) — gramática SLR")
    render_automaton(ptr.lr0, ASSETS / "ptr_lr0.png", "Autómata LR(0) — gramática de punteros")
    render_automaton(eps.lr0, ASSETS / "eps_lr0.png", "Autómata LR(0) — gramática con epsilon")
    tree = run_parse(expr.slr_table, ["SENTENCE", "OR", "SENTENCE"]).tree
    render_parse_tree(tree, ASSETS / "expr_tree.png")

    s = []  # story

    # ───────────────────────────────── Portada ────────────────────────────
    s += [Spacer(1, 1.0 * inch)]
    s += [P("Universidad del Valle de Guatemala", SUB)]
    s += [P("Facultad de Ingeniería — CC3071 Diseño de Lenguajes de Programación", SUB)]
    s += [Spacer(1, 0.6 * inch)]
    s += [P("YALex &amp; YAPar", TITLE)]
    s += [P("Generador de Analizadores Léxicos y Sintácticos", SUB)]
    s += [P("Tablas de parseo SLR(1) y LALR(1)", SUB)]
    s += [Spacer(1, 0.7 * inch)]
    s += [P("<b>Integrantes</b>", CENTER)]
    s += [P("<br/>".join(f"{n} — {c}" for n, c in INTEGRANTES), CENTER)]
    s += [Spacer(1, 0.4 * inch)]
    s += [P("Informe técnico — implementación, algoritmos, validación y uso", CENTER)]
    s += [PageBreak()]

    # ───────────────────────── 0. Resumen ejecutivo ───────────────────────
    s += [P("Resumen ejecutivo", H1)]
    s += [P(
        "Se construyó un ecosistema completo de generación de analizadores: "
        "<b>YALex</b> (léxico, a partir de expresiones regulares) y <b>YAPar</b> "
        "(sintáctico, a partir de una gramática libre de contexto). YAPar implementa "
        "<b>dos</b> métodos de análisis ascendente, <b>SLR(1)</b> y <b>LALR(1)</b>, "
        "incluyendo la construcción del autómata LR(0), el cálculo de FIRST/FOLLOW, "
        "las tablas de parseo, un motor de parseo con traza paso a paso, generación "
        "de un parser autónomo, visualización del autómata y reporte de errores "
        "sintácticos y gramaticales. La implementación se validó contra el "
        "documento manual de la actividad (autómata de 12 estados, tabla y traza "
        "idénticas) y con 51 pruebas automáticas.")]
    s += [HRFlowable(width="100%", color=colors.HexColor("#d5dbdb"))]

    # ───────────────────── 1. Introducción y objetivos ────────────────────
    s += [P("1. Introducción y objetivos", H1)]
    s += [P(
        "Un compilador procesa el código fuente en fases. La <b>fase léxica</b> "
        "divide el texto en <i>tokens</i> y la <b>fase sintáctica</b> verifica que "
        "esos tokens formen estructuras válidas según una gramática. Este proyecto "
        "genera ambos analizadores y, para el sintáctico, implementa SLR(1) y "
        "LALR(1) para poder compararlos.")]
    s += [bullets([
        "Producir tokens desde una especificación YALex.",
        "Construir el autómata LR(0) con CLOSURE, GOTO, FIRST y FOLLOW.",
        "Construir las tablas de parseo SLR(1) y LALR(1).",
        "Evaluar cadenas y determinar su corrección sintáctica.",
        "Reportar errores sintácticos y gramaticales durante el proceso.",
    ])]

    # ─────────────────── 2. Conceptos fundamentales ───────────────────────
    s += [P("2. Conceptos fundamentales (glosario)", H1)]
    s += [P(
        "<b>Análisis ascendente (bottom-up):</b> el parser lee los tokens de "
        "izquierda a derecha manteniendo una <i>pila</i>; reconstruye el árbol de "
        "derivación de las hojas hacia la raíz aplicando dos operaciones:")]
    s += [bullets([
        "<b>shift (desplazar):</b> introduce el token actual en la pila.",
        "<b>reduce (reducir):</b> reconoce que la cima de la pila es el cuerpo de "
        "una producción A→β (el <b>handle</b>) y lo sustituye por A.",
        "<b>accept:</b> la entrada se redujo al símbolo inicial → cadena válida.",
    ])]
    rows = [["Término", "Definición"],
            ["Terminal", "Token producido por el lexer (MAYÚSCULAS): SENTENCE, AND…"],
            ["No-terminal", "Variable de la gramática (minúsculas): s, p, q…"],
            ["Producción", "Regla cabeza → cuerpo, p. ej. s → s AND p"],
            ["Item LR(0)", "Producción con un punto: s → s · AND p"],
            ["Gramática aumentada", "Se añade S' → S para un único estado de aceptación"],
            ["FIRST(α)", "Terminales con que puede empezar lo derivable de α"],
            ["FOLLOW(A)", "Terminales que pueden seguir a A"],
            ["Prefijo viable", "Prefijo de una forma sentencial que puede estar en la pila"],
            ["Conflicto", "Una celda de la tabla pide dos acciones (shift/reduce o reduce/reduce)"]]
    t = Table(rows, colWidths=[1.5 * inch, 5.0 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f8")]),
    ]))
    s += [t, Spacer(1, 6)]
    s += [P(
        "<b>SLR(1) vs LALR(1):</b> ambos usan los mismos estados (los del autómata "
        "LR(0)); difieren en <i>cuándo reducen</i>. SLR reduce A→β ante todo "
        "<b>FOLLOW(A)</b>; LALR reduce solo ante el <b>lookahead propio</b> del "
        "item (más preciso). Esto define la jerarquía <b>SLR ⊂ LALR ⊂ LR(1)</b>: "
        "cada método acepta más gramáticas que el anterior (se demuestra en §13–14).")]

    # ───────────────────────── 3. Arquitectura ────────────────────────────
    s += [PageBreak()]
    s += [P("3. Arquitectura general", H1)]
    s += [P(
        "El flujo es una tubería de cuatro etapas. La frontera entre YALex y YAPar "
        "es el <b>contrato de tokens</b>: el lexer expone "
        "<font face='Courier'>Lexer(text).tokenize()</font>, que entrega "
        "<font face='Courier'>Token(type, lexeme, line, column)</font>; YAPar usa "
        "<font face='Courier'>type</font> como terminal.")]
    s += [code_block(
        "  .yal  --[YALex]-->  lexer.py  --tokenize()-->  [Token, Token, ...]\n"
        "                                                       |\n"
        "  .yalp --[YAPar]-->  Grammar --> aumentar --> FIRST / FOLLOW\n"
        "                         |                            |\n"
        "                         +--> Automata LR(0)   --> Tabla SLR(1)\n"
        "                         +--> Automata LALR(1)  --> Tabla LALR(1)\n"
        "                                                       |\n"
        "       [Token, ...] --> Motor de parseo (shift/reduce) --> ACEPTA / RECHAZA\n"
        "                                                  (+ traza, arbol, errores)")]
    rows = [["Módulo (yapargen/)", "Responsabilidad"],
            ["yapar_reader", "Lee %token, IGNORE y el separador %%"],
            ["yapar_parser", "Producciones → Grammar; valida errores gramaticales"],
            ["grammar", "Production, Grammar, aumentación, orden de símbolos"],
            ["first_follow", "FIRST y FOLLOW por punto fijo"],
            ["lr0_items", "Item LR(0), CLOSURE, GOTO"],
            ["lr0_automaton", "Colección canónica LR(0) (BFS)"],
            ["slr_table", "Tabla SLR(1) e impresión"],
            ["lr1_items / lalr_automaton / lalr_table", "Items LR(1), fusión de núcleos, tabla LALR(1)"],
            ["parse_runner / slr_parser", "Motor shift/reduce con traza y árbol"],
            ["diagnostics", "Reporte de conflictos"],
            ["visualize", "Render del autómata (.dot/.png/.txt) y del árbol"],
            ["codegen", "Emite un parser .py autónomo"],
            ["pipeline", "Orquesta el análisis completo (analyze)"]]
    t = Table(rows, colWidths=[2.5 * inch, 4.0 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 1), (0, -1), "Courier"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f8")]),
    ]))
    s += [t]

    # ─────────────────── 4. El archivo .yalp ──────────────────────────────
    s += [P("4. El archivo .yalp y la gramática", H1)]
    s += [P(
        "El archivo tiene una sección de tokens (<font face='Courier'>%token</font>, "
        "<font face='Courier'>IGNORE</font>) y, tras <font face='Courier'>%%</font>, "
        "las producciones. Minúsculas = no-terminales; MAYÚSCULAS = terminales. El "
        "símbolo inicial es la primera producción.")]
    s += [code_block((ROOT / "examples/yapar/expr_slr.yalp").read_text(encoding="utf-8").strip())]
    s += [P("Gramática aumentada (la regla 0 es la de aceptación):", BODY)]
    s += [code_block("\n".join(
        f"({i}) {p}" + ("   <- aceptacion" if i == 0 else "")
        for i, p in enumerate(expr.augmented.productions)))]

    # ─────────────────── 5. FIRST y FOLLOW ─────────────────────────────────
    s += [PageBreak()]
    s += [P("5. FIRST y FOLLOW", H1)]
    s += [P("Se calculan por iteración de punto fijo hasta que los conjuntos no "
            "cambian. FIRST de una secuencia agrega FIRST del primer símbolo y, si "
            "es anulable, continúa con el siguiente; ε aparece si toda la secuencia "
            "es anulable.")]
    s += [pseudo("Algoritmo FIRST",
        "para cada terminal t:  FIRST(t) = { t }\n"
        "para cada no-terminal A:  FIRST(A) = {}\n"
        "repetir hasta que no haya cambios:\n"
        "  para cada produccion A -> X1 X2 ... Xn:\n"
        "    si es A -> e:  agregar e a FIRST(A)\n"
        "    si no:  FIRST(A) |= FIRST(X1 X2 ... Xn)")]
    s += [pseudo("Algoritmo FOLLOW",
        "FOLLOW(simbolo_inicial) = { $ }\n"
        "repetir hasta que no haya cambios:\n"
        "  para cada produccion A -> a B b   (B no-terminal):\n"
        "    FOLLOW(B) |= FIRST(b) \\ { e }\n"
        "    si e in FIRST(b):  FOLLOW(B) |= FOLLOW(A)")]
    nts = [nt for nt in expr.augmented.ordered_symbols()
           if nt in expr.augmented.non_terminals and nt != expr.augmented.start]
    s += [P("Resultado para la gramática de ejemplo:", BODY)]
    s += [code_block("FIRST\n" + format_sets(expr.first, nts) +
                     "\n\nFOLLOW\n" + format_sets(expr.follow, nts))]

    # ─────────────────── 6. Items LR(0), CLOSURE y GOTO ────────────────────
    s += [P("6. Items LR(0), CLOSURE y GOTO", H1)]
    s += [pseudo("CLOSURE(I)",
        "result = I\n"
        "repetir hasta estabilizar:\n"
        "  para cada item [A -> a . B b] en result   (B no-terminal):\n"
        "    para cada produccion B -> g:\n"
        "      agregar [B -> . g] a result")]
    s += [pseudo("GOTO(I, X)",
        "J = { [A -> a X . b]  por cada [A -> a . X b] en I }\n"
        "devolver CLOSURE(J)")]
    i0_lines = automaton_to_text(expr.lr0).split("I0")[1].split("I1")[0].strip().splitlines()[:7]
    s += [KeepTogether([
        P("<b>Ejemplo paso a paso.</b> El estado inicial es "
          "CLOSURE({s' → · s}). Como el punto precede a <font face='Courier'>s</font> "
          "(no-terminal), se agregan sus producciones; luego, como aparece "
          "<font face='Courier'>p</font> y <font face='Courier'>q</font> tras un "
          "punto, también las de ellos. El resultado es el estado I0:", BODY),
        state_box("I0 = CLOSURE({s' -> . s})", i0_lines)])]
    s += [Spacer(1, 6)]
    i1 = expr.lr0.transitions[(0, "s")]
    s += [KeepTogether([
        P(f"Y un paso de GOTO: GOTO(I0, s) mueve el punto sobre "
          f"<font face='Courier'>s</font> y cierra, dando I{i1}:", BODY),
        state_box(f"I{i1} = GOTO(I0, s)",
                  sorted(str(it) for it in expr.lr0.states[i1]))])]

    # ─────────────────── 7. Autómata LR(0) ─────────────────────────────────
    s += [PageBreak()]
    s += [P("7. Autómata LR(0)", H1)]
    s += [P(
        "La colección canónica se construye por BFS desde I0, generando un estado "
        "por cada conjunto de items alcanzable vía GOTO. La numeración de estados es "
        "determinista (no-terminales por orden de definición, luego terminales por "
        f"primera aparición), por lo que coincide con el documento manual: "
        f"<b>{len(expr.lr0.states)} estados</b> (I0–I11).")]
    s += [figure(ASSETS / "expr_lr0.png",
                 "Figura 1. Autómata LR(0) de la gramática SLR (12 estados).")]

    # ─────────────────── 8. Tabla SLR(1) ───────────────────────────────────
    s += [PageBreak()]
    s += [P("8. Tabla de parseo SLR(1)", H1)]
    s += [pseudo("Construcción de la tabla SLR(1)",
        "para cada estado i con conjunto de items I_i:\n"
        "  para [A -> a . x b] en I_i, x terminal y GOTO(I_i,x)=I_j:\n"
        "     ACTION[i, x] = shift j\n"
        "  para [A -> a .] en I_i  (A != S'):\n"
        "     para cada t en FOLLOW(A):  ACTION[i, t] = reduce A->a\n"
        "  para [S' -> S .] en I_i:  ACTION[i, $] = accept\n"
        "  para cada no-terminal A con GOTO(I_i,A)=I_j:  GOTO[i, A] = j")]
    s += [P("La tabla generada coincide celda por celda con el oráculo de la "
            "actividad (s# = shift, r# = reduce por la regla #, acc = accept):", BODY)]
    s += [code_block(format_table(expr.slr_table))]

    # ─────────────────── 9. Motor de parseo ────────────────────────────────
    s += [PageBreak()]
    s += [P("9. Motor de parseo y análisis de cadenas", H1)]
    s += [pseudo("Motor LR dirigido por tabla",
        "pila = [0];  ip = 0  (apunta al token actual, con $ al final)\n"
        "repetir:\n"
        "  s = cima(pila);  a = entrada[ip];  act = ACTION[s, a]\n"
        "  si act = shift t:  apilar t;  ip += 1\n"
        "  si act = reduce A->b:  desapilar |b| estados;  t = cima(pila)\n"
        "                         apilar GOTO[t, A]\n"
        "  si act = accept:  ACEPTAR\n"
        "  si act vacio:  ERROR sintactico (token inesperado)")]
    s += [P("Traza para <font face='Courier'>sentence ∨ sentence</font> (tokens "
            "<font face='Courier'>SENTENCE OR SENTENCE</font>), idéntica a la del "
            "documento manual:", BODY)]
    s += [code_block(format_trace(run_parse(expr.slr_table, ["SENTENCE", "OR", "SENTENCE"])))]
    s += [Spacer(1, 6)]
    s += [figure(ASSETS / "expr_tree.png",
                 "Figura 2. Árbol de parseo de <i>sentence ∨ sentence</i>.",
                 max_h=3.0 * inch)]

    # ─────────────────── 10. LALR(1) + fusión de núcleos ──────────────────
    s += [PageBreak()]
    s += [P("10. Construcción LALR(1) por fusión de núcleos", H1)]
    s += [pseudo("LALR(1) = LR(1) canónico + fusión",
        "1. construir la coleccion canonica LR(1) (CLOSURE1/GOTO1; cada item lleva\n"
        "   un lookahead terminal: [A -> a . b, t]).\n"
        "2. agrupar estados con el mismo NUCLEO LR(0) (items sin el lookahead).\n"
        "3. fusionar cada grupo en un estado: union de los lookaheads.\n"
        "   -> mismo numero de estados que LR(0), con lookaheads precisos.\n"
        "Reducir [A -> a ., t] ocurre SOLO ante t (no ante todo FOLLOW(A)).")]
    # Ejemplo dinámico de fusión: encontrar un núcleo con >1 estado LR(1).
    aug, lr1_states, _tr = build_canonical_lr1(
        YAParParser().parse_file(ROOT / "examples/yapar/expr_slr.yalp"))
    from collections import defaultdict
    by_core = defaultdict(list)
    for idx, st in enumerate(lr1_states):
        core = frozenset(it.core() for it in st)
        by_core[core].append(idx)
    merged_example = next((idxs for idxs in by_core.values() if len(idxs) >= 2), None)
    if merged_example:
        a_idx, b_idx = merged_example[0], merged_example[1]
        s += [P("<b>Ejemplo de fusión.</b> En el autómata LR(1) de la gramática de "
                "ejemplo, dos estados distintos comparten el mismo núcleo LR(0) "
                "(difieren solo en el lookahead). Al fusionarlos se unen sus "
                "lookaheads en un único estado LALR:", BODY)]
        s += [state_box(f"LR(1) estado A (#{a_idx})", merge_lookaheads(lr1_states[a_idx]))]
        s += [Spacer(1, 4)]
        s += [state_box(f"LR(1) estado B (#{b_idx})", merge_lookaheads(lr1_states[b_idx]))]
        s += [Spacer(1, 4)]
        union = frozenset(set(lr1_states[a_idx]) | set(lr1_states[b_idx]))
        s += [P("→ estado LALR fusionado:", BODY)]
        s += [state_box("LALR (A fusionado con B)", merge_lookaheads(union))]
    s += [Spacer(1, 8)]
    s += [P(f"Para la gramática de ejemplo, LALR produce <b>{len(expr.lalr.states)} "
            f"estados</b> (igual que LR(0)) y, por ser ya SLR, una tabla idéntica a "
            "la SLR. Cada estado muestra los lookaheads fusionados por núcleo:", BODY)]
    s += [figure(ASSETS / "expr_lalr.png",
                 "Figura 3. Autómata LALR(1) de la gramática SLR.")]

    # ─────────────────── 11. SLR vs LALR (punteros) ───────────────────────
    s += [PageBreak()]
    s += [P("11. SLR(1) vs LALR(1): la gramática de punteros", H1)]
    s += [P("Gramática clásica <font face='Courier'>S → L=R | R, L → *R | id, "
            "R → L</font>: es LALR(1) pero <b>no</b> SLR(1). SLR genera un conflicto "
            "shift/reduce sobre <font face='Courier'>=</font> porque "
            "<font face='Courier'>=</font> ∈ FOLLOW(R); LALR lo evita con lookaheads "
            "precisos.")]
    s += [_compare_table(ptr)]
    s += [Spacer(1, 6)]
    s += [P("Conflicto detectado por SLR(1):", BODY)]
    s += [code_block("\n".join(ptr.slr_table.conflicts) or "(ninguno)")]
    s += [P(f"LALR(1): {len(ptr.lalr_table.conflicts)} conflictos. Acepta cadenas "
            "como <font face='Courier'>* id = id</font>.", BODY)]
    s += [figure(ASSETS / "ptr_lr0.png",
                 "Figura 4. Autómata LR(0) de la gramática de punteros (10 estados).",
                 max_h=3.8 * inch)]

    # ─────────────────── 12. El límite de LALR (LR(1) no LALR) ─────────────
    s += [PageBreak()]
    s += [P("12. El límite de LALR: una gramática LR(1) que no es LALR(1)", H1)]
    s += [P("Gramática de Aho-Sethi-Ullman (ej. 4.49): "
            "<font face='Courier'>S → aAd | bBd | aBe | bAe, A → c, B → c</font>. "
            "Es LR(1), pero al fusionar núcleos los estados "
            "<font face='Courier'>{A→c·}</font> y <font face='Courier'>{B→c·}</font> "
            "(alcanzados por <font face='Courier'>a</font> y por "
            "<font face='Courier'>b</font>) se combinan y sus lookaheads "
            "<font face='Courier'>{d,e}</font> se unen, creando un conflicto "
            "<b>reduce/reduce</b> que LR(1) canónico no tiene. Es el límite conocido "
            "de LALR frente a LR(1).")]
    s += [_compare_table(lr1)]
    s += [Spacer(1, 6)]
    s += [P("Conflicto reduce/reduce detectado por LALR(1):", BODY)]
    s += [code_block("\n".join(lr1.lalr_table.conflicts) or "(ninguno)")]
    s += [P("<b>Conclusión de la jerarquía:</b> la gramática de punteros (§11) es "
            "LALR pero no SLR, y esta es LR(1) pero no LALR. Juntas demuestran "
            "<b>SLR ⊂ LALR ⊂ LR(1)</b>.", BODY)]

    # ─────────────────── 13. Producciones epsilon ─────────────────────────
    s += [PageBreak()]
    s += [P("13. Producciones epsilon (gramáticas anulables)", H1)]
    s += [P("Gramática de expresiones con producciones vacías "
            "<font face='Courier'>e→t e'; e'→+ t e' | ε; t→f t'; t'→* f t' | ε; "
            "f→( e ) | id</font>. Un item <font face='Courier'>e' → ·</font> está "
            "completo de inmediato (genera reducción), y ε se propaga en FIRST. Los "
            "FIRST/FOLLOW coinciden con los del libro de texto:")]
    nts_e = [nt for nt in eps.augmented.ordered_symbols()
             if nt in eps.augmented.non_terminals and nt != eps.augmented.start]
    s += [code_block("FIRST\n" + format_sets(eps.first, nts_e) +
                     "\n\nFOLLOW\n" + format_sets(eps.follow, nts_e))]
    s += [P(f"La gramática es SLR(1) ({len(eps.slr_table.conflicts)} conflictos) y "
            f"su autómata tiene {len(eps.lr0.states)} estados. Acepta entradas como "
            "<font face='Courier'>(x + y) * z</font>.", BODY)]
    s += [figure(ASSETS / "eps_lr0.png",
                 "Figura 5. Autómata LR(0) de la gramática con epsilon (16 estados).")]

    # ─────────────────── 14. Manejo de errores ────────────────────────────
    s += [PageBreak()]
    s += [P("14. Manejo de errores", H1)]
    s += [P("<b>Errores gramaticales</b> (al leer el .yalp): terminal usado sin "
            "<font face='Courier'>%token</font>, no-terminal sin definir, nombre de "
            "producción en mayúscula, bloque sin <font face='Courier'>:</font>, "
            "ausencia de <font face='Courier'>%%</font>. Ejemplos:")]
    s += [bullets([
        "<font face='Courier'>terminal 'Z' used in production 's' is not declared with %token</font>",
        "<font face='Courier'>non-terminal 'x' used in production 's' is never defined</font>",
        "<font face='Courier'>missing '%%' separator between token declarations and production rules</font>",
    ], style=ParagraphStyle("b", parent=BODY, fontSize=8.5, leading=12))]
    s += [P("<b>Errores sintácticos</b> (al parsear): cuando no hay acción en la "
            "celda (estado, token) se reporta el token inesperado, su posición "
            "(línea/columna, vía el Token del lexer) y los tokens esperados:", BODY)]
    bad = run_parse(expr.slr_table, ["SENTENCE", "SENTENCE"])
    import re as _re
    bad_trace = _re.sub(r"ERROR —.*", "ERROR (ver mensaje abajo)", format_trace(bad))
    s += [code_block(bad_trace)]

    # ─────────────────── 15. Uso del programa ─────────────────────────────
    s += [P("15. Uso del programa", H1)]
    s += [code_block(
        "# Lexer (YALex)\n"
        "python3 run_generator.py examples/pico/pico.yal -o build/pico_lexer.py\n\n"
        "# Parser (YAPar) — flujo completo lexer + gramatica + cadena\n"
        "python3 run_yapar.py examples/yapar/expr_slr.yalp \\\n"
        "    -l examples/yapar/expr.yal \\\n"
        "    -i examples/yapar/inputs/accept_or.txt --parser both\n\n"
        "# Parser autonomo generado\n"
        "echo 'SENTENCE OR SENTENCE' | python3 build/yapar/expr_slr_slr_parser.py")]
    s += [P("Opciones de <font face='Courier'>run_yapar.py</font>: "
            "<font face='Courier'>-l</font> (lexer), <font face='Courier'>-i</font> "
            "(entrada), <font face='Courier'>-o</font> (salida), "
            "<font face='Courier'>--parser slr|lalr|both</font>, "
            "<font face='Courier'>--no-graph</font>. Código de salida: 0 = OK/aceptada, "
            "1 = error/rechazada, 2 = la tabla tiene conflictos.", BODY)]

    # ─────────────────── 16. Pruebas ──────────────────────────────────────
    s += [P("16. Pruebas y validación", H1)]
    s += [bullets([
        "12 pruebas de YALex (PICO y ArnoldC; métodos directo y Thompson).",
        "39 pruebas de YAPar: gramática, FIRST/FOLLOW, autómata, tablas, parseo, "
        "LALR, epsilon, conflictos (shift/reduce, reduce/reduce, LR(1)-no-LALR) y CLI.",
        "Smoke test end-to-end (run_smoke_tests.py) de ambos generadores.",
        "Validación contra el oráculo manual: autómata de 12 estados, tabla SLR "
        "celda por celda y la traza de <i>sentence ∨ sentence</i>, idénticos.",
    ])]

    # ─────────────────── 17. Decisiones técnicas ──────────────────────────
    s += [P("17. Decisiones técnicas relevantes", H1)]
    s += [bullets([
        "<b>Numeración estable de estados:</b> el BFS recorre los símbolos en orden "
        "determinista, reproduciendo I0–I11 del documento manual.",
        "<b>LALR por fusión de núcleos:</b> método transparente y fácil de explicar; "
        "se construye LR(1) y se fusionan estados con el mismo núcleo LR(0).",
        "<b>Resolución de conflictos estilo yacc:</b> shift sobre reduce; en "
        "reduce/reduce, la producción de menor número. Los conflictos se reportan.",
        "<b>Lexer pure-ASCII:</b> las tablas embebidas se emiten con ascii() para "
        "evitar bytes 0x80–0xFF crudos que rompían el tokenizador de Python.",
        "<b>Parser autónomo:</b> codegen produce un .py sin dependencias de yapargen.",
    ])]

    # ─────────────────── 18. Apéndice: presentación ───────────────────────
    s += [PageBreak()]
    s += [P("Apéndice A. Puntos clave para la presentación", H1)]
    s += [P("<b>Ideas para defender:</b>", BODY)]
    s += [bullets([
        "SLR y LALR tienen los mismos estados (LR(0)); difieren en el lookahead de "
        "reduce: FOLLOW(A) global (SLR) vs lookahead del item (LALR).",
        "La jerarquía SLR ⊂ LALR ⊂ LR(1) se demuestra con dos gramáticas concretas "
        "(punteros y Dragon 4.49).",
        "Las producciones epsilon se manejan como items completos (A → ·) y "
        "propagación de ε en FIRST/FOLLOW.",
        "Los conflictos se detectan y reportan; se resuelven estilo yacc para poder "
        "continuar.",
        "La salida (autómata, tabla, traza) coincide con el trabajo hecho a mano, lo "
        "que da confianza en la correctitud.",
    ])]
    s += [P("<b>Preguntas probables y respuestas breves:</b>", BODY)]
    s += [bullets([
        "<i>¿Por qué mismos estados?</i> Porque LALR fusiona el LR(1) de vuelta al "
        "núcleo LR(0).",
        "<i>¿Cómo manejan ε?</i> Item A→· es reduce inmediato; ε se propaga en FIRST.",
        "<i>¿Cómo detectan conflictos?</i> Si una celda ya tiene otra acción, se "
        "registra (shift/reduce o reduce/reduce) con estado y símbolo.",
        "<i>¿Y si la gramática es ambigua?</i> Aparecen conflictos (ej. dangling "
        "else); se reportan y se resuelve estilo yacc.",
        "<i>¿Cómo se conecta con YALex?</i> Importa el lexer generado, usa "
        "Token.type como terminal; IGNORE descarta tokens.",
    ])]

    # ─────────────────── 19. Referencias ──────────────────────────────────
    s += [P("Apéndice B. Referencias y enlaces", H1)]
    s += [bullets([
        "Aho, Lam, Sethi, Ullman. <i>Compilers: Principles, Techniques, and Tools</i> "
        "(2.ª ed.), cap. 4 (análisis LR, SLR, LALR, FIRST/FOLLOW; ejemplos 4.48 y 4.49).",
        "Documentación de <font face='Courier'>ocamlyacc</font> / "
        "<font face='Courier'>yacc</font> (formato y resolución de conflictos).",
        "Documento de la actividad «Construcción del Autómata LR(0)» (oráculo de "
        "validación de este informe).",
        f"Repositorio del proyecto: <font face='Courier'>{REPO_URL}</font>",
        f"Video de arquitectura (YALex): <font face='Courier'>{VIDEO_URL}</font>",
    ])]

    out = ROOT / "docs" / "Informe_YALex_YAPar.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=letter,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        title="Informe YALex & YAPar", author=", ".join(n for n, _ in INTEGRANTES),
    )
    doc.build(s)
    print(f"Informe generado: {out}")
    return out


def _compare_table(an):
    rows = [["", "SLR(1)", "LALR(1)"],
            ["Estados", str(len(an.lr0.states)), str(len(an.lalr.states))],
            ["Conflictos", str(len(an.slr_table.conflicts)), str(len(an.lalr_table.conflicts))]]
    t = Table(rows, colWidths=[1.8 * inch, 1.6 * inch, 1.6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#eaf2f8")),
    ]))
    return t


if __name__ == "__main__":
    build()
