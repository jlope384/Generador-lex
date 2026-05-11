from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from yalexgen.automata import DFA, minimize_dfa
from yalexgen.generator import YALexGenerator

ROOT = Path(__file__).resolve().parents[1]

PICO_SUCCESS_CASES = {
    "hello.pico": [
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "STRING_LIT",
        "SEMICOLON",
        "KW_EMIT",
        "STRING_LIT",
        "SEMICOLON",
        "KW_EMIT",
        "IDENT",
        "SEMICOLON",
    ],
    "arithmetic.pico": [
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "INT_LIT",
        "SEMICOLON",
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "INT_LIT",
        "SEMICOLON",
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "LPAREN",
        "IDENT",
        "PLUS",
        "IDENT",
        "RPAREN",
        "TIMES",
        "INT_LIT",
        "SEMICOLON",
        "KW_EMIT",
        "IDENT",
        "SEMICOLON",
    ],
    "conditional.pico": [
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "INT_LIT",
        "SEMICOLON",
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "IDENT",
        "GEQ",
        "INT_LIT",
        "SEMICOLON",
        "KW_WHEN",
        "LPAREN",
        "IDENT",
        "RPAREN",
        "LBRACE",
        "KW_EMIT",
        "STRING_LIT",
        "SEMICOLON",
        "RBRACE",
        "KW_OTHERWISE",
        "LBRACE",
        "KW_EMIT",
        "STRING_LIT",
        "SEMICOLON",
        "RBRACE",
    ],
    "loop.pico": [
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "INT_LIT",
        "SEMICOLON",
        "KW_REPEAT",
        "LBRACE",
        "KW_EMIT",
        "IDENT",
        "SEMICOLON",
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "IDENT",
        "MINUS",
        "INT_LIT",
        "SEMICOLON",
        "RBRACE",
        "KW_UNTIL",
        "LPAREN",
        "IDENT",
        "EQ",
        "INT_LIT",
        "RPAREN",
        "SEMICOLON",
    ],
    "macro.pico": [
        "KW_MACRO",
        "IDENT",
        "LPAREN",
        "IDENT",
        "RPAREN",
        "LBRACE",
        "IDENT",
        "TIMES",
        "INT_LIT",
        "RBRACE",
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "INT_LIT",
        "SEMICOLON",
        "KW_EMIT",
        "IDENT",
        "LPAREN",
        "IDENT",
        "RPAREN",
        "SEMICOLON",
    ],
    "floats_and_logic.pico": [
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "FLOAT_LIT",
        "SEMICOLON",
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "FLOAT_LIT",
        "SEMICOLON",
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "IDENT",
        "TIMES",
        "IDENT",
        "TIMES",
        "IDENT",
        "SEMICOLON",
        "KW_LET",
        "IDENT",
        "ASSIGN",
        "IDENT",
        "GT",
        "FLOAT_LIT",
        "AND",
        "IDENT",
        "NEQ",
        "FLOAT_LIT",
        "SEMICOLON",
        "KW_EMIT",
        "IDENT",
        "SEMICOLON",
    ],
    "comments_only.pico": [],
}

PICO_ERROR_CASES = {
    "bad_string.pico": ["line 2, column 12", "Unterminated string literal"],
    "invalid_char.pico": ["line 3, column 12", "@"],
    "bad_number.pico": ["line 2, column 12", "3.", "float requires digits after the decimal point"],
    "hash_comment.pico": ["line 1, column 1", "#"],
    "bad_assign.pico": ["line 2, column 7", "="],
    "unclosed_block.pico": ["line 5, column 17", "$"],
}

