"use strict";

const $ = (sel) => document.querySelector(sel);

/* ---------- Toast ---------- */
let toastTimer;
function toast(msg, type = "") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = `toast ${type}`;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3500);
}

/* ---------- API helpers ---------- */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw new Error(data.error || `Fehler ${res.status}`);
  return data;
}

/* ---------- CA status ---------- */
async function loadCa() {
  const chip = $("#caChip");
  try {
    const data = await api("/api/ca");
    const ok = data.installed;
    $("#caDot").className = "dot " + (ok ? "ok" : "bad");
    $("#caText").textContent = ok ? "CA installiert" : "CA fehlt";
    $("#caStatusText").textContent = ok ? "Bereit ✓" : "Nicht installiert";
    $("#installCa").textContent = ok ? "CA installiert ✓" : "CA installieren";
    $("#installCa").disabled = ok;
    const dl = $("#downloadCa");
    dl.disabled = !ok || !data.files?.pem;
    dl.title = ok ? "rootCA.pem auf den Client laden" : "Zuerst CA installieren";
  } catch (e) {
    $("#caDot").className = "dot bad";
    $("#caText").textContent = "offline?";
    $("#caStatusText").textContent = "Prüfung fehlgeschlagen";
  }
}

function downloadCa() {
  downloadFile("/api/ca/download", "rootCA.pem");
}

/* Lädt eine Datei per fetch (Blob) herunter — funktioniert auch, wenn der
   Server per Auth geschützt ist, da der fetch-Cookie/Header mitgesendet wird. */
