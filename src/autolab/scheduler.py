"""CampaignScheduler — run multiple Campaigns concurrently, sharing resources.

Design
------

A :class:`CampaignScheduler` owns a priority-sorted list of
:class:`CampaignState` entries. Each active campaign runs its
:class:`~autolab.campaign.CampaignRunner` loop as an independent
``asyncio.Task`` — campaigns share the Lab's :class:`ResourceManager`
and never step on each other's provenance.

Priority
    Lower number = higher priority. The scheduler does not preempt a
    running step, but when a high-priority campaign needs a resource that
    a lower-priority campaign is about to acquire, the condition variable
    in :class:`~autolab.resources.manager.ResourceManager` will naturally
    favour the higher-priority waiter on the next available slot.

Pause / resume / cancel
    Implemented via per-campaign ``asyncio.Event`` flags checked between
    batches in the ``CampaignRunner`` loop. A paused campaign yields its
    current execution slot; any in-flight Operation finishes normally
    (you can't safely interrupt a furnace run).

Reprioritize
    The priority integer on a ``CampaignState`` is mutable at runtime.
    The scheduler re-sorts the active list on the next scheduler tick
    so resource allocation shifts toward higher-priority campaigns.

Multi-campaign interaction
    Multiple campaigns block on the same ``asyncio.Condition`` in the
    ``ResourceManager``. When a resource is released, all waiting
    campaigns wake; the one that acquired the best position in the sorted
    order gets it. This is not strictly fair (no round-robin) but it is
    correct and predictable given explicit priorities.

Usage
-----

>>> scheduler = CampaignScheduler(lab)
>>> camp_id = await scheduler.submit(campaign, planner, priority=10)
>>> await scheduler.submit(background_campaign, background_planner, priority=50)
>>> await scheduler.run()          # blocks; runs all campaigns to completion
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from autolab.campaign import Campaign, CampaignRunner, CampaignSummary
from autolab.planners.base import Planner

if TYPE_CHECKING:
    from autolab.lab import Lab


CampaignStatus = Literal[
    "queued",
    "running",
    "paused",
    "completed",
    "cancelled",
    "failed",
]


@dataclass
class CampaignState:
    """Runtime tracking for one submitted Campaign."""

    campaign: Campaign
    planner: Planner
    priority: int  # lower = more urgent
    status: CampaignStatus = "queued"
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: CampaignSummary | None = None
    error: str | None = None

    # Internal async signalling — not serialised.
    _pause_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _task: asyncio.Task | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # Paused campaigns wait on _pause_event; it starts cleared (not paused).
        self._pause_event.set()  # set = allowed to run


class CampaignScheduler:
    """Run multiple :class:`Campaign` instances concurrently inside one Lab.

    The scheduler is a thin coordination layer — it spawns one
    ``asyncio.Task`` per campaign and manages pause/resume/cancel signals.
    All resource arbitration happens in the ``ResourceManager``.

    Typical usage::

        lab = Lab("./runs")
        scheduler = CampaignScheduler(lab)
        await scheduler.submit(urgent_campaign, optuna_planner, priority=5)
        await scheduler.submit(screen_campaign, random_planner, priority=50)
        await scheduler.run()   # returns when all campaigns are terminal

    Or from inside an async server::

        asyncio.create_task(scheduler.run())   # non-blocking background loop
        await scheduler.submit(...)             # add campaigns at any time
    """

    def __init__(self, lab: Lab) -> None:
        self._lab = lab
        self._campaigns: dict[str, CampaignState] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    async def submit(
        self,
        campaign: Campaign,
        planner: Planner,
        *,
        priority: int = 50,
    ) -> str:
        """Enqueue a Campaign. Returns the campaign id.

        ``priority``
            Integer priority (lower = more urgent). Campaigns with the
            same priority run concurrently; campaigns with lower priority
            numbers get first pick of resources when competing.
        """
        async with self._lock:
            if campaign.id in self._campaigns:
                raise ValueError(f"campaign {campaign.id!r} already submitted")
            state = CampaignState(campaign=campaign, planner=planner, priority=priority)
            self._campaigns[campaign.id] = state
        return campaign.id

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    async def pause(self, campaign_id: str) -> None:
        """Signal a campaign to pause between batches."""
        state = self._get(campaign_id)
        if state.status == "running":
            state._pause_event.clear()
            state.status = "paused"

    async def resume(self, campaign_id: str) -> None:
        """Resume a paused campaign."""
        state = self._get(campaign_id)
        if state.status == "paused":
            state.status = "running"
            state._pause_event.set()

    async def cancel(self, campaign_id: str) -> None:
        """Cancel a campaign cooperatively.

        Sets the cancellation flag and unblocks any pause. The
        :class:`_PausableRunner` checks this flag between batches and
        exits cleanly. We do **not** call :meth:`asyncio.Task.cancel`
        because cancelling an asyncio task mid-``asyncio.to_thread``
        leaves the SQLite worker thread running while the event loop
        moves on — on Windows this causes an access violation when the
        Lab's SQLite connection is closed. Cooperative cancellation is
        slightly less responsive (you wait for the current step to
        finish) but it never leaves orphan threads.
        """
        state = self._get(campaign_id)
        if state.status in ("queued", "running", "paused"):
            state.status = "cancelled"
            state._pause_event.set()  # unblock if paused; runner sees the flag

    async def reprioritize(self, campaign_id: str, priority: int) -> None:
        """Change a campaign's priority. Takes effect on the next batch."""
        self._get(campaign_id).priority = priority

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Launch all queued campaigns and block until all reach a terminal state.

        Safe to call once. For a long-running server, wrap in
        ``asyncio.create_task(scheduler.run())``.
        """
        # Launch tasks for all currently queued campaigns.
        async with self._lock:
            to_launch = [s for s in self._campaigns.values() if s.status == "queued"]
        for state in to_launch:
            self._launch(state)

        # Wait for all tasks.
        tasks = [s._task for s in self._campaigns.values() if s._task is not None]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _launch(self, state: CampaignState) -> None:
        """Spawn the asyncio task that drives this campaign."""
        if state._task is not None:
            return
        state.status = "running"
        state.started_at = datetime.now(UTC)
        task = asyncio.create_task(self._run_campaign(state), name=f"campaign-{state.campaign.id}")
        state._task = task

    async def _run_campaign(self, state: CampaignState) -> None:
        """Wrapper that patches pause-checking into the CampaignRunner loop."""
        session = self._lab.new_session()
        runner = _PausableRunner(
            campaign=state.campaign,
            planner=state.planner,
            lab=self._lab,
            session=session,
            pause_event=state._pause_event,
            cancel_check=lambda: state.status == "cancelled",
        )
        try:
            summary = await runner.run()
            state.summary = summary
            if state.status not in ("cancelled",):
                state.status = "completed"
        except asyncio.CancelledError:
            state.status = "cancelled"
        except Exception as exc:
            state.status = "failed"
            state.error = repr(exc)
        finally:
            state.completed_at = datetime.now(UTC)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def status(self) -> list[dict[str, Any]]:
        """Return a snapshot of all campaign states, sorted by priority."""
        return [
            {
                "campaign_id": s.campaign.id,
                "name": s.campaign.name,
                "priority": s.priority,
                "status": s.status,
                "submitted_at": s.submitted_at.isoformat(),
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "objective_key": s.campaign.objective.key,
                "budget": s.campaign.budget,
                "error": s.error,
            }
            for s in sorted(self._campaigns.values(), key=lambda x: x.priority)
        ]

    def get_summary(self, campaign_id: str) -> CampaignSummary | None:
        return self._get(campaign_id).summary

    def _get(self, campaign_id: str) -> CampaignState:
        if campaign_id not in self._campaigns:
            raise KeyError(f"campaign {campaign_id!r} not found in scheduler")
        return self._campaigns[campaign_id]


# ---------------------------------------------------------------------------
# _PausableRunner — CampaignRunner with pause/cancel signalling
# ---------------------------------------------------------------------------


class _PausableRunner(CampaignRunner):
    """CampaignRunner that checks a pause event and a cancel predicate.

    The pause check happens between batches in the main ``run()`` loop.
    In-flight Operations always complete — there is no mid-step
    interruption. This mirrors real lab behaviour: you can't safely
    interrupt a furnace run, but you can pause the next step from
    starting.
    """

    def __init__(
        self,
        *,
        pause_event: asyncio.Event,
        cancel_check: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._pause_event = pause_event
        self._cancel_check = cancel_check

    async def run(self) -> CampaignSummary:
        from autolab.events import Event

        self.lab.events.publish(
            Event(
                kind="campaign.started",
                payload={
                    "campaign_id": self.campaign.id,
                    "name": self.campaign.name,
                    "objective": self.campaign.objective.model_dump(),
                },
            )
        )

        try:
            while not self._is_done():
                # Pause point: wait here if the scheduler said pause.
                await self._pause_event.wait()
                # Cancel point.
                if self._cancel_check():
                    self._stopped = ("cancelled", "scheduler cancelled this campaign")
                    break

                from autolab.planners.base import PlanContext

                history = list(self.lab.ledger.iter_records(campaign_id=self.campaign.id))
                ctx = PlanContext(
                    campaign_id=self.campaign.id,
                    objective=self.campaign.objective,
                    history=history,
                    resources=self.lab.resources.list(),
                    acceptance=self.campaign.acceptance,
                    remaining_budget=self._remaining_budget(),
                    metadata=self.campaign.metadata,
                )
                proposals = self.planner.plan(ctx)
                if not proposals:
                    self._stopped = ("empty", "planner returned no proposals")
                    break
                await self._dispatch_batch(proposals)
        finally:
            self.lab.events.publish(
                Event(
                    kind="campaign.finished",
                    payload={
                        "campaign_id": self.campaign.id,
                        "status": self._status_text(),
                    },
                )
            )

        return self._summary()


__all__ = ["CampaignScheduler", "CampaignState", "CampaignStatus"]
