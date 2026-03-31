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
        # Beispiel-Config aus dem Package kopieren
        example = Path(__file__).parent.parent.parent / ".pii-guard.yaml"
        if example.exists():
            shutil.copy(example, config_path)
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
    click.echo("")
    click.echo("Claude Code Hook registrieren:")
    click.echo('  Füge in ~/.claude/settings.json hinzu:')
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
