from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .action_parser import ActionInfo, parse_action
from .dfa import EOF_SENTINEL, minimize_dfa
from .direct_dfa import regexes_to_direct_dfa
from .regex_ast import Charset, Concat, EOFMarker, Epsilon, Literal, OptionalNode, Plus, RegexNode, Star, Tagged, UnionNode
from .regex_parser import ASCII_UNIVERSE, RegexParser
from .thompson import combine_rule_nfas, nfa_to_dfa
from .yalex_parser import YALexParser, YALexSpec


@dataclass
class GeneratedArtifacts:
    spec: YALexSpec
    python_path: Path
    graph_path: Path
    dfa_state_count: int
    dfa_state_count_before_minimization: int
    method: str


class YALexGenerator:
    def __init__(self, universe=ASCII_UNIVERSE):
        self.universe = universe

    def load_spec(self, path: str | os.PathLike[str]) -> YALexSpec:
        text = Path(path).read_text(encoding='utf-8')
        return YALexParser().parse(text)

    def generate(
        self,
        yal_path: str | os.PathLike[str],
        output_py: str | os.PathLike[str],
        graph_path: Optional[str | os.PathLike[str]] = None,
        method: str = "direct",
    ) -> GeneratedArtifacts:
        if method not in {"direct", "thompson"}:
            raise ValueError(f"Unknown construction method {method!r}; expected 'direct' or 'thompson'")

        spec = self.load_spec(yal_path)
        parser = RegexParser(spec.definitions, universe=self.universe)

        rule_asts: List[RegexNode] = []
        visual_roots: List[RegexNode] = []
        action_infos: List[ActionInfo] = []
        eof_action: Optional[ActionInfo] = None
        regex_texts: List[str] = []

        non_eof_index = 0
        for entry in spec.entries:
            if entry.regex_text.strip() == 'eof':
                eof_action = parse_action(entry.action_text)
                continue
            ast = parser.parse(entry.regex_text)
            # Nullable regexes would cause the lexer to loop forever on empty matches
            if self._is_nullable(ast):
                raise ValueError(f"Rule regex can match the empty string, which would loop forever: {entry.regex_text!r}")
            rule_asts.append(ast)
            visual_roots.append(Tagged(ast, f'R{non_eof_index}'))
            action_infos.append(parse_action(entry.action_text))
            regex_texts.append(entry.regex_text)
            non_eof_index += 1

        if not rule_asts:
            raise ValueError('No non-eof regex rules were found in the YALex file')

        visual_root = visual_roots[0]
        for nxt in visual_roots[1:]:
            visual_root = UnionNode(visual_root, nxt)

        alphabet = [*self.universe, EOF_SENTINEL]
        raw_dfa = self._build_dfa(rule_asts, alphabet, method)
        dfa = minimize_dfa(raw_dfa, alphabet)

        graph = Path(graph_path) if graph_path else Path(output_py).with_suffix('.ast.png')
        graph.parent.mkdir(parents=True, exist_ok=True)
        from .visualize import ASTGrapher

        ASTGrapher().save_png(visual_root, str(graph), title=f'Expression Tree — {Path(yal_path).name}')

        out_path = Path(output_py)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(self._render_python(spec, dfa, action_infos, eof_action, regex_texts, method), encoding='utf-8')
        return GeneratedArtifacts(
            spec=spec,
            python_path=out_path,
            graph_path=graph,
            dfa_state_count=len(dfa.transitions),
            dfa_state_count_before_minimization=len(raw_dfa.transitions),
            method=method,
        )

    def _build_dfa(self, rule_asts: List[RegexNode], alphabet: List[str], method: str):
        if method == "direct":
            return regexes_to_direct_dfa(rule_asts, alphabet)
        nfa = combine_rule_nfas(rule_asts)
        return nfa_to_dfa(nfa, alphabet)

    def _is_nullable(self, node: RegexNode) -> bool:
        if isinstance(node, Epsilon):
            return True
        if isinstance(node, (Literal, Charset, EOFMarker)):
            return False
        if isinstance(node, Concat):
            return self._is_nullable(node.left) and self._is_nullable(node.right)
        if isinstance(node, UnionNode):
            return self._is_nullable(node.left) or self._is_nullable(node.right)
        if isinstance(node, Star):
            return True
        if isinstance(node, OptionalNode):
            return True
        if isinstance(node, Plus):
            return self._is_nullable(node.child)
        if isinstance(node, Tagged):
            return self._is_nullable(node.child)
        raise TypeError(f'Unsupported regex node for nullability check: {type(node)!r}')

    def _render_python(self, spec: YALexSpec, dfa, action_infos: List[ActionInfo], eof_action: Optional[ActionInfo], regex_texts: List[str], method: str) -> str:
        actions_payload = [ai.__dict__ for ai in action_infos]
        eof_payload = eof_action.__dict__ if eof_action else None
        token_names = sorted({ai.token_name for ai in action_infos if ai.token_name})
        if eof_action and eof_action.token_name:
            token_names.append(eof_action.token_name)
        token_names = sorted(set(token_names))
        token_defaults = '\n'.join([f"globals().setdefault('{name}', '{name}')" for name in token_names])
        header = spec.header.strip()
        trailer = spec.trailer.strip()
        sections = [
            "# -*- coding: utf-8 -*-",
            f"# Auto-generated by yalexgen from {spec.entrypoint}",
            "from __future__ import annotations",
            "",
            "import argparse",
            "from dataclasses import dataclass",
            "from pathlib import Path",
            "from typing import Iterator, Optional",
            "",
        ]
        if header:
            sections.append(header)
            sections.append("")
        if token_defaults:
            sections.append(token_defaults)
            sections.append("")
        sections.extend(
            [
                # Use ascii() (not repr()) so all embedded tables are pure-ASCII
                # source: characters in 0x80-0xFF (from negated sets over the full
                # byte universe) are emitted as \xNN escapes instead of raw bytes,
                # which keeps the generated file tokenizable on every platform.
                f"DFA_TRANSITIONS = {ascii(dfa.transitions)}",
                f"DFA_ACCEPTS = {ascii(dfa.accepts)}",
                f"DFA_METHOD = {method!r}",
                f"ACTIONS = {ascii(actions_payload)}",
                f"EOF_ACTION = {ascii(eof_payload)}",
                f"EOF_SENTINEL = {ascii(EOF_SENTINEL)}",
                f"RULE_REGEXES = {ascii(regex_texts)}",
                "",
                "@dataclass",
                "class Token:",
                "    type: str",
                "    lexeme: str",
                "    line: int",
                "    column: int",
                "    value: object = None",
                "",
                "    def __str__(self) -> str:",
                "        return self.type if self.value is None else f'{self.type}({self.value!r})'",
                "",
                "",
                "class LexicalError(Exception):",
                "    pass",
                "",
                "",
                "class Lexer:",
                "    def __init__(self, text: str):",
                "        self.text = text",
                "        self.pos = 0",
                "        self.line = 1",
                "        self.column = 1",
                "        self._eof_done = False",
                "",
                "    def tokenize(self) -> Iterator[Token]:",
                "        while self.pos < len(self.text):",
                "            token = self._next_token()",
                "            if token is not None:",
                "                yield token",
                "        eof_token = self._handle_eof()",
                "        if eof_token is not None:",
                "            yield eof_token",
                "",
                "    def _advance_position(self, lexeme: str) -> None:",
                "        for ch in lexeme:",
                "            if ch == '\\n':",
                "                self.line += 1",
                "                self.column = 1",
                "            else:",
                "                self.column += 1",
                "        self.pos += len(lexeme)",
                "",
                "    def _diagnose_error(self, start: int, line: int, col: int) -> str:",
                "        if start < len(self.text) and self.text[start] == '\"':",
                "            j = start + 1",
                "            escaped = False",
                "            while j < len(self.text):",
                "                c = self.text[j]",
                "                if escaped:",
                "                    escaped = False",
                "                elif c == '\\\\':",
                "                    escaped = True",
                "                elif c == '\"':",
                "                    break",
                "                elif c == '\\n':",
                "                    return f'LEXICAL ERROR at line {line}, column {col}: Unterminated string literal'",
                "                j += 1",
                "        if start < len(self.text) and self.text[start].isdigit():",
                "            j = start",
                "            while j < len(self.text) and self.text[j].isdigit():",
                "                j += 1",
                "            if j < len(self.text) and self.text[j] == '.':",
                "                if j + 1 >= len(self.text) or not self.text[j + 1].isdigit():",
                "                    bad = self.text[start:j + 1]",
                "                    return f\"LEXICAL ERROR at line {line}, column {col}: Unrecognized token {bad!r} - float requires digits after the decimal point\"",
                "        if start < len(self.text) and self.text[start] == '.' and start > 0 and self.text[start - 1].isdigit():",
                "            j = start - 1",
                "            while j > 0 and self.text[j - 1].isdigit():",
                "                j -= 1",
                "            bad = self.text[j:start + 1]",
                "            return f\"LEXICAL ERROR at line {line}, column {col}: Unrecognized token {bad!r} - float requires digits after the decimal point\"",
                "        bad = self.text[start]",
                "        return f\"LEXICAL ERROR at line {line}, column {col}: Unrecognized character {bad!r}\"",
                "",
                "    def _next_token(self) -> Optional[Token]:",
                "        state = 0",
                "        i = self.pos",
                "        start_line, start_col = self.line, self.column",
                "        last_accept = None",
                "        last_pos = self.pos",
                "        consumed_eof = False",
                "        while True:",
                "            if i < len(self.text):",
                "                ch = self.text[i]",
                "                consumed = True",
                "            elif not consumed_eof:",
                "                ch = EOF_SENTINEL",
                "                consumed = False",
                "                consumed_eof = True",
                "            else:",
                "                break",
                "            next_state = DFA_TRANSITIONS.get(state, {}).get(ch)",
                "            if next_state is None:",
                "                break",
                "            state = next_state",
                "            if consumed:",
                "                i += 1",
                "            if state in DFA_ACCEPTS:",
                "                last_accept = DFA_ACCEPTS[state]",
                "                last_pos = i",
                "        if last_accept is None:",
                "            raise LexicalError(self._diagnose_error(self.pos, start_line, start_col))",
                "        lexeme = self.text[self.pos:last_pos]",
                "        action = ACTIONS[last_accept]",
                "        return self._apply_action(action, lexeme, start_line, start_col)",
                "",
                "    def _run_raw_action(self, source: str, lxm: str):",
                "        namespace = dict(globals())",
                "        namespace.update({'lxm': lxm, 'lexbuf': None})",
                "        func_src = 'def __yalex_action(lxm, lexbuf):\\n' + '\\n'.join('    ' + line for line in source.splitlines())",
                "        exec(func_src, namespace)",
                "        return namespace['__yalex_action'](lxm, None)",
                "",
                "    def _apply_action(self, action, lexeme: str, start_line: int, start_col: int) -> Optional[Token]:",
                "        kind = action['kind']",
                "        self._advance_position(lexeme)",
                "        if kind == 'skip':",
                "            return None",
                "        if kind == 'return_name':",
                "            return Token(action['token_name'], lexeme, start_line, start_col)",
                "        if kind == 'return_call':",
                "            token_name = action['token_name']",
                "            arg = (action.get('argument') or '').strip()",
                "            value = lexeme if arg in ('lxm', 'lexeme') else None",
                "            if value is None and arg:",
                "                try:",
                "                    value = eval(arg, dict(globals()), {'lxm': lexeme, 'lexeme': lexeme})",
                "                except Exception:",
                "                    value = lexeme",
                "            return Token(token_name, lexeme, start_line, start_col, value=value)",
                "        if kind == 'raise':",
                "            expr = action.get('argument') or repr('End of input')",
                "            try:",
                "                value = eval(expr, dict(globals()), {'lxm': lexeme})",
                "            except Exception:",
                "                value = expr",
                "            raise StopIteration(value)",
                "        result = self._run_raw_action(action.get('raw', ''), lexeme)",
                "        if result is None:",
                "            return None",
                "        if isinstance(result, Token):",
                "            return result",
                "        if isinstance(result, str):",
                "            return Token(result, lexeme, start_line, start_col)",
                "        return Token(type(result).__name__.upper(), lexeme, start_line, start_col, value=result)",
                "",
                "    def _handle_eof(self) -> Optional[Token]:",
                "        if self._eof_done:",
                "            return None",
                "        self._eof_done = True",
                "        action = EOF_ACTION",
                "        if not action:",
                "            return None",
                "        if action['kind'] == 'raise':",
                "            return None",
                "        if action['kind'] == 'return_name':",
                "            return Token(action['token_name'], '', self.line, self.column)",
                "        if action['kind'] == 'return_call':",
                "            return Token(action['token_name'], '', self.line, self.column, value='')",
                "        return None",
                "",
                "",
                "def lex_file(path: str, with_lexeme: bool = False) -> int:",
                "    text = Path(path).read_text(encoding='utf-8')",
                "    lexer = Lexer(text)",
                "    try:",
                "        for token in lexer.tokenize():",
                "            if with_lexeme:",
                "                print(f'{token.type}\t{token.lexeme!r}\t(line={token.line}, col={token.column})')",
                "            else:",
                "                print(token.type)",
                "        return 0",
                "    except StopIteration:",
                "        return 0",
                "    except LexicalError as exc:",
                "        print(str(exc))",
                "        return 1",
                "",
                "",
                "def main() -> int:",
                "    parser = argparse.ArgumentParser(description='Generated lexer from YALex spec')",
                "    parser.add_argument('input', help='Text file to lex')",
                "    parser.add_argument('--with-lexeme', action='store_true', help='Print lexemes and positions')",
                "    args = parser.parse_args()",
                "    return lex_file(args.input, with_lexeme=args.with_lexeme)",
                "",
                "",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
            ]
        )
        if trailer:
            sections.extend(["", trailer, ""])
        return '\n'.join(sections) + '\n'
