"""VMExecutor — run a Python snippet inside a VM (WSL / local / SSH).

Modelling a VM as an autolab :class:`~autolab.Resource` gives every
MaMMoS operation a consistent execution context. The VM is where
``mammos-*`` packages live; the autolab process on the host only
orchestrates.

Three execution kinds
---------------------

``wsl`` (default on Windows)
    ``wsl.exe [-d <distro>] -- <python> -`` — pipe the script on stdin.
    Works out of the box if WSL is installed. The distro defaults to
    the WSL default.

``local``
    Runs the Python snippet in the current interpreter's ``python3``.
    Useful on Linux/macOS, and for CI where WSL is not available.

``ssh``
    ``ssh <host> <python> -`` — pipe the script on stdin. Set
    ``AUTOLAB_VM_SSH_HOST=user@host`` to select the remote.

Environment configuration
-------------------------

================================  ======================================
``AUTOLAB_VM_KIND``               ``wsl`` | ``local`` | ``ssh`` | ``auto``
``AUTOLAB_VM_DISTRO``             WSL distro name
``AUTOLAB_VM_PYTHON``             Python interpreter inside the VM
                                  (default ``python3``)
``AUTOLAB_VM_SSH_HOST``           ``user@host`` for ``ssh`` kind
``AUTOLAB_VM_TIMEOUT_S``          Per-script timeout (default 600 s)
``AUTOLAB_MAMMOS_FORCE_SURROGATE`` ``1`` forces the surrogate path even
                                  if mammos is installed; useful in
                                  tests for determinism.
================================  ======================================

Error taxonomy
--------------

The executor raises **two** distinct exceptions so the calling Operation
can surface the right :data:`~autolab.FailureMode`:

- :class:`VMError` — the VM itself is unreachable (wsl.exe missing, SSH
  auth failure, timeout). Map to ``equipment_failure``.
- :class:`ScriptError` — the VM ran the script but it exited non-zero
  or produced non-JSON stdout. Map to ``process_deviation``.

This aligns with the framework's failure taxonomy: a broken instrument
is retried, a broken recipe is escalated.
"""

from __future__ import annotations

import json
import os
import platform
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any


class VMError(RuntimeError):
    """The VM itself could not be reached or returned a system-level error."""


class ScriptError(RuntimeError):
    """The VM ran the script but it failed (non-zero exit or bad stdout)."""

    def __init__(self, message: str, *, returncode: int, stderr: str = "") -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


@dataclass
class VMConfig:
    """VM execution configuration. Defaults pull from the environment.

    ``pixi_project``
        Absolute path (inside the VM) of a pixi project directory. When
        set, commands are wrapped as ``bash -c 'cd <proj> && pixi run
        python -'`` so the pixi environment is activated — this puts
        binary deps (e.g. OOMMF for ubermag) on ``PATH`` and makes
        pip-installed packages importable without needing absolute
        interpreter paths.
    """

    kind: str = "auto"
    distro: str | None = None
    python: str = "python3"
    ssh_host: str | None = None
    timeout_s: float = 600.0
    force_surrogate: bool = False
    pixi_project: str | None = None
    extra_env: dict[str, str] | None = None

    @classmethod
    def from_env(cls) -> "VMConfig":
        kind = os.environ.get("AUTOLAB_VM_KIND", "auto").lower()
        if kind == "auto":
            kind = "wsl" if platform.system() == "Windows" else "local"
        return cls(
            kind=kind,
            distro=os.environ.get("AUTOLAB_VM_DISTRO"),
            python=os.environ.get("AUTOLAB_VM_PYTHON", "python3"),
            ssh_host=os.environ.get("AUTOLAB_VM_SSH_HOST"),
            timeout_s=float(os.environ.get("AUTOLAB_VM_TIMEOUT_S", "600")),
            force_surrogate=os.environ.get("AUTOLAB_MAMMOS_FORCE_SURROGATE", "") == "1",
            pixi_project=os.environ.get("AUTOLAB_VM_PIXI_PROJECT"),
        )


#: Pixi projects autolab probes for when ``AUTOLAB_VM_PIXI_PROJECT`` is unset.
#: The first one whose ``pixi.toml`` exists inside the VM is activated
#: automatically — so a user who followed the README's setup gets real
#: backends with zero env-var fiddling.
DEFAULT_PIXI_PROJECT_CANDIDATES: tuple[str, ...] = (
    "~/autolab-mammos",
    "~/mammos",
    "~/autolab",
)


