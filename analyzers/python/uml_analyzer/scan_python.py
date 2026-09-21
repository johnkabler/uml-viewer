"""Scan a Python tree into the uml-viewer class/edge/member contract."""

from __future__ import annotations

import ast
import re
from pathlib import Path

SKIP_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".git",
    ".uml-viewer",
    "tests",
    "test",
    "__tests__",
    ".tox",
    ".mypy_cache",
    "site-packages",
    ".eggs",
}

STDLIB_INTERFACE = {
    ("abc", "ABC"),
    ("abc", "ABCMeta"),
    ("typing", "Protocol"),
    (None, "ABC"),
    (None, "ABCMeta"),
    (None, "Protocol"),
}


def _is_private(name: str) -> bool:
    if name.startswith("__") and name.endswith("__"):
        return name != "__init__"
    return name.startswith("_")


def _display_name(id_str: str) -> str:
    last = id_str.split(".")[-1]
    bits = re.split(r"[-_]", last)
    return "".join(b[:1].upper() + b[1:] for b in bits if b) or last


def _module_id(ns: str, prefix: str) -> str:
    if prefix and (ns == prefix or ns.startswith(prefix + ".")):
        tail = ns[len(prefix) + 1 :] if ns.startswith(prefix + ".") else ns
    else:
        tail = ns
    return tail.replace("/", ".")


def _skip_dir(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def _skip_file(path: Path) -> bool:
    name = path.name
    if name == "conftest.py" or name.endswith("_test.py") or name.startswith("test_"):
        return True
    return _skip_dir(path.parent)


def _py_files(src: Path) -> list[Path]:
    files = []
    if not src.exists():
        return files
    for path in src.rglob("*.py"):
        if path.is_file() and not _skip_file(path):
            files.append(path)
    return sorted(files)


def _module_ns(src: Path, path: Path, prefix: str) -> tuple[str, bool]:
    rel = path.relative_to(src)
    parts = list(rel.parts)
    is_package = parts[-1] == "__init__.py"
    if is_package:
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][: -len(".py")]
    if not parts:
        ns = prefix or ""
    else:
        ns = ".".join(parts)
        if prefix and not (ns == prefix or ns.startswith(prefix + ".")):
            ns = prefix + "." + ns
    return ns, is_package


def _expr_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expr_name(node.value)
        if prefix:
            return prefix + "." + node.attr
    return None


def _complexity(node: ast.AST) -> int:
    cc = 1

    def walk(n: ast.AST) -> None:
        nonlocal cc
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
                                  ast.With, ast.AsyncWith, ast.Assert, ast.IfExp)):
                cc += 1
            elif isinstance(child, ast.comprehension):
                cc += 1 + len(child.ifs)
            elif isinstance(child, ast.BoolOp):
                cc += max(0, len(child.values) - 1)
            elif isinstance(child, ast.Match):
                cc += max(0, len(child.cases) - 1)
            walk(child)

    walk(node)
    return cc


