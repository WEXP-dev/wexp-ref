#!/usr/bin/env python3
"""Validate the cross-repository vector lock without fetching anything."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from wexp_ref.locks import validate_vectors_lock


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config/wexp-vectors.lock.json")
    with path.open("r", encoding="utf-8") as stream:
        result = validate_vectors_lock(json.load(stream))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("VALID_") else 2


if __name__ == "__main__":
    raise SystemExit(main())

