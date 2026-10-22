"""Render Free: authenticated ZIP upload + GPT-native MCP image delivery.

This server NEVER calls a vision model or an OpenAI API. All visual interpretation
must be carried out by ChatGPT upon receiving ImageContent in a MCP tool result.
WARNING: /tmp storage is ephemeral on Render Free. Download backups frequently.
"""
from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import secrets
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from hosted_core import HostedStudyCore
import chatgpt_cloud_ledger as ledger

TOKEN = os.getenv("THUMBNAIL_TOKEN", "")
if len(TOKEN) < 32:
    raise RuntimeError("Set THUMBNAIL_TOKEN to a unique secret of at least 32 characters in Render Environment")
ROOT = Path(os.getenv("THUMBNAIL_ROOT", "/tmp/thumbnail-forensics")).resolve()
core = HostedStudyCore(ROOT)
lock = threading.RLock()
MAX_ZIP_BYTES = 125 * 1024 * 1024
MAX_EXPANDED_BYTES = 768 * 1024 * 1024

mcp = FastMCP("Thumbnail Forensics — GPT reads the images", stateless_http=True, json_response=True)

@mcp.tool()
def study_status(study_id: str) -> dict:
    """Get per-image progress. Storage is ephemeral on Render Free."""
    with lock:
        return {"study_id": study_id, "audit": core.audit(study_id), "ephemeral_storage": True}

@mcp.tool()
def next_thumbnail(study_id: str, stage: str = "first") -> dict:
    """Identify exactly one pending image. Does NOT itself show pixels to GPT."""
    with lock:
        return core.pending(study_id, stage)

@mcp.tool()
def inspect_thumbnail(study_id: str, image_id: str, stage: str = "first") -> list[TextContent | ImageContent]:
    """Deliver the original PNG pixels as MCP ImageContent, not URL or OCR text.
    Immediately write visible observations via save_thumbnail_observation.
    """
    with lock:
        receipt, pixels = core.deliver(study_id, image_id, stage)
    return [
        TextContent(type="text", text=json.dumps(receipt, ensure_ascii=False)),
        ImageContent(type="image", data=base64.b64encode(pixels).decode("ascii"), mimeType="image/png"),
    ]

@mcp.tool()
def save_thumbnail_observation(study_id: str, image_id: str, stage: str, delivery_nonce: str,
                               observation: dict) -> dict:
    """Store GPT-authored observation for ONE delivered image; nonce/sha must match.
    Required visible_evidence contains specific characters/text/layout actually seen.
    """
    with lock:
        return core.save_observation(study_id, image_id, stage, delivery_nonce, observation)

@mcp.tool()
def assign_thumbnail_groups(study_id: str, groups: dict[str, list[str]]) -> dict:
    """Assign ALL 1st-pass inspected images exactly once to visual-content groups.
    Each group must contain at least 5 distinct source images.
    """
    with lock:
        return core.assign_groups(study_id, groups)

@mcp.tool()
def select_thumbnail_examples(study_id: str, selected: dict[str, list[str]]) -> dict:
    """Choose precisely five representative image IDs within each assigned group."""
    with lock:
        return core.select(study_id, selected)

@mcp.tool()
def save_thumbnail_style_dna(study_id: str, style_dna: dict) -> dict:
    """Write evidence-linked common design principles after all deep reads."""
    with lock:
        return core.style(study_id, style_dna)

@mcp.tool()
def export_thumbnail_study(study_id: str) -> dict:
    """Validate coverage and create final ZIP. Download via the authenticated web page."""
    with lock:
        result = core.export(study_id)
        return {"study_id": study_id, "ready": True, "zip_bytes": result.stat().st_size,
                "download_from_web_dashboard": True}

@mcp.tool()
def storage_warning() -> dict:
    """Explain risk of free Render storage. Backup current study frequently in web dashboard."""
    return {"storage": "ephemeral", "risk": "Render Free clears files on restart/redeploy/spindown; not a durable store", 
            "mitigation": "Download study checkpoint ZIP from dashboard after each batch; reupload checkpoint after reset."}

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield

app = FastAPI(title="Thumbnail Forensics Render Bridge", lifespan=lifespan)

class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(("/api/", "/mcp")):
            authorization = request.headers.get("authorization", "")
            if not secrets.compare_digest(authorization, "Bearer " + TOKEN):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)

app.add_middleware(TokenMiddleware)

@app.get("/healthz")
def health():
    return {"status": "ok", "service": "thumbnail-forensics-render", "storage": "ephemeral"}

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(Path(__file__).with_name("index.html").read_text(encoding="utf-8"))


