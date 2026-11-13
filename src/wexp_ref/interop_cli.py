"""CLI adapter for the external interoperability evidence harness."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from wexp_ref.interop import InteropError, load_json, prepare_commitment, verify_reveal


def _write(value: Any, path: Path | None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path is None:
        sys.stdout.write(rendered)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")


def _prepare(args: argparse.Namespace) -> int:
    try:
        record = prepare_commitment(args.source_lock, args.fixtures, args.reading)
    except (InteropError, OSError) as exc:
        sys.stderr.write(f"interop error: {exc}\n")
        return 2
    _write(record, args.output)
    return 0


def _verify(args: argparse.Namespace) -> int:
    try:
        record = verify_reveal(load_json(args.commitment), args.source_lock, args.fixtures, args.reading, args.source_root)
    except (InteropError, OSError) as exc:
        sys.stderr.write(f"interop error: {exc}\n")
        return 2
    _write(record, args.output)
    return 0 if record["status"] == "VERIFIED" else 1


def add_interop_parser(commands: argparse._SubParsersAction) -> None:
    interop = commands.add_parser("interop", help="bind and verify external interop evidence without inferring protocol semantics")
    sub = interop.add_subparsers(dest="interop_command", required=True)

    prepare = sub.add_parser("prepare", help="commit to exact source-lock, fixture, and reading bytes")
    prepare.add_argument("--source-lock", type=Path, required=True)
    prepare.add_argument("--fixtures", type=Path, required=True)
    prepare.add_argument("--reading", type=Path, required=True)
    prepare.add_argument("--output", "-o", type=Path)
    prepare.set_defaults(handler=_prepare)

    verify = sub.add_parser("verify", help="verify revealed bytes and selected source materials")
    verify.add_argument("--commitment", type=Path, required=True)
    verify.add_argument("--source-lock", type=Path, required=True)
    verify.add_argument("--source-root", type=Path, required=True)
    verify.add_argument("--fixtures", type=Path, required=True)
    verify.add_argument("--reading", type=Path, required=True)
    verify.add_argument("--output", "-o", type=Path)
    verify.set_defaults(handler=_verify)
