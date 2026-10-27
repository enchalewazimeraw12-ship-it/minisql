"""Driver that runs all compiler phases."""
from .lexer import tokenize
from .parser import parse
from .semantic import analyze, Catalog
from .codegen import generate, format_plan
from .executor import execute, format_table
from .ast_nodes import dump_ast
import json


def load_catalog(path):
    with open(path, encoding="utf-8") as f:
        return Catalog(json.load(f))


class Result:
    def __init__(self):
        self.tokens, self.statements, self.symtabs, self.plans = [], [], [], []
        self.valid_statements, self.valid_symtabs = [], []
        self.errors, self.outputs = [], []


def compile_source(src, catalog):
    res = Result()
    res.tokens, lex_errors = tokenize(src)
    res.errors += lex_errors
    stmts, parse_errors = parse(res.tokens)
    res.statements = stmts
    res.errors += parse_errors

    line_offsets = [0]
    for line in src.splitlines(keepends=True):
        line_offsets.append(line_offsets[-1] + len(line))

    def offset(line, col):
        if line <= 0 or line > len(line_offsets):
            return len(src)
        return min(line_offsets[line - 1] + max(col - 1, 0), len(src))

    semicolons = [offset(t.line, t.col) for t in res.tokens if t.type == ";"]

    def statement_index(line, col):
        position = offset(line, col)
        return sum(semicolon < position for semicolon in semicolons)

    blocked_statements = {
        statement_index(error.line, error.col)
        for error in lex_errors + parse_errors
    }

    for s in stmts:
        index = statement_index(s.line, s.col)
        if index in blocked_statements:
            res.symtabs.append(None)
            continue
        symtab, errs = analyze(s, catalog)
        res.symtabs.append(symtab)
        res.errors += errs
        if not errs:
            res.valid_statements.append(s)
            res.valid_symtabs.append(symtab)
            res.plans.append(generate(s))
    return res


def run(src, catalog):
    res = compile_source(src, catalog)
    res.outputs = [execute(p, catalog) for p in res.plans]
    return res
