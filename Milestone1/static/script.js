// ---------- tiny toast helper ----------
function showToast(message = "", duration = 1200) {
  // create container once
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
    credentials: "include", // important for JWT cookies
    body: JSON.stringify(body || {})
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
        if (msg) msg.textContent = "Registered successfully. Please log in.";
        showToast("Registered successfully. Please log in.");
        setTimeout(() => (window.location.href = "/login"), 1000);
      } else {
        if (msg) msg.textContent = data.message || "Registration failed.";
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
        if (msg) msg.textContent = "Login successful.";
        showToast("Login successful");
        setTimeout(() => (window.location.href = "/admin/dashboard"), 900);
      } else {
        if (msg) msg.textContent = data.message || "Invalid credentials.";
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
});
