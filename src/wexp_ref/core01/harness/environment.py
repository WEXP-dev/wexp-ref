"""Qualification environments as declared data.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

An environment is a descriptor, not a code path. The same generic entrypoint
runs everywhere; what differs between portable, container and native runs is
declared in ``wexp_ref/core01/environments/*.json`` and observed here.

Probes follow the same constrained-declarative rule as the verdict table: the
descriptor may only *name* probes from a fixed registry that this module
implements. There is no expression language, and an unknown probe name is a
failure rather than a silently skipped hint.

The distinction this module exists to record:

* **portable observations** are expected to be identical in every environment.
  Engine payload digests are the load-bearing example: if they ever differ
  between environments, the qualification is not portable and that is a finding,
  not a footnote.
* **environment observations** are expected to differ. They are recorded so a
  reader can see exactly what was environment-specific, rather than inferring it.
"""

from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import canonical, schema as schema_module

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"
ENVIRONMENT_DIR = Path(__file__).resolve().parents[1] / "environments"
SUPPORTED_ENVIRONMENT_VERSIONS = frozenset({1})


class EnvironmentError_(ValueError):
    """Raised when an environment descriptor is unusable or unsatisfied."""


def _probe_python_version() -> str:
    return platform.python_version()


def _probe_python_implementation() -> str:
    return platform.python_implementation()


def _probe_system() -> str:
    return platform.system()


def _probe_machine() -> str:
    return platform.machine()


def _probe_byteorder() -> str:
    return sys.byteorder


def _probe_filesystem_case_sensitive() -> bool:
    """Genuinely environment-varying: Darwin defaults to case-insensitive."""

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "CaseProbe").write_text("x", encoding="utf-8")
        return not (root / "caseprobe").exists()


def _probe_temp_path_is_symlinked() -> bool:
    """Darwin resolves /tmp through /private; most Linux images do not."""

    with tempfile.TemporaryDirectory() as raw:
        return Path(raw).resolve() != Path(raw)


def _probe_path_separator() -> str:
    return os.sep


def _probe_max_filename_bytes() -> int:
    return int(os.pathconf("/", "PC_NAME_MAX")) if hasattr(os, "pathconf") else -1


#: The only probes a descriptor may name. Adding one is a reviewed code change.
PROBES: dict[str, Callable[[], Any]] = {
    "python_version": _probe_python_version,
    "python_implementation": _probe_python_implementation,
    "system": _probe_system,
    "machine": _probe_machine,
    "byteorder": _probe_byteorder,
    "filesystem_case_sensitive": _probe_filesystem_case_sensitive,
    "temp_path_is_symlinked": _probe_temp_path_is_symlinked,
    "path_separator": _probe_path_separator,
    "max_filename_bytes": _probe_max_filename_bytes,
}


def load_descriptor(reference: str | Path) -> dict[str, Any]:
    """Load an environment descriptor by label or by path."""

    path = Path(reference)
    if not path.suffix:
        path = ENVIRONMENT_DIR / f"{reference}.json"
    if not path.is_file():
        raise EnvironmentError_(f"unknown environment: {reference}")

    document = canonical.load_json(path)
    schema = canonical.load_json(SCHEMA_DIR / "environment.schema.json")
    try:
        schema_module.validate(document, schema, location=path.name)
    except (schema_module.ValidationError, schema_module.SchemaError) as exc:
        raise EnvironmentError_(f"{path.name}: {exc}") from exc
    if document["environment_version"] not in SUPPORTED_ENVIRONMENT_VERSIONS:
        raise EnvironmentError_(f"unsupported environment_version: {document['environment_version']}")

    unknown = sorted(set(document["probes"]) - set(PROBES))
    if unknown:
        raise EnvironmentError_(f"{path.name}: unknown probe(s): {', '.join(unknown)}")
    return document


def observe(descriptor: dict[str, Any]) -> dict[str, Any]:
    """Run the declared probes and check the declared requirements."""

    # Validated again here, not only in the loader: a descriptor can reach this
    # function without having been loaded from disk, and an unknown probe must
    # fail closed rather than raise a bare KeyError.
    unknown = sorted(set(descriptor["probes"]) - set(PROBES))
    if unknown:
        raise EnvironmentError_(
            f"{descriptor.get('label', '<unlabelled>')}: unknown probe(s): {', '.join(unknown)}"
        )
    observations = {name: PROBES[name]() for name in sorted(descriptor["probes"])}

    unmet: list[str] = []
    for name, expected in (descriptor.get("require") or {}).items():
        if name not in PROBES:
            raise EnvironmentError_(f"require names an unknown probe: {name}")
        actual = observations.get(name, PROBES[name]())
        observations.setdefault(name, actual)
        if actual != expected:
            unmet.append(f"{name}: required {expected!r}, observed {actual!r}")
    if unmet:
        raise EnvironmentError_(
            f"{descriptor['label']}: environment requirements not met: " + "; ".join(unmet)
        )

    return {
        "label": descriptor["label"],
        "kind": descriptor["kind"],
        "observations": observations,
        "portable_claim": descriptor["portable_claim"],
        "environment_specific": sorted(descriptor.get("environment_specific", [])),
    }
