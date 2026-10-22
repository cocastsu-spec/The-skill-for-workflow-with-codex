# Thumbnail Forensics — Render Free host

**Live service:** https://thumbnail-forensics-mcp-free.onrender.com
**MCP endpoint:** https://thumbnail-forensics-mcp-free.onrender.com/mcp
**Render dashboard:** https://dashboard.render.com/web/srv-dbcv7deq1p3s73ddvqbg
**GitHub branch:** `deploy/thumbnail-forensics-render-free` in `cocastsu-spec/The-skill-for-workflow-with-codex`.

Web service is Free plan in Singapore. Use `pip install -r render/requirements.txt` for build and `cd render && uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1` for startup. Set `THUMBNAIL_TOKEN` (random >=32 characters) securely in Render → Service → Environment. The process intentionally refuses to start without this variable. Do not disclose the key to ChatGPT or commit it to GitHub. Set it as the Bearer API key when connecting this plugin MCP (in `mcp.json`).

From `https://thumbnail-forensics-mcp-free.onrender.com/` enter that secret *on the private web form* and upload an image ZIP (PNG/JPG/JPEG/WebP) (<=125 MiB ZIP, <=768 MiB uncompressed). Copy only the returned `study_id` to ChatGPT Chat. Use MCP tool sequence as described in `../SKILL.md`. After each work batch, download checkpoint ZIP via the web page. On restoration a **new** study ID is returned. Render Free disks are ephemeral; missing backups can mean lost progress.

The app offers token-authenticated upload/status/checkpoint/restore/download and streamable HTTP MCP for image transport/recording. It does **not** run another vision model, and a successful MCP delivery receipt alone is not proof of GPT visual understanding. Run 1-image and 5-image live tests before processing ~1000 PNG. ChatGPT Chat tool/message limits may require repeated turns. Service is single-user and should not hold confidential content unless Render is an acceptable processor.

`/healthz` is public; `/api/*` and `/mcp` require bearer token. No secret belongs in Git, a plugin ZIP, chat message or URL query parameter.

### ZIP preflight and multi-format originals
Use the `Kiểm tra nội dung ZIP` button before upload. It reports image counts by extension and detects nested ZIPs. Direct PNG, JPEG, and WebP are accepted and their original bytes are preserved in analysis, MCP tool output, and final grouped ZIP. Nested ZIPs are reported but not silently recursively extracted. The GPT model remains the only visual analyst.
