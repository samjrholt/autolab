import { useState } from "react";
import PageHeader from "../shell/PageHeader";

const SECTIONS = [
  { id: "lab", label: "Lab" },
  { id: "api_keys", label: "API keys" },
  { id: "assistant", label: "Setup Assistant" },
  { id: "integrations", label: "Integrations" },
  { id: "provenance", label: "Provenance" },
  { id: "examples", label: "Examples" },
  { id: "about", label: "About" },
];

function Section({ id, active, children }) {
  if (active !== id) return null;
  return <div className="panel" style={{ padding: 20 }}>{children}</div>;
}

export default function SettingsPage({ status, onOpenAssistant }) {
  const [active, setActive] = useState("lab");

  return (
    <>
      <PageHeader
        title="Settings"
        description="Lab-level configuration. Campaign-level configuration lives inside each Campaign's Config tab."
      />

      <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
        <aside style={{ width: 180, flexShrink: 0 }}>
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setActive(s.id)}
              className={`sidebar-item${active === s.id ? " is-active" : ""}`}
            >
              {s.label}
            </button>
          ))}
        </aside>

        <div style={{ flex: 1, minWidth: 0 }}>
          <Section id="lab" active={active}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500 }}>Lab</h3>
            <div style={{ fontSize: 13, color: "var(--color-muted)" }}>
              <div style={{ marginBottom: 8 }}>
                <span style={{ color: "var(--color-secondary)" }}>Lab ID:</span>{" "}
                <code>{status?.lab_id || "—"}</code>
              </div>
              <div style={{ marginBottom: 8 }}>
                <span style={{ color: "var(--color-secondary)" }}>Root:</span>{" "}
                <code style={{ fontSize: 11 }}>{status?.root || "—"}</code>
              </div>
              <div>
                <span style={{ color: "var(--color-secondary)" }}>Total records:</span>{" "}
                {status?.total_records ?? 0}
              </div>
            </div>
          </Section>

          <Section id="api_keys" active={active}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500 }}>API keys</h3>
            <div style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 10 }}>
              Anthropic API key. Read from <code>ANTHROPIC_API_KEY</code> env var or <code>~/.autolab/env</code>. autolab does not store it itself.
            </div>
            <div style={{ fontSize: 13 }}>
              <span className="status-dot" style={{ background: status?.claude_configured ? "var(--color-status-green)" : "var(--color-status-red)", marginRight: 6 }} />
              <span style={{ color: "var(--color-text)" }}>
                {status?.claude_configured ? "Anthropic key detected" : "No Anthropic key configured"}
              </span>
            </div>
          </Section>

          <Section id="assistant" active={active}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500 }}>Setup Assistant</h3>
            <div style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 14 }}>
              Describe your lab in natural language. Claude will walk you through connecting hosts,
              authoring capabilities from your repos, and running a smoke test.
            </div>
            <button type="button" className="btn-primary" onClick={onOpenAssistant}>
              Open Setup Assistant
            </button>
          </Section>

          <Section id="integrations" active={active}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500 }}>Integrations</h3>
            <div style={{ fontSize: 13, color: "var(--color-muted)" }}>
              SSH hosts are configured through your standard <code>~/.ssh/config</code> and <code>ssh-agent</code>.
              autolab uses aliases from that file; see <a href="https://www.ssh.com/academy/ssh/config" style={{ color: "var(--color-accent)" }}>the SSH docs</a> for details.
            </div>
          </Section>

          <Section id="provenance" active={active}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500 }}>Provenance</h3>
            <div style={{ fontSize: 13, color: "var(--color-muted)" }}>
              Records are append-only, hashed (SHA-256), and dual-written to SQLite + JSONL.
              Use <code>autolab replay &lt;campaign-id&gt;</code> to byte-for-byte reproduce a campaign from cached outputs.
            </div>
          </Section>

          <Section id="examples" active={active}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500 }}>Example packs</h3>
            <div style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 10 }}>
              Removable bundles of Capabilities, Workflows, and sample data. Examples live under
              {" "}<code>examples/</code> in the repo. Install them to try the lab without writing your own capabilities first.
            </div>
            <div style={{ fontSize: 13, color: "var(--color-secondary)" }}>
              (Discovery surface coming — for now, install via <code>autolab register tool examples/&lt;pack&gt;/capabilities/*.yaml</code>.)
            </div>
          </Section>

          <Section id="about" active={active}>
            <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500 }}>About</h3>
            <div style={{ fontSize: 13, color: "var(--color-muted)" }}>
              autolab · an autonomous lab with provenance as its foundation.
            </div>
          </Section>
        </div>
      </div>
    </>
  );
}
