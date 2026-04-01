# PII Guard – Field-Test-Feedback

**Datum:** 2026-04-01  
**Version:** 0.1.0 (pip-Installation)  
**Umgebung:** Windows 11, Python 3.12, Claude Code VS Code Extension  
**Modus:** Docker (`piiguard.azurecr.io/pii-guard:latest`, Port 7437)  
**Tester:** b-imtec (Praxiseinsatz, kein automatisierter QA-Lauf)

---

## Kontext

Erstinstallation und erster Praxiseinsatz von PII Guard als globaler Claude Code Hook
(gilt für alle Projekte und Sessions). Ergänzt den automatisierten QA-Testbericht
(`test-report-2026-04-01.md`) um reale Nutzererfahrungen und plattformspezifische Befunde.

---

## Kritischer Bug: Hook gibt bei Block Exit-Code 0 zurück

**Issue:** [#3](https://github.com/b-imtec-gmbh/pii-guard/issues/3)

`pii_guard.hook` schreibt bei Block-Entscheidungen `{"decision": "block", "reason": "..."}`
nach stdout und beendet sich mit Exit-Code 0.

**Verhalten in der Praxis:**

- **Claude Code CLI:** Claude Code injiziert den JSON-Output als Kontext-Text. Claude sieht
  `{"decision": "block"}` und antwortet gar nicht — der User bekommt keine Reaktion und
  keinen Hinweis.

- **VS Code Extension:** Gleiches Problem. Zusätzlich: Exit-Code 2 (als Workaround getestet)
  erscheint in der VS Code Extension nur in der Konsole/Output-Panel, nicht im Chat-Fenster.

**Workaround (lokal implementiert):**

Wrapper-Skript (`pii-guard-hook.py`), das den JSON-Output auswertet und bei Block
Exit-Code 0 mit einem Klartexttext ausgibt, der eine INSTRUCTION für Claude enthält
(damit Claude die Meldung im Chat relayed):

```python
if response.get("decision") == "block":
    reason = response.get("reason", "PII Guard: Prompt blockiert.")
    print(
        f"[PII Guard] {reason}\n"
        f"Bitte den Prompt anpassen und erneut senden. "
        f"Ausnahme möglich mit: /allow \"Begriff\" Begründung\n"
        f"INSTRUCTION: Gib dem User NUR diese PII-Guard-Meldung aus. "
        f"Beantworte die ursprüngliche Anfrage NICHT."
    )
    sys.exit(0)
```

**Empfehlung an Entwickler:**

`hook.py` sollte nativ das richtige Hook-Protokoll implementieren, damit kein Wrapper
nötig ist. Das korrekte Verhalten für Claude Code (CLI und VS Code Extension):

```python
# Bei Block: Klartext-Begründung + Exit 2 (CLI) ODER Exit 0 + Instruction (VS Code)
# Idealfall: Claude Code / VS Code Extension zeigen Exit-2-Blocks im Chat-Fenster.
# Alternativ: Dokumentieren welches Protokoll in welchem Client funktioniert.
```

---

## VS Code Extension: Exit-2-Blocks nicht im Chat sichtbar

**Beobachtung:** Wenn `hook.py` mit Exit-Code 2 beendet wird, zeigt die VS Code Extension
die Block-Begründung nur im Terminal/Output-Panel — nicht im Chat-Fenster, wo der User
den Prompt eingegeben hat.

**Impact:** Für VS Code-Nutzer (vermutlich der häufigste Einsatzkontext) ist der Block
faktisch unsichtbar — der User bekommt keine Antwort und keinen Hinweis.

**Empfehlung:** Entweder in der Dokumentation explizit auf dieses VS Code-Verhalten
hinweisen, oder das Hook-Protokoll so gestalten, dass Block-Meldungen in beiden
Umgebungen im Chat erscheinen.

---

## auto_mask wirkt wie block — Name irreführend

**Issue:** [#3 (Kommentar)](https://github.com/b-imtec-gmbh/pii-guard/issues/3)

Die `pii-guard test`-Ausgabe zeigt `[AUTO_MASK]` für Entitäten wie `PERSON` und
`EMAIL_ADDRESS`. Das impliziert, dass der Text ersetzt wird.

In der Praxis verhält sich `auto_mask` identisch zu `block` — Claude Code Hooks können
Prompts nicht modifizieren. Der `masked_preview` (`max***`) ist nur für die Fehlermeldung.

**Empfehlung:** In der `pii-guard test`-Ausgabe und der Dokumentation klarer kommunizieren:

```
[MASKIERBAR ] PERSON  Score: 0.85  'Tho***'   ← im Proxy-Modus ersetzbar, jetzt: block
[BLOCK      ] IBAN    Score: 1.00  'DE8***'   ← immer block
```

---

## Secrets werden nicht erkannt (API Keys, Passwörter, Azure Connection Strings)

**Issue:** [#1](https://github.com/b-imtec-gmbh/pii-guard/issues/1),
[#2](https://github.com/b-imtec-gmbh/pii-guard/issues/2)

Trotz konfigurierter Regeln (`action: block`) werden folgende Typen nicht erkannt:

| Muster | Konfigurierter Typ | Ergebnis |
|--------|-------------------|---------|
| `OPENAI_API_KEY=sk-proj-abc123...` | `API_KEY` | nicht erkannt |
| `aws_access_key_id = AKIAIOSFODNN7EXAMPLE` | `AWS_ACCESS_KEY` | nicht erkannt |
| `password=geheim123` | `PASSWORD` | nicht erkannt |
| `DefaultEndpointsProtocol=https;AccountName=...` | `AZURE_CONNECTION_STRING` | nicht erkannt |

Presidio scheint diese Recognizer nicht für die deutsche Language-Registry zu laden.
Im lokalen Modus sind entsprechende Warnungen sichtbar:
```
presidio-analyzer: Recognizer not added to registry because language is not supported
```

**Impact:** Kritisch — diese Daten sind häufige Leak-Vektoren in Coding-Prompts.

---

## Hook-Latenz ~364 ms im Docker-Modus (Windows)

**Issue:** [#2](https://github.com/b-imtec-gmbh/pii-guard/issues/2)

Gemessen über 10 Runs auf Windows 11 (Docker Desktop, localhost):

```
Ø 364 ms  (Min: 345 ms, Max: 397 ms)
```

Der QA-Testbericht nennt 113 ms (Warmstart) — mögliche Ursache der Differenz:
Python-Prozess-Startup auf Windows (~300 ms) wird bei jedem Hook-Aufruf neu fällig,
da Claude Code Hooks als Subprozess gestartet werden.

**Empfehlung:** Einen persistenten Hook-Daemon evaluieren (ähnlich dem Docker-Server,
aber für den Hook-Client), der ohne Python-Startup-Overhead auf dem localhost lauscht.

---

## Fehlende Startup-Prüfung: Container-Down unsichtbar

Bei nicht laufendem Container greift `on_error: allow` still — kein Hinweis im Chat.

**Workaround (lokal implementiert):** `pii-guard-startup-check.py` — prüft einmal pro
Session per TCP-Check ob Port 7437 erreichbar ist. Bei Fehler: Warnung als Claude-Kontext.

```python
# Einmalige Prüfung pro Session via session_id aus Hook-Input
if not is_running(host="127.0.0.1", port=7437):
    print("[PII Guard] WARNUNG: Container nicht erreichbar. Prompts werden nicht gefiltert!")
```

**Empfehlung:** Als optionalen Check in `pii-guard init` und `pii-guard on` aufnehmen.

---

## Feature-Anfrage: Bidirektionales PII-Mapping (Proxy-Modus)

**Issue:** [#4](https://github.com/b-imtec-gmbh/pii-guard/issues/4)

Usecase: Konzeptionspapiere und Dokumentation mit echten Namen erstellen, ohne PII
an externe APIs zu übertragen. Gewünschter Ablauf:

```
Eingabe:   "Schreibe ein Konzept für Max Mustermann (max@firma.de)"
→ Claude:  "Schreibe ein Konzept für [PERSON_001] ([EMAIL_001])"
← Claude:  "Hier ist ein Konzept für [PERSON_001]..."
→ User:    "Hier ist ein Konzept für Max Mustermann..."
```

Die Infrastruktur (`mapper.py`, `substitutor.py`) ist bereits vorhanden. Fehlt:
eine Integration, die eingehende Prompts und ausgehende Antworten transformiert
(Hooks reichen dafür nicht — sie können Prompts nicht modifizieren).

**Mögliche Umsetzung:** Lokaler HTTP-Proxy zwischen Claude Code und Anthropic-API.

---

## Claude Code Skills in VS Code Extension ohne Ausgabe

`pii-guard init` installiert drei Slash-Commands in `~/.claude/commands/`:
`allow.md`, `revoke.md`, `pii-status.md`.

In der VS Code Extension werden diese als Eingabe akzeptiert (`/allow`, `/revoke`,
`/pii-status`), produzieren aber **keine Ausgabe im Chat**. Die Extension injiziert
den Skill-Inhalt als Prompt an Claude, Claude müsste dann einen Bash-Befehl ausführen —
eine möglicherweise nötige Bestätigungsdialog erscheint in VS Code nicht.

**Zusätzliches Problem:** Die Skill-Dateien rufen `pii-guard` ohne Pfad auf. Auf Windows
liegt `pii-guard.exe` unter `%APPDATA%\Python\Python312\Scripts\`, das nicht im
Standard-PATH ist. Folge: Bash-Aufruf schlägt silent fehl, keine Rückmeldung.

**Workaround:** Terminal-Befehle sind zuverlässiger:

```powershell
pii-guard allow "Begriff" --reason "Begründung"
pii-guard revoke "Begriff"
pii-guard status
pii-guard overrides
```

**Empfehlung an Entwickler:**
1. Skill-Dateien sollten `python -m pii_guard.cli` statt `pii-guard` verwenden
   (plattformunabhängig, kein PATH-Problem)
2. Dokumentieren, dass Skills in der VS Code Extension anders als in der CLI funktionieren

---

## Audit-Log: projektlokal, aber Hook läuft global

Das Audit-Log wird relativ zum aktuellen Verzeichnis geschrieben
(`audit.path: .pii-guard/audit.log` in `.pii-guard.yaml`). Der Hook läuft global
(für alle Projekte), aber nur Projekte mit einer `.pii-guard.yaml` erzeugen ein Log.

**Beobachtung:** `pii-guard status` zeigt 0 Einträge, wenn der Befehl aus einem
Verzeichnis ohne aktive Config aufgerufen wird (z.B. dem geklonten Source-Repo).
Das befüllte Log liegt im Projektverzeichnis, das die Config enthält.

**Konsequenz:** Prompts aus Projekten ohne `.pii-guard.yaml` werden zwar gefiltert
(über die User-Level-Config), aber **nicht auditiert**. Das ist eine Lücke für
ISO-27001-Compliance-Anforderungen.

**Empfehlung:** Audit-Log-Pfad in der User-Level-Config
(`%APPDATA%/pii-guard/config.yaml`) auf einen absoluten, globalen Pfad setzen,
z.B. `%APPDATA%/pii-guard/audit.log`. Alternativ: `pii-guard init` explizit darauf
hinweisen, dass Auditing nur mit projektspezifischer Config funktioniert.

---

## Zusammenfassung offener Punkte

| # | Titel | Priorität | Issue |
|---|-------|-----------|-------|
| 1 | Hook Exit-Code 0 bei Block | Kritisch | [#3](https://github.com/b-imtec-gmbh/pii-guard/issues/3) |
| 2 | Secrets nicht erkannt | Kritisch | [#1](https://github.com/b-imtec-gmbh/pii-guard/issues/1) |
| 3 | VS Code Exit-2 nicht im Chat | Hoch | [#3](https://github.com/b-imtec-gmbh/pii-guard/issues/3) |
| 4 | auto_mask-Bezeichnung irreführend | Mittel | [#3](https://github.com/b-imtec-gmbh/pii-guard/issues/3) |
| 5 | Latenz ~364 ms (Windows) | Mittel | [#2](https://github.com/b-imtec-gmbh/pii-guard/issues/2) |
| 6 | Container-Down unsichtbar | Mittel | – |
| 7 | Skills in VS Code ohne Ausgabe + PATH-Problem | Mittel | – |
| 8 | Audit-Log nur mit projektspezifischer Config | Mittel | – |
| 9 | Bidirektionales Mapping | Feature | [#4](https://github.com/b-imtec-gmbh/pii-guard/issues/4) |
