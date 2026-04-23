import { useState } from "react";

function SidebarItem({ label, icon, active, onClick, indent = 0 }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={`sidebar-item${active ? " is-active" : ""}`}
      style={indent ? { paddingLeft: 10 + indent * 14 } : undefined}
    >
      {icon ? <span aria-hidden style={{ width: 14, opacity: 0.7 }}>{icon}</span> : null}
      <span>{label}</span>
    </button>
  );
}

export default function Sidebar({ route, navigate, labName = "default" }) {
  const [libraryOpen, setLibraryOpen] = useState(true);

  const is = (page) => route.page === page;
  const isLib = (page) =>
    ["workflows", "resources", "capabilities"].includes(route.page) && route.page === page;

  return (
    <aside className="app-sidebar">
      <div className="sidebar-header">Lab</div>
      <div
        style={{
          padding: "6px 10px 10px",
          color: "var(--color-text)",
          fontSize: 13,
          borderBottom: "1px solid var(--color-line)",
          marginBottom: 8,
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <span style={{ color: "var(--color-accent)" }}>*</span>
        <span>{labName}</span>
        <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--color-secondary)" }}>v</span>
      </div>

      <SidebarItem
        label="Campaigns"
        icon="o"
        active={is("campaigns") || route.page === "campaign"}
        onClick={() => navigate({ page: "campaigns" })}
      />
      <SidebarItem
        label="Analysis"
        icon="/"
        active={is("analysis")}
        onClick={() => navigate({ page: "analysis" })}
      />

      <SidebarItem
        label="Library"
        icon={libraryOpen ? "v" : ">"}
        onClick={() => setLibraryOpen((value) => !value)}
      />
      {libraryOpen ? (
        <>
          <SidebarItem
            label="Workflows"
            active={isLib("workflows")}
            onClick={() => navigate({ page: "workflows" })}
            indent={1}
          />
          <SidebarItem
            label="Resources"
            active={isLib("resources")}
            onClick={() => navigate({ page: "resources" })}
            indent={1}
          />
          <SidebarItem
            label="Capabilities"
            active={isLib("capabilities")}
            onClick={() => navigate({ page: "capabilities" })}
            indent={1}
          />
        </>
      ) : null}

      <SidebarItem
        label="Ledger"
        icon="="
        active={is("ledger")}
        onClick={() => navigate({ page: "ledger" })}
      />

      <div className="sidebar-header">Setup</div>
      <SidebarItem
        label="Assistant"
        icon="+"
        active={is("assistant")}
        onClick={() => navigate({ page: "assistant" })}
      />

      <div style={{ flex: 1 }} />

      <div className="sidebar-header">Workspace</div>
      <SidebarItem
        label="Settings"
        icon="#"
        active={is("settings")}
        onClick={() => navigate({ page: "settings" })}
      />
    </aside>
  );
}
