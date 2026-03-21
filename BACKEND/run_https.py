"""
Arranca el servidor con HTTPS (necesario para micrófono en móvil).
Uso: python run_https.py

Si no tienes cert.pem / key.pem, ejecuta primero: python generate_cert.py
"""

import socket
from pathlib import Path
import uvicorn

BASE = Path(__file__).parent
CERT = BASE / "cert.pem"
KEY  = BASE / "key.pem"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


if __name__ == "__main__":
    if not CERT.exists() or not KEY.exists():
        print("ERROR: Faltan cert.pem / key.pem")
        print("Ejecuta primero:  python generate_cert.py")
        exit(1)

    ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"  Active Recall — HTTPS (micrófono habilitado)")
    print(f"  Frontend móvil: https://{ip}:8443/app")
    print(f"  API:            https://{ip}:8443")
    print(f"{'='*50}\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8443,
        ssl_certfile=str(CERT),
        ssl_keyfile=str(KEY),
        reload=True,
    )
