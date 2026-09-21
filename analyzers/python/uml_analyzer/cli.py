"""CLI: scan, locate, discover, coverage, mutate. JSON on stdout."""

from __future__ import annotations

import argparse
import json
import sys

from uml_analyzer.coverage_import import coverage_entries
from uml_analyzer.mutation_import import mutation_snapshots
from uml_analyzer.scan_python import discover, locate, scan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uml_analyzer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan_p = sub.add_parser("scan")
    scan_p.add_argument("--src", required=True)
    scan_p.add_argument("--prefix", default="")

    loc = sub.add_parser("locate")
    loc.add_argument("--src", required=True)
    loc.add_argument("--prefix", default="")
    loc.add_argument("--ns", required=True)
    loc.add_argument("--name", default="")

    disc = sub.add_parser("discover")
    disc.add_argument("--root", required=True)

    cov = sub.add_parser("coverage")
    cov.add_argument("--src", required=True)
    cov.add_argument("--prefix", default="")
    cov.add_argument("--coverage", required=True)

    mut = sub.add_parser("mutate")
    mut.add_argument("--src", required=True)
    mut.add_argument("--prefix", default="")
    mut.add_argument("--report", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "scan":
        payload = scan(args.src, args.prefix)
    elif args.cmd == "locate":
        payload = locate(args.src, args.prefix, args.ns, args.name or None)
    elif args.cmd == "discover":
        payload = discover(args.root)
    elif args.cmd == "coverage":
        payload = coverage_entries(args.src, args.prefix, args.coverage)
    elif args.cmd == "mutate":
        payload = mutation_snapshots(args.src, args.prefix, args.report)
    else:
        return 2
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0
