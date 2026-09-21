"""Join coverage.py or Istanbul JSON onto scanned members."""

from __future__ import annotations

import json
from pathlib import Path

from uml_analyzer.scan_python import scan


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _match_file(files: dict, member_file: str) -> dict | None:
    target = Path(member_file).resolve()
    if member_file in files:
        return files[member_file]
    for key, body in files.items():
        try:
            if Path(key).resolve() == target:
                return body
        except OSError:
            continue
        if key.replace("\\", "/").endswith(target.as_posix()) or target.as_posix().endswith(key.replace("\\", "/")):
            return body
    return None


def _percent(file_data: dict | None, start: int, end: int) -> float | None:
    if not file_data:
        return None
    executed = set(file_data.get("executed_lines") or [])
    missing = set(file_data.get("missing_lines") or [])
    if not executed and not missing:
        # Istanbul statement map.
        stmt_map = file_data.get("statementMap") or {}
        hits = file_data.get("s") or {}
        covered = 0
        total = 0
        for sid, loc in stmt_map.items():
            line = ((loc or {}).get("start") or {}).get("line")
            if line is None or line < start or line > end:
                continue
            total += 1
            if hits.get(sid) or hits.get(str(sid)):
                covered += 1
        if total == 0:
            return None
        return 100.0 * covered / total
    stmts = [n for n in range(start, end + 1) if n in executed or n in missing]
    if not stmts:
        return None
    return 100.0 * sum(1 for n in stmts if n in executed) / len(stmts)


def coverage_entries(src: str, prefix: str, coverage_file: str) -> dict:
    graph = scan(src, prefix)
    data = _load(coverage_file)
    files = data.get("files") or data
    if not isinstance(files, dict):
        files = {}
    entries = []
    for member in graph["members"]:
        body = _match_file(files, member.get("file") or "")
        cov = _percent(body, int(member["line"]), int(member["endLine"]))
        entry = {
            "namespace": member["ns"],
            "name": member["name"],
            "complexity": member["complexity"],
            "private": bool(member["private"]),
        }
        if cov is not None:
            entry["coverage"] = cov
        entries.append(entry)
    return {"entries": entries}
