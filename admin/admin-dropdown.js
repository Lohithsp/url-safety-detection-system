document.addEventListener('DOMContentLoaded', function () {
  function createDropdown() {
    const profileButtons = document.querySelectorAll('.topbar .topbar-actions .profile-chip');
    profileButtons.forEach(btn => {
      // ensure we don't add twice
      if (btn.dataset.dropdownAttached) return;
      btn.dataset.dropdownAttached = '1';

      // create dropdown element
      const dropdown = document.createElement('div');
      dropdown.className = 'profile-dropdown';
      dropdown.innerHTML = `
        <a href="settings.html">Profile</a>
        <a href="settings.html">Settings</a>
        <a href="#" data-action="logout">Logout</a>
      `;

      // append to body so it's not clipped by parent overflow
      document.body.appendChild(dropdown);

      // helper to position dropdown below the button
      function positionDropdown() {
        const rect = btn.getBoundingClientRect();
        // align right edge of dropdown with right edge of button
        const right = window.innerWidth - rect.right;
        dropdown.style.top = (rect.bottom + 8) + 'px';
        dropdown.style.right = right + 'px';
      }

      // toggle on button click
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        const isOpen = btn.classList.toggle('open');
        if (isOpen) {
          dropdown.style.display = 'flex';
          positionDropdown();
        } else {
          dropdown.style.display = 'none';
        }
      });

      // reposition on resize/scroll when open
      window.addEventListener('resize', function () {
        if (btn.classList.contains('open')) positionDropdown();
      });
      window.addEventListener('scroll', function () {
        if (btn.classList.contains('open')) positionDropdown();
      }, true);

      // handle dropdown link clicks
      dropdown.addEventListener('click', function (e) {
        e.stopPropagation();
        const target = e.target.closest('a');
        if (!target) return;
        const action = target.dataset.action;
        // logout should call the PHP endpoint and then redirect client-side
        if (action === 'logout') {
          e.preventDefault();
          fetch('../php/logout.php', { method: 'GET', credentials: 'include' })
            .then(res => res.json().catch(() => ({ success: false })))
            .then(data => {
              const redirect = (data && data.redirect) ? data.redirect : '../index.html';
              window.location.href = redirect;
            })
            .catch(() => { window.location.href = '../index.html'; });
          return;
        }
        // for normal links, close the menu and allow navigation
        btn.classList.remove('open');
        dropdown.style.display = 'none';
      });
    });

    // global outside click to close all
    document.addEventListener('click', function () {
      document.querySelectorAll('.topbar .topbar-actions .profile-chip.open').forEach(openBtn => {
        openBtn.classList.remove('open');
      });
      document.querySelectorAll('.profile-dropdown').forEach(dd => dd.style.display = 'none');
    });
  }

  createDropdown();
});
