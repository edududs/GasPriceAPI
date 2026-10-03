"""The core may import only the stdlib, pydantic and the layers beneath it."""

import ast
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

ROOT = "gasprice"
PACKAGE = Path(__file__).resolve().parents[1] / "src" / ROOT
CONTEXTS = ("prices",)
LAYERS = {"domain": ("domain",), "application": ("domain", "application")}


def violations(source: str, module: str, context: str, layer: str) -> list[str]:
    package = module.rsplit(".", 1)[0]
    permitted = {"pydantic"} | {f"{ROOT}.{context}.{beneath}" for beneath in LAYERS[layer]}
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
