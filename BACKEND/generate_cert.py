"""
Genera un certificado SSL autofirmado para desarrollo local.
Incluye la IP de red local para que funcione desde el móvil.
Requiere: pip install cryptography
"""

import ipaddress
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate():
    local_ip = get_local_ip()
    print(f"IP local detectada: {local_ip}")

    # Generar clave privada
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Certificado
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, local_ip),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Active Recall Dev"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                x509.IPAddress(ipaddress.IPv4Address(local_ip)),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    base = Path(__file__).parent
    cert_path = base / "cert.pem"
    key_path  = base / "key.pem"

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )

    print(f"✓ Certificado generado: {cert_path}")
    print(f"✓ Clave privada:        {key_path}")
    print(f"\nAccede desde el móvil en: https://{local_ip}:8443/app")
    print("(El navegador mostrará advertencia de seguridad — pulsa 'Avanzado > Continuar')")


if __name__ == "__main__":
    generate()
