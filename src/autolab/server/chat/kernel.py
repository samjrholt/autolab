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
matplotlib.use("module://matplotlib_inline.backend_inline")
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
