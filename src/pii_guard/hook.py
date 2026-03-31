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
                "reason": "PII Guard: Docker-Daemon nicht erreichbar, Prompt geblockt (on_error: block)",
            }
        return {"decision": "allow"}


def process_prompt(prompt: str, config: dict, *, session_id: str | None = None) -> dict:
    """Verarbeitet einen Prompt und gibt die Hook-Entscheidung zurück."""
    # Lazy Imports: schwere Abhängigkeiten (Presidio, spaCy, Faker) erst hier laden.
    # Im Docker-Modus wird diese Funktion nicht aufgerufen – der Hook bleibt dünn.
    from pii_guard.detector import detect_pii
    from pii_guard.substitutor import substitute_pii
    from pii_guard.mapper import SessionMapper
    from pii_guard.audit import log_findings

    sid = session_id or str(uuid4())
    findings = detect_pii(prompt, config)

    if not findings:
        from pii_guard.audit import log_event
        log_event("PROMPT_ALLOWED", config, session_id=sid, details={"pii_count": 0})
        return {"decision": "allow"}

    # Prüfe ob etwas geblockt werden muss
    blocked = [f for f in findings if f.action == "block"]
    if blocked:
        reasons = [f"{f.entity_type}: '{f.masked_preview}'" for f in blocked]
        log_findings(findings, config, session_id=sid, prompt=prompt)
        return {
            "decision": "block",
            "reason": f"PII Guard: Sensible Daten erkannt – {', '.join(reasons)}",
        }

    warnings = [f for f in findings if f.action == "warn"]
    masks = [f for f in findings if f.action == "auto_mask"]

    log_findings(findings, config, session_id=sid, prompt=prompt)

    # Warn-Message zusammenbauen (falls Warnungen vorhanden)
    warn_message = ""
    if warnings:
        warn_parts = [f"{f.entity_type}: '{f.masked_preview}'" for f in warnings]
        warn_message = f"PII Guard Hinweis: {', '.join(warn_parts)} erkannt (nicht maskiert)"

    # Auto-Mask anwenden
    if masks:
        mapper = SessionMapper(config)
        substituted_prompt = substitute_pii(prompt, masks, mapper, config)
        result = {"decision": "allow", "prompt": substituted_prompt}
        if warn_message:
            result["message"] = warn_message
        return result

    if warnings:
        return {"decision": "allow", "message": warn_message}

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
