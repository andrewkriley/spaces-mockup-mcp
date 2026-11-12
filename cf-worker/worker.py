"""Cloudflare Worker entry for the spaces-mockup MCP HTTP door."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint

import server as srv

try:
    from dataset_embed import DATA as _EMBEDDED_DATASET
except ImportError:
    _EMBEDDED_DATASET = None

_DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"


def _load_dataset() -> None:
    if srv.DATASET:
        return
    if _EMBEDDED_DATASET is not None:
        srv.DATASET = _EMBEDDED_DATASET
        return
    if _DATASET_PATH.is_file():
        srv.DATASET = srv.load_dataset(_DATASET_PATH)


_load_dataset()


class Default(WorkerEntrypoint):
    def _ready(self) -> None:
        srv.TOKEN = getattr(self.env, "MCP_BEARER_TOKEN", None) or ""
        _load_dataset()

    async def fetch(self, request):
        self._ready()
        parsed = urlparse(str(request.url))
        path = parsed.path or "/"
        method = str(request.method)
        authorization = request.headers.get("Authorization") or ""
        body = None
        if method == "POST":
            body = await request.text()
        status, payload = srv.handle_http(method, path, authorization, body)
        if payload is None:
            return Response("", status=status)
        return Response(
            json.dumps(payload, default=str),
            status=status,
            headers={"content-type": "application/json"},
        )
