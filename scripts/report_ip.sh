#!/bin/bash
# Se ejecuta al arrancar la instancia (systemd oneshot). Detecta la IP pública
# actual (gratis, vía instance metadata) y la publica en GitHub como STATUS.md,
# para no depender de una IP elástica (que cobra) mientras la sesión de AWS
# Academy Learner Lab va y viene.
set -e

REPO_DIR="/home/ubuntu/environment/aws_apis"
cd "$REPO_DIR"

TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
FECHA=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > STATUS.md << EOF
# Estado del despliegue EC2 / Cloud9

- **API en vivo:** http://${PUBLIC_IP}:8000
- **Última actualización:** ${FECHA} (UTC)
- **Nota:** la IP pública cambia cada vez que la sesión de AWS Academy Learner
  Lab se reinicia (no usamos IP elástica a propósito, para no generar costo
  mientras la instancia está detenida). Este archivo se actualiza solo, al
  arrancar la instancia, vía un servicio systemd (\`report-ip.service\`).
EOF

git add STATUS.md
if ! git diff --cached --quiet; then
  git commit -m "chore: actualizar IP pública (auto, ${FECHA})"
  git push origin main
fi