async function downloadFile(url, fallbackName) {
  try {
    const res = await fetch(url);
    if (!res.ok) {
      let msg = `Fehler ${res.status}`;
      try { const j = await res.json(); if (j.error) msg = j.error; } catch (_) {}
      throw new Error(msg);
    }
    const blob = await res.blob();
    // Dateiname aus Content-Disposition ableiten, sonst fallback
    const cd = res.headers.get("Content-Disposition") || "";
    let name = fallbackName;
    const m = cd.match(/filename\*?=([^;]+)/i);
    if (cd && m) name = m[1].replace(/^UTF-8''/i, "").replace(/"/g, "").trim();
    const urlObj = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = urlObj;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(urlObj);
    toast("Download gestartet: " + name, "ok");
  } catch (e) {
    toast("Download fehlgeschlagen: " + e.message, "err");
  }
}

async function installCa() {
  const btn = $("#installCa");
  btn.disabled = true; btn.textContent = "Installiere…";
  try {
    const data = await api("/api/ca/install", { method: "POST" });
    toast(data.message || "CA installiert", "ok");
    loadCa();
  } catch (e) {
    toast(e.message, "err");
    btn.disabled = false; btn.textContent = "CA installieren";
  }
}

/* ---------- Zertifikate ---------- */
async function loadCerts() {
  try {
    const certs = await api("/api/certs");
    if (!Array.isArray(certs) || certs.length === 0) {
      $("#emptyState").hidden = false;
      $("#certTable").hidden = true;
      $("#certCount").textContent = "0 Dateien";
      return;
    }
    $("#emptyState").hidden = true;
    $("#certTable").hidden = false;
    $("#certCount").textContent = certs.length + " Dateien";
    const body = $("#certBody");
    body.innerHTML = "";
    for (const c of certs) {
      const name = c.name.replace(/\.pem$/i, "").replace(/-key$/i, "");
      const tr = document.createElement("tr");

      const tdName = document.createElement("td");
      tdName.className = "mono";
      tdName.textContent = c.name;
      if (c.key && c.cert) tdName.textContent = `${c.name}.pem + key`;

      const tdSize = document.createElement("td");
      const sizeParts = [];
      if (c.cert_file) sizeParts.push(fmtSize(c.cert_size ?? 0));
      if (c.key_file) sizeParts.push(fmtSize(c.key_size ?? 0));
      tdSize.textContent = sizeParts.join(" + ") || "";

      const tdTime = document.createElement("td");
      tdTime.textContent = c.mtime ? new Date(c.mtime).toLocaleString() : "";

      const tdActions = document.createElement("td");
      tdActions.className = "actions-cell";

      if (c.cert) {
        const dlCert = document.createElement("button");
        dlCert.className = "row-btn";
        dlCert.title = "Zertifikat (.pem) herunterladen";
        dlCert.textContent = "⬇";
        dlCert.onclick = () => downloadFile(`/api/certs/${encodeURIComponent(name)}/download`);
        tdActions.appendChild(dlCert);
      }
      if (c.key) {
        const dlKey = document.createElement("button");
        dlKey.className = "row-btn";
        dlKey.title = `Privater Schlüssel (${name}-key.pem) herunterladen`;
        dlKey.textContent = "🔑";
        dlKey.onclick = () => downloadFile(`/api/certs/${encodeURIComponent(name)}/key/download`);
        tdActions.appendChild(dlKey);
      }
      if (c.cert) {
        const editBtn = document.createElement("button");
        editBtn.className = "row-btn";
        editBtn.title = "Zertifikat um Hosts ergänzen";
        editBtn.textContent = "✎ Ergänzen";
        editBtn.onclick = () => openEdit(name);
        tdActions.appendChild(editBtn);
      }
      const delBtn = document.createElement("button");
      delBtn.className = "del";
      delBtn.title = "Zertifikat + Key löschen";
      delBtn.textContent = "🗑";
      delBtn.onclick = () => deleteCert(name);
      tdActions.appendChild(delBtn);

      tr.append(tdName, tdSize, tdTime, tdActions);
      body.appendChild(tr);
    }
  } catch (e) {
    toast(e.message, "err");
  }
}

/* ---------- Zertifikat ergänzen / aktualisieren ---------- */
let editCertName = null;

async function openEdit(name) {
  editCertName = name;
  $("#editTitle").textContent = `Zertifikat ergänzen: ${name}`;
  $("#editAdd").value = "";
  $("#editExisting").value = "Lade Hosts…";
  $("#editModal").hidden = false;
  $("#saveEdit").disabled = false;
  $("#saveEdit").textContent = "Aktualisieren & neu erstellen";
  try {
    const data = await api(`/api/certs/${encodeURIComponent(name)}/hosts`);
    $("#editExisting").value = data.hosts.join("\n");
  } catch (e) {
    $("#editExisting").value = "Fehler: " + e.message;
  }
}

function closeEdit() {
  $("#editModal").hidden = true;
  editCertName = null;
}

async function saveEdit() {
  if (!editCertName) return;
  const add_hosts = $("#editAdd").value
    .split("\n")
    .map((h) => h.trim())
    .filter(Boolean);
  if (!add_hosts.length) { toast("Bitte mindestens einen neuen Host angeben", "err"); return; }

  const btn = $("#saveEdit");
  btn.disabled = true; btn.textContent = "Aktualisiere…";
  try {
    const data = await api(`/api/certs/${encodeURIComponent(editCertName)}/update`, {
      method: "POST",
      body: JSON.stringify({ add_hosts }),
    });
    toast(data.message, "ok");
    closeEdit();
    loadCerts();
  } catch (e) {
    toast(e.message, "err");
    btn.disabled = false; btn.textContent = "Aktualisieren & neu erstellen";
  }
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (m) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}
function fmtSize(b) {
  if (b < 1024) return b + " B";
  if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
  return (b / 1048576).toFixed(1) + " MB";
}

async function createCert(ev) {
  ev.preventDefault();
  const name = $("#certName").value.trim().toLowerCase();
  const hosts = $("#hosts").value
    .split("\n")
    .map((h) => h.trim())
    .filter(Boolean);

  if (!hosts.length) { toast("Mindestens ein Host erforderlich", "err"); return; }

  const btn = ev.target.querySelector("button[type=submit]");
  btn.disabled = true; const orig = btn.textContent; btn.textContent = "Erstelle…";
  try {
    const data = await api("/api/certs/create", {
      method: "POST",
      body: JSON.stringify({ name, hosts }),
    });
    toast(`${data.message} (${data.cert})`, "ok");
    loadCa(); loadCerts();
  } catch (e) {
    toast(e.message, "err");
  } finally {
    btn.disabled = false; btn.textContent = orig;
  }
}

async function deleteCert(name) {
  if (!confirm(`Zertifikat "${name}" wirklich löschen?`)) return;
  try {
    const data = await api(`/api/certs/${encodeURIComponent(name)}`, { method: "DELETE" });
    toast(data.removed.join(", ") + " gelöscht", "ok");
    loadCerts();
  } catch (e) {
    toast(e.message, "err");
  }
}

/* ---------- Init ---------- */
loadCa();
loadCerts();
setInterval(() => { loadCa(); loadCerts(); }, 15000);

// Defensiv: Modal startet IMMER verborgen, auch wenn ein früher Fehler/altes CSS
// das [hidden]-Attribut übersteuert hätte. Öffnet ausschließlich per Klick.
document.addEventListener("DOMContentLoaded", () => {
  const m = document.getElementById("editModal");
  if (m) m.hidden = true;
});
