# Änderungen im Branch `compose`

## Web-UI: Status-Dashboard

- **Letzte 10 Log-Einträge**: Neue Tabelle unterhalb der Status-Zusammenfassung zeigt die neuesten Audit-Einträge (Zeitpunkt, Event-Typ, PII-Typ, Aktion, Vorschau), neuester Eintrag zuerst.
- **Lokale Zeitanzeige**: Alle Zeitstempel werden jetzt client-seitig im Browser in die lokale Zeitzone umgewandelt (`data-utc`-Attribut + JavaScript). Damit wird die korrekte Lokalzeit unabhängig von der Server- bzw. Container-Zeitzone (UTC) angezeigt.

## Dockerfile

- **Redundanz beseitigt**: Das Base-Image `python:3.11-slim` wird nur noch einmal als `ARG BASE` definiert und in beiden Stages (`builder` und Runtime) referenziert.
