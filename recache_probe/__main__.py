"""CLI: python -m recache_probe [--json] script.py [args...]"""

from __future__ import annotations

import json
import runpy
import sys

from .probe import Probe, format_report


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = False
    if args and args[0] == "--json":
        as_json = True
        args.pop(0)
    if not args:
        print("usage: python -m recache_probe [--json] script.py [args...]", file=sys.stderr)
        return 2
    script, rest = args[0], args[1:]
    sys.argv = [script, *rest]
    p = Probe()
    code = 0
    with p:
        try:
            runpy.run_path(script, run_name="__main__")
        except SystemExit as exc:
            code = int(exc.code or 0)
    if as_json:
        print(
            json.dumps(
                {
                    "calls": p.calls,
                    "str_calls": p.str_calls,
                    "unique_patterns": p.unique_patterns,
                    "compile_seconds": p.compile_seconds,
                    "wall_seconds": p.wall_seconds,
                    "tax_ratio": p.tax_ratio,
                    "top": [
                        {"pattern": pat, "flags": fl, "calls": n, "seconds": s}
                        for pat, fl, n, s in p.top(20)
                    ],
                },
                indent=2,
            )
        )
    else:
        print(format_report(p), file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
