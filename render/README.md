# Thumbnail Forensics — Render Free bridge (prototype)

This project provides a private HTTP upload UI and a Streamable HTTP MCP server.
**GPT inside ChatGPT is the only visual analyst.** No vision API key or OCR model.

## Deploy

1. Put these files in a Git repository (e.g. a private repo).
2. On Render, **New → Blueprint** with this repo and `render.yaml`, or **New → Web Service**, plan **Free**, build `pip install -r requirements.txt`, start `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1`.
3. Create environment `THUMBNAIL_TOKEN` as a random secret, at least 32 characters (the Blueprint generates one). Keep it secret; NEVER paste it into ChatGPT messages.
4. Open `https://<your-service>.onrender.com/healthz`. Expect `status: ok`.
5. Open the root website `/`, enter your token in its password input and upload the PNG ZIP (<=125MiB compressed, <=768MiB uncompressed).
6. Copy the returned `study_id` to ChatGPT and connect your MCP server at `https://<your-service>.onrender.com/mcp` with API-key/Bearer authentication. Some ChatGPT configurations may not permit user-added remote MCP; that must be verified in the user's ChatGPT UI. Do NOT embed the token in the plugin ZIP.
7. Ask the agent to call `next_thumbnail` → `inspect_thumbnail` → `save_thumbnail_observation` one at a time. The model must write actual visible image evidence. Group, select five per category, reread selected, synthesize, export only after passing audit.
8. After every batch, open the web UI and download a *checkpoint*. Render Free has no persistent disk; use Restore if lost. Download final result ZIP from the web UI.

### Security

- All API and MCP routes require the same `Authorization: Bearer <THUMBNAIL_TOKEN>` header.
- The server refuses to start without `THUMBNAIL_TOKEN` at least 32 characters.
- Upload and extraction size caps, path checks, source SHA-256, nonces, and duplicate-record rules are enforced.
- Single-user/single-token application: do not share a deployment with unrelated people.
- Avoid uploading confidential thumbnails if Render is not an acceptable processor.

### Known limitations

- **No durable storage on Render Free**. This is a prototype; ZIP backups are manual. A free external object store and credentials would be needed for automatic durable persistence.
- Delivering MCP ImageContent does not itself prove the ChatGPT app actually renders it into model vision. **First test with 1 PNG**, compare visible text and characters, then expand to 10, 100, 1000.
- ChatGPT Chat message/tool limits, per-call latency, and automatic continuation are outside server control. Backend hosting does not create autonomous 1000-image processing.
- Potential FastMCP host allowlist/DNS rebinding protection issues behind Render; test live endpoint and configure the exact hostname if returned 421.
- Not a public/multi-user SaaS. Requires a functioning secure API key integration with ChatGPT plugin; if user's plugin system cannot supply authorization, do not expose token via URL or disable auth.
