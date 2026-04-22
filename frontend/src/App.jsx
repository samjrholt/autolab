import { useMemo, useState } from "react";

import { useLabState } from "./hooks/useLabState";
import Shell from "./components/Shell";
import Overview from "./components/Overview";
import CampaignTab from "./components/CampaignTab";
import Provenance from "./components/Provenance";
import RecordDetail from "./components/RecordDetail";
import NewCampaignSlideOver from "./components/NewCampaignSlideOver";
import EscalationsSlideOver from "./components/EscalationsSlideOver";
import InterventionSlideOver from "./components/InterventionSlideOver";
import SettingsDrawer from "./components/SettingsDrawer";

function App() {
  const { status, records, events, connected, loading, error, etaByCampaign, counts, refresh } =
    useLabState();

  const [activeTab, setActiveTab] = useState("overview");
  const [selectedCampaignId, setSelectedCampaignId] = useState(null);

  // Slide-over state
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [showNewCampaign, setShowNewCampaign] = useState(false);
  const [showEscalations, setShowEscalations] = useState(false);
  const [showIntervention, setShowIntervention] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const campaigns = status?.campaigns || [];
  const resources = status?.resources || [];
  const escalationCount = status?.escalations?.length || 0;

  // Navigate to Campaign tab with a specific campaign selected
  const goToCampaign = (campaign) => {
    setSelectedCampaignId(campaign.campaign_id);
    setActiveTab("campaign");
  };

  // Active tab content
  const tabContent = useMemo(() => {
    switch (activeTab) {
      case "overview":
        return (
          <Overview
            status={status}
            records={records}
            counts={counts}
            campaigns={campaigns}
            resources={resources}
            etaByCampaign={etaByCampaign}
            onSelectCampaign={goToCampaign}
            onShowResources={() => setShowSettings(true)}
            onSelectRecord={setSelectedRecord}
          />
        );
      case "campaign":
        return (
          <CampaignTab
            campaigns={campaigns}
            records={records}
            resources={resources}
            etaByCampaign={etaByCampaign}
            selectedCampaignId={selectedCampaignId}
            onSelectRecord={setSelectedRecord}
            onOpenIntervention={() => setShowIntervention(true)}
            onOpenNewCampaign={() => setShowNewCampaign(true)}
            refresh={refresh}
          />
        );
      case "provenance":
        return (
          <Provenance
            records={records}
            loading={loading}
            onSelectRecord={setSelectedRecord}
            onFilter={(f) => refresh(f)}
          />
        );
      default:
        return null;
    }
  }, [activeTab, status, records, counts, campaigns, resources, etaByCampaign, selectedCampaignId, loading]);

  return (
    <>
      <Shell
        activeTab={activeTab}
        onTabChange={setActiveTab}
        connected={connected}
        escalationCount={escalationCount}
        onOpenEscalations={() => setShowEscalations(true)}
        onOpenNewCampaign={() => setShowNewCampaign(true)}
        onOpenSettings={() => setShowSettings(true)}
      >
        {tabContent}
      </Shell>

      {/* Error bar */}
      {error && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-[var(--color-status-red)]/10 border border-[var(--color-status-red)]/30 rounded-xl px-5 py-3 text-[13px] text-[var(--color-status-red)] z-50">
          {error}
        </div>
      )}

      {/* Slide-overs */}
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

export default App;