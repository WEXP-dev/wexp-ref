#!/usr/bin/env python3
"""Fail when a workflow uses an external action without an exact commit SHA."""

from __future__ import annotations

import re
import sys
from pathlib import Path

USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
PIN = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".github/workflows")
    failures: list[str] = []
    for path in sorted(root.glob("*.y*ml")):
        for use in USES.findall(path.read_text(encoding="utf-8")):
            if use.startswith("./"):
                continue
            if PIN.fullmatch(use) is None:
                failures.append(f"{path}: action is not pinned to 40 hex: {use}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 2
    print(f"PASS: exact action pins in {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

