#!/bin/sh
# mkcert-webui Entrypoint
# - Installiert die Root-CA in den CAROOT (falls noch nicht vorhanden)
# - Startet dann die Flask-App

set -e

echo "📁 CAROOT:       ${MKCERT_CAROOT:-/certs/ca}"
echo "📁 CERT_DIR:     ${MKCERT_CERT_DIR:-/certs/certs}"
echo "🌍 PORT:         ${PORT:-8080}"

mkdir -p "${MKCERT_CAROOT:-/certs/ca}" "${MKCERT_CERT_DIR:-/certs/certs}"

# CA automatisch installieren (optional per env deaktivierbar)
if [ "${MKCERT_AUTO_INSTALL_CA:-true}" = "true" ]; then
  echo "🔐 Installiere Root-CA…"
  CAROOT="${MKCERT_CAROOT:-/certs/ca}" mkcert -install || {
    echo "⚠️ CA-Installation fehlgeschlagen (kann im Container normal nicht das System nutzen, Dateien liegen trotzdem bereit)."
  }
fi

echo "🚀 Starte Flask-App auf 0.0.0.0:${PORT:-8080}"
exec python3 /app/app.py
