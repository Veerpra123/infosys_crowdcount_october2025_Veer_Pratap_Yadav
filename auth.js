// static/auth.js
// Register & login using backend API, store access_token in localStorage

async function handleRegister(e) {
  e.preventDefault();
  const username = document.getElementById("reg-username").value.trim();
  const email = document.getElementById("reg-email")?.value.trim() || "";
  const password = document.getElementById("reg-password").value;
  if (!username || !password) return alert("Enter username and password");

  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ username, password, email })
  });
  if (res.ok) {
    alert("Registered. Please login.");
    window.location.href = "/login";
  } else {
    const err = await res.json().catch(()=>({}));
    alert("Register failed: " + (err.detail || JSON.stringify(err)));
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  if (!username || !password) return alert("Enter username and password");

  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ username, password })
  });
  if (!res.ok) {
    const err = await res.json().catch(()=>({}));
    alert("Login failed: " + (err.detail || JSON.stringify(err)));
    return;
  }
  const data = await res.json();
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("session_user", JSON.stringify({ username }));
  alert("Login successful");
  window.location.href = "/";
}

window.addEventListener("DOMContentLoaded", () => {
  const reg = document.getElementById("registerForm");
  if (reg) reg.addEventListener("submit", handleRegister);

  const login = document.getElementById("loginForm");
  if (login) login.addEventListener("submit", handleLogin);

  // dashboard: show username and logout
  const header = document.getElementById("welcome-header");
  const logoutBtn = document.getElementById("logoutBtn");
  const session = JSON.parse(localStorage.getItem("session_user") || "null");
  if (header) {
    if (!session || !session.username) {
      window.location.href = "/login";
    } else {
      header.textContent = `Welcome, ${session.username}`;
    }
  }
  if (logoutBtn) {
    logoutBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      localStorage.removeItem("access_token");
      localStorage.removeItem("session_user");
      window.location.href = "/login";
    });
  }
});
