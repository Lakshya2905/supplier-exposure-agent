"""Read a function's or module's CODE, with docstrings and comments removed.

Several tests assert that a word does not appear in an implementation:
"weight", "composite", "band", "severity". Those are exactly the words the
docstrings use to explain why the thing is REFUSED, so a raw source scan flags
the explanations rather than the violations. It has caught the wrong thing four
times now, and a test that fails on correct code teaches the next person to
delete the test instead of fixing the violation.

`ast.unparse` drops comments; docstrings are stripped explicitly.
"""
import ast
import inspect
import textwrap


def _strip_docstring(body):
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        return body[1:]
    return body


def code_of(target, functions_only=False):
    """Executable code only, as a string. Accepts a function, class or module.

    `functions_only` drops module-level statements. Needed where a module
    DECLARES the forbidden vocabulary as data: `scoring.FORBIDDEN_UNIT_WORDS`
    literally contains "weight" and "normalised" so that a unit named either can
    be refused at construction. Scanning that declaration flags the guard rather
    than a breach, which is the same wrong-thing failure the module header
    describes.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(target)))
    if not inspect.ismodule(target):
        node = tree.body[0]
        return "\n".join(ast.unparse(item) for item in _strip_docstring(node.body))

    pieces = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            pieces.extend(ast.unparse(item)
                          for item in _strip_docstring(node.body))
        elif not functions_only and not (isinstance(node, ast.Expr)
                                         and isinstance(node.value,
                                                        ast.Constant)):
            pieces.append(ast.unparse(node))
    return "\n".join(pieces)
