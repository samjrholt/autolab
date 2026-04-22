import { useMemo } from "react";

// Gantt-lane renderer. One lane per Resource, Operations as pills positioned along a time axis.
export default function ResourceLanes({ resources, records }) {
  const { lanes, t0, t1 } = useMemo(() => {
    const resList = resources || [];
    const recsWithResource = (records || []).filter(
      (r) => r.resource || r.inputs?.resource || r.resource_name,
    );

    const allTimes = recsWithResource
      .flatMap((r) => [r.created_at, r.finalised_at])
      .filter(Boolean)
      .map((t) => new Date(t).getTime());
    const t0 = allTimes.length ? Math.min(...allTimes) : Date.now() - 60000;
    const t1 = allTimes.length ? Math.max(...allTimes) : Date.now();
    const span = Math.max(1000, t1 - t0);

    const lanes = resList.map((res) => {
      const rname = res.name;
      const opsOnRes = recsWithResource
        .filter((r) => (r.resource || r.inputs?.resource || r.resource_name) === rname)
        .slice(0, 40);

      const pills = opsOnRes.map((r) => {
        const start = new Date(r.created_at).getTime();
        const end = r.finalised_at ? new Date(r.finalised_at).getTime() : start + 5000;
        const leftPct = Math.max(0, ((start - t0) / span) * 100);
        const widthPct = Math.max(1.5, ((end - start) / span) * 100);
        const klass =
          r.status === "completed"
            ? "lane-pill--completed"
            : r.status === "failed"
              ? "lane-pill--failed"
              : r.status === "running"
                ? "lane-pill--running"
                : "lane-pill--queued";
        return {
          id: r.id,
          label: r.operation || "op",
          leftPct,
          widthPct,
          klass,
        };
      });

      return { name: rname, kind: res.kind || res.backend || "—", pills };
    });

    return { lanes, t0, t1 };
  }, [resources, records]);

  if (!resources || resources.length === 0) {
    return (
      <div style={{ padding: 18, textAlign: "center", color: "var(--color-secondary)", fontSize: 12 }}>
        No resources registered yet.
      </div>
    );
  }

  return (
    <div>
      {lanes.map((lane) => (
        <div className="lane" key={lane.name}>
          <div className="lane-label">{lane.name}</div>
          <div className="lane-track">
            {lane.pills.length === 0 ? (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--color-tertiary)",
                  fontSize: 10,
                }}
              >
                idle
              </div>
            ) : null}
            {lane.pills.map((p) => (
              <div
                key={p.id}
                className={`lane-pill ${p.klass}`}
                style={{ left: `${p.leftPct}%`, width: `${p.widthPct}%` }}
                title={`${p.label} · ${p.id}`}
              >
                {p.label}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
