# START HIER — mkcert Web-UI ohne eigenen Container-Build

> **Wichtigste Änderung:** Statt eines selbst gebauten Images nutzen wir das
> **fertige, gepflegte Image `jeffcaldwellca/mkcertweb`** von Docker Hub.
> Damit entfällt das fehleranfällige eigene Dockerfile komplett.

## Warum lief es vorher nicht?

Die häufigsten zwei Gründe, warum ein selbst gebauter mkcert-Container
„startet und sofort stoppt“:

1. **`mkcert -install` im Container**
   mkcert versucht dabei, das Root-Zertifikat in den **System-Trust-Store des
   Containers** zu schreiben. In einem minimalen Image sind dafür die Tools
   (`trust`, NSS) nicht vorhanden → mkcert bricht ab. Mehrere Entrypoints
   brechen dann ebenfalls ab → Container stirbt.
   **Im Container NICHT `-install` nutzen** — nur `mkcert -CAROOT` die
   CA-Dateien erzeugen lassen. Die CA muss auf den *Clients* importiert werden.

2. **Schreibrechte auf dem Volume**
   mkcert schreibt in das gemountete Verzeichnis. Läuft der Container als
   uid 1000, das Host-Volume gehört aber z. B. `root` → „permission denied“
   beim ersten Zertifikat. → Rechte vergeben: `chown -R 1000:1000 <volume>`

## Option A — Unraid (empfohlen)

1. `templates/mkcertweb-unraid.xml` nach
   `/boot/config/plugins/community.applications/templates/` kopieren.
2. In Unraid unter **Apps** nach **mkcertweb** suchen → installieren.
3. Image kommt automatisch von Docker Hub (kein Build nötig).
4. Zugriff: `http://<UNRAID-IP>:3000`

## Option B — Test-Docker-Host (curl ausführbar)

```bash
mkdir -p ~/mkcertweb/certificates ~/mkcertweb/data
chown -R 1000:1000 ~/mkcertweb

docker run -d --name mkcertweb --restart unless-stopped \
  -p 3000:3000 \
  -e TZ=Europe/Berlin \
  -v ~/mkcertweb/certificates:/app/certificates \
  -v ~/mkcertweb/data:/app/data \
  jeffcaldwellca/mkcertweb:latest

# Log pruefen
docker logs -f mkcertweb
# Zugriff
open http://localhost:3000
```

## Zugangsdaten (Standard)

Login ist standardmäßig **`admin` / `admin`**.
Für Netzwerkzugriff unbedingt `ENABLE_AUTH=true`, eigenes `AUTH_PASSWORD`
und ein langes `SESSION_SECRET` setzen (siehe Unraid-Template-Variablen).

## Nützliche Diagnose-Kommandos

```bash
docker logs mkcertweb            # Container-Log ansehen
docker ps -a                     # Status pruefen
docker exec -it mkcertweb sh     # In Container gehen (falls vorhanden)
```
