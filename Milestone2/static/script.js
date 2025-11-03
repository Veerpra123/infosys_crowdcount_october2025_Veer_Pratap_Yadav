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

  if (img && canvas && ctx && zoneList) {
    let drawing = false;
    let pointsDisplay = [];
    let zones = [];
    let imgNaturalWidth = 0;
    let imgNaturalHeight = 0;

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

    function drawPoly(poly, color="rgba(0,150,255,0.35)") {
      if (poly.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(poly[0].x, poly[0].y);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i].x, poly[i].y);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "rgba(255,255,255,.9)";
      ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,.9)";
      poly.forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    function redraw() {
      ctx.clearRect(0,0,canvas.width,canvas.height);
      zones.forEach(z => drawPoly(z.points.map(scaleToDisplay), "rgba(0,200,0,0.25)"));
      drawPoly(pointsDisplay, "rgba(0,150,255,0.35)");
    }

    async function loadZones() {
      const { ok, data } = await getJSON("/api/zones");
      if (!ok) { zoneList.innerHTML="<li>Failed to load zones</li>"; return; }
      zones = Array.isArray(data) ? data : [];
      renderZoneList();
      redraw();
    }

    function renderZoneList() {
      zoneList.innerHTML = "";
      if (!zones.length) {
        zoneList.innerHTML = "<li>No zones yet.</li>";
        return;
      }
      zones.forEach(z => {
        const li = document.createElement("li");
        li.textContent = z.name;
        const row = document.createElement("div");
        row.style.display="flex";
        row.style.gap="8px";
        row.style.marginLeft="auto";

        const preview=document.createElement("button");
        preview.textContent="Highlight";
        preview.onclick=()=>{ drawPoly(z.points.map(scaleToDisplay),"rgba(255,215,0,0.35)"); setTimeout(redraw,600); };

        const del=document.createElement("button");
        del.textContent="Delete";
        del.onclick=async()=> {
          if (!confirm(`Delete zone "${z.name}"?`)) return;
          const { ok, data } = await sendJSON(`/api/zones/${z.id}`,"DELETE");
          if (ok){ zones=zones.filter(x=>x.id!==z.id); renderZoneList(); redraw(); showToast("Zone deleted"); }
          else showToast(data?.message||"Failed to delete zone",1600);
        };

        row.appendChild(preview);
        row.appendChild(del);
        li.appendChild(row);
        zoneList.appendChild(li);
      });
    }

    btnStart?.addEventListener("click",()=>{
      const name = zoneNameInput?.value.trim();
      if (!name) return showToast("Enter zone name first");
      pointsDisplay=[]; drawing=true;
      btnSave.disabled=false; btnCancel.disabled=false;
      showToast("Draw zone: click on video");
    });

    canvas.addEventListener("click",(e)=>{
      if (!drawing) return;
      const rect=canvas.getBoundingClientRect();
      const x=e.clientX-rect.left;
      const y=e.clientY-rect.top;
      pointsDisplay.push({x:Math.max(0,Math.min(canvas.width,x)),y:Math.max(0,Math.min(canvas.height,y))});
      redraw();
    });

    btnCancel?.addEventListener("click",()=>{
      drawing=false; pointsDisplay=[];
      btnSave.disabled=true; btnCancel.disabled=true;
      redraw(); showToast("Drawing cancelled");
    });

    btnSave?.addEventListener("click",async()=>{
      if (!drawing||pointsDisplay.length<3) return showToast("Need 3+ points");
      const name=zoneNameInput.value.trim();
      if (!name) return showToast("Enter zone name");
      const originalPoints = pointsDisplay.map(scaleToOriginal);
      const { ok, data } = await sendJSON("/api/zones","POST",{name,points:originalPoints});
      if (ok){
        drawing=false; pointsDisplay=[];
        btnSave.disabled=true; btnCancel.disabled=true;
        zoneNameInput.value=""; await loadZones(); showToast("Zone saved");
      } else showToast(data?.message||"Save failed",1600);
    });

    function initAfterImageLoads(){
      const tmp=new Image();
      tmp.onload=()=>{
        imgNaturalWidth=tmp.naturalWidth||1280;
        imgNaturalHeight=tmp.naturalHeight||720;
        resizeCanvas(); loadZones();
      };
      tmp.src=img.src;
    }

    if (img.complete) initAfterImageLoads();
    else img.onload=initAfterImageLoads;

    window.onresize=resizeCanvas;
  }

  // ============================================================
  // ✅ VIDEO CONTROLS: Camera Start / Stop / Upload Video / Image
  // ============================================================
  const btnStartCam = document.getElementById("btnStartCam");
  const btnStopCam = document.getElementById("btnStopCam");
  const btnUploadVideo = document.getElementById("btnUploadVideo");
  const btnUploadImage = document.getElementById("btnUploadImage");
  const videoFileInput = document.getElementById("videoFile");
  const imageFileInput = document.getElementById("imageFile");
  const feed = document.getElementById("feed");

  // ✅ Start Camera
  btnStartCam?.addEventListener("click", async () => {
    const { ok, data } = await postJSON("/api/camera/start");
    if (ok) {
      showToast("Camera Started ✅");
      feed.src = "/video?ts=" + Date.now();
    } else showToast(data?.message || "Failed to start");
  });

  // ✅ Stop Camera
  btnStopCam?.addEventListener("click", async () => {
    const { ok, data } = await postJSON("/api/camera/stop");
    if (ok) {
      showToast("Camera Stopped 🛑");
      feed.src = "";
    } else showToast(data?.message || "Failed to stop");
  });

  // ✅ Upload Video
  btnUploadVideo?.addEventListener("click", async () => {
    const file = videoFileInput?.files?.[0];
    if (!file) return showToast("Pick a video file");

    const fd = new FormData();
    fd.append("file", file);

    const res = await fetch("/api/upload/video", {
      method: "POST",
      credentials: "include",
      body: fd
    });

    let data={}; try { data=await res.json(); } catch(_){}

    if (res.ok) {
      showToast("Video Loaded ✅");
      feed.src = "/video?ts=" + Date.now();
    } else showToast(data?.message || "Upload fail ❌");
  });

  // ✅ Upload Image
  btnUploadImage?.addEventListener("click", async () => {
    const file = imageFileInput?.files?.[0];
    if (!file) return showToast("Pick an image file");

    const fd = new FormData();
    fd.append("file", file);

    const res = await fetch("/api/upload/image", {
      method: "POST",
      credentials: "include",
      body: fd
    });

    let data={}; try { data=await res.json(); } catch(_){}

    if (res.ok) {
      showToast("Image Loaded 🖼✅");
      feed.src = "/video?ts=" + Date.now();
    } else showToast(data?.message || "Image upload failed ❌");
  });

}); // END DOMContentLoaded
