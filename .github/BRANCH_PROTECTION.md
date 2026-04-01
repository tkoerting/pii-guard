# Branch Protection – nach Transfer einrichten

Diese Regeln auf GitHub unter Settings > Branches > Branch protection rules
fuer den Branch `main` setzen:

## Pflicht-Einstellungen

- [x] Require a pull request before merging
  - [x] Require approvals: 1
- [x] Require status checks to pass before merging
  - [x] Require branches to be up to date before merging
  - Status Check: `test` (aus der CI GitHub Action)
- [x] Do not allow bypassing the above settings

## Empfohlene Einstellungen

- [x] Automatically delete head branches (Feature-Branches nach Merge aufräumen)
- [ ] Require signed commits (optional, wenn SSH-Signing eingerichtet)

## Workflow

```
1. git checkout -b feature/mein-feature
2. Arbeiten, committen
3. git push -u origin feature/mein-feature
4. gh pr create (oder auf GitHub)
5. Review durch Kollegen
6. CI gruen → Squash and Merge
7. Feature-Branch wird automatisch gelöscht
```
