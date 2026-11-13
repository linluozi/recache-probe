import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from recache_probe import Probe, format_report, probe

ROOT = Path(__file__).resolve().parents[1]


def test_counts_string_re_entries():
    with probe() as p:
        for _ in range(200):
            re.match(r"a+", "aaa")
    assert p.calls == 200
    assert p.str_calls == 200
    assert p.unique_patterns == 1
    (pattern, flags), stat = next(iter(p.stats.items()))
    assert pattern == r"a+"
    assert flags == 0
    assert stat.calls == 200
    assert stat.seconds > 0


def test_precompiled_patterns_are_not_counted():
    compiled = re.compile(r"a+")
    with probe() as p:
        for _ in range(200):
            compiled.match("aaa")
    assert p.calls == 0
    assert p.str_calls == 0
    assert p.stats == {}


def test_distinct_patterns_are_kept_apart():
    with probe() as p:
        for _ in range(3):
            re.match("a", "a")
        for _ in range(2):
            re.match("b", "b")
    assert p.unique_patterns == 2
    assert p.stats[("a", 0)].calls == 3
    assert p.stats[("b", 0)].calls == 2


def test_compile_is_restored():
    original = re._compile
    with probe():
        assert re._compile is not original
    assert re._compile is original


def test_compile_is_restored_after_exception():
    original = re._compile
    with pytest.raises(RuntimeError):
        with probe():
            raise RuntimeError("boom")
    assert re._compile is original


def test_wall_and_ratio_are_finite():
    with probe() as p:
        re.match("x", "x")
    assert p.wall_seconds > 0
    assert 0.0 <= p.tax_ratio <= 1.0


def test_format_report_mentions_every_number():
    with probe() as p:
        for _ in range(7):
            re.match("z", "z")
    text = format_report(p)
    assert "7" in text
    assert "unique patterns   : 1" in text
    assert "time in _compile" in text


def test_top_is_sorted_by_seconds():
    with probe() as p:
        for _ in range(50):
            re.match(r"(a+)+$", "a" * 20)
        for _ in range(2):
            re.match("q", "q")
    top = p.top(1)
    assert len(top) == 1
    assert top[0][0] == r"(a+)+$"


def test_cli_counts_calls_in_child_script(tmp_path):
    script = tmp_path / "child.py"
    script.write_text(
        "import re\n"
        "for _ in range(50):\n"
        "    re.match('abc', 'abc')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-m", "recache_probe", "--json", str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["str_calls"] >= 50
    assert payload["unique_patterns"] >= 1
    assert payload["top"][0]["calls"] >= 50
