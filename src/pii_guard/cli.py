# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""CLI für PII Guard."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from pii_guard.config import load_config, find_config_path


@click.group()
def main() -> None:
    """PII Guard – Lokaler Datenschutz-Filter für KI-Coding-Tools."""
    pass


@main.command()
@click.option("--with-gitleaks", is_flag=True, help="Gitleaks Pre-Commit Hook mitinstallieren")
def init(with_gitleaks: bool) -> None:
    """Initialisiert PII Guard im aktuellen Projekt."""
    config_path = Path(".pii-guard.yaml")

    if config_path.exists():
        click.echo(f"Config existiert bereits: {config_path}")
    else:
        config_path.write_text(_MINIMAL_CONFIG)
        click.echo(f"Config angelegt: {config_path}")

    # .pii-guard Verzeichnis erstellen
    guard_dir = Path(".pii-guard")
    guard_dir.mkdir(exist_ok=True)
    gitignore = guard_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("session-map.json\n")
    click.echo(f"Guard-Verzeichnis: {guard_dir}/")

    # Claude Code Hook-Hinweis
    from pii_guard.config import _user_config_dir
    import sys as _sys
    claude_settings = "~\\.claude\\settings.json" if _sys.platform == "win32" else "~/.claude/settings.json"
    click.echo("")
    click.echo("Claude Code Hook registrieren:")
    click.echo(f"  Füge in {claude_settings} hinzu:")
    click.echo("")
    hook_config = {
        "hooks": {
            "user_prompt_submit": [
                {"command": "python -m pii_guard.hook", "timeout": 5000}
            ]
        }
    }
    click.echo(f"  {json.dumps(hook_config, indent=2)}")

    if with_gitleaks:
        click.echo("")
        if shutil.which("gitleaks"):
            click.echo("Gitleaks gefunden. Pre-Commit Hook wird aktiviert...")
            pre_commit = Path(".pre-commit-config.yaml")
            if not pre_commit.exists():
                pre_commit.write_text(_PRECOMMIT_CONFIG)
                click.echo(f"Pre-Commit Config angelegt: {pre_commit}")
            else:
                click.echo(f"Pre-Commit Config existiert bereits: {pre_commit}")
        else:
            click.echo("Gitleaks nicht gefunden. Installation:")
            click.echo("  brew install gitleaks")


@main.command()
@click.argument("text")
def test(text: str) -> None:
    """Testet die PII-Erkennung auf einem Text (Trockenlauf)."""
    from pii_guard.detector import detect_pii

    config = load_config()
    findings = detect_pii(text, config)

    if not findings:
        click.echo("Keine PII erkannt.")
        return

    for f in findings:
        color = {"block": "red", "auto_mask": "yellow", "warn": "blue"}.get(f.action, "white")
        click.secho(
            f"  [{f.action.upper():10s}] {f.entity_type:20s} "
            f"Score: {f.score:.2f}  '{f.masked_preview}'",
            fg=color,
        )


@main.command()
@click.option("--check", is_flag=True, help="Exit-Code 1 wenn keine Config gefunden")
def status(check: bool) -> None:
    """Zeigt den aktuellen PII Guard Status."""
    config_path = find_config_path()

    if config_path:
        click.echo(f"Config: {config_path}")
        config = load_config()
        rules = config.get("rules", [])
        click.echo(f"Regeln: {len(rules)} definiert")
        allow_list = config.get("allow_list", [])
        click.echo(f"Allow-List: {len(allow_list)} Einträge")

        audit_path = Path(config.get("audit", {}).get("path", ".pii-guard/audit.log"))
        if audit_path.exists():
            lines = len(audit_path.read_text().splitlines())
            click.echo(f"Audit-Log: {audit_path} ({lines} Einträge)")
        else:
            click.echo("Audit-Log: noch keine Einträge")
    else:
        click.echo("Keine Config gefunden. Führe 'pii-guard init' aus.")
        if check:
            raise SystemExit(1)


