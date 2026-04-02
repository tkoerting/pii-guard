#!/usr/bin/env bash
# pii-guard-statusline.sh – PII Guard Status fuer die Claude Code Statusleiste
#
# Konfiguration in ~/.claude/settings.json:
# {
#   "statusLine": {
#     "type": "command",
#     "command": "bash /pfad/zu/piiguard/pii-guard-statusline.sh"
#   }
# }
#
# Anzeige:
#   PII aktiv          Hook registriert, Container healthy, nicht pausiert
#   PII: pausiert      Filterung manuell pausiert
#   PII: kein Container  Hook aktiv, Container nicht erreichbar
#   PII: inaktiv       Hook nicht in settings.json registriert
#
# Konfiguration per Umgebungsvariable:
#   PII_GUARD_URL       API-Basis-URL (Default: http://127.0.0.1:4141)
#   PII_GUARD_FLAG_DIR  Verzeichnis mit der disabled-Flagdatei
#                       (Default: ~/mydocker/piiguard/.pii-guard)

PII_GUARD_URL="${PII_GUARD_URL:-http://127.0.0.1:4141}"
PII_GUARD_FLAG_DIR="${PII_GUARD_FLAG_DIR:-$HOME/mydocker/piiguard/.pii-guard}"
SETTINGS="$HOME/.claude/settings.json"

# 1. Hook registriert?
if ! [ -f "$SETTINGS" ]; then
    echo "PII: inaktiv"
    exit 0
fi

if command -v jq &>/dev/null; then
    hook_found=$(jq -r '.hooks.UserPromptSubmit // [] | .[].hooks // [] | .[].command' \
        "$SETTINGS" 2>/dev/null | grep -c "pii-guard" || true)
else
    hook_found=$(grep -c "pii-guard" "$SETTINGS" 2>/dev/null || true)
fi

if [ "${hook_found:-0}" -eq 0 ]; then
    echo "PII: inaktiv"
    exit 0
fi

# 2. Pausiert?
if [ -f "$PII_GUARD_FLAG_DIR/disabled" ]; then
    echo "PII: pausiert"
    exit 0
fi

# 3. Container erreichbar?
if ! curl -sf --max-time 1 "$PII_GUARD_URL/health" >/dev/null 2>&1; then
    echo "PII: kein Container"
    exit 0
fi

echo "PII aktiv"
exit 0
