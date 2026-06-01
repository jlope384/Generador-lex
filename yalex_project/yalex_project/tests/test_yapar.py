"""Automated tests for the YAPar parser generator (SLR(1) and LALR(1)).

The canonical SLR grammar and its hand-worked automaton / table / parse trace
come from the course activity *"Construcción del Autómata LR(0)"*; these tests
assert the implementation reproduces that oracle exactly.  The pointer grammar
checks the SLR-vs-LALR difference.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from yapargen.codegen import generate_parser
from yapargen.grammar import END_MARKER
from yapargen.lalr_automaton import build_lalr_automaton
from yapargen.lalr_table import build_lalr_table
from yapargen.lr0_automaton import build_lr0_automaton
from yapargen.parse_runner import run_parse
from yapargen.pipeline import analyze
from yapargen.slr_table import build_slr_table
from yapargen.yapar_parser import YAParGrammarError, YAParParser

EXPR = ROOT / "examples" / "yapar" / "expr_slr.yalp"
PTR = ROOT / "examples" / "yapar" / "ptr_lalr.yalp"


def load_expr():
    return YAParParser().parse_file(EXPR)


class TestGrammarParsing(unittest.TestCase):
    def test_terminals_and_nonterminals(self):
        g = load_expr()
        self.assertEqual(g.terminals, {"AND", "OR", "LBRACKET", "RBRACKET", "SENTENCE"})
        self.assertEqual(g.non_terminals, {"s", "p", "q"})
        self.assertEqual(g.start, "s")
        self.assertEqual(len(g.productions), 6)

    def test_augmentation(self):
        g = load_expr()
        aug = g.augment()
        self.assertEqual(aug.start, "s'")
        self.assertEqual(aug.productions[0].head, "s'")
        self.assertEqual(aug.productions[0].body, ("s",))
        self.assertIn(END_MARKER, aug.terminals)
        self.assertEqual(len(aug.productions), 7)

    def test_grammatical_errors(self):
        bad = [
            "%token A\n%%\ns: A b ;\n",          # undefined non-terminal b
            "%token A\n%%\ns: A Z ;\n",          # undeclared terminal Z
            "%token A\n%%\nS: A ;\n",            # uppercase head
            "%token A\n%%\ns A ;\n",             # missing ':'
        ]
        for src in bad:
            with self.assertRaises(YAParGrammarError):
                YAParParser().parse_string(src)

    def test_epsilon_production(self):
        g = YAParParser().parse_string("%token A\n%%\ns: A t ;\nt: A | ;\n")
        self.assertTrue(any(p.is_epsilon() for p in g.productions))


class TestFirstFollow(unittest.TestCase):
    def setUp(self):
        self.an = analyze(load_expr())

    def test_first(self):
        for nt in ("s", "p", "q"):
            self.assertEqual(self.an.first[nt], {"LBRACKET", "SENTENCE"})

    def test_follow(self):
        self.assertEqual(self.an.follow["s"], {"$", "AND", "RBRACKET"})
        self.assertEqual(self.an.follow["p"], {"$", "AND", "OR", "RBRACKET"})
        self.assertEqual(self.an.follow["q"], {"$", "AND", "OR", "RBRACKET"})


class TestLR0Automaton(unittest.TestCase):
    def setUp(self):
        self.auto = build_lr0_automaton(load_expr())

    def test_state_count(self):
        self.assertEqual(len(self.auto.states), 12)  # I0..I11 (oracle)

    def test_key_transitions(self):
        t = self.auto.transitions
        self.assertEqual(t[(0, "s")], 1)
        self.assertEqual(t[(0, "p")], 2)
        self.assertEqual(t[(0, "q")], 3)
        self.assertEqual(t[(0, "LBRACKET")], 4)
        self.assertEqual(t[(0, "SENTENCE")], 5)
        self.assertEqual(t[(1, "AND")], 6)
        self.assertEqual(t[(8, "RBRACKET")], 11)
        self.assertEqual(t[(4, "LBRACKET")], 4)  # self loop


class TestSLRTable(unittest.TestCase):
    def setUp(self):
        g = load_expr()
        self.auto = build_lr0_automaton(g)
        self.table = build_slr_table(g, self.auto)

    def test_no_conflicts(self):
        self.assertEqual(self.table.conflicts, [])

    def test_oracle_cells(self):
        a = self.table.action
        self.assertEqual(a[(0, "SENTENCE")], ("shift", 5))
        self.assertEqual(a[(1, END_MARKER)], ("accept", None))
        self.assertEqual(a[(2, "OR")], ("shift", 7))
        self.assertEqual(a[(2, "AND")][0], "reduce")
        self.assertEqual(a[(8, "RBRACKET")], ("shift", 11))
        self.assertEqual(self.table.goto[(0, "s")], 1)
        self.assertEqual(self.table.goto[(4, "s")], 8)

    def test_reduce_targets(self):
        # state 5 reduces by q -> SENTENCE on every FOLLOW(q) terminal
        idx = self.table.grammar.production_index()
        for term in ("AND", "OR", "RBRACKET", END_MARKER):
            kind, prod = self.table.action[(5, term)]
            self.assertEqual(kind, "reduce")
            self.assertEqual(str(prod), "q -> SENTENCE")


class TestParsing(unittest.TestCase):
    def setUp(self):
        g = load_expr()
        self.table = build_slr_table(g, build_lr0_automaton(g))

    def test_accept_sentence_or_sentence(self):
        res = run_parse(self.table, ["SENTENCE", "OR", "SENTENCE"])
        self.assertTrue(res.accepted)
        # Oracle trace has exactly 9 steps ending in accept.
        self.assertEqual(len(res.steps), 9)
        self.assertEqual(res.steps[-1].action, "accept")
        actions = [s.action.split(":")[0].strip() for s in res.steps]
        self.assertEqual(actions, [
            "shift -> I5", "reduce r6", "reduce r4", "shift -> I7",
            "shift -> I5", "reduce r6", "reduce r3", "reduce r2", "accept",
        ])

    def test_accept_bracket(self):
        # [ sentence ] & sentence  ==  LBRACKET SENTENCE RBRACKET AND SENTENCE
        toks = ["LBRACKET", "SENTENCE", "RBRACKET", "AND", "SENTENCE"]
        self.assertTrue(run_parse(self.table, toks).accepted)

    def test_reject_two_sentences(self):
        res = run_parse(self.table, ["SENTENCE", "SENTENCE"])
        self.assertFalse(res.accepted)
        self.assertIn("SENTENCE", res.error)

    def test_reject_unbalanced(self):
        res = run_parse(self.table, ["LBRACKET", "SENTENCE"])
        self.assertFalse(res.accepted)

    def test_parse_tree(self):
        res = run_parse(self.table, ["SENTENCE", "OR", "SENTENCE"])
        self.assertIsNotNone(res.tree)
        self.assertEqual(res.tree.label, "s")


class TestLALR(unittest.TestCase):
    def test_state_count_matches_lr0(self):
        g = load_expr()
        lr0 = build_lr0_automaton(g)
        lalr = build_lalr_automaton(g)
        self.assertEqual(len(lalr.states), len(lr0.states))

    def test_slr_equals_lalr_for_slr_grammar(self):
        an = analyze(load_expr())
        self.assertEqual(an.slr_table.action, an.lalr_table.action)
        self.assertEqual(an.slr_table.goto, an.lalr_table.goto)
        self.assertEqual(an.lalr_table.conflicts, [])

    def test_lalr_accepts_same_strings(self):
        an = analyze(load_expr())
        toks = ["SENTENCE", "OR", "SENTENCE"]
        self.assertTrue(run_parse(an.lalr_table, toks).accepted)


class TestPointerGrammar(unittest.TestCase):
    """The classic grammar that is LALR(1) but not SLR(1)."""

    def setUp(self):
        self.an = analyze(YAParParser().parse_file(PTR))

    def test_slr_has_conflict(self):
        self.assertTrue(len(self.an.slr_table.conflicts) >= 1)
        self.assertIn("shift/reduce", self.an.slr_table.conflicts[0])

    def test_lalr_conflict_free(self):
        self.assertEqual(self.an.lalr_table.conflicts, [])

    def test_lalr_parses(self):
        for toks in (["ID", "ASSIGN", "ID"],
                     ["STAR", "ID", "ASSIGN", "ID"],
                     ["ID"]):
            self.assertTrue(run_parse(self.an.lalr_table, toks).accepted)
        self.assertFalse(run_parse(self.an.lalr_table, ["ID", "ID"]).accepted)


class TestCodegen(unittest.TestCase):
    def test_generated_parser_runs(self):
        import tempfile
        an = analyze(load_expr())
        with tempfile.TemporaryDirectory() as d:
            path = generate_parser(an.slr_table, Path(d) / "theparser.py")
            # Importable and pure-ASCII.
            data = path.read_bytes()
            self.assertEqual(sum(1 for b in data if b > 127), 0)
            spec = importlib.util.spec_from_file_location("theparser", path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["theparser"] = mod
            spec.loader.exec_module(mod)
            self.assertTrue(mod.parse(["SENTENCE", "OR", "SENTENCE"]).accepted)
            self.assertFalse(mod.parse(["SENTENCE", "SENTENCE"]).accepted)

    def test_generated_parser_cli(self):
        import tempfile
        an = analyze(load_expr())
        with tempfile.TemporaryDirectory() as d:
            path = generate_parser(an.slr_table, Path(d) / "theparser.py")
            ok = subprocess.run([sys.executable, str(path)],
                                input="SENTENCE OR SENTENCE",
                                capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            bad = subprocess.run([sys.executable, str(path)],
                                 input="SENTENCE SENTENCE",
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)


# ── casos límite añadidos tras el barrido exhaustivo ────────────────────────
EPS_GRAMMAR = (
    "%token PLUS TIMES LPAREN RPAREN ID\n%%\n"
    "e: t ep ;\nep: PLUS t ep | ;\nt: f tp ;\ntp: TIMES f tp | ;\n"
    "f: LPAREN e RPAREN | ID ;\n"
)


class TestEpsilonGrammar(unittest.TestCase):
    """Gramática de expresiones con producciones-epsilon (nullable)."""

    def setUp(self):
        self.an = analyze(YAParParser().parse_string(EPS_GRAMMAR))

    def test_nullable_in_first(self):
        self.assertIn("", self.an.first["ep"])
        self.assertIn("", self.an.first["tp"])
        self.assertEqual(self.an.first["e"], {"ID", "LPAREN"})

    def test_follow_matches_textbook(self):
        self.assertEqual(self.an.follow["e"], {"$", "RPAREN"})
        self.assertEqual(self.an.follow["t"], {"$", "PLUS", "RPAREN"})
        self.assertEqual(self.an.follow["f"], {"$", "PLUS", "RPAREN", "TIMES"})

    def test_no_conflicts(self):
        self.assertEqual(self.an.slr_table.conflicts, [])
        self.assertEqual(self.an.lalr_table.conflicts, [])

    def test_parse(self):
        for toks in ["ID", "ID PLUS ID", "ID PLUS ID TIMES ID",
                     "LPAREN ID PLUS ID RPAREN TIMES ID"]:
            self.assertTrue(run_parse(self.an.slr_table, toks.split()).accepted, toks)
        for toks in ["ID PLUS", "PLUS ID", ""]:
            self.assertFalse(run_parse(self.an.slr_table, toks.split()).accepted, toks)


class TestStartNullable(unittest.TestCase):
    """Gramática cuyo símbolo inicial es anulable (acepta la cadena vacía)."""

    def test_accepts_empty(self):
        an = analyze(YAParParser().parse_string("%token A\n%%\ns: A s | ;\n"))
        self.assertEqual(an.slr_table.conflicts, [])
        self.assertTrue(run_parse(an.slr_table, []).accepted)
        self.assertTrue(run_parse(an.slr_table, ["A", "A", "A"]).accepted)


class TestConflictDetection(unittest.TestCase):
    def test_reduce_reduce(self):
        an = analyze(YAParParser().parse_string(
            "%token A C\n%%\ns: a C | b C ;\na: A ;\nb: A ;\n"))
        self.assertTrue(any("reduce/reduce" in c for c in an.slr_table.conflicts))
        self.assertTrue(any("reduce/reduce" in c for c in an.lalr_table.conflicts))

    def test_shift_reduce_dangling_else(self):
        an = analyze(YAParParser().parse_string(
            "%token IF THEN ELSE OTHER\n%%\n"
            "s: IF s THEN s | IF s THEN s ELSE s | OTHER ;\n"))
        self.assertTrue(any("shift/reduce" in c for c in an.slr_table.conflicts))

    def test_lr1_but_not_lalr(self):
        # Dragon 4.49: LR(1) pero no LALR(1); la fusión de núcleos crea un
        # conflicto reduce/reduce que confirma el límite de LALR frente a LR(1).
        an = analyze(YAParParser().parse_file(
            ROOT / "examples" / "yapar" / "lr1_not_lalr.yalp"))
        self.assertTrue(any("reduce/reduce" in c for c in an.lalr_table.conflicts))


class TestEdgeCases(unittest.TestCase):
    def test_same_head_two_blocks(self):
        an = analyze(YAParParser().parse_string("%token A B\n%%\ns: A ;\ns: B ;\n"))
        self.assertTrue(run_parse(an.slr_table, ["A"]).accepted)
        self.assertTrue(run_parse(an.slr_table, ["B"]).accepted)
        self.assertFalse(run_parse(an.slr_table, ["A", "B"]).accepted)

    def test_empty_input_rejected_gracefully(self):
        res = run_parse(analyze(load_expr()).slr_table, [])
        self.assertFalse(res.accepted)
        self.assertIsNotNone(res.error)

    def test_unused_declared_token_does_not_break(self):
        an = analyze(YAParParser().parse_string("%token A B EXTRA\n%%\ns: A | B ;\n"))
        self.assertEqual(an.slr_table.conflicts, [])
        self.assertTrue(run_parse(an.slr_table, ["A"]).accepted)


class TestCLIRobustness(unittest.TestCase):
    """El front-end devuelve códigos de salida correctos ante errores."""

    def _run(self, *args, **kw):
        return subprocess.run(
            [sys.executable, str(ROOT / "run_yapar.py"), *args, "--no-graph"],
            capture_output=True, text=True, cwd=ROOT, **kw)

    def test_missing_grammar_file(self):
        self.assertEqual(self._run("no_existe.yalp").returncode, 1)

    def test_malformed_grammar(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.yalp"
            p.write_text("%token A\ns: A ;\n", encoding="utf-8")  # falta %%
            self.assertEqual(self._run(str(p)).returncode, 1)

    def test_full_pipeline_accept(self):
        r = self._run("examples/yapar/expr_slr.yalp",
                      "-l", "examples/yapar/expr.yal",
                      "-i", "examples/yapar/inputs/accept_or.txt", "--parser", "both")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CADENA ACEPTADA", r.stdout)

    def test_full_pipeline_reject(self):
        r = self._run("examples/yapar/expr_slr.yalp",
                      "-l", "examples/yapar/expr.yal",
                      "-i", "examples/yapar/inputs/reject_two.txt", "--parser", "slr")
        self.assertEqual(r.returncode, 1)
        self.assertIn("CADENA RECHAZADA", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
