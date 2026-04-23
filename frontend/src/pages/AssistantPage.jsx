import { useState } from "react";
import PageHeader from "../shell/PageHeader";
import { postJson } from "../lib/api";

function MessageBubble({ role, children }) {
  const isUser = role === "user";
  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        margin: "10px 0",
      }}
    >
      <div
        style={{
          maxWidth: "72%",
          background: isUser ? "var(--color-accent-soft)" : "var(--color-card)",
          color: isUser ? "var(--color-accent)" : "var(--color-text)",
          border: isUser ? "1px solid rgba(201, 99, 66, 0.3)" : "1px solid var(--color-line-strong)",
          borderRadius: 8,
          padding: "10px 14px",
          fontSize: 13,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
        }}
      >
        {children}
      </div>
    </div>
  );
}

function ProposalCard({ title, items }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="card" style={{ padding: 12, marginBottom: 10 }}>
      <div
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: 0.07,
          color: "var(--color-tertiary)",
          marginBottom: 8,
        }}
      >
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {items.map((item, i) => (
          <div
            key={item.name || item.capability || i}
            style={{
              background: "var(--color-panel)",
              border: "1px solid var(--color-line)",
              borderRadius: 4,
              padding: "8px 10px",
              fontSize: 12,
              color: "var(--color-muted)",
              fontFamily: "var(--font-mono)",
            }}
          >
            {item.name ? <strong style={{ color: "var(--color-text)" }}>{item.name}</strong> : null}
            {item.name && item.kind ? <span style={{ color: "var(--color-secondary)" }}> - {item.kind}</span> : null}
            {item.capability ? <strong style={{ color: "var(--color-text)" }}>{item.capability}</strong> : null}
            {item.resource_kind ? <span style={{ color: "var(--color-secondary)" }}> - {item.resource_kind}</span> : null}
            {item.description ? (
              <div style={{ marginTop: 3, color: "var(--color-muted)", fontFamily: "var(--font-sans)" }}>
                {item.description}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AssistantPage({ status, refresh }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hi - I'm Claude running inside autolab. Tell me about the compute and equipment you have, and any goal you're working toward. I'll ask for missing details, then propose resources, capabilities, and workflows for you to approve.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState(null);
  const [registering, setRegistering] = useState(false);
  const [registered, setRegistered] = useState(false);

  if (status && !status.claude_configured) {
    return (
      <>
        <PageHeader title="Setup Assistant" />
        <div className="panel empty-state">
          <h3>Anthropic API key not detected</h3>
          <p>
            The Assistant needs <code>ANTHROPIC_API_KEY</code> to be set in the environment, or in{" "}
            <code>~/.autolab/env</code>. Set it and restart the lab to continue.
          </p>
        </div>
      </>
    );
  }

  const send = async () => {
    const text = input.trim();
    if (!text) return;
    setBusy(true);
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);

    try {
      const result = await postJson("/lab/setup", { text });
      setProposal(result);
      setRegistered(false);

      if (result.questions?.length) {
        const questions = result.questions.map((q) => `- ${q}`).join("\n");
        const notes = result.notes ? `\n\n${result.notes}` : "";
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `I need a few details before registering anything:\n${questions}${notes}`,
          },
        ]);
        return;
      }

      const summaryBits = [];
      if (result.resources?.length) {
        summaryBits.push(`${result.resources.length} resource${result.resources.length === 1 ? "" : "s"}`);
      }
      if (result.operations?.length) {
        summaryBits.push(`${result.operations.length} capabilit${result.operations.length === 1 ? "y" : "ies"}`);
      }
      if (result.workflow) summaryBits.push("1 workflow");

      const summary = summaryBits.length
        ? `I've drafted ${summaryBits.join(" and ")}. Review them below and approve if they look right, or tell me what to change.`
        : "I couldn't draft anything concrete from that. Can you tell me about the specific hosts or instruments you have?";
      const notes = result.notes ? `\n\n${result.notes}` : "";
      setMessages((m) => [...m, { role: "assistant", content: summary + notes }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `Error: ${String(err)}. Is ANTHROPIC_API_KEY set?` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const registerProposal = async () => {
    if (!proposal) return;
    setRegistering(true);
    try {
      await postJson("/lab/setup/apply", proposal);
      setRegistered(true);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            "Done - everything is registered. You can now start a campaign that uses these resources, capabilities, and workflows from the Campaigns page.",
        },
      ]);
      if (refresh) await refresh();
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: `Registration failed: ${String(err)}` }]);
    } finally {
      setRegistering(false);
    }
  };

  const hasConcreteProposal = Boolean(proposal?.resources?.length || proposal?.operations?.length || proposal?.workflow);

  return (
    <>
      <PageHeader
        title="Setup Assistant"
        description="Describe your lab in natural language. Claude asks for missing details, then proposes setup changes for approval."
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16, alignItems: "flex-start" }}>
        <div className="panel" style={{ padding: 14, height: "calc(100vh - 220px)", display: "flex", flexDirection: "column" }}>
          <div style={{ flex: 1, overflowY: "auto", paddingRight: 4 }}>
            {messages.map((m, i) => (
              <MessageBubble key={i} role={m.role}>
                {m.content}
              </MessageBubble>
            ))}
            {busy ? (
              <MessageBubble role="assistant">
                <span style={{ color: "var(--color-tertiary)" }}>...thinking</span>
              </MessageBubble>
            ) : null}
          </div>
          <div
            style={{
              borderTop: "1px solid var(--color-line-strong)",
              paddingTop: 10,
              display: "flex",
              gap: 8,
              marginTop: 10,
            }}
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="I have a WSL host at localhost and a script in ~/code/my-sim that I run via pixi..."
              disabled={busy}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={3}
              style={{
                flex: 1,
                background: "var(--color-canvas)",
                border: "1px solid var(--color-line-strong)",
                borderRadius: 5,
                padding: 10,
                color: "var(--color-text)",
                fontSize: 13,
                resize: "none",
              }}
            />
            <button type="button" onClick={send} disabled={busy || !input.trim()} className="btn-primary">
              Send
            </button>
          </div>
        </div>

        <aside style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div
            style={{
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: 0.07,
              color: "var(--color-tertiary)",
            }}
          >
            Proposed setup
          </div>
          {proposal ? (
            <>
              <ProposalCard title="Resources" items={proposal.resources || []} />
              <ProposalCard title="Capabilities" items={proposal.operations || []} />
              <ProposalCard title="Workflow" items={proposal.workflow ? [proposal.workflow] : []} />
              {proposal.questions?.length ? (
                <div className="card" style={{ padding: 14, fontSize: 12, color: "var(--color-secondary)" }}>
                  {proposal.questions.map((q) => (
                    <div key={q} style={{ marginBottom: 6 }}>
                      {q}
                    </div>
                  ))}
                </div>
              ) : null}
              {hasConcreteProposal ? (
                <div>
                  {registered ? (
                    <span style={{ color: "var(--color-status-green)", fontSize: 12 }}>Registered</span>
                  ) : (
                    <button
                      type="button"
                      disabled={registering || proposal.ready_to_apply === false}
                      onClick={registerProposal}
                      className="btn-primary"
                    >
                      {registering ? "Registering..." : "Register setup"}
                    </button>
                  )}
                </div>
              ) : null}
            </>
          ) : (
            <div className="card" style={{ padding: 14, fontSize: 12, color: "var(--color-secondary)" }}>
              Proposals appear here after you describe your lab.
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
