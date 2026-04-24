/**
 * Record-hash citation utilities.
 *
 * Scans Claude's free-text output for inline record-hash references of the
 * form `0x[a-f0-9]{4,}` and wraps them in visually distinct, hoverable
 * spans that link to the matching ledger record.
 */

/** Regex that matches record short-hash citations like 0x4a2c or 0x4a2cff. */
export const HASH_RE = /0x[a-f0-9]{4,}/gi;

/**
 * Build a lookup map from the first-6-hex-chars of each record's checksum
 * to the record itself.  Collision chance with 6 hex chars is negligible for
 * demo-scale ledgers (<1000 records).
 *
 * @param {Array} records - Array of normalised record objects from useLabState.
 * @returns {Map<string, object>} key = lowercase "0x" + first 6 hex chars
 */
export function buildHashIndex(records) {
  const index = new Map();
  if (!records) return index;
  for (const rec of records) {
    const cs = rec.checksum || rec.id || "";
    if (cs) {
      const key = ("0x" + cs.slice(0, 6)).toLowerCase();
      if (!index.has(key)) index.set(key, rec);
    }
  }
  return index;
}

/**
 * Return a short human-readable tooltip string for a record.
 *
 * @param {object} rec
 */
export function recordTooltip(rec) {
  if (!rec) return "No matching record in ledger";
  const op = rec.operation || rec.capability || "?";
  const status = rec.record_status || rec.status || "?";
  const inputsSummary = (() => {
    try {
      const inp = rec.inputs || {};
      const keys = Object.keys(inp).slice(0, 3);
      if (!keys.length) return "";
      return keys.map((k) => `${k}=${JSON.stringify(inp[k])?.slice(0, 20)}`).join(", ");
    } catch {
      return "";
    }
  })();
  return `${op} · ${status}${inputsSummary ? " · " + inputsSummary : ""}`;
}

/**
 * Split text into an array of plain strings and { hash, record? } objects.
 * Consumers render the objects as highlighted spans.
 *
 * @param {string} text
 * @param {Map<string, object>} hashIndex - built by buildHashIndex()
 * @returns {Array<string|{hash: string, record: object|null}>}
 */
export function parseCitations(text, hashIndex) {
  if (!text) return [text || ""];
  const parts = [];
  let lastIndex = 0;
  const re = new RegExp(HASH_RE.source, "gi");
  let match;
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const raw = match[0].toLowerCase();
    parts.push({ hash: match[0], record: hashIndex.get(raw) ?? null });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}
