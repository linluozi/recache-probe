"""Per-call cost of re.match(str) vs a precompiled Pattern.match()."""
import json
import re
import statistics
import time

N = 200_000
SUBJECT = "abc abc abc"
PATTERN = re.compile("a+")


def run(fn):
    samples = []
    for _ in range(5):
        started = time.perf_counter()
        for _ in range(N):
            fn()
        samples.append(time.perf_counter() - started)
    return statistics.median(samples) / N * 1e9


if __name__ == "__main__":
    print(json.dumps({
        "n_per_sample": N,
        "samples_per_impl": 5,
        "re_match_string_ns": round(run(lambda: re.match("a+", SUBJECT)), 1),
        "pattern_match_ns": round(run(lambda: PATTERN.match(SUBJECT)), 1),
    }, indent=2))