class _FileParser(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: list[dict] = []
        self.classes: list[dict] = []
        self.functions: list[dict] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append({"module": alias.name, "level": 0, "names": [],
                                 "alias": alias.asname})
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append({
            "module": node.module,
            "level": node.level or 0,
            "names": [{"name": a.name, "alias": a.asname} for a in node.names],
            "alias": None,
        })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append({
            "name": node.name,
            "bases": [n for n in (_expr_name(b) for b in node.bases) if n],
            "line": node.lineno,
            "end": getattr(node, "end_lineno", node.lineno),
            "node": node,
        })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._fn(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._fn(node)

    def _fn(self, node: ast.AST) -> None:
        self.functions.append({
            "name": node.name,
            "line": node.lineno,
            "end": getattr(node, "end_lineno", node.lineno),
            "node": node,
            "owner": None,
        })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        called = None
        if isinstance(func, ast.Attribute) and func.attr == "import_module":
            called = func.attr
        elif isinstance(func, ast.Name) and func.id == "import_module":
            called = func.id
        if called == "import_module" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                self.imports.append({"module": arg.value, "level": 0, "names": [], "alias": None})
        self.generic_visit(node)


def _parse_file(path: Path) -> _FileParser | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None
    parser = _FileParser()
    parser.visit(tree)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for fn in parser.functions:
                        if fn["node"] is child:
                            fn["owner"] = node.name
    return parser


def _package_parts(ns: str, is_package: bool) -> list[str]:
    parts = ns.split(".") if ns else []
    if not is_package and parts:
        parts = parts[:-1]
    return parts


def _resolve_relative(ns: str, is_package: bool, module: str | None, level: int) -> str | None:
    parts = _package_parts(ns, is_package)
    drop = level - 1
    if drop > len(parts):
        return None
    base = parts[: len(parts) - drop]
    if module:
        return ".".join([*base, *module.split(".")])
    return ".".join(base) if base else None


def _absolute_module(ns: str, is_package: bool, imp: dict) -> str | None:
    if imp["level"]:
        return _resolve_relative(ns, is_package, imp["module"], imp["level"])
    return imp["module"]


def _stdlib_interface(base: str, bindings: dict) -> bool:
    if "." not in base:
        bound = bindings.get(base)
        if bound and bound.get("attr") is None and bound.get("module") in {"abc", "typing"}:
            return (bound["module"], base) in {("abc", "ABC"), ("abc", "ABCMeta"), ("typing", "Protocol")} or (
                bound.get("origin") in {"ABC", "ABCMeta", "Protocol"}
            )
        origin = bound["origin"] if bound else base
        module = bound["module"] if bound else None
        if bound and bound.get("attr"):
            return (module, bound["attr"]) in STDLIB_INTERFACE or (None, origin) in STDLIB_INTERFACE
        return (module, origin) in STDLIB_INTERFACE or (None, origin) in STDLIB_INTERFACE
    head, _, tail = base.partition(".")
    bound = bindings.get(head)
    module = bound["module"] if bound else head
    attr = tail.split(".")[-1]
    return (module, attr) in STDLIB_INTERFACE


def _bindings_for(ns: str, is_package: bool, imports: list[dict], known: set[str]) -> tuple[dict, list[str]]:
    bindings: dict[str, dict] = {}
    targets: list[str] = []
    for imp in imports:
        mod = _absolute_module(ns, is_package, imp)
        if not mod:
            continue
        names = imp["names"]
        if not names:
            targets.append(mod)
            alias = imp.get("alias") or mod.split(".")[0]
            bindings[alias] = {"module": mod, "attr": None, "origin": alias}
            continue
        package_hit = False
        for item in names:
            if item["name"] == "*":
                targets.append(mod)
                package_hit = True
                continue
            sub = f"{mod}.{item['name']}"
            local = item["alias"] or item["name"]
            if sub in known:
                targets.append(sub)
                bindings[local] = {"module": sub, "attr": None, "origin": item["name"]}
            else:
                if not package_hit:
                    targets.append(mod)
                    package_hit = True
                bindings[local] = {"module": mod, "attr": item["name"], "origin": item["name"]}
    return bindings, targets


def _lookup_class(module: str, attr: str | None, class_index: dict) -> dict | None:
    classes = class_index.get(module) or []
    if attr is None:
        return None
    for cls in classes:
        if cls["name"] == attr:
            return {"module": module, "name": attr, "interface": cls["interface"]}
    return None


def _resolve_base(base: str, bindings: dict, class_index: dict, known: set[str]) -> dict | None:
    if "." not in base:
        bound = bindings.get(base)
        if not bound:
            return None
        module = bound["module"]
        attr = bound.get("attr") or (None if bound.get("attr") is None and module in known else base)
        if bound.get("attr") is None and module in known:
            # `import pkg.mod as alias` then `class C(alias.Name)` is dotted; a bare alias is the module.
            return None
        if module not in known:
            return None
        return _lookup_class(module, bound.get("attr"), class_index)
    head, _, tail = base.partition(".")
    bound = bindings.get(head)
    if not bound:
        return None
    module = bound["module"]
    extra = tail.split(".")
    if bound.get("attr"):
        # bound name already points at a class; further attributes are not a module edge
        return None
    # Walk submodule segments, last segment is the class name.
    if len(extra) >= 2:
        module = module + "." + ".".join(extra[:-1])
        attr = extra[-1]
    else:
        attr = extra[0]
    if module not in known:
        return None
    return _lookup_class(module, attr, class_index)


def scan(src: str, prefix: str = "") -> dict:
    root = Path(src).resolve()
    prefix = prefix or ""
    parsed = []
    for path in _py_files(root):
        ns, is_package = _module_ns(root, path, prefix)
        if not ns:
            continue
        parser = _parse_file(path)
        if parser is None:
            continue
        parsed.append({
            "path": path,
            "ns": ns,
            "is_package": is_package,
            "parser": parser,
        })
    known = {item["ns"] for item in parsed}
    class_index: dict[str, list[dict]] = {}
    file_bindings = []
    for item in parsed:
        bindings, targets = _bindings_for(item["ns"], item["is_package"], item["parser"].imports, known)
        classes = []
        for cls in item["parser"].classes:
            classes.append({
                "name": cls["name"],
                "bases": cls["bases"],
                "interface": False,
                "line": cls["line"],
                "end": cls["end"],
            })
        class_index[item["ns"]] = classes
        file_bindings.append((item, bindings, targets, classes))

    for item, bindings, _targets, classes in file_bindings:
        live = {c["name"]: c for c in classes}
        for cls in item["parser"].classes:
            rec = live[cls["name"]]
            rec["interface"] = any(_stdlib_interface(base, bindings) for base in cls["bases"])

    classes_out = []
    edges = []
    members = []
    foreign: dict[str, dict] = {}
    seen_edges: set[tuple] = set()

    def add_edge(frm: str, to: str, kind: str) -> None:
        key = (frm, to, kind)
        if frm == to or key in seen_edges or not to:
            return
        seen_edges.add(key)
        edges.append({"from": frm, "to": to, "kind": kind})

    for item, bindings, targets, classes in file_bindings:
        ns = item["ns"]
        id_str = _module_id(ns, prefix)
        public_classes = [c for c in classes if not _is_private(c["name"])]
        public_fns = [f for f in item["parser"].functions
                      if f["owner"] is None and not _is_private(f["name"])]
        stereotype = None
        if public_classes and not public_fns and all(c["interface"] for c in public_classes):
            stereotype = "interface"
        rec = {"id": id_str, "name": _display_name(id_str), "ns": ns}
        if stereotype:
            rec["stereotype"] = stereotype
        classes_out.append(rec)

        for target in targets:
            if target in known:
                add_edge(id_str, _module_id(target, prefix), "dependency")
            elif target and not target.startswith("__future__"):
                fid = target.replace("/", ".")
                foreign[fid] = {"id": fid, "name": fid, "ns": target, "foreign": True}
                add_edge(id_str, fid, "dependency")

        for cls in item["parser"].classes:
            rec_cls = next(c for c in classes if c["name"] == cls["name"])
            for base in cls["bases"]:
                resolved = _resolve_base(base, bindings, class_index, known)
                if not resolved or resolved["module"] == ns:
                    continue
                kind = "implements" if resolved["interface"] else "inheritance"
                add_edge(id_str, _module_id(resolved["module"], prefix), kind)
            members.append({
                "ns": ns,
                "name": cls["name"],
                "private": _is_private(cls["name"]),
                "complexity": 1,
                "line": cls["line"],
                "endLine": cls["end"],
                "file": str(item["path"]),
            })
        for fn in item["parser"].functions:
            name = f"{fn['owner']}.{fn['name']}" if fn["owner"] else fn["name"]
            members.append({
                "ns": ns,
                "name": name,
                "private": _is_private(fn["name"]),
                "complexity": _complexity(fn["node"]),
                "line": fn["line"],
                "endLine": fn["end"],
                "file": str(item["path"]),
            })

    classes_out.extend(foreign.values())
    return {"classes": classes_out, "edges": edges, "members": members}


def locate(src: str, prefix: str, ns: str, name: str | None = None) -> dict:
    root = Path(src).resolve()
    prefix = prefix or ""
    found = None
    for path in _py_files(root):
        mod, _is_pkg = _module_ns(root, path, prefix)
        if mod == ns:
            found = path
            break
    if found is None:
        return {"file": None, "line": None, "title": None}
    line = None
    if name:
        parser = _parse_file(found)
        if parser is not None:
            if "." in name:
                owner, meth = name.split(".", 1)
                for fn in parser.functions:
                    if fn["owner"] == owner and fn["name"] == meth:
                        line = fn["line"]
                        break
            else:
                for fn in parser.functions:
                    if fn["owner"] is None and fn["name"] == name:
                        line = fn["line"]
                        break
                if line is None:
                    for cls in parser.classes:
                        if cls["name"] == name:
                            line = cls["line"]
                            break
    title = str(found) if line is None else f"{found}:{line}"
    return {"file": str(found), "line": line, "title": title}


def discover(project: str) -> dict:
    root = Path(project).resolve()
    src = root / "src" if (root / "src").is_dir() else root
    graph = scan(str(src), "")
    modules = [c["ns"] for c in graph["classes"] if not c.get("foreign") and c.get("ns")]
    prefix = ""
    parts = [m.split(".") for m in modules if m]
    if parts and all(p[0] == parts[0][0] for p in parts) and all(len(p) > 1 or (src / p[0]).is_dir() for p in parts):
        # A shared first segment that is a package directory is the prefix.
        first = parts[0][0]
        if (src / first).is_dir() and any(len(p) > 1 for p in parts):
            prefix = first
    order = []
    seen = set()
    for ns in sorted(modules):
        rest = ns[len(prefix) + 1 :] if prefix and (ns == prefix or ns.startswith(prefix + ".")) else ns
        if prefix and ns == prefix:
            continue
        seg = rest.split(".")[0] if rest else ""
        if seg and seg not in seen:
            seen.add(seg)
            order.append(seg)
    title = prefix or root.name
    rel_src = "src" if src == root / "src" else "."
    return {"lang": "python", "src": rel_src, "prefix": prefix, "order": order, "title": title}
