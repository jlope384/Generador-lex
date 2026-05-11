from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .regex_ast import Charset, Concat, EOF_NODE, EPSILON, Epsilon, Literal, OptionalNode, Plus, RegexNode, Star, UnionNode

ASCII_UNIVERSE = frozenset(chr(i) for i in range(256))
SPECIAL_CHARS = frozenset('()|*+?#')


class RegexParseError(Exception):
    pass


@dataclass
class Token:
    kind: str
    value: Optional[str] = None
    pos: int = 0


class RegexTokenizer:
    def __init__(self, text: str):
        self.text = text
        self.i = 0
        self.n = len(text)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while self.i < self.n:
            c = self.text[self.i]
            if c.isspace():
                self.i += 1
                continue
            if c in SPECIAL_CHARS:
                tokens.append(Token(c, c, self.i))
                self.i += 1
                continue
            if c == '_':
                tokens.append(Token('ANY', '_', self.i))
                self.i += 1
                continue
            if c == "'":
                tokens.append(Token('CHAR', self._read_char_literal(), self.i))
                continue
            if c == '"':
                tokens.append(Token('STRING', self._read_string_literal(), self.i))
                continue
            if c == '[':
                tokens.append(Token('CHARSET', self._read_charset_literal(), self.i))
                continue
            if c.isalpha() or c == '_':
                ident = self._read_ident()
                kind = 'EOF' if ident == 'eof' else 'IDENT'
                tokens.append(Token(kind, ident, self.i))
                continue
            raise RegexParseError(f"Unexpected character in regex at {self.i}: {c!r}")
        return tokens

    def _read_ident(self) -> str:
        start = self.i
        while self.i < self.n and (self.text[self.i].isalnum() or self.text[self.i] == '_'):
            self.i += 1
        return self.text[start:self.i]

    def _read_quoted_body(self, quote: str) -> str:
        assert self.text[self.i] == quote
        self.i += 1
        buf = []
        while self.i < self.n:
            c = self.text[self.i]
            if c == '\\':
                self.i += 1
                if self.i >= self.n:
                    raise RegexParseError('Incomplete escape sequence')
                buf.append(_decode_escape(self.text[self.i]))
                self.i += 1
                continue
            if c == quote:
                self.i += 1
                return ''.join(buf)
            buf.append(c)
            self.i += 1
        raise RegexParseError(f'Unterminated {quote} literal')

    def _read_char_literal(self) -> str:
        body = self._read_quoted_body("'")
        if len(body) != 1:
            raise RegexParseError(f'Character literal must contain exactly one character, got {body!r}')
        return body

    def _read_string_literal(self) -> str:
        return self._read_quoted_body('"')

    def _read_charset_literal(self) -> Tuple[bool, List[Tuple[str, object]]]:
        assert self.text[self.i] == '['
        self.i += 1
        negated = False
        if self.i < self.n and self.text[self.i] == '^':
            negated = True
            self.i += 1
        items: List[Tuple[str, object]] = []
        while self.i < self.n:
            while self.i < self.n and self.text[self.i].isspace():
                self.i += 1
            if self.i >= self.n:
                break
            if self.text[self.i] == ']':
                self.i += 1
                return (negated, items)
            if self.text[self.i] == "'":
                first = self._read_char_literal()
                save = self.i
                while self.i < self.n and self.text[self.i].isspace():
                    self.i += 1
                if self.i < self.n and self.text[self.i] == '-':
                    self.i += 1
                    while self.i < self.n and self.text[self.i].isspace():
                        self.i += 1
                    if self.i < self.n and self.text[self.i] == "'":
                        second = self._read_char_literal()
                        items.append(('RANGE', (first, second)))
                    else:
                        items.append(('CHAR', first))
                        items.append(('CHAR', '-'))
                else:
                    self.i = save
                    items.append(('CHAR', first))
                continue
            if self.text[self.i] == '"':
                s = self._read_string_literal()
                items.append(('STRINGSET', s))
                continue
            raise RegexParseError(f'Invalid character-set item near position {self.i}')
        raise RegexParseError('Unterminated character set')


