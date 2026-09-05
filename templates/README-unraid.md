# mkcert Web-UI — Unraid Application Template

Dieses Template installiert den **mkcert-WebUI**-Container in Unraid
(Community Applications / Apps "Install Custom Template").

## Verwendung

1. Lege die Datei `mkcert-webui.xml` im Template-Ordner ab:
   - **Community Applications:** `/boot/config/plugins/community.applications/templates/`
   - Danach unter **Apps** → "mkcert Web-UI" suchen und installieren.

2. **Pfade** anpassen (Beispiele):
   - `/mnt/cache/appdata/mkcert/certs`  → Container-Pfad `/certs/ca` (CA)
   - `/mnt/cache/appdata/mkcert/certs`  → Container-Pfad `/certs/certs` (Zertifikate)

   > Wichtig: `ca` und `certs` können dasselbe Host-Volume nutzen, wenn du
   > zwei Volume-Zeilen mit unterschiedlichen Container-Pfaden anlegst.

3. Web-UI aufrufen: `http://<UNRAID-IP>:8080`

## Verfügbare Umgebungsvariablen

| Variable | Standard | Beschreibung |
|----------|----------|--------------|
| `PORT` | `8080` | HTTP-Port der Web-UI |
| `MKCERT_CAROOT` | `/certs/ca` | Ablage der Root-CA (`rootCA.pem`, `rootCA-key.pem`) |
| `MKCERT_CERT_DIR` | `/certs/certs` | Ausgestellte Zertifikate |
| `MKCERT_AUTO_INSTALL_CA` | `true` | CA beim Start automatisch anlegen |
| `MKCERT_ALLOWED_HOSTS` | *(leer = alle)* | Kommagetrennte Whitelist erlaubter Domains |

---

## Lizenz / Quelle

Web-UI: Open source (MIT) – siehe README.
