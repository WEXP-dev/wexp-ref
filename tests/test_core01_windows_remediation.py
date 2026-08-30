from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from wexp_ref.core01.harness import environment
from wexp_ref.core01.tools import compare_environments, matrix_policy, new_candidate

from scripts.verify_core01_corpus import REQUIRED_CANDIDATES, validate_lock, verify


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config" / "wexp-vectors-core01.lock.json"
README = ROOT / "README.md"
TAMPER_SCRIPT = ROOT / "scripts" / "windows_tamper_demo.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "core01-qualification.yml"


class WindowsMatrixTests(unittest.TestCase):
    def test_windows_x64_is_a_required_native_environment(self) -> None:
        descriptor = environment.load_descriptor("windows")
        self.assertEqual(descriptor["kind"], "native")
        self.assertEqual(descriptor["require"], {"machine": "AMD64", "system": "Windows"})
        self.assertIn(
            {"environment": "windows", "runner": "windows-latest"},
            matrix_policy.FULL_MATRIX,
        )
        self.assertEqual(
            compare_environments.REQUIRED_FULL_MATRIX,
            {entry["environment"] for entry in matrix_policy.FULL_MATRIX},
        )

    def test_lock_binds_every_published_set_and_manifest(self) -> None:
        lock = json.loads(LOCK.read_bytes())
        self.assertEqual(lock["lock_version"], 3)
        entries = {entry["candidate_id"]: entry for entry in lock["vector_sets"]}
        self.assertEqual(set(entries), REQUIRED_CANDIDATES)
        self.assertEqual(
            entries["WEXP-CORE-01-VECTORS-001"]["vector_set_sha256"],
            "e315b6055148dbf05c6104c57feb991104b1ae6a47741a99cde5eb50d1900daf",
        )
        self.assertEqual(
            entries["WEXP-CORE-01-VECTORS-003"]["vector_set_sha256"],
            "338b14cffdb846ca2aec4574ad9e52dd3615e15c8de7861d922e4323989440cd",
        )
        self.assertEqual(
            entries["WEXP-CORE-01-VECTORS-002"]["vector_set_sha256"],
            "8b2dfd5ac6f983201f8869c331b58936e3378f382a3a989b9a63c8d85791facf",
        )
        self.assertEqual(lock["manifest_path"], entries["WEXP-CORE-01-VECTORS-001"]["manifest_path"])
        self.assertEqual(
            lock["manifest_sha256"],
            entries["WEXP-CORE-01-VECTORS-001"]["manifest_sha256"],
        )

    def test_workflow_exercises_windows_powershell_and_both_sets(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for required in (
            "runs-on: ${{ matrix.runner }}",
            "shell: powershell",
            "$PSVersionTable.PSVersion.Major -ne 5",
            "git config --global core.autocrlf true",
            "WEXP-CORE-01-VECTORS-001 WEXP-CORE-01-VECTORS-002",
            "windows=evidence/core01-qualification-windows/",
            "scripts\\windows_tamper_demo.ps1",
        ):
            with self.subTest(required=required):
                self.assertIn(required, workflow)


class CorpusVerifierTests(unittest.TestCase):
    def test_verifier_rejects_loose_or_platform_ambiguous_lock_metadata(self) -> None:
        checked_in = json.loads(LOCK.read_bytes())
        cases = []

        unknown = json.loads(json.dumps(checked_in))
        unknown["unexpected"] = True
        cases.append(unknown)

        released = json.loads(json.dumps(checked_in))
        released["package_status"] = "released"
        cases.append(released)

        backslash_path = json.loads(json.dumps(checked_in))
        backslash_path["vector_sets"][0]["manifest_path"] = "manifests\\set.json"
        cases.append(backslash_path)

        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_lock(value)

    def test_verifier_checks_the_commit_and_every_set_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            temporary = Path(raw)
            repository = temporary / "vectors"
            repository.mkdir()
            entries = []
            bound_paths = []
            for number, candidate_id in enumerate(sorted(REQUIRED_CANDIDATES), start=1):
                candidate = repository / "vectors" / candidate_id
                candidate.mkdir(parents=True)
                bound = candidate / "descriptor.json"
                bound.write_bytes(f"candidate {number}\n".encode())
                bound_paths.append(bound)
                manifest_path = Path("manifests") / f"set-{number}.json"
                manifest = repository / manifest_path
                manifest.parent.mkdir(exist_ok=True)
                vector_set_sha256 = f"{number:064x}"
                manifest.write_text(
                    json.dumps(
                        {
                            "vector_set_id": candidate_id,
                            "vector_set_sha256": vector_set_sha256,
                            "schemas": {},
                            "artifacts": [
                                {
                                    "path": bound.relative_to(repository).as_posix(),
                                    "sha256": hashlib.sha256(bound.read_bytes()).hexdigest(),
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                entries.append(
                    {
                        "candidate_id": candidate_id,
                        "manifest_path": manifest_path.as_posix(),
                        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        "vector_set_sha256": vector_set_sha256,
                    }
                )

            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "test@example.invalid"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "WEXP test"],
                check=True,
            )
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-q", "-m", "fixture"],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            lock_path = temporary / "lock.json"
            set_001 = entries[0]
            lock_path.write_text(
                json.dumps(
                    {
                        "lock_version": 3,
                        "dependency": "wexp-vectors",
                        "repository": "WEXP-dev/wexp-vectors",
                        "status": "pinned",
                        "package_status": "candidate",
                        "commit": commit,
                        "manifest_path": set_001["manifest_path"],
                        "manifest_sha256": set_001["manifest_sha256"],
                        "vector_sets": entries,
                    }
                ),
                encoding="utf-8",
            )

            manifest_paths = {
                repository / entry["manifest_path"]: 0 for entry in entries
            }
            original_read_bytes = Path.read_bytes

            def tracked_read_bytes(path: Path) -> bytes:
                if path in manifest_paths:
                    manifest_paths[path] += 1
                return original_read_bytes(path)

            with mock.patch.object(Path, "read_bytes", tracked_read_bytes):
                results = verify(lock_path, repository)
            self.assertEqual(len(results), 1 + len(REQUIRED_CANDIDATES))
            self.assertIn(commit, results[0])
            self.assertEqual(set(manifest_paths.values()), {1})

            bound_paths[1].write_bytes(b"changed after checkout\n")
            with self.assertRaisesRegex(ValueError, "artifact digest mismatch"):
                verify(lock_path, repository)


class CandidateDirectoryDocumentationTests(unittest.TestCase):
    def test_documented_output_parent_matches_the_enforced_basename(self) -> None:
        documentation = README.read_text(encoding="utf-8")
        self.assertIn("`--output` names the **parent** directory", documentation)
        self.assertIn("directory basename must\nequal the descriptor's `candidate_id`", documentation)

        seed = ROOT / "src" / "wexp_ref" / "core01" / "seeds" / "synthetic-a.json"
        with tempfile.TemporaryDirectory() as raw:
            output_parent = Path(raw) / "candidates"
            candidate = new_candidate.build(seed, output_parent)
            self.assertEqual(candidate.parent, output_parent)
            self.assertEqual(candidate.name, "WEXP-SYNTH-CANDIDATE-A")


class PowerShellTamperRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.powershell = (
            shutil.which("powershell.exe")
            or shutil.which("powershell")
            or shutil.which("pwsh")
        )

    def invoke(self, candidate: Path, relative: str, index: int) -> subprocess.CompletedProcess[str]:
        if self.powershell is None:
            self.skipTest("PowerShell is unavailable; the windows-latest job runs this test")
        return subprocess.run(
            [
                self.powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(TAMPER_SCRIPT),
                "-Candidate",
                str(candidate),
                "-RelativeFile",
                relative,
                "-Index",
                str(index),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_script_is_fail_closed_and_reports_success_only_after_write(self) -> None:
        source = TAMPER_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('$ErrorActionPreference = "Stop"', source)
        self.assertIn("$WorkingDirectory = (Get-Location).Path", source)
        self.assertIn("Test-Path -LiteralPath $TargetPath -PathType Leaf", source)
        self.assertIn("$Index -lt 0 -or $Index -ge $Bytes.Length", source)
        self.assertGreater(source.index("Write-Output"), source.index("WriteAllBytes"))

    def test_script_mutates_exactly_the_requested_byte(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            candidate = Path(raw) / "CANDIDATE"
            target = candidate / "vectors" / "case.json"
            target.parent.mkdir(parents=True)
            before = b'{"value":"unchanged"}\n'
            target.write_bytes(before)

            result = self.invoke(candidate, "vectors/case.json", 4)
            self.assertEqual(result.returncode, 0, result.stderr)
            after = target.read_bytes()
            self.assertEqual(len(after), len(before))
            self.assertEqual(
                [index for index, values in enumerate(zip(before, after)) if values[0] != values[1]],
                [4],
            )
            self.assertIn("MUTATION COMPLETE", result.stdout)

    def test_script_returns_nonzero_without_writing_for_an_invalid_index(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            candidate = Path(raw) / "CANDIDATE"
            target = candidate / "vectors" / "case.json"
            target.parent.mkdir(parents=True)
            before = b"abc"
            target.write_bytes(before)

            result = self.invoke(candidate, "vectors/case.json", len(before))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), before)
            self.assertNotIn("MUTATION COMPLETE", result.stdout)


if __name__ == "__main__":
    unittest.main()
