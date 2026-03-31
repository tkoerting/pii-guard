"""Claude Code Hook – user_prompt_submit.

Dieses Script wird von Claude Code als Hook aufgerufen.
Es empfängt den Prompt auf stdin als JSON und gibt eine Entscheidung zurück.

Registrierung in ~/.claude/settings.json:
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
import sys

from pii_guard.config import load_config
from pii_guard.detector import detect_pii
from pii_guard.substitutor import substitute_pii
from pii_guard.mapper import SessionMapper
from pii_guard.audit import log_findings


def process_prompt(prompt: str, config: dict) -> dict:
    """Verarbeitet einen Prompt und gibt die Hook-Entscheidung zurück."""
    findings = detect_pii(prompt, config)

    if not findings:
        return {"decision": "allow"}

    # Prüfe ob etwas geblockt werden muss
    blocked = [f for f in findings if f.action == "block"]
    if blocked:
        reasons = [f"{f.entity_type}: '{f.masked_preview}'" for f in blocked]
        log_findings(findings, config)
        return {
            "decision": "block",
            "reason": f"PII Guard: Sensible Daten erkannt – {', '.join(reasons)}",
        }

    # Prüfe ob Warnungen vorliegen (User entscheidet)
    warnings = [f for f in findings if f.action == "warn"]
    masks = [f for f in findings if f.action == "auto_mask"]

    # Auto-Mask anwenden
    if masks:
        mapper = SessionMapper(config)
        substituted_prompt = substitute_pii(prompt, masks, mapper, config)
        log_findings(findings, config)
        return {"decision": "allow", "prompt": substituted_prompt}

    if warnings:
        # Warnungen loggen, aber durchlassen
        log_findings(findings, config)
        return {"decision": "allow"}

    return {"decision": "allow"}


def main() -> None:
    """Entry point für den Claude Code Hook."""
    try:
        input_data = json.loads(sys.stdin.read())
        prompt = input_data.get("prompt", "")

        if not prompt:
            json.dump({"decision": "allow"}, sys.stdout)
            return

        config = load_config()
        result = process_prompt(prompt, config)
        json.dump(result, sys.stdout)

    except Exception as e:
        # Bei Fehler: Prompt durchlassen, aber loggen
        json.dump({"decision": "allow"}, sys.stdout)
        sys.stderr.write(f"PII Guard Error: {e}\n")


if __name__ == "__main__":
    main()
