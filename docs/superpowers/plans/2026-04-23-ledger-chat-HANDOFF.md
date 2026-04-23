# Ledger Chat — Implementation Handoff

**Status as of 2026-04-23:** Tasks 1 and 2 of 11 complete and committed. Task 3 partially written (file exists, uncommitted, **unvalidated**). Tasks 4–11 untouched.

**Primary spec:** [`2026-04-23-ledger-chat.md`](./2026-04-23-ledger-chat.md) in this same directory. It contains every task's full code, file paths, commands, and commit messages. The handoff document you are reading is a *resumption overlay* on top of that plan, not a replacement.

**Design rationale:** `C:\Users\holtsamu\.claude\plans\i-have-recently-created-optimized-porcupine.md` (on the owner's machine) — the decision log behind the design, plus explicit notes on what is out of scope this week. If that file isn't accessible to you, the `## Context` and `## Out of scope` sections of the main plan cover the essentials.

---

## Where the repo is

**Branch:** `master` (not a feature branch — owner is running the whole hackathon on master and asked to continue that pattern).

**Commits already landed:**

```
2613cc6 feat(chat): flatten ledger records into a pandas DataFrame view
2ab3f14 chore(chat): scaffold chat package and add jupyter_client deps
```

**Files already created and committed:**

- `src/autolab/server/chat/__init__.py` (empty package marker)
- `src/autolab/server/chat/ledger_frame.py` (Task 2 — exports `build_ledger_frame`, `describe_columns`)
- `pyproject.toml` — now depends on `jupyter_client>=8.6` and `ipykernel>=6.29`
- `pixi.lock` — refreshed

**Runtime directories present (gitignored):**

- `var/chats/`
- `var/chat-kernels/`

**Uncommitted file — needs validation before committing:**

- `src/autolab/server/chat/kernel.py` — this is the full Task 3 code, copied verbatim from the plan by a previous subagent. **It was never run through the sanity check** because the subagent was interrupted. Treat this as "Task 3 step 1 done, steps 2–3 pending."

---

## Resuming

### Immediate next action: finish Task 3

1. Open the existing `src/autolab/server/chat/kernel.py`. Diff it against Task 3 Step 1 in the main plan ([`2026-04-23-ledger-chat.md`](./2026-04-23-ledger-chat.md#task-3-kernel-manager)). It should match verbatim; if not, align it with the plan.
2. Run Task 3 Step 2 (the sanity check) — the exact command is in the plan. Expected output: `figs: 1`, `err: None`, and a printed DataFrame.
3. If the sanity check passes, run Task 3 Step 3: `git add src/autolab/server/chat/kernel.py && git commit -m "feat(chat): per-chat Jupyter kernel manager with figure capture"`.
4. If the sanity check fails, do NOT paper over it. Report the error and fix it in `kernel.py` (likely candidates: Windows path quoting in the inline python `-c` call, or `jupyter_client` API differences between installed version and what the plan assumed). This is the foundational piece; silent bugs here will cascade through Tasks 5 and 6.

### Remaining tasks (4–11)

Follow the main plan file task-by-task. Summary:

| Task | Summary | Complexity | Depends on |
|---|---|---|---|
| 4 | `src/autolab/server/chat/store.py` — chat JSON persistence | low | — |
| 5 | `src/autolab/server/chat/agent.py` — Anthropic tool-use loop | high | 3 |
| 6 | `src/autolab/server/chat/routes.py` + register router — `/chats` REST + WS | high | 2, 3, 4, 5 |
| 7 | Remove old `/analysis/query` and `_analysis_*` helpers from `src/autolab/server/app.py` | low | 6 |
| 8 | `frontend/src/pages/ChatPage.jsx` + sidebar + chat.css + App.jsx nav rewire | medium | — |
| 9 | `frontend/src/pages/chat/{MessageThread,PromptInput}.jsx` + WS wiring | medium | 6, 8 |
| 10 | Polish: markdown rendering, live title, example prompts | low | 9 |
| 11 | End-to-end verification against live lab + sensor demo data | — | all |

---

## Known quirks / gotchas for the next team

1. **Deps location.** `jupyter_client` and `ipykernel` belong in `pyproject.toml` `[project] dependencies`, not in `pixi.toml`. Pixi pulls them via the editable `autolab` install.
2. **Python invocation.** Shell is bash on Windows 11. Use `pixi run python -c "..."` — triple-quoted heredocs are risky; prefer `python -c` with single-line code or writing a temp `.py` file (remember to clean it up). A previous subagent left behind `_smoke_kernel*.py` files at the repo root; those have been removed but the pattern is a footgun.
3. **Lab API surface in Task 6.** The plan uses `lab.records()` and `lab.list_campaigns()` in `routes.py`. Verify those match the actual Lab class — if the method names differ, adjust. `grep -n "def records\|def list_campaigns" src/autolab/lab*.py` is the fastest check.
4. **App wiring in Task 6.** The plan says to register `chat_router` "near where other routers are". [src/autolab/server/app.py](../../src/autolab/server/app.py) currently uses `@app.post(...)` decorators rather than routers — pick a spot right after `app = FastAPI(...)` is constructed.
5. **Nav entry in Task 8.** The "Analysis" label/route lives in `frontend/src/App.jsx` **and** in whatever nav component `AppShell` uses. `grep -rn "analysis" frontend/src/` will find all of them. The plan's `App.jsx` snippet only covers one of the two sites.
6. **Offline mode.** If `ANTHROPIC_API_KEY` is unset, `agent.run_turn` returns a stub. This is intentional — tests and the test-lab server should still boot without a key. Don't remove the offline branch.
7. **Frontend build.** `cd frontend && npm run build` is the verification step; the production bundle lands in `src/autolab/server/static/`.

---

## Out of scope — do not build

These are explicitly deferred to a later PR and must stay out of this one to keep the change reviewable:

- Pin-to-ledger (📌 button + `AnalysisClaim` record writing via orchestrator)
- Kernel orphan cleanup on Lab restart
- Ledger-staleness banner / version comparison
- Large PNG offload to disk
- Token-level streaming of assistant text (block-level is fine)
- Any `react()` integration consuming analysis claims

---

## Execution recipe (if you're using subagent-driven-development)

Owner preferences set in the prior session:

- **Branch:** master, no new branch
- **Subagent model:** sonnet (not haiku)
- **Review cadence:** one final combined code review at the end of all 11 tasks, not per-task spec+quality reviews. Owner gates the work through manual demo testing in Task 11.

**Prompt template per task:** point the subagent at the plan file with the task number. Do NOT paste the full task text into the prompt — the plan file is in-repo and self-contained. Instruct the subagent to read only its assigned task, to stay on master, and to run the plan's sanity-check step before committing. Always ask for `git log --oneline -3` in the report so you can verify the commit.

**Between-task gate for the controller:** `git log --oneline -N` to confirm the commit, `git status` to confirm no stray files, then mark todo complete and dispatch the next.

---

## If a task blocks

Do not invent workarounds when the plan's code doesn't fit the actual codebase. Instead, stop and surface:

- What you tried
- What failed (exact error)
- Which plan step you're on
- What you think should change in the plan

The plan is a living spec; update it in the same commit that deviates from it.
