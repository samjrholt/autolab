"""Tests for the ``shell_command`` Capability adapter."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from autolab.backends import LocalBackend
from autolab.operations.base import OperationContext
from autolab.tools.adapters.shell_command import ShellCommand


@pytest.mark.asyncio
async def test_shell_command_echo(tmp_path: Path) -> None:
    op = ShellCommand()
    op.backend_override = LocalBackend(root=tmp_path / "work")

    ctx = OperationContext(record_id="rec-testfeed1234", operation="shell_command")
    # Portable echo: use Python so tests work on Windows + POSIX.
    result = await op.run(
        {"command": f"{sys.executable} -c \"print('hello')\""},
        context=ctx,
    )
    assert result.status == "completed"
    assert result.outputs["exit_code"] == 0
    assert "hello" in result.outputs["stdout"]


@pytest.mark.asyncio
async def test_shell_command_fails_without_command() -> None:
    op = ShellCommand()
    result = await op.run({})
    assert result.status == "failed"
    assert "requires" in result.outputs["reason"]


@pytest.mark.asyncio
async def test_shell_command_captures_nonzero_exit(tmp_path: Path) -> None:
    op = ShellCommand()
    op.backend_override = LocalBackend(root=tmp_path / "work")

    ctx = OperationContext(record_id="rec-fail12345678", operation="shell_command")
    result = await op.run(
        {"command": f'{sys.executable} -c "import sys; sys.exit(7)"'},
        context=ctx,
    )
    assert result.status == "failed"
    assert result.outputs["exit_code"] == 7


@pytest.mark.asyncio
async def test_shell_command_collects_declared_artefact(tmp_path: Path) -> None:
    op = ShellCommand()
    op.backend_override = LocalBackend(root=tmp_path / "work")

    ctx = OperationContext(record_id="rec-artefact9999", operation="shell_command")
    result = await op.run(
        {
            "command": f"{sys.executable} -c \"open('note.txt','w').write('persisted')\"",
            "declared_outputs": ["note.txt"],
        },
        context=ctx,
    )
    assert result.status == "completed"
    assert "artefacts" in result.outputs
    assert "note.txt" in result.outputs["artefacts"]
    artefact_path = Path(result.outputs["artefacts"]["note.txt"])
    assert artefact_path.exists()
    assert artefact_path.read_text().strip() == "persisted"
