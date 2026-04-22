"""Helpers for running commands in the WSL pixi environment.

All autolab WSL operations go through these two helpers so the subprocess
invocation is one place and easy to swap out (e.g. swap wsl.exe for SSH
when asyncssh becomes available).

WSL env layout
--------------
  /home/sam/autolab-wsl/       <- pixi project root
    pixi.toml                  <- numpy, scipy, matplotlib, pandas deps
    scripts/
      health.py                <- system info JSON
      numpy_eval.py            <- eval numpy expression for a given x
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

WSL_PROJECT = "/home/sam/autolab-wsl"
PIXI_BIN = "/home/sam/.pixi/bin/pixi"


def _wsl(bash_cmd: str, timeout: int = 30) -> tuple[str, str, int]:
    """Run a bash command inside WSL Ubuntu. Returns (stdout, stderr, returncode)."""
    result = subprocess.run(
        ["wsl", "-e", "bash", "-c", bash_cmd],
        capture_output=True,
        timeout=timeout,
    )
    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    return stdout, stderr, result.returncode


def run_pixi_script(script: str, *args: str, timeout: int = 30) -> Any:
    """Run a script in the WSL pixi env and parse its JSON stdout.

    script: path relative to WSL_PROJECT/scripts/ (e.g. 'numpy_eval.py')
    args:   positional arguments forwarded to the script
    Returns the parsed JSON object the script prints to stdout.
    """
    arg_str = " ".join(f"'{a}'" for a in args)
    cmd = f"cd {WSL_PROJECT} && {PIXI_BIN} run python3 scripts/{script} {arg_str} 2>&1"
    stdout, stderr, rc = _wsl(cmd, timeout=timeout)

    # Strip pixi warnings (lines starting with WARN) before JSON parsing.
    clean = "\n".join(line for line in stdout.splitlines()
                      if not line.strip().startswith(("WARN", "warn", " WARN", "+")))
    clean = clean.strip()

    if not clean:
        raise RuntimeError(
            f"WSL script {script!r} produced no output (rc={rc}).\nRaw: {stdout!r}"
        )
    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"WSL script {script!r} returned non-JSON (rc={rc}): {clean!r}"
        ) from exc


def wsl_available() -> bool:
    """Return True if wsl.exe is on PATH and Ubuntu distro is running."""
    try:
        _, _, rc = _wsl("echo ok", timeout=5)
        return rc == 0
    except Exception:
        return False
