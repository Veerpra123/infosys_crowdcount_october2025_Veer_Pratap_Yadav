// static/script.js
// Zone editor that calls server APIs (requires logged-in user token)

function getToken() {
  return localStorage.getItem("access_token");
}

async function loadZonesFromServer() {
  const token = getToken();
  if (!token) { window.location.href = "/login"; return []; }
  const res = await fetch("/api/zones", {
    headers: { "Authorization": "Bearer " + token }
  });
  if (!res.ok) {
    alert("Failed to load zones. Please login again.");
    window.location.href = "/login";
    return [];
  }
  const data = await res.json();
  return data.zones || [];
}

async function saveZoneToServer(zone) {
  const token = getToken();
  const res = await fetch("/api/zones", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
    body: JSON.stringify(zone)
  });
  if (!res.ok) {
    const err = await res.json().catch(()=>({}));
    alert("Save failed: " + (err.detail || JSON.stringify(err)));
    return null;
  }
  return await res.json();
}

async function deleteZoneOnServer(id) {
  const token = getToken();
  const res = await fetch("/api/zones/" + id, {
    method: "DELETE",
    headers: { "Authorization": "Bearer " + token }
  });
  return res.ok;
}

function initZoneEditor() {
  const canvas = document.getElementById("overlay");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const img = document.getElementById("video");

  function resize() {
    canvas.width = img.clientWidth || 640;
    canvas.height = img.clientHeight || 480;
  }
  resize();
  window.addEventListener("resize", resize);

  let drawing = false;
  let currentPoints = [];
  let serverZones = [];

  const startBtn = document.getElementById("start-draw");
  const finishBtn = document.getElementById("finish-draw");
  const clearBtn = document.getElementById("clear-draw");
  const zoneNameInput = document.getElementById("zone-name");
  const zonesListEl = document.getElementById("zones-list");

  startBtn.onclick = () => { drawing = true; currentPoints = []; drawAll(); };
  clearBtn.onclick = () => { currentPoints = []; drawAll(); };

  finishBtn.onclick = async () => {
    drawing = false;
    if (currentPoints.length < 3) { alert("Draw at least 3 points"); return; }
    const name = zoneNameInput.value.trim() || `Zone-${Date.now()}`;
    const zonePayload = { name, points: currentPoints, camera_id: "cam1" };
    const saved = await saveZoneToServer(zonePayload);
    if (saved && saved.status === "ok") {
      alert("Zone saved");
      currentPoints = [];
      await reloadZones();
    }
  };

  canvas.addEventListener("click", (ev) => {
    if (!drawing) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(ev.clientX - rect.left);
    const y = Math.round(ev.clientY - rect.top);
    currentPoints.push([x,y]);
    drawAll();
  });

  async function reloadZones() {
    serverZones = await loadZonesFromServer();
    drawAll();
    renderZonesList();
  }

  function drawAll() {
    ctx.clearRect(0,0,canvas.width, canvas.height);
    serverZones.forEach(z => {
      drawPolygon(z.points, "rgba(255,0,0,0.25)", "#ff0000");
      if (z.points && z.points.length) {
        const [x,y] = z.points[0];
        ctx.fillStyle = "#ff0000";
        ctx.fillText(z.name, x+6, y+6);
      }
    });
    if (currentPoints.length) drawPolygon(currentPoints, "rgba(0,255,0,0.15)", "#00aa00", false);
  }

  function drawPolygon(points, fill, stroke, close=true) {
    if (!points || !points.length) return;
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i=1;i<points.length;i++) ctx.lineTo(points[i][0], points[i][1]);
    if (close) ctx.closePath();
    ctx.fillStyle = fill;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();
  }

  function renderZonesList() {
    zonesListEl.innerHTML = "";
    if (!serverZones.length) { zonesListEl.innerHTML = "<li>No zones</li>"; return; }
    serverZones.forEach(z => {
      const li = document.createElement("li");
      li.className = "zone-item";
      const nameSpan = document.createElement("span");
      nameSpan.textContent = z.name;
      const delBtn = document.createElement("button");
      delBtn.textContent = "Delete";
      delBtn.onclick = async () => {
        if (!confirm("Delete zone?")) return;
        const ok = await deleteZoneOnServer(z.id);
        if (ok) { alert("Deleted"); await reloadZones(); } else alert("Delete failed");
      };
      li.appendChild(nameSpan);
      li.appendChild(delBtn);
      zonesListEl.appendChild(li);
    });
  }

  // initial
  reloadZones();
  setInterval(drawAll, 300);
}

document.addEventListener("DOMContentLoaded", initZoneEditor);
