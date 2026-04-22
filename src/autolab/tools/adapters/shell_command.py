"""``shell_command`` — run any command on a Resource, capture stdout/exit/files.

The first and most primitive Capability. Lets a user wire a scientific
tool into the lab without writing any Python adapter code — they name
the command, declare what output files to collect, and autolab handles
staging, execution, output capture, and provenance.

Inputs:
    command: str
        The shell command to run.
    cwd: str | None
        Working directory inside the workdir. Defaults to the workdir
        itself. Absolute paths are honoured (useful for running from an
        existing repo checkout).
    env: dict[str, str] | None
        Environment variables to set for this invocation only.
    timeout_seconds: float | None
        Optional timeout; command is killed if exceeded.
    declared_outputs: list[str] | None
        Relative paths (from ``cwd``) of files the command produces.
        These are fetched back to the local ledger after the run.

Outputs:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    artefacts: dict[str, str]
        Declared-output-name → local path where the file was staged.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from autolab.backends import LocalBackend, ResourceBackend
from autolab.backends.base import RemoteWorkdir
from autolab.models import OperationResult
from autolab.operations.base import Operation, OperationContext


class ShellCommand(Operation):
    """Run a command on the Resource's backend, via a framework-owned workdir."""

    capability = "shell_command"
    resource_kind = None  # runs on any Resource (backend provides execution)
    module = "autolab.shell_command.v1"
    typical_duration = 2.0

    #: Backend override for tests / explicit Resource wiring. When ``None``,
    #: the operation uses the Resource's registered backend; fallback is
    #: a LocalBackend rooted at ``<lab-root>/.autolab-work``.
    backend_override: ResourceBackend | None = None

    async def run(  # type: ignore[override]
        self,
        inputs: dict[str, Any],
        context: OperationContext | None = None,
    ) -> OperationResult:
        command = inputs.get("command")
        if not command or not isinstance(command, str):
            return OperationResult(
                status="failed",
                outputs={"reason": "shell_command requires `command` (string)"},
            )

        cwd = inputs.get("cwd")
        env = inputs.get("env") or {}
        timeout = inputs.get("timeout_seconds")
        declared = list(inputs.get("declared_outputs") or [])

        record_id = context.record_id if context else _fallback_record_id(inputs)
        record_hash = record_id.split("-", 1)[-1][:16]

        backend = self._pick_backend(context)
        await backend.connect()
        try:
            workdir = RemoteWorkdir(
                record_hash=record_hash,
                backend=backend,
                remote_root=_remote_root_for(backend),
                local_staging=_local_staging_for(record_hash),
                declared_outputs=declared,
            )

            await workdir.write_inputs(inputs)
            run_cwd = cwd or workdir.remote_path
            result = await workdir.run(command, env=env, timeout_seconds=timeout)

            outputs_payload = {
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_seconds": result.duration_seconds,
            }

            # Write an outputs.json for the adapter-side convention.
            await backend.put_text(
                f"{workdir.remote_path}/outputs.json",
                json.dumps(outputs_payload, indent=2),
            )

            # Collect declared output files, if any.
            artefacts: dict[str, str] = {}
            if declared:
                try:
                    fetched = await workdir.fetch_artefacts()
                    artefacts = {k: str(v) for k, v in fetched.items()}
                except Exception as exc:  # noqa: BLE001
                    outputs_payload["artefact_error"] = str(exc)

            if artefacts:
                outputs_payload["artefacts"] = artefacts

            status = "completed" if result.ok else "failed"
            return OperationResult(status=status, outputs=outputs_payload)
        finally:
            await backend.close()

    def _pick_backend(self, context: OperationContext | None) -> ResourceBackend:
        if self.backend_override is not None:
            return self.backend_override
        # Resource side-channel: if the context's resource declares a backend,
        # wire it up. For now we fall back to LocalBackend for hackathon demos.
        return LocalBackend()


def _fallback_record_id(inputs: dict[str, Any]) -> str:
    # Deterministic when no context is provided (e.g. unit tests).
    blob = json.dumps(inputs, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:12]
    return f"rec-{digest}"


def _remote_root_for(backend: ResourceBackend) -> str:
    if isinstance(backend, LocalBackend):
        return str(backend.root)
    return getattr(backend, "remote_root", "~/.autolab-work")


def _local_staging_for(record_hash: str) -> Path:
    # Staging dir for fetched artefacts. Lives under the same root the
    # LocalBackend uses so ``autolab replay`` can find everything under
    # one path.
    base = Path.cwd() / ".autolab-runs" / "staging" / record_hash
    return base


def _cleanup(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


__all__ = ["ShellCommand"]
