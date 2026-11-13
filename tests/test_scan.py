import json
import subprocess
import sys
from pathlib import Path

from recache_probe.scan import scan_paths, scan_source

ROOT = Path(__file__).resolve().parents[1]


def test_detects_attribute_calls_and_ignores_compile():
    source = 'import re\nre.match(r"a+", s)\nre.compile("x")\nre.findall("b", s)\n'
    sites = scan_source(source, "m.py")
    assert [s.function for s in sites] == ["match", "findall"]
    assert sites[0].pattern == r"a+"
    assert sites[0].line == 2


def test_detects_module_alias_and_from_import_alias():
    source = (
        "import re as rx\n"
        'rx.search("a", s)\n'
        "from re import fullmatch as fm\n"
        'fm("b", s)\n'
    )
    sites = scan_source(source, "m.py")
    assert [(s.function, s.pattern) for s in sites] == [("search", "a"), ("fullmatch", "b")]


def test_skips_non_literal_patterns():
    source = 'import re\npattern = "a"\nre.match(pattern, s)\nre.sub(f"{pattern}", "x", s)\n'
    assert scan_source(source, "m.py") == []


def test_scan_paths_skips_pycache_and_bad_syntax(tmp_path):
    (tmp_path / "good.py").write_text('import re\nre.match("a", s)\n')
    (tmp_path / "broken.py").write_text("def (:\n")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "cached.py").write_text('import re\nre.match("a", s)\n')
    sites = scan_paths([str(tmp_path)])
    assert [s.path for s in sites] == [str(tmp_path / "good.py")]


def test_cli_scan(tmp_path):
    (tmp_path / "mod.py").write_text('import re\nre.match("abc", s)\n')
    proc = subprocess.run(
        [sys.executable, "-m", "recache_probe", "scan", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "re.match('abc')" in proc.stdout
    assert "1 literal-pattern call site(s)" in proc.stderr
