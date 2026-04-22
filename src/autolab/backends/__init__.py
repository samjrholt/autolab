"""Execution backends for Operations.

A ``ResourceBackend`` is the uniform interface every Operation goes
through to actually execute somewhere — local subprocess, SSH into a
remote host, SLURM submission, MCP-tool invocation, or a user-supplied
custom backend.

Provenance lives one layer up (the Orchestrator wraps every call and
persists write-ahead Records). This module just provides the execution
primitive: open a working directory, stage inputs, run, fetch outputs,
close. Every backend implements the same lifecycle, so adapters stay
backend-agnostic: they read ``inputs.json`` and write ``outputs.json``.

Hackathon scope:
    - ``LocalBackend`` — fully wired, runs as subprocess on the autolab
      host.
    - ``SshExecBackend`` — stub; raises ``NotImplementedError`` at
      connect time with a message pointing at the install path. Real
      implementation lands when ``asyncssh`` is added to deps.
    - ``SlurmBackend``, ``McpBackend`` — defined in the protocol,
      implementations deferred.

The ``ResourceBackend`` protocol is intentionally tiny so user-written
backends (instruments, vendor SDKs) can conform without inheriting from
autolab code.
"""

from autolab.backends.base import (
    BackendType,
    RemoteWorkdir,
    ResourceBackend,
)
from autolab.backends.local import LocalBackend
from autolab.backends.ssh import SshExecBackend

__all__ = [
    "BackendType",
    "LocalBackend",
    "RemoteWorkdir",
    "ResourceBackend",
    "SshExecBackend",
    "get_backend",
]


def get_backend(backend_type: str) -> type[ResourceBackend]:
    """Return the backend class for a given backend type string.

    Raises ``ValueError`` for unknown types. Used by the ResourceManager
    when instantiating a Resource.
    """
    registry: dict[str, type[ResourceBackend]] = {
        "local": LocalBackend,
        "ssh_exec": SshExecBackend,
    }
    if backend_type not in registry:
        raise ValueError(
            f"unknown backend type {backend_type!r}. "
            f"Built-in: {sorted(registry)}. "
            "For slurm / mcp / custom backends, register via entry point."
        )
    return registry[backend_type]
