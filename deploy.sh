#!/bin/bash
# Active Recall — Deploy / actualización
# Ejecutar desde el servidor: bash deploy.sh

set -e

echo "=== Preparando deploy ==="
OLD_HEAD="$(git rev-parse HEAD)"

echo "=== Pulling latest code ==="
git pull --ff-only origin main

NEW_HEAD="$(git rev-parse HEAD)"

if [ "$OLD_HEAD" = "$NEW_HEAD" ]; then
  echo "No hay cambios nuevos. Nada que desplegar."
  exit 0
fi

echo "=== Cambios detectados ==="
CHANGED_FILES="$(git diff --name-only "$OLD_HEAD" "$NEW_HEAD")"
echo "$CHANGED_FILES"
echo ""

echo "=== Rebuilding and restarting backend ==="
docker compose up -d --build --no-deps backend

# Si cambia la configuración de infraestructura/web, refresca nginx también.
if echo "$CHANGED_FILES" | grep -Eq "^(nginx\.conf|docker-compose\.yml|docker-compose\.yaml|Dockerfile)"; then
  echo "=== Infra/web config changed: restarting nginx ==="
  docker compose up -d --no-deps nginx
fi

echo "=== Status ==="
docker compose ps

echo ""
echo "Deploy completado. Logs:"
docker compose logs --tail=20 backend
