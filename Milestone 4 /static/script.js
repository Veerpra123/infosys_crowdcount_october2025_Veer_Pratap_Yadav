// ---------- tiny toast helper ----------
function showToast(message = "", duration = 1200) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    Object.assign(container.style, {
      position: "fixed",
      left: "50%",
      top: "24px",
      transform: "translateX(-50%)",
      zIndex: 9999,
    });
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.textContent = message;
  Object.assign(toast.style, {
    background: "#1e2a5a",
    color: "white",
    padding: "10px 14px",
    marginTop: "8px",
    border: "1px solid #2f3a66",
    borderRadius: "10px",
    boxShadow: "0 8px 24px rgba(0,0,0,.35)",
    fontWeight: 600,
    minWidth: "240px",
    textAlign: "center",
  });

  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
    if (container.childElementCount === 0) container.remove();
  }, duration);
}

// ---------- helper to POST JSON with cookies ----------
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body || {})
  });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  return { ok: res.ok, status: res.status, data };
}

// ---------- helper to GET JSON with cookies ----------
async function getJSON(url) {
  const res = await fetch(url, { credentials: "include" });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  return { ok: res.ok, status: res.status, data };
}

// ---------- helper to PUT/DELETE JSON with cookies ----------
async function sendJSON(url, method, body) {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined
  });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  return { ok: res.ok, status: res.status, data };
}

