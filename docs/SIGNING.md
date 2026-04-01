# Git Commit Signing

PII Guard verwendet SSH-signierte Commits. Jeder Commit wird kryptographisch signiert, damit die Urheberschaft nachweisbar ist.

Auf GitHub werden signierte Commits mit einem grünen "Verified"-Badge angezeigt.

## Warum

- Kryptographischer Nachweis wer einen Commit autorisiert hat
- Nicht fälschbar (ohne den privaten Schlüssel)
- Besonders relevant für ein Sicherheits-Tool wie PII Guard

## Einrichtung (einmalig)

### 1. SSH-Key prüfen

```bash
ls ~/.ssh/id_ed25519.pub
```

Falls kein Key existiert:
```bash
ssh-keygen -t ed25519 -C "deine@email.com"
```

### 2. Key bei GitHub hinterlegen

1. Öffne https://github.com/settings/keys
2. "New SSH key"
3. **Key type: Signing Key** (nicht Authentication!)
4. Public Key einfügen: `cat ~/.ssh/id_ed25519.pub`
5. Titel: "Vorname Nachname – Commit Signing"

### 3. Git konfigurieren

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
```

### 4. Lokale Verifikation (optional)

```bash
mkdir -p ~/.config/git
echo "deine@email.com $(cat ~/.ssh/id_ed25519.pub)" > ~/.config/git/allowed_signers
git config --global gpg.ssh.allowedSignersFile ~/.config/git/allowed_signers
```

Danach kannst du Signaturen lokal prüfen:
```bash
git log --show-signature -1
```

## Prüfen ob es funktioniert

```bash
# Signatur des letzten Commits anzeigen
git log --show-signature -1

# Erwartete Ausgabe:
# Good "git" signature for deine@email.com with ED25519 key SHA256:...
```

Auf GitHub: Commit hat ein grünes "Verified"-Badge.

## Sicherheit

- Der **private Schlüssel** (`~/.ssh/id_ed25519`) darf den Rechner nie verlassen
- Nicht in Repos, .env-Dateien, Cloud-Storage oder Chats teilen
- Passphrase setzen: `ssh-keygen -p -f ~/.ssh/id_ed25519`
- Backup: Nur verschlüsselt (z.B. Passwort-Manager, verschlüsselter USB-Stick)
