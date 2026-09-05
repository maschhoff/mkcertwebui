#!/usr/bin/env python3
"""
mkcert Web-UI — Flask-Backend
Verwaltet lokale Entwicklungs-Zertifikate über mkcert.
"""
import os
import re
import shutil
import subprocess
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)

# ---- Konfiguration über Umgebungsvariablen ----
DATA_DIR = os.getenv("MKCERT_DATA_DIR", "/certs")
CAROOT = os.getenv("MKCERT_CAROOT", "/certs/ca")
CERT_DIR = os.getenv("MKCERT_CERT_DIR", "/certs/certs")
HOSTS_ALLOWED_RAW = os.getenv("MKCERT_ALLOWED_HOSTS", "")
HOSTS_ALLOWED = [h.strip() for h in HOSTS_ALLOWED_RAW.split(",") if h.strip()]
# Leere/ungesetzte Whitelist = ALLE Hosts erlaubt. Nur wenn tatsächlich Einträge
# existieren, wird gefiltert.
HOSTS_ALLOWED = HOSTS_ALLOWED or None

MKCERT_BIN = os.environ.get("MKCERT_BIN", "mkcert")

# Host-Namen ohne Eingabe validieren
SAFE_HOST = re.compile(r"^[a-zA-Z0-9*.-]+$")
IP_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$|^\[?[0-9a-fA-F:]+\]?$")


