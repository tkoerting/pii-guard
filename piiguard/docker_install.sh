#!/bin/bash

#  curl und jq installieren, damit die restlichen Skripte funktionieren
sudo apt install -y curl jq

# Docker installieren auf Ubuntu
# Alte Versionen entfernen
sudo apt remove docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc

# Abhängigkeiten & GPG-Key
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Repository hinzufügen
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker installieren
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Aktuellen User zur docker-Gruppe hinzufügen (kein sudo nötig)
sudo usermod -aG docker $USER
newgrp docker

# Test
docker run hello-world