def validate_zip(zp: Path) -> None:
    try:
        with zipfile.ZipFile(zp) as z:
            entries = [x for x in z.infolist() if x.filename.lower().endswith(".png") and not x.is_dir()]
            if not entries or len(entries) > 10_000:
                raise HTTPException(400, "ZIP must contain 1..10000 PNG files")
            if sum(e.file_size for e in entries) > MAX_EXPANDED_BYTES:
                raise HTTPException(413, "PNG uncompressed total exceeds 768MiB on Render Free")
            if any(e.file_size > ledger.MAX_SINGLE_BYTES for e in entries):
                raise HTTPException(413, "Individual PNG exceeds 30MiB")
    except zipfile.BadZipFile as e:
        raise HTTPException(400, "Invalid ZIP") from e


async def receive_upload(file: UploadFile) -> Path:
    fd, temp_name = tempfile.mkstemp(suffix=".zip", dir=core.uploads)
    size = 0
    try:
        with os.fdopen(fd, "wb") as f:
            while buf := await file.read(1024 * 1024):
                size += len(buf)
                if size > MAX_ZIP_BYTES:
                    raise HTTPException(413, "ZIP upload exceeds 125MiB")
                f.write(buf)
        return Path(temp_name)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise

@app.post("/api/upload")
async def upload_zip(file: UploadFile = File(...)):
    """Single authenticated upload from web UI. Returns study ID for ChatGPT."""
    tempfile_zip = await receive_upload(file)
    upload_id = "upload_" + secrets.token_hex(10)
    target = core.uploads / (upload_id + ".zip")
    sid = "study_" + secrets.token_hex(10)
    try:
        validate_zip(tempfile_zip)
        tempfile_zip.replace(target)
        with lock:
            info = core.initialize(sid, upload_id)
        return {**info, "storage": "ephemeral", "must_download_checkpoints": True}
    except (HTTPException, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(400, str(exc)) from exc
        raise
    finally:
        tempfile_zip.unlink(missing_ok=True)
        target.unlink(missing_ok=True)

@app.get("/api/status/{study_id}")
def study_http_status(study_id: str):
    try:
        with lock:
            return core.audit(study_id)
    except ValueError as ex:
        raise HTTPException(404, str(ex)) from ex

@app.get("/api/result/{study_id}")
def download_result(study_id: str):
    try:
        with lock:
            path = core.export(study_id)
        return FileResponse(path, filename=f"{study_id}-result.zip", media_type="application/zip")
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(409, str(exc)) from exc

@app.get("/api/checkpoint/{study_id}")
def download_checkpoint(study_id: str):
    """Portable backup: source originals + ledger. Save OFF Render after each batch."""
    try:
        with lock:
            ws = core._existing(study_id)
            out = ROOT / f"checkpoint-{study_id}.zip"
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
                for p in sorted(ws.rglob("*")):
                    if p.is_file() and not p.is_symlink() and p.name != "result.zip":
                        zf.write(p, p.relative_to(ws).as_posix())
        return FileResponse(out, filename=f"{study_id}-checkpoint.zip", media_type="application/zip")
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

@app.post("/api/restore")
async def restore_checkpoint(file: UploadFile = File(...)):
    """Restore a private checkpoint if Render Free cleared its filesystem."""
    tmp = await receive_upload(file)
    try:
        with zipfile.ZipFile(tmp) as zf:
            names = zf.namelist()
            if not names or "manifest.json" not in names:
                raise HTTPException(400, "Not a Thumbnail Forensics checkpoint")
            if len(names) > 20_000 or sum(i.file_size for i in zf.infolist()) > MAX_EXPANDED_BYTES:
                raise HTTPException(413, "Checkpoint uncompressed size too large")
            for item in zf.infolist():
                p = Path(item.filename)
                if item.filename.startswith(("/", "\\")) or ".." in p.parts or "\\" in item.filename:
                    raise HTTPException(400, "Unsafe path in checkpoint")
            manifest = json.loads(zf.read("manifest.json"))
            if not isinstance(manifest.get("count"), int) or not 0 < manifest["count"] <= 10_000:
                raise HTTPException(400, "Invalid checkpoint manifest")
            sid = "study_" + secrets.token_hex(10)
            ws = core.workspace(sid)
            with lock:
                ws.mkdir(parents=True, exist_ok=False)
                try:
                    zf.extractall(ws)
                    for e in ledger.state(ws)["images"]:
                        original = ws / e["original"]
                        if not original.is_file() or not original.resolve().is_relative_to(ws):
                            raise ValueError("Checkpoint original missing/outside workspace")
                        import hashlib
                        if hashlib.sha256(original.read_bytes()).hexdigest() != e["sha256"]:
                            raise ValueError("Checkpoint hash mismatch")
                except BaseException:
                    shutil.rmtree(ws, ignore_errors=True)
                    raise
        return {"restored_study_id": sid, "images": manifest["count"], "storage": "ephemeral"}
    except (zipfile.BadZipFile, ValueError, KeyError, json.JSONDecodeError) as ex:
        raise HTTPException(400, "Corrupt checkpoint") from ex
    finally:
        tmp.unlink(missing_ok=True)

# Mounted last: streamable HTTP on /mcp. MCP's session manager is started by outer lifespan.
app.mount("/", mcp.streamable_http_app())
