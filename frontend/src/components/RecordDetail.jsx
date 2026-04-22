import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import KeyValue from "./KeyValue";
import MiniChart from "./MiniChart";
import StatusIndicator from "./StatusIndicator";
import SlideOver from "./SlideOver";
import { extractSpotlight } from "../lib/helpers";
import { formatNumber, formatTime, getJson, postJson } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function RecordDetail({ record, open, onClose }) {
  const [detail, setDetail] = useState(null);
  const [annotationText, setAnnotationText] = useState("");
  const [annotating, setAnnotating] = useState(false);

  useEffect(() => {
    if (!record) { setDetail(null); return; }
    let cancelled = false;
    getJson(`/records/${record.id}`)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch(() => { if (!cancelled) setDetail(null); });
    return () => { cancelled = true; };
  }, [record]);

  const data = detail || record;
  const spotlight = data ? extractSpotlight(data, formatNumber) : null;

  const handleAnnotate = async () => {
    if (!annotationText.trim() || !record) return;
    setAnnotating(true);
    try {
      await postJson(`/records/${record.id}/annotate`, { kind: "note", body: annotationText });
      setAnnotationText("");
      // Refresh detail
      const fresh = await getJson(`/records/${record.id}`);
      setDetail(fresh);
    } finally {
      setAnnotating(false);
    }
  };

  return (
    <SlideOver open={open} onClose={onClose} width="max-w-xl">
      {data && (
        <motion.div initial="hidden" animate="visible" variants={stagger}>
          {/* Header */}
          <motion.div variants={fadeInUp} className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <StatusIndicator
                status={data.record_status}
                pulse={data.record_status === "running"}
              />
              <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)]">
                {data.record_status}
              </span>
            </div>
            <h3
              className="text-[36px] font-normal text-white tracking-[-0.02em]"
              style={{ fontFamily: "var(--font-serif)" }}
            >
              {data.operation}
            </h3>
            <div
              className="flex flex-wrap gap-x-6 gap-y-1 mt-3 text-[12px] text-[var(--color-secondary)]"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              <span>{formatTime(data.created_at)}</span>
              {data.resource_name && <span>{data.resource_name}</span>}
              {data.campaign_id && <span>{data.campaign_id}</span>}
              {data.checksum && <span className="text-[var(--color-tertiary)]">{data.checksum.slice(0, 24)}</span>}
            </div>
          </motion.div>

          {/* Chart if applicable */}
          {spotlight?.points && (
            <motion.div variants={fadeInUp} className="mb-8 rounded-xl overflow-hidden border border-[var(--color-line)]">
              <MiniChart points={spotlight.points} height={160} />
            </motion.div>
          )}

          {/* Outputs */}
          {data.outputs && Object.keys(data.outputs).length > 0 && (
            <motion.section variants={fadeInUp} className="mb-8">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">
                Outputs
              </p>
              <KeyValue data={data.outputs} />
            </motion.section>
          )}

          {/* Inputs */}
          {data.inputs && Object.keys(data.inputs).length > 0 && (
            <motion.section variants={fadeInUp} className="mb-8">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">
                Inputs
              </p>
              <KeyValue data={data.inputs} />
            </motion.section>
          )}

          {/* Annotations */}
          {data.annotations?.length > 0 && (
            <motion.section variants={fadeInUp} className="mb-8">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">
                Annotations
              </p>
              <div className="flex flex-col gap-2">
                {data.annotations.map((a, i) => (
                  <div key={i} className="text-[13px] text-[var(--color-secondary)] border-l-2 border-[var(--color-line)] pl-3 py-1">
                    <span className="text-[11px] text-[var(--color-tertiary)] uppercase">{a.kind}</span>
                    <p className="text-white mt-0.5">{a.body}</p>
                  </div>
                ))}
              </div>
            </motion.section>
          )}

          {/* Annotate */}
          <motion.section variants={fadeInUp} className="mb-8">
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">
              Add annotation
            </p>
            <textarea
              value={annotationText}
              onChange={(e) => setAnnotationText(e.target.value)}
              placeholder="Add a note to this record…"
              rows={3}
              className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-4 py-3 text-[14px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none"
            />
            <button
              type="button"
              onClick={handleAnnotate}
              disabled={annotating || !annotationText.trim()}
              className="mt-2 bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-4 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30"
            >
              {annotating ? "Saving…" : "Annotate"}
            </button>
          </motion.section>

          {/* Actions row */}
          <motion.div variants={fadeInUp} className="flex flex-wrap gap-3 mb-8">
            <a
              href={`/export/prov?record_id=${data.id}`}
              download
              className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--color-secondary)] hover:text-white transition-all no-underline"
            >
              Export PROV
            </a>
            {data.sample_id && (
              <a
                href={`/samples/${data.sample_id}/history`}
                className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--color-secondary)] hover:text-white transition-all no-underline"
              >
                Sample lineage
              </a>
            )}
          </motion.div>

          {/* Raw JSON toggle */}
          <RawJsonToggle data={data} />
        </motion.div>
      )}
    </SlideOver>
  );
}

function RawJsonToggle({ data }) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setShow(!show)}
        className="bg-transparent border-none text-[12px] text-[var(--color-tertiary)] hover:text-[var(--color-secondary)] transition-colors p-0"
      >
        {show ? "Hide" : "View"} raw JSON
      </button>
      {show && (
        <pre className="mt-3 p-4 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] text-[12px] max-h-[400px] overflow-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
