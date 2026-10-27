"""Local web server. Everything stays on this machine: images live in memory and are dropped when a session ends."""

from __future__ import annotations

import hashlib
import io
import json
import threading
import uuid
import zipfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, changes, imaging, models, provenance, runtime
from .pipeline import ALL_STEPS, DEFAULT_STEPS, Options, Pipeline, RunResult
from .split import Quad

WEB_DIR = Path(__file__).parent / "web"
MAX_SESSIONS = 4
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
PREVIEW_SIDE = 2600


class RunRequest(BaseModel):
    steps: list[str] = Field(default_factory=lambda: list(DEFAULT_STEPS))
    face_strength: int = 35
    face_strengths: dict[int, list[int]] = Field(default_factory=dict)
    color_strength: int = 100
    scale: int = 2
    quads: list[dict] | None = None
    quarter_turns: dict[int, int] = Field(default_factory=dict)
    force_fade: bool = False


@dataclass
class Session:
    id: str
    name: str
    source: np.ndarray
    quads: list[Quad]
    split_note: str
    sha256: str = ""
    result: RunResult | None = None
    masks: dict[int, np.ndarray] = field(default_factory=dict)
    mask_keys: dict[int, str] = field(default_factory=dict)  # which outline each hand painted mask belongs to
    run_keys: dict[int, str] = field(default_factory=dict)  # the outline each photo of the last run came from
    progress: dict = field(default_factory=lambda: {"state": "idle"})


class Store:
    def __init__(self) -> None:
        self._items: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

    def add(self, session: Session) -> None:
        with self._lock:
            self._items[session.id] = session
            while len(self._items) > MAX_SESSIONS:
                self._items.popitem(last=False)

    def get(self, sid: str) -> Session:
        with self._lock:
            session = self._items.get(sid)
        if session is None:
            raise HTTPException(404, "session not found, upload the image again")
        return session


