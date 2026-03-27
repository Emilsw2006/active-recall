#!/bin/bash
# Active Recall — Setup inicial para Oracle Cloud VM (Ubuntu 22.04)
# Ejecutar UNA VEZ tras crear la VM: bash setup-server.sh

set -e

echo "=== 1. Crear SWAP (4GB) — vital para servidores con poca RAM ==="
if [ ! -f /swapfile ]; then
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    # Reducir swappiness para que use RAM primero
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    echo "Swap de 4GB creado y activado"
else
    echo "Swap ya existe, saltando"
fi

echo "=== 2. Actualizar sistema ==="
sudo apt-get update && sudo apt-get upgrade -y

echo "=== 3. Instalar Docker ==="
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

echo "=== 4. Instalar Docker Compose ==="
sudo apt-get install -y docker-compose-plugin
echo 'alias docker-compose="docker compose"' >> ~/.bashrc

echo "=== 5. Instalar Git ==="
sudo apt-get install -y git

echo "=== 6. Abrir puertos en el firewall ==="
# En la consola web de Oracle también hay que abrir los puertos
# Networking > VCN > Security Lists > Ingress Rules: TCP 80, 443, 8000
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save || sudo apt-get install -y iptables-persistent

echo "=== 7. Configurar DuckDNS (dominio gratuito) ==="
echo ""
echo "Para configurar DuckDNS:"
echo "  1. Ve a https://www.duckdns.org y logueate"
echo "  2. Crea el subdominio 'activerecallmvp'"
echo "  3. Pon la IP pública de este servidor"
echo "  4. Copia tu token y ejecuta:"
echo "     echo 'url=\"https://www.duckdns.org/update?domains=activerecallmvp&token=TU_TOKEN&ip=\"' | sudo tee /etc/cron.d/duckdns"
echo ""

echo ""
echo "=== Setup completado ==="
echo ""
echo "Próximos pasos:"
echo "1. IMPORTANTE: Cierra sesión y vuelve a entrar (para que Docker funcione sin sudo)"
echo "   exit"
echo "   ssh -i tu-clave.pem ubuntu@IP"
echo ""
echo "2. Clona el repo:"
echo "   git clone https://github.com/TU_USUARIO/active-recall.git"
echo "   cd active-recall"
echo ""
echo "3. Configura credenciales:"
echo "   cp BACKEND/.env.example BACKEND/.env"
echo "   nano BACKEND/.env"
echo ""
echo "4. Arranca:"
echo "   docker compose up -d --build"
echo ""
echo "5. Comprueba:"
echo "   curl http://localhost:8000/health"
echo "   docker compose logs -f backend"
echo ""
echo "6. Para SSL con DuckDNS:"
echo "   docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d activerecallmvp.duckdns.org"
echo "   # Luego edita nginx.conf: descomenta el bloque HTTPS y comenta el proxy del bloque HTTP"
echo "   docker compose restart nginx"
