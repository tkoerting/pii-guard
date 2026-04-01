# PII Guard – Entscheidungshistorie

Dieses Dokument protokolliert die wesentlichen Architektur- und Designentscheidungen, wer sie getroffen hat und warum. Es dient als Nachweis der Urheberschaft und Entscheidungsgrundlage für zukünftige Änderungen.

## Autor und Urheberschaft

**Autor**: Thomas Körting / b-imtec GmbH
**Erstellt**: 2026-03-31
**Lizenz**: MIT

PII Guard wurde von Thomas Körting konzipiert, architektonisch entworfen und durch alle Entwicklungsphasen gesteuert. Die Implementierung erfolgte mit Unterstützung von Claude (Anthropic). Alle Architektur-, Design- und Geschäftsentscheidungen wurden von Thomas Körting getroffen.

---

## Entscheidungen

### E0: Projektidee und Zweck
- **Datum**: 2026-03-31
- **Entscheidung**: Entwicklung eines lokalen PII-Filters für KI-Coding-Tools
- **Begründung**: Entwickler arbeiten mit echten Kundendaten. Jeder Prompt an Claude Code, Cursor oder Copilot kann PII enthalten. Es gibt kein Tool das diesen Kanal automatisch schützt.
- **Entscheider**: Thomas Körting

### E1: Lokale Architektur (kein Cloud-Proxy)
- **Datum**: 2026-03-31
- **Entscheidung**: Alles läuft lokal. Kein Proxy-Server, kein Cloud-Dienst, kein neuer Datenverarbeiter.
- **Begründung**: Ein Cloud-Proxy wäre selbst ein Datenverarbeiter und bräuchte einen AVV. Lokale Verarbeitung eliminiert dieses Problem vollständig.
- **Alternativen verworfen**: Cloud-basierter PII-Filter (zu viel Compliance-Overhead), Browser-Extension (kein Zugang zum Prompt-Kanal)
- **Entscheider**: Thomas Körting

### E2: Hook-basierter Ansatz (user_prompt_submit)
- **Datum**: 2026-03-31
- **Entscheidung**: Claude Code Hook als primärer Einstiegspunkt
- **Begründung**: Claude Code bietet nativ einen Hook-Mechanismus der vor dem API-Call greift. Kein Wrapper, kein Proxy nötig.
- **Entscheider**: Thomas Körting

### E3: Typerhaltende Substitution statt Platzhalter
- **Datum**: 2026-03-31
- **Entscheidung**: Fake-Daten im gleichen Format statt [PERSON_1] Platzhalter
- **Begründung**: Platzhalter produzieren kaputte KI-Ergebnisse. Typerhaltende Fake-Daten (Max Müller -> Hans Schmidt) ermöglichen korrekte KI-Antworten.
- **Entscheider**: Thomas Körting

### E4: Microsoft Presidio als NER-Engine
- **Datum**: 2026-03-31
- **Entscheidung**: Presidio + spaCy für PII-Erkennung
- **Begründung**: Etablierte Open-Source-Lösung (MIT-Lizenz), unterstützt Deutsch und Englisch, erweiterbar, aktiv gepflegt von Microsoft.
- **Alternativen verworfen**: Regex-basierter Ansatz (zu viele False Negatives), kommerzielle NER-APIs (Cloud-Abhängigkeit)
- **Entscheider**: Thomas Körting

### E5: Docker als optionales Backend
- **Datum**: 2026-03-31
- **Entscheidung**: Docker-Daemon als Alternative zur lokalen pip-Installation
- **Begründung**: spaCy-Modelle sind ~1 GB groß und die Installation auf Windows-Rechnern ist fehleranfällig. Docker eliminiert Installationsprobleme und ermöglicht einfache Updates.
- **Auslöser**: Feedback von Markus (Collana-Gruppe): "Damit wir nicht abhängig von der lokalen Installation sind, würde ich dafür plädieren das ganze Konstrukt in Docker laufen zu lassen."
- **Entscheider**: Thomas Körting + Markus

