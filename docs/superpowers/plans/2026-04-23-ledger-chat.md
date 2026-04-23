# Ledger Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-shot NL-to-chart Analysis page with an agentic "Ledger Chat" — Opus 4.7 drives a persistent Jupyter kernel with a preloaded `ledger` DataFrame, writes pandas/matplotlib, sees its own figures, iterates. Chats persist and are resumable.

**Architecture:** One IPython kernel per chat (via `jupyter_client`). One tool exposed to Claude: `exec_python(code)`. Chats stored as JSON on disk. New FastAPI `/chats` namespace with a WebSocket for streaming. New React ChatPage replacing AnalysisPage.

**Tech Stack:** Python 3.12, FastAPI, jupyter_client + ipykernel, Anthropic SDK (Opus 4.7), pandas + matplotlib, React/Vite.

**Scope note — MVP only.** Pin-to-ledger, kernel orphan cleanup, ledger-staleness banner, and large-figure-as-file offload are explicitly **deferred** to v2. Deliver the demo-visible core first.

**Design doc:** `C:\Users\holtsamu\.claude\plans\i-have-recently-created-optimized-porcupine.md`

---

## File Structure

**New files:**

- `src/autolab/server/chat/__init__.py` — package marker
- `src/autolab/server/chat/ledger_frame.py` — ledger → `pd.DataFrame`
- `src/autolab/server/chat/kernel.py` — per-chat IPython kernel manager
- `src/autolab/server/chat/store.py` — chat JSON persistence
- `src/autolab/server/chat/agent.py` — Anthropic tool-use loop
- `src/autolab/server/chat/routes.py` — FastAPI `/chats` router + WS
- `frontend/src/pages/ChatPage.jsx` — top-level chat page
- `frontend/src/pages/chat/ChatSidebar.jsx` — list of saved chats
- `frontend/src/pages/chat/MessageThread.jsx` — messages + code cells + figures
- `frontend/src/pages/chat/PromptInput.jsx` — input + refresh button
- `frontend/src/pages/chat/chat.css` — scoped styling for the chat page

**Modified:**

- `pyproject.toml` — add `jupyter_client`, `ipykernel` deps
- `src/autolab/server/app.py` — register chat router, remove `/analysis/query` and `_analysis_*` helpers (kept adapter if still needed)
- `frontend/src/App.jsx` — nav label "Analysis" → "Chat", route "analysis" → ChatPage

---

## Task 1: Dependencies and scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `src/autolab/server/chat/__init__.py` (empty)
- Create directory: `var/chats/` and `var/chat-kernels/`

- [ ] **Step 1: Add deps to `pyproject.toml`**

Find the `[project]` dependency block and add:

```toml
    "jupyter_client>=8.6",
    "ipykernel>=6.29",
```

- [ ] **Step 2: Install**

```bash
pixi install
```

- [ ] **Step 3: Create package + storage dirs**

```bash
mkdir -p src/autolab/server/chat
touch src/autolab/server/chat/__init__.py
mkdir -p var/chats var/chat-kernels
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml pixi.lock src/autolab/server/chat/__init__.py
git commit -m "chore(chat): scaffold chat package and add jupyter_client deps"
```

---

## Task 2: Ledger → DataFrame helper

**Files:**
- Create: `src/autolab/server/chat/ledger_frame.py`

