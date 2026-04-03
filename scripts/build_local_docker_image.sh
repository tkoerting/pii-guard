#!/bin/bash

# Build lokales Docker-Image für PII Guard
# Verwendet das Dockerfile aus dem Parent-Verzeichnis

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-pii-guard}"
IMAGE_TAG="${IMAGE_TAG:-local}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Building local Docker image for PII Guard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Image:    $FULL_IMAGE"
echo "Context:  $PROJECT_ROOT"
echo "DockerFile: $PROJECT_ROOT/Dockerfile"
echo ""

# Build durchführen
docker build \
  --tag "$FULL_IMAGE" \
  --file "$PROJECT_ROOT/Dockerfile" \
  "$PROJECT_ROOT"

BUILD_RESULT=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $BUILD_RESULT -eq 0 ]; then
  echo "✓ Build erfolgreich!"
  echo ""
  echo "Image bereit: $FULL_IMAGE"
  echo ""
  echo "Weitere Schritte:"
  echo "  • Mit docker compose starten:"
  echo "    docker compose up -d"
  echo ""
  echo "  • Image-Details anzeigen:"
  echo "    docker inspect $FULL_IMAGE"
  echo ""
else
  echo "✗ Build fehlgeschlagen!"
  exit 1
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0
