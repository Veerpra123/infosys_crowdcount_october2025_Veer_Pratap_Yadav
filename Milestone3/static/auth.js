document.addEventListener("DOMContentLoaded", () => {
  // ---------- helpers ----------
  const setMsg = (id, text, ok = true) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("muted", ok);
  };

  const withLoading = async (btn, fn) => {
    const original = btn?.textContent;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Please wait…";
    }
    try { return await fn(); }
    finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = original;
      }
    }
  };

  // Toggle password visibility (works for <button class="show-password"> or <i class="show-password">)
  const wireShowPassword = () => {
    document.querySelectorAll(".input-group").forEach(group => {
      group.addEventListener("click", (e) => {
        const t = e.target;
        if (!t.classList.contains("show-password")) return;
        const input = group.querySelector('input[type="password"], input[type="text"][data-pw]');
        if (!input) return;

        const showing = input.getAttribute("type") === "text";
        if (showing) {
          input.setAttribute("type", "password");
          input.removeAttribute("data-pw");
          t.setAttribute("aria-label", "Show password");
          t.title = "Show Password";
          t.classList.remove("fa-eye-slash");
          t.classList.add("fa-eye");
        } else {
          input.setAttribute("type", "text");
          input.setAttribute("data-pw", "1");
          t.setAttribute("aria-label", "Hide password");
          t.title = "Hide Password";
          t.classList.remove("fa-eye");
          t.classList.add("fa-eye-slash");
        }
      });
    });
  };

  wireShowPassword();

  // ---------- REGISTER ----------
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = registerForm.querySelector('button[type="submit"]');
      const name = document.getElementById("reg-username")?.value?.trim();
      const email = document.getElementById("reg-email")?.value?.trim().toLowerCase();
      const password = document.getElementById("reg-password")?.value || "";

      if (!name || !email || !password) {
        setMsg("register-msg", "All fields are required.", false);
        return;
      }

      await withLoading(btn, async () => {
        try {
          const res = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password }),
            credentials: "include"
          });

          const data = await res.json().catch(() => ({}));
          if (res.ok) {
            setMsg("register-msg", data.message || "Registered!", true);
            // small delay so the user can see the message
            setTimeout(() => (window.location.href = "/login"), 400);
          } else {
            setMsg("register-msg", data.message || "Registration failed.", false);
          }
        } catch {
          setMsg("register-msg", "Network error. Please try again.", false);
        }
      });
    });
  }

  // ---------- LOGIN ----------
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = loginForm.querySelector('button[type="submit"]');
      const email = document.getElementById("login-email")?.value?.trim().toLowerCase();
      const password = document.getElementById("login-password")?.value || "";

      if (!email || !password) {
        setMsg("login-msg", "Email and password are required.", false);
        return;
      }

      await withLoading(btn, async () => {
        try {
          const res = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
            credentials: "include" // receive/set HttpOnly JWT cookie
          });

          const data = await res.json().catch(() => ({}));
          if (res.ok) {
            setMsg("login-msg", data.message || "Logged in.", true);
            window.location.href = "/admin/dashboard";
          } else {
            setMsg("login-msg", data.message || "Invalid credentials.", false);
          }
        } catch {
          setMsg("login-msg", "Network error. Please try again.", false);
        }
      });
    });
  }

  // ---------- LOGOUT ----------
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        await fetch("/api/logout", { method: "POST", credentials: "include" });
      } finally {
        window.location.href = "/login";
      }
    });
  }
});
