import os, sys, unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from minisql.compiler import compile_source, run, load_catalog
from minisql.lexer import tokenize
from main import process

DB = load_catalog(os.path.join(os.path.dirname(__file__), "..", "data", "sample_db.json"))


def q(sql):
    r = run(sql, DB)
    assert not r.errors, [str(e) for e in r.errors]
    return r.outputs[0]


class TestScanner(unittest.TestCase):
    def test_tokens(self):
        toks, errs = tokenize("select a.b >= 10.5 and 'it''s' <> x;")
        self.assertEqual([t.type for t in toks],
                         ["SELECT", "IDENT", ".", "IDENT", ">=", "FLOAT", "AND", "STRING", "<>", "IDENT", ";", "EOF"])
        self.assertEqual(toks[7].value, "it's")
        self.assertFalse(errs)

    def test_illegal_char_and_unterminated(self):
        _, errs = tokenize("SELECT # FROM 'abc")
        self.assertEqual(len(errs), 2)

    def test_positions_and_comments(self):
        toks, _ = tokenize("-- hi\nSELECT\n  x")
        self.assertEqual((toks[0].line, toks[0].col), (2, 1))
        self.assertEqual((toks[1].line, toks[1].col), (3, 3))


class TestParser(unittest.TestCase):
    def errs(self, sql):
        return [str(e) for e in compile_source(sql, DB).errors]

    def test_missing_from(self):
        self.assertTrue(any("FROM" in e for e in self.errs("SELECT name employees;")))

    def test_join_needs_on(self):
        self.assertTrue(any("ON" in e for e in self.errs("SELECT * FROM employees e JOIN departments d;")))

    def test_missing_paren(self):
        self.assertTrue(any("')'" in e for e in self.errs("SELECT * FROM employees WHERE (age > 3;")))

    def test_recovery_reports_multiple(self):
        self.assertEqual(len(self.errs("SELECT FROM a; SELECT * employees;")), 2)

    def test_valid_statements_compile_after_errors(self):
        r = compile_source(
            "SELECT name FROM employee; SELECT id FROM departments ORDER BY id;", DB
        )
        self.assertEqual(len(r.errors), 1)
        self.assertEqual(len(r.valid_statements), 1)
        self.assertEqual(len(r.plans), 1)

    def test_precedence(self):
        r = compile_source("SELECT 1 + 2 * 3 AS v FROM departments;", DB)
        top = r.statements[0].items[0].expr
        self.assertEqual(top.op, "+")
        self.assertEqual(top.right.op, "*")


class TestSemantic(unittest.TestCase):
    def errs(self, sql):
        return [str(e) for e in compile_source(sql, DB).errors]

    def test_unknown_table(self):
        self.assertTrue(any("unknown table 'employee'" in e for e in self.errs("SELECT name FROM employee;")))

    def test_unknown_column(self):
        self.assertTrue(any("unknown column 'nam'" in e for e in self.errs("SELECT nam FROM employees;")))

    def test_ambiguous(self):
        self.assertTrue(any("ambiguous" in e for e in
                            self.errs("SELECT name FROM employees e JOIN departments d ON e.dept_id = d.id;")))

    def test_type_mismatch(self):
        self.assertTrue(any("cannot compare FLOAT with TEXT" in e for e in
                            self.errs("SELECT id FROM employees WHERE salary > 'abc';")))

    def test_where_not_boolean(self):
        self.assertTrue(any("WHERE condition must be boolean" in e.replace("a boolean expression", "boolean")
                            for e in self.errs("SELECT id FROM employees WHERE age + 1;")))

    def test_bad_alias(self):
        self.assertTrue(any("unknown table or alias 'x'" in e for e in self.errs("SELECT x.name FROM employees e;")))

    def test_duplicate_alias(self):
        self.assertTrue(any("duplicate" in e for e in self.errs("SELECT * FROM employees e JOIN departments e ON 1 = 1;")))


class TestExecution(unittest.TestCase):
    def test_where_order(self):
        h, rows = q("SELECT name FROM employees WHERE salary > 10000 ORDER BY salary DESC;")
        self.assertEqual([r[0] for r in rows], ["Tigist", "fasika", "enchalew", "Selam"])

    def test_join(self):
        h, rows = q("SELECT e.name, d.name AS dept FROM employees e JOIN departments d ON e.dept_id = d.id ORDER BY e.id;")
        self.assertEqual(h, ["name", "dept"])
        self.assertEqual(rows[0], ("enchalew", "Engineering"))
        self.assertEqual(len(rows), 5)          # Selam has no department

    def test_left_join(self):
        h, rows = q("SELECT e.name, d.name FROM employees e LEFT JOIN departments d ON e.dept_id = d.id ORDER BY e.id;")
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[-1], ("Selam", None))

    def test_arithmetic_limit(self):
        h, rows = q("SELECT name, salary * 2 AS dbl FROM employees ORDER BY salary DESC LIMIT 2;")
        self.assertEqual(rows, [("Tigist", 36000.0), ("fasika", 31001.0)])

    def test_logic(self):
        h, rows = q("SELECT id FROM departments WHERE NOT (city = 'Addis Ababa') OR id = 10 ORDER BY id;")
        self.assertEqual([r[0] for r in rows], [10, 20, 40])

    def test_star(self):
        h, rows = q("SELECT * FROM departments;")
        self.assertEqual(h, ["id", "name", "city"])
        self.assertEqual(len(rows), 4)

    def test_multi_sort(self):
        h, rows = q("SELECT d.city, e.name FROM employees e JOIN departments d ON e.dept_id = d.id ORDER BY d.city ASC, e.salary DESC;")
        self.assertEqual(rows[0], ("Addis Ababa", "Tigist"))

    def test_order_by_alias(self):
        h, rows = q("SELECT name, salary * 12 AS yearly FROM employees ORDER BY yearly DESC LIMIT 1;")
        self.assertEqual(rows[0][0], "Tigist")

    def test_no_cascade_errors(self):
        r = compile_source("SELECT name FROM employee;", DB)
        self.assertEqual(len(r.errors), 1)

    def test_valid_statements_run_after_errors(self):
        r = run(
            "SELECT name FROM employee; SELECT id FROM departments ORDER BY id;", DB
        )
        self.assertEqual(len(r.errors), 1)
        self.assertEqual(r.outputs, [(["id"], [(10,), (20,), (30,), (40,)])])

    def test_syntax_and_lexer_errors_skip_only_their_statements(self):
        source = (
            "SELECT #id FROM departments; "
            "SELECT FROM departments; "
            "SELECT id FROM departments ORDER BY id;"
        )
        r = run(source, DB)
        self.assertEqual(len(r.errors), 2)
        self.assertEqual(len(r.valid_statements), 1)
        self.assertEqual(r.outputs, [(["id"], [(10,), (20,), (30,), (40,)])])

    def test_div_zero(self):
        from minisql.errors import ExecError
        with self.assertRaises(ExecError):
            q("SELECT salary / 0 FROM employees;")


class TestCLI(unittest.TestCase):
    def test_valid_statements_run_after_errors(self):
        output = StringIO()
        args = Namespace(tokens=False, ast=False, symtab=False, plan=False, no_run=False)
        with redirect_stdout(output):
            status = process(
                "SELECT name FROM employee; SELECT id FROM departments ORDER BY id;",
                DB,
                args,
            )
        self.assertEqual(status, 1)
        self.assertIn("unknown table 'employee'", output.getvalue())
        self.assertIn("######## Statement 1 ########", output.getvalue())
        self.assertIn("(4 rows)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
