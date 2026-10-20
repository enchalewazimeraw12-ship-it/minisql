"""Part 1 - Scanner (lexical analysis). Regex based; identifiers/keywords are case-insensitive."""
import re
from dataclasses import dataclass
from .errors import LexError

KEYWORDS = {"SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "ON", "AS", "AND", "OR",
            "NOT", "ORDER", "BY", "ASC", "DESC", "LIMIT"}

TOKEN_SPEC = [
    ("NL", r"\n"),
    ("WS", r"[ \t\r]+"),
    ("COMMENT", r"--[^\n]*"),
    ("FLOAT", r"\d+\.\d+"),
    ("INT", r"\d+"),
    ("STRING", r"'(?:[^'\n]|'')*'"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("OP", r"<>|!=|<=|>=|=|<|>"),
    ("PUNCT", r"[(),.*;+\-/]"),
    ("BAD", r"."),
]
MASTER = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))


@dataclass
class Token:
    type: str      # SELECT, IDENT, INT, FLOAT, STRING, '=', ',', EOF ...
    value: object
    line: int
    col: int

    def __str__(self):
        return f"{self.type:<8} {self.value!r:<18} (line {self.line}, col {self.col})"


def tokenize(src):
    """Returns (tokens, errors). Scanning continues after an illegal character."""
    tokens, errors = [], []
    line, line_start = 1, 0
    for m in MASTER.finditer(src):
        kind, text = m.lastgroup, m.group()
        col = m.start() - line_start + 1
        if kind == "NL":
            line, line_start = line + 1, m.end()
        elif kind in ("WS", "COMMENT"):
            continue
        elif kind == "IDENT":
            up = text.upper()
            if up in KEYWORDS:
                tokens.append(Token(up, up, line, col))
            else:
                tokens.append(Token("IDENT", text.lower(), line, col))
        elif kind == "INT":
            tokens.append(Token("INT", int(text), line, col))
        elif kind == "FLOAT":
            tokens.append(Token("FLOAT", float(text), line, col))
        elif kind == "STRING":
            tokens.append(Token("STRING", text[1:-1].replace("''", "'"), line, col))
        elif kind in ("OP", "PUNCT"):
            tokens.append(Token(text, text, line, col))
        else:
            msg = "unterminated string literal" if text == "'" else f"illegal character {text!r}"
            errors.append(LexError(msg, line, col))
    tokens.append(Token("EOF", "<EOF>", line, len(src) - line_start + 1))
    return tokens, errors
