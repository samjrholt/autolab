import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function AppShell({ route, navigate, connected, escalationCount, onOpenEscalations, crumbs, children }) {
  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--color-canvas)", color: "var(--color-text)" }}>
      <Sidebar route={route} navigate={navigate} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <TopBar
          crumbs={crumbs}
          connected={connected}
          escalationCount={escalationCount}
          onOpenEscalations={onOpenEscalations}
        />
        <main style={{ flex: 1, overflow: "auto", padding: "20px 24px" }}>{children}</main>
      </div>
    </div>
  );
}
