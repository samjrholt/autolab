"""Tests for the backends module — LocalBackend + RemoteWorkdir."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autolab.backends import LocalBackend, get_backend
from autolab.backends.base import RemoteWorkdir


@pytest.mark.asyncio
async def test_local_backend_round_trip(tmp_path: Path) -> None:
    backend = LocalBackend(root=tmp_path / "work")
    await backend.connect()
    try:
        remote = str(tmp_path / "work" / "abc123")
        await backend.put_text(f"{remote}/inputs.json", '{"x": 1}')
        text = await backend.get_text(f"{remote}/inputs.json")
        assert json.loads(text) == {"x": 1}

        # Run a command in the workdir and capture stdout.
        result = await backend.run_command("python -c \"print('hi')\"", cwd=remote)
        assert result.exit_code == 0
        assert "hi" in result.stdout
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_local_backend_ping() -> None:
    backend = LocalBackend()
    assert await backend.ping() is True


@pytest.mark.asyncio
async def test_remote_workdir_lifecycle(tmp_path: Path) -> None:
    backend = LocalBackend(root=tmp_path / "work")
    await backend.connect()
    try:
        wd = RemoteWorkdir(
            record_hash="feedface",
            backend=backend,
            remote_root=str(backend.root),
            local_staging=tmp_path / "staging",
            declared_outputs=["result.txt"],
        )

        await wd.write_inputs({"hello": "world"})
        # Write a "result" file in the workdir to be fetched back.
        result_path = Path(wd.remote_path) / "result.txt"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text("42\n")

        fetched = await wd.fetch_artefacts()
        assert "result.txt" in fetched
        # On local backend, fetched path is the same file (if staging dir differs)
        assert fetched["result.txt"].read_text() == "42\n"
    finally:
        await backend.close()


@pytest.mark.asyncio
async def test_remote_workdir_rejects_oversize(tmp_path: Path) -> None:
    backend = LocalBackend(root=tmp_path / "work")
    await backend.connect()
    try:
        wd = RemoteWorkdir(
            record_hash="big",
            backend=backend,
            remote_root=str(backend.root),
            local_staging=tmp_path / "staging",
            declared_outputs=["big.bin"],
        )
        big = Path(wd.remote_path) / "big.bin"
        big.parent.mkdir(parents=True, exist_ok=True)
        # Write 100 bytes but set size limit to 10 — should reject.
        big.write_bytes(b"x" * 100)
        with pytest.raises(ValueError, match="output_too_large"):
            await backend.get_file(str(big), tmp_path / "dest.bin", size_limit_bytes=10)
    finally:
        await backend.close()


def test_get_backend_lookup() -> None:
    assert get_backend("local").__name__ == "LocalBackend"
    assert get_backend("ssh_exec").__name__ == "SshExecBackend"
    with pytest.raises(ValueError, match="unknown backend"):
        get_backend("martian_exec")
