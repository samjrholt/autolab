"""autolab CLI — thin client over the Lab service.

Available commands::

    autolab serve                               # boot the FastAPI Lab service
    autolab verify  --root ./.autolab-runs/...  # recompute SHA-256 for every Record
    autolab status                              # query /status on a running Lab
    autolab replay  --root <dir> --campaign <id> # byte-for-byte checksum replay

The replay command is the credibility anchor from
[docs/design/2026-04-22-competitive-landscape.md](../../docs/design/2026-04-22-competitive-landscape.md):
for each Record in a campaign, rehash the stored payload and compare
against the stored checksum. Any drift is printed as a mismatched id.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from autolab.lab import Lab
from autolab.provenance.hashing import hash_record

app = typer.Typer(add_completion=False, help="autolab — thin client over the Lab service.")


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    root: str = typer.Option(None, help="Ledger root directory (defaults to ./.autolab-runs/default)"),
    bootstrap: str = typer.Option(
        None,
        help="Bootstrap mode: superellipse | mammos | demo_quadratic | all | none | <module:fn>",
    ),
) -> None:
    """Boot the FastAPI Lab service."""
    if root:
        os.environ["AUTOLAB_ROOT"] = root
    if bootstrap:
        os.environ["AUTOLAB_BOOTSTRAP"] = bootstrap
    import uvicorn

    uvicorn.run("autolab.server.app:app", host=host, port=port, reload=False)


@app.command()
def verify(root: Path = typer.Option(..., help="Lab root containing ledger/")) -> None:
    """Recompute every Record's SHA-256; print any mismatched ids."""
    with Lab(root) as lab:
        bad = lab.verify_ledger()
        if not bad:
            typer.secho(f"OK — {sum(1 for _ in lab.ledger.iter_records())} records verified", fg="green")
        else:
            typer.secho(f"FAIL — {len(bad)} bad record ids:", fg="red")
            for rid in bad:
                typer.echo(f"  {rid}")
            raise typer.Exit(1)


@app.command()
def replay(
    root: Path = typer.Option(..., help="Lab root containing ledger/"),
    campaign: str = typer.Option(..., help="Campaign id to replay"),
) -> None:
    """Byte-for-byte replay: for each Record, recompute the hash over its stored
    canonical payload and compare against the stored checksum.

    This does NOT re-execute Operations. It is the integrity-audit variant of
    replay — enough for the "ledger is byte-stable" credibility anchor.
    Re-execution-style replay (running cached Operation outputs) is v2.
    """
    with Lab(root) as lab:
        records = list(lab.ledger.iter_records(campaign_id=campaign))
        if not records:
            typer.secho(f"no records for campaign {campaign!r}", fg="yellow")
            raise typer.Exit(2)
        mismatches = []
        for rec in records:
            stored = rec.checksum
            recomputed = hash_record(rec)
            if stored != recomputed:
                mismatches.append((rec.id, stored, recomputed))
        if not mismatches:
            typer.secho(
                f"OK — {len(records)} records replay byte-for-byte",
                fg="green",
            )
            return
        typer.secho(f"FAIL — {len(mismatches)} hash mismatches", fg="red")
        for rid, s, r in mismatches:
            typer.echo(f"  {rid}: stored={s[:12]} recomputed={r[:12]}")
        raise typer.Exit(1)


@app.command()
def status(url: str = "http://127.0.0.1:8000") -> None:
    """Fetch /status from a running Lab server and pretty-print it."""
    import httpx

    try:
        data = httpx.get(f"{url}/status", timeout=5).json()
    except httpx.HTTPError as exc:
        typer.secho(f"cannot reach {url}: {exc}", fg="red")
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(data, indent=2, default=str))


@app.command()
def export(
    root: Path = typer.Option(..., help="Lab root containing ledger/"),
    fmt: str = typer.Option("ro-crate", help="ro-crate | prov"),
    campaign: str = typer.Option(None, help="Restrict to one campaign"),
    out: Path = typer.Option(None, help="Write to file (default: stdout)"),
) -> None:
    """Export the ledger as RO-Crate 1.1 JSON-LD or PROV-O JSON."""
    from autolab.export import to_prov, to_ro_crate

    with Lab(root) as lab:
        if fmt == "ro-crate":
            data = to_ro_crate(lab, campaign_id=campaign)
        elif fmt == "prov":
            data = to_prov(lab, campaign_id=campaign)
        else:
            typer.secho(f"unknown format {fmt!r} — use ro-crate or prov", fg="red")
            raise typer.Exit(2)
    payload = json.dumps(data, indent=2, default=str)
    if out:
        out.write_text(payload, encoding="utf-8")
        typer.secho(f"wrote {out}", fg="green")
    else:
        typer.echo(payload)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
