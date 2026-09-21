"""Turn mutmut, Stryker, or a normalized JSON report into mutate snapshots."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from uml_analyzer.scan_python import scan

_KILLED = {"killed", "kill"}
_SURVIVED = {"survived", "timeout", "suspicious", "alive"}
_UNCOVERED = {"nocoverage", "no_coverage", "uncovered", "untested", "notcovered"}
_SKIP = {"ignored", "compileerror", "runtimeerror"}


def _bucket(status: str) -> str | None:
    key = (status or "").replace(" ", "").replace("_", "").lower()
    if key in _SKIP:
        return None
    if key in _KILLED:
        return "killed"
    if key in _SURVIVED:
        return "survived"
    if key in _UNCOVERED:
        return "uncovered"
    return None


def _normalized(modules: list) -> list[dict]:
    out = []
    for mod in modules:
        forms = []
        for form in mod.get("forms") or []:
            killed = int(form.get("killed") or 0)
            survived = int(form.get("survived") or 0)
            uncovered = int(form.get("uncovered") or 0)
            sites = int(form.get("sites") or (killed + survived + uncovered))
            forms.append({
                "name": form["name"],
                "private": bool(form.get("private")),
                "killed": killed,
                "survived": survived,
                "uncovered": uncovered,
                "sites": sites,
            })
        out.append({
            "namespace": mod["namespace"],
            "source": mod.get("source") or "",
            "forms": forms,
        })
    return out


def _stryker_mutants(data: dict) -> list[dict]:
    rows = []
    for file, body in (data.get("files") or {}).items():
        if not isinstance(body, dict):
            continue
        for mutant in body.get("mutants") or []:
            line = ((mutant.get("location") or {}).get("start") or {}).get("line")
            if line:
                rows.append({"file": file, "line": int(line), "status": mutant.get("status") or ""})
    return rows


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _mutmut_rows(path: Path) -> list[dict]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            info = list(con.execute(f"PRAGMA table_info({_quote(table)})"))
            cols = {row[1].lower(): row[1] for row in info}
            file_col = next((cols[k] for k in ("file", "source", "sourcefile", "filename") if k in cols), None)
            line_col = next((cols[k] for k in ("line", "lineno", "line_number") if k in cols), None)
            status_col = next((cols[k] for k in ("status", "result") if k in cols), None)
            if not (file_col and line_col and status_col):
                continue
            rows = []
            query = (
                f"SELECT {_quote(file_col)}, {_quote(line_col)}, {_quote(status_col)} "
                f"FROM {_quote(table)}"
            )
            for file, line, status in con.execute(query):
                if line is None:
                    continue
                rows.append({"file": str(file), "line": int(line), "status": str(status)})
            if rows:
                return rows
    finally:
        con.close()
    return []


def _member_at(members: list[dict], line: int) -> dict | None:
    hits = [m for m in members if m["line"] <= line <= m["endLine"]]
    if not hits:
        return None
    hits.sort(key=lambda m: (m["endLine"] - m["line"], m["line"]))
    return hits[0]


def _from_rows(graph: dict, rows: list[dict]) -> list[dict]:
    by_file: dict[str, list[dict]] = {}
    for member in graph["members"]:
        by_file.setdefault(member.get("file") or "", []).append(member)
    resolved = {}
    for key in list(by_file):
        try:
            resolved[str(Path(key).resolve())] = by_file[key]
        except OSError:
            resolved[key] = by_file[key]
    counts: dict[tuple, dict] = {}
    sources: dict[str, str] = {}
    for row in rows:
        bucket = _bucket(row["status"])
        if not bucket:
            continue
        try:
            key = str(Path(row["file"]).resolve())
        except OSError:
            key = row["file"]
        members = resolved.get(key)
        if members is None:
            for path, group in resolved.items():
                if path.endswith(row["file"]) or row["file"].endswith(path):
                    members = group
                    break
        if not members:
            continue
        member = _member_at(members, row["line"])
        if member is None:
            continue
        slot = counts.setdefault((member["ns"], member["name"]), {
            "name": member["name"],
            "private": bool(member["private"]),
            "killed": 0,
            "survived": 0,
            "uncovered": 0,
        })
        slot[bucket] += 1
        sources[member["ns"]] = member.get("file") or ""
    grouped: dict[str, list] = {}
    for (ns, _name), form in counts.items():
        form["sites"] = form["killed"] + form["survived"] + form["uncovered"]
        grouped.setdefault(ns, []).append(form)
    return [{"namespace": ns, "source": sources.get(ns, ""), "forms": forms}
            for ns, forms in sorted(grouped.items())]


def mutation_snapshots(src: str, prefix: str, report: str) -> dict:
    path = Path(report)
    if path.suffix in {".sqlite", ".db"} or path.name.endswith("mutmut-cache"):
        return {"modules": _from_rows(scan(src, prefix), _mutmut_rows(path))}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("modules"):
        return {"modules": _normalized(data["modules"])}
    if isinstance(data, dict) and data.get("files"):
        return {"modules": _from_rows(scan(src, prefix), _stryker_mutants(data))}
    return {"modules": []}
