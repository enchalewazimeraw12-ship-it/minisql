class CompilerError(Exception):
    phase = "Error"

    def __init__(self, msg, line=0, col=0):
        super().__init__(msg)
        self.msg, self.line, self.col = msg, line, col

    def __str__(self):
        loc = f" line {self.line}, col {self.col}:" if self.line else ""
        return f"[{self.phase}]{loc} {self.msg}"


class LexError(CompilerError):
    phase = "Lexical Error"


class ParseError(CompilerError):
    phase = "Syntax Error"


class SemanticError(CompilerError):
    phase = "Semantic Error"


class ExecError(CompilerError):
    phase = "Runtime Error"
