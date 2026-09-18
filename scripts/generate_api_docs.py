import ast
from pathlib import Path

root = Path.cwd()
for repo in sorted(root.glob("nexus-atom-*")):
    pkg = repo.name.replace("-", "_")
    (repo / "docs").mkdir(exist_ok=True)
    lines = [
        f"# {repo.name} Python API",
        "",
        "Public definitions below are generated from the shipped source. See USAGE.md and the README for runnable setup, semantics and limits. Contracts inherit strict extra-field rejection and finite-number validation where declared. Source links include the implementation for details.",
        "",
    ]
    for source in sorted((repo / "src" / pkg).rglob("*.py")):
        if source.name in {"__init__.py", "__main__.py"}:
            continue
        tree = ast.parse(source.read_text())
        module = ".".join(source.relative_to(repo / "src").with_suffix("").parts)
        lines += [f"## `{module}`", ""]
        doc = ast.get_docstring(tree)
        if doc:
            lines += [doc, ""]
        for node in tree.body:
            if not isinstance(
                node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ) or node.name.startswith("_"):
                continue
            link = f"../{source.relative_to(repo)}#L{node.lineno}"
            lines += [f"### `{node.name}`", "", f"[Source]({link})", ""]
            doc = ast.get_docstring(node)
            if doc:
                lines += [doc, ""]
            if isinstance(node, ast.ClassDef):
                bases = ", ".join(ast.unparse(base) for base in node.bases)
                lines += ["```python", f"class {node.name}({bases}):"]
                for child in node.body:
                    if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                        lines.append("    " + ast.unparse(child))
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        not child.name.startswith("_") or child.name == "__init__"
                    ):
                        signature = (
                            ("async " if isinstance(child, ast.AsyncFunctionDef) else "")
                            + "def "
                            + child.name
                            + "("
                            + ast.unparse(child.args)
                            + ")"
                        )
                        if child.returns:
                            signature += " -> " + ast.unparse(child.returns)
                        lines.append("    " + signature + ": ...")
                lines += ["```", ""]
            else:
                signature = (
                    ("async " if isinstance(node, ast.AsyncFunctionDef) else "")
                    + "def "
                    + node.name
                    + "("
                    + ast.unparse(node.args)
                    + ")"
                )
                if node.returns:
                    signature += " -> " + ast.unparse(node.returns)
                lines += ["```python", signature + ": ...", "```", ""]
    (repo / "docs/API.md").write_text("\n".join(lines))
