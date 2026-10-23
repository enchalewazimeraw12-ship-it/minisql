"""Part 4 - Code generation: AST -> execution plan made of Three-Address Code.

Plan operators (relational):  SCAN, JOIN, FILTER, SORT, PROJECT, LIMIT, EMIT
Row expressions are compiled to TAC blocks:  dest = a op b   (evaluated once per row by the executor)
Operands are tuples: ('col','e.salary') | ('const',5000) | ('tmp','r1')
"""
from dataclasses import dataclass, field
from typing import List, Optional
from .ast_nodes import *


@dataclass
class TAC:
    dest: str
    op: str
    a: tuple
    b: Optional[tuple] = None

    def __str__(self):
        if self.b is None:
            return f"{self.dest} = {self.op} {fmt(self.a)}" if self.op != "MOVE" else f"{self.dest} = {fmt(self.a)}"
        return f"{self.dest} = {fmt(self.a)} {self.op} {fmt(self.b)}"


def fmt(o):
    return repr(o[1]) if o[0] == "const" else str(o[1])







@dataclass
class Block:
    label: str
    code: List[TAC]
    result: tuple
    ascending: bool = True


@dataclass
class PlanOp:
    dest: str
    op: str
    args: dict = field(default_factory=dict)
    blocks: List[Block] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)


class CodeGen:
    def __init__(self):
        self.ops = []
        self.t = 0

    def new_t(self):
        self.t += 1
        return f"t{self.t}"

    def gen_expr(self, e, code, counter):
        if isinstance(e, Literal):
            return ("const", e.value)
        if isinstance(e, Column):
            return ("col", f"{e.alias}.{e.name}")
        if isinstance(e, Unary):
            a = self.gen_expr(e.operand, code, counter)
            counter[0] += 1
            d = f"r{counter[0]}"
            code.append(TAC(d, e.op, a))
            return ("tmp", d)
        a = self.gen_expr(e.left, code, counter)
        b = self.gen_expr(e.right, code, counter)
        counter[0] += 1
        d = f"r{counter[0]}"
        code.append(TAC(d, e.op, a, b))
        return ("tmp", d)

    def block(self, label, e, asc=True):
        code, counter = [], [0]
        res = self.gen_expr(e, code, counter)
        return Block(label, code, res, asc)

    def emit(self, op, inputs=(), **args):
        dest = self.new_t()
        self.ops.append(PlanOp(dest, op, args, [], list(inputs)))
        return self.ops[-1]

    def generate(self, s):
        cur = self.emit("SCAN", table=s.source.name, alias=s.source.alias)
        for j in s.joins:
            right = self.emit("SCAN", table=j.table.name, alias=j.table.alias)
            cur = self.emit("JOIN", [cur.dest, right.dest], kind=j.kind, right_alias=j.table.alias)
            cur.blocks.append(self.block("ON", j.on))
        if s.where is not None:
            cur = self.emit("FILTER", [cur.dest])
            cur.blocks.append(self.block("WHERE", s.where))
        if s.order_by:
            cur = self.emit("SORT", [cur.dest])
            for o in s.order_by:
                cur.blocks.append(self.block(expr_to_str(o.expr), o.expr, o.ascending))
        cur = self.emit("PROJECT", [cur.dest])
        for it in s.items:
            cur.blocks.append(self.block(it.alias, it.expr))
        if s.limit is not None:
            cur = self.emit("LIMIT", [cur.dest], n=s.limit)
        self.emit("EMIT", [cur.dest])
        return self.ops


def generate(select):
    return CodeGen().generate(select)


def format_plan(ops):
    out = []
    for p in ops:
        ins = ", ".join(p.inputs)
        if p.op == "SCAN":
            out.append(f"{p.dest} = SCAN {p.args['table']} AS {p.args['alias']}")
        elif p.op == "JOIN":
            out.append(f"{p.dest} = {p.args['kind']} JOIN {ins}")
        elif p.op == "LIMIT":
            out.append(f"{p.dest} = LIMIT {ins}, {p.args['n']}")
        elif p.op == "EMIT":
            out.append(f"EMIT {ins}")
        else:
            out.append(f"{p.dest} = {p.op} {ins}")
        for b in p.blocks:
            tag = b.label + ("" if b.ascending else " DESC")
            out.append(f"      [{p.op}:{tag}]")
            for c in b.code:
                out.append(f"          {c}")
            out.append(f"          => {fmt(b.result)}")
    return "\n".join(out)
