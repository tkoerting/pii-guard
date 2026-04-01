# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""Claude Code Hook – user_prompt_submit.

Dieses Script wird von Claude Code als Hook aufgerufen.
Es empfängt den Prompt auf stdin als JSON und gibt eine Entscheidung zurück.

Registrierung in der Claude Code settings.json (Pfad plattformabhängig):
{
  "hooks": {
    "user_prompt_submit": [
      {
        "command": "python -m pii_guard.hook",
        "timeout": 5000
      }
    ]
  }
}
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from uuid import uuid4

from pii_guard.config import load_config

log = logging.getLogger("pii_guard.hook")


def _is_docker_mode(config: dict) -> bool:
    """Prüft ob Docker-Modus aktiv ist (Env-Variable hat Vorrang vor Config)."""
    env = os.environ.get("PII_GUARD_DOCKER")
    if env is not None:
        return env.lower() in ("1", "true", "yes")
    return config.get("docker", {}).get("enabled", False)


def _process_via_docker(prompt: str, config: dict) -> dict:
    """Sendet den Prompt an den Docker-Daemon zur Verarbeitung."""
    docker_config = config.get("docker", {})
    host = docker_config.get("host", "127.0.0.1")
    port = docker_config.get("port", 7437)
    url = f"http://{host}:{port}/process"

    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        on_error = config.get("on_error", "allow")
        log.warning("Docker-Daemon nicht erreichbar (%s), Fallback: %s", e, on_error)
        if on_error == "block":
            return {
                "decision": "block",
                "reason": (
                    "PII Guard: Docker-Daemon nicht erreichbar, "
                    "Prompt geblockt (on_error: block)"
                ),
            }
        return {"decision": "allow"}


def process_prompt(prompt: str, config: dict, *, session_id: str | None = None) -> dict:
    """Verarbeitet einen Prompt und gibt die Hook-Entscheidung zurück.

    Claude Code unterstützt kein 'prompt'-Feld in der Hook-Antwort.
    Daher wird bei PII-Funden geblockt (decision: block) mit einer
    Auflistung der gefundenen Daten. Der User kann dann entscheiden,
    ob er den Prompt anpassen möchte.

    Warnungen (action: warn) werden als systemMessage durchgereicht,
    blockieren aber nicht.
    """
    from pii_guard.audit import log_findings
    from pii_guard.detector import detect_pii

    sid = session_id or str(uuid4())
    findings = detect_pii(prompt, config)

    if not findings:
        from pii_guard.audit import log_event
        log_event("PROMPT_ALLOWED", config, session_id=sid, details={"pii_count": 0})
        return {"decision": "allow"}

    log_findings(findings, config, session_id=sid, prompt=prompt)

    # Harte Secrets – immer blocken
    blocked = [f for f in findings if f.action == "block"]
    if blocked:
        reasons = [f"{f.entity_type}: '{f.masked_preview}'" for f in blocked]
        return {
            "decision": "block",
            "reason": f"PII Guard: Sensible Daten erkannt – {', '.join(reasons)}",
        }

    # Auto-Mask Findings – ebenfalls blocken, da wir den Prompt
    # nicht modifizieren können
    masks = [f for f in findings if f.action == "auto_mask"]
    warnings = [f for f in findings if f.action == "warn"]

    if masks:
        details = [f"{f.entity_type}: '{f.masked_preview}'" for f in masks]
        reason = (
            f"PII Guard: Personenbezogene Daten erkannt"
            f" – {', '.join(details)}."
            f" Bitte entferne die PII aus deinem Prompt."
        )
        if warnings:
            warn_parts = [f"{f.entity_type}: '{f.masked_preview}'" for f in warnings]
            reason += f" Zusaetzlich erkannt (Warnung): {', '.join(warn_parts)}"
        return {
            "decision": "block",
            "reason": reason,
        }

    # Nur Warnungen – durchlassen mit Hinweis
    if warnings:
        warn_parts = [f"{f.entity_type}: '{f.masked_preview}'" for f in warnings]
        return {
            "decision": "allow",
            "systemMessage": f"PII Guard Hinweis: {', '.join(warn_parts)} erkannt (nicht maskiert)",
        }

    return {"decision": "allow"}


def main() -> None:
    """Entry point für den Claude Code Hook."""
    # Logging auf stderr – stdout ist für Hook-JSON reserviert
    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        input_data = json.loads(sys.stdin.read())
        prompt = input_data.get("prompt", "")

        if not prompt:
            json.dump({"decision": "allow"}, sys.stdout)
            return

        config = load_config()

        if _is_docker_mode(config):
            result = _process_via_docker(prompt, config)
        else:
            result = process_prompt(prompt, config)

        json.dump(result, sys.stdout)

    except Exception as e:
        # Bei Fehler: Prompt durchlassen, aber loggen
        json.dump({"decision": "allow"}, sys.stdout)
        log.error("Fehler bei Prompt-Verarbeitung: %s", e)


if __name__ == "__main__":
    main()
