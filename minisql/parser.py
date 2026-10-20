"""Part 2 - Recursive-descent parser producing an AST.

Grammar (EBNF):
  program     := { select_stmt [';'] }
  select_stmt := 'SELECT' ( '*' | item {',' item} ) 'FROM' table_ref { join }
                 [ 'WHERE' expr ] [ 'ORDER' 'BY' order {',' order} ] [ 'LIMIT' INT ]
  item        := expr [ 'AS' IDENT ]
  table_ref   := IDENT [ ['AS'] IDENT ]
  join        := [ 'INNER' | 'LEFT' ] 'JOIN' table_ref 'ON' expr
  order       := expr [ 'ASC' | 'DESC' ]
  expr        := and_expr { 'OR' and_expr }
  and_expr    := not_expr { 'AND' not_expr }
  not_expr    := 'NOT' not_expr | comparison
  comparison  := additive [ ('='|'<>'|'!='|'<'|'<='|'>'|'>=') additive ]
  additive    := term { ('+'|'-') term }
  term        := unary { ('*'|'/') unary }
  unary       := '-' unary | primary
  primary     := INT | FLOAT | STRING | column | '(' expr ')'
  column      := IDENT [ '.' IDENT ]
"""
from .ast_nodes import *
from .errors import ParseError

CMP_OPS = {"=", "<>", "!=", "<", "<=", ">", ">="}


class Parser:
    def __init__(self, tokens):
        self.toks, self.i = tokens, 0

    # ---- helpers ----
    @property
    def cur(self):
        return self.toks[self.i]

    def advance(self):
        t = self.cur
        if t.type != "EOF":
            self.i += 1
        return t

    def match(self, *types):
        if self.cur.type in types:
            return self.advance()
        return None

    def expect(self, ttype, what=None):
        if self.cur.type == ttype:
            return self.advance()
        raise ParseError(f"expected {what or ttype} but found {self.cur.value!r}", self.cur.line, self.cur.col)

    # ---- program ----
    def parse_program(self):
        stmts, errors = [], []
        while self.cur.type != "EOF":
            if self.match(";"):
                continue
            try:
                stmts.append(self.select_stmt())
                if self.cur.type not in (";", "EOF"):
                    raise ParseError(f"unexpected {self.cur.value!r} after end of statement", self.cur.line, self.cur.col)
            except ParseError as e:
                errors.append(e)
                while self.cur.type not in (";", "EOF"):   # panic-mode recovery
                    self.advance()
        return stmts, errors

    def select_stmt(self):
        t = self.expect("SELECT", "SELECT")
        node = Select(line=t.line, col=t.col)
        if self.match("*"):
            node.star = True
        else:
            node.items.append(self.item())
            while self.match(","):
                node.items.append(self.item())
        self.expect("FROM", "FROM")
        node.source = self.table_ref()
        while self.cur.type in ("JOIN", "INNER", "LEFT"):
            node.joins.append(self.join())
        if self.match("WHERE"):
            node.where = self.expr()
        if self.match("ORDER"):
            self.expect("BY", "BY after ORDER")
            node.order_by.append(self.order())
            while self.match(","):
                node.order_by.append(self.order())
        if self.match("LIMIT"):
            n = self.expect("INT", "integer after LIMIT")
            node.limit = n.value
        return node

    def item(self):
        e = self.expr()
        alias = None
        if self.match("AS"):
            alias = self.expect("IDENT", "alias name").value
        return SelectItem(line=e.line, col=e.col, expr=e, alias=alias)

    def table_ref(self):
        t = self.expect("IDENT", "table name")
        alias = t.value
        if self.match("AS"):
            alias = self.expect("IDENT", "alias name").value
        elif self.cur.type == "IDENT":
            alias = self.advance().value
        return TableRef(line=t.line, col=t.col, name=t.value, alias=alias)

    def join(self):
        kind = "INNER"
        start = self.cur
        if self.match("LEFT"):
            kind = "LEFT"
        else:
            self.match("INNER")
        self.expect("JOIN", "JOIN")
        tbl = self.table_ref()
        self.expect("ON", "ON (JOIN needs a condition)")
        return JoinClause(line=start.line, col=start.col, kind=kind, table=tbl, on=self.expr())

    def order(self):
        e = self.expr()
        asc = True
        if self.match("DESC"):
            asc = False
        else:
            self.match("ASC")
        return OrderItem(line=e.line, col=e.col, expr=e, ascending=asc)

    # ---- expressions ----
    def expr(self):
        left = self.and_expr()
        while (t := self.match("OR")):
            left = Binary(line=t.line, col=t.col, op="OR", left=left, right=self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while (t := self.match("AND")):
            left = Binary(line=t.line, col=t.col, op="AND", left=left, right=self.not_expr())
        return left

    def not_expr(self):
        if (t := self.match("NOT")):
            return Unary(line=t.line, col=t.col, op="NOT", operand=self.not_expr())
        return self.comparison()

    def comparison(self):
        left = self.additive()
        if self.cur.type in CMP_OPS:
            t = self.advance()
            op = {"=": "==", "<>": "!="}.get(t.type, t.type)
            return Binary(line=t.line, col=t.col, op=op, left=left, right=self.additive())
        return left

    def additive(self):
        left = self.term()
        while (t := self.match("+", "-")):
            left = Binary(line=t.line, col=t.col, op=t.type, left=left, right=self.term())
        return left

    def term(self):
        left = self.unary()
        while (t := self.match("*", "/")):
            left = Binary(line=t.line, col=t.col, op=t.type, left=left, right=self.unary())
        return left

    def unary(self):
        if (t := self.match("-")):
            return Unary(line=t.line, col=t.col, op="NEG", operand=self.unary())
        return self.primary()

    def primary(self):
        t = self.cur
        if t.type in ("INT", "FLOAT", "STRING"):
            self.advance()
            ty = {"INT": "INT", "FLOAT": "FLOAT", "STRING": "TEXT"}[t.type]
            return Literal(line=t.line, col=t.col, value=t.value, type=ty)
        if t.type == "IDENT":
            self.advance()
            if self.match("."):
                c = self.expect("IDENT", "column name after '.'")
                return Column(line=t.line, col=t.col, table=t.value, name=c.value)
            return Column(line=t.line, col=t.col, name=t.value)
        if self.match("("):
            e = self.expr()
            self.expect(")", "')'")
            return e
        raise ParseError(f"unexpected {t.value!r}, expected an expression", t.line, t.col)


def parse(tokens):
    return Parser(tokens).parse_program()