Reuse the flattening logic at [src/autolab/server/app.py:1200](src/autolab/server/app.py#L1200) (`_analysis_rows`) as a starting point but return a DataFrame.

- [ ] **Step 1: Write `build_ledger_frame`**

```python
"""Build a flat pandas DataFrame view of the ledger for chat kernels."""
from __future__ import annotations

from typing import Any

import pandas as pd


def build_ledger_frame(records: list[Any], campaigns: dict[str, Any]) -> pd.DataFrame:
    """Flatten records into one row per record with inputs.* and outputs.* columns.

    `records` is the full ledger list (objects with to_dict()).
    `campaigns` maps campaign_id -> campaign dict (for name and objective lookups).
    """
    rows: list[dict[str, Any]] = []
    for rec in records:
        d = rec.to_dict() if hasattr(rec, "to_dict") else dict(rec)
        campaign_id = d.get("campaign_id")
        campaign = campaigns.get(campaign_id) or {}
        base = {
            "id": d.get("id"),
            "campaign_id": campaign_id,
            "campaign_name": campaign.get("name"),
            "capability": d.get("capability"),
            "module": d.get("module"),
            "status": d.get("status"),
            "started_at": d.get("started_at"),
            "completed_at": d.get("completed_at"),
            "trial": (d.get("metadata") or {}).get("trial"),
            "parent_ids": d.get("parent_ids") or [],
        }
        for k, v in (d.get("inputs") or {}).items():
            base[f"inputs.{k}"] = v
        for k, v in (d.get("outputs") or {}).items():
            base[f"outputs.{k}"] = v
        rows.append(base)
    df = pd.DataFrame(rows)
    for col in ("started_at", "completed_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


def describe_columns(df: pd.DataFrame) -> str:
    """Compact schema description for the agent system prompt."""
    if df.empty:
        return "(no records yet)"
    lines = []
    for col in df.columns:
        sample = df[col].dropna()
        dtype = str(df[col].dtype)
        example = sample.iloc[0] if not sample.empty else None
        lines.append(f"- {col}: {dtype}  e.g. {example!r}")
    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add src/autolab/server/chat/ledger_frame.py
git commit -m "feat(chat): flatten ledger records into a pandas DataFrame view"
```

---

## Task 3: Kernel manager

**Files:**
- Create: `src/autolab/server/chat/kernel.py`

This is the most infrastructural piece. Build it carefully; everything else depends on it.

- [ ] **Step 1: Write `ChatKernelManager`**

```python
"""Per-chat IPython kernel management via jupyter_client.

One kernel per chat_id. Figures captured as PNG base64. Lightweight async
execute() that collects IOPub messages until the shell channel returns idle.
"""
from __future__ import annotations

import asyncio
import base64
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jupyter_client.manager import AsyncKernelManager


_KERNEL_DIR = Path("var/chat-kernels")
_KERNEL_DIR.mkdir(parents=True, exist_ok=True)


_BOOTSTRAP = """
import base64, io, pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def _autolab_load_ledger(b64):
    global ledger
    ledger = pickle.loads(base64.b64decode(b64))
    return ("ledger: ", ledger.shape, list(ledger.columns)[:12])
"""


@dataclass
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    figures: list[str] = field(default_factory=list)  # base64 PNGs
    error: str | None = None
    result_repr: str | None = None


class ChatKernelManager:
    """Holds one AsyncKernelManager per chat_id."""

    def __init__(self) -> None:
        self._kernels: dict[str, AsyncKernelManager] = {}
        self._clients: dict[str, Any] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, chat_id: str) -> asyncio.Lock:
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    async def get_or_start(self, chat_id: str) -> Any:
        if chat_id in self._clients:
            return self._clients[chat_id]
        km = AsyncKernelManager(
            connection_file=str(_KERNEL_DIR / f"{chat_id}.json"),
        )
        await km.start_kernel()
        client = km.client()
        client.start_channels()
        await client.wait_for_ready(timeout=30)
        self._kernels[chat_id] = km
        self._clients[chat_id] = client
        await self._execute_raw(client, _BOOTSTRAP, timeout=30)
        return client

    async def bind_ledger(self, chat_id: str, df: Any) -> ExecResult:
        """Pickle the DataFrame out-of-band and rebind `ledger` in the kernel."""
        client = await self.get_or_start(chat_id)
        blob = base64.b64encode(pickle.dumps(df)).decode()
        code = f"_autolab_load_ledger({blob!r})"
        return await self._execute_raw(client, code, timeout=30)

    async def execute(self, chat_id: str, code: str, timeout: float = 30.0) -> ExecResult:
        client = await self.get_or_start(chat_id)
        async with self._lock(chat_id):
            return await self._execute_raw(client, code, timeout)

    @staticmethod
    async def _execute_raw(client: Any, code: str, timeout: float) -> ExecResult:
        res = ExecResult()
        msg_id = client.execute(code, store_history=False)
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                res.error = f"timeout after {timeout}s"
                return res
            try:
                msg = await asyncio.wait_for(client.get_iopub_msg(), timeout=remaining)
            except asyncio.TimeoutError:
                res.error = f"timeout after {timeout}s"
                return res
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            mtype = msg["msg_type"]
            content = msg["content"]
            if mtype == "stream":
                if content.get("name") == "stderr":
                    res.stderr += content.get("text", "")
                else:
                    res.stdout += content.get("text", "")
            elif mtype in ("display_data", "execute_result"):
                data = content.get("data", {}) or {}
                if "image/png" in data:
                    res.figures.append(data["image/png"])
                if mtype == "execute_result" and "text/plain" in data:
                    res.result_repr = data["text/plain"]
            elif mtype == "error":
                res.error = "\n".join(content.get("traceback", []))
            elif mtype == "status" and content.get("execution_state") == "idle":
                return res

    async def shutdown(self, chat_id: str) -> None:
        client = self._clients.pop(chat_id, None)
        km = self._kernels.pop(chat_id, None)
        self._locks.pop(chat_id, None)
        if client is not None:
            client.stop_channels()
        if km is not None:
            await km.shutdown_kernel(now=True)
        cf = _KERNEL_DIR / f"{chat_id}.json"
        cf.unlink(missing_ok=True)


kernel_manager = ChatKernelManager()
```

- [ ] **Step 2: Sanity-run**

```bash
pixi run python -c "
import asyncio, pandas as pd
from autolab.server.chat.kernel import kernel_manager

async def go():
    df = pd.DataFrame({'x': [1,2,3], 'y': [10,20,30]})
    await kernel_manager.bind_ledger('smoke', df)
    r = await kernel_manager.execute('smoke', 'print(ledger); import matplotlib.pyplot as plt; plt.plot(ledger[\"x\"], ledger[\"y\"]); plt.show()')
    print('stdout:', r.stdout); print('figs:', len(r.figures)); print('err:', r.error)
    await kernel_manager.shutdown('smoke')

asyncio.run(go())
"
```

Expected: prints the DataFrame, `figs: 1`, `err: None`.

- [ ] **Step 3: Commit**

```bash
git add src/autolab/server/chat/kernel.py
git commit -m "feat(chat): per-chat Jupyter kernel manager with figure capture"
```

---

## Task 4: Chat store

**Files:**
- Create: `src/autolab/server/chat/store.py`

- [ ] **Step 1: Write the store**

```python
"""Persist chats as JSON under var/chats/."""
from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any


_CHATS_DIR = Path("var/chats")
_CHATS_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_chat_id() -> str:
    return f"chat-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def _path(chat_id: str) -> Path:
    safe = chat_id.replace("/", "").replace("..", "")
    return _CHATS_DIR / f"{safe}.json"


def create_chat(title: str | None = None) -> dict[str, Any]:
    chat = {
        "id": new_chat_id(),
        "title": title or "New chat",
        "created_at": _now(),
        "updated_at": _now(),
        "messages": [],
    }
    save_chat(chat)
    return chat


def list_chats() -> list[dict[str, Any]]:
    out = []
    for p in sorted(_CHATS_DIR.glob("chat-*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append({
            "id": d.get("id"),
            "title": d.get("title"),
            "updated_at": d.get("updated_at"),
            "created_at": d.get("created_at"),
            "message_count": len(d.get("messages", [])),
        })
    return sorted(out, key=lambda x: x.get("updated_at") or "", reverse=True)


def load_chat(chat_id: str) -> dict[str, Any] | None:
    p = _path(chat_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_chat(chat: dict[str, Any]) -> None:
    chat["updated_at"] = _now()
    p = _path(chat["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(chat, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def delete_chat(chat_id: str) -> bool:
    p = _path(chat_id)
    if p.exists():
        p.unlink()
        return True
    return False


def append_message(chat_id: str, message: dict[str, Any]) -> dict[str, Any]:
    chat = load_chat(chat_id)
    if chat is None:
        raise FileNotFoundError(chat_id)
    chat["messages"].append(message)
    save_chat(chat)
    return chat
```

- [ ] **Step 2: Commit**

```bash
git add src/autolab/server/chat/store.py
git commit -m "feat(chat): JSON file store for resumable chats"
```

---

## Task 5: Agent loop

**Files:**
- Create: `src/autolab/server/chat/agent.py`

Drive Opus 4.7 with a single `exec_python` tool. Offline fallback mirrors the pattern in [src/autolab/agents/claude.py](src/autolab/agents/claude.py).

- [ ] **Step 1: Write the agent**

```python
"""Anthropic tool-use loop: Opus 4.7 drives a persistent kernel via `exec_python`."""
from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncIterator, Callable

from autolab.server.chat.kernel import ExecResult, kernel_manager


MODEL = "claude-opus-4-7"

SYSTEM = """You are an autonomous-lab data analyst inside autolab. You have access to a
persistent IPython kernel via the `exec_python` tool. The kernel already has:

  - `ledger` — a pandas DataFrame of every Record in the lab. One row per record.
    Columns include: id, campaign_id, campaign_name, capability, module, status,
    started_at, completed_at, trial, parent_ids, and flattened inputs.* / outputs.*.
  - `pd`, `np`, `plt` (matplotlib Agg backend).

Guidelines:
- Prefer small incremental cells. Inspect before plotting.
- Show figures with `plt.show()`. One figure per cell unless the question demands side-by-side.
- After tool calls, write a short prose narrative of what you found. Be specific — cite
  trial numbers, record ids, and numeric values from the DataFrame.
- If the user's question needs data that isn't in `ledger`, say so; do not make anything up.
- Never write to disk outside of plotting. Never network. Never mutate the ledger in ways
  that affect subsequent analysis (it's a snapshot — harmless, but avoid confusion).
"""

TOOLS = [
    {
        "name": "exec_python",
        "description": "Execute Python code in the persistent chat kernel. Returns stdout, stderr, and any matplotlib figures produced (as image blocks).",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python source to execute."}},
            "required": ["code"],
        },
    }
]


def _tool_result_blocks(res: ExecResult) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    text_chunks = []
    if res.stdout:
        text_chunks.append(f"stdout:\n{res.stdout}")
    if res.stderr:
        text_chunks.append(f"stderr:\n{res.stderr}")
    if res.result_repr:
        text_chunks.append(f"result:\n{res.result_repr}")
    if res.error:
        text_chunks.append(f"ERROR:\n{res.error}")
    if not text_chunks and not res.figures:
        text_chunks.append("(no output)")
    if text_chunks:
        parts.append({"type": "text", "text": "\n\n".join(text_chunks)})
    for b64 in res.figures:
        parts.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    return parts


def _is_offline() -> bool:
    return not os.environ.get("ANTHROPIC_API_KEY")


async def run_turn(
    chat_id: str,
    messages: list[dict[str, Any]],
    schema_hint: str,
    on_event: Callable[[dict[str, Any]], Any] | None = None,
    max_tool_calls: int = 10,
    wall_clock_s: float = 60.0,
) -> list[dict[str, Any]]:
    """Run one assistant turn. `messages` is the full history (Anthropic format).
    Returns the list of assistant content blocks to append to history.
    Emits events via `on_event` for streaming UI updates.
    """
    if _is_offline():
        stub = {"role": "assistant", "content": [
            {"type": "text", "text": "(offline stub — no ANTHROPIC_API_KEY set)"}
        ]}
        if on_event:
            await _maybe_await(on_event({"type": "message", "message": stub}))
        return stub["content"]

    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()

    system = SYSTEM + "\n\nDataFrame schema:\n" + schema_hint
    history = list(messages)
    accumulated: list[dict[str, Any]] = []
    deadline = asyncio.get_event_loop().time() + wall_clock_s
    calls = 0

    while True:
        if asyncio.get_event_loop().time() > deadline:
            accumulated.append({"type": "text", "text": "(stopped: wall-clock cap reached)"})
            break
        resp = await client.messages.create(
            model=MODEL, max_tokens=4096, system=system, tools=TOOLS, messages=history,
        )
        for block in resp.content:
            accumulated.append(block.model_dump())
        if on_event:
            for block in resp.content:
                await _maybe_await(on_event({"type": "block", "block": block.model_dump()}))

        if resp.stop_reason != "tool_use":
            break

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        tool_results: list[dict[str, Any]] = []
        for tu in tool_uses:
            if calls >= max_tool_calls:
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu.id,
                    "content": [{"type": "text", "text": "(stopped: max tool calls reached)"}],
                })
                continue
            calls += 1
            code = (tu.input or {}).get("code", "")
            if on_event:
                await _maybe_await(on_event({"type": "tool_call", "id": tu.id, "code": code}))
            res = await kernel_manager.execute(chat_id, code)
            blocks = _tool_result_blocks(res)
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": blocks})
            if on_event:
                await _maybe_await(on_event({
                    "type": "tool_result", "id": tu.id,
                    "stdout": res.stdout, "stderr": res.stderr,
                    "error": res.error, "figures": res.figures,
                }))

        history.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        history.append({"role": "user", "content": tool_results})
        if calls >= max_tool_calls:
            accumulated.append({"type": "text", "text": "(stopped: max tool calls reached)"})
            break

    return accumulated


async def _maybe_await(v: Any) -> None:
    if asyncio.iscoroutine(v):
        await v


async def autotitle(first_user_text: str) -> str:
    """Best-effort short title for a new chat."""
    if _is_offline():
        return first_user_text[:48] or "New chat"
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()
    try:
        resp = await client.messages.create(
            model=MODEL, max_tokens=40,
            system="Return a 3-6 word title for this analysis question. No quotes, no punctuation at the end.",
            messages=[{"role": "user", "content": first_user_text}],
        )
        for b in resp.content:
            if b.type == "text":
                return b.text.strip()[:64] or "New chat"
    except Exception:
        pass
    return first_user_text[:48] or "New chat"
```

- [ ] **Step 2: Commit**

```bash
git add src/autolab/server/chat/agent.py
git commit -m "feat(chat): Anthropic tool-use loop with exec_python and figure-as-image blocks"
```

---

## Task 6: Chat routes and WebSocket

**Files:**
- Create: `src/autolab/server/chat/routes.py`
- Modify: `src/autolab/server/app.py`

The WS is the hot path — user sends one message, server streams events, persists history, closes the turn.

- [ ] **Step 1: Write the router**

```python
"""FastAPI routes for /chats. The WS carries one user message per turn."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from autolab.server.chat import agent, store
from autolab.server.chat.kernel import kernel_manager
from autolab.server.chat.ledger_frame import build_ledger_frame, describe_columns


router = APIRouter(prefix="/chats", tags=["chat"])


def _lab(request: Request) -> Any:
    lab = getattr(request.app.state, "lab", None)
    if lab is None:
        raise HTTPException(503, "lab not ready")
    return lab


def _ledger_snapshot(lab: Any):
    records = list(lab.records())
    campaigns = {c["campaign_id"]: c for c in lab.list_campaigns()}
    df = build_ledger_frame(records, campaigns)
    return df, describe_columns(df)


class CreateChatBody(BaseModel):
    title: str | None = None


@router.post("")
async def create(body: CreateChatBody | None = None) -> dict[str, Any]:
    chat = store.create_chat((body.title if body else None))
    return chat


@router.get("")
async def list_() -> list[dict[str, Any]]:
    return store.list_chats()


@router.get("/{chat_id}")
async def get(chat_id: str) -> dict[str, Any]:
    c = store.load_chat(chat_id)
    if c is None:
        raise HTTPException(404, "chat not found")
    return c


@router.delete("/{chat_id}")
async def delete(chat_id: str) -> dict[str, Any]:
    ok = store.delete_chat(chat_id)
    await kernel_manager.shutdown(chat_id)
    return {"deleted": ok}


@router.post("/{chat_id}/refresh")
async def refresh(chat_id: str, request: Request) -> dict[str, Any]:
    chat = store.load_chat(chat_id)
    if chat is None:
        raise HTTPException(404, "chat not found")
    df, schema = _ledger_snapshot(_lab(request))
    await kernel_manager.bind_ledger(chat_id, df)
    return {"rows": int(df.shape[0]), "cols": int(df.shape[1])}


@router.websocket("/{chat_id}/stream")
async def stream(ws: WebSocket, chat_id: str) -> None:
    await ws.accept()
    chat = store.load_chat(chat_id)
    if chat is None:
        await ws.close(code=4404)
        return
    lab = getattr(ws.app.state, "lab", None)
    if lab is None:
        await ws.close(code=4503)
        return

    df, schema = _ledger_snapshot(lab)
    await kernel_manager.bind_ledger(chat_id, df)

    try:
        while True:
            incoming = await ws.receive_json()
            if incoming.get("type") != "user_message":
                continue
            user_text = (incoming.get("text") or "").strip()
            if not user_text:
                continue

            user_msg = {"role": "user", "content": user_text}
            chat = store.append_message(chat_id, user_msg)
            await ws.send_json({"type": "user_appended", "message": user_msg})

            if len(chat["messages"]) == 1:
                try:
                    chat["title"] = await agent.autotitle(user_text)
                    store.save_chat(chat)
                    await ws.send_json({"type": "title", "title": chat["title"]})
                except Exception:
                    pass

            async def on_event(evt: dict[str, Any]) -> None:
                await ws.send_json({"type": "agent_event", "event": evt})

            history = [_to_anthropic_message(m) for m in chat["messages"]]
            assistant_blocks = await agent.run_turn(
                chat_id=chat_id, messages=history, schema_hint=schema, on_event=on_event,
            )
            assistant_msg = {"role": "assistant", "content": assistant_blocks}
            store.append_message(chat_id, assistant_msg)
            await ws.send_json({"type": "turn_complete", "message": assistant_msg})
    except WebSocketDisconnect:
        return


def _to_anthropic_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Persisted messages already use Anthropic's content-block shape for assistant.
    User messages may be plain strings."""
    if msg["role"] == "user" and isinstance(msg["content"], str):
        return {"role": "user", "content": msg["content"]}
    return msg
```

- [ ] **Step 2: Register the router in `app.py`**

In [src/autolab/server/app.py](src/autolab/server/app.py), find where other routers/endpoints are registered (near the top of the file, after `app = FastAPI(...)`). Add:

```python
from autolab.server.chat.routes import router as chat_router
app.include_router(chat_router)
```

- [ ] **Step 3: Smoke test the REST path**

```bash
pixi run serve-prod &   # wait a few seconds
curl -X POST http://localhost:8000/chats -H 'content-type: application/json' -d '{}'
curl http://localhost:8000/chats
```

Expected: creation returns a `chat-...` id, list includes it.

- [ ] **Step 4: Commit**

```bash
git add src/autolab/server/chat/routes.py src/autolab/server/app.py
git commit -m "feat(chat): FastAPI /chats routes and streaming WS"
```

---

## Task 7: Remove old Analysis endpoint

**Files:**
- Modify: `src/autolab/server/app.py`

Delete the old single-shot analysis code now that the chat replaces it. Keep the commit focused — this is a pure removal.

- [ ] **Step 1: Delete**

In [src/autolab/server/app.py](src/autolab/server/app.py), remove:
- `class AnalysisRequest` near line 185
- The `@app.post("/analysis/query")` handler at line 1172 and all `_analysis_*` helpers through line ~1510

Search for `analysis` after editing; only imports/leftovers from the chat integration should remain.

- [ ] **Step 2: Verify the server still boots**

```bash
pixi run python -c "from autolab.server.app import app; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/autolab/server/app.py
git commit -m "refactor(server): remove single-shot /analysis/query in favor of /chats"
```

---

## Task 8: Frontend — ChatPage shell + sidebar

**Files:**
- Create: `frontend/src/pages/ChatPage.jsx`
- Create: `frontend/src/pages/chat/ChatSidebar.jsx`
- Create: `frontend/src/pages/chat/chat.css`

Match the existing dashboard aesthetic — look at [frontend/src/pages/LedgerPage.jsx](frontend/src/pages/LedgerPage.jsx) and [frontend/src/shell/](frontend/src/shell/) for patterns. Use existing CSS variables (`--color-muted`, etc.). Don't invent a new design language.

- [ ] **Step 1: `chat.css` — scoped styles**

```css
.chat-page { display: grid; grid-template-columns: 260px 1fr; height: calc(100vh - 64px); min-height: 0; }
.chat-sidebar { border-right: 1px solid var(--color-border); overflow-y: auto; padding: 12px 0; background: var(--color-surface-alt, transparent); }
.chat-sidebar h4 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-muted); margin: 0 14px 8px; }
.chat-sidebar-item { padding: 10px 14px; cursor: pointer; border-left: 2px solid transparent; }
.chat-sidebar-item:hover { background: rgba(255,255,255,0.03); }
.chat-sidebar-item.active { background: rgba(140,170,255,0.08); border-left-color: var(--color-accent, #8caaff); }
.chat-sidebar-item .title { font-size: 13px; color: var(--color-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-sidebar-item .meta { font-size: 11px; color: var(--color-muted); margin-top: 2px; }
.chat-sidebar-new { margin: 10px 14px 14px; }
.chat-main { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.chat-thread { flex: 1; overflow-y: auto; padding: 20px 28px; }
.chat-message { margin-bottom: 18px; max-width: 760px; }
.chat-message.user { margin-left: auto; }
.chat-message.user .bubble { background: rgba(140,170,255,0.10); padding: 10px 14px; border-radius: 10px; }
.chat-message.assistant .bubble { padding: 0; }
.chat-code-cell { margin: 8px 0; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
.chat-code-cell-header { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; font-size: 11px; color: var(--color-muted); background: rgba(255,255,255,0.02); cursor: pointer; }
.chat-code-cell pre { margin: 0; padding: 10px; font-size: 12px; overflow-x: auto; background: var(--color-bg); }
.chat-code-cell .output { padding: 8px 10px; border-top: 1px solid var(--color-border); font-family: var(--font-mono); font-size: 12px; white-space: pre-wrap; color: var(--color-muted); }
.chat-figure { padding: 10px; }
.chat-figure img { max-width: 100%; border-radius: 4px; }
.chat-prompt { border-top: 1px solid var(--color-border); padding: 12px 20px; display: flex; gap: 8px; }
.chat-prompt textarea { flex: 1; min-height: 48px; max-height: 160px; resize: vertical; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: 6px; padding: 10px; color: var(--color-text); font-family: inherit; font-size: 13px; }
.chat-empty { color: var(--color-muted); padding: 40px; text-align: center; }
```

- [ ] **Step 2: `ChatSidebar.jsx`**

```jsx
import { useEffect, useState } from "react";

export default function ChatSidebar({ activeId, onSelect, onNew, refreshKey }) {
  const [chats, setChats] = useState([]);

  useEffect(() => {
    fetch("/chats").then((r) => r.json()).then(setChats).catch(() => setChats([]));
  }, [refreshKey]);

  return (
    <aside className="chat-sidebar">
      <h4>Chats</h4>
      <div className="chat-sidebar-new">
        <button type="button" className="btn-secondary" style={{ width: "100%" }} onClick={onNew}>
          + New chat
        </button>
      </div>
      {chats.length === 0 ? (
        <div style={{ padding: "0 14px", color: "var(--color-muted)", fontSize: 12 }}>
          No chats yet.
        </div>
      ) : null}
      {chats.map((c) => (
        <div
          key={c.id}
          className={`chat-sidebar-item${c.id === activeId ? " active" : ""}`}
          onClick={() => onSelect(c.id)}
        >
          <div className="title">{c.title || c.id}</div>
          <div className="meta">{c.message_count} messages</div>
        </div>
      ))}
    </aside>
  );
}
```

- [ ] **Step 3: `ChatPage.jsx` skeleton (thread + prompt stubbed; full wiring in next task)**

```jsx
import { useCallback, useEffect, useRef, useState } from "react";
import ChatSidebar from "./chat/ChatSidebar";
import "./chat/chat.css";

export default function ChatPage() {
  const [activeId, setActiveId] = useState(null);
  const [chat, setChat] = useState(null);
  const [sidebarKey, setSidebarKey] = useState(0);
  const [pending, setPending] = useState(false);

  const loadChat = useCallback(async (id) => {
    if (!id) return setChat(null);
    const r = await fetch(`/chats/${id}`);
    if (!r.ok) return setChat(null);
    setChat(await r.json());
  }, []);

  useEffect(() => { loadChat(activeId); }, [activeId, loadChat]);

  const newChat = useCallback(async () => {
    const r = await fetch("/chats", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
    const c = await r.json();
    setSidebarKey((k) => k + 1);
    setActiveId(c.id);
  }, []);

  return (
    <div className="chat-page">
      <ChatSidebar activeId={activeId} onSelect={setActiveId} onNew={newChat} refreshKey={sidebarKey} />
      <div className="chat-main">
        {chat ? (
          <ChatActive chat={chat} onReload={() => loadChat(activeId)} pending={pending} setPending={setPending} />
        ) : (
          <div className="chat-empty">
            <h3>Ledger Chat</h3>
            <p>Talk to your lab's data. Opus 4.7 writes pandas, runs it, reads its own charts, iterates.</p>
            <button type="button" className="btn-primary" onClick={newChat}>Start a chat</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ChatActive is filled in Task 9.
function ChatActive({ chat }) {
  return <div style={{ padding: 20 }}>Opened {chat.id} — thread coming in Task 9.</div>;
}
```

- [ ] **Step 4: Wire into `App.jsx`**

Replace the `import AnalysisPage` and `analysis` route branch in [frontend/src/App.jsx](frontend/src/App.jsx):

```jsx
import ChatPage from "./pages/ChatPage";
// ...
const CRUMBS = {
  // ...
  chat: ["Chat"],
  // remove: analysis: ["Analysis"],
};
// ...
if (route.page === "chat") {
  return <ChatPage />;
}
// remove the old analysis branch
```

Also find the navigation item for "Analysis" (likely in `AppShell` or similar) and rename it to "Chat" with `page: "chat"`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ChatPage.jsx frontend/src/pages/chat frontend/src/App.jsx
git commit -m "feat(frontend): ChatPage shell and sidebar; nav renamed Analysis -> Chat"
```

---

## Task 9: Frontend — MessageThread, WebSocket wiring, live events

**Files:**
- Create: `frontend/src/pages/chat/MessageThread.jsx`
- Create: `frontend/src/pages/chat/PromptInput.jsx`
- Modify: `frontend/src/pages/ChatPage.jsx` (fill in `ChatActive`)

- [ ] **Step 1: `MessageThread.jsx` — render history and live streamed blocks**

```jsx
import { useEffect, useRef, useState } from "react";

function CodeCell({ code, stdout, stderr, error, figures, running }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="chat-code-cell">
      <div className="chat-code-cell-header" onClick={() => setOpen((v) => !v)}>
        <span>{running ? "▶ running…" : "▸ code"}</span>
        <span>{open ? "hide" : "show"}</span>
      </div>
      {open ? <pre>{code}</pre> : null}
      {(stdout || stderr || error) && (
        <div className="output">
          {stdout}
          {stderr ? <span style={{ color: "var(--color-status-red)" }}>{stderr}</span> : null}
          {error ? <span style={{ color: "var(--color-status-red)" }}>{error}</span> : null}
        </div>
      )}
      {(figures || []).map((b64, i) => (
        <div className="chat-figure" key={i}>
          <img src={`data:image/png;base64,${b64}`} alt={`figure ${i + 1}`} />
        </div>
      ))}
    </div>
  );
}

