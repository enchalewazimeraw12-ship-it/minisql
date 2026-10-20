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
        self.errors, self.outputs = [], []


def compile_source(src, catalog):
    res = Result()
    res.tokens, lex_errors = tokenize(src)
    res.errors += lex_errors
    if lex_errors:
        return res
    stmts, parse_errors = parse(res.tokens)
    res.statements = stmts
    res.errors += parse_errors
    if parse_errors:
        return res
    for s in stmts:
        symtab, errs = analyze(s, catalog)
        res.symtabs.append(symtab)
        res.errors += errs
    if res.errors:
        return res
    res.plans = [generate(s) for s in stmts]
    return res


def run(src, catalog):
    res = compile_source(src, catalog)
    if not res.errors:
        res.outputs = [execute(p, catalog) for p in res.plans]
    return res
