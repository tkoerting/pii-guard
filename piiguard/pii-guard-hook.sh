#!/usr/bin/env bash
# PII Guard Hook – ersetzt python3 -m pii_guard.hook im Docker-Modus
#
# Voraussetzungen: curl, jq  (WSL2: apt install curl jq)
#
# Registrierung in ~/.claude/settings.json:
# {
#   "hooks": {
#     "UserPromptSubmit": [{
#       "matcher": "",
#       "hooks": [{"type": "command", "command": "/pfad/zu/pii-guard-hook.sh", "timeout": 5000}]
#     }]
#   }
# }
#
# Konfiguration per Umgebungsvariable:
#   PII_GUARD_URL      – API-URL (Default: http://127.0.0.1:4141/process)
#   PII_GUARD_ON_ERROR – Verhalten wenn Container nicht erreichbar: allow|block (Default: allow)

set -euo pipefail

ON_ERROR="${PII_GUARD_ON_ERROR:-allow}"
URL="${PII_GUARD_URL:-http://127.0.0.1:4141/process}"

# Abhängigkeiten prüfen – bei fehlenden Tools Prompt durchlassen
if ! command -v jq &>/dev/null; then
    printf 'PII Guard: jq nicht gefunden. Installation: apt install jq\n' >&2
    exit 0
fi
if ! command -v curl &>/dev/null; then
    printf 'PII Guard: curl nicht gefunden. Installation: apt install curl\n' >&2
    exit 0
fi

INPUT=$(cat)
PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // ""')

if [ -z "$PROMPT" ]; then
    printf '{"decision":"allow"}'
    exit 0
fi

# Prompt als JSON-String kodieren (verhindert Injection durch Sonderzeichen)
PROMPT_JSON=$(printf '%s' "$PROMPT" | jq -R -s '.')

RESULT=$(curl -s --max-time 3 \
    -X POST \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": $PROMPT_JSON}" \
    "$URL" 2>/dev/null) || RESULT=""

if [ -z "$RESULT" ]; then
    if [ "$ON_ERROR" = "block" ]; then
        printf 'PII Guard: Container nicht erreichbar. Starte mit: docker start pii-guard\n' >&2
        exit 2
    fi
    printf '{"decision":"allow"}'
    exit 0
fi

DECISION=$(printf '%s' "$RESULT" | jq -r '.decision // "allow"')

printf '%s' "$RESULT"
exit 0
