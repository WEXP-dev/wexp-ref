"""Command-line entry point for WEXP reference tooling."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from wexp_ref import __version__
from wexp_ref.core00 import Core00InputError, PackageError, evaluate, run_package
from wexp_ref.locks import validate_vectors_lock
from wexp_ref.runner import PlanError, run_plan


class JsonInputError(ValueError):
    """A JSON object contains duplicate member names."""


def _read_json(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise JsonInputError(f"duplicate JSON member {key!r} in {path}")
            value[key] = item
        return value

    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=reject_duplicates)


def _write_json(value: Any, path: Path | None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path is None:
        sys.stdout.write(rendered)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _xml(args: argparse.Namespace) -> int:
    try:
        ET.parse(args.input)
    except (ET.ParseError, OSError) as exc:
        result = {
            "status": "INVALID",
            "artifact": str(args.input),
            "diagnostic": str(exc),
            "non_claims": ["XML parsing does not establish IETF or specification acceptance."],
        }
        _write_json(result, args.output)
        return 2
    result = {
        "status": "VALID",
        "artifact": str(args.input),
        "sha256": _sha256(args.input),
        "parser": "python.xml.etree.ElementTree",
        "non_claims": [
            "XML parsing does not establish IETF or specification acceptance.",
            "No WEXP claim was evaluated for semantic support.",
        ],
    }
    _write_json(result, args.output)
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        record = run_plan(_read_json(args.plan), args.workspace)
    except (PlanError, JsonInputError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"plan error: {exc}\n")
        return 2
    _write_json(record, args.record)
    return int(record["overall_exit_status"])


def _lock(args: argparse.Namespace) -> int:
    try:
        result = validate_vectors_lock(_read_json(args.input))
    except (JsonInputError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"lock error: {exc}\n")
        return 2
    _write_json(result, args.output)
    return 0 if result["status"].startswith("VALID_") else 2


def _core00_evaluate(args: argparse.Namespace) -> int:
    try:
        result = evaluate(_read_json(args.input))
    except (Core00InputError, JsonInputError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Core -00 input error: {exc}\n")
        return 2
    _write_json(result, args.output)
    return 0


def _core00_run_vectors(args: argparse.Namespace) -> int:
    try:
        result = run_package(args.package, _read_json(args.lock))
    except (PackageError, JsonInputError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Core -00 package error: {exc}\n")
        return 2
    _write_json(result, args.output)
    return 0 if result["summary"]["status"] == "PASS" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wexp-ref")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    xml = commands.add_parser("validate-xml", help="perform a non-normative XML parse check")
    xml.add_argument("input", type=Path)
    xml.add_argument("--output", "-o", type=Path)
    xml.set_defaults(handler=_xml)

    runner = commands.add_parser("run", help="run an argv-only declarative plan")
    runner.add_argument("plan", type=Path)
    runner.add_argument("--workspace", type=Path, default=Path.cwd())
    runner.add_argument(
        "--record", type=Path, default=Path("WEXP-REF-RUNNER-OBSERVATION.json")
    )
    runner.set_defaults(handler=_run)

    lock = commands.add_parser("validate-lock", help="check the wexp-vectors dependency lock")
    lock.add_argument(
        "input", type=Path, nargs="?", default=Path("config/wexp-vectors.lock.json")
    )
    lock.add_argument("--output", "-o", type=Path)
    lock.set_defaults(handler=_lock)

    core00 = commands.add_parser(
        "core00-evaluate",
        help="evaluate one input in the non-normative Core -00 slice harness",
    )
    core00.add_argument("input", type=Path)
    core00.add_argument("--output", "-o", type=Path)
    core00.set_defaults(handler=_core00_evaluate)

    core00_package = commands.add_parser(
        "core00-run-vectors",
        help="run the exact pinned Core -00 candidate vector package",
    )
    core00_package.add_argument("package", type=Path)
    core00_package.add_argument(
        "--lock", type=Path, default=Path("config/wexp-vectors.lock.json")
    )
    core00_package.add_argument("--output", "-o", type=Path)
    core00_package.set_defaults(handler=_core00_run_vectors)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
