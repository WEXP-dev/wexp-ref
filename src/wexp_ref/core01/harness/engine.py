"""The engine protocol and registry.

Classification: **SHARED-INFRASTRUCTURE-SAFE** (this file only)

This module defines *how* an engine is invoked and *nothing* about what it
decides. It holds no semantic logic: no token classification, no ordering, no
verdict derivation. Engines that implement the protocol live under
``wexp_ref/core01/engines/`` and are each classified

    ASSURANCE-CRITICAL — MUST REMAIN INDEPENDENT

They must not import each other, and they must not share a semantic library.
``check_independence`` enforces the import half of that rule mechanically, so
the firewall is a test result rather than a convention.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .candidate import Candidate, Vector


@dataclass(frozen=True)
class EngineResult:
    """One engine's observation for one vector."""

    vector_id: str
    actual: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"vector_id": self.vector_id, "actual": self.actual}


@runtime_checkable
class Engine(Protocol):
    """A semantic engine.

    ``engine_id``      stable identifier recorded in evidence.
    ``implementation`` human-readable description of the implementation lineage.
    ``evaluate``       compute the observed result for one vector, using only
                       the candidate profile and the vector input. An engine
                       must never read the vector's ``expected`` payload.
    """

    engine_id: str
    implementation: str

    def evaluate(self, vector: Vector, candidate: Candidate) -> dict[str, Any]:
        ...


#: Engines are addressed by dotted module path so that no shared registry file
#: has to import both of them, which would create a single point of failure.
ENGINE_MODULES: dict[str, str] = {
    "independent": "wexp_ref.core01.engines.independent.engine",
    "reference": "wexp_ref.core01.engines.reference.engine",
}


def load_engine(name: str) -> Engine:
    if name not in ENGINE_MODULES:
        raise KeyError(f"unknown engine: {name!r}")
    module = importlib.import_module(ENGINE_MODULES[name])
    engine = getattr(module, "ENGINE", None)
    if engine is None:
        raise KeyError(f"{ENGINE_MODULES[name]} does not expose ENGINE")
    if not isinstance(engine, Engine):
        raise TypeError(f"{ENGINE_MODULES[name]}.ENGINE does not satisfy the Engine protocol")
    return engine


def check_independence() -> list[str]:
    """Return every violation of the independence firewall.

    A violation is one engine package importing another engine package, or an
    engine importing a module that is not classified SHARED-INFRASTRUCTURE-SAFE.
    """

    import ast
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    engines_root = Path(__file__).resolve().parents[1] / "engines"
    # The shared-infrastructure package and its classified modules. Every module
    # listed here carries a SHARED-INFRASTRUCTURE-SAFE classification in its
    # docstring; adding one without that classification is a review failure.
    allowed_shared = {
        "wexp_ref.core01.harness",
        "wexp_ref.core01.harness.canonical",
        "wexp_ref.core01.harness.candidate",
        "wexp_ref.core01.harness.schema",
        "wexp_ref.core01.harness.evidence",
        "wexp_ref.core01.harness.engine",
    }
    violations: list[str] = []
    packages = [path for path in sorted(engines_root.iterdir()) if path.is_dir()]
    for package in packages:
        others = {other.name for other in packages if other.name != package.name}
        for source in sorted(package.rglob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    # ``from a.b import c``: always check the module. Check
                    # ``a.b.c`` as well, but only when it is itself a module on
                    # disk, so importing a *symbol* from an allowed module is
                    # not mistaken for importing an unclassified module.
                    names = [node.module]
                    for alias in node.names:
                        dotted = f"{node.module}.{alias.name}"
                        if (repo_root / Path(*dotted.split("."))).with_suffix(".py").is_file():
                            names.append(dotted)
                for name in names:
                    for other in others:
                        if f"wexp_ref.core01.engines.{other}" in name:
                            violations.append(
                                f"{source.relative_to(engines_root)}: imports engine {other!r}"
                            )
                    if name.startswith("wexp_ref.core01.") and name not in allowed_shared:
                        if not name.startswith(f"wexp_ref.core01.engines.{package.name}"):
                            violations.append(
                                f"{source.relative_to(engines_root)}: imports non-shared module {name!r}"
                            )
    return violations
