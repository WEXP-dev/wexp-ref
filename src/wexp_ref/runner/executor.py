"""Execute a declared argv-only plan and emit a generic runner observation."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wexp_ref import __version__

RECORD_KIND = "wexp-ref-runner-observation"
REQUIRED_NON_CLAIMS = (
    "This record does not establish IETF acceptance.",
    "This record does not establish independent implementation conformance.",
    "This record does not establish complete correctness of WEXP.",
    "This record is not itself a standardized WEXP protocol record.",
)
_SHA256 = __import__("re").compile(r"^[0-9a-f]{64}$")


class PlanError(ValueError):
    """The declarative plan cannot be interpreted safely."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(workspace: Path, relative: Any, field: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise PlanError(f"{field} must be a non-empty relative path")
    resolved = (workspace / relative).resolve(strict=False)
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise PlanError(f"{field} escapes the workspace") from exc
    return resolved


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PlanError(f"{field} must be an array of strings")
    return value


def _mapping_list(value: Any, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise PlanError(f"{field} must be an array of objects")
    return value


def _validate_identity(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PlanError(f"{field} must be an object")
    if not isinstance(value.get("repository"), str) or not value["repository"]:
        raise PlanError(f"{field}.repository must be a non-empty string")
    revision = value.get("revision")
    status = value.get("revision_status", "pinned")
    if status == "pinned":
        if not isinstance(revision, str) or not revision:
            raise PlanError(f"{field}.revision is required when revision_status is pinned")
        if revision.lower() in {"head", "main", "master", "latest"}:
            raise PlanError(f"{field}.revision must not be floating")
    elif status not in {"working-tree", "blocked"}:
        raise PlanError(f"{field}.revision_status is invalid")
    return dict(value)


def validate_plan(plan: Any, workspace: Path) -> dict[str, Any]:
    """Validate and normalize a runner plan (not a protocol wire schema)."""

    if not isinstance(plan, Mapping):
        raise PlanError("plan must be an object")
    required = {
        "plan_version",
        "execution_id",
        "subject",
        "source",
        "dependencies",
        "external_dependencies",
        "inputs",
        "procedure",
        "outputs",
        "claims",
        "non_claims",
    }
    if set(plan) != required:
        raise PlanError(
            f"plan members differ (missing={sorted(required - set(plan))}, "
            f"extra={sorted(set(plan) - required)})"
        )
    if plan["plan_version"] != 1:
        raise PlanError("only plan_version 1 is supported")
    for field in ("execution_id", "subject"):
        if not isinstance(plan[field], str) or not plan[field]:
            raise PlanError(f"{field} must be a non-empty string")

    source = _validate_identity(plan["source"], "source")
    dependencies = [
        _validate_identity(item, f"dependencies[{index}]")
        for index, item in enumerate(_mapping_list(plan["dependencies"], "dependencies"))
    ]
    external_dependencies = [
        _validate_identity(item, f"external_dependencies[{index}]")
        for index, item in enumerate(
            _mapping_list(plan["external_dependencies"], "external_dependencies")
        )
    ]

    inputs: list[dict[str, Any]] = []
    seen_inputs: set[str] = set()
    for index, raw in enumerate(_mapping_list(plan["inputs"], "inputs")):
        if not {"path"} <= set(raw) <= {"path", "sha256"}:
            raise PlanError(f"inputs[{index}] must contain path and optional sha256")
        path = raw["path"]
        _safe_path(workspace, path, f"inputs[{index}].path")
        if path in seen_inputs:
            raise PlanError(f"duplicate declared input {path}")
        seen_inputs.add(path)
        expected = raw.get("sha256")
        if expected is not None and (
            not isinstance(expected, str) or _SHA256.fullmatch(expected) is None
        ):
            raise PlanError(f"inputs[{index}].sha256 must be lowercase SHA-256 hex")
        inputs.append(dict(raw))

    procedure: list[dict[str, Any]] = []
    seen_steps: set[str] = set()
    for index, raw in enumerate(_mapping_list(plan["procedure"], "procedure")):
        allowed = {"name", "argv", "cwd", "timeout_seconds", "continue_on_error"}
        if not {"name", "argv"} <= set(raw) <= allowed:
            raise PlanError(f"procedure[{index}] has an unsupported shape")
        name = raw["name"]
        if not isinstance(name, str) or not name or name in seen_steps:
            raise PlanError(f"procedure[{index}].name must be unique and non-empty")
        seen_steps.add(name)
        argv = _string_list(raw["argv"], f"procedure[{index}].argv")
        if not argv or any(not item for item in argv):
            raise PlanError(f"procedure[{index}].argv must contain non-empty strings")
        cwd = raw.get("cwd", ".")
        _safe_path(workspace, cwd, f"procedure[{index}].cwd")
        timeout = raw.get("timeout_seconds", 300)
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise PlanError(f"procedure[{index}].timeout_seconds must be 1..3600")
        continuation = raw.get("continue_on_error", False)
        if type(continuation) is not bool:
            raise PlanError(f"procedure[{index}].continue_on_error must be boolean")
        procedure.append(
            {
                "name": name,
                "argv": argv,
                "cwd": cwd,
                "timeout_seconds": timeout,
                "continue_on_error": continuation,
            }
        )

    outputs: list[dict[str, Any]] = []
    seen_outputs: set[str] = set()
    for index, raw in enumerate(_mapping_list(plan["outputs"], "outputs")):
        if not {"artifact"} <= set(raw) <= {"artifact", "required"}:
            raise PlanError(f"outputs[{index}] must contain artifact and optional required")
        artifact = raw["artifact"]
        _safe_path(workspace, artifact, f"outputs[{index}].artifact")
        if artifact in seen_outputs:
            raise PlanError(f"duplicate declared output {artifact}")
        seen_outputs.add(artifact)
        required_output = raw.get("required", True)
        if type(required_output) is not bool:
            raise PlanError(f"outputs[{index}].required must be boolean")
        outputs.append({"artifact": artifact, "required": required_output})

    return {
        "plan_version": 1,
        "execution_id": plan["execution_id"],
        "subject": plan["subject"],
        "source": source,
        "dependencies": dependencies,
        "external_dependencies": external_dependencies,
        "inputs": inputs,
        "procedure": procedure,
        "outputs": outputs,
        "claims": _string_list(plan["claims"], "claims"),
        "non_claims": _string_list(plan["non_claims"], "non_claims"),
    }


def _argv_with_placeholders(argv: list[str], workspace: Path) -> list[str]:
    replacements = {"{python}": sys.executable, "{workspace}": str(workspace)}
    return [replacements.get(item, item) for item in argv]


def run_plan(plan: Any, workspace: str | Path) -> dict[str, Any]:
    """Run a validated plan with ``shell=False`` and return a record object."""

    root = Path(workspace).resolve(strict=True)
    if not root.is_dir():
        raise PlanError("workspace must be a directory")
    normalized = validate_plan(plan, root)
    started_at = _now()

    input_hashes: list[dict[str, Any]] = []
    preflight_failed = False
    for item in normalized["inputs"]:
        path = _safe_path(root, item["path"], "input.path")
        observation: dict[str, Any] = {"path": item["path"]}
        if not path.is_file():
            observation.update({"status": "MISSING", "sha256": None})
            preflight_failed = True
        else:
            actual = _sha256(path)
            expected = item.get("sha256")
            status = "MATCH" if expected is None or expected == actual else "MISMATCH"
            observation.update(
                {"status": status, "sha256": actual, "size_bytes": path.stat().st_size}
            )
            if expected is not None:
                observation["expected_sha256"] = expected
            preflight_failed |= status == "MISMATCH"
        input_hashes.append(observation)

    observations: list[dict[str, Any]] = []
    exit_statuses: dict[str, int | None] = {}
    stop = preflight_failed
    for step in normalized["procedure"]:
        if stop:
            observations.append(
                {
                    "step": step["name"],
                    "argv": _argv_with_placeholders(step["argv"], root),
                    "cwd": step["cwd"],
                    "status": "NOT_RUN",
                    "reason": "input preflight or earlier required step failed",
                }
            )
            exit_statuses[step["name"]] = None
            continue
        argv = _argv_with_placeholders(step["argv"], root)
        cwd = _safe_path(root, step["cwd"], "step.cwd")
        step_started = _now()
        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=step["timeout_seconds"],
                check=False,
                env=os.environ.copy(),
            )
            code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            status = "COMPLETED"
        except subprocess.TimeoutExpired as exc:
            code = 124
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            status = "TIMED_OUT"
        except OSError as exc:
            code = 127
            stdout = b""
            stderr = str(exc).encode("utf-8", errors="replace")
            status = "EXECUTION_ERROR"
        observation = {
            "step": step["name"],
            "argv": argv,
            "cwd": step["cwd"],
            "shell": False,
            "status": status,
            "started_at": step_started,
            "finished_at": _now(),
            "exit_status": code,
            "stdout": {
                "size_bytes": len(stdout),
                "sha256": hashlib.sha256(stdout).hexdigest(),
            },
            "stderr": {
                "size_bytes": len(stderr),
                "sha256": hashlib.sha256(stderr).hexdigest(),
            },
        }
        observations.append(observation)
        exit_statuses[step["name"]] = code
        if code != 0 and not step["continue_on_error"]:
            stop = True

    outputs: list[dict[str, Any]] = []
    output_failed = False
    for declaration in normalized["outputs"]:
        path = _safe_path(root, declaration["artifact"], "output.artifact")
        if path.is_file():
            outputs.append(
                {
                    "artifact": declaration["artifact"],
                    "status": "OBSERVED",
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
        else:
            outputs.append(
                {
                    "artifact": declaration["artifact"],
                    "status": "MISSING",
                    "sha256": None,
                }
            )
            output_failed |= declaration["required"]

    step_failed = any(code not in (0, None) for code in exit_statuses.values())
    overall = 1 if preflight_failed or step_failed or output_failed else 0
    source = dict(normalized["source"])
    source["input_hashes"] = input_hashes
    return {
        "record_kind": RECORD_KIND,
        "record_version": 1,
        "execution_id": normalized["execution_id"],
        "subject": normalized["subject"],
        "source": source,
        "dependencies": normalized["dependencies"],
        "external_dependencies": normalized["external_dependencies"],
        "executor": {
            "environment": {
                "platform": platform.platform(),
                "python_implementation": platform.python_implementation(),
                "python_version": platform.python_version(),
            },
            "runner": "wexp-ref generic runner",
            "runner_version": __version__,
            "shell_execution": False,
        },
        "procedure": normalized["procedure"],
        "observations": observations,
        "exit_statuses": exit_statuses,
        "outputs": outputs,
        "claims": normalized["claims"],
        "non_claims": list(dict.fromkeys([*normalized["non_claims"], *REQUIRED_NON_CLAIMS])),
        "timestamps": {"started_at": started_at, "finished_at": _now()},
        "overall_exit_status": overall,
    }
