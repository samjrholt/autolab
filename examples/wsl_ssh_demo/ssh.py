"""SSH-based helpers for the wsl_ssh_demo.

The remote host alias is ``wsl2`` — configured in ``~/.ssh/config`` so
``ssh wsl2`` works with key-based auth, no password. Scripts live at
``/home/sam/autolab-wsl/scripts/`` on that host.

Everything goes through ``run_script`` so the subprocess invocation is
in one place. These Operations only need plain ``python3`` (no numpy);
we skip pixi to keep startup instant and stdout clean.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

SSH_HOST = "wsl2"
REMOTE_SCRIPTS_DIR = "/home/sam/autolab-wsl/scripts"


def _ssh(remote_cmd: str, timeout: int = 20) -> tuple[str, str, int]:
    """Run a command on the SSH host. Returns (stdout, stderr, rc)."""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", SSH_HOST, remote_cmd],
        capture_output=True,
        timeout=timeout,
    )
    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    return stdout, stderr, result.returncode


def run_script(script: str, *args: str, timeout: int = 20) -> Any:
    """Run a remote script and parse its JSON stdout."""
    arg_str = " ".join(f"'{a}'" for a in args)
    cmd = f"python3 {REMOTE_SCRIPTS_DIR}/{script} {arg_str}"
    stdout, stderr, rc = _ssh(cmd, timeout=timeout)
    if rc != 0 or not stdout:
        raise RuntimeError(
            f"ssh {SSH_HOST!r} script {script!r} failed (rc={rc}): {stderr or stdout!r}"
        )
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"ssh {SSH_HOST!r} script {script!r} returned non-JSON: {stdout!r}"
        ) from exc


def ssh_available() -> bool:
    try:
        _, _, rc = _ssh("echo ok", timeout=5)
        return rc == 0
    except Exception:
        return False
