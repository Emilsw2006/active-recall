#!/bin/bash
# Active Recall — Setup inicial para Oracle Cloud VM (Ubuntu 22.04 ARM)
# Ejecutar UNA VEZ tras crear la VM: bash setup-server.sh

set -e

echo "=== 1. Actualizar sistema ==="
sudo apt-get update && sudo apt-get upgrade -y

echo "=== 2. Instalar Docker ==="
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

echo "=== 3. Instalar Docker Compose ==="
sudo apt-get install -y docker-compose-plugin
# Alias para compatibilidad con docker-compose (sin guion)
echo 'alias docker-compose="docker compose"' >> ~/.bashrc

echo "=== 4. Instalar Git ==="
sudo apt-get install -y git

echo "=== 5. Abrir puertos en el firewall de Oracle ==="
# En la consola web de Oracle también hay que abrir los puertos 80 y 443
# Networking > VCN > Security Lists > Ingress Rules: añadir TCP 80 y 443
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save || sudo apt-get install -y iptables-persistent

echo ""
echo "=== Setup completado ==="
echo ""
echo "Próximos pasos:"
echo "1. Cierra sesión y vuelve a entrar para que Docker funcione sin sudo"
echo "2. Clona el repo: git clone https://github.com/TU_USUARIO/active-recall.git"
echo "3. cd active-recall && cp BACKEND/.env.example BACKEND/.env"
echo "4. Edita BACKEND/.env con tus credenciales: nano BACKEND/.env"
echo "5. Edita nginx.conf con tu dominio (o usa la IP pública por ahora)"
echo "6. docker compose up -d --build"
echo "7. Comprueba: curl http://localhost:8000/health"
echo ""
echo "Para SSL con dominio propio:"
echo "  docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d TU_DOMINIO.COM"
echo "  docker compose restart nginx"