function renderAssistant(content, liveToolResults) {
  const tools = liveToolResults || {};
  return content.map((b, i) => {
    if (b.type === "text") {
      return <div className="bubble" key={i} style={{ whiteSpace: "pre-wrap" }}>{b.text}</div>;
    }
    if (b.type === "tool_use") {
      const tr = tools[b.id] || {};
      return (
        <CodeCell
          key={i}
          code={b.input?.code || ""}
          stdout={tr.stdout}
          stderr={tr.stderr}
          error={tr.error}
          figures={tr.figures}
          running={tr.running}
        />
      );
    }
    if (b.type === "tool_result") {
      // already represented via the matching tool_use above
      return null;
    }
    return null;
  });
}

export default function MessageThread({ messages, live }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [messages, live]);

  const liveToolResults = {};
  for (const evt of live?.events || []) {
    if (evt.type === "tool_call") liveToolResults[evt.id] = { running: true };
    if (evt.type === "tool_result") {
      liveToolResults[evt.id] = {
        running: false,
        stdout: evt.stdout, stderr: evt.stderr, error: evt.error, figures: evt.figures,
      };
    }
  }
  const liveBlocks = (live?.blocks || []).filter((b) => b.type !== "tool_result");

  return (
    <div className="chat-thread" ref={ref}>
      {messages.map((m, i) => (
        <div className={`chat-message ${m.role}`} key={i}>
          {m.role === "user" ? (
            <div className="bubble">{typeof m.content === "string" ? m.content : ""}</div>
          ) : (
            renderAssistant(m.content, {})
          )}
        </div>
      ))}
      {live?.active ? (
        <div className="chat-message assistant">{renderAssistant(liveBlocks, liveToolResults)}</div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: `PromptInput.jsx`**

```jsx
import { useState } from "react";

export default function PromptInput({ onSend, onRefresh, disabled }) {
  const [text, setText] = useState("");
  const submit = () => {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
  };
  return (
    <div className="chat-prompt">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); }
        }}
        placeholder="Ask a question about the ledger. ⌘↵ to send."
        disabled={disabled}
      />
      <button type="button" className="btn-secondary" onClick={onRefresh} disabled={disabled} title="Re-read the ledger into the kernel">
        ↻
      </button>
      <button type="button" className="btn-primary" onClick={submit} disabled={disabled || !text.trim()}>
        Send
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Fill in `ChatActive` in `ChatPage.jsx`**

Replace the stub `ChatActive` with:

```jsx
function ChatActive({ chat, onReload }) {
  const [messages, setMessages] = useState(chat.messages || []);
  const [live, setLive] = useState({ active: false, blocks: [], events: [] });
  const wsRef = useRef(null);

  useEffect(() => { setMessages(chat.messages || []); }, [chat.id]);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/chats/${chat.id}/stream`);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "user_appended") {
        setMessages((m) => [...m, msg.message]);
      } else if (msg.type === "agent_event") {
        const evt = msg.event;
        setLive((L) => {
          const nextEvents = [...L.events, evt];
          let nextBlocks = L.blocks;
          if (evt.type === "block") nextBlocks = [...L.blocks, evt.block];
          return { active: true, blocks: nextBlocks, events: nextEvents };
        });
      } else if (msg.type === "turn_complete") {
        setMessages((m) => [...m, msg.message]);
        setLive({ active: false, blocks: [], events: [] });
      } else if (msg.type === "title") {
        // sidebar refresh handled by parent
      }
    };
    ws.onclose = () => { wsRef.current = null; };
    return () => ws.close();
  }, [chat.id]);

  const send = (text) => {
    if (!wsRef.current) return;
    setLive({ active: true, blocks: [], events: [] });
    wsRef.current.send(JSON.stringify({ type: "user_message", text }));
  };

  const refresh = async () => {
    await fetch(`/chats/${chat.id}/refresh`, { method: "POST" });
  };

  return (
    <>
      <MessageThread messages={messages} live={live} />
      <PromptInput onSend={send} onRefresh={refresh} disabled={live.active} />
    </>
  );
}
```

And add at the top of `ChatPage.jsx`:

```jsx
import MessageThread from "./chat/MessageThread";
import PromptInput from "./chat/PromptInput";
```

- [ ] **Step 4: Build and spot-check**

```bash
cd frontend && npm run build && cd ..
```

Expected: build succeeds with no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ChatPage.jsx frontend/src/pages/chat/MessageThread.jsx frontend/src/pages/chat/PromptInput.jsx
git commit -m "feat(frontend): chat thread, live tool-call streaming, prompt input"
```

---

## Task 10: Polish pass

**Files:**
- Modify: `frontend/src/pages/chat/MessageThread.jsx`
- Modify: `frontend/src/pages/ChatPage.jsx`
- Modify: `frontend/src/pages/chat/chat.css`

Three small things that make it *look good* for the demo.

- [ ] **Step 1: Sidebar refresh on new chat / title update**

In `ChatPage.jsx`, when you receive a `title` WS event, bump `sidebarKey` so the sidebar re-fetches. Lift the `title` handler up via a prop:

```jsx
// In ChatActive props, add: onTitleUpdate
// In ws.onmessage title branch:
else if (msg.type === "title") {
  onTitleUpdate && onTitleUpdate();
}

// In ChatPage, pass:
<ChatActive chat={chat} onReload={() => loadChat(activeId)} onTitleUpdate={() => { setSidebarKey((k) => k + 1); loadChat(activeId); }} />
```

- [ ] **Step 2: Markdown rendering for assistant text**

Install `marked`:

```bash
cd frontend && npm install marked && cd ..
```

In `MessageThread.jsx`, replace the plain `<div>{b.text}</div>` with:

```jsx
import { marked } from "marked";
// ...
return (
  <div
    className="bubble"
    key={i}
    dangerouslySetInnerHTML={{ __html: marked.parse(b.text, { breaks: true }) }}
  />
);
```

Add minimal prose styling to `chat.css`:

```css
.chat-message.assistant .bubble { font-size: 14px; line-height: 1.55; }
.chat-message.assistant .bubble p { margin: 0 0 10px; }
.chat-message.assistant .bubble code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-size: 12px; }
.chat-message.assistant .bubble pre { background: var(--color-bg); padding: 10px; border-radius: 4px; overflow-x: auto; }
.chat-message.assistant .bubble ul, .chat-message.assistant .bubble ol { margin: 4px 0 10px 20px; }
```

- [ ] **Step 3: Empty-state example prompts**

In the `chat-empty` block in `ChatPage.jsx`, add three clickable example questions that create a new chat and immediately send that prompt. This makes the demo feel alive on first click.

```jsx
const EXAMPLES = [
  "Compare best-so-far between the two sensor campaigns as a function of trial. Which won and where did the gap open?",
  "Plot the sx_nm trajectory of every completed sensor trial, coloured by campaign.",
  "Which campaigns have failed records? Summarise the failures.",
];

// inside the empty state:
<div style={{ marginTop: 20, display: "grid", gap: 8, maxWidth: 520 }}>
  {EXAMPLES.map((e) => (
    <button
      key={e}
      type="button"
      className="btn-secondary"
      style={{ textAlign: "left", whiteSpace: "normal" }}
      onClick={async () => {
        const r = await fetch("/chats", { method: "POST", headers: {"content-type":"application/json"}, body: "{}" });
        const c = await r.json();
        setSidebarKey((k) => k + 1);
        setActiveId(c.id);
        // defer the send until ChatActive has mounted and opened its WS.
        // Simplest: stash the pending prompt in state and let ChatActive auto-send once open.
        setPendingPrompt({ chatId: c.id, text: e });
      }}
    >
      {e}
    </button>
  ))}
</div>
```

Implement `pendingPrompt` state in `ChatPage`, pass to `ChatActive`, and have `ChatActive` send it on WS open when its id matches.

- [ ] **Step 4: Rebuild + visual check**

```bash
cd frontend && npm run build && cd ..
```

Expected: clean build.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "polish(chat): markdown rendering, sidebar live updates, example prompts"
```

---

## Task 11: End-to-end verification

**No files changed — this is the verification gate.**

- [ ] **Step 1: Clean boot**

```bash
pkill -f "autolab serve" 2>/dev/null || true
pixi run serve-prod &
sleep 3
```

- [ ] **Step 2: Ensure sensor demo data exists**

If the ledger is empty, run:

```bash
pixi run sensor-demo
# then start both campaigns; wait for completion
```

- [ ] **Step 3: Manual smoke — run these prompts in order, in the same chat**

1. *"Compare best-so-far Hmax_A_per_m between the two sensor campaigns as a function of trial. Tell me which won and where the gap opened."*
   - Expect: at least one code cell, one line chart rendered inline, narrative naming the crossover trial.
2. *"Now plot the sx_nm trajectory for the winner only."*
   - Expect: Claude reuses `ledger` and a variable from turn 1 (no re-query). Kernel persistence verified.
3. *"Are there any failed records? If so, by campaign and capability."*
   - Expect: a count/table output and a short narrative.

- [ ] **Step 4: Reload test**

Refresh the browser, click the chat in the sidebar. History (text + images) should rehydrate identically.

- [ ] **Step 5: Delete test**

Delete the chat from the sidebar. Confirm:

```bash
ls var/chats/ var/chat-kernels/
```

The chat JSON is gone and no orphan `chat-...json` connection file remains in `var/chat-kernels/`.

- [ ] **Step 6: Lint + test**

```bash
pixi run lint
pixi run test
```

Expected: both pass.

- [ ] **Step 7: Final commit if any fix-ups**

```bash
git add -A
git commit -m "test(chat): verification fix-ups" || true
```

---

## Out of scope (explicitly deferred)

- **Pin as finding** → writes `AnalysisClaim` Record. Add as a single POST handler + a 📌 button in a follow-up PR.
- **Kernel orphan cleanup** on Lab restart. Add a `cleanup_orphans()` pass in `app.py` startup.
- **Ledger-staleness banner** — compare ledger version at bind time vs latest.
- **Large PNGs to disk** — currently inlined as data URLs. Fine for demo; add offload if chat JSONs get huge.
- **Streaming assistant text token-by-token** — currently streams at block granularity.
- **Analysis claims consumed by `react()`** — v2 direction.