def _allowed(host: str) -> bool:
    """Prüft, ob ein Host erlaubt ist. Keine Whitelist (=None) => alles erlaubt."""
    if HOSTS_ALLOWED is None:
        return True
    return host in HOSTS_ALLOWED or bool(SAFE_HOST.match(host)) and host in HOSTS_ALLOWED


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Führt mkcert mit den nötigen Umgebungsvariablen aus."""
    env = os.environ.copy()
    env["CAROOT"] = CAROOT
    os.makedirs(CAROOT, exist_ok=True)
    os.makedirs(CERT_DIR, exist_ok=True)
    return subprocess.run(
        [MKCERT_BIN, *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=CERT_DIR,
    )


def _cert_path(name: str) -> str:
    """Pfad zum Zertifikat (pem) für einen Zertifikatsnamen."""
    return os.path.join(CERT_DIR, f"{name}.pem")


def _normalize_ipv6(host: str) -> str:
    """Verkürzt eine volle IPv6-Adresse (0:0:...:1 -> ::1) für Vergleich/Zusammenführen."""
    host = host.strip()
    if ":" in host and host.startswith("0:"):
        try:
            import ipaddress
            return ipaddress.IPv6Address(host).compressed
        except ValueError:
            pass
    return host


def _read_cert_hosts(name: str):
    """Liest die in einem Zertifikat enthaltenen Hosts/IPs (SubjectAltName) per openssl.
    Gibt (ok, hosts|error) zurück."""
    path = _cert_path(name)
    if not os.path.isfile(path):
        return False, f"Zertifikat {name}.pem nicht gefunden."
    try:
        raw = subprocess.run(
            ["openssl", "x509", "-in", path, "-noout", "-ext", "subjectAltName"],
            capture_output=True, text=True, timeout=15,
        )
        if raw.returncode != 0:
            return False, f"SAN nicht lesbar: {raw.stderr.strip() or 'unbekannter Fehler'}"
    except FileNotFoundError:
        return False, "openssl ist nicht installiert."

    hosts: list[str] = []
    for line in raw.stdout.splitlines():
        if "DNS:" not in line and "IP Address:" not in line:
            continue
        # Zeile: "    DNS:localhost, DNS:x, IP Address:1.2.3.4"
        for part in line.split(","):
            part = part.strip()
            if part.startswith("DNS:"):
                hosts.append(part[4:].strip())
            elif part.startswith("IP Address:"):
                hosts.append(_normalize_ipv6(part[11:].strip()))
    # dedupe, sortiere (localhost/127.0.0.1/::1 zuerst für Übersichtlichkeit)
    seen, ordered = set(), []
    for h in hosts:
        if h and h not in seen:
            seen.add(h)
            ordered.append(h)
    ordered.sort(key=lambda h: (h not in {"localhost", "127.0.0.1", "::1"}, h))
    return True, ordered


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/ca")
def ca_status():
    root = os.path.join(CAROOT, "rootCA.pem")
    key = os.path.join(CAROOT, "rootCA-key.pem")
    installed = os.path.exists(root)
    return jsonify({
        "installed": installed,
        "rootCA": root,
        "files": {
            "pem": os.path.exists(root),
            "key": os.path.exists(key),
        },
    })


@app.get("/api/ca/download")
def ca_download():
    """Stellt die Root-CA (rootCA.pem) zum Herunterladen bereit."""
    root = os.path.join(CAROOT, "rootCA.pem")
    if not os.path.isfile(root):
        return jsonify({
            "ok": False,
            "error": "Root-CA noch nicht vorhanden. Bitte zuerst 'CA installieren'."
        }), 404
    return send_file(
        root,
        as_attachment=True,
        download_name="rootCA.pem",
        mimetype="application/x-pem-file",
    )


@app.get("/api/ca/key/download")
def ca_key_download():
    """Stellt den Root-CA-Private-Key herunter (nur falls explizit aktiviert)."""
    if os.getenv("MKCERT_ALLOW_KEY_DOWNLOAD", "false").lower() != "true":
        return jsonify({"ok": False,
                        "error": "Key-Download ist deaktiviert. MKCERT_ALLOW_KEY_DOWNLOAD=true setzen."}), 403
    key = os.path.join(CAROOT, "rootCA-key.pem")
    if not os.path.isfile(key):
        return jsonify({"ok": False, "error": "Root-CA-Key nicht vorhanden."}), 404
    return send_file(
        key,
        as_attachment=True,
        download_name="rootCA-key.pem",
        mimetype="application/x-pem-file",
    )


@app.get("/api/certs")
def list_certs():
    """Listet Zertifikate als logische Paare (Zertifikat + optional zugehoeriger Key).
    Jeder Eintrag ist EIN ausgestelltes Zertifikat (name.pem) mit passendem
    privaten Schluessel (name-key.pem), falls vorhanden."""
    if not os.path.isdir(CERT_DIR):
        return jsonify([])

    # Kandidaten für Zertifikatsnamen: der Teil von Dateinamen ohne Bekannte Suffixe
    files = sorted(os.listdir(CERT_DIR))
    # Erst die 'echten' Zert-Paare erkennen: *.pem, deren Name NICHT auf -key endet,
    # plus evtl. .crt-Varianten. Keys (??-key.pem / ??-key.key) werden den Zerts zugeordnet.
    names: dict[str, dict] = {}

    def ensure(name: str) -> dict:
        if name not in names:
            names[name] = {
                "name": name,
                "cert": False,
                "key": False,
                "cert_size": 0,
                "key_size": 0,
                "mtime": None,
            }
        return names[name]

    for f in files:
        low = f.lower()
        if not low.endswith((".pem", ".crt", ".key")):
            continue
        base = f[: -len(".pem") if low.endswith(".pem") else (
            -len(".crt") if low.endswith(".crt") else -len(".key"))]
        is_key = low.endswith("-key.pem") or low.endswith("-key.crt") or low.endswith("-key.key")
        name = base[:-4] if low.endswith(("-key.pem", "-key.crt", "-key.key")) else base

        key_field = "key" if is_key else "cert"
        entry = ensure(name)
        size_field = "cert_size" if not is_key else "key_size"
        entry[key_field] = True
        entry[size_field] = os.path.getsize(os.path.join(CERT_DIR, f)) or 0
        st = os.stat(os.path.join(CERT_DIR, f))
        mt = datetime.fromtimestamp(st.st_mtime).isoformat()
        if entry["mtime"] is None or mt > entry["mtime"]:
            entry["mtime"] = mt

    result = []
    for name in sorted(names):
        e = names[name]
        total = e["cert_size"] + e["key_size"]
        result.append({
            "name": name,
            "cert": e["cert"],
            "key": e["key"],
            "cert_file": f"{name}.pem" if e["cert"] else None,
            "key_file": f"{name}-key.pem" if e["key"] else None,
            "size": total,
            "mtime": e["mtime"],
        })
    return jsonify(result)


@app.get("/api/certs/<name>/download")
def cert_download(name: str):
    """Stellt das Zertifikat (name.pem) zum Herunterladen bereit."""
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", name):
        return jsonify({"ok": False, "error": "Ungültiger Name."}), 400
    path = _cert_path(name)
    if not os.path.isfile(path):
        return jsonify({"ok": False, "error": f"Zertifikat {name}.pem nicht gefunden."}), 404
    return send_file(
        path,
        as_attachment=True,
        download_name=f"{name}.pem",
        mimetype="application/x-pem-file",
    )


@app.get("/api/certs/<name>/key/download")
def cert_key_download(name: str):
    """Stellt den privaten Schluessel (name-key.pem) eines Zertifikats zum
    Herunterladen bereit. Privater Schlüssel — nur gezielt & bei Bedarf nutzen."""
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", name):
        return jsonify({"ok": False, "error": "Ungültiger Name."}), 400
    key = os.path.join(CERT_DIR, f"{name}-key.pem")
    if not os.path.isfile(key):
        return jsonify({"ok": False, "error": f"Key {name}-key.pem nicht gefunden."}), 404
    return send_file(
        key,
        as_attachment=True,
        download_name=f"{name}-key.pem",
        mimetype="application/x-pem-file",
    )


@app.post("/api/ca/install")
def ca_install():
    if ca_status().json.get("installed"):
        return jsonify({"ok": True, "message": "CA bereits vorhanden."}), 200
    res = _run(["-install"])
    if res.returncode != 0:
        return jsonify({"ok": False, "error": res.stderr or res.stdout}), 500
    # rootCA wird in CAROOT erzeugt
    return jsonify({"ok": True, "message": "CA installiert.", "output": res.stdout}), 200


@app.post("/api/certs/create")
def create_cert():
    data = request.get_json(silent=True) or {}
    cert_name = (data.get("name") or "").strip().lower()
    hosts = data.get("hosts") or []

    # Validierung
    if not cert_name:
        return jsonify({"ok": False, "error": "Zertifikatsname fehlt."}), 400
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", cert_name):
        return jsonify({"ok": False, "error": "Ungültiger Zertifikatsname."}), 400
    if not hosts:
        return jsonify({"ok": False, "error": "Mindestens ein Host erforderlich."}), 400

    for h in hosts:
        if not _allowed(h):
            return jsonify({"ok": False, "error": f"Host nicht erlaubt: {h}"}), 400

    # Standard localhost-Hosts ergänzen, wenn nur IPs/Hosts übergeben wurden
    arg_hosts = [h for h in hosts if h]
    res = _run(["-cert-file", f"{cert_name}.pem",
                "-key-file", f"{cert_name}-key.pem", *arg_hosts])
    if res.returncode != 0:
        return jsonify({"ok": False, "error": res.stderr or res.stdout}), 500
    return jsonify({
        "ok": True,
        "message": f"Zertifikat {cert_name} erstellt.",
        "cert": f"{cert_name}.pem",
        "key": f"{cert_name}-key.pem",
        "output": res.stdout,
    }), 201


@app.delete("/api/certs/<name>")
def delete_cert(name):
    if not re.match(r"^[a-z0-9._-]+$", name):
        return jsonify({"ok": False, "error": "Ungültiger Name."}), 400
    removed = []
    for suffix in ("", "-key"):
        path = os.path.join(CERT_DIR, f"{name}{suffix}.pem")
        cert_path_variants = [path]
        # auch .crt Varianten beruecksichtigen
        if suffix == "":
            cert_path_variants.append(os.path.join(CERT_DIR, f"{name}.crt"))
        for p in cert_path_variants:
            if os.path.isfile(p):
                os.remove(p)
                removed.append(os.path.basename(p))
    if not removed:
        return jsonify({"ok": False, "error": "Zertifikat nicht gefunden."}), 404
    return jsonify({"ok": True, "removed": removed})


@app.get("/api/certs/<name>/hosts")
def get_cert_hosts(name: str):
    """Liest die im Zertifikat enthaltenen Hosts/IPs (SubjectAltName) aus."""
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", name):
        return jsonify({"ok": False, "error": "Ungültiger Zertifikatsname."}), 400
    ok, result = _read_cert_hosts(name)
    if not ok:
        return jsonify({"ok": False, "error": result}), 404
    return jsonify({"ok": True, "name": name, "hosts": result})


@app.post("/api/certs/<name>/update")
def update_cert(name: str):
    """Ergänzt ein bestehendes Zertifikat um neue Hosts und erstellt es neu.
    Liest die vorhandenen Hosts aus dem SAN, vereint sie mit den neuen
    und ruft mkcert erneut auf (überschreibt cert & key in-place)."""
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", name):
        return jsonify({"ok": False, "error": "Ungültiger Zertifikatsname."}), 400

    data = request.get_json(silent=True) or {}
    add_hosts = data.get("add_hosts") or []
    if not add_hosts:
        return jsonify({"ok": False,
                        "error": "Keine neuen Hosts angegeben."}), 400

    # 1) Hosts aus dem bestehenden Zertifikat lesen
    ok, existing = _read_cert_hosts(name)
    if not ok:
        return jsonify({"ok": False, "error": existing}), 404

    # 2) Neue Hosts validieren
    add_norm = []
    for h in add_hosts:
        h = (h or "").strip()
        if not h:
            continue
        if not _allowed(h):
            return jsonify({"ok": False, "error": f"Host nicht erlaubt: {h}"}), 400
        add_norm.append(_normalize_ipv6(h))
    if not add_norm:
        return jsonify({"ok": False, "error": "Keine gültigen neuen Hosts."}), 400

    # 3) Vereinigen (ohne Duplikate)
    merged = list(dict.fromkeys(existing + add_norm))
    if len(merged) == len(existing):
        return jsonify({"ok": False,
                        "error": "Die neuen Hosts sind bereits alle im Zertifikat enthalten."}), 400

    # 4) mkcert neu aufrufen -> überschreibt cert & key
    res = _run(["-cert-file", f"{name}.pem",
                "-key-file", f"{name}-key.pem", *merged])
    if res.returncode != 0:
        return jsonify({"ok": False, "error": res.stderr or res.stdout}), 500

    return jsonify({
        "ok": True,
        "name": name,
        "message": f"Zertifikat {name} um {len(add_norm)} Host(s) ergänzt und neu erstellt.",
        "hosts": merged,
        "added": [h for h in add_norm if h not in existing],
        "output": res.stdout,
    }), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
