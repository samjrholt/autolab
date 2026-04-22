import { useCallback, useEffect, useMemo, useState } from "react";

import { getJson, wsUrl } from "../lib/api";


const LEDGER_LIMIT = 320;


export function useLabState() {
  const [status, setStatus] = useState(null);
  const [records, setRecords] = useState([]);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [etaByCampaign, setEtaByCampaign] = useState({});

  const refresh = useCallback(async (filter = "") => {
    try {
      setError("");
      const ledgerPath = filter
        ? `/ledger?limit=${LEDGER_LIMIT}&filter=${encodeURIComponent(filter)}`
        : `/ledger?limit=${LEDGER_LIMIT}`;
      const [nextStatus, nextLedger] = await Promise.all([
        getJson("/status"),
        getJson(ledgerPath),
      ]);
      setStatus(nextStatus);
      setRecords(nextLedger.records || []);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    let disposed = false;
    let socket;

    const connect = () => {
      socket = new WebSocket(wsUrl("/events"));
      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!disposed) {
          window.setTimeout(connect, 1200);
        }
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          setEvents((previous) => [...previous.slice(-119), message]);
          if (
            message.kind?.startsWith("record.") ||
            message.kind?.startsWith("campaign.") ||
            message.kind?.startsWith("resource.") ||
            message.kind?.startsWith("tool.") ||
            message.kind?.startsWith("workflow.")
          ) {
            refresh();
          }
        } catch {
          // Ignore malformed events rather than taking down the shell.
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      socket?.close();
    };
  }, [refresh]);

  useEffect(() => {
    if (!status?.campaigns?.length) {
      setEtaByCampaign({});
      return undefined;
    }

    let disposed = false;

    const poll = async () => {
      const running = (status.campaigns || []).filter((campaign) =>
        ["running", "queued", "paused"].includes(campaign.status),
      );
      if (!running.length) {
        if (!disposed) {
          setEtaByCampaign({});
        }
        return;
      }
      const entries = await Promise.all(
        running.map(async (campaign) => {
          try {
            const eta = await getJson(`/estimate/eta?campaign_id=${campaign.campaign_id}`);
            return [campaign.campaign_id, eta];
          } catch {
            return [campaign.campaign_id, null];
          }
        }),
      );
      if (!disposed) {
        setEtaByCampaign(Object.fromEntries(entries));
      }
    };

    poll();
    const interval = window.setInterval(poll, 4000);
    return () => {
      disposed = true;
      window.clearInterval(interval);
    };
  }, [status]);

  const counts = useMemo(() => status?.record_counts || {}, [status]);

  return {
    status,
    records,
    events,
    connected,
    loading,
    error,
    etaByCampaign,
    counts,
    refresh,
  };
}
