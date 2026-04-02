# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""HTTP API Server für Docker-basiertes PII Guard Backend.

Läuft als Daemon im Container, empfängt Prompts per HTTP und gibt
Hook-Entscheidungen zurück. Nutzt process_prompt() aus hook.py.

Endpoints:
  POST /process        – Hook-API (wird vom pii-guard-hook.sh aufgerufen)
  GET  /health         – Health-Check
  GET  /               – Web-UI: Status-Dashboard
  GET  /test           – Web-UI: PII-Erkennung testen
  POST /test           – Web-UI: Testformular auswerten
  GET  /report         – Web-UI: Audit-Report (?from=YYYY-MM-DD&to=YYYY-MM-DD)
  GET  /export         – Web-UI: Audit-Log als CSV herunterladen
  GET  /overrides      – Web-UI: Overrides verwalten
  POST /overrides/add  – Web-UI: Override hinzufügen
  POST /overrides/remove – Web-UI: Override entfernen

Starten: python -m pii_guard.server [--port 4141] [--config /pfad/config.yaml]
"""

from __future__ import annotations

import html
import json
import logging
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pii_guard
from pii_guard.config import load_config
from pii_guard.hook import process_prompt

log = logging.getLogger("pii_guard.server")

_lock = threading.Lock()


def _h(text: object) -> str:
    """HTML-escaping für sichere Ausgabe von User-Daten."""
    return html.escape(str(text))


class PiiGuardHandler(BaseHTTPRequestHandler):
    """HTTP Handler für PII Guard API und Web-UI."""

    config: dict = {}

    # ── Routing ──────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        routes = {
            "/": self._handle_dashboard,
            "/health": self._handle_health,
            "/test": self._handle_test_form,
            "/report": self._handle_report,
            "/export": self._handle_export,
            "/overrides": self._handle_overrides,
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        routes = {
            "/process": self._handle_process,
            "/test": self._handle_test_submit,
            "/overrides/add": self._handle_override_add,
            "/overrides/remove": self._handle_override_remove,
        }
        handler = routes.get(self.path)
        if handler:
            handler()
        else:
            self.send_error(404)

    # ── API Endpoints ─────────────────────────────────────────────────────────

    def _handle_process(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self.send_error(400, "Content-Length fehlt oder ist 0")
                return
            body = self.rfile.read(length)
            data = json.loads(body)
            prompt = data.get("prompt", "")

            if not prompt:
                self._send_json({"decision": "allow"})
                return

            with _lock:
                result = process_prompt(prompt, self.config)

            self._send_json(result)

        except Exception as e:
            log.error("Fehler bei /process: %s", e)
            self._send_json({"decision": "allow"}, status=500)

    def _handle_health(self) -> None:
        self._send_json({
            "status": "ok",
            "version": pii_guard.__version__,
        })

    # ── Web-UI Helpers ────────────────────────────────────────────────────────

    def _parse_query(self) -> dict:
        if "?" in self.path:
            _, qs = self.path.split("?", 1)
            return dict(urllib.parse.parse_qsl(qs))
        return {}

    def _read_form(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return dict(urllib.parse.parse_qsl(body))

    def _send_html(self, html_content: str, status: int = 200) -> None:
        body = html_content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_csv(self, csv_str: str, filename: str) -> None:
        body = csv_str.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _page(self, title: str, content: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_h(title)} – PII Guard</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,sans-serif;background:#f0f2f5;color:#1a1a1a;line-height:1.5}}
  nav{{background:#1a1a2e;color:#fff;padding:.75rem 1.5rem;display:flex;align-items:center;gap:1.5rem}}
  nav .brand{{font-weight:700;font-size:1.1rem;color:#fff;margin-right:.5rem}}
  nav a{{color:#a0c4ff;text-decoration:none;font-size:.9rem}}
  nav a:hover{{color:#fff}}
  main{{max-width:920px;margin:2rem auto;padding:0 1rem}}
  h1{{font-size:1.5rem;margin-bottom:1.25rem;color:#1a1a2e}}
  h2{{font-size:1rem;font-weight:600;margin:1.25rem 0 .6rem;color:#444;text-transform:uppercase;letter-spacing:.04em}}
  .card{{background:#fff;border-radius:8px;padding:1.5rem;margin-bottom:1rem;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  .stats{{display:flex;flex-wrap:wrap;gap:.75rem;margin-bottom:1rem}}
  .stat{{background:#f8f9fa;border-radius:6px;padding:.75rem 1.25rem;min-width:110px}}
  .stat-value{{font-size:1.8rem;font-weight:700;color:#1a1a2e}}
  .stat-label{{font-size:.75rem;color:#666;text-transform:uppercase;letter-spacing:.05em}}
  table{{width:100%;border-collapse:collapse;font-size:.9rem}}
  th{{text-align:left;padding:.5rem .75rem;background:#f8f9fa;border-bottom:2px solid #e5e7eb;color:#555;font-weight:600}}
  td{{padding:.5rem .75rem;border-bottom:1px solid #f0f0f0;vertical-align:top}}
  tr:last-child td{{border-bottom:none}}
  .badge{{display:inline-block;padding:.15rem .5rem;border-radius:4px;font-size:.8rem;font-weight:700}}
  .badge-block{{background:#fee2e2;color:#b91c1c}}
  .badge-mask{{background:#fef3c7;color:#92400e}}
  .badge-warn{{background:#dbeafe;color:#1e40af}}
  .badge-allow{{background:#dcfce7;color:#166534}}
  .form-group{{margin-bottom:.9rem}}
  label{{display:block;font-size:.88rem;font-weight:500;margin-bottom:.25rem;color:#444}}
  input[type=text],input[type=date],textarea{{width:100%;padding:.45rem .7rem;border:1px solid #d1d5db;border-radius:6px;font-size:.95rem;font-family:inherit}}
  textarea{{font-family:monospace;resize:vertical;min-height:120px}}
  button{{padding:.45rem 1.2rem;border:none;border-radius:6px;cursor:pointer;font-size:.95rem;font-weight:500;background:#1a1a2e;color:#fff}}
  button:hover{{background:#2d2d4e}}
  .btn-danger{{background:#dc2626}}
  .btn-danger:hover{{background:#b91c1c}}
  .btn-sm{{padding:.25rem .7rem;font-size:.8rem}}
  .alert{{padding:.7rem 1rem;border-radius:6px;margin-bottom:1rem;font-size:.9rem}}
  .alert-error{{background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5}}
  .alert-success{{background:#dcfce7;color:#166534;border:1px solid #86efac}}
  .mono{{font-family:monospace;font-size:.85rem}}
  .empty{{color:#9ca3af;font-style:italic;text-align:center;padding:2rem}}
  .row{{display:flex;gap:1rem;align-items:flex-end}}
  .row .form-group{{flex:1;margin-bottom:0}}
</style>
</head>
<body>
<nav>
  <span class="brand">PII Guard</span>
  <a href="/">Status</a>
  <a href="/test">Testen</a>
  <a href="/report">Audit-Report</a>
  <a href="/export">CSV-Export</a>
  <a href="/overrides">Overrides</a>
</nav>
<main>
{content}
</main>
</body>
</html>"""

    # ── Web-UI Endpoints ──────────────────────────────────────────────────────

    def _handle_dashboard(self) -> None:
        from pii_guard.audit import _read_log_entries

        config = self.config
        audit_path = Path(config.get("audit", {}).get("path", ".pii-guard/audit.log"))
        entries = _read_log_entries(audit_path)

        total = len(entries)
        blocked = sum(1 for e in entries if e.get("action_taken") == "BLOCK")
        masked = sum(1 for e in entries if e.get("action_taken") == "MASK")
        warned = sum(1 for e in entries if e.get("action_taken") == "WARN")
        last_ts = entries[-1].get("timestamp", "")[:19].replace("T", " ") if entries else "–"

        rules = config.get("rules", [])
        allow_list = config.get("allow_list", [])

        content = f"""
<h1>Status</h1>
<div class="card">
  <div class="stats">
    <div class="stat"><div class="stat-value">{total}</div><div class="stat-label">Audit-Eintraege</div></div>
    <div class="stat"><div class="stat-value">{blocked}</div><div class="stat-label">Blockiert</div></div>
    <div class="stat"><div class="stat-value">{masked}</div><div class="stat-label">Maskiert</div></div>
    <div class="stat"><div class="stat-value">{warned}</div><div class="stat-label">Gewarnt</div></div>
  </div>
  <table>
    <tr><th>Version</th><td>{_h(pii_guard.__version__)}</td></tr>
    <tr><th>Regeln</th><td>{len(rules)}</td></tr>
    <tr><th>Allow-List</th><td>{len(allow_list)} Eintraege</td></tr>
    <tr><th>Audit-Log</th><td class="mono">{_h(audit_path)}</td></tr>
    <tr><th>Letzter Eintrag</th><td>{_h(last_ts)}</td></tr>
  </table>
</div>"""
        self._send_html(self._page("Status", content))

    def _handle_test_form(self, result_html: str = "") -> None:
        content = f"""
<h1>PII-Erkennung testen</h1>
<div class="card">
  <form method="post" action="/test">
    <div class="form-group">
      <label for="text">Text eingeben</label>
      <textarea id="text" name="text" placeholder="z.B. Max Müller, max@firma.de, +49 170 1234567"></textarea>
    </div>
    <button type="submit">Analysieren</button>
  </form>
</div>
{result_html}"""
        self._send_html(self._page("Testen", content))

    def _handle_test_submit(self) -> None:
        from pii_guard.detector import detect_pii

        form = self._read_form()
        text = form.get("text", "").strip()

        if not text:
            self._handle_test_form()
            return

        with _lock:
            findings = detect_pii(text, self.config)

        if not findings:
            result_html = '<div class="card"><p class="badge badge-allow">Keine PII erkannt</p></div>'
        else:
            rows = ""
            for f in findings:
                badge_cls = {"block": "badge-block", "auto_mask": "badge-mask", "warn": "badge-warn"}.get(f.action, "badge-allow")
                rows += f"""<tr>
  <td><span class="badge {badge_cls}">{_h(f.action.upper())}</span></td>
  <td>{_h(f.entity_type)}</td>
  <td>{_h(f"{f.score:.0%}")}</td>
  <td class="mono">{_h(f.masked_preview)}</td>
</tr>"""
            result_html = f"""<div class="card">
<h2>Ergebnis</h2>
<table>
  <tr><th>Aktion</th><th>PII-Typ</th><th>Konfidenz</th><th>Vorschau</th></tr>
  {rows}
</table>
</div>"""

        self._handle_test_form(result_html)

    def _handle_report(self) -> None:
        from pii_guard.audit import _read_log_entries

        params = self._parse_query()
        from_date = params.get("from", "")
        to_date = params.get("to", "")

        config = self.config
        audit_path = Path(config.get("audit", {}).get("path", ".pii-guard/audit.log"))
        entries = _read_log_entries(audit_path, from_date or None, to_date or None)

        # Datumsfilter-Formular
        filter_form = f"""
<div class="card">
  <form method="get" action="/report">
    <div class="row">
      <div class="form-group">
        <label>Von</label>
        <input type="date" name="from" value="{_h(from_date)}">
      </div>
      <div class="form-group">
        <label>Bis</label>
        <input type="date" name="to" value="{_h(to_date)}">
      </div>
      <button type="submit">Filtern</button>
      &nbsp;
      <a href="/export?from={_h(from_date)}&amp;to={_h(to_date)}"><button type="button">CSV herunterladen</button></a>
    </div>
  </form>
</div>"""

        if not entries:
            content = f"<h1>Audit-Report</h1>{filter_form}<div class='card'><p class='empty'>Keine Eintraege im angegebenen Zeitraum.</p></div>"
            self._send_html(self._page("Audit-Report", content))
            return

        # Zusammenfassung
        by_type: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for e in entries:
            t = e.get("pii_type") or ""
            a = e.get("action_taken") or ""
            if t:
                by_type[t] = by_type.get(t, 0) + 1
            if a:
                by_action[a] = by_action.get(a, 0) + 1

        type_rows = "".join(
            f"<tr><td>{_h(t)}</td><td>{c}</td></tr>"
            for t, c in sorted(by_type.items(), key=lambda x: -x[1])
        )
        action_rows = "".join(
            f"<tr><td>{_h(a)}</td><td>{c}</td></tr>"
            for a, c in sorted(by_action.items(), key=lambda x: -x[1])
        )

        scores = [e.get("confidence_score", 0) for e in entries if e.get("confidence_score", 0) > 0]
        score_html = ""
        if scores:
            score_html = f"""
<div class="card">
  <h2>Konfidenz-Statistik</h2>
  <table>
    <tr><th>Durchschnitt</th><td>{sum(scores)/len(scores):.0%}</td></tr>
    <tr><th>Minimum</th><td>{min(scores):.0%}</td></tr>
    <tr><th>Maximum</th><td>{max(scores):.0%}</td></tr>
  </table>
</div>"""

        content = f"""
<h1>Audit-Report</h1>
{filter_form}
<div class="card">
  <div class="stats">
    <div class="stat"><div class="stat-value">{len(entries)}</div><div class="stat-label">Eintraege gesamt</div></div>
  </div>
</div>
<div class="card">
  <h2>Nach PII-Typ</h2>
  <table><tr><th>Typ</th><th>Anzahl</th></tr>{type_rows}</table>
</div>
<div class="card">
  <h2>Nach Aktion</h2>
  <table><tr><th>Aktion</th><th>Anzahl</th></tr>{action_rows}</table>
</div>
{score_html}"""
        self._send_html(self._page("Audit-Report", content))

    def _handle_export(self) -> None:
        from pii_guard.audit import export_csv

        params = self._parse_query()
        from_date = params.get("from") or None
        to_date = params.get("to") or None

        csv_str = export_csv(self.config, from_date, to_date)
        self._send_csv(csv_str, "pii-guard-audit.csv")

    def _handle_overrides(self, message: str = "", error: str = "") -> None:
        from pii_guard.overrides import list_overrides

        overrides = list_overrides(self.config)

        alert_html = ""
        if message:
            alert_html = f'<div class="alert alert-success">{_h(message)}</div>'
        elif error:
            alert_html = f'<div class="alert alert-error">{_h(error)}</div>'

        rows = ""
        if overrides:
            for entry in overrides:
                entity = _h(entry.get("entity_type") or "–")
                rows += f"""<tr>
  <td>{_h(entry.get("term", ""))}</td>
  <td>{_h(entry.get("reason", ""))}</td>
  <td>{entity}</td>
  <td>{_h(entry.get("added_by", ""))}</td>
  <td>{_h((entry.get("timestamp") or "")[:10])}</td>
  <td>
    <form method="post" action="/overrides/remove" style="display:inline">
      <input type="hidden" name="term" value="{_h(entry.get("term", ""))}">
      <button type="submit" class="btn-danger btn-sm">Widerrufen</button>
    </form>
  </td>
</tr>"""
        else:
            rows = '<tr><td colspan="6" class="empty">Keine aktiven Freigaben.</td></tr>'

        content = f"""
<h1>Overrides</h1>
{alert_html}
<div class="card">
  <h2>Freigabe hinzufügen</h2>
  <form method="post" action="/overrides/add">
    <div class="row">
      <div class="form-group">
        <label>Begriff</label>
        <input type="text" name="term" placeholder="z.B. Siemens AG" required>
      </div>
      <div class="form-group">
        <label>PII-Typ (optional)</label>
        <input type="text" name="entity_type" placeholder="z.B. ORGANIZATION">
      </div>
    </div>
    <div class="form-group">
      <label>Begründung (Pflichtfeld)</label>
      <input type="text" name="reason" placeholder="Warum ist das kein PII?" required>
    </div>
    <div class="form-group">
      <label>Hinzugefügt von</label>
      <input type="text" name="who" placeholder="Name oder Kürzel">
    </div>
    <button type="submit">Freigeben</button>
  </form>
</div>
<div class="card">
  <h2>Aktive Freigaben</h2>
  <table>
    <tr><th>Begriff</th><th>Begründung</th><th>PII-Typ</th><th>Von</th><th>Datum</th><th></th></tr>
    {rows}
  </table>
</div>"""
        self._send_html(self._page("Overrides", content))

    def _handle_override_add(self) -> None:
        from pii_guard.audit import log_event
        from pii_guard.overrides import add_override

        form = self._read_form()
        term = form.get("term", "").strip()
        reason = form.get("reason", "").strip()
        who = form.get("who", "").strip() or None
        entity_type = form.get("entity_type", "").strip() or None

        if not term or not reason:
            self._handle_overrides(error="Begriff und Begründung sind Pflichtfelder.")
            return

        try:
            entry = add_override(term, reason, self.config, who=who, entity_type=entity_type)
            log_event("OVERRIDE_ADDED", self.config, details={
                "term": term,
                "reason": reason,
                "added_by": entry["added_by"],
                "entity_type": entity_type or "",
            })
            self._redirect(f"/overrides?msg={urllib.parse.quote(f'Freigegeben: {term}')}")
        except ValueError as e:
            self._handle_overrides(error=str(e))

    def _handle_override_remove(self) -> None:
        from pii_guard.audit import log_event
        from pii_guard.overrides import remove_override

        form = self._read_form()
        term = form.get("term", "").strip()

        if not term:
            self._redirect("/overrides")
            return

        removed = remove_override(term, self.config)
        if removed:
            log_event("OVERRIDE_REMOVED", self.config, details={
                "term": term,
                "removed_entry": removed,
            })
            self._redirect(f"/overrides?msg={urllib.parse.quote(f'Freigabe widerrufen: {term}')}")
        else:
            self._redirect(f"/overrides?error={urllib.parse.quote(f'Keine Freigabe für: {term}')}")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Umleitung des HTTP-Logs auf Python logging."""
        log.debug(format, *args)


def run_server(
    host: str = "0.0.0.0",
    port: int = 4141,
    config_path: str | None = None,
) -> None:
    """Startet den PII Guard HTTP-Server."""
    config = load_config(Path(config_path) if config_path else None)
    PiiGuardHandler.config = config

    # Engine-Warmup: spaCy-Modell vorladen damit der erste Request schnell ist
    log.info("Engine-Warmup startet...")
    from pii_guard.detector import _get_engine
    _get_engine(config)
    log.info("Engine-Warmup abgeschlossen")

    server = HTTPServer((host, port), PiiGuardHandler)
    server.daemon_threads = True
    log.info("PII Guard Server gestartet auf %s:%d", host, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Server wird beendet")
        server.shutdown()


def main() -> None:
    """Entry point: python -m pii_guard.server"""
    import argparse

    parser = argparse.ArgumentParser(description="PII Guard HTTP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind-Adresse (Default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=4141, help="Port (Default: 4141)")
    parser.add_argument("--config", dest="config_path", help="Pfad zur Config-Datei")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    run_server(host=args.host, port=args.port, config_path=args.config_path)


if __name__ == "__main__":
    main()
