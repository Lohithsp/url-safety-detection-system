// Add this script to the top of each protected page (admin & user pages)
// Usage: Include <script src="../js/session-protection.js"></script> before closing </body>

(async function() {
  try {
    const response = await fetch('../php/check_session.php');
    const data = await response.json();

    if (!data.logged_in) {
      // Redirect to login if not authenticated
      window.location.href = '../index.html';
      return;
    }

    // Optional: Store user info for use in page
    window.CURRENT_USER = data.user;

    // Add logout button functionality if available
    const logoutButtons = document.querySelectorAll('[data-logout]');
    logoutButtons.forEach(button => {
      button.addEventListener('click', async (e) => {
        e.preventDefault();
        await fetch('../php/logout.php');
        window.location.href = '../index.html';
      });
    });

    // Check role-based access
    const requiredRole = document.documentElement.getAttribute('data-require-role');
    if (requiredRole && data.user.role !== requiredRole) {
      console.error('Access denied. Required role: ' + requiredRole);
      window.location.href = '../index.html';
      return;
    }

  } catch (error) {
    console.error('Session check failed:', error);
    window.location.href = '../index.html';
  }
})();
