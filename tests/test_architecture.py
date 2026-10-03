"""The core of each context may import only the stdlib, pydantic, the layers beneath it, and the
domain of the contexts it is declared to build on (D-11)."""

import ast
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

ROOT = "gasprice"
PACKAGE = Path(__file__).resolve().parents[1] / "src" / ROOT
CONTEXTS = ("prices", "trips")
LAYERS = {"domain": ("domain",), "application": ("domain", "application")}
UPSTREAM = {"trips": ("prices",)}
"""trips speaks of states and fuels in the prices context's terms; never the other way round."""


def violations(source: str, module: str, context: str, layer: str) -> list[str]:
    package = module.rsplit(".", 1)[0]
    permitted = (
        {"pydantic"}
        | {f"{ROOT}.{context}.{beneath}" for beneath in LAYERS[layer]}
        | {f"{ROOT}.{upstream}.domain" for upstream in UPSTREAM.get(context, ())}
    )
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "." * node.level + (node.module or "")
            imported.append(resolve_name(name, package) if node.level else name)
    return [
        name
        for name in imported
        if name.split(".")[0] not in sys.stdlib_module_names
        and not any(name == prefix or name.startswith(f"{prefix}.") for prefix in permitted)
    ]


@pytest.mark.parametrize(("context", "layer"), [(c, layer) for c in CONTEXTS for layer in LAYERS])
def test_core_layers_import_only_what_they_may(context: str, layer: str) -> None:
    directory = PACKAGE / context / layer
    assert directory.is_dir(), f"{directory} is missing: the guard would pass vacuously"
    for path in directory.rglob("*.py"):
        module = ".".join((ROOT, *path.relative_to(PACKAGE).with_suffix("").parts))
        assert not violations(path.read_text(encoding="utf-8"), module, context, layer), path


def test_guard_detects_deliberate_violations() -> None:
    assert violations("import django", f"{ROOT}.prices.domain.state", "prices", "domain")
    assert violations("import httpx", f"{ROOT}.prices.application.collect", "prices", "application")
    assert violations(
        f"from {ROOT}.prices.application import x", f"{ROOT}.prices.domain.x", "prices", "domain"
    )
    assert violations(
        "from ..adapters import models", f"{ROOT}.prices.application.x", "prices", "application"
    )
    assert not violations("from decimal import Decimal", f"{ROOT}.prices.domain.x", "prices", "domain")
    assert not violations(
        f"from {ROOT}.prices.domain import State", f"{ROOT}.trips.domain.x", "trips", "domain"
    )
    assert violations(f"from {ROOT}.trips.domain import Route", f"{ROOT}.prices.domain.x", "prices", "domain")
    assert violations(f"from {ROOT}.prices.application import x", f"{ROOT}.trips.domain.x", "trips", "domain")
    assert violations(
        f"from {ROOT}.shared.http import get_bytes", f"{ROOT}.trips.domain.x", "trips", "domain"
    )
