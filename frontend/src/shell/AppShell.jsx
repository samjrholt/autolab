import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function AppShell({ route, navigate, connected, escalationCount, onOpenEscalations, crumbs, children }) {
  return (
    <div className="app-shell">
      <Sidebar route={route} navigate={navigate} />
      <div className="app-shell-main">
        <TopBar
          crumbs={crumbs}
          connected={connected}
          escalationCount={escalationCount}
          onOpenEscalations={onOpenEscalations}
        />
        <main className="app-shell-content">{children}</main>
      </div>
    </div>
  );
}
