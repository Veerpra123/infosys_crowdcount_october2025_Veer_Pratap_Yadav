// static/auth.js
function qs(id){ return document.getElementById(id); }
async function safeJson(res){ try{return await res.json(); }catch(e){return {}; } }

/* Register */
async function handleRegister(event){
  event.preventDefault();
  const username = qs('reg-username')?.value?.trim();
  const email = qs('reg-email')?.value?.trim() || '';
  const password = qs('reg-password')?.value;
  if(!username||!password){ alert('Please enter username and password'); return; }
  try{
    const res = await fetch('/api/auth/register',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ username, password, email })
    });
    const data = await safeJson(res);
    if(res.ok && data.status === 'ok'){ alert('Registration successful! Redirecting to login...'); window.location.href = '/login'; }
    else { alert('Registration failed: ' + (data.detail || data.message || 'Unknown error')); }
  }catch(err){ console.error(err); alert('Network error while registering'); }
}

/* Login */
async function handleLogin(event){
  event.preventDefault();
  const username = qs('login-username')?.value?.trim();
  const password = qs('login-password')?.value;
  if(!username||!password){ alert('Please enter username and password'); return; }
  try{
    const res = await fetch('/api/auth/login',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ username, password })
    });
    const data = await safeJson(res);
    if(res.ok && data.access_token){
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('session_user', JSON.stringify({ username }));
      alert('Login successful! Redirecting to dashboard...');
      window.location.href = '/';
    } else {
      alert('Login failed: ' + (data.detail || 'Invalid credentials'));
    }
  }catch(err){ console.error(err); alert('Network error while logging in'); }
}

/* Logout */
function handleLogout(e){
  if(e) e.preventDefault();
  localStorage.removeItem('access_token');
  localStorage.removeItem('session_user');
  window.location.href = '/login';
}

/* Password toggle */
function initPasswordToggles(){
  document.querySelectorAll('.show-password').forEach(icon=>{
    icon.addEventListener('click', ()=>{
      const inp = icon.previousElementSibling;
      if(!inp) return;
      inp.type = (inp.type === 'password') ? 'text' : 'password';
      icon.classList.toggle('fa-eye'); icon.classList.toggle('fa-eye-slash');
    });
  });
}

/* Dashboard auth & header */
function initDashboardAuth(){
  const header = qs('welcome-header');
  const logoutBtn = qs('logoutBtn');
  const session = JSON.parse(localStorage.getItem('session_user') || 'null');
  const token = localStorage.getItem('access_token');
  if(!token || !session || !session.username){
    if(!/\/(login|register)/.test(window.location.pathname)) window.location.href = '/login';
    return;
  }
  if(header) header.textContent = `Welcome, ${session.username} 🙋`;
  if(logoutBtn) logoutBtn.addEventListener('click', handleLogout);
}

/* Attach */
document.addEventListener('DOMContentLoaded', ()=>{
  const regForm = qs('registerForm');
  const loginForm = qs('loginForm');
  if(regForm) { regForm.addEventListener('submit', handleRegister); initPasswordToggles(); }
  if(loginForm) { loginForm.addEventListener('submit', handleLogin); initPasswordToggles(); }
  initDashboardAuth();
});