class RegexParser:
    def __init__(self, definitions: Dict[str, str], universe: frozenset[str] = ASCII_UNIVERSE):
        self.definitions = definitions
        self.universe = universe
        self._ast_cache: Dict[str, RegexNode] = {}
        self._stack: List[str] = []

    def parse(self, text: str) -> RegexNode:
        tokens = RegexTokenizer(text).tokenize()
        prev_tokens = getattr(self, "tokens", None)
        prev_pos = getattr(self, "pos", None)
        self.tokens = tokens
        self.pos = 0
        try:
            node = self._parse_union()
            if self.pos != len(self.tokens):
                tok = self.tokens[self.pos]
                raise RegexParseError(f'Unexpected token {tok.kind} at end of regex')
            return node
        finally:
            if prev_tokens is None:
                if hasattr(self, "tokens"):
                    del self.tokens
                if hasattr(self, "pos"):
                    del self.pos
            else:
                self.tokens = prev_tokens
                self.pos = prev_pos

    def expand_definition(self, name: str) -> RegexNode:
        if name in self._ast_cache:
            return self._ast_cache[name]
        if name in self._stack:
            cycle = ' -> '.join(self._stack + [name])
            raise RegexParseError(f'Cyclic let definition: {cycle}')
        if name not in self.definitions:
            raise RegexParseError(f'Undefined regex identifier: {name}')
        self._stack.append(name)
        ast = self.parse(self.definitions[name])
        self._stack.pop()
        self._ast_cache[name] = ast
        return ast

    def _peek(self) -> Optional[Token]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _eat(self, kind: Optional[str] = None) -> Token:
        tok = self._peek()
        if tok is None:
            raise RegexParseError('Unexpected end of regex')
        if kind is not None and tok.kind != kind:
            raise RegexParseError(f'Expected {kind}, got {tok.kind}')
        self.pos += 1
        return tok

    def _starts_atom(self, tok: Optional[Token]) -> bool:
        return tok is not None and tok.kind in {'CHAR', 'STRING', 'CHARSET', 'ANY', 'IDENT', 'EOF', '('}

    def _parse_union(self) -> RegexNode:
        node = self._parse_concat()
        while self._peek() is not None and self._peek().kind == '|':
            self._eat('|')
            node = UnionNode(node, self._parse_concat())
        return node

    def _parse_concat(self) -> RegexNode:
        parts: List[RegexNode] = []
        while self._starts_atom(self._peek()):
            parts.append(self._parse_postfix())
        if not parts:
            return EPSILON
        node = parts[0]
        for part in parts[1:]:
            node = Concat(node, part)
        return node

    def _parse_postfix(self) -> RegexNode:
        node = self._parse_difference()
        while self._peek() is not None and self._peek().kind in {'*', '+', '?'}:
            op = self._eat().kind
            if op == '*':
                node = Star(node)
            elif op == '+':
                node = Plus(node)
            else:
                node = OptionalNode(node)
        return node

    def _parse_difference(self) -> RegexNode:
        node = self._parse_atom()
        while self._peek() is not None and self._peek().kind == '#':
            self._eat('#')
            other = self._parse_atom()
            left = self._as_charset(node)
            right = self._as_charset(other)
            node = Charset(frozenset(left.chars.difference(right.chars)), label=None)
        return node

    def _parse_atom(self) -> RegexNode:
        tok = self._peek()
        if tok is None:
            raise RegexParseError('Unexpected end of regex while parsing atom')
        if tok.kind == 'CHAR':
            self._eat('CHAR')
            return Literal(tok.value or '')
        if tok.kind == 'STRING':
            self._eat('STRING')
            return self._string_to_concat(tok.value or '')
        if tok.kind == 'CHARSET':
            self._eat('CHARSET')
            negated, items = tok.value  # type: ignore[misc]
            chars = set()
            for kind, val in items:
                if kind == 'CHAR':
                    chars.add(val)
                elif kind == 'RANGE':
                    a, b = val
                    lo, hi = ord(a), ord(b)
                    if lo > hi:
                        lo, hi = hi, lo
                    for code in range(lo, hi + 1):
                        chars.add(chr(code))
                elif kind == 'STRINGSET':
                    chars.update(val)
                else:
                    raise RegexParseError(f'Unknown charset item {kind}')
            if negated:
                chars = set(self.universe.difference(chars))
            return Charset(frozenset(chars), label=self._format_charset_label(negated, items))
        if tok.kind == 'ANY':
            self._eat('ANY')
            return Charset(self.universe, label='_')
        if tok.kind == 'IDENT':
            self._eat('IDENT')
            return self.expand_definition(tok.value or '')
        if tok.kind == 'EOF':
            self._eat('EOF')
            return EOF_NODE
        if tok.kind == '(':
            self._eat('(')
            node = self._parse_union()
            self._eat(')')
            return node
        raise RegexParseError(f'Unexpected token in atom: {tok.kind}')

    def _as_charset(self, node: RegexNode) -> Charset:
        if isinstance(node, Charset):
            return node
        if isinstance(node, Literal):
            return Charset(frozenset({node.char}), label=repr(node.char))
        raise RegexParseError('Operator # only supports character sets or char literals')

    def _string_to_concat(self, s: str) -> RegexNode:
        if s == '':
            return EPSILON
        node: RegexNode = Literal(s[0])
        for ch in s[1:]:
            node = Concat(node, Literal(ch))
        return node

    def _format_charset_label(self, negated: bool, items: Sequence[Tuple[str, object]]) -> str:
        parts = []
        for kind, value in items:
            if kind == 'CHAR':
                parts.append(repr(value))
            elif kind == 'RANGE':
                a, b = value
                parts.append(f"{a}-{b}")
            elif kind == 'STRINGSET':
                parts.append(f'"{value}"')
        inner = ' '.join(parts)
        return f"[{'^' if negated else ''}{inner}]"


def _decode_escape(ch: str) -> str:
    mapping = {
        'n': '\n',
        't': '\t',
        'r': '\r',
        '\\': '\\',
        '"': '"',
        "'": "'",
        '0': '\0',
        'b': '\b',
        'f': '\f',
        'v': '\v',
    }
    return mapping.get(ch, ch)