class VMExecutor:
    """Runs Python snippets inside a VM and returns their JSON-encoded stdout.

    The script you submit MUST ``print(json.dumps(...))`` its result on
    stdout and nothing else — the executor parses stdout as a single
    JSON object.

    Auto-detection
    --------------

    If ``config.pixi_project`` is ``None`` (i.e. ``AUTOLAB_VM_PIXI_PROJECT``
    is not set), the executor probes :data:`DEFAULT_PIXI_PROJECT_CANDIDATES`
    in the VM and activates the first one that has a ``pixi.toml``.
    This means a user who followed the README's install steps
    (``~/autolab-mammos``) gets real ubermag/OOMMF/mammos backends on the
    first ``pixi run python -m examples.mammos_sensor.run`` with no
    extra configuration.

    To opt out of auto-detection, set ``AUTOLAB_VM_PIXI_PROJECT=none`` or
    ``AUTOLAB_VM_PIXI_PROJECT=""``.
    """

    def __init__(self, config: VMConfig | None = None) -> None:
        self.config = config or VMConfig.from_env()
        # Opt-out sentinel.
        if self.config.pixi_project in ("none", ""):
            self.config.pixi_project = None
        elif self.config.pixi_project is None:
            self.config.pixi_project = self._autodetect_pixi_project()
        # Expand leading `~` against the VM's $HOME so the runner invocation works.
        if self.config.pixi_project and self.config.pixi_project.startswith("~"):
            self.config.pixi_project = self._expand_home(self.config.pixi_project)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def kind(self) -> str:
        return self.config.kind

    @property
    def description(self) -> str:
        suffix = (
            f" (pixi@{self.config.pixi_project})" if self.config.pixi_project else ""
        )
        if self.config.kind == "wsl":
            return (
                f"wsl.exe -d {self.config.distro or '<default>'} -- "
                f"{self.config.python}{suffix}"
            )
        if self.config.kind == "local":
            return f"local {self.config.python}{suffix}"
        if self.config.kind == "ssh":
            return f"ssh {self.config.ssh_host or '?'} {self.config.python}{suffix}"
        return f"unknown kind={self.config.kind!r}"

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_python(
        self,
        code: str,
        *,
        stdin_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute ``code`` inside the VM.

        ``code`` is passed to the VM's Python via stdin (``python -``).
        ``stdin_payload`` is embedded as a literal ``payload`` dict at
        the top of the script — we can't send it *through* stdin because
        ``python -`` consumes the entire stdin buffer as source code
        before the script body runs, leaving nothing for
        ``sys.stdin.readline()`` to read.
        """
        header = "# -*- autolab vm runner -*-\n"
        if stdin_payload is not None:
            # Serialise the payload and parse it back inside the VM. Using
            # json.loads keeps the payload encoding-safe and independent of
            # Python version.
            payload_json = json.dumps(stdin_payload, ensure_ascii=True)
            header += (
                "import json as __autolab_json\n"
                f"payload = __autolab_json.loads({payload_json!r})\n"
            )
        full_script = header + code

        argv = self._build_argv()
        input_bytes = full_script.encode()

        try:
            proc = subprocess.run(
                argv,
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.timeout_s,
                check=False,
            )
        except FileNotFoundError as exc:
            raise VMError(f"VM executor command not found: {argv[0]!r} ({exc})") from exc
        except subprocess.TimeoutExpired as exc:
            raise VMError(f"VM script exceeded timeout {self.config.timeout_s}s") from exc

        stdout = proc.stdout.decode(errors="replace")
        stderr = proc.stderr.decode(errors="replace")

        if proc.returncode != 0:
            # If stderr screams about wsl/ssh missing it's a VM error; else script.
            lower_err = stderr.lower()
            if any(
                sig in lower_err
                for sig in (
                    "wsl is not recognized",
                    "no such host",
                    "connection refused",
                    "permission denied",
                    "wsl/service",
                )
            ):
                raise VMError(f"VM unreachable: {stderr.strip()}")
            raise ScriptError(
                f"VM script exited {proc.returncode}: {stderr.strip()}",
                returncode=proc.returncode,
                stderr=stderr,
            )

        # stdout must be a single-line JSON object on the last non-empty line.
        line = _last_nonempty_line(stdout)
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise ScriptError(
                f"VM script stdout not valid JSON: {line!r}\nfull stdout:\n{stdout}\nstderr:\n{stderr}",
                returncode=0,
                stderr=stderr,
            ) from exc

    def _autodetect_pixi_project(self) -> str | None:
        """Probe the VM for a pixi project at one of the default paths.

        Returns the first path whose ``pixi.toml`` exists, or ``None`` if
        no candidate matches. Quiet on failure — auto-detection is a
        best-effort convenience, not a hard requirement.
        """
        for cand in DEFAULT_PIXI_PROJECT_CANDIDATES:
            argv = self._probe_argv(f"test -f {shlex.quote(cand)}/pixi.toml")
            if argv is None:
                return None  # kind not supported for remote probing
            try:
                proc = subprocess.run(
                    argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=5.0, check=False,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return None
            if proc.returncode == 0:
                return cand
        return None

    def _expand_home(self, path: str) -> str:
        """Expand a leading ``~`` against the VM's $HOME."""
        if not path.startswith("~"):
            return path
        argv = self._probe_argv(f"echo {shlex.quote(path)}")
        if argv is None:
            return path
        try:
            proc = subprocess.run(
                argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=5.0, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return path
        if proc.returncode != 0:
            return path
        expanded = proc.stdout.decode(errors="replace").strip()
        return expanded or path

    def _probe_argv(self, shell_cmd: str) -> list[str] | None:
        """Return argv that runs ``shell_cmd`` inside the VM (None for local)."""
        if self.config.kind == "wsl":
            argv = ["wsl.exe"]
            if self.config.distro:
                argv += ["-d", self.config.distro]
            argv += ["--", "bash", "-c", shell_cmd]
            return argv
        if self.config.kind == "local":
            return ["bash", "-c", shell_cmd]
        if self.config.kind == "ssh":
            if not self.config.ssh_host:
                return None
            return ["ssh", self.config.ssh_host, shell_cmd]
        return None

    def _build_argv(self) -> list[str]:
        # If a pixi project is configured, wrap everything in `cd <proj> && pixi run python -`
        # so the pixi environment is activated and e.g. OOMMF appears on PATH.
        # We don't use a login shell (``-lc``) because some setups source non-interactive
        # login scripts that make pixi unreachable. Instead, prepend the standard pixi
        # bin directory to ``PATH`` explicitly.
        if self.config.pixi_project:
            inner = (
                'export PATH="$HOME/.pixi/bin:$PATH" && '
                f"cd {shlex.quote(self.config.pixi_project)} && exec pixi run python -"
            )
            if self.config.kind == "wsl":
                argv = ["wsl.exe"]
                if self.config.distro:
                    argv += ["-d", self.config.distro]
                argv += ["--", "bash", "-c", inner]
                return argv
            if self.config.kind == "local":
                return ["bash", "-c", inner]
            if self.config.kind == "ssh":
                if not self.config.ssh_host:
                    raise VMError("AUTOLAB_VM_SSH_HOST not set for ssh kind")
                return ["ssh", self.config.ssh_host, inner]

        # Plain python-direct path (no pixi).
        if self.config.kind == "wsl":
            argv = ["wsl.exe"]
            if self.config.distro:
                argv += ["-d", self.config.distro]
            argv += ["--", self.config.python, "-"]
            return argv
        if self.config.kind == "local":
            return [self.config.python, "-"]
        if self.config.kind == "ssh":
            if not self.config.ssh_host:
                raise VMError("AUTOLAB_VM_SSH_HOST not set for ssh kind")
            # shlex.quote the remote command so it survives the shell on the far side.
            remote = shlex.quote(self.config.python) + " -"
            return ["ssh", self.config.ssh_host, remote]
        raise VMError(f"unknown VM kind {self.config.kind!r}")


# ---------------------------------------------------------------------------
# Capability probe
# ---------------------------------------------------------------------------


_PROBE_SCRIPT = r"""
import json, sys, importlib, shutil


def _ver(name):
    try:
        mod = importlib.import_module(name)
    except Exception:  # noqa: BLE001
        return None
    return getattr(mod, "__version__", "unknown")


info = {
    "reachable": True,
    "python_version": sys.version.split()[0],
    # MaMMoS packages — pull in full ab-initio chain when present.
    "mammos_entity": _ver("mammos_entity"),
    "mammos_spindynamics": _ver("mammos_spindynamics"),
    "mammos_mumag": _ver("mammos_mumag"),
    "mammos_ai": _ver("mammos_ai"),
    "mammos_dft": _ver("mammos_dft"),
    # MLIP — structure relaxation backend.
    "mace": _ver("mace") or _ver("mace_torch"),
    "ase": _ver("ase"),
    # Ubermag stack — intermediate backend for micromagnetic simulation.
    "ubermag": _ver("ubermag"),
    "discretisedfield": _ver("discretisedfield"),
    "micromagneticmodel": _ver("micromagneticmodel"),
    "oommfc": _ver("oommfc"),
    # OOMMF — ubermag drives OOMMF via oommfc; the pip 'oommf' package
    # ships a prebuilt binary, or the user can install it manually.
    "oommf_binary": shutil.which("oommf"),
    "oommf_pip_package": _ver("oommf"),
}
info["has_full_mammos_chain"] = all(
    info[k] is not None for k in ("mammos_spindynamics", "mammos_mumag")
)
info["has_ubermag_chain"] = all(
    info[k] is not None
    for k in ("discretisedfield", "micromagneticmodel", "oommfc")
)
info["has_mace"] = info["mace"] is not None
print(json.dumps(info))
"""


def probe_vm(executor: VMExecutor | None = None) -> dict[str, Any]:
    """Detect which MaMMoS packages are importable in the VM.

    Always returns a dict (even on VM failure) so callers can inspect
    ``info["reachable"]`` and decide whether to proceed with the surrogate.
    The returned dict is stamped into the Resource's ``capabilities`` so
    future Records can tell which backend was live at run time.
    """
    ex = executor or VMExecutor()
    if ex.config.force_surrogate:
        return {
            "reachable": True,
            "force_surrogate": True,
            "python_version": None,
            "has_full_mammos_chain": False,
        }
    try:
        info = ex.run_python(_PROBE_SCRIPT)
        info.setdefault("force_surrogate", False)
        return info
    except (VMError, ScriptError) as exc:
        return {
            "reachable": False,
            "force_surrogate": False,
            "error": str(exc),
            "python_version": None,
            "has_full_mammos_chain": False,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line:
            return line
    return ""


__all__ = [
    "ScriptError",
    "VMConfig",
    "VMError",
    "VMExecutor",
    "probe_vm",
]
