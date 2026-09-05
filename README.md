# 🔐 mkcert Web-UI

Eine **moderne Weboberfläche für [mkcert](https://github.com/FiloSottile/mkcert)**.
Erstelle und verwalte lokale Entwicklungs-Zertifikate (für `localhost`, LAN-IPs
und eigene Domains) bequem im Browser — plus fertiges Dockerfile & Unraid-Template.

## Screenshot-Funktionen

- **CA-Verwaltung** – Status anzeigen, Root-CA installieren **& direkt herunterladen**
- **Zertifikate erstellen** – Name + Hosts/IPs, ein Zertifikat pro Klick
- **Übersicht & Löschen** – alle ausgestellten Dateien mit Größe & Zeit
- **Modernes Dark Design** – responsiv, keine externen Frameworks

## Technik

| Schicht | Technologie |
|--------|-------------|
| Backend | Python 3 + Flask |
| Frontend | Vanilla JS + CSS (kein Build-Schritt) |
| Zertifikate | mkcert (statisches Binary) |
| Container | Debian-/Python-Slim, nicht-root, Healthcheck |

## Verzeichnisstruktur

```
mkcert-webui/
├── app.py                # Flask-Backend (REST-API)
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── templates/
│   ├── index.html        # Web-Oberfläche
│   ├── mkcert-webui.xml  # Unraid-Template
│   └── README-unraid.md
├── static/
│   ├── style.css
│   └── app.js
└── scripts/
    └── entrypoint.sh     # Container-Start (legt CA an)
```

## Schnellstart (lokal, ohne Docker)

```bash
# mkcert installieren (empfohlen via https://github.com/FiloSottile/mkcert)
pip install -r requirements.txt
MKCERT_CAROOT=/tmp/mkcert-ca MKCERT_CERT_DIR=/tmp/mkcert-certs python3 app.py
# → http://localhost:8080
```

## Docker-Build & Start

```bash
cd mkcert-webui
docker build -t mkcert-webui .

docker run -d --name mkcert-webui \
  -p 8080:8080 \
  -v mkcert-ca:/certs/ca \
  -v mkcert-certs:/certs/certs \
  mkcert-webui
# → http://localhost:8080
```

or use knex666/mkcertwebui:latest 

> **Hinweis zu mkcert im Container:** Die Root-CA (`rootCA.pem` + `rootCA-key.pem`)
> werden im Volume `/certs/ca` abgelegt. Damit Browser/Systeme diesen Zertifikaten
> vertrauen, muss genau diese `rootCA.pem` auf den jeweiligen Client-Systemen in
> den Trust-Store importiert werden (`mkcert -install` auf dem Host, oder im
> Container kein System-Trust möglich). Die Dateien sind dauerhaft gesichert.

## Unraid

1. `templates/mkcert-webui.xml` in
   `/boot/config/plugins/community.applications/templates/` legen
2. In Unraid unter **Apps** → **mkcert-webui** suchen & installieren
3. Netzwerk-/Pfadangaben prüfen → Starten → `http://<UNRAID-IP>:8080`

Details: siehe `templates/README-unraid.md`

## Umgebungsvariablen

| Variable | Standard | Beschreibung |
|----------|----------|--------------|
| `PORT` | `8080` | HTTP-Port der Web-UI |
| `MKCERT_CAROOT` | `/certs/ca` | Ablage der Root-CA |
| `MKCERT_CERT_DIR` | `/certs/certs` | Ausgestellte Zertifikate |
| `MKCERT_AUTO_INSTALL_CA` | `true` | CA beim Start automatisch anlegen |
| `MKCERT_ALLOWED_HOSTS` | *(leer)* | Komma-getrennte Host-Whitelist (leer = alle) |

## REST-API

| Methode | Pfad | Zweck |
|---------|------|-------|
| GET | `/api/ca` | CA-Status |
| POST | `/api/ca/install` | CA installieren / anlegen |
| GET | `/api/ca/download` | 🔽 Root-CA (`rootCA.pem`) herunterladen |
| GET | `/api/ca/key/download` | Root-CA-Key (`rootCA-key.pem`) — nur mit `MKCERT_ALLOW_KEY_DOWNLOAD=true` |
| GET | `/api/certs` | Zertifikate auflisten |
| POST | `/api/certs/create` | Zertifikat erstellen `{name, hosts[]}` |
| DELETE | `/api/certs/<name>` | Zertifikat löschen |
| GET | `/health` | Healthcheck |

## Lizenz

MIT. mkcert ist © Filippo Valsorda (Mozilla), Apache-2.0/MIT.
