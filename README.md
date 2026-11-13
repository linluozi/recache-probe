# recache-probe

Measure how much time a Python process wastes re-entering CPython's regex cache, per pattern, with a reproducible case study showing when "precompile your regexes" is worth it — and when it is not.

Upstream: none (original tool).

## Why

`re.match("a+", s)` does **not** reuse a compiled pattern object. Every call goes through `re._compile(pattern, flags)`, which performs a cache lookup (and a lock) before returning the cached `Pattern`. A precompiled `PATTERN.match(s)` skips that path. The cost is small per call, but it is paid in every parser loop, and until now it was invisible: profilers attribute the time to `re._compile`, not to your pattern.

`recache-probe` wraps `re._compile`, counts every re-entry, and attributes time to `(pattern, flags)`. It answers: *how many calls, which patterns, how many milliseconds, and what fraction of wall time?*

## Install

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
# or just run from the checkout:
PYTHONPATH=. python -m recache_probe --json your_script.py
```

No runtime dependencies. CPython 3.9+ (uses the private `re._compile`, restored on exit).

## Use

```python
import re
from recache_probe import probe, format_report

with probe() as p:
    for line in lines:
        re.match(r"\s*#", line)

print(format_report(p))
print(p.calls, p.unique_patterns, p.compile_seconds, p.tax_ratio)
```

CLI:

```bash
PYTHONPATH=. python -m recache_probe --json path/to/script.py arg1
```

## Case study: marko 2.x block parser (real corpus)

Corpus: marko commit `5611794` test fixtures `tests/spec/commonmark.txt` + `gfm.txt` + `tests/samples/*.md` = **437,388 bytes** of real Markdown. Harness: `bench/marko_case.py`, one parse after import, probe around a second parse. Results in `bench/results.json`.

| metric | value |
| --- | --- |
| parse median (5 runs) | **0.2879 s** |
| `re._compile` re-entries | **27,544** |
| distinct patterns | **54** |
| time inside `re._compile` | **14.3 ms** |
| tax ratio (probe) | **4.41 %** |
| microbench `re.match(str)` | **540.6 ns/call** |
| microbench `Pattern.match` | **246.9 ns/call** |

Two takeaways, both measured rather than assumed:

1. The tax is real but bounded: ~294 ns per call at this pattern set. You need roughly **3.4 million** re-entries to pay one second.
2. The probe's 4.41 % is an **upper bound**: instrumenting every call adds two `perf_counter()` calls. An end-to-end ablation confirms the gap — applying a 90-line micro-patch (`bench/micro_patch.diff`) that caches prefix regexes and hoists three patterns moved the same corpus from **0.2974 s to 0.2907 s (1.02x, 5 runs each)**, not the ~4.4 % the probe alone suggests.

So the honest conclusion is a **negative result for the common advice**: precompiling regexes in an already-compiled-regex parser is a ~2 % optimization, not a 20 % one. Use this tool to decide whether your call count is in the range where it matters (10^6+), instead of rewriting hot loops on a hunch.

## Tests

```bash
python -m pytest tests -q
# 9 passed
```

Tests cover: counting string re-entries, ignoring precompiled `Pattern.match`, per-pattern separation, `re._compile` restoration on normal exit and on exception, finite wall/ratio, report contents, `top()` ordering, and the CLI in a child process.

## Reproduce

```bash
# 1. tool tests
python -m pytest tests -q
# 2. microbenchmark
python bench/microbench.py
# 3. marko case study (clone marko at 5611794 first)
git clone --depth=1 git@github.com:frostming/marko.git /tmp/marko
cat /tmp/marko/tests/spec/commonmark.txt /tmp/marko/tests/spec/gfm.txt \
    /tmp/marko/tests/samples/jquery.md /tmp/marko/tests/samples/syntax.md > /tmp/corpus.md
PYTHONPATH=/tmp/marko:. python bench/marko_case.py /tmp/corpus.md
```

## Environment

- CPU: AMD EPYC 7K62 (4 vCPU), RAM 3,723 MB
- CPython **3.12.3** (`/usr/bin/python3.12`), pytest 9.2.0
- Seed: not applicable (no randomized inputs); every timing is `time.perf_counter()`, 5 samples, median reported
- marko revision: `5611794991268c5a77dc4cc98cc369525b50d356`

## 本轮创新

第一次把 CPython 正则缓存**重复进入**（`re._compile` re-entry）按 pattern 归因并量化，给出可复算的阈值（~0.29 µs/次，10^6 次才值得改），并用 marko 真实语料上的 1.02x 端到端消融**推翻**"预编译正则总能显著提速"的常见假设。与台账里按热点函数/缓存结果做的 lab 不同：这里测的是解释器调用路径本身的开销，结论是负面的、可证伪的。

## Limits

- `re._compile` is a CPython implementation detail; the wrapper is restored on exit but a hard crash inside the block would leave it patched in that process.
- Counters are not lock-protected; use one probe per thread.
- The probe measures **cache re-entry**, not regex matching itself. It cannot tell you a pattern is slow to run.

## License

MIT, original work. See `LICENSE`.
