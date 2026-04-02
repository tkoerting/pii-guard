# Field-Test Feedback — Session 2 (2026-04-01)

Tester: [Person-01]
Setup: Windows 11, Claude Code VS Code Extension, Python 3.12

## 1. Upstream-Fixes getestet

Commits getestet: `543ef40` (Fix #1/#2/#3/#6) + `b9adeae` (Proxy-Modus #4)

### Issue #1 — API Key Recognizer

| Testfall | Ergebnis |
|----------|----------|
| OpenAI Key `sk-proj-...` | BLOCK (lokal) |
| AWS Key `AKIA...` | BLOCK (lokal) |
| Azure Connection String | BLOCK (lokal) |

Status: **Fix funktioniert** (lokaler Modus). Docker-Image auf ACR noch nicht aktualisiert.

### Issue #2 — Password Recognizer

| Testfall | Ergebnis |
|----------|----------|
| `password=geheim123` | BLOCK (lokal) |

Status: **Fix funktioniert** (lokaler Modus).

### Issue #3 — Exit-Code

- `python -m pii_guard.hook` gibt jetzt korrekt Exit 2 + Reason auf stderr aus
- **VS Code Extension zeigt Exit-2-Blocks weiterhin nur in der Konsole, nicht im Chat-Fenster**
- Workaround (Exit 0 + INSTRUCTION-Text) bleibt fuer VS Code notwendig
- Fix ist technisch korrekt, Problem liegt in der VS Code Extension

### Issue #6 — False Positives

| Testfall | Ergebnis |
|----------|----------|
| "Adam Optimizer" | Korrekt nicht erkannt |
| "Max Pooling" | Korrekt nicht erkannt |
| "Xavier Initialization" | Korrekt nicht erkannt |

Status: **Fix funktioniert**.

### Regression (bestehende Erkennungen)

| Testfall | Ergebnis |
|----------|----------|
| Name + E-Mail | BLOCK |
| IBAN | BLOCK |
| Telefon +49 | BLOCK |

Status: **Keine Regression**.

## 2. Docker-Image (ACR) nicht aktualisiert

Nach `az acr login && docker pull piiguard.azurecr.io/pii-guard:latest` ist das Image
identisch (gleicher Digest). Neue Recognizer (#1, #2) funktionieren im Docker-Modus nicht.

**Aktion:** Image neu bauen und nach ACR pushen.

## 3. Proxy-Modus (#4) — End-to-End-Test

### Setup
- Proxy auf Port 7438: `python -c "from pii_guard.proxy import run_proxy; run_proxy()"`
- `ANTHROPIC_BASE_URL=http://localhost:7438` als Windows User-Variable

### Ergebnisse

**Masking-Pipeline (isoliert getestet):**
```
Original:  "Thomas Koerting, thomas.koerting@b-imtec.de"
Maskiert:  "Frau Susanne Seifert, sonialiebelt@example.org"
Reverse:   "Thomas Koerting, thomas.koerting@b-imtec.de"
```
-> Detection, Substitution und Reverse-Mapping funktionieren korrekt.

**End-to-End (curl -> Proxy -> Anthropic API -> Proxy -> Client):**
- API-Call mit PII erfolgreich durchgeleitet
- Antwort enthaelt Originaldaten (Reverse-Mapping korrekt)
- Claude (Haiku) hat mit den Fake-Daten gearbeitet, nicht mit den Originalen

### Gefundene Probleme

**Problem 1: Gzip-Dekomprimierung (502)**
```
{"error":"PII Guard Proxy: 'utf-8' codec can't decode byte 0x8b in position 1: invalid start byte"}
```
Ursache: Anthropic API antwortet mit `Content-Encoding: gzip` trotz `Accept-Encoding: identity`.

Fix (3 Aenderungen in proxy.py):
1. `import gzip as _gzip`
2. `"content-encoding"` zu `_HOP_BY_HOP` (Body wird unkomprimiert neu serialisiert)
3. `headers["Accept-Encoding"] = "identity"` + Fallback-Dekomprimierung

**Problem 2: Request too large bei langen Sessions (Issue #8)**
Der Proxy setzt `stream: false`, wodurch der gesamte Konversationskontext als ein
synchroner Request gesendet wird. Bei laengeren Sessions (>30 Nachrichten) ueberschreitet
das die 20MB-Grenze der Anthropic API.

-> Proxy-Modus derzeit nur fuer kurze Sessions nutzbar.
-> Issue #8 mit Loesungsvorschlaegen eingereicht.

**Problem 3: Streaming deaktiviert (UX)**
Auch bei kurzen Sessions: Antworten erscheinen erst komplett statt wortweise.
Akzeptabel fuer Testing, aber UX-Einschraenkung im Alltag.

## 4. Hook-Modus — Grundsaetzliche Einschraenkung

Claude Code Hooks koennen Prompts **nicht modifizieren** — nur Exit 0 (allow) oder Exit 2 (block).
`auto_mask` im Hook-Modus ist daher identisch mit `block`. Echtes bidirektionales Masking
funktioniert nur ueber den Proxy-Modus.

Zusaetzlich: VS Code Extension zeigt Exit-2-Blocks nur in der Konsole, nicht im Chat.
INSTRUCTION-Relay-Workaround (Exit 0 + Text fuer Claude) ist fragil — Claude reformatiert
die Meldung gelegentlich.

## 5. Zusammenfassung

| Feature | Status |
|---------|--------|
| API Key Recognizer (#1) | Funktioniert (lokal) |
| Password Recognizer (#2) | Funktioniert (lokal) |
| Exit-Code Fix (#3) | Korrekt, aber VS Code zeigt Exit 2 nicht im Chat |
| Proxy-Modus (#4) | Funktioniert, aber stream:false verursacht Request-Limit |
| False-Positive-Fix (#6) | Funktioniert |
| Docker-Image (ACR) | Nicht aktualisiert |
| Gzip-Fix (Proxy) | Lokal gefixt, PR pending |
