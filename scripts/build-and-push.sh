#!/bin/bash
set -e

# PII Guard – Multi-Arch Docker Build + Push nach ACR
#
# WICHTIG: Immer dieses Script verwenden statt "docker build".
# Ohne --platform baut Docker nur für die lokale Architektur
# (z.B. ARM64 auf Mac), was auf Windows/Linux (AMD64) nicht läuft.

IMAGE="piiguard.azurecr.io/pii-guard:latest"

echo "ACR Login..."
az acr login --name piiguard

echo "Multi-Arch Build (AMD64 + ARM64)..."
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t "$IMAGE" \
  --push \
  .

echo "Verifiziere Manifest..."
docker manifest inspect "$IMAGE" | grep -E '"architecture"'

echo "Fertig. Image gepusht: $IMAGE"