document.addEventListener("DOMContentLoaded", () => {

  // ---------- REGISTER FLOW ----------
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("register-msg");

      const payload = {
        name: document.getElementById("reg-username")?.value || "",
        email: document.getElementById("reg-email")?.value || "",
        password: document.getElementById("reg-password")?.value || "",
      };

      const { ok, data } = await postJSON("/api/register", payload);

      if (ok) {
        msg.textContent = "Registered successfully. Please log in.";
        showToast("Registered successfully. Please log in.");
        setTimeout(() => (window.location.href = "/login"), 1000);
      } else {
        msg.textContent = data.message || "Registration failed.";
      }
    });
  }

  // ---------- LOGIN FLOW ----------
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("login-msg");

      const payload = {
        email: document.getElementById("login-email")?.value || "",
        password: document.getElementById("login-password")?.value || "",
      };

      const { ok, data } = await postJSON("/api/login", payload);

      if (ok) {
        msg.textContent = "Login successful.";
        showToast("Login successful");
        setTimeout(() => (window.location.href = "/admin/dashboard"), 900);
      } else {
        msg.textContent = data.message || "Invalid credentials.";
      }
    });
  }

  // ---------- LOGOUT ----------
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      await postJSON("/api/logout");
      showToast("Logged out");
      setTimeout(() => (window.location.href = "/login"), 700);
    });
  }

  // ============================================================
  //                    DASHBOARD ZONE LOGIC
  // ============================================================
  const img = document.getElementById("feed");
  const canvas = document.getElementById("zoneCanvas");
  const ctx = canvas ? canvas.getContext("2d") : null;

  const zoneNameInput = document.getElementById("zoneName");
  const btnStart = document.getElementById("btnStart");
  const btnSave  = document.getElementById("btnSave");
  const btnCancel= document.getElementById("btnCancel");
  const zoneList = document.getElementById("zoneList");

  const drawLineBtn = document.getElementById("drawLineBtn");
  const drawPolyBtn = document.getElementById("drawPolyBtn");
  const editBtn     = document.getElementById("editBtn");
  const liveStats   = document.getElementById("liveStats");

  // Charts & alerts elements
  const lineEl = document.getElementById("lineChart");
  const barEl = document.getElementById("barChart");
  const heatmapEl = document.getElementById("heatmapCanvas");
  const alertBanner = document.getElementById("alertBanner");
  const alertThresholdEl = document.getElementById("alertThreshold");
  const toggleAlertsBtn = document.getElementById("toggleAlerts");
  const exportCSVBtn = document.getElementById("btnExportCSV");
  const exportPDFBtn = document.getElementById("btnExportPDF");
  const exportWindowSel = document.getElementById("exportWindow");

  let alertsEnabled = false;

  toggleAlertsBtn?.addEventListener("click", async () => {
    alertsEnabled = !alertsEnabled;
    toggleAlertsBtn.textContent = alertsEnabled ? "Disable Alerts" : "Enable Alerts";
    showToast(alertsEnabled ? "Alerts enabled" : "Alerts disabled");
    if (!alertsEnabled && alertBanner) alertBanner.classList.add("hidden");
    // persist enabled flag is optional; we persist only threshold for now
  });

  // ======= Persisted Alert Threshold (load on start, save on change) =======
  async function loadSettings(){
    const { ok, data } = await getJSON("/api/settings");
    if (ok && data && typeof data.alert_threshold === "number") {
      alertThresholdEl.value = data.alert_threshold;
    }
  }
  alertThresholdEl?.addEventListener("change", async ()=>{
    const thr = Number(alertThresholdEl.value || 0) || 0;
    await postJSON("/api/settings", { alert_threshold: thr });
    showToast("Threshold saved");
  });

  // =========== ZONE UI ===========
  if (img && canvas && ctx && zoneList) {
    let drawing = false;
    let toolMode = "none";   // "none" | "line" | "poly" | "edit"
    let pointsDisplay = [];
    let zones = [];
    let imgNaturalWidth = 0;
    let imgNaturalHeight = 0;
    let restoreDefaultSave = null;

    // NEW: live per-zone counts (from /api/live)
    let liveZoneCounts = {};   // { zoneName: number }

    function resizeCanvas() {
      canvas.width = img.clientWidth;
      canvas.height = img.clientHeight;
      redraw();
    }

    function scaleToDisplay(p) {
      return {
        x: p.x * (canvas.width / imgNaturalWidth),
        y: p.y * (canvas.height / imgNaturalHeight),
      };
    }
    function scaleToOriginal(p) {
      return {
        x: Math.round(p.x * (imgNaturalWidth / canvas.width)),
        y: Math.round(p.y * (imgNaturalHeight / canvas.height)),
      };
    }

    // ---------- REPLACED: drawPoly now supports label ----------
    function drawPoly(poly, color="rgba(0,150,255,0.35)", labelText=null) {
      if (poly.length < 2) return;

      if (poly.length === 2) {
        // line zone
        ctx.lineWidth = 3;
        ctx.strokeStyle = color === "auto-line" ? "rgba(255,215,0,.95)" : color;
        ctx.beginPath();
        ctx.moveTo(poly[0].x, poly[0].y);
        ctx.lineTo(poly[1].x, poly[1].y);
        ctx.stroke();

        // label near the line
        if (labelText != null) {
          const lx = Math.min(poly[0].x, poly[1].x) + 6;
          const ly = Math.min(poly[0].y, poly[1].y) - 6;
          ctx.font = "12px system-ui, -apple-system, Segoe UI, Roboto, Arial";
          ctx.fillStyle = "rgba(0,0,0,.75)";
          const w = Math.max(28, labelText.length * 7 + 12);
          ctx.fillRect(lx-4, ly-12, w, 18);
          ctx.fillStyle = "#fff";
          ctx.fillText(labelText, lx+4, ly+2);
        }
      } else {
        // polygon zone
        ctx.beginPath();
        ctx.moveTo(poly[0].x, poly[0].y);
        for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i].x, poly[i].y);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "rgba(255,255,255,.9)";
        ctx.stroke();

        // label at top-left-ish
        if (labelText != null) {
          const xs = poly.map(p=>p.x), ys = poly.map(p=>p.y);
          const lx = Math.min(...xs) + 6, ly = Math.min(...ys) + 16;
          ctx.font = "12px system-ui, -apple-system, Segoe UI, Roboto, Arial";
          ctx.fillStyle = "rgba(0,0,0,.75)";
          const w = Math.max(28, labelText.length * 7 + 12);
          ctx.fillRect(lx-4, ly-12, w, 18);
          ctx.fillStyle = "#fff";
          ctx.fillText(labelText, lx+4, ly+2);
        }
      }

      // vertices
      ctx.fillStyle = "rgba(255,255,255,.9)";
      poly.forEach(pt => { ctx.beginPath(); ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2); ctx.fill(); });
    }

    // ---------- REPLACED: redraw to use live counts + colors ----------
    function redraw() {
      ctx.clearRect(0,0,canvas.width,canvas.height);

      zones.forEach(z => {
        const ptsDisp = z.points.map(scaleToDisplay);

        // live value (default 0)
        const count = (liveZoneCounts && typeof liveZoneCounts[z.name] === "number")
          ? liveZoneCounts[z.name]
          : 0;

        // color logic
        let color;
        if (z.points.length === 2) {
          // line zones: keep golden line, just show count label
          color = "auto-line";
        } else {
          // polygon zones: green when occupied, blue when empty
          color = count > 0 ? "rgba(44,195,138,0.30)" : "rgba(0,150,255,0.25)";
        }

        const label = `🧍 ${count}`;
        drawPoly(ptsDisp, color, label);
      });

      // current drawing overlay
      if (toolMode === "line" || toolMode === "poly" || drawing) {
        const color = (toolMode === "line") ? "rgba(255,215,0,0.90)" : "rgba(0,150,255,0.35)";
        drawPoly(pointsDisplay, color);
      }

      // canvas mode classes
      canvas.classList.remove("draw-line","draw-poly","edit-mode");
      if (toolMode === "line") canvas.classList.add("draw-line");
      if (toolMode === "poly" || drawing) canvas.classList.add("draw-poly");
      if (toolMode === "edit") canvas.classList.add("edit-mode");
    }

    async function loadZones() {
      const { ok, data } = await getJSON("/api/zones");
      if (!ok) { zoneList.innerHTML="<li>Failed to load zones</li>"; return; }
      zones = Array.isArray(data) ? data : [];
      renderZoneList();
      redraw();
    }

    // ------------ [UPDATED] richer list with live count badges ------------
    function renderZoneList() {
      zoneList.innerHTML = "";
      if (!zones.length) {
        zoneList.innerHTML = "<li>No zones yet.</li>";
        return;
      }
      zones.forEach(z => {
        const li = document.createElement("li");

        // left: name + live count badge
        const left = document.createElement("div");
        left.style.display = "flex";
        left.style.alignItems = "center";
        left.style.gap = "10px";

        const nameEl = document.createElement("span");
        nameEl.textContent = z.name;

        const countEl = document.createElement("span");
        countEl.className = "count-badge";
        countEl.dataset.zoneName = z.name;    // used for live updates
        countEl.textContent = "0";

        left.appendChild(nameEl);
        left.appendChild(countEl);

        // right: actions
        const row = document.createElement("div");
        row.style.display="flex";
        row.style.gap="8px";
        row.style.marginLeft="auto";

        const preview=document.createElement("button");
        preview.textContent="Highlight";
        preview.onclick=()=>{ drawPoly(z.points.map(scaleToDisplay), "rgba(255,215,0,0.35)"); setTimeout(redraw,800); };

        const pick=document.createElement("button");
        pick.textContent="Pick";
        pick.onclick=()=>{ pointsDisplay = z.points.map(scaleToDisplay); redraw(); showToast(`Picked "${z.name}"`); };

        const edit=document.createElement("button");
        edit.textContent="Edit";
        edit.onclick=()=>{ /* (same edit handler you already have) */
          if (!zoneNameInput) return;
          toolMode = "edit";
          pointsDisplay = z.points.map(scaleToDisplay);
          zoneNameInput.value = z.name;
          redraw();

          const originalSave = btnSave.onclick;
          restoreDefaultSave = () => { btnSave.onclick = originalSave; };
          btnSave.disabled = false; btnCancel.disabled = false;
          btnSave.onclick = async () => {
            const name = zoneNameInput.value.trim();
            if (!name) return showToast("Enter zone name");
            if (pointsDisplay.length < 2) return showToast("Need at least 2 points");
            const originalPoints = pointsDisplay.map(scaleToOriginal);
            const { ok, data } = await sendJSON(`/api/zones/${z.id}`, "PUT", { name, points: originalPoints });
            if (ok){
              showToast("Zone updated");
              pointsDisplay = []; zoneNameInput.value = ""; toolMode = "none";
              await loadZones(); redraw(); restoreDefaultSave && restoreDefaultSave();
              btnSave.disabled = true; btnCancel.disabled = true;
            } else showToast(data?.message || "Update failed", 1600);
          };
        };

        const del=document.createElement("button");
        del.textContent="Delete";
        del.onclick=async()=> {
          if (!confirm(`Delete zone "${z.name}"?`)) return;
          const { ok, data } = await sendJSON(`/api/zones/${z.id}`,"DELETE");
          if (ok){ zones=zones.filter(x=>x.id!==z.id); renderZoneList(); redraw(); showToast("Zone deleted"); }
          else showToast(data?.message||"Failed to delete zone",1600);
        };

        row.appendChild(preview); row.appendChild(pick); row.appendChild(edit); row.appendChild(del);

        li.appendChild(left);
        li.appendChild(row);
        zoneList.appendChild(li);
      });
    }

    // ------------ NEW: live badge updater ------------
    function updateZoneBadges(counts) {
      const map = counts || {};
      document.querySelectorAll('[data-zone-name]').forEach(el => {
        const name = el.dataset.zoneName;
        const val = (name in map) ? map[name] : 0;
        el.textContent = String(val);
      });
    }

    // original polygon button
    btnStart?.addEventListener("click",()=>{
      const name = zoneNameInput?.value.trim();
      if (!name) return showToast("Enter zone name first");
      drawing=true; toolMode="poly"; pointsDisplay=[];
      btnSave.disabled=false; btnCancel.disabled=false;
      showToast("Draw zone: click on video (polygon)"); redraw();
    });

    // new line/polygon tools
    drawLineBtn?.addEventListener("click", ()=>{
      const name = zoneNameInput?.value.trim();
      if (!name) return showToast("Enter zone name first");
      toolMode = "line"; drawing=false; pointsDisplay = [];
      btnSave.disabled=false; btnCancel.disabled=false;
      drawLineBtn.setAttribute("aria-pressed","true");
      drawPolyBtn?.setAttribute("aria-pressed","false"); editBtn?.setAttribute("aria-pressed","false");
      showToast("Draw LINE: click two points"); redraw();
    });
    drawPolyBtn?.addEventListener("click", ()=>{
      const name = zoneNameInput?.value.trim();
      if (!name) return showToast("Enter zone name first");
      toolMode = "poly"; drawing=false; pointsDisplay = [];
      btnSave.disabled=false; btnCancel.disabled=false;
      drawPolyBtn.setAttribute("aria-pressed","true");
      drawLineBtn?.setAttribute("aria-pressed","false"); editBtn?.setAttribute("aria-pressed","false");
      showToast("Draw POLYGON: click 3+ points"); redraw();
    });
    editBtn?.addEventListener("click", ()=>{
      toolMode = "edit"; drawing=false; pointsDisplay = [];
      btnSave.disabled=true; btnCancel.disabled=false;
      editBtn.setAttribute("aria-pressed","true");
      drawLineBtn?.setAttribute("aria-pressed","false"); drawPolyBtn?.setAttribute("aria-pressed","false");
      showToast("Edit mode: select a zone from the list, then Save to update"); redraw();
    });

    canvas.addEventListener("click",(e)=>{
      const rect=canvas.getBoundingClientRect();
      const x=e.clientX-rect.left, y=e.clientY-rect.top;
      const p = { x:Math.max(0,Math.min(canvas.width,x)), y:Math.max(0,Math.min(canvas.height,y)) };

      if (drawing) { pointsDisplay.push(p); redraw(); return; }
      if (toolMode === "line" || toolMode === "poly") { pointsDisplay.push(p); redraw(); }
    });

    btnCancel?.addEventListener("click",()=>{
      drawing=false; toolMode="none"; pointsDisplay=[];
      btnSave.disabled=true; btnCancel.disabled=true;
      restoreDefaultSave && restoreDefaultSave();
      redraw(); showToast("Drawing cancelled");
    });

    const defaultSaveHandler = async ()=>{
      const minPts = (toolMode === "line") ? 2 : 3;
      if ((drawing || toolMode==="poly" || toolMode==="line") && pointsDisplay.length < minPts)
        return showToast(`Need ${minPts}+ points`);
      const name=zoneNameInput.value.trim();
      if (!name) return showToast("Enter zone name");

      const originalPoints = pointsDisplay.map(scaleToOriginal);
      const { ok, data } = await sendJSON("/api/zones","POST",{name,points:originalPoints});
      if (ok){
        drawing=false; toolMode="none"; pointsDisplay=[];
        btnSave.disabled=true; btnCancel.disabled=true;
        zoneNameInput.value=""; await loadZones(); showToast("Zone saved");
      } else showToast(data?.message||"Save failed",1600);
    };
    btnSave && (btnSave.onclick = defaultSaveHandler);

    function initAfterImageLoads(){
      const tmp=new Image();
      tmp.onload=()=>{
        imgNaturalWidth=tmp.naturalWidth||1280;
        imgNaturalHeight=tmp.naturalHeight||720;
        resizeCanvas(); loadZones(); loadSettings();
      };
      tmp.src=img.src;
    }
    if (img.complete) initAfterImageLoads(); else img.onload=initAfterImageLoads;
    window.onresize=resizeCanvas;

    // ---------- Charts + SSE ----------
    let lineChart, barChart;
    function ensureCharts(){
      if (lineEl && !lineChart){
        lineChart = new Chart(lineEl.getContext('2d'), {
          type: 'line',
          data: { labels: [], datasets: [{ label: 'People', data: [] }] },
          options: { animation:false, responsive:true, maintainAspectRatio:false,
            plugins:{ legend:{ display:false } },
            scales:{ x:{ ticks:{ display:false }}, y:{ beginAtZero:true, suggestedMax:10 } } }
        });
      }
      if (barEl && !barChart){
        barChart = new Chart(barEl.getContext('2d'), {
          type: 'bar',
          data: { labels: [], datasets: [{ label: 'Per Zone', data: [] }] },
          options: { animation:false, responsive:true, maintainAspectRatio:false,
            plugins:{ legend:{ display:false } },
            scales:{ y:{ beginAtZero:true, suggestedMax:10 } } }
        });
      }
    }

    function updateCharts(payload){
      ensureCharts();
      const t = new Date(payload.timestamp * 1000).toLocaleTimeString();
      const total = payload.total_people || 0;

      lineChart.data.labels.push(t);
      lineChart.data.datasets[0].data.push(total);
      if (lineChart.data.labels.length > 120){ lineChart.data.labels.shift(); lineChart.data.datasets[0].data.shift(); }
      lineChart.update('none');

      const zonesObj = payload.zones || {};
      barChart.data.labels = Object.keys(zonesObj);
      barChart.data.datasets[0].data = Object.values(zonesObj);
      barChart.update('none');
    }

    // compact heat scatter
    const heatCtx = heatmapEl ? heatmapEl.getContext('2d') : null;
    function drawHeatmap(centersNorm){
      if (!heatCtx || !heatmapEl) return;
      heatCtx.fillStyle = "rgba(14,22,52,0.35)";
      heatCtx.fillRect(0,0,heatmapEl.width,heatmapEl.height);
      centersNorm.forEach(pt=>{
        const x = Math.round(pt.x * heatmapEl.width);
        const y = Math.round(pt.y * heatmapEl.height);
        const r = 14;
        const grad = heatCtx.createRadialGradient(x,y,1, x,y,r);
        grad.addColorStop(0, "rgba(0,200,255,0.65)");
        grad.addColorStop(1, "rgba(0,200,255,0.0)");
        heatCtx.fillStyle = grad;
        heatCtx.beginPath(); heatCtx.arc(x,y,r,0,Math.PI*2); heatCtx.fill();
      });
    }

    function updateStats(payload){
      if (!liveStats) return;
      const rows = [`<span class="pill">Total: <b>${payload.total_people ?? 0}</b></span>`];
      if (payload.zones){ for (const [k,v] of Object.entries(payload.zones)){ rows.push(`<span class="pill">${k}: <b>${v}</b></span>`); } }
      liveStats.innerHTML = rows.join(" ");
    }
    function checkAlerts(payload){
      if (!alertsEnabled || !alertBanner) return;
      const thr = Number(alertThresholdEl?.value ?? 0) || 0;
      const tot = Number(payload.total_people ?? 0);
      if (tot > thr) alertBanner.classList.remove("hidden");
      else alertBanner.classList.add("hidden");
    }

    // SSE (fallback to polling)
    function startLive(){
      if (window.EventSource){
        const es = new EventSource("/api/live");
        es.onmessage = (ev)=>{
          try{
            const payload = JSON.parse(ev.data);

            // NEW: store live per-zone counts and repaint overlay
            liveZoneCounts = payload.zones || {};
            if (ctx) redraw();

            updateCharts(payload);
            updateStats(payload);
            drawHeatmap(payload.centers || []);
            updateZoneBadges(payload.zones);  // list badges
            checkAlerts(payload);
          }catch(_){}
        };
      } else { pollLive(); }
    }
    async function pollLive(){
      try{
        const { ok, data } = await getJSON("/api/count/live");
        if (ok && data){
          const payload = { total_people: data.total, zones: data.per_zone, timestamp: Math.floor(Date.now()/1000), centers: [] };

          // NEW: store live per-zone counts and repaint overlay
          liveZoneCounts = payload.zones || {};
          if (ctx) redraw();

          updateCharts(payload);
          updateStats(payload);
          drawHeatmap([]);
          updateZoneBadges(payload.zones);    // list badges
          checkAlerts(payload);
        }
      }catch(_){}
      finally{ setTimeout(pollLive, 1000); }
    }
    startLive();

    // ======= Export buttons (CSV/PDF) =======
    exportCSVBtn?.addEventListener("click", ()=>{
      const mins = exportWindowSel?.value || "15";
      window.location.href = `/api/export/csv?minutes=${encodeURIComponent(mins)}`;
    });
    exportPDFBtn?.addEventListener("click", ()=>{
      const mins = exportWindowSel?.value || "15";
      window.location.href = `/api/export/pdf?minutes=${encodeURIComponent(mins)}`;
    });
  }

  // ============================================================
  // ✅ VIDEO CONTROLS
  // ============================================================
  const btnStartCam = document.getElementById("btnStartCam");
  const btnStopCam = document.getElementById("btnStopCam");
  const btnUploadVideo = document.getElementById("btnUploadVideo");
  const btnUploadImage = document.getElementById("btnUploadImage");
  const videoFileInput = document.getElementById("videoFile");
  const imageFileInput = document.getElementById("imageFile");
  const feed = document.getElementById("feed");

  btnStartCam?.addEventListener("click", async () => {
    const { ok, data } = await postJSON("/api/camera/start");
    if (ok) { showToast("Camera Started ✅"); feed.src = "/video?ts=" + Date.now(); }
    else showToast(data?.message || "Failed to start");
  });

  btnStopCam?.addEventListener("click", async () => {
    const { ok, data } = await postJSON("/api/camera/stop");
    if (ok) { showToast("Camera Stopped 🛑"); feed.src = ""; }
    else showToast(data?.message || "Failed to stop");
  });

  btnUploadVideo?.addEventListener("click", async () => {
    const file = videoFileInput?.files?.[0];
    if (!file) return showToast("Pick a video file");
    const fd = new FormData(); fd.append("file", file);
    const res = await fetch("/api/upload/video", { method: "POST", credentials: "include", body: fd });
    let data={}; try { data=await res.json(); } catch(_){}
    if (res.ok) { showToast("Video Loaded ✅"); feed.src = "/video?ts=" + Date.now(); }
    else showToast(data?.message || "Upload fail ❌");
  });

  btnUploadImage?.addEventListener("click", async () => {
    const file = imageFileInput?.files?.[0];
    if (!file) return showToast("Pick an image file");
    const fd = new FormData(); fd.append("file", file);
    const res = await fetch("/api/upload/image", { method: "POST", credentials: "include", body: fd });
    let data={}; try { data=await res.json(); } catch(_){}
    if (res.ok) { showToast("Image Loaded 🖼✅"); feed.src = "/video?ts=" + Date.now(); }
    else showToast(data?.message || "Image upload failed ❌");
  });

});
async function checkRole() {
  const res = await fetch("/api/me", { credentials: "include" });
  const data = await res.json();

  if (data.ok && data.role === "admin") {
    document.querySelectorAll(".admin-only").forEach(el => el.classList.remove("hidden"));
  }
}

checkRole();