@main.command(name="audit-export")
@click.option("--from", "from_date", help="Ab Datum (YYYY-MM-DD)")
@click.option("--output", "-o", help="Ausgabedatei (Default: stdout)")
def audit_export(from_date: str | None, output: str | None) -> None:
    """Exportiert das Audit-Log als CSV."""
    from pii_guard.audit import export_csv

    config = load_config()
    csv_data = export_csv(config, from_date)

    if output:
        Path(output).write_text(csv_data, encoding="utf-8")
        click.echo(f"Exportiert nach: {output}")
    else:
        click.echo(csv_data)


@main.command(name="audit-report")
@click.option("--from", "from_date", help="Ab Datum (YYYY-MM-DD)")
@click.option("--to", "to_date", help="Bis Datum (YYYY-MM-DD)")
@click.option("--format", "fmt", type=click.Choice(["markdown", "csv"]), default="markdown")
@click.option("--output", "-o", help="Ausgabedatei (Default: stdout)")
def audit_report(from_date: str | None, to_date: str | None, fmt: str, output: str | None) -> None:
    """Generiert einen strukturierten Compliance-Report."""
    from pii_guard.audit import _read_log_entries, export_csv, _config_hash
    import pii_guard

    config = load_config()
    audit_config = config.get("audit", {})
    log_path = Path(audit_config.get("path", ".pii-guard/audit.log"))

    if fmt == "csv":
        result = export_csv(config, from_date, to_date)
        if output:
            Path(output).write_text(result, encoding="utf-8")
            click.echo(f"Exportiert nach: {output}")
        else:
            click.echo(result)
        return

    entries = _read_log_entries(log_path, from_date, to_date)

    # Markdown Report
    lines = ["# PII Guard Audit-Report", ""]
    lines.append(f"- **Zeitraum**: {from_date or 'Beginn'} bis {to_date or 'heute'}")
    from datetime import datetime as _dt
    import getpass as _getpass
    lines.append(f"- **Erstellt am**: {_dt.now().isoformat()[:19]}")
    lines.append(f"- **Erstellt durch**: {_getpass.getuser()}")
    lines.append(f"- **PII Guard Version**: {pii_guard.__version__}")
    lines.append(f"- **Config-Hash**: {_config_hash(config)}")
    lines.append(f"- **Geprüft durch**: ___")
    lines.append("")

    if not entries:
        lines.append("Keine Einträge im angegebenen Zeitraum.")
    else:
        lines.append("## Zusammenfassung")
        lines.append("")
        lines.append(f"- **Einträge gesamt**: {len(entries)}")

        # Nach PII-Typ
        by_type: dict[str, int] = {}
        for e in entries:
            t = e.get("pii_type") or e.get("entity_type", "")
            if t:
                by_type[t] = by_type.get(t, 0) + 1

        if by_type:
            lines.append("")
            lines.append("## Aufschlüsselung nach PII-Typ")
            lines.append("")
            lines.append("| PII-Typ | Anzahl |")
            lines.append("|---------|--------|")
            for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
                lines.append(f"| {t} | {count} |")

        # Nach Aktion
        by_action: dict[str, int] = {}
        for e in entries:
            a = e.get("action_taken") or e.get("action", "")
            if a:
                by_action[a] = by_action.get(a, 0) + 1

        if by_action:
            lines.append("")
            lines.append("## Aufschlüsselung nach Aktion")
            lines.append("")
            lines.append("| Aktion | Anzahl |")
            lines.append("|--------|--------|")
            for a, count in sorted(by_action.items(), key=lambda x: -x[1]):
                lines.append(f"| {a} | {count} |")

        # Confidence-Statistik
        all_scores = [e.get("confidence_score") or e.get("score", 0) for e in entries]
        scores = [s for s in all_scores if s > 0]
        if scores:
            lines.append("")
            lines.append("## Confidence-Statistik")
            lines.append("")
            lines.append(f"- **Durchschnitt**: {sum(scores) / len(scores):.2f}")
            lines.append(f"- **Minimum**: {min(scores):.2f}")
            lines.append(f"- **Maximum**: {max(scores):.2f}")

        # Allow-List
        allow_list = config.get("allow_list", [])
        if allow_list:
            lines.append("")
            lines.append("## Allow-List")
            lines.append("")
            for item in allow_list:
                lines.append(f"- {item}")

        # Exceptions (outcome=FAILURE)
        failures = [e for e in entries if e.get("outcome") == "FAILURE"]
        if failures:
            lines.append("")
            lines.append("## Exceptions")
            lines.append("")
            lines.append(f"**{len(failures)} Fehler im Zeitraum.**")

        # Wirksamkeitstests
        tests = [e for e in entries if e.get("event_type") == "EFFECTIVENESS_TEST"]
        if tests:
            lines.append("")
            lines.append("## Wirksamkeitstests")
            lines.append("")
            lines.append(f"- **Anzahl Testläufe**: {len(tests)}")
            lines.append(f"- **Letzter Test**: {tests[-1].get('timestamp', 'unbekannt')}")

    report = "\n".join(lines) + "\n"

    if output:
        Path(output).write_text(report, encoding="utf-8")
        click.echo(f"Report exportiert nach: {output}")
    else:
        click.echo(report)


