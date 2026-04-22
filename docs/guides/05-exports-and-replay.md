# Exports, verify, and replay

The ledger is append-only and hashed. Three things fall out of that:
RO-Crate / PROV exports for ELN interop, a `verify` pass that
recomputes every checksum, and a `replay` pass that proves a campaign
is byte-stable on disk.

## Exporting

### RO-Crate 1.1 (ELN Consortium)

```bash
curl "http://localhost:8000/export/ro-crate?campaign_id=wf-abcdef" > crate.json
```

Matches the ELN Consortium's `.eln` packaging format. Chemotion,
eLabFTW, RSpace, and Kadi4Mat all import the resulting graph.
Dataset → CreateAction (one per Record) → PropertyValue (inputs /
outputs) → Comment (one per Annotation). The `identifier` on each
CreateAction is the Record's SHA-256 — downstream tools can verify
integrity without re-hashing.

### W3C PROV-O

```bash
curl "http://localhost:8000/export/prov?campaign_id=wf-abcdef" > prov.json
```

One Entity per Record, one Activity per Operation run, `wasDerivedFrom`
edges over `parent_ids` and sample lineage. Hand off to any
PROV-aware tool.

### From the CLI

```bash
pixi run autolab export --root .autolab-runs/default --fmt ro-crate \
  --campaign wf-abcdef --out crate.json
```

## Verify — is the on-disk ledger intact?

```bash
pixi run autolab verify --root .autolab-runs/default
# OK — 42 records verified
```

`verify` rehydrates the Ledger from SQLite + JSONL, rehashes every
Record, and reports any id whose stored `checksum` no longer matches
its canonical payload. Zero mismatches = the ledger has not been
tampered with since write.

## Replay — byte-for-byte reproducibility

```bash
pixi run autolab replay --root .autolab-runs/default --campaign wf-abcdef
# OK — 6 records replay byte-for-byte
```

For each Record in the campaign, `replay` re-canonicalises the stored
payload and recomputes the SHA-256. The check is strictly stronger than
`verify` for a campaign-scoped slice: it proves that the sequence of
events that made this campaign is reconstructible from the Records
alone. This is the **credibility anchor** from the competitive-landscape
doc — no ELN, no experiment tracker, and no prior autonomous-lab
framework ships an equivalent.

A future iteration will also re-execute cached Operation outputs
against their adapter code, proving that the same inputs + the same
code yield the same Record. Today's `replay` is the on-disk
verification step of that larger round-trip.

## Audit trail for Claude calls

Every LLM call — Planner `react()`, `CampaignDesigner`,
`annotation_extract` — lands as a `claim` Annotation with:

- `model` — exact model id
- `prompt_sha256` — hashed prompt
- `response_text` — full text (trimmed)
- `offline` — whether the response came from the offline stub

Export a campaign as RO-Crate and the Comments on each CreateAction
carry these fields. No tracker or ELN in the surveyed ecosystem records
agent reasoning this way; see
[docs/design/2026-04-22-competitive-landscape.md](../design/2026-04-22-competitive-landscape.md)
§7 differentiator #4.
