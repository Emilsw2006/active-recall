#!/bin/bash
# Active Recall — Deploy / actualización
# Ejecutar desde el servidor: bash deploy.sh

set -e

echo "=== Pulling latest code ==="
git pull origin main

echo "=== Rebuilding and restarting ==="
docker compose up -d --build --no-deps backend

echo "=== Status ==="
docker compose ps

echo ""
echo "Deploy completado. Logs:"
docker compose logs --tail=20 backend
