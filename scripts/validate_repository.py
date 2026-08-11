#!/usr/bin/env python3
"""Run the dependency-free local public-tooling validation suite."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    commands = [
        [sys.executable, "-m", "compileall", "-q", "src", "tests", "scripts"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [sys.executable, "scripts/validate_vectors_lock.py"],
        [sys.executable, "scripts/check_action_pins.py"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=root, env=environment, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