### E6: ISO 27001 Audit-Funktion
- **Datum**: 2026-03-31
- **Entscheidung**: 15-Felder Audit-Log nach ISO 27002:2022 Clause 8.15
- **Begründung**: Ein Auditor muss nachweisen können: Was wurde erkannt, welche Aktion wurde durchgeführt, wann, durch wen, auf welchem System, mit welcher Config-Version. 5 Felder reichen nicht, 15 decken die ISO-Anforderungen ab.
- **Grundlage**: Recherche zu ISO 27001:2022 Controls A.8.11, A.8.12, A.8.15, A.5.34 und DSGVO Art. 32
- **Review**: Auditor-Agent hat den Audit-Plan geprüft und 6 Findings eingebracht (tool_version, config_hash, PASS/FAIL-Schwellenwerte, False-Positive-Tests, Allow-List im Report, keep_days auf 365)
- **Entscheider**: Thomas Körting

### E7: Windows-Kompatibilität als Pflicht
- **Datum**: 2026-03-31
- **Entscheidung**: Windows-Support ab Phase 1, nicht als Nachgedanke
- **Begründung**: Thomas ist der einzige bei b-imtec mit Mac. Der Rest des Teams und die Collana-Gruppe arbeiten auf Windows. Ohne Windows-Support kann niemand außer Thomas das Tool nutzen.
- **Maßnahmen**: Plattform-Weichen für Dateipfade (%APPDATA% vs. ~/.config), atomares Schreiben (os.replace + Windows-Fallback), chmod nur auf Unix, konsistente Line-Endings
- **Entscheider**: Thomas Körting

### E8: Collana IT Gruppen-Rollout
- **Datum**: 2026-03-31
- **Entscheidung**: PII Guard als gemeinsames Tool für die Collana IT Gruppe
- **Begründung**: Jede Firma in der Gruppe nutzt oder plant KI-Tools. Gemeinsamer Standard ist effizienter als Einzellösungen. Einheitliches Audit-Format ermöglicht gruppenweites Reporting.
- **Strategie**: Demo -> Pilot (2-3 Firmen) -> Gruppen-Rollout
- **Entscheider**: Thomas Körting

### E9: Strengen-Rangfolge für Config-Merge
- **Datum**: 2026-03-31
- **Entscheidung**: `block > auto_mask > warn` – eine untere Config-Ebene kann Sicherheits-Settings nicht abschwächen
- **Begründung**: Architekten-Review hat Edge Cases identifiziert: Was passiert wenn eine Projekt-Config eine Gruppen-Block-Rule auf "warn" setzt? Darf nicht möglich sein.
- **Entscheider**: Thomas Körting (nach Architekten-Review)

### E10: 3 Sekunden Docker-Timeout
- **Datum**: 2026-03-31
- **Entscheidung**: HTTP-Call an Docker-Container mit 3s Timeout (nicht 4s)
- **Begründung**: Claude Code Hook hat 5s Timeout. Bei 4s bleiben nur 1s für Config-Laden und I/O. 3s lassen 2s Puffer.
- **Entscheider**: Thomas Körting (nach Architekten-Review)

### E11: Kein curl|bash Onboarding
- **Datum**: 2026-03-31
- **Entscheidung**: Kein `curl | bash` Installationsscript
- **Begründung**: Architekten-Review hat das als Sicherheits-Antipattern identifiziert. Stattdessen dokumentierter Onboarding-Guide.
- **Entscheider**: Thomas Körting (nach Architekten-Review)

---

## Reviews

| Datum | Typ | Scope | Findings |
|-------|-----|-------|----------|
| 2026-03-31 | Arch-Review | Gesamtprojekt | 6 Säulen, Report in tech-sparring/reviews/pii-guard_review.md |
| 2026-03-31 | ISO 27001 Recherche | Audit-Anforderungen | 7 Controls, 15 Pflichtfelder, 7 Nachweisdokumente |
| 2026-03-31 | Auditor-Agent | Audit-Plan | 6 Findings (tool_version, config_hash, PASS/FAIL, False Positives, Allow-List, keep_days) |
| 2026-03-31 | Architekten-Review | Gesamtplan | Scope-Reduktion, Config-Edge-Cases, Timeout, Windows, curl|bash |
| 2026-03-31 | Code Review 1 | Phase 1 | 13 Findings, 10 gefixt, 2 auf spätere Phasen verschoben |
| 2026-03-31 | Code Review 2 | Phase 2 | 12 Findings, alle gefixt |
| 2026-04-01 | Code Review 3 | Phase 3 | 9 Findings, alle gefixt |
