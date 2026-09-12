# Third-party notices

The AIX project code is licensed under `AGPL-3.0-only`. Third-party components retain their own licenses and copyright notices.

## Source dependencies

- Flask 3.1.3 — BSD-3-Clause
- Requests 2.34.2 — Apache-2.0
- websocket-client 1.9.0 — Apache-2.0
- Tailwind CSS browser build 3.4.17 and its bundled dependencies — upstream permissive licenses, including MIT; notices embedded in `static/tailwindcss.js` must be preserved

The pinned Python dependency list is in `requirements-web.txt`. The vendored browser bundle is included for offline use.

## Components not shipped in this source repository

ComfyUI, custom nodes, llama.cpp, FFmpeg, Python runtimes, MiniMax/Qwen models, LoRAs, VAEs, text encoders, and model packs are separate works. Their upstream licenses and model terms must be reviewed and included with each independently distributed runtime or model package. Inclusion in an AIX installation does not relicense them under the AIX license.
