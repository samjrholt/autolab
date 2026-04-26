"""SSH-backed execution.

Connects to an ssh alias from ``~/.ssh/config`` (or a host/user pair),
authenticating via ``ssh-agent``. autolab never holds SSH credentials
itself — this matches the subsystem 2+3 design's "framework does not
own secrets" stance.

Implementation status:
    This module defines the shape using ``asyncssh``. Actual wiring is
    deferred: when the user calls ``connect()`` on a lab without
    ``asyncssh`` installed (it is not in the base dep set to keep the
    install lean), they get a clear ``NotImplementedError`` pointing at
    ``pip install asyncssh`` or ``pixi add asyncssh``.

The shape is here because tests (and the Resource registration UI) need
to import the type and reason about ssh Resources even when they aren't
invocable.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autolab.backends.base import RemoteCommandResult

try:  # pragma: no cover — optional dep
    import asyncssh  # type: ignore

    _ASYNCSSH_AVAILABLE = True
except ImportError:  # pragma: no cover
    asyncssh = None  # type: ignore
    _ASYNCSSH_AVAILABLE = False


@dataclass
class SshExecBackend:
    """Execute commands on a remote host via SSH (asyncssh).

    ``host`` is the ssh alias (e.g. ``wsl-dev``). If the user's
    ``~/.ssh/config`` names that alias, all connection details (user,
    port, key) come from there. Otherwise ``host`` is interpreted as a
    hostname and ``user`` / ``port`` are used.
    """

    host: str
    user: str | None = None
    port: int | None = None
    remote_root: str = "~/.autolab-work"
    backend_type: str = "ssh_exec"
    _conn: Any = field(default=None, repr=False, compare=False)

    async def connect(self) -> None:
        if not _ASYNCSSH_AVAILABLE:
            raise NotImplementedError(
                "SSH execution requires asyncssh. Install with "
                "`pixi add asyncssh` or `pip install asyncssh`. "
                "autolab reads ssh-agent / ~/.ssh/config, no passwords stored."
            )
        kwargs: dict[str, Any] = {"known_hosts": None}
        if self.user:
            kwargs["username"] = self.user
        if self.port:
            kwargs["port"] = self.port
        self._conn = await asyncssh.connect(self.host, **kwargs)

    async def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None

    def _require_connection(self) -> Any:
        if self._conn is None:
            raise RuntimeError("SshExecBackend: connect() must be awaited first")
        return self._conn

    async def put_text(self, remote_path: str, content: str) -> None:
        conn = self._require_connection()
        parent = remote_path.rsplit("/", 1)[0]
        await conn.run(f"mkdir -p {shlex.quote(parent)}", check=True)
        async with conn.start_sftp_client() as sftp, sftp.open(remote_path, "w") as f:
            await f.write(content)

    async def get_text(self, remote_path: str) -> str:
        conn = self._require_connection()
        check = await conn.run(f"test -f {shlex.quote(remote_path)}", check=False)
        if check.exit_status != 0:
            return ""
        async with conn.start_sftp_client() as sftp, sftp.open(remote_path, "r") as f:
            content = await f.read()
            return content if isinstance(content, str) else content.decode("utf-8")

    async def get_file(
        self,
        remote_path: str,
        local_path: Path,
        size_limit_bytes: int = 500 * 1024 * 1024,
    ) -> None:
        conn = self._require_connection()
        async with conn.start_sftp_client() as sftp:
            stat = await sftp.stat(remote_path)
            if stat.size is not None and stat.size > size_limit_bytes:
                raise ValueError(
                    f"output_too_large: {remote_path} ({stat.size} bytes) "
                    f"exceeds {size_limit_bytes}"
                )
            local_path.parent.mkdir(parents=True, exist_ok=True)
            await sftp.get(remote_path, localpath=str(local_path))

    async def run_command(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> RemoteCommandResult:
        conn = self._require_connection()
        prefix = ""
        if cwd:
            prefix += f"cd {shlex.quote(cwd)} && "
        if env:
            exports = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            prefix += f"export {exports} && "
        full = prefix + command

        import time

        started = time.monotonic()
        try:
            result = await conn.run(full, check=False, timeout=timeout_seconds)
        except Exception as e:
            return RemoteCommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=time.monotonic() - started,
            )
        duration = time.monotonic() - started

        return RemoteCommandResult(
            exit_code=result.exit_status if result.exit_status is not None else -1,
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
            duration_seconds=duration,
        )

    async def ping(self) -> bool:
        if self._conn is None:
            return False
        try:
            result = await self._conn.run("true", check=False, timeout=5)
            return result.exit_status == 0
        except Exception:
            return False
