const authTabs = Array.from(document.querySelectorAll('[data-auth-tab]'));
const authPanels = Array.from(document.querySelectorAll('[data-auth-panel]'));

function setMessage(key, text, type = '') {
  const target = document.querySelector(`[data-message-for="${key}"]`);
  if (!target) return;
  target.textContent = text || '';
  target.classList.remove('is-error', 'is-success');
  if (type) target.classList.add(type);
}

function setActiveTab(name) {
  authTabs.forEach((button) => button.classList.toggle('is-active', button.dataset.authTab === name));
  authPanels.forEach((panel) => panel.classList.toggle('is-active', panel.dataset.authPanel === name));
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  let data;
  try {
    data = await response.json();
  } catch (error) {
    data = { success: false, message: 'Unexpected server response' };
  }

  return { response, data };
}

function setBusy(form, busy) {
  form.querySelectorAll('button, input').forEach((el) => {
    if (el.type === 'button' || el.type === 'submit' || el.tagName === 'INPUT') {
      el.disabled = busy && el.type !== 'hidden';
    }
  });
}

authTabs.forEach((button) => {
  button.addEventListener('click', () => setActiveTab(button.dataset.authTab));
});

const adminLoginForm = document.getElementById('adminLoginForm');
if (adminLoginForm) {
  adminLoginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(adminLoginForm);
    setMessage('admin');
    setBusy(adminLoginForm, true);

    try {
      const { data } = await postJson('php/login.php', {
        role: 'admin',
        email: String(formData.get('email') || '').trim(),
        password: String(formData.get('password') || ''),
        remember: formData.get('remember') === 'on',
      });

      if (!data.success) {
        setMessage('admin', data.message || 'Admin login failed', 'is-error');
        return;
      }

      window.location.href = data.redirect || 'admin/admin.html';
    } catch (error) {
      setMessage('admin', 'Could not reach the server', 'is-error');
    } finally {
      setBusy(adminLoginForm, false);
    }
  });
}

const userLoginForm = document.getElementById('userLoginForm');

if (userLoginForm) {
  userLoginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(userLoginForm);
    const email = String(formData.get('email') || '').trim();
    const password = String(formData.get('password') || '');

    setMessage('user-login');
    setBusy(userLoginForm, true);

    try {
      const { data } = await postJson('php/login.php', {
        role: 'user',
        email,
        password,
      });

      if (!data.success) {
        setMessage('user-login', data.message || 'User login failed', 'is-error');
        return;
      }

      window.location.href = data.redirect || 'user/index.html';
    } catch (error) {
      setMessage('user-login', 'Could not reach the server', 'is-error');
    } finally {
      setBusy(userLoginForm, false);
    }
  });
}

const registerForm = document.getElementById('registerForm');

if (registerForm) {
  registerForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(registerForm);
    const name = String(formData.get('name') || '').trim();
    const email = String(formData.get('email') || '').trim();
    const password = String(formData.get('password') || '');
    const otp = String(formData.get('otp') || '').trim();

    setMessage('register');
    setBusy(registerForm, true);

    try {
      const { data } = await postJson('php/register.php', {
        action: 'register',
        name,
        email,
        password,
      });

      if (!data.success) {
        setMessage('register', data.message || 'Could not create account', 'is-error');
        return;
      }

      setMessage('register', data.message || 'Registration completed', 'is-success');
      registerForm.reset();
      setActiveTab('user-login');
    } catch (error) {
      setMessage('register', 'Could not reach the server', 'is-error');
    } finally {
      setBusy(registerForm, false);
    }
  });
}

setActiveTab('admin');