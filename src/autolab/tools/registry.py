"""Capability-named Tool registry.

Two registration paths
----------------------

1. **Python-first (recommended)** — call ``registry.register_class(MyOp)``
   where ``MyOp`` is an :class:`~autolab.operations.base.Operation` subclass.
   The registry derives the full declaration from the class attributes and,
   optionally, from inner ``Inputs`` / ``Outputs`` Pydantic models.  No YAML
   needed.  The declaration hash is the SHA-256 of the canonical JSON schema
   derived from the class, so changing the class signature is a
   provenance-visible event.

2. **YAML / dict (for external/legacy adapters)** — call
   ``register_path(path)`` or ``register_dict(raw)``.  Use this when wrapping
   an instrument that has no Python adapter (e.g. a proprietary CLI tool), or
   when you want a human-readable on-disk record of the capability interface.

Python-first example
--------------------

::

    from autolab.operations.base import Operation, OperationContext
    from autolab.models import OperationResult
    from pydantic import BaseModel, Field

    class TubeFurnaceSinter(Operation):
        capability    = "sinter"
        resource_kind = "tube_furnace"
        requires      = {"max_temp_k": {">=": 1300}}
        module        = "sinter.v1.0"
        produces_sample = True
        destructive     = True
        typical_duration = 7200  # seconds, used by scheduler for Gantt ETAs

        class Inputs(BaseModel):
            temp_k:   float = Field(..., ge=600, le=1300)
            time_min: float = Field(..., ge=10, le=480)
            atmosphere: str = "Ar"

        class Outputs(BaseModel):
            grain_size_nm: float
            densification: float

        async def run(self, inputs: Inputs, ctx: OperationContext) -> OperationResult:
            ...

    lab.register_operation(TubeFurnaceSinter)   # ← single call, no YAML

The ``Inputs`` and ``Outputs`` inner models become the canonical column
names for the :class:`~autolab.dataset.DatasetBuilder` and the input
validation schema.  If they are absent the registry falls back to empty
dicts and no validation is performed.

YAML is still fully supported
------------------------------

``register_path`` / ``register_dict`` work as before.  YAML is the right
choice for **external adapters** (shell-command wrappers, proprietary
instrument software) because there is no Python class to introspect.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from autolab.operations.base import Operation
from autolab.provenance.hashing import file_sha256, sha256_hex


@dataclass(frozen=True)
class ToolDeclaration:
    """One Tool entry in the registry.

    ``typical_duration_s``
        Best-guess duration in seconds for the scheduler's ETA estimates.
        Derived from ``Operation.typical_duration`` (int, seconds) if present;
        otherwise ``None``.
    """

    name: str
    capability: str
    version: str
    resource_kind: str | None
    requires: dict[str, Any]
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    adapter_path: str
    module: str
    produces_sample: bool
    destructive: bool
    declaration_hash: str
    typical_duration_s: int | None = None
    source_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    # Populated only for Python-first registrations.
    _adapter_class: type[Operation] | None = field(default=None, compare=False, repr=False)


class ToolRegistry:
    """In-memory registry of declared Tools.

    Lookup is O(1) by capability/name.  Hash collision across two tools
    with the same name raises ``ValueError`` at registration time.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDeclaration] = {}
        self._adapter_cache: dict[str, type[Operation]] = {}

    # ------------------------------------------------------------------
    # Python-first registration
    # ------------------------------------------------------------------

    def register_class(self, cls: type[Operation]) -> ToolDeclaration:
        """Derive a :class:`ToolDeclaration` from an Operation subclass.

        The declaration hash is computed from the canonical JSON of the
        inferred schema (name, version, resource, requires, inputs schema,
        outputs schema).  Changing any of these attributes on the class
        produces a different hash — provenance-visible.

        Optional class attributes used:
        - ``capability`` (str) — defaults to ``cls.__name__``
        - ``resource_kind`` (str | None)
        - ``requires`` (dict)
        - ``produces_sample`` (bool)
        - ``destructive`` (bool)
        - ``module`` (str) — defaults to ``"{capability}.v0"``
        - ``typical_duration`` (int, seconds) — for Gantt ETAs
        - ``version`` (str) — defaults to ``"0.0.0"``
        - ``Inputs`` (inner Pydantic model) — input schema
        - ``Outputs`` (inner Pydantic model) — output schema
        """
        cap = getattr(cls, "capability", cls.__name__)
        version = getattr(cls, "version", "0.0.0")
        resource_kind = getattr(cls, "resource_kind", None)
        requires = dict(getattr(cls, "requires", {}) or {})
        produces_sample = bool(getattr(cls, "produces_sample", False))
        destructive = bool(getattr(cls, "destructive", False))
        module = getattr(cls, "module", f"{cap}.v0")
        typical_duration_s: int | None = getattr(cls, "typical_duration", None)

        inputs_schema = _model_to_schema(getattr(cls, "Inputs", None))
        outputs_schema = _model_to_schema(getattr(cls, "Outputs", None))

        schema_dict = {
            "capability": cap,
            "version": version,
            "resource_kind": resource_kind,
            "requires": requires,
            "inputs": inputs_schema,
            "outputs": outputs_schema,
            "module": module,
        }
        decl_hash = sha256_hex(schema_dict)

        # Build a dotted adapter path so the YAML path still works if needed.
        mod = inspect.getmodule(cls)
        mod_name = mod.__name__ if mod is not None else cls.__module__
        adapter_path = f"{mod_name}:{cls.__name__}"

        decl = ToolDeclaration(
            name=cap,
            capability=cap,
            version=str(version),
            resource_kind=resource_kind,
            requires=requires,
            inputs=inputs_schema,
            outputs=outputs_schema,
            adapter_path=adapter_path,
            module=str(module),
            produces_sample=produces_sample,
            destructive=destructive,
            declaration_hash=decl_hash,
            typical_duration_s=typical_duration_s,
            _adapter_class=cls,
        )
        if cap in self._tools:
            raise ValueError(f"tool {cap!r} already registered")
        self._tools[cap] = decl
        self._adapter_cache[cap] = cls
        return decl

    # ------------------------------------------------------------------
    # YAML / dict registration
    # ------------------------------------------------------------------

    def register_path(self, path: str | Path) -> ToolDeclaration:
        path = Path(path)
        with path.open("rb") as fh:
            raw = yaml.safe_load(fh)
        decl_hash = file_sha256(str(path))
        return self._register(raw, decl_hash, source=path)

    def register_dict(self, raw: dict[str, Any]) -> ToolDeclaration:
        decl_hash = sha256_hex(raw)
        return self._register(raw, decl_hash, source=None)

    def register_paths(self, paths: Iterable[str | Path]) -> list[ToolDeclaration]:
        return [self.register_path(p) for p in paths]

    def _register(
        self, raw: dict[str, Any], decl_hash: str, *, source: Path | None
    ) -> ToolDeclaration:
        name = raw["name"]
        if name in self._tools:
            raise ValueError(f"tool {name!r} already registered")
        decl = ToolDeclaration(
            name=name,
            capability=raw.get("capability", name),
            version=str(raw.get("version", "0.0.0")),
            resource_kind=raw.get("resource"),
            requires=dict(raw.get("requires", {}) or {}),
            inputs=dict(raw.get("inputs", {}) or {}),
            outputs=dict(raw.get("outputs", {}) or {}),
            adapter_path=raw["adapter"],
            module=str(raw.get("module", f"{name}.v{raw.get('version', '0.0.0')}")),
            produces_sample=bool(raw.get("produces_sample", False)),
            destructive=bool(raw.get("destructive", False)),
            declaration_hash=decl_hash,
            typical_duration_s=raw.get("typical_duration_s"),
            source_path=source,
            raw=raw,
        )
        self._tools[name] = decl
        return decl

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> ToolDeclaration:
        if name not in self._tools:
            raise KeyError(f"tool {name!r} not registered")
        return self._tools[name]

    def list(self) -> list[ToolDeclaration]:
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        return name in self._tools

    # ------------------------------------------------------------------
    # Adapter resolution
    # ------------------------------------------------------------------

    def adapter(self, name: str) -> type[Operation]:
        """Resolve and cache the Operation subclass for a Tool."""
        if name in self._adapter_cache:
            return self._adapter_cache[name]
        decl = self.get(name)
        # Python-first: class stored directly.
        if decl._adapter_class is not None:
            self._adapter_cache[name] = decl._adapter_class
            return decl._adapter_class
        # YAML path: import by dotted/colon path.
        cls = _import_attr(decl.adapter_path)
        if not (isinstance(cls, type) and issubclass(cls, Operation)):
            raise TypeError(
                f"adapter {decl.adapter_path!r} for tool {name!r} is not an Operation subclass"
            )
        self._adapter_cache[name] = cls
        return cls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _model_to_schema(model_cls: Any) -> dict[str, Any]:
    """Extract a JSON-schema-like dict from a Pydantic model class, or ``{}``."""
    if model_cls is None:
        return {}
    try:
        schema = model_cls.model_json_schema()
        # Flatten to {field_name: {kind, ...}} for backward compat with YAML format.
        props = schema.get("properties", {})
        return {k: {"kind": "scalar", **v} for k, v in props.items()}
    except Exception:
        return {}


def _import_attr(path: str) -> Any:
    """Import ``module.path:attribute`` or ``module.path.attribute``."""
    if ":" in path:
        mod_path, attr = path.split(":", 1)
    else:
        mod_path, _, attr = path.rpartition(".")
    if not mod_path:
        raise ValueError(f"invalid adapter path {path!r}")
    module = importlib.import_module(mod_path)
    return getattr(module, attr)


__all__ = ["ToolDeclaration", "ToolRegistry"]
