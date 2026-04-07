#!/bin/bash
set -e

# PII Guard – Multi-Arch Docker Build + Push nach ACR
#
# WICHTIG: Immer dieses Script verwenden statt "docker build".
# Ohne --platform baut Docker nur für die lokale Architektur
# (z.B. ARM64 auf Mac), was auf Windows/Linux (AMD64) nicht läuft.
#
# Version wird automatisch aus pyproject.toml gelesen.
# Beide Tags werden gepusht: latest + vX.Y.Z

REPO="piiguard.azurecr.io/pii-guard"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Version aus pyproject.toml lesen
VERSION=$(grep -m1 '^version' "$PROJECT_DIR/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')

if [ -z "$VERSION" ]; then
  echo "Fehler: Version nicht in pyproject.toml gefunden"
  exit 1
fi

echo "Version: v${VERSION}"
echo "Tags:    ${REPO}:latest + ${REPO}:v${VERSION}"
echo ""

echo "ACR Login..."
az acr login --name piiguard

echo "Multi-Arch Build (AMD64 + ARM64)..."
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t "${REPO}:latest" \
  -t "${REPO}:v${VERSION}" \
  --push \
  "$PROJECT_DIR"

echo ""
echo "Verifiziere Manifest..."
docker manifest inspect "${REPO}:v${VERSION}" | grep -E '"architecture"'

echo ""
echo "Fertig. Images gepusht:"
echo "  ${REPO}:latest"
echo "  ${REPO}:v${VERSION}"