@main.command(name="audit-test")
@click.option("--export", "export_path", help="CSV-Export-Pfad")
def audit_test(export_path: str | None) -> None:
    """Führt Wirksamkeitstests durch und protokolliert das Ergebnis."""
    from pii_guard.detector import detect_pii
    from pii_guard.audit import log_event

    config = load_config()
    min_rate = config.get("test", {}).get("min_detection_rate", 0.8)

    # Positive Testfälle: PII die erkannt werden MUSS
    positive_cases = [
        ("PERSON", "Max Müller arbeitet hier"),
        ("PERSON", "Dr. Anna Schmidt ist Ärztin"),
        ("EMAIL_ADDRESS", "Kontakt: max.mueller@firma.de"),
        ("PHONE_NUMBER", "Telefon: +49 170 1234567"),
        ("LOCATION", "Er wohnt in München"),
        ("IBAN_CODE", "IBAN: DE89 3704 0044 0532 0130 00"),
        ("PERSON", "John Smith is here"),
        ("EMAIL_ADDRESS", "Contact: john@example.com"),
    ]

    # Negative Testfälle: KEINE PII, darf NICHT maskiert werden
    negative_cases = [
        "Die Max Pool Layer hat 3x3 Kernel",
        "Adam Optimizer mit Lernrate 0.001",
        "SELECT * FROM users WHERE id = 42",
        "Der Code nutzt Python 3.11",
    ]

    results = []
    click.echo("PII Guard Wirksamkeitstest")
    click.echo("=" * 50)

    # Positive Tests
    click.echo("\nPositive Tests (PII muss erkannt werden):")
    type_stats: dict[str, dict] = {}
    for expected_type, text in positive_cases:
        findings = detect_pii(text, config)
        found_types = {f.entity_type for f in findings}
        detected = expected_type in found_types
        score = max((f.score for f in findings if f.entity_type == expected_type), default=0.0)

        if expected_type not in type_stats:
            type_stats[expected_type] = {"total": 0, "detected": 0}
        type_stats[expected_type]["total"] += 1
        if detected:
            type_stats[expected_type]["detected"] += 1

        status = click.style("OK", fg="green") if detected else click.style("FAIL", fg="red")
        click.echo(f"  {status}  {expected_type:20s}  Score: {score:.2f}  '{text[:40]}'")
        results.append({
            "test_type": "positive",
            "expected_type": expected_type,
            "text": text[:40],
            "detected": detected,
            "score": score,
        })

    # Negative Tests
    click.echo("\nNegative Tests (Keine PII, darf nicht maskiert werden):")
    false_positives = 0
    for text in negative_cases:
        findings = detect_pii(text, config)
        mask_findings = [f for f in findings if f.action == "auto_mask"]
        is_clean = len(mask_findings) == 0

        status = click.style("OK", fg="green") if is_clean else click.style("FAIL", fg="red")
        fp_types = ", ".join(f.entity_type for f in mask_findings) if mask_findings else "-"
        click.echo(f"  {status}  '{text[:50]}'  False Positives: {fp_types}")
        if not is_clean:
            false_positives += 1
        results.append({
            "test_type": "negative",
            "expected_type": "",
            "text": text[:50],
            "detected": not is_clean,
            "score": 0.0,
        })

    # PASS/FAIL pro Typ
    click.echo("\nErkennungsrate pro Typ:")
    click.echo("-" * 50)
    all_pass = True
    for pii_type, stats in sorted(type_stats.items()):
        rate = stats["detected"] / stats["total"] if stats["total"] > 0 else 0
        passed = rate >= min_rate
        if not passed:
            all_pass = False
        status = click.style("PASS", fg="green") if passed else click.style("FAIL", fg="red")
        click.echo(f"  {status}  {pii_type:20s}  {stats['detected']}/{stats['total']}  ({rate:.0%}, Minimum: {min_rate:.0%})")

    if false_positives > 0:
        all_pass = False
        click.secho(f"\n  FAIL  {false_positives} False Positive(s) in negativen Tests", fg="red")
    else:
        click.secho(f"\n  PASS  Keine False Positives", fg="green")

    # Gesamtergebnis
    click.echo("\n" + "=" * 50)
    if all_pass:
        click.secho("ERGEBNIS: BESTANDEN", fg="green", bold=True)
    else:
        click.secho("ERGEBNIS: NICHT BESTANDEN", fg="red", bold=True)

    # Ins Audit-Log schreiben
    log_event("EFFECTIVENESS_TEST", config, details={
        "outcome": "SUCCESS" if all_pass else "FAILURE",
        "action_taken": f"positive:{len(positive_cases)},negative:{len(negative_cases)},fp:{false_positives}",
    })

    # CSV-Export
    if export_path:
        import csv
        with Path(export_path).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["test_type", "expected_type", "text", "detected", "score"])
            writer.writeheader()
            writer.writerows(results)
        click.echo(f"\nTestprotokoll exportiert nach: {export_path}")


