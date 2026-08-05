# Quick Start - Login System

## 📋 Quick Setup (5 minutes)

### 1️⃣ Create Database
```sql
1. Open http://localhost/phpmyadmin
2. Create database: url_safety
3. Go to SQL tab → paste contents of php/setup.sql → Click Go
```



### 2️⃣ Test Admin Login
```
URL: http://localhost/url-safety-detection-system/
Email: youremail@gmail.com
Password: yourpassword
```

### 3️⃣ Test User Registration
```
1. Click "User" tab
2. Fill registration form
3. Click "Register"
4. Registration uses email OTP verification; account is active after OTP verification
```

### 4️⃣ Approve Users (Admin)
```
1. (Optional) Admin can review users at /admin/users.html — approval is not required for OTP-verified registrations
```

### 5️⃣ User Login
```
Once approved, user can log in with their registered email & password
```

---

## 📁 New Files Created

| File | Purpose |
|------|---------|
| `index.html` | Updated login page |
| `php/db_config.php` | Database connection |
| `php/login.php` | Login handler |
| `php/register.php` | Registration handler |
| `php/check_session.php` | Session validation |
| `php/logout.php` | Logout handler |
| `php/manage_users.php` | Admin user management |
| `php/setup.sql` | Database schema |
| `admin/users.html` | Updated with approval UI |
| `SETUP_GUIDE.md` | Detailed guide |

---

## 🔐 User Types

### Admin
- **Email**: youremail@gmail.com
- **Password**: yourpassword
- **Access**: `/admin/users.html` to approve/reject users

### Users
- **Self-register** with email, name, password
- **Verification**: Users verify their email using a 6-digit OTP sent during registration and are active immediately after verification
- **Access**: `/user/` pages after verification

---

## ⚠️ Important Notes

1. **Database**: Create `url_safety` database first
2. **Admin**: Default credentials are hardcoded in `php/login.php`
3. **Sessions**: Expire after 2 hours
4. **Passwords**: Hashed using bcrypt
5. **Approval/Verification**: Admin approval is not required — OTP verification grants immediate access


---

## 🐛 If Something Breaks

| Issue | Solution |
|-------|----------|
| Database error | Check MySQL is running, db name is `url_safety` |
| Login fails | Check credentials in `php/db_config.php` |
| Users not visible | Refresh `/admin/users.html` page |
| Can't register | Email might already exist in database |

---

## 📞 Testing Flow

```
1. Clear database (delete all users from phpMyAdmin)
2. Register new user via User tab (you will receive an OTP by email)
3. Complete OTP verification on the registration form
4. Login as the new user (no admin approval required)
```

---

Good to go! 🚀
