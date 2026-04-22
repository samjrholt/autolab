"""Dataset export — flatten ledger Records into a tabular DataFrame.

The framework's load-bearing moat is the ledger. A ledger you can't feed
into a model is just a log file, so we ship a first-class flattener:
every completed :class:`~autolab.Record` becomes one row, with a
consistent column scheme so downstream code (ML training, BO seeding,
dashboard plots) doesn't have to re-learn the structure each time.

Column scheme
-------------

Each row has these fixed columns::

    record_id, campaign_id, experiment_id, session_id,
    sample_id, operation, module, record_status,
    created_at, finalised_at, duration_ms,
    gate_result, checksum

plus flattened columns:

- ``inputs.<name>`` — one per input key (nested dicts get dotted keys).
- ``outputs.<name>`` — one per output key.
- ``decision.<name>`` — one per planner decision key (e.g. ``decision.trial_number``).

pandas is a **soft dependency** — the module imports it on demand so
autolab's runtime surface stays minimal. Install with
``pip install 'autolab[dataset]'`` or ``pip install pandas``.

Usage
-----

>>> from autolab import Lab
>>> from autolab.dataset import DatasetBuilder
>>> lab = Lab("./runs")
>>> df = DatasetBuilder(lab.ledger).for_campaign("camp-abc123").to_dataframe()
>>> df[["outputs.score", "gate_result"]].head()
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from autolab.models import Record

if TYPE_CHECKING:  # pragma: no cover
    import pandas as _pd

    from autolab.provenance.store import Ledger


_FIXED_COLUMNS = (
    "record_id",
    "campaign_id",
    "experiment_id",
    "session_id",
    "sample_id",
    "operation",
    "module",
    "record_status",
    "created_at",
    "finalised_at",
    "duration_ms",
    "gate_result",
    "checksum",
)


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}", v, out)
    else:
        out[prefix] = value


def record_to_row(record: Record) -> dict[str, Any]:
    """Convert one :class:`Record` into a flat row dict.

    Exposed for reuse in custom exporters and for testing without the
    ledger in the way.
    """
    row: dict[str, Any] = {
        "record_id": record.id,
        "campaign_id": record.campaign_id,
        "experiment_id": record.experiment_id,
        "session_id": record.session_id,
        "sample_id": record.sample_id,
        "operation": record.operation,
        "module": record.module,
        "record_status": record.record_status,
        "created_at": record.created_at,
        "finalised_at": record.finalised_at,
        "duration_ms": record.duration_ms,
        "gate_result": record.gate_result,
        "checksum": record.checksum,
    }
    for k, v in (record.inputs or {}).items():
        _flatten(f"inputs.{k}", v, row)
    for k, v in (record.outputs or {}).items():
        _flatten(f"outputs.{k}", v, row)
    for k, v in (record.decision or {}).items():
        _flatten(f"decision.{k}", v, row)
    return row


class DatasetBuilder:
    """Turn a stream of Records into a table.

    A builder is a short-lived view — construct, narrow with
    :meth:`for_campaign` / :meth:`with_operation` / :meth:`only_completed`,
    then call :meth:`rows` or :meth:`to_dataframe`.
    """

    def __init__(
        self,
        records_or_ledger: Iterable[Record] | Ledger,
    ) -> None:
        from autolab.provenance.store import Ledger  # local to avoid cycle

        self._ledger: Ledger | None = None
        self._records: Iterable[Record] | None = None
        if isinstance(records_or_ledger, Ledger):
            self._ledger = records_or_ledger
        else:
            self._records = records_or_ledger

        self._campaign_id: str | None = None
        self._operation: str | None = None
        self._only_completed: bool = False

    # ------------------------------------------------------------------
    # Narrowing
    # ------------------------------------------------------------------

    def for_campaign(self, campaign_id: str) -> DatasetBuilder:
        self._campaign_id = campaign_id
        return self

    def with_operation(self, operation: str) -> DatasetBuilder:
        self._operation = operation
        return self

    def only_completed(self, flag: bool = True) -> DatasetBuilder:
        self._only_completed = flag
        return self

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _iter_records(self) -> Iterable[Record]:
        if self._ledger is not None:
            status = "completed" if self._only_completed else None
            for rec in self._ledger.iter_records(campaign_id=self._campaign_id, status=status):
                if self._operation and rec.operation != self._operation:
                    continue
                yield rec
            return
        assert self._records is not None
        for rec in self._records:
            if self._campaign_id and rec.campaign_id != self._campaign_id:
                continue
            if self._operation and rec.operation != self._operation:
                continue
            if self._only_completed and rec.record_status != "completed":
                continue
            yield rec

    def rows(self) -> list[dict[str, Any]]:
        return [record_to_row(r) for r in self._iter_records()]

    def to_dataframe(self) -> _pd.DataFrame:
        """Return a :class:`pandas.DataFrame` — requires pandas installed."""
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover — deps failure surface
            raise ImportError(
                "pandas is required for DatasetBuilder.to_dataframe; "
                "install with `pip install pandas` or `pip install autolab[dataset]`"
            ) from exc

        rows = self.rows()
        if not rows:
            return pd.DataFrame(columns=list(_FIXED_COLUMNS))
        return pd.DataFrame(rows)


__all__ = ["DatasetBuilder", "record_to_row"]
