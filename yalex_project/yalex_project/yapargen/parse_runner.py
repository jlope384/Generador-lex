"""The table-driven LR parsing engine (shared by SLR and LALR).

``run_parse`` executes the standard shift/reduce loop against any table that
exposes ``action``, ``goto`` and ``grammar`` (so :class:`~yapargen.slr_table.
SLRTable` and ``LALRTable`` both work).  It records a step-by-step trace
(stack / input / action), reports the first syntax error with its position, and
optionally builds a parse tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional, Union

from .grammar import END_MARKER

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .slr_table import SLRTable
    from .lalr_table import LALRTable
    AnyTable = Union["SLRTable", "LALRTable"]


@dataclass
class ParseTreeNode:
    """A node of the parse tree (``label`` + ordered ``children``)."""

    label: str
    children: List["ParseTreeNode"] = field(default_factory=list)


@dataclass
class ParseStep:
    """One row of the parse trace."""

    stack: str
    input: str
    action: str


@dataclass
class ParseResult:
    """Outcome of a parse.

    Truthy iff the input was accepted, so ``if run_parse(...):`` reads naturally.
    """

    accepted: bool
    steps: List[ParseStep] = field(default_factory=list)
    error: Optional[str] = None
    tree: Optional[ParseTreeNode] = None

    def __bool__(self) -> bool:
        return self.accepted


def _terminal_of(tok: Any) -> str:
    """Terminal name for a token, which may be a bare string or a Token object."""
    if isinstance(tok, str):
        return tok
    return getattr(tok, "type", str(tok))


def _describe(terminal: str, tok: Any) -> str:
    if terminal == END_MARKER:
        return "el final de la entrada ($)"
    lexeme = getattr(tok, "lexeme", None)
    if lexeme:
        return f"el token {terminal} ('{lexeme}')"
    return f"el token {terminal}"


def _position(tok: Any) -> str:
    line = getattr(tok, "line", None)
    col = getattr(tok, "column", None)
    if line is not None and col is not None:
        return f" en línea {line}, columna {col}"
    return ""


def run_parse(table, tokens: List[Any], build_tree: bool = True) -> ParseResult:
    """Drive an LR parse of *tokens* using *table*.

    Args:
        table:      An SLR or LALR table (``action`` / ``goto`` / ``grammar``).
        tokens:     A list of terminal names (``str``) or token objects with a
                    ``.type`` attribute (e.g. the YALex-generated ``Token``).
        build_tree: When true, assemble a :class:`ParseTreeNode` tree.

    Returns:
        A :class:`ParseResult` with the trace, accept flag and (on failure) the
        error message.
    """
    grammar = table.grammar
    prod_index = grammar.production_index()

    terminals = [_terminal_of(t) for t in tokens] + [END_MARKER]
    originals = list(tokens) + [END_MARKER]

    state_stack: List[int] = [0]
    symbol_stack: List[str] = []
    node_stack: List[ParseTreeNode] = []
    steps: List[ParseStep] = []
    ip = 0

    def stack_repr() -> str:
        out = str(state_stack[0])
        for sym, st in zip(symbol_stack, state_stack[1:]):
            out += f" {sym} {st}"
        return out

    def input_repr() -> str:
        return " ".join(terminals[ip:])

    while True:
        state = state_stack[-1]
        a = terminals[ip]
        action = table.action.get((state, a))

        if action is None:
            tok = originals[ip]
            expected = sorted(sym for (st, sym) in table.action if st == state)
            msg = (
                f"Error sintáctico: no se esperaba {_describe(a, tok)}"
                f"{_position(tok)}. "
                f"Se esperaba uno de: {', '.join(expected) if expected else '(nada)'}."
            )
            steps.append(ParseStep(stack_repr(), input_repr(), f"ERROR — {msg}"))
            return ParseResult(False, steps, error=msg)

        kind, value = action

        if kind == "shift":
            steps.append(ParseStep(stack_repr(), input_repr(), f"shift -> I{value}"))
            symbol_stack.append(a)
            state_stack.append(value)
            if build_tree:
                tok = originals[ip]
                lexeme = getattr(tok, "lexeme", None)
                label = a if not lexeme or lexeme == a else f"{a}\n{lexeme}"
                node_stack.append(ParseTreeNode(label))
            ip += 1

        elif kind == "reduce":
            prod = value
            k = len(prod.body)
            desc = f"reduce r{prod_index[prod]}: {prod}"
            steps.append(ParseStep(stack_repr(), input_repr(), desc))
            children: List[ParseTreeNode] = []
            for _ in range(k):
                symbol_stack.pop()
                state_stack.pop()
                if build_tree:
                    children.append(node_stack.pop())
            children.reverse()
            t = state_stack[-1]
            goto_state = table.goto.get((t, prod.head))
            if goto_state is None:
                msg = (
                    f"Error interno: no hay GOTO[I{t}, {prod.head}] tras reducir "
                    f"{prod}."
                )
                steps.append(ParseStep(stack_repr(), input_repr(), f"ERROR — {msg}"))
                return ParseResult(False, steps, error=msg)
            symbol_stack.append(prod.head)
            state_stack.append(goto_state)
            if build_tree:
                if not children:
                    children = [ParseTreeNode("ε")]
                node_stack.append(ParseTreeNode(prod.head, children))

        elif kind == "accept":
            steps.append(ParseStep(stack_repr(), input_repr(), "accept"))
            tree = node_stack[-1] if (build_tree and node_stack) else None
            return ParseResult(True, steps, tree=tree)

        else:  # pragma: no cover - defensive
            msg = f"Acción desconocida en la tabla: {action!r}"
            return ParseResult(False, steps, error=msg)


def format_trace(result: ParseResult) -> str:
    """Render a :class:`ParseResult` trace as an aligned ``Stack/Input/Acción`` table."""
    rows = [("Stack", "Input", "Acción")] + [
        (s.stack, s.input, s.action) for s in result.steps
    ]
    w0 = max(len(r[0]) for r in rows)
    w1 = max(len(r[1]) for r in rows)
    lines = []
    header = rows[0]
    lines.append(f"{header[0]:<{w0}}  |  {header[1]:<{w1}}  |  {header[2]}")
    lines.append("-" * w0 + "--+--" + "-" * w1 + "--+--" + "-" * 24)
    for stack, inp, act in rows[1:]:
        lines.append(f"{stack:<{w0}}  |  {inp:<{w1}}  |  {act}")
    verdict = "CADENA ACEPTADA ✓" if result.accepted else "CADENA RECHAZADA ✗"
    lines.append("")
    lines.append(verdict)
    if result.error:
        lines.append(result.error)
    return "\n".join(lines)
