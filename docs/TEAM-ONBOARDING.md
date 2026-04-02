# PII Guard – Team Onboarding

Hi Markus, hi Stephan,

PII Guard ist unser lokaler Datenschutz-Filter für Claude Code. Er prüft jeden Prompt bevor er an die API geht und blockiert personenbezogene Daten (Namen, E-Mails, Telefonnummern, IBANs). Alles läuft lokal — keine Cloud, kein Proxy.

## Warum machen wir das?

- **DSGVO/ISO 27001**: Wir müssen nachweisen können, dass PII nicht unkontrolliert an externe APIs fließt
- **Collana-Rollout**: PII Guard soll gruppenübergreifend ausgerollt werden — wir sind das Pilotteam
- **Audit-Trail**: Jeder PII-Fund wird protokolliert (wer, wann, was, welche Aktion)

## Was ist heute drin?

- PII-Erkennung: Personennamen, E-Mails, Telefonnummern (auch deutsche Formate, danke Markus fuer den Input zum Docker-Setup), IBANs, IP-Adressen, Kreditkarten
- Docker-Image auf Azure Container Registry (piiguard.azurecr.io) — kein lokales spaCy noetig
- Begründete Freigaben: `/allow "Begriff" Begründung` wenn PII Guard falsch liegt
- Ein/Aus-Toggle: `pii-guard off` oder `/pii-toggle` wenn es gerade nervt
- ISO 27001 Audit-Log mit Compliance-Reports
- CI Pipeline (pytest + ruff) bei jedem Pull Request

## Installation (10 Minuten)

### 1. Docker-Image holen

```bash
az login
az acr login --name piiguard
docker pull piiguard.azurecr.io/pii-guard:latest
```

### 2. Container starten

```bash
docker run -d -p 4141:4141 --restart=unless-stopped --name pii-guard piiguard.azurecr.io/pii-guard:latest
```

Prüfen: `curl http://localhost:4141/health`

### 3. CLI installieren

```bash
pip install git+https://github.com/b-imtec-gmbh/pii-guard.git
```

### 4. In eurem Projekt einrichten

```bash
cd /euer/projekt
pii-guard init
```

Das legt die Config an und installiert die Claude Code Skills.

### 5. Docker-Modus aktivieren

In `.pii-guard.yaml`:

```yaml
docker:
  enabled: true
```

### 6. Testen

```bash
pii-guard test "Max Müller hat angerufen"
```

## Wichtigste Befehle

| Was | Befehl |
|-----|--------|
| PII Guard ausschalten | `pii-guard off` oder `/pii-toggle` |
| PII Guard einschalten | `pii-guard on` oder `/pii-toggle` |
| Begriff freigeben | `/allow "Max Müller" Fiktiver Testname` |
| Freigabe widerrufen | `/revoke Max Müller` |
| Status anzeigen | `/pii-status` |
| PII-Erkennung testen | `pii-guard test "irgendein Text"` |

## Git-Konvention

Wir haben kein Branch Protection (braucht GitHub Team Plan), daher halten wir uns an diese Regeln:

### Nicht direkt auf main pushen

```
main = immer lauffähig, niemand pusht direkt
```

### Workflow

```
1. Feature-Branch erstellen    git checkout -b feature/mein-feature
2. Arbeiten, committen         git commit -m "Beschreibung"
3. Pushen                      git push -u origin feature/mein-feature
4. Pull Request erstellen      gh pr create (oder auf GitHub)
5. Mindestens 1 Review         Jemand anders schaut drüber
6. CI grün                     Tests + Lint müssen durchlaufen
7. Squash and Merge            Auf GitHub mergen
```

### Branch-Benennung

- `feature/confirm-flow` — neues Feature
- `fix/false-positives` — Bugfix
- `docs/setup-guide` — Dokumentation

### Commit Messages

Deutsch oder Englisch, kurz und klar. Kein Zwang zu Conventional Commits — wir sind zu dritt, kein Konzern.

## Fragen?

Einfach Thomas fragen oder ein Issue auf GitHub aufmachen.
