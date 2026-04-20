#!/usr/bin/env python3
"""
Minimal local web timeline viewer for simulation events.

Run:
    python3 timeline_viewer.py --events events.jsonl --port 8000
Then open:
    http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML = """<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <title>Simulation Timeline</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: #0b1020; color: #e6edf3; }
    .wrap { max-width: 1050px; margin: 0 auto; padding: 20px; }
    h1 { margin: 0 0 16px; }
    .controls { display: flex; gap: 8px; margin-bottom: 12px; }
    select, input { background: #11182f; color: #e6edf3; border: 1px solid #27345f; border-radius: 6px; padding: 6px; }
    .event { background: #11182f; border: 1px solid #27345f; border-radius: 8px; padding: 10px; margin-bottom: 8px; }
    .meta { font-size: 12px; color: #9db0d0; margin-bottom: 6px; }
    code { background: #0d1428; padding: 2px 5px; border-radius: 4px; }
  </style>
</head>
<body>
  <div class='wrap'>
    <h1>Simulation Timeline</h1>
    <div class='controls'>
      <label>Type
        <select id='typeFilter'>
          <option value=''>All</option>
        </select>
      </label>
      <label>Search
        <input id='search' placeholder='agent, location, action...' />
      </label>
      <button id='refresh'>Refresh</button>
    </div>
    <div id='stats'></div>
    <div id='events'></div>
  </div>

<script>
async function loadEvents() {
  const resp = await fetch('/api/events');
  return await resp.json();
}

function renderStats(events) {
  const byType = {};
  for (const e of events) byType[e.type] = (byType[e.type] || 0) + 1;
  const text = Object.entries(byType).map(([k,v]) => `${k}: ${v}`).join(' | ');
  document.getElementById('stats').innerHTML = `<p><strong>Total:</strong> ${events.length} &nbsp; ${text}</p>`;
}

function ensureTypeOptions(events) {
  const sel = document.getElementById('typeFilter');
  const current = sel.value;
  const types = [...new Set(events.map(e => e.type))].sort();
  sel.innerHTML = `<option value=''>All</option>` + types.map(t => `<option value='${t}'>${t}</option>`).join('');
  sel.value = current;
}

function renderEvents(events) {
  const eventsRoot = document.getElementById('events');
  const typeFilter = document.getElementById('typeFilter').value;
  const query = document.getElementById('search').value.trim().toLowerCase();

  const filtered = events.filter(e => {
    const typeOK = !typeFilter || e.type === typeFilter;
    const raw = JSON.stringify(e.payload).toLowerCase();
    const queryOK = !query || raw.includes(query) || e.type.toLowerCase().includes(query);
    return typeOK && queryOK;
  });

  eventsRoot.innerHTML = filtered.map(e => {
    return `<div class='event'>
      <div class='meta'>Day ${e.day} ${String(e.hour).padStart(2, '0')}:00 · <code>${e.type}</code></div>
      <pre>${JSON.stringify(e.payload, null, 2)}</pre>
    </div>`;
  }).join('');
}

async function boot() {
  const events = await loadEvents();
  ensureTypeOptions(events);
  renderStats(events);
  renderEvents(events);

  document.getElementById('typeFilter').addEventListener('change', () => renderEvents(events));
  document.getElementById('search').addEventListener('input', () => renderEvents(events));
  document.getElementById('refresh').addEventListener('click', () => location.reload());
}

boot();
</script>
</body>
</html>"""


def load_events(path: Path):
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def make_handler(events_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if self.path == "/api/events":
                payload = json.dumps(load_events(events_path)).encode("utf-8")
                self._send(200, payload, "application/json; charset=utf-8")
                return
            self._send(404, b"Not Found", "text/plain; charset=utf-8")

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Timeline viewer for simulation events")
    parser.add_argument("--events", default="events.jsonl", help="Path to JSONL events file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events_path = Path(args.events)
    handler = make_handler(events_path)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving timeline viewer at http://{args.host}:{args.port} using {events_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
