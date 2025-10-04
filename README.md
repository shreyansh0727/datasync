# DataShare

FastAPI + WebSockets + static HTML/CSS/JS for LAN/Internet data sharing.

## Run
- Create venv, install requirements, then start the server:
  - `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Open the server root in a browser to load the UI.

## How it works
- `/` serves `static/index.html`.
- `/static` serves CSS/JS assets via StaticFiles.
- `/ws/{room_id}` provides room-based WebSocket broadcast for messages and chunked file transfer (JSON-wrapped byte arrays).
- `/signal/{room_id}` is an optional signaling bus stub for later WebRTC data channels.

## Notes
- For production WSS, put the app behind TLS termination and ensure reverse proxy supports WebSockets.
- Zeroconf lines are provided (commented) to advertise `_datasync._tcp.local` for LAN discovery.
