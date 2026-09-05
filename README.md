# 🔐 mkcert Web-UI

A **modern web interface for [mkcert](https://github.com/FiloSottile/mkcert)**.
Create and manage local development certificates (for `localhost`, LAN IPs,
and custom domains) conveniently from your browser — with a ready-to-use Dockerfile & Unraid template.

## Features

* **CA Management** – view status, install **& directly download** the Root CA
* **Create Certificates** – enter a name + hosts/IPs and create a certificate with one click
* **Overview & Deletion** – view all issued files with size & timestamp
* **Modern Dark Design** – responsive, no external frameworks

## Technology

| Layer        | Technology                                |
| ------------ | ----------------------------------------- |
| Backend      | Python 3 + Flask                          |
| Frontend     | Vanilla JS + CSS (no build step)          |
| Certificates | mkcert (static binary)                    |
| Container    | Debian/Python Slim, non-root, healthcheck |

## Directory Structure

```text
mkcert-webui/
├── app.py                # Flask backend (REST API)
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── templates/
│   ├── index.html        # Web interface
│   ├── mkcert-webui.xml  # Unraid template
│   └── README-unraid.md
├── static/
│   ├── style.css
│   └── app.js
└── scripts/
    └── entrypoint.sh     # Container startup (creates CA)
```

## Quick Start (Local, without Docker)

```bash
# Install mkcert (recommended via https://github.com/FiloSottile/mkcert)
pip install -r requirements.txt
MKCERT_CAROOT=/tmp/mkcert-ca MKCERT_CERT_DIR=/tmp/mkcert-certs python3 app.py
# → http://localhost:8080
```

## Docker Build & Start

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

or use `knex666/mkcertwebui:latest`

> **Note about mkcert inside the container:** The Root CA (`rootCA.pem` + `rootCA-key.pem`)
> is stored in the `/certs/ca` volume. For browsers/systems to trust certificates
> issued by this CA, the exact same `rootCA.pem` must be imported into the trust store
> on each client system (`mkcert -install` on the host, or note that system trust
> installation is not possible from inside the container). The files are persistently stored.

## Unraid

1. Place `templates/mkcert-webui.xml` in
   `/boot/config/plugins/community.applications/templates/`
2. In Unraid, go to **Apps** → search for **mkcert-webui** and install it
3. Check the network/path settings → Start → `http://<UNRAID-IP>:8080`

Details: see `templates/README-unraid.md`

## Environment Variables

| Variable                 | Default        | Description                                  |
| ------------------------ | -------------- | -------------------------------------------- |
| `PORT`                   | `8080`         | HTTP port of the Web UI                      |
| `MKCERT_CAROOT`          | `/certs/ca`    | Root CA storage location                     |
| `MKCERT_CERT_DIR`        | `/certs/certs` | Issued certificates                          |
| `MKCERT_AUTO_INSTALL_CA` | `true`         | Automatically create the CA on startup       |
| `MKCERT_ALLOWED_HOSTS`   | *(empty)*      | Comma-separated host whitelist (empty = all) |

## REST API

| Method | Path                   | Purpose                                                                     |
| ------ | ---------------------- | --------------------------------------------------------------------------- |
| GET    | `/api/ca`              | CA status                                                                   |
| POST   | `/api/ca/install`      | Install / create CA                                                         |
| GET    | `/api/ca/download`     | 🔽 Download Root CA (`rootCA.pem`)                                          |
| GET    | `/api/ca/key/download` | Root CA key (`rootCA-key.pem`) — only with `MKCERT_ALLOW_KEY_DOWNLOAD=true` |
| GET    | `/api/certs`           | List certificates                                                           |
| POST   | `/api/certs/create`    | Create certificate `{name, hosts[]}`                                        |
| DELETE | `/api/certs/<name>`    | Delete certificate                                                          |
| GET    | `/health`              | Healthcheck                                                                 |

## License

GPL-3.0 license. mkcert is © Filippo Valsorda (Mozilla), Apache-2.0/MIT.