@main.command()
@click.argument("term")
@click.option("--reason", "-r", required=True, help="Begründung für die Freigabe")
@click.option("--who", "-w", help="Wer gibt frei (Default: aktueller User)")
@click.option("--type", "entity_type", help="PII-Typ (z.B. PERSON, ORGANIZATION)")
def allow(term: str, reason: str, who: str | None, entity_type: str | None) -> None:
    """Gibt einen Begriff begründet frei (Override).

    Beispiel: pii-guard allow "Max Müller" --reason "Fiktiver Testname in Doku"
    """
    from pii_guard.overrides import add_override
    from pii_guard.audit import log_event

    config = load_config()

    try:
        entry = add_override(term, reason, config, who=who, entity_type=entity_type)
    except ValueError as e:
        click.secho(str(e), fg="yellow")
        return

    # Ins Audit-Log schreiben
    log_event("OVERRIDE_ADDED", config, details={
        "term": term,
        "reason": reason,
        "added_by": entry["added_by"],
        "entity_type": entity_type or "",
    })

    click.secho(f"Freigegeben: '{term}'", fg="green")
    click.echo(f"  Begründung: {reason}")
    click.echo(f"  Von: {entry['added_by']}")
    click.echo(f"  Zeitpunkt: {entry['timestamp']}")


@main.command()
@click.argument("term")
def revoke(term: str) -> None:
    """Widerruft eine Freigabe (Override).

    Beispiel: pii-guard revoke "Max Müller"
    """
    from pii_guard.overrides import remove_override
    from pii_guard.audit import log_event

    config = load_config()
    removed = remove_override(term, config)

    if removed:
        log_event("OVERRIDE_REMOVED", config, details={
            "term": term,
            "removed_entry": removed,
        })
        click.secho(f"Freigabe widerrufen: '{term}'", fg="yellow")
        click.echo(f"  War freigegeben von: {removed.get('added_by')}")
        click.echo(f"  Begründung war: {removed.get('reason')}")
    else:
        click.echo(f"Keine Freigabe für '{term}' gefunden.")


@main.command(name="overrides")
def list_overrides_cmd() -> None:
    """Zeigt alle aktiven Freigaben (Overrides)."""
    from pii_guard.overrides import list_overrides

    config = load_config()
    overrides = list_overrides(config)

    if not overrides:
        click.echo("Keine aktiven Freigaben.")
        return

    click.echo(f"{len(overrides)} aktive Freigabe(n):\n")
    for entry in overrides:
        click.echo(f"  Begriff:     {entry.get('term')}")
        click.echo(f"  Begründung:  {entry.get('reason')}")
        click.echo(f"  Freigabe:    {entry.get('added_by')} am {entry.get('timestamp', '?')[:10]}")
        if entry.get("entity_type"):
            click.echo(f"  PII-Typ:     {entry.get('entity_type')}")
        click.echo()


