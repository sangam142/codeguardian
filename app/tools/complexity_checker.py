"""
Deterministic layer for the Quality Agent: complexity + style checks.

Pure-stdlib (ast) so the pipeline still runs with zero extra dependencies.
Like Bandit, this tool *finds* the issues; the LLM only explains them.

Checks:
    QUAL_COMPLEXITY      cyclomatic complexity over threshold
    QUAL_LONG_FUNC       function body too long
    QUAL_MANY_ARGS       too many parameters
    QUAL_DEEP_NESTING    control flow nested too deep
    QUAL_MUTABLE_DEFAULT mutable default argument (classic Python bug)
    QUAL_BARE_EXCEPT     bare `except:` swallows everything
    QUAL_SYNTAX_ERROR    file does not parse
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.models import Finding, Severity

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}

MAX_COMPLEXITY = 10
MAX_FUNC_LINES = 60
MAX_ARGS = 6
MAX_NESTING = 4

_BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
                 ast.Assert, ast.IfExp)
_NESTING_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With,
                  ast.AsyncWith, ast.Try)
_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def check_complexity(path: str) -> list[Finding]:
    """Run complexity/style checks over every .py file. Never raises."""
    root = Path(path)
    findings: list[Finding] = []
    if not root.exists():
        return findings

    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    for f in files:
        if not f.is_file() or f.suffix != ".py":
            continue
        if any(part in _SKIP_DIRS for part in f.parts):
            continue
        try:
            source = f.read_text(errors="ignore")
            tree = ast.parse(source)
        except SyntaxError as exc:
            findings.append(_finding("QUAL_SYNTAX_ERROR", Severity.LOW,
                                     "File does not parse as Python",
                                     f, root, exc.lineno or 0,
                                     f"SyntaxError: {exc.msg}"))
            continue
        except OSError:
            continue
        findings += _check_tree(tree, f, root)
    return findings


def _check_tree(tree: ast.AST, f: Path, root: Path) -> list[Finding]:
    out: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            out.append(_finding("QUAL_BARE_EXCEPT", Severity.LOW,
                                "Bare `except:` catches everything",
                                f, root, node.lineno,
                                "Catch specific exceptions; bare except hides "
                                "bugs and swallows KeyboardInterrupt."))
        if not isinstance(node, _FUNC_NODES):
            continue

        cc = _cyclomatic_complexity(node)
        if cc > MAX_COMPLEXITY:
            sev = Severity.HIGH if cc > 2 * MAX_COMPLEXITY else Severity.MEDIUM
            out.append(_finding("QUAL_COMPLEXITY", sev,
                                f"`{node.name}` is too complex "
                                f"(cyclomatic complexity {cc})",
                                f, root, node.lineno,
                                f"Threshold is {MAX_COMPLEXITY}. Split the "
                                "function into smaller, testable pieces."))

        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if length > MAX_FUNC_LINES:
            out.append(_finding("QUAL_LONG_FUNC", Severity.LOW,
                                f"`{node.name}` is {length} lines long",
                                f, root, node.lineno,
                                f"Functions over {MAX_FUNC_LINES} lines are "
                                "hard to test; extract helpers."))

        n_args = _arg_count(node)
        if n_args > MAX_ARGS:
            out.append(_finding("QUAL_MANY_ARGS", Severity.LOW,
                                f"`{node.name}` takes {n_args} parameters",
                                f, root, node.lineno,
                                "Group related parameters into a dataclass "
                                "or config object."))

        depth = _max_nesting(node)
        if depth > MAX_NESTING:
            out.append(_finding("QUAL_DEEP_NESTING", Severity.MEDIUM,
                                f"`{node.name}` nests control flow "
                                f"{depth} levels deep",
                                f, root, node.lineno,
                                "Use early returns or extract inner blocks "
                                "to flatten the logic."))

        for default in list(node.args.defaults) + [
                d for d in node.args.kw_defaults if d is not None]:
            if _is_mutable_literal(default):
                out.append(_finding("QUAL_MUTABLE_DEFAULT", Severity.MEDIUM,
                                    f"`{node.name}` has a mutable default "
                                    "argument",
                                    f, root, default.lineno,
                                    "Default is shared across calls. Use "
                                    "`None` and create the object inside."))
    return out


def _cyclomatic_complexity(func: ast.AST) -> int:
    cc = 1
    for node in ast.walk(func):
        if isinstance(node, _BRANCH_NODES):
            cc += 1
        elif isinstance(node, ast.BoolOp):
            cc += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            cc += 1 + len(node.ifs)
        elif isinstance(node, ast.match_case):
            cc += 1
    return cc


def _arg_count(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    a = func.args
    names = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
    # `self`/`cls` don't count against the caller.
    if names and names[0] in ("self", "cls"):
        names = names[1:]
    return len(names) + (1 if a.vararg else 0) + (1 if a.kwarg else 0)


def _max_nesting(func: ast.AST, _depth: int = 0) -> int:
    deepest = _depth
    for child in ast.iter_child_nodes(func):
        if isinstance(child, _FUNC_NODES) and child is not func:
            continue  # nested defs get their own report
        bump = 1 if isinstance(child, _NESTING_NODES) else 0
        deepest = max(deepest, _max_nesting(child, _depth + bump))
    return deepest


def _is_mutable_literal(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("list", "dict", "set"))


def _finding(rule: str, sev: Severity, title: str, f: Path, root: Path,
             line: int, detail: str) -> Finding:
    return Finding(agent="quality", rule=rule, severity=sev, title=title,
                   file=_rel(f, root), line=line, detail=detail)


def _rel(f: Path, root: Path) -> str:
    try:
        return f.relative_to(root).as_posix() if root.is_dir() else f.name
    except ValueError:
        return f.as_posix()
