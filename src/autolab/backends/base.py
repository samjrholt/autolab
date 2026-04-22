"""Backend protocol and the RemoteWorkdir lifecycle primitive.

Every Operation gets a remote working directory whose name *is* the
record hash. This is the load-bearing uniformity that lets the
framework enforce provenance — adapters cannot skip writing to the
workdir because the orchestrator is the one that opens it, uploads
``inputs.json``, and downloads the declared outputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

BackendType = str  # "local" | "ssh_exec" | "slurm" | "mcp" | "custom"


@dataclass
class RemoteCommandResult:
    """Outcome of a single command on a remote (or local) backend."""

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class RemoteWorkdir:
    """A working directory for one Operation, managed by the framework.

    Lifecycle (matches the subsystem 2+3 design):

    1. ``open()`` — create ``~/.autolab-work/<record-hash>/`` on the
       backend and upload ``inputs.json``.
    2. ``run()`` — execute the command from inside the workdir.
    3. ``fetch()`` — download declared output files back to the local
       staging dir, hash them for the Record.
    4. ``close()`` — does NOT delete immediately. A pruner removes
       workdirs for Records older than the retention window.

    For the ``local`` backend, the "remote" path is a subdirectory of
    the autolab root on the same host — the semantics are identical.
    """

    record_hash: str
    backend: ResourceBackend
    remote_root: str
    local_staging: Path
    # Fetched back on close; hashes filled by the orchestrator.
    declared_outputs: list[str] = field(default_factory=list)

    @property
    def remote_path(self) -> str:
        """The remote workdir path. Backend-specific separator."""
        return f"{self.remote_root.rstrip('/')}/{self.record_hash}"

    async def write_inputs(self, inputs: dict[str, Any]) -> None:
        """Upload ``inputs.json`` into the workdir."""
        payload = json.dumps(inputs, indent=2, default=str)
        await self.backend.put_text(f"{self.remote_path}/inputs.json", payload)

    async def read_outputs(self) -> dict[str, Any]:
        """Download ``outputs.json`` from the workdir."""
        raw = await self.backend.get_text(f"{self.remote_path}/outputs.json")
        return json.loads(raw) if raw else {}

    async def run(
        self,
        command: str,
        env: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> RemoteCommandResult:
        """Run a command inside the workdir on the backend."""
        return await self.backend.run_command(
            command=command,
            cwd=self.remote_path,
            env=env or {},
            timeout_seconds=timeout_seconds,
        )

    async def fetch_artefacts(self) -> dict[str, Path]:
        """Download declared output files to the local staging dir.

        Returns a mapping from declared-output-name → local path. Files
        exceeding the size limit (500 MB per file) fail at fetch time.
        """
        fetched: dict[str, Path] = {}
        for path in self.declared_outputs:
            local_path = self.local_staging / Path(path).name
            self.local_staging.mkdir(parents=True, exist_ok=True)
            await self.backend.get_file(
                f"{self.remote_path}/{path}",
                local_path,
                size_limit_bytes=500 * 1024 * 1024,
            )
            fetched[path] = local_path
        return fetched


@runtime_checkable
class ResourceBackend(Protocol):
    """The extension-point every Resource backend implements.

    Six methods — minimal by design. A user wrapping an oscilloscope or
    a vendor SDK writes a class conforming to this Protocol and
    registers it via an entry point. No inheritance from autolab code
    required.
    """

    backend_type: str

    async def connect(self) -> None:
        """Open any transport the backend needs (SSH, MCP socket, …)."""
        ...

    async def close(self) -> None:
        """Tear down the transport."""
        ...

    async def put_text(self, remote_path: str, content: str) -> None:
        """Upload a UTF-8 text file to the backend."""
        ...

    async def get_text(self, remote_path: str) -> str:
        """Download a UTF-8 text file from the backend (``""`` if absent)."""
        ...

    async def get_file(
        self,
        remote_path: str,
        local_path: Path,
        size_limit_bytes: int = 500 * 1024 * 1024,
    ) -> None:
        """Download a binary file, rejecting if it exceeds the limit."""
        ...

    async def run_command(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> RemoteCommandResult:
        """Execute one command and return its outcome."""
        ...

    async def ping(self) -> bool:
        """Return True if the backend is reachable right now."""
        ...