ARNOLDC_SUCCESS_CASES = {
    "hello.arnoldc": [
        "KW_MAIN_START",
        "KW_PRINT",
        "STRING_LIT",
        "KW_MAIN_END",
    ],
    "variables.arnoldc": [
        "KW_MAIN_START",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_PRINT",
        "IDENT",
        "KW_PRINT",
        "IDENT",
        "KW_MAIN_END",
    ],
    "arithmetic.arnoldc": [
        "KW_MAIN_START",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_ASSIGN_START",
        "IDENT",
        "KW_ASSIGN_INIT",
        "INT_LIT",
        "KW_PLUS",
        "IDENT",
        "KW_TIMES",
        "INT_LIT",
        "KW_ASSIGN_END",
        "KW_PRINT",
        "IDENT",
        "KW_MAIN_END",
    ],
    "conditional.arnoldc": [
        "KW_MAIN_START",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_IF",
        "IDENT",
        "KW_PRINT",
        "STRING_LIT",
        "KW_ELSE",
        "KW_PRINT",
        "STRING_LIT",
        "KW_ENDIF",
        "KW_MAIN_END",
    ],
    "while_loop.arnoldc": [
        "KW_MAIN_START",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "KW_TRUE",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_WHILE",
        "IDENT",
        "KW_ASSIGN_START",
        "IDENT",
        "KW_ASSIGN_INIT",
        "IDENT",
        "KW_PLUS",
        "INT_LIT",
        "KW_ASSIGN_END",
        "KW_PRINT",
        "IDENT",
        "KW_ASSIGN_START",
        "IDENT",
        "KW_ASSIGN_INIT",
        "INT_LIT",
        "KW_GT",
        "IDENT",
        "KW_ASSIGN_END",
        "KW_ENDWHILE",
        "KW_MAIN_END",
    ],
    "method.arnoldc": [
        "KW_MAIN_START",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_CALL_ASSIGN",
        "IDENT",
        "KW_CALL_VOID",
        "IDENT",
        "INT_LIT",
        "KW_PRINT",
        "IDENT",
        "KW_MAIN_END",
        "KW_METHOD_DEF",
        "IDENT",
        "KW_METHOD_ARG",
        "IDENT",
        "KW_METHOD_NONVOID",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_ASSIGN_START",
        "IDENT",
        "KW_ASSIGN_INIT",
        "IDENT",
        "KW_TIMES",
        "INT_LIT",
        "KW_ASSIGN_END",
        "KW_RETURN",
        "IDENT",
        "KW_METHOD_END",
    ],
    "logic.arnoldc": [
        "KW_MAIN_START",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "KW_TRUE",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "KW_FALSE",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_ASSIGN_START",
        "IDENT",
        "KW_ASSIGN_INIT",
        "IDENT",
        "KW_OR",
        "IDENT",
        "KW_AND",
        "IDENT",
        "KW_ASSIGN_END",
        "KW_PRINT",
        "IDENT",
        "KW_MAIN_END",
    ],
    "negative_int.arnoldc": [
        "KW_MAIN_START",
        "KW_DECLARE",
        "IDENT",
        "KW_INIT",
        "INT_LIT",
        "KW_PRINT",
        "IDENT",
        "KW_MAIN_END",
    ],
}

ARNOLDC_ERROR_CASES = {
    "lowercase_keyword.arnoldc": ["line 1, column 3", "Unrecognized character"],
    "bad_string.arnoldc": ["line 2, column 18", "Unterminated string literal"],
    "wrong_macro.arnoldc": ["line 3, column 15", "@"],
    "mixed_case_keyword.arnoldc": ["line 2, column 1", "T"],
    "missing_comma.arnoldc": ["line 3, column 1", "H"],
    "symbol_in_ident.arnoldc": ["line 2, column 22", "-"],
    "hash_comment.arnoldc": ["line 2, column 1", "#"],
}


class YALexGeneratorIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.tempdir.name)
        self.generator = YALexGenerator()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _generate(self, *, spec_text: str | None = None, spec_path: Path | None = None, stem: str = "lexer", method: str = "direct"):
        if spec_text is None and spec_path is None:
            raise ValueError("spec_text or spec_path is required")
        if spec_text is not None:
            source = self.temp_path / f"{stem}.yal"
            source.write_text(textwrap.dedent(spec_text).lstrip(), encoding="utf-8")
        else:
            assert spec_path is not None
            source = spec_path
        output = self.temp_path / f"{stem}.py"
        graph = self.temp_path / f"{stem}.png"
        artifacts = self.generator.generate(source, output, graph, method=method)
        self.assertTrue(output.exists(), output)
        self.assertTrue(graph.exists(), graph)
        self.assertGreater(graph.stat().st_size, 0)
        self.assertGreater(artifacts.dfa_state_count, 0)
        self.assertEqual(artifacts.method, method)
        self.assertLessEqual(artifacts.dfa_state_count, artifacts.dfa_state_count_before_minimization)
        return output

    def _run_lexer(self, lexer_path: Path, *, input_text: str | None = None, input_path: Path | None = None, with_lexeme: bool = False):
        if input_text is None and input_path is None:
            raise ValueError("input_text or input_path is required")
        if input_text is not None:
            source = self.temp_path / "input.txt"
            source.write_text(input_text, encoding="utf-8")
        else:
            assert input_path is not None
            source = input_path
        cmd = [sys.executable, str(lexer_path), str(source)]
        if with_lexeme:
            cmd.append("--with-lexeme")
        return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)

    def _assert_success_case(self, lexer_path: Path, input_path: Path, expected_tokens: list[str]) -> None:
        result = self._run_lexer(lexer_path, input_path=input_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), expected_tokens)

    def _assert_error_case(self, lexer_path: Path, input_path: Path, expected_fragments: list[str]) -> None:
        result = self._run_lexer(lexer_path, input_path=input_path)
        self.assertEqual(result.returncode, 1, result.stderr)
        for fragment in expected_fragments:
            self.assertIn(fragment, result.stdout)

    def test_pico_success_examples_from_spec(self) -> None:
        for method in ("direct", "thompson"):
            lexer_path = self._generate(spec_path=ROOT / "examples" / "pico" / "pico.yal", stem=f"pico_{method}", method=method)
            for filename, expected in PICO_SUCCESS_CASES.items():
                with self.subTest(method=method, filename=filename):
                    self._assert_success_case(lexer_path, ROOT / "examples" / "pico" / filename, expected)

    def test_pico_error_examples_from_spec(self) -> None:
        for method in ("direct", "thompson"):
            lexer_path = self._generate(spec_path=ROOT / "examples" / "pico" / "pico.yal", stem=f"pico_errors_{method}", method=method)
            for filename, fragments in PICO_ERROR_CASES.items():
                with self.subTest(method=method, filename=filename):
                    self._assert_error_case(lexer_path, ROOT / "examples" / "pico" / filename, fragments)

    def test_arnoldc_success_examples_from_spec(self) -> None:
        for method in ("direct", "thompson"):
            lexer_path = self._generate(spec_path=ROOT / "examples" / "arnoldc" / "arnoldc.yal", stem=f"arnoldc_{method}", method=method)
            for filename, expected in ARNOLDC_SUCCESS_CASES.items():
                with self.subTest(method=method, filename=filename):
                    self._assert_success_case(lexer_path, ROOT / "examples" / "arnoldc" / filename, expected)

    def test_arnoldc_error_examples_from_spec(self) -> None:
        for method in ("direct", "thompson"):
            lexer_path = self._generate(spec_path=ROOT / "examples" / "arnoldc" / "arnoldc.yal", stem=f"arnoldc_errors_{method}", method=method)
            for filename, fragments in ARNOLDC_ERROR_CASES.items():
                with self.subTest(method=method, filename=filename):
                    self._assert_error_case(lexer_path, ROOT / "examples" / "arnoldc" / filename, fragments)

    def test_respects_longest_match_and_rule_priority(self) -> None:
        for method in ("direct", "thompson"):
            lexer_path = self._generate(
                stem=f"priority_{method}",
                method=method,
                spec_text=r"""
                rule gettoken =
                    [' ' '\t' '\n'] { return lexbuf }
                  | "if"            { return IF }
                  | ['a'-'z']+      { return IDENT(lxm) }
                  | "=="            { return EQEQ }
                  | "="             { return EQ }
                  | eof             { raise('End of input') }
                """,
            )

            result = self._run_lexer(lexer_path, input_text="if iff == =")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["IF", "IDENT", "EQEQ", "EQ"])

    def test_supports_regex_operators_and_eof_inside_regex(self) -> None:
        for method in ("direct", "thompson"):
            lexer_path = self._generate(
                stem=f"operators_{method}",
                method=method,
                spec_text=r"""
                let lower    = ['a'-'z']
                let vowel    = ["aeiou"]
                let cons     = lower # vowel
                let ident    = cons+ '!'?
                let str_char = [^ '"' '\n']
                let str_lit  = '"' str_char+ '"'
                let escaped  = '\\' _
                let line_cmt = '/' '/' [^ '\n']* ('\n' | eof)

                rule gettoken =
                    [' ' '\t' '\n']  { return lexbuf }
                  | line_cmt         { return lexbuf }
                  | "if"             { return IF }
                  | ident            { return IDENT(lxm) }
                  | str_lit          { return STRING(lxm) }
                  | escaped          { return ESC(lxm) }
                  | eof              { raise('End of input') }
                """,
            )

            result = self._run_lexer(lexer_path, input_text='if bcd! "xyz" \\? // trailing comment')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["IF", "IDENT", "STRING", "ESC"])

    def test_rejects_nullable_rules(self) -> None:
        spec = """
        rule gettoken =
            'a'? { return A }
          | eof { raise('End of input') }
        """

        with self.assertRaisesRegex(ValueError, "empty string"):
            self._generate(spec_text=spec, stem="nullable")

    def test_generator_defaults_to_direct_method(self) -> None:
        source = self.temp_path / "default_method.yal"
        source.write_text(
            textwrap.dedent(
                r"""
                rule gettoken =
                    'a' { return A }
                  | eof { raise('End of input') }
                """
            ).lstrip(),
            encoding="utf-8",
        )
        artifacts = self.generator.generate(source, self.temp_path / "default_method.py", self.temp_path / "default_method.png")
        self.assertEqual(artifacts.method, "direct")

    def test_minimization_merges_equivalent_same_rule_acceptors(self) -> None:
        dfa = DFA(
            start=0,
            transitions={
                0: {"a": 1, "b": 2},
                1: {"a": 1},
                2: {"a": 1},
            },
            accepts={1: 0, 2: 0},
        )

        minimized = minimize_dfa(dfa, ["a", "b"])

        self.assertEqual(minimized.transitions[0]["a"], minimized.transitions[0]["b"])
        self.assertEqual(len(minimized.transitions), 2)

    def test_minimization_keeps_different_accept_rules_separate(self) -> None:
        dfa = DFA(
            start=0,
            transitions={
                0: {"a": 1, "b": 2},
                1: {},
                2: {},
            },
            accepts={1: 0, 2: 1},
        )

        minimized = minimize_dfa(dfa, ["a", "b"])

        self.assertNotEqual(minimized.transitions[0]["a"], minimized.transitions[0]["b"])
        self.assertEqual(set(minimized.accepts.values()), {0, 1})

    def test_minimization_keeps_missing_transitions_as_implicit_rejects(self) -> None:
        dfa = DFA(
            start=0,
            transitions={
                0: {"a": 1},
                1: {},
            },
            accepts={1: 0},
        )

        minimized = minimize_dfa(dfa, ["a", "b"])

        self.assertNotIn("b", minimized.transitions[0])
        self.assertNotIn("a", minimized.transitions[minimized.transitions[0]["a"]])

    def test_direct_and_thompson_methods_are_equivalent(self) -> None:
        spec = r"""
        let lower    = ['a'-'z']
        let vowel    = ["aeiou"]
        let cons     = lower # vowel
        let ident    = cons+ '!'?
        let str_char = [^ '"' '\n']
        let str_lit  = '"' str_char+ '"'
        let escaped  = '\\' _
        let line_cmt = '/' '/' [^ '\n']* ('\n' | eof)

        rule gettoken =
            [' ' '\t' '\n']  { return lexbuf }
          | line_cmt         { return lexbuf }
          | "if"             { return IF }
          | ident            { return IDENT(lxm) }
          | str_lit          { return STRING(lxm) }
          | escaped          { return ESC(lxm) }
          | eof              { raise('End of input') }
        """
        direct = self._generate(stem="equiv_direct", method="direct", spec_text=spec)
        thompson = self._generate(stem="equiv_thompson", method="thompson", spec_text=spec)

        for input_text in ['if bcd! "xyz" \\? // trailing comment', "if iff", "@"]:
            with self.subTest(input_text=input_text):
                direct_result = self._run_lexer(direct, input_text=input_text)
                thompson_result = self._run_lexer(thompson, input_text=input_text)
                self.assertEqual(direct_result.returncode, thompson_result.returncode)
                self.assertEqual(direct_result.stdout, thompson_result.stdout)


if __name__ == "__main__":
    unittest.main()
