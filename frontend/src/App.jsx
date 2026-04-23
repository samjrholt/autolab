import { useCallback, useMemo, useState } from "react";

import { useLabState } from "./hooks/useLabState";
import AppShell from "./shell/AppShell";

import CampaignsPage from "./pages/CampaignsPage";
import CampaignDetailPage from "./pages/CampaignDetailPage";
import ResourcesPage from "./pages/ResourcesPage";
import ResourceDetailPage from "./pages/ResourceDetailPage";
import CapabilitiesPage from "./pages/CapabilitiesPage";
import CapabilityDetailPage from "./pages/CapabilityDetailPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import WorkflowDetailPage from "./pages/WorkflowDetailPage";
import LedgerPage from "./pages/LedgerPage";
import SettingsPage from "./pages/SettingsPage";
import AssistantPage from "./pages/AssistantPage";
import DesignerPage from "./pages/DesignerPage";

import RecordDetail from "./components/RecordDetail";
import NewCampaignSlideOver from "./components/NewCampaignSlideOver";
import EscalationsSlideOver from "./components/EscalationsSlideOver";
import InterventionSlideOver from "./components/InterventionSlideOver";

const CRUMBS = {
  campaigns: ["Campaigns"],
  resources: ["Library", "Resources"],
  capabilities: ["Library", "Capabilities"],
  workflows: ["Library", "Workflows"],
  ledger: ["Ledger"],
  assistant: ["Setup", "Assistant"],
  settings: ["Settings"],
};

const DESIGNER_CRUMBS = {
  resource: ["Library", "Resources", "New"],
  workflow: ["Library", "Workflows", "New"],
  capability: ["Library", "Capabilities", "New"],
};

export default function App() {
  const { status, records, events, connected, loading, error, refresh } = useLabState();

  const [route, setRoute] = useState({ page: "campaigns" });
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [showNewCampaign, setShowNewCampaign] = useState(false);
  const [showEscalations, setShowEscalations] = useState(false);
  const [showIntervention, setShowIntervention] = useState(false);

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

  const selectedResource = useMemo(
    () => (route.page === "resource" ? resources.find((r) => r.name === route.name) : null),
    [route, resources],
  );

  const selectedWorkflow = useMemo(
    () => (route.page === "workflow" ? workflows.find((w) => w.name === route.name) : null),
    [route, workflows],
  );

  const selectedCapability = useMemo(
    () =>
      route.page === "capability"
        ? tools.find((t) => (t.capability || t.name) === route.name)
        : null,
    [route, tools],
  );

  const crumbs = useMemo(() => {
    if (route.page === "campaign" && selectedCampaign) {
      return ["Campaigns", selectedCampaign.objective?.description || selectedCampaign.name || selectedCampaign.campaign_id];
    }
    if (route.page === "resource") return ["Library", "Resources", route.name];
    if (route.page === "workflow") return ["Library", "Workflows", route.name];
    if (route.page === "capability") return ["Library", "Capabilities", route.name];
    if (route.page === "designer") return DESIGNER_CRUMBS[route.kind] || ["Designer"];
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
          <button type="button" className="btn-secondary" onClick={() => navigate({ page: "campaigns" })}>
            ← Back to campaigns
          </button>
        </div>
      );
    }

    if (route.page === "resources") {
      return (
        <ResourcesPage
          resources={resources}
          onAddResource={() => navigate({ page: "designer", kind: "resource" })}
          onSelectResource={(r) => navigate({ page: "resource", name: r.name })}
        />
      );
    }
    if (route.page === "resource") {
      return (
        <ResourceDetailPage
          resource={selectedResource}
          refresh={refresh}
          onBack={() => navigate({ page: "resources" })}
        />
      );
    }

    if (route.page === "capabilities") {
      return (
        <CapabilitiesPage
          tools={tools}
          onRegister={() => navigate({ page: "designer", kind: "capability" })}
          onSelectCapability={(t) =>
            navigate({ page: "capability", name: t.capability || t.name })
          }
        />
      );
    }
    if (route.page === "capability") {
      return (
        <CapabilityDetailPage
          tool={selectedCapability}
          onBack={() => navigate({ page: "capabilities" })}
        />
      );
    }

    if (route.page === "workflows") {
      return (
        <WorkflowsPage
          workflows={workflows}
          onCreate={() => navigate({ page: "designer", kind: "workflow" })}
          onSelectWorkflow={(w) => navigate({ page: "workflow", name: w.name })}
        />
      );
    }
    if (route.page === "workflow") {
      return (
        <WorkflowDetailPage
          workflow={selectedWorkflow}
          onBack={() => navigate({ page: "workflows" })}
          onEdit={() =>
            navigate({ page: "designer", kind: "workflow", editing: selectedWorkflow })
          }
          refresh={refresh}
        />
      );
    }

    if (route.page === "designer") {
      const backTarget = {
        resource: "resources",
        workflow: "workflows",
        capability: "capabilities",
      }[route.kind];
      return (
        <DesignerPage
          kind={route.kind}
          status={status}
          refresh={refresh}
          initial={route.editing || null}
          onDone={() => navigate({ page: backTarget })}
        />
      );
    }

    if (route.page === "ledger") {
      return <LedgerPage records={records} onSelectRecord={setSelectedRecord} />;
    }
    if (route.page === "assistant") {
      return <AssistantPage status={status} refresh={refresh} />;
    }
    if (route.page === "settings") {
      return (
        <SettingsPage
          status={status}
          onOpenAssistant={() => navigate({ page: "assistant" })}
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
    </>
  );
}