def _find_compose_dir() -> str | None:
    """Sucht docker-compose.yml im aktuellen oder übergeordneten Verzeichnis."""
    current = Path.cwd()
    for _ in range(5):
        if (current / "docker-compose.yml").exists():
            return str(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


@main.group()
def docker() -> None:
    """Docker-Daemon verwalten."""
    pass


@docker.command()
@click.option("--port", default=7437, help="Port für den PII Guard Daemon")
@click.option("--build", "do_build", is_flag=True, help="Docker Image neu bauen")
def start(port: int, do_build: bool) -> None:
    """Startet den PII Guard Docker-Daemon."""
    import subprocess

    if not shutil.which("docker"):
        click.secho("Docker nicht gefunden. Bitte Docker Desktop installieren.", fg="red")
        raise SystemExit(1)

    # Finde docker-compose.yml im Projekt
    compose_dir = _find_compose_dir()
    if not compose_dir:
        click.secho("Keine docker-compose.yml gefunden. Liegt sie im Projekt-Root?", fg="red")
        raise SystemExit(1)

    # Prüfe ob Container bereits läuft
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=pii-guard", "--format", "{{.Status}}"],
        capture_output=True, text=True,
    )
    if result.stdout.strip():
        click.echo(f"PII Guard Container läuft bereits: {result.stdout.strip()}")
        return

    if do_build:
        click.echo("Docker Image wird gebaut...")
        subprocess.run(["docker", "compose", "build"], check=True, cwd=compose_dir)

    click.echo(f"PII Guard Daemon wird gestartet (Port {port})...")
    subprocess.run(["docker", "compose", "up", "-d"], check=True, cwd=compose_dir)

    # Health-Check (max 30s warten)
    import time
    import urllib.request
    import urllib.error

    for i in range(30):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            click.secho(f"PII Guard Daemon läuft auf Port {port}", fg="green")
            click.echo("\nDocker-Modus in .pii-guard.yaml aktivieren:")
            click.echo("  docker:")
            click.echo("    enabled: true")
            return
        except (urllib.error.URLError, OSError):
            time.sleep(1)

    click.secho("Daemon gestartet, aber Health-Check antwortet noch nicht.", fg="yellow")
    click.echo("Prüfe: docker logs pii-guard")


@docker.command()
def stop() -> None:
    """Stoppt den PII Guard Docker-Daemon."""
    import subprocess

    compose_dir = _find_compose_dir()
    subprocess.run(["docker", "compose", "down"], check=True, cwd=compose_dir)
    click.echo("PII Guard Daemon gestoppt.")


@docker.command(name="status")
def docker_status() -> None:
    """Zeigt den Status des Docker-Daemons."""
    import subprocess
    import urllib.request
    import urllib.error

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=pii-guard", "--format", "{{.Status}}"],
        capture_output=True, text=True,
    )

    if not result.stdout.strip():
        click.echo("PII Guard Container läuft nicht.")
        return

    click.echo(f"Container: {result.stdout.strip()}")

    config = load_config()
    port = config.get("docker", {}).get("port", 7437)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
            data = json.loads(resp.read())
            click.secho(f"Health: {data.get('status', 'unknown')} (v{data.get('version', '?')})", fg="green")
    except (urllib.error.URLError, OSError):
        click.secho("Health-Check fehlgeschlagen", fg="red")


_MINIMAL_CONFIG = """\
version: 1
engine:
  languages: ["de", "en"]
  confidence_threshold: 0.7
rules:
  - types: [PASSWORD, API_KEY, CREDIT_CARD, IBAN_CODE]
    action: block
  - types: [PERSON, EMAIL_ADDRESS, PHONE_NUMBER]
    action: auto_mask
  - types: [ORGANIZATION]
    action: warn
allow_list: []
audit:
  enabled: true
  path: .pii-guard/audit.log
mapping:
  enabled: true
  path: .pii-guard/session-map.json
"""

_PRECOMMIT_CONFIG = """\
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks
"""
