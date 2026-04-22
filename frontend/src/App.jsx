import { useCallback, useMemo, useState } from "react";

import { useLabState } from "./hooks/useLabState";
import AppShell from "./shell/AppShell";

import CampaignsPage from "./pages/CampaignsPage";
import CampaignDetailPage from "./pages/CampaignDetailPage";
import ResourcesPage from "./pages/ResourcesPage";
import CapabilitiesPage from "./pages/CapabilitiesPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import LedgerPage from "./pages/LedgerPage";
import SettingsPage from "./pages/SettingsPage";

import RecordDetail from "./components/RecordDetail";
import NewCampaignSlideOver from "./components/NewCampaignSlideOver";
import EscalationsSlideOver from "./components/EscalationsSlideOver";
import InterventionSlideOver from "./components/InterventionSlideOver";
import SettingsDrawer from "./components/SettingsDrawer";

const CRUMBS = {
  campaigns: ["Campaigns"],
  resources: ["Library", "Resources"],
  capabilities: ["Library", "Capabilities"],
  workflows: ["Library", "Workflows"],
  ledger: ["Ledger"],
  settings: ["Settings"],
};

export default function App() {
  const { status, records, events, connected, loading, error, refresh } = useLabState();

  const [route, setRoute] = useState({ page: "campaigns" });
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [showNewCampaign, setShowNewCampaign] = useState(false);
  const [showEscalations, setShowEscalations] = useState(false);
  const [showIntervention, setShowIntervention] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const campaigns = status?.campaigns || [];
  const resources = status?.resources || [];
  const tools = status?.tools || [];
  const workflows = status?.workflows || [];
  const escalationCount = status?.escalations?.length || 0;

  const navigate = useCallback((next) => setRoute(next), []);

  const selectedCampaign = useMemo(
    () => (route.page === "campaign" ? campaigns.find((c) => c.campaign_id === route.campaignId) : null),
    [route, campaigns],
  );

  const crumbs = useMemo(() => {
    if (route.page === "campaign" && selectedCampaign) {
      const goal = selectedCampaign.objective?.description || selectedCampaign.name || selectedCampaign.campaign_id;
      return ["Campaigns", goal];
    }
    return CRUMBS[route.page] || [route.page];
  }, [route, selectedCampaign]);

  const pageContent = (() => {
    if (route.page === "campaigns") {
      return (
        <CampaignsPage
          campaigns={campaigns}
          onSelectCampaign={(c) => navigate({ page: "campaign", campaignId: c.campaign_id })}
          onNewCampaign={() => setShowNewCampaign(true)}
        />
      );
    }
    if (route.page === "campaign" && selectedCampaign) {
      return (
        <CampaignDetailPage
          campaign={selectedCampaign}
          records={records}
          resources={resources}
          events={events}
          refresh={refresh}
          onBack={() => navigate({ page: "campaigns" })}
          onOpenIntervention={() => setShowIntervention(true)}
        />
      );
    }
    if (route.page === "campaign") {
      return (
        <div className="empty-state">
          <h3>Campaign not found</h3>
          <p>This campaign may have been deleted or never existed.</p>
          <button type="button" className="btn-secondary" onClick={() => navigate({ page: "campaigns" })}>
            ← Back to campaigns
          </button>
        </div>
      );
    }
    if (route.page === "resources") {
      return <ResourcesPage resources={resources} onAddResource={() => setShowSettings(true)} />;
    }
    if (route.page === "capabilities") {
      return <CapabilitiesPage tools={tools} onRegister={() => setShowSettings(true)} />;
    }
    if (route.page === "workflows") {
      return <WorkflowsPage workflows={workflows} onCreate={() => setShowSettings(true)} />;
    }
    if (route.page === "ledger") {
      return <LedgerPage records={records} onSelectRecord={setSelectedRecord} />;
    }
    if (route.page === "settings") {
      return (
        <SettingsPage
          status={status}
          onOpenAssistant={() => {
            /* TODO: open onboarding wizard */
          }}
        />
      );
    }
    return null;
  })();

  return (
    <>
      <AppShell
        route={route}
        navigate={navigate}
        connected={connected}
        escalationCount={escalationCount}
        onOpenEscalations={() => setShowEscalations(true)}
        crumbs={crumbs}
      >
        {loading ? (
          <div style={{ padding: 40, color: "var(--color-muted)", fontSize: 13 }}>Loading…</div>
        ) : (
          pageContent
        )}
      </AppShell>

      {error ? (
        <div
          style={{
            position: "fixed",
            bottom: 18,
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(214, 102, 102, 0.1)",
            border: "1px solid rgba(214, 102, 102, 0.3)",
            borderRadius: 6,
            padding: "9px 16px",
            fontSize: 12,
            color: "var(--color-status-red)",
            zIndex: 60,
          }}
        >
          {error}
        </div>
      ) : null}

      <RecordDetail
        record={selectedRecord}
        open={!!selectedRecord}
        onClose={() => setSelectedRecord(null)}
      />
      <NewCampaignSlideOver
        open={showNewCampaign}
        onClose={() => setShowNewCampaign(false)}
        status={status}
        refresh={refresh}
      />
      <EscalationsSlideOver
        open={showEscalations}
        onClose={() => setShowEscalations(false)}
        refresh={refresh}
      />
      <InterventionSlideOver
        open={showIntervention}
        onClose={() => setShowIntervention(false)}
        campaigns={campaigns}
        refresh={refresh}
      />
      <SettingsDrawer
        open={showSettings}
        onClose={() => setShowSettings(false)}
        status={status}
        refresh={refresh}
      />
    </>
  );
}
