"""Run a representative workload of several real libraries under the probe."""
import importlib.metadata as md
import json

import jinja2
import requests
import yaml
from packaging.version import Version
from rich.text import Text

from recache_probe import probe

rows = {}


def record(name, fn):
    with probe() as p:
        fn()
    rows[name] = {
        "calls": p.calls,
        "string_pattern_calls": p.str_calls,
        "unique_patterns": p.unique_patterns,
        "compile_seconds": round(p.compile_seconds, 6),
        "wall_seconds": round(p.wall_seconds, 4),
    }


versions = sorted({d.version for d in md.distributions() if d.version})
record("packaging.Version x5x95", lambda: [Version(v) for _ in range(5) for v in versions])

env = jinja2.Environment()
template = "{% for x in items %}<li>{{ x|upper }}</li>{% endfor %}"
record(
    "jinja2.from_string+render x100",
    lambda: [env.from_string(template).render(items=["a", "b", "c"]) for _ in range(100)],
)

document = {"a": [1, 2, {"b": "c"}], "d": {"e": None}}
record(
    "yaml.safe_dump+safe_load x100",
    lambda: [yaml.safe_load(yaml.safe_dump(document)) for _ in range(100)],
)

record(
    "rich.Text.from_markup x200",
    lambda: [Text.from_markup("[bold]a[/bold] [red]b[/red]") for _ in range(200)],
)

record(
    "requests.Request.prepare x200",
    lambda: [
        requests.Request("GET", "https://example.com/a?b=1").prepare()
        for _ in range(200)
    ],
)

print(json.dumps(rows, indent=2, sort_keys=True))
