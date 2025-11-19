// shared helpers
async function getJSON(url){ const r=await fetch(url,{credentials:"include"}); let d=null; try{d=await r.json()}catch{} return {ok:r.ok,status:r.status,data:d}; }
async function sendJSON(url,method,body){ const r=await fetch(url,{method,credentials:"include",headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined}); let d={}; try{d=await r.json()}catch{} return {ok:r.ok,status:r.status,data:d}; }
function showToast(msg,d=1200){ let c=document.getElementById("toast-container"); if(!c){c=document.createElement("div");c.id="toast-container";Object.assign(c.style,{position:"fixed",left:"50%",top:"24px",transform:"translateX(-50%)",zIndex:9999});document.body.appendChild(c)} const t=document.createElement("div");t.textContent=msg;Object.assign(t.style,{background:"#1e2a5a",color:"#fff",padding:"10px 14px",marginTop:"8px",border:"1px solid #2f3a66",borderRadius:"10px",boxShadow:"0 8px 24px rgba(0,0,0,.35)",fontWeight:600,minWidth:"240px",textAlign:"center"});c.appendChild(t);setTimeout(()=>{t.remove(); if(!c.childElementCount) c.remove();},d);}

// detect page by tables present
document.addEventListener("DOMContentLoaded", async () => {
  const camTable = document.getElementById("camTable");
  const logsTable = document.getElementById("logsTable");
  const repTable  = document.getElementById("repTable");

  // --- Cameras page ---
  if (camTable){
    const tbody = camTable.querySelector("tbody");
    async function loadCams(){
      const {ok,data}=await getJSON("/api/cameras");
      tbody.innerHTML="";
      if(!ok){ tbody.innerHTML="<tr><td colspan=5>Failed to load</td></tr>"; return;}
      data.forEach(c=>{
        const tr=document.createElement("tr");
        tr.innerHTML = `
          <td>${c.id}</td>
          <td>${c.name}</td>
          <td style="max-width:420px;overflow:hidden;text-overflow:ellipsis;">${c.rtsp_url||"<i>webcam</i>"}</td>
          <td>${c.is_active? "Active":"Disabled"}</td>
          <td class="row">
            <button class="btn" data-act="start" data-id="${c.id}">Start</button>
            <button class="btn secondary" data-act="stop" data-id="${c.id}">Stop</button>
            <button class="btn" data-act="edit" data-id="${c.id}">Edit</button>
            <button class="btn" data-act="del" data-id="${c.id}">Delete</button>
          </td>`;
        tbody.appendChild(tr);
      })
    }
    await loadCams();

    document.getElementById("btnAddCam").onclick = async ()=>{
      const name = prompt("Camera name:");
      if(!name) return;
      const rtsp = prompt("RTSP URL (leave empty for webcam):") || "";
      const {ok,data}=await sendJSON("/api/cameras","POST",{name:name, rtsp_url:rtsp, is_active:true});
      if(ok){ showToast("Camera added"); loadCams(); } else showToast(data.message||"Create failed",1600);
    };

    tbody.addEventListener("click", async (e)=>{
      const btn=e.target.closest("button"); if(!btn) return;
      const id = btn.dataset.id; const act = btn.dataset.act;
      if(act==="start"){
        const {ok,data}=await fetch(`/api/camera/start_by_id?id=${id}`,{method:"POST",credentials:"include"}); 
        showToast(ok?"Started":"Failed"); 
      }
      if(act==="stop"){
        const {ok,data}=await fetch(`/api/camera/stop_by_id`,{method:"POST",credentials:"include"});
        showToast(ok?"Stopped":"Failed");
      }
      if(act==="edit"){
        const currentRow = btn.closest("tr");
        const curName = currentRow.children[1].textContent.trim();
        const curSrc  = currentRow.children[2].textContent.trim();
        const name = prompt("New name:", curName) || curName;
        const rtsp = prompt("New RTSP (blank=webcam):", (curSrc==="webcam"? "":curSrc)) || "";
        const {ok,data}=await sendJSON(`/api/cameras/${id}`,"PUT",{name,rtsp_url:rtsp,is_active:true});
        showToast(ok?"Updated":"Update failed");
        if(ok) loadCams();
      }
      if(act==="del"){
        if(!confirm("Delete camera?")) return;
        const {ok,data}=await sendJSON(`/api/cameras/${id}`,"DELETE");
        showToast(ok?"Deleted":"Delete failed");
        if(ok) loadCams();
      }
    });
  }

  // --- Logs page ---
  if (logsTable){
    const tbody = logsTable.querySelector("tbody");
    async function loadLogs(){
      const level = document.getElementById("logLevel").value;
      const q = document.getElementById("logQuery").value.trim();
      const from = document.getElementById("logFrom").value;
      const to   = document.getElementById("logTo").value;
      const qs = new URLSearchParams({level,q,from,to,limit:"200"});
      const {ok,data}=await getJSON("/api/logs?"+qs.toString());
      tbody.innerHTML="";
      if(!ok){ tbody.innerHTML="<tr><td colspan=6>Failed to load</td></tr>"; return;}
      data.forEach(r=>{
        const tr=document.createElement("tr");
        const meta = r.meta_json ? r.meta_json : "";
        tr.innerHTML = `
          <td>${r.id}</td>
          <td>${r.ts}</td>
          <td>${r.level}</td>
          <td>${r.actor_email||""}</td>
          <td>${r.action}</td>
          <td><code style="font-size:12px">${meta}</code></td>`;
        tbody.appendChild(tr);
      });
    }
    document.getElementById("btnLogFilter").onclick = loadLogs;
    await loadLogs();
  }

  // --- Reports page ---
  if (repTable){
    const tbody = repTable.querySelector("tbody");
    async function loadReports(){
      const {ok,data}=await getJSON("/api/reports");
      tbody.innerHTML="";
      if(!ok){ tbody.innerHTML="<tr><td colspan=5>Failed to load</td></tr>"; return;}
      data.forEach(r=>{
        const range = `${new Date(r.ts_from*1000).toLocaleString()} → ${new Date(r.ts_to*1000).toLocaleString()}`;
        const tr=document.createElement("tr");
        tr.innerHTML = `
          <td>${r.id}</td>
          <td>${range}</td>
          <td>${r.kind.toUpperCase()}</td>
          <td style="max-width:420px;overflow:hidden;text-overflow:ellipsis;">${r.path}</td>
          <td class="row">
            <a class="btn" href="/api/reports/${r.id}">Download</a>
            <button class="btn secondary" data-del="${r.id}">Delete</button>
          </td>`;
        tbody.appendChild(tr);
      });
    }
    await loadReports();

    document.getElementById("btnExportCSV").onclick = async ()=>{
      const r = await fetch("/api/export/csv?minutes=15",{credentials:"include"});
      if(r.ok){ showToast("CSV exported"); await loadReports(); window.location.href = r.url; }
      else showToast("Export failed",1600);
    };
    document.getElementById("btnExportPDF").onclick = async ()=>{
      const r = await fetch("/api/export/pdf?minutes=15",{credentials:"include"});
      if(r.ok){ showToast("PDF exported"); await loadReports(); window.location.href = r.url; }
      else showToast("Export failed",1600);
    };

    tbody.addEventListener("click", async (e)=>{
      const btn=e.target.closest("button"); if(!btn) return;
      const id = btn.dataset.del;
      if(!id) return;
      if(!confirm("Delete report?")) return;
      const {ok}=await sendJSON(`/api/reports/${id}`,"DELETE");
      showToast(ok?"Deleted":"Delete failed");
      if(ok) loadReports();
    });
  }
});
