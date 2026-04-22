"""Local subprocess backend.

Runs commands on the autolab host itself. Semantically identical to
``ssh_exec`` — single-slot lane, same ``RemoteWorkdir`` lifecycle —
but zero transport overhead. Useful for development, tests, and the
built-in ``shell_command`` Capability when the user hasn't connected a
remote host yet.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from autolab.backends.base import RemoteCommandResult


@dataclass
class LocalBackend:
    """Runs commands in a local subprocess; 'remote paths' are just local paths."""

    #: Where to stage work. Defaults to ``<cwd>/.autolab-work``.
    root: Path = Path(".autolab-work")
    backend_type: str = "local"

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()

    async def connect(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        # Nothing to tear down — subprocesses are ephemeral.
        return

    async def put_text(self, remote_path: str, content: str) -> None:
        path = Path(remote_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    async def get_text(self, remote_path: str) -> str:
        path = Path(remote_path)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    async def get_file(
        self,
        remote_path: str,
        local_path: Path,
        size_limit_bytes: int = 500 * 1024 * 1024,
    ) -> None:
        src = Path(remote_path)
        if not src.exists():
            raise FileNotFoundError(f"output not produced: {remote_path}")
        if src.stat().st_size > size_limit_bytes:
            raise ValueError(
                f"output_too_large: {remote_path} exceeds {size_limit_bytes} bytes"
            )
        local_path.parent.mkdir(parents=True, exist_ok=True)
        # "Local" backend: same filesystem, copy only if paths differ.
        if src.resolve() != local_path.resolve():
            local_path.write_bytes(src.read_bytes())

    async def run_command(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> RemoteCommandResult:
        work_dir = Path(cwd) if cwd else self.root
        work_dir.mkdir(parents=True, exist_ok=True)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        # Use shell=False on POSIX with argv from shlex; on Windows we shell out
        # so pixi / activation scripts still work.
        started = time.monotonic()
        if sys.platform == "win32":
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(work_dir),
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                *shlex.split(command),
                cwd=str(work_dir),
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return RemoteCommandResult(
                exit_code=124,
                stdout="",
                stderr=f"command timed out after {timeout_seconds}s",
                duration_seconds=time.monotonic() - started,
            )

        duration = time.monotonic() - started
        return RemoteCommandResult(
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout_b.decode("utf-8", errors="replace"),
            stderr=stderr_b.decode("utf-8", errors="replace"),
            duration_seconds=duration,
        )

    async def ping(self) -> bool:
        return True
