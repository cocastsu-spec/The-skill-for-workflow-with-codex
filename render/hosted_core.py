"""Cloud-side source-image transport and checkpoint core.

No AI model, OCR, or paid API is called here. The caller must supply
GPT-authored per-image observations only after receiving a model-visible image.
This module is platform-neutral; ChatGPT Sites must supply durable storage
and a private file-upload bridge. It is NOT itself a deployed service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
from pathlib import Path

import chatgpt_cloud_ledger as ledger

IDENT = re.compile(r"^[a-zA-Z0-9_-]{5,64}$")
IMAGE = re.compile(r"^IMG-[0-9]{6}$")
STAGES = {"first", "deep"}


class HostedStudyCore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.studies = self.root / "studies"
        self.uploads = self.root / "uploads"
        self.studies.mkdir(exist_ok=True)
        self.uploads.mkdir(exist_ok=True)

    @staticmethod
    def _ident(value: str) -> str:
        if not IDENT.fullmatch(value):
            raise ValueError("Invalid opaque identifier")
        return value

    def workspace(self, study_id: str) -> Path:
        return self.studies / self._ident(study_id)

    def _existing(self, study_id: str) -> Path:
        ws = self.workspace(study_id)
        if not (ws / "manifest.json").is_file():
            raise ValueError("Study was not initialized")
        return ws

    def initialize(self, study_id: str, upload_id: str) -> dict:
        """Upload ID must have been created by a private host-side upload adapter.
        Deliberately disallows arbitrary URLs and filesystem paths (SSRF/traversal).
        """
        ws = self.workspace(study_id)
        zpath = self.uploads / f"{self._ident(upload_id)}.zip"
        if not zpath.is_file() or not zpath.resolve().is_relative_to(self.uploads):
            raise ValueError("Unknown upload ID")
        if ws.exists():
            raise ValueError("Study already exists")
        try:
            ledger.ingest(argparse.Namespace(workspace=ws, zip=zpath))
        except Exception:
            shutil.rmtree(ws, ignore_errors=True)
            raise
        return {"study_id": study_id, "image_count": ledger.state(ws)["count"]}

    def _image_entry(self, study_id: str, image_id: str, stage: str) -> tuple[Path, dict]:
        if not IMAGE.fullmatch(image_id) or stage not in STAGES:
            raise ValueError("Invalid image ID or stage")
        ws = self._existing(study_id)
        e = next((e for e in ledger.state(ws)["images"] if e["image_id"] == image_id), None)
        if e is None:
            raise ValueError("Unknown image")
        if stage == "deep":
            sel_path = ws / "selections.json"
            if not sel_path.is_file() or image_id not in {
                i for arr in ledger.read_json(sel_path).values() for i in arr
            }:
                raise ValueError("Deep image is not selected")
        path = ws / e["original"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != e["sha256"]:
            raise ValueError("Original image failed SHA-256")
        return ws, e

    def pending(self, study_id: str, stage: str) -> dict:
        if stage not in STAGES:
            raise ValueError("Invalid stage")
        ws = self._existing(study_id)
        images = ledger.state(ws)["images"]
        allowed = {e["image_id"] for e in images}
        if stage == "deep":
            sel = ledger.read_json(ws / "selections.json")
            allowed = {i for group in sel.values() for i in group}
        done = ledger.saved_records(ws, stage)
        missing = [e["image_id"] for e in images if e["image_id"] in allowed and e["image_id"] not in done]
        return {"study_id": study_id, "stage": stage, "remaining": len(missing),
                "image_id": missing[0] if missing else None}

    def deliver(self, study_id: str, image_id: str, stage: str) -> tuple[dict, bytes]:
        """Return the untouched original image bytes to an MCP ImageContent tool result.
        Creates a one-use delivery nonce; it proves transport, not comprehension.
        """
        ws, e = self._image_entry(study_id, image_id, stage)
        if image_id in ledger.saved_records(ws, stage):
            raise ValueError("Image already observed in this stage")
        nonce = secrets.token_urlsafe(24)
        info = {"study_id": study_id, "image_id": image_id, "stage": stage,
                "sha256": e["sha256"], "delivery_nonce": nonce,
                "source_path": e["source_path"], "mime_type": e.get("mime_type", "image/png")}
        ledger.write_json(ws / "deliveries" / stage / f"{image_id}.json", info)
        return info, (ws / e["original"]).read_bytes()

    def save_observation(self, study_id: str, image_id: str, stage: str, nonce: str,
                         observation: dict) -> dict:
        ws, e = self._image_entry(study_id, image_id, stage)
        ticket_file = ws / "deliveries" / stage / f"{image_id}.json"
        if not ticket_file.is_file():
            raise ValueError("No model-image delivery recorded")
        ticket = ledger.read_json(ticket_file)
        if not secrets.compare_digest(ticket.get("delivery_nonce", ""), nonce):
            raise ValueError("Delivery nonce mismatch")
        if ticket["sha256"] != e["sha256"]:
            raise ValueError("Delivery source mismatch")
        if image_id in ledger.saved_records(ws, stage):
            raise ValueError("Existing record: cannot overwrite")
        payload = dict(observation)
        payload.update({"image_id": image_id, "sha256": e["sha256"],
                        "observed_with": "chatgpt_visual"})
        # Supplying a nonce only confirms a transport event. The host must verify
        # the GPT-visible image was actually returned as MCP ImageContent.
        req = ws / "requests" / f"{secrets.token_hex(8)}.json"
        ledger.write_json(req, payload)
        try:
            ledger.record(argparse.Namespace(workspace=ws, stage=stage,
                                               image_id=image_id, json=req))
        finally:
            req.unlink(missing_ok=True)
        return {"saved": image_id, "stage": stage,
                "verification_level": "delivery_nonce_plus_model_self_attestation"}

    def _json_action(self, study_id: str, action: str, obj: dict) -> dict:
        ws = self._existing(study_id)
        req = ws / "requests" / f"{secrets.token_hex(8)}.json"
        ledger.write_json(req, obj)
        try:
            if action == "groups":
                ledger.set_groups(argparse.Namespace(workspace=ws, json=req))
            elif action == "select":
                ledger.set_selection(argparse.Namespace(workspace=ws, json=req))
            elif action == "style":
                ledger.state(ws)
                if not (ws / "selections.json").is_file():
                    raise ValueError("Select representative images first")
                if not isinstance(obj, dict) or not obj:
                    raise ValueError("Empty style synthesis")
                ledger.write_json(ws / "style_dna.json", obj)
            else:
                raise ValueError("Unsupported action")
        finally:
            req.unlink(missing_ok=True)
        return {"saved": action, "study_id": study_id}

    def assign_groups(self, study_id: str, groups: dict) -> dict:
        return self._json_action(study_id, "groups", {"groups": groups})

    def select(self, study_id: str, selected: dict) -> dict:
        return self._json_action(study_id, "select", selected)

    def style(self, study_id: str, style_dna: dict) -> dict:
        return self._json_action(study_id, "style", style_dna)

    def audit(self, study_id: str) -> dict:
        return ledger.audit(self._existing(study_id))

    def export(self, study_id: str) -> Path:
        ws = self._existing(study_id)
        target = ws / "result.zip"
        ledger.package(argparse.Namespace(workspace=ws, output=target))
        return target
