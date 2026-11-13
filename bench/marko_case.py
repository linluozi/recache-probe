"""Case study: regex-cache tax inside marko's block parser.

Usage: PYTHONPATH=/path/to/marko python bench/marko_case.py corpus.md
"""
import json
import statistics
import sys
import time

import marko

from recache_probe import probe


def timed(corpus, repeats=5):
    samples = []
    for _ in range(repeats):
        parser = marko.Markdown()
        started = time.perf_counter()
        parser.parse(corpus)
        samples.append(time.perf_counter() - started)
    return statistics.median(samples), samples


if __name__ == "__main__":
    path = sys.argv[1]
    corpus = open(path, encoding="utf-8").read()
    plain, samples = timed(corpus)
    with probe() as p:
        marko.Markdown().parse(corpus)
    print(json.dumps({
        "corpus_bytes": len(corpus.encode("utf-8")),
        "parse_seconds_median": round(plain, 4),
        "parse_samples": [round(s, 4) for s in samples],
        "compile_calls": p.calls,
        "string_pattern_calls": p.str_calls,
        "unique_patterns": p.unique_patterns,
        "compile_seconds": round(p.compile_seconds, 5),
        "tax_ratio": round(p.tax_ratio, 4),
        "top": [
            {"pattern": pat, "flags": fl, "calls": n, "seconds": round(s, 5)}
            for pat, fl, n, s in p.top(5)
        ],
    }, indent=2))
