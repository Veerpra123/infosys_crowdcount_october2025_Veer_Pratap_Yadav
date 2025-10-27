document.addEventListener("DOMContentLoaded", () => {
  // ---------- REGISTER ----------
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("register-msg");

      const payload = {
        name: document.getElementById("reg-username").value,
        email: document.getElementById("reg-email").value,
        password: document.getElementById("reg-password").value
      };

      const res = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include"
      });

      const data = await res.json().catch(() => ({}));
      if (msg) msg.textContent = data.message || (res.ok ? "Registered!" : "Failed.");

      if (res.ok) window.location.href = "/login";
    });
  }

  // ---------- LOGIN ----------
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("login-msg");

      const payload = {
        email: document.getElementById("login-email").value,
        password: document.getElementById("login-password").value
      };

      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include" // set/receive HttpOnly JWT cookie
      });

      const data = await res.json().catch(() => ({}));
      if (msg) msg.textContent = data.message || (res.ok ? "Logged in." : "Invalid credentials.");

      if (res.ok) window.location.href = "/admin/dashboard";
    });
  }

  // ---------- LOGOUT ----------
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      await fetch("/api/logout", { method: "POST", credentials: "include" });
      window.location.href = "/login";
    });
  }
});