def _jpeg(rgb: np.ndarray, side: int | None = PREVIEW_SIDE) -> Response:
    if side:
        rgb = imaging.fit_long_side(rgb, side)
    return Response(imaging.encode(rgb, ".jpg", 90), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def _hostname(header: str) -> str:
    """The name in a Host header without its port, brackets removed from an IPv6 address."""
    if header.startswith("["):
        return header[1:].split("]", 1)[0]
    return header.rsplit(":", 1)[0] if header.count(":") == 1 else header


def create_app(device: str = "auto", host: str | None = None) -> FastAPI:
    """``host`` is the address the server binds to. When given, other Host headers are refused (DNS rebinding)."""
    app = FastAPI(title="Unfaded", version=__version__, docs_url=None, redoc_url=None)
    store = Store()
    pipeline = Pipeline(device)
    gpu_lock = threading.Lock()
    exposed = host in (None, "0.0.0.0", "::")  # bound to every interface on purpose, any Host is fine
    allowed_hosts = None if exposed else {host.strip("[]"), "127.0.0.1", "localhost", "::1"}

    def photo_of(session: Session, index: int):
        if session.result is None or not 0 <= index < len(session.result.photos):
            raise HTTPException(404, "no such photo, run the restoration first")
        return session.result.photos[index]

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if allowed_hosts and _hostname(request.headers.get("host", "")) not in allowed_hosts:
            return JSONResponse({"detail": "unexpected Host header refused"}, status_code=403)
        origin = request.headers.get("origin")
        host = request.headers.get("host", "")
        if request.method != "GET" and origin and origin.split("://", 1)[-1] != host:
            return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
        return await call_next(request)

    @app.get("/api/info")
    def info():
        dev = runtime.pick_device(device)
        return {
            "version": __version__,
            "device": runtime.describe(dev),
            "steps": list(ALL_STEPS),
            "defaults": list(DEFAULT_STEPS),
            "models": models.status(),
        }

    @app.post("/api/models/fetch")
    async def fetch_models(payload: dict):
        steps = set(payload.get("steps", [])) & set(ALL_STEPS)
        await run_in_threadpool(models.ensure_for_steps, steps)
        return {"models": models.status()}

    @app.post("/api/session")
    async def new_session(file: UploadFile = File(...)):
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "file too large")
        try:
            rgb = imaging.load_rgb(data)
        except Exception as exc:
            raise HTTPException(400, "this file is not an image I can read") from exc
        quads, note = await run_in_threadpool(pipeline.detect_quads, rgb)
        session = Session(
            uuid.uuid4().hex[:12], file.filename or "photo", rgb, quads, note, hashlib.sha256(data).hexdigest()
        )
        store.add(session)
        h, w = rgb.shape[:2]
        return {
            "id": session.id,
            "name": session.name,
            "width": w,
            "height": h,
            "quads": [q.to_json() for q in quads],
            "note": note,
        }

    @app.get("/api/session/{sid}/source.jpg")
    def source_image(sid: str):
        return _jpeg(store.get(sid).source)

    @app.post("/api/session/{sid}/run")
    async def run(sid: str, req: RunRequest):
        session = store.get(sid)
        quads = None if req.quads is None else [Quad.from_json(q) for q in req.quads]
        shown = session.quads if quads is None else quads
        keys = {
            i: json.dumps([shown[i].to_json() if i < len(shown) else None, req.quarter_turns.get(i, 0)])
            for i in range(max(len(shown), 1))
        }
        # A mask belongs to one outline. It no longer fits after a corner moves, a print turns or an outline goes.
        dropped = sorted(i for i in session.masks if session.mask_keys.get(i) != keys.get(i))
        for i in dropped:
            del session.masks[i]
            session.mask_keys.pop(i, None)
        try:
            options = Options(
                steps=tuple(s for s in ALL_STEPS if s in req.steps),
                face_strength=req.face_strength,
                face_strengths=req.face_strengths,
                color_strength=req.color_strength,
                scale=req.scale,
                quads=quads,
                quarter_turns=req.quarter_turns,
                masks=session.masks,
                force_fade=req.force_fade,
            )
            options.validate()
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        def progress(step: str, photo: int, state: str) -> None:
            session.progress = {"state": "running", "step": step, "photo": photo, "phase": state}

        def work() -> RunResult:
            with gpu_lock:
                models.ensure_for_steps(set(options.steps))
                session.progress = {"state": "running", "step": "start", "photo": 0, "phase": "start"}
                try:
                    return pipeline.run(session.source, options, progress)
                finally:
                    session.progress = {"state": "idle"}

        try:
            session.result = await run_in_threadpool(work)
        except Exception as exc:  # surface model or download problems to the UI
            raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
        session.run_keys = keys
        return describe_result(session) | {"masks_dropped": dropped}

    @app.get("/api/session/{sid}/progress")
    def progress_of(sid: str):
        return store.get(sid).progress

    def describe_result(session: Session) -> dict:
        result = session.result
        assert result is not None
        return {
            "seconds": round(result.seconds, 2),
            "note": result.split_note,
            "photos": [
                {
                    "index": p.index,
                    "width": int(p.final.shape[1]),
                    "height": int(p.final.shape[0]),
                    "original": [int(p.original.shape[1]), int(p.original.shape[0])],
                    "faces": p.faces,
                    "has_mask": p.damage_mask is not None,
                    "steps": [
                        s.summary() | {"invented": s.invented is not None or (s.name == "upscale" and not s.skipped)}
                        for s in p.steps
                    ],
                }
                for p in result.photos
            ],
        }

    @app.get("/api/session/{sid}/photo/{index}/original.jpg")
    def original(sid: str, index: int):
        return _jpeg(photo_of(store.get(sid), index).original)

    @app.get("/api/session/{sid}/photo/{index}/step/{name}.jpg")
    def step_image(sid: str, index: int, name: str, heat: bool = False, invented: bool = False):
        photo = photo_of(store.get(sid), index)
        step = next((s for s in photo.steps if s.name == name), None)
        if step is None:
            raise HTTPException(404, "that step did not run")
        if heat:
            mask = step.change if step.change is not None else np.zeros(step.image.shape[:2], np.float32)
            return _jpeg(changes.heat_overlay(step.image, mask))
        if invented:
            weight = step.invented
            if weight is None:
                filler = np.ones if step.name == "upscale" and not step.skipped else np.zeros
                weight = filler(step.image.shape[:2], np.float32)
            return _jpeg(changes.heat_overlay(step.image, np.clip(weight, 0, 1)))
        return _jpeg(step.image)

    @app.get("/api/session/{sid}/photo/{index}/mask.png")
    def damage_mask(sid: str, index: int):
        mask = photo_of(store.get(sid), index).damage_mask
        if mask is None:
            raise HTTPException(404, "the repair step did not run")
        ok, buf = cv2.imencode(".png", mask)
        return Response(buf.tobytes(), media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.put("/api/session/{sid}/photo/{index}/mask")
    async def put_mask(sid: str, index: int, request: Request):
        session = store.get(sid)
        photo = photo_of(session, index)
        data = await request.body()
        arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
        if arr is None or arr.shape != photo.original.shape[:2]:
            raise HTTPException(422, "the mask must be a PNG with the same size as the photo")
        session.masks[index] = np.where(arr > 127, 255, 0).astype(np.uint8)
        session.mask_keys[index] = session.run_keys.get(index, "")
        return {"ok": True}

    @app.delete("/api/session/{sid}/photo/{index}/mask")
    def reset_mask(sid: str, index: int):
        session = store.get(sid)
        session.masks.pop(index, None)
        session.mask_keys.pop(index, None)
        return {"ok": True}

    @app.get("/api/session/{sid}/download.zip")
    def download_all(sid: str):
        session = store.get(sid)
        if session.result is None:
            raise HTTPException(404, "nothing to download yet")
        stem = Path(session.name).stem
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for p in session.result.photos:
                name = f"{stem}.unfaded-{p.index + 1}.jpg"
                z.writestr(name, imaging.encode(p.final, ".jpg", 95))
                z.writestr(
                    name + ".xmp", provenance.build_xmp(Path(session.name), Path(name), p, source_hash=session.sha256)
                )
        return Response(
            buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{stem}.unfaded.zip"'},
        )

    @app.get("/api/session/{sid}/photo/{index}/download.jpg")
    def download_one(sid: str, index: int):
        session = store.get(sid)
        photo = photo_of(session, index)
        name = f"{Path(session.name).stem}.unfaded-{index + 1}.jpg"
        return Response(
            imaging.encode(photo.final, ".jpg", 95),
            media_type="image/jpeg",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
    return app
