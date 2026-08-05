# URL Safety Detection System - Login Setup Guide

## Overview
This document provides step-by-step instructions to set up the login system with admin approval workflow for the URL Safety Detection System using XAMPP.

---

## Prerequisites
- XAMPP installed and running
- MySQL/MariaDB running
- PHP 7.4 or higher

---

## Database Setup

### Step 1: Create Database

1. Open **phpMyAdmin** in your browser:
   ```
   http://localhost/phpmyadmin
   ```

2. Click on **SQL** tab or use the interface to create a new database:
   ```
   Database Name: url_safety
   ```

3. Once created, select the `url_safety` database from the left sidebar

4. Click on the **SQL** tab and paste the contents from `php/setup.sql`:
   - Copy all the SQL code from the setup file
   - Paste it into the SQL tab in phpMyAdmin
   - Click **Go** to execute

This will create the required tables:
- `users` - Stores user account information
- `url_scans` - Stores URL scan history
- `approval_logs` - Tracks user approvals

---

## File Structure

```
url-safety-detection-system/
├── index.html              ← Login page (updated)
├── styles.css
├── script.js
├── php/
│   ├── db_config.php       ← Database connection
│   ├── login.php           ← Admin/User login handler
│   ├── register.php        ← User registration handler
│   ├── check_session.php   ← Session validation
│   ├── logout.php          ← Logout handler
│   ├── manage_users.php    ← Admin user management
│   └── setup.sql           ← Database schema
├── admin/
│   ├── users.html          ← Updated with approval interface
│   └── [other admin pages]
└── user/
    └── [user pages]
```

---

## User Roles & Workflow

### Admin Login
- **Default Email**: `youremail@gmail.com`
- **Default Password**: `yourpassword`
- **Access**: Admin dashboard at `/admin/scan.html`
- **Capabilities**:
  - View pending user registrations
  - Approve or reject user accounts
  - View all users and their status
  - Access all admin tools

### User Registration
1. Users register via the **User** tab on the login page
2. After registration, status is set to **pending**
3. Admin must approve the user before they can log in
4. Once approved, users can access `/user/index.html`

### Approval Workflow
1. User submits registration form
2. User account created with status = **pending**
3. Admin views pending users in `/admin/users.html`
4. Admin clicks **Approve** button to activate user
5. User can now log in with their credentials

---

## Database Tables Schema

### users table
```sql
- id: INT (Primary Key, Auto-increment)
- name: VARCHAR(100)
- email: VARCHAR(120) - Unique
- password: VARCHAR(255) - Bcrypt hashed
- status: ENUM('pending', 'approved', 'rejected')
- registration_date: DATETIME
- approved_date: DATETIME
- last_login: DATETIME
```

### url_scans table
```sql
- id: INT (Primary Key)
- user_id: INT (Foreign Key to users)
- url: VARCHAR(2048)
- status: ENUM('safe', 'suspicious', 'malicious')
- detection_details: JSON
- scan_date: TIMESTAMP
```

### approval_logs table
```sql
- id: INT (Primary Key)
- user_id: INT (Foreign Key to users)
- admin_id: VARCHAR(100)
- action: ENUM('approved', 'rejected', 'pending')
- reason: TEXT
- timestamp: TIMESTAMP
```

---

## API Endpoints

### Login
**Endpoint**: `POST /php/login.php`
```json
Request Body:
{
  "email": "user@email.com",
  "password": "password123",
  "role": "admin" or "user",
  "remember": true/false
}

Response:
{
  "success": true/false,
  "message": "Login successful / Invalid credentials",
  "redirect": "page.html"
}
```

### Register
**Endpoint**: `POST /php/register.php`
```json
Request Body:
{
  "email": "newuser@email.com",
  "name": "User Full Name",
  "password": "password123"
}

Response:
{
  "success": true/false,
  "message": "Registration successful / Email already registered"
}
```

### Check Session
**Endpoint**: `GET /php/check_session.php`
```json
Response:
{
  "logged_in": true/false,
  "user": {
    "id": "user_id",
    "name": "User Name",
    "email": "user@email.com",
    "role": "admin" or "user"
  }
}
```

### Manage Users (Admin only)
**Endpoint**: `GET /php/manage_users.php?action=list`
```
Returns list of all users

POST /php/manage_users.php?action=approve&user_id=123
Approves a user

POST /php/manage_users.php?action=reject&user_id=123
Rejects a user
```

### Logout
**Endpoint**: `GET /php/logout.php`
```
Clears session and redirects to login
```

---

## Testing the System

### Test Admin Login
1. Open `http://localhost/url-safety-detection-system/`
2. Click on **Admin** tab
3. Enter:
   - Email: `youremail@gmail.com`
   - Password: `yourpassword`
4. Click **Login as Admin**
5. You should be redirected to admin dashboard

### Test User Registration
1. Open `http://localhost/url-safety-detection-system/`
2. Click on **User** tab
3. Fill in registration form with:
   - Email: `testuser@example.com`
   - Name: `Test User`
   - Password: `TestPass123`
   - Confirm Password: `TestPass123`
4. Click **Register**
5. You should see "Registration successful! Awaiting admin approval."

### Test User Approval
1. Log in as Admin
2. Go to `/admin/users.html`
3. You should see the pending user registration
4. Click **✓ Approve** button
5. The user will move from "Pending" to "Approved" status

### Test User Login
1. Open `http://localhost/url-safety-detection-system/`
2. Click on **User** tab
3. Enter approved user credentials
4. Click **Login**
5. You should be redirected to user dashboard

---

## Database Configuration

Edit `php/db_config.php` if your MySQL credentials are different:

```php
define('DB_HOST', 'localhost');     // MySQL host
define('DB_USER', 'root');          // MySQL username
define('DB_PASSWORD', '');          // MySQL password (usually empty for XAMPP)
define('DB_NAME', 'url_safety');    // Database name
```

---

## Session Management

- Session timeout: **2 hours** (7200 seconds)
- Session data includes: user_id, email, name, role
- Sessions are stored server-side (PHP default)
- Optional "Remember Me" feature uses cookies

---

## Security Features

1. **Password Hashing**: Uses bcrypt (PASSWORD_BCRYPT)
2. **SQL Injection Protection**: Prepared statements with parameterized queries
3. **CSRF Protection**: Set to implement with tokens (future)
4. **Session Security**: HTTPOnly cookies, SameSite policy
5. **Role-Based Access Control**: Admin vs User roles
6. **Email Validation**: Format validation before storage

---

## Troubleshooting

### "Database connection failed"
- Check if MySQL is running in XAMPP Control Panel
- Verify database name, username, and password in `db_config.php`
- Ensure `url_safety` database was created

### "Email already registered"
- User already exists in database
- Clear database or use different email

### Login not working
- Check browser console for errors
- Verify PHP files are in correct `php/` directory
- Check file paths in JavaScript (index.html)

### Admin can't see pending users
- Ensure new users were registered before logging in as admin
- Check `users` table in phpMyAdmin
- Verify user status is "pending" in database

### CORS/AJAX errors
- Ensure all PHP files return `header('Content-Type: application/json');`
- Check that requests are to correct relative paths

---

## Next Steps

1. Customize branding/logo in login page
2. Add email notifications for user approvals
3. Implement password recovery system
4. Add two-factor authentication (2FA)
5. Create user profile management page
6. Add activity logging and audit trail

---

## Support

For issues or questions, check:
- Browser Developer Console (F12) for errors
- phpMyAdmin to verify database structure
- XAMPP error logs for server issues

