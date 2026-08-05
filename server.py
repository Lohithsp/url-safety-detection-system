from flask import Flask, request, session, jsonify, send_from_directory, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
import mysql.connector
from mysql.connector import Error as MySQLError

APP_ROOT = os.path.dirname(__file__)
DATA_DIR = os.path.join(APP_ROOT, 'data')
OTP_LOG = os.path.join(DATA_DIR, 'otp_log.txt')

os.makedirs(DATA_DIR, exist_ok=True)

def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip("\"'")
            if k and os.getenv(k) is None:
                os.environ[k] = v

load_env_file(os.path.join(APP_ROOT, '.env'))
load_env_file(os.path.join(APP_ROOT, '..', '.env'))

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'youremail@gmail.com')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'yourpassword')
MAIL_FROM_EMAIL = os.getenv('MAIL_FROM_EMAIL', ADMIN_EMAIL)
MAIL_FROM_NAME = os.getenv('MAIL_FROM_NAME', 'URL safety')
MAIL_APP_PASSWORD = os.getenv('MAIL_APP_PASSWORD', '').replace(' ', '')
APP_NAME = os.getenv('APP_NAME', 'URL safety')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', '1') != '0'
SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', '0') == '1'
OTP_EXPIRY_SECONDS = int(os.getenv('OTP_EXPIRY_SECONDS', '600'))
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'url_safety')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_SOCKET = os.getenv('DB_SOCKET')
SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '7200'))

app = Flask(__name__, static_folder=None)
app.secret_key = os.getenv('FLASK_SECRET', secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = True

class MySQLCompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        return self._cursor.execute(query.replace('?', '%s'), params)

    def executemany(self, query, seq_params):
        return self._cursor.executemany(query.replace('?', '%s'), seq_params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class MySQLCompatConnection:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return MySQLCompatCursor(self._connection.cursor(dictionary=True))

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)


def get_db():
    return MySQLCompatConnection(get_mysql_connection(create_database=True))

def mysql_dict_cursor(conn):
    return conn.cursor(dictionary=True)

def get_mysql_connection(create_database=False):
    connection_kwargs = {
        'user': DB_USER,
        'password': DB_PASSWORD,
    }
    if DB_SOCKET:
        connection_kwargs['unix_socket'] = DB_SOCKET
    else:
        connection_kwargs['host'] = DB_HOST
        connection_kwargs['port'] = DB_PORT

    if create_database:
        base_conn = mysql.connector.connect(**connection_kwargs)
        base_cur = base_conn.cursor()
        base_cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        base_conn.commit()
        base_cur.close()
        base_conn.close()

    connection_kwargs['database'] = DB_NAME
    conn = mysql.connector.connect(**connection_kwargs)
    conn.autocommit = False
    return conn

def get_mysql_otp_connection():
    try:
        return get_mysql_connection(create_database=False)
    except MySQLError:
        return get_mysql_connection(create_database=True)

def init_mysql_otp_tables():
    conn = get_mysql_otp_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS login_otps (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(120) NOT NULL,
        role VARCHAR(20) NOT NULL,
        user_id INT NULL,
        otp_hash VARCHAR(255) NOT NULL,
        expires_at DATETIME NOT NULL,
        used TINYINT(1) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_email_role (email, role),
        INDEX idx_expires_at (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
    cur.execute('''CREATE TABLE IF NOT EXISTS registration_otps (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(120) NOT NULL,
        name VARCHAR(100) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        otp_hash VARCHAR(255) NOT NULL,
        expires_at DATETIME NOT NULL,
        used TINYINT(1) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_email (email),
        INDEX idx_expires_at (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(120) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        role ENUM('user', 'admin') DEFAULT 'user',
        status ENUM('pending', 'approved', 'rejected') DEFAULT 'approved',
        last_login DATETIME NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
    cur.execute('''CREATE TABLE IF NOT EXISTS settings_store (
        id INT AUTO_INCREMENT PRIMARY KEY,
        role VARCHAR(20) NOT NULL,
        owner_key VARCHAR(120) NOT NULL,
        setting_key VARCHAR(120) NOT NULL,
        setting_value TEXT,
        UNIQUE KEY uniq_setting (role, owner_key, setting_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
    conn.commit()
    cur.close()
    conn.close()

def init_db():
    conn = get_mysql_connection(create_database=True)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(120) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        role ENUM('user', 'admin') DEFAULT 'user',
        status ENUM('pending', 'approved', 'rejected') DEFAULT 'approved',
        last_login DATETIME NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
    cur.execute('''CREATE TABLE IF NOT EXISTS settings_store (
        id INT AUTO_INCREMENT PRIMARY KEY,
        role VARCHAR(20) NOT NULL,
        owner_key VARCHAR(120) NOT NULL,
        setting_key VARCHAR(120) NOT NULL,
        setting_value TEXT,
        UNIQUE KEY uniq_setting (role, owner_key, setting_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
    cur.execute('''CREATE TABLE IF NOT EXISTS login_activity (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(120) NOT NULL,
        ip_address VARCHAR(45) NOT NULL,
        user_agent TEXT,
        login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
    cur.execute('''CREATE TABLE IF NOT EXISTS auth_attempts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        role VARCHAR(20) NOT NULL,
        email VARCHAR(120) NOT NULL,
        failed_count INT DEFAULT 0,
        blocked_until DATETIME NULL,
        last_failed_at DATETIME NULL,
        UNIQUE KEY uniq_role_email (role, email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
    conn.commit()
    cur.close()
    conn.close()

init_db()
init_mysql_otp_tables()

# Preload ML model and blacklist in background thread to warm up the memory cache
def preload_models_async():
    try:
        import time
        time.sleep(1) # Wait briefly for server startup
        from predict import scan_url
        # Run a dummy scan to warm up the joblib model and SHAP TreeExplainer caches
        scan_url("https://google.com")
    except Exception:
        pass

import threading
threading.Thread(target=preload_models_async, daemon=True).start()

def write_otp_log(email, otp):
    with open(OTP_LOG, 'a', encoding='utf-8') as f:
        f.write(f"{int(time.time())}\t{email}\t{otp}\n")

def send_otp_email(to_email, otp, purpose='registration'):
    subject = f"{APP_NAME} - {'Registration' if purpose == 'registration' else 'Login'} OTP"
    body = [
        'Hello,',
        '',
        f'Your OTP for {APP_NAME} {purpose} is: {otp}',
        'This OTP expires in 10 minutes.',
        '',
        'If you did not request this, please ignore this email.',
        '',
        f'{APP_NAME} Team',
    ]

    msg = EmailMessage()
    msg['From'] = f'{MAIL_FROM_NAME} <{MAIL_FROM_EMAIL}>'
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content('\r\n'.join(body))

    attempts = []

    def try_send(host, port, use_tls=False, use_ssl=False):
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.ehlo()
                if use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                smtp.send_message(msg)

    write_otp_log(to_email, otp)
    try:
        try_send(SMTP_HOST, SMTP_PORT, use_tls=SMTP_USE_TLS, use_ssl=SMTP_USE_SSL)
        return {'success': True, 'message': 'OTP sent'}
    except Exception as exc:
        attempts.append(str(exc))

    fallback_matrix = [
        ('smtp.gmail.com', 587, True, False),
        ('smtp.gmail.com', 465, False, True),
    ]

    for host, port, use_tls, use_ssl in fallback_matrix:
        if host == SMTP_HOST and port == SMTP_PORT and use_tls == SMTP_USE_TLS and use_ssl == SMTP_USE_SSL:
            continue
        try:
            try_send(host, port, use_tls=use_tls, use_ssl=use_ssl)
            return {'success': True, 'message': 'OTP sent'}
        except Exception as exc:
            attempts.append(str(exc))

    write_otp_log(to_email, otp)
    return {'success': False, 'message': 'Unable to send OTP by email. Check Gmail app password and SMTP settings.'}

def send_security_alert_email(to_email):
    import threading
    def _run():
        subject = f"{APP_NAME} - Security Alert: Multiple Failed Login Attempts"
        body = [
            'Hello,',
            '',
            'We detected multiple failed login attempts on your account. For your security, login has been temporarily disabled for 15 minutes.',
            '',
            'Please change your password immediately to secure your account.',
            '',
            'Additionally, Two-Factor Authentication (2FA) has been automatically enabled for your account. You will be required to verify via OTP for future logins.',
            '',
            "If this wasn't you, please contact support or update your password right away.",
            '',
            f'{APP_NAME} Team',
        ]

        msg = EmailMessage()
        msg['From'] = f'{MAIL_FROM_NAME} <{MAIL_FROM_EMAIL}>'
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.set_content('\r\n'.join(body))

        def try_send(host, port, use_tls=False, use_ssl=False):
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                    smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=15) as smtp:
                    smtp.ehlo()
                    if use_tls:
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                    smtp.send_message(msg)

        # Log for debugging/development
        write_otp_log(to_email, 'security_alert_2fa_enabled_change_password')
        import sys
        try:
            try_send(SMTP_HOST, SMTP_PORT, use_tls=SMTP_USE_TLS, use_ssl=SMTP_USE_SSL)
            print(f"[SMTP Alert] Security alert email successfully sent to {to_email}", file=sys.stderr)
            return
        except Exception as exc:
            print(f"[SMTP Alert] Failed to send to {to_email} via primary SMTP: {exc}", file=sys.stderr)

        fallback_matrix = [
            ('smtp.gmail.com', 587, True, False),
            ('smtp.gmail.com', 465, False, True),
        ]

        for host, port, use_tls, use_ssl in fallback_matrix:
            if host == SMTP_HOST and port == SMTP_PORT and use_tls == SMTP_USE_TLS and use_ssl == SMTP_USE_SSL:
                continue
            try:
                try_send(host, port, use_tls=use_tls, use_ssl=use_ssl)
                print(f"[SMTP Alert] Security alert email successfully sent to {to_email} via fallback {host}:{port}", file=sys.stderr)
                return
            except Exception as exc:
                print(f"[SMTP Alert] Failed to send to {to_email} via fallback {host}:{port}: {exc}", file=sys.stderr)

    threading.Thread(target=_run, daemon=True).start()

@app.route('/php/<path:filename>', methods=['GET', 'POST'])
def php_shim(filename):
    # map known PHP endpoints to Python handlers
    if filename == 'check_session.php':
        return check_session()
    if filename == 'login.php':
        return login()
    if filename == 'logout.php':
        return logout()
    if filename == 'register.php':
        return register()
    if filename == 'manage_users.php':
        return manage_users()
    if filename == 'settings.php':
        return settings()
    if filename == 'scan.php':
        return ml_scan()
    if filename == 'admin_stats.php':
        return admin_stats()
    if filename == 'model_performance.php':
        return get_model_performance()
    if filename == 'history.php':
        return get_user_history()
    if filename == 'clear_history.php':
        return clear_user_history()
    if filename == 'change_password.php':
        return change_password()
    if filename == 'login_activity.php':
        return get_login_activity()
    if filename == 'account_delete.php':
        return delete_user_account()
    if filename == 'system_logs.php':
        return get_system_logs()
    if filename == 'generate_report.php':
        return generate_report()
    # For other php endpoints, return 501
    return jsonify({'success': False, 'message': 'Not implemented'}), 501

def log_login_activity(user_id, ip_address, user_agent):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO login_activity (user_id, ip_address, user_agent) VALUES (?, ?, ?)',
            (str(user_id), ip_address, user_agent)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass

def get_login_activity():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'message': 'Access denied'}), 401

    user_id = user.get('id')
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'SELECT ip_address, user_agent, login_time FROM login_activity WHERE user_id = ? ORDER BY id DESC LIMIT 50',
            (str(user_id),)
        )
        rows = cur.fetchall()
        activities = []
        for row in rows:
            t = row['login_time']
            if isinstance(t, datetime):
                t_str = t.strftime('%Y-%m-%d %H:%M:%S')
            else:
                t_str = str(t)
            activities.append({
                'ip_address': row['ip_address'],
                'user_agent': row['user_agent'],
                'login_time': t_str
            })
        cur.close()
        conn.close()
        return jsonify({'success': True, 'activities': activities})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

def check_session():
    user = session.get('user')
    if not user:
        return jsonify({'logged_in': False, 'user': None}), 401
    return jsonify({'logged_in': True, 'user': user})

def change_password():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'message': 'Access denied. Please log in.'}), 401

    user_id = user.get('id')
    data = request.get_json(force=True, silent=True) or {}
    current_pw = str(data.get('current_password', ''))
    new_pw = str(data.get('new_password', ''))

    if not current_pw or not new_pw:
        return jsonify({'success': False, 'message': 'All password fields are required.'}), 400

    conn = get_db()
    cur = conn.cursor()

    if user_id == 'admin':
        cur.execute('SELECT id, password FROM users WHERE role = ? OR email = ? LIMIT 1', ('admin', ADMIN_EMAIL))
        db_admin = cur.fetchone()
        if db_admin:
            if not check_password_hash(db_admin['password'], current_pw):
                return jsonify({'success': False, 'message': 'Incorrect current password.'}), 400
            cur.execute('UPDATE users SET password = ? WHERE id = ?', (generate_password_hash(new_pw), db_admin['id']))
            conn.commit()
            return jsonify({'success': True, 'message': 'Admin password changed successfully.'})
        else:
            if current_pw != ADMIN_PASSWORD:
                return jsonify({'success': False, 'message': 'Incorrect current password.'}), 400
            cur.execute('INSERT INTO users (name, email, password, role, status) VALUES (?, ?, ?, ?, ?)', ('Admin', ADMIN_EMAIL, generate_password_hash(new_pw), 'admin', 'approved'))
            conn.commit()
            return jsonify({'success': True, 'message': 'Admin password changed successfully.'})

    cur.execute('SELECT id, password FROM users WHERE id = ? LIMIT 1', (user_id,))
    db_user = cur.fetchone()
    if not db_user:
        return jsonify({'success': False, 'message': 'User account not found.'}), 404

    if not check_password_hash(db_user['password'], current_pw):
        return jsonify({'success': False, 'message': 'Incorrect current password.'}), 400

    cur.execute('UPDATE users SET password = ? WHERE id = ?', (generate_password_hash(new_pw), user_id))
    conn.commit()
    return jsonify({'success': True, 'message': 'Password changed successfully.'})

def login():
    data = request.get_json(force=True, silent=True) or {}
    action = data.get('action', '')
    conn = get_db()
    cur = conn.cursor()

    if action == 'verify_2fa':
        otp_id = data.get('otp_id')
        otp_plain = str(data.get('otp', '')).strip()
        v_email = str(data.get('email', '')).strip()
        v_role = str(data.get('role', '')).strip()

        if not otp_id or not otp_plain or not v_email or not v_role:
            return jsonify({'success': False, 'message': 'Missing fields for 2FA verification'}), 400

        cur.execute(
            'SELECT id, email, role, user_id, otp_hash, expires_at, used FROM login_otps WHERE id = ? AND role = ? AND email = ? LIMIT 1',
            (otp_id, v_role, v_email)
        )
        otp_row = cur.fetchone()
        if not otp_row:
            return jsonify({'success': False, 'message': 'OTP record not found.'}), 401

        if otp_row['used']:
            return jsonify({'success': False, 'message': 'OTP already used.'}), 401

        exp = otp_row['expires_at']
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)
        if exp < datetime.now():
            return jsonify({'success': False, 'message': 'OTP expired.'}), 401

        if not check_password_hash(otp_row['otp_hash'], otp_plain):
            return jsonify({'success': False, 'message': 'Invalid OTP.'}), 401

        cur.execute('UPDATE login_otps SET used = 1 WHERE id = ?', (otp_row['id'],))
        conn.commit()

        if v_role == 'admin':
            session['user'] = {'id': 'admin', 'name': 'Admin', 'email': v_email, 'role': 'admin'}
            log_login_activity('admin', request.headers.get('X-Forwarded-For', request.remote_addr), request.headers.get('User-Agent', ''))
            return jsonify({'success': True, 'message': 'Admin login successful', 'redirect': '../admin/scan.html'})

        cur.execute('SELECT id, name, email FROM users WHERE email = ? LIMIT 1', (v_email,))
        u = cur.fetchone()
        if not u:
            return jsonify({'success': False, 'message': 'User not found.'}), 401

        session['user'] = {'id': u['id'], 'name': u['name'], 'email': u['email'], 'role': 'user'}
        cur.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (u['id'],))
        conn.commit()

        log_login_activity(u['id'], request.headers.get('X-Forwarded-For', request.remote_addr), request.headers.get('User-Agent', ''))
        return jsonify({'success': True, 'message': 'User login successful', 'redirect': '../user/index.html'})

    # calculate session timeout
    session_timeout = SESSION_TIMEOUT

    # normal login
    role = data.get('role')
    email = str(data.get('email', '')).strip()
    password = str(data.get('password', ''))

    if role == 'admin':
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['user'] = {'id': 'admin', 'name': 'Admin', 'email': email, 'role': 'admin'}
            log_login_activity('admin', request.headers.get('X-Forwarded-For', request.remote_addr), request.headers.get('User-Agent', ''))
            return jsonify({'success': True, 'message': 'Admin login successful', 'redirect': '../admin/scan.html'})
        # fallback: try users table
        cur.execute('SELECT id, name, email, password, role, status FROM users WHERE email = ? LIMIT 1', (email,))
        admin = cur.fetchone()
        if not admin:
            return jsonify({'success': False, 'message': 'Invalid admin credentials'}), 401
        if admin['status'] != 'approved' or admin['role'] != 'admin':
            return jsonify({'success': False, 'message': 'No admin access.'}), 403
        if not check_password_hash(admin['password'], password):
            return jsonify({'success': False, 'message': 'Invalid admin credentials'}), 401
        session['user'] = {'id': admin['id'], 'name': admin['name'], 'email': admin['email'], 'role': 'admin'}
        log_login_activity('admin', request.headers.get('X-Forwarded-For', request.remote_addr), request.headers.get('User-Agent', ''))
        return jsonify({'success': True, 'message': 'Admin login successful', 'redirect': '../admin/scan.html'})

    # user login
    cur.execute('SELECT id, name, email, password, role, status FROM users WHERE email = ? LIMIT 1', (email,))
    user = cur.fetchone()
    if not user:
        cur.close()
        conn.close()
        return jsonify({'success': False, 'message': 'User not found'}), 401
    if user['status'] != 'approved':
        cur.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Your account is pending admin approval'}), 403
    if user['role'] != 'user':
        cur.close()
        conn.close()
        return jsonify({'success': False, 'message': 'This account has admin role. Use Admin login.'}), 403

    # Check if user is locked out
    cur.execute('SELECT failed_count, blocked_until FROM auth_attempts WHERE role = ? AND email = ? LIMIT 1', ('user', email))
    attempt_row = cur.fetchone()
    if attempt_row and attempt_row['blocked_until']:
        blocked_until = attempt_row['blocked_until']
        if isinstance(blocked_until, str):
            blocked_until = datetime.fromisoformat(blocked_until)
        if blocked_until > datetime.now():
            remaining_sec = int((blocked_until - datetime.now()).total_seconds())
            remaining_min = (remaining_sec + 59) // 60
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': f'Account locked due to too many failed attempts. Try again in {remaining_min} minutes.'
            }), 403
        else:
            # Lockout expired, clear attempts
            cur.execute('DELETE FROM auth_attempts WHERE role = ? AND email = ?', ('user', email))
            conn.commit()
            attempt_row = None

    if not check_password_hash(user['password'], password):
        failed_count = 1
        if attempt_row:
            failed_count = (attempt_row['failed_count'] or 0) + 1
        
        limit_val = get_admin_setting('login_attempts_limit', '5')
        try:
            limit = int(limit_val)
        except ValueError:
            limit = 5

        if failed_count >= limit:
            blocked_until = datetime.now() + timedelta(minutes=15)
            cur.execute('''
                INSERT INTO auth_attempts (role, email, failed_count, blocked_until, last_failed_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    failed_count = VALUES(failed_count),
                    blocked_until = VALUES(blocked_until),
                    last_failed_at = VALUES(last_failed_at)
            ''', ('user', email, failed_count, blocked_until))
            
            # Automatically enable 2-Factor Authentication (2FA) for this user
            cur.execute('''
                INSERT INTO settings_store (role, owner_key, setting_key, setting_value)
                VALUES (?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
            ''', ('user', email, 'two_factor_user', '1'))
            
            conn.commit()
            
            # Send security alert email asynchronously
            send_security_alert_email(email)
            
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Account locked due to too many failed attempts. Try again in 15 minutes.'
            }), 403
        else:
            cur.execute('''
                INSERT INTO auth_attempts (role, email, failed_count, blocked_until, last_failed_at)
                VALUES (?, ?, ?, NULL, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    failed_count = VALUES(failed_count),
                    blocked_until = VALUES(blocked_until),
                    last_failed_at = VALUES(last_failed_at)
            ''', ('user', email, failed_count))
            conn.commit()
            cur.close()
            conn.close()
            remaining = limit - failed_count
            return jsonify({'success': False, 'message': f'Invalid password. {remaining} attempts remaining.'}), 401

    # Clear login attempts on successful password verification
    cur.execute('DELETE FROM auth_attempts WHERE role = ? AND email = ?', ('user', email))
    conn.commit()

    # Check user-specific 2FA setting
    cur.execute(
        "SELECT setting_value FROM settings_store WHERE role = 'user' AND owner_key = ? AND setting_key = 'two_factor_user' LIMIT 1",
        (email,)
    )
    setting_row = cur.fetchone()
    user2fa = setting_row['setting_value'] if setting_row else '0'

    if user2fa in ('1', 'true'):
        plain_otp = f"{secrets.randbelow(900000) + 100000}"
        otp_hash = generate_password_hash(plain_otp)
        expires_at = datetime.now() + timedelta(seconds=OTP_EXPIRY_SECONDS)

        cur.execute(
            'INSERT INTO login_otps (email, role, user_id, otp_hash, expires_at, used) VALUES (?, ?, ?, ?, ?, 0)',
            (email, 'user', user['id'], otp_hash, expires_at)
        )
        conn.commit()
        otp_id = cur.lastrowid

        email_status = send_otp_email(email, plain_otp, 'login')
        if not email_status.get('success'):
            cur.execute('DELETE FROM login_otps WHERE id = ?', (otp_id,))
            conn.commit()
            return jsonify({'success': False, 'message': email_status.get('message', 'Unable to send 2FA OTP')}), 500

        return jsonify({
            'success': True,
            'two_factor': True,
            'otp_id': otp_id,
            'message': '2FA OTP sent to your email.'
        })

    session['user'] = {'id': user['id'], 'name': user['name'], 'email': user['email'], 'role': 'user'}
    cur.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
    conn.commit()
    log_login_activity(user['id'], request.headers.get('X-Forwarded-For', request.remote_addr), request.headers.get('User-Agent', ''))
    return jsonify({'success': True, 'message': 'User login successful', 'redirect': '../user/index.html'})

def logout():
    session.clear()
    return jsonify({'success': True})

def register():
    data = request.get_json(force=True, silent=True) or {}
    action = (data.get('action', '') or '').strip()
    name = (data.get('name', '') or '').strip()
    email = (data.get('email', '') or '').strip()
    password = data.get('password', '') or ''
    otp = (data.get('otp', '') or '').strip()

    conn = get_db()
    cur = conn.cursor()

    if action in ('request_otp', 'resend_otp', 'register', ''):
        if not name or not email or not password:
            return jsonify({'success': False, 'message': 'Missing fields'}), 400

        cur.execute('SELECT id FROM users WHERE email = ? LIMIT 1', (email,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'Email already registered'}), 400

        generated_otp = f"{secrets.randbelow(900000) + 100000}"
        expires_at = datetime.now() + timedelta(seconds=OTP_EXPIRY_SECONDS)

        cur.execute('UPDATE registration_otps SET used = 1 WHERE email = ? AND used = 0', (email,))
        cur.execute(
            'INSERT INTO registration_otps (email, name, password_hash, otp_hash, expires_at, used) VALUES (?, ?, ?, ?, ?, 0)',
            (email, name, generate_password_hash(password), generate_password_hash(generated_otp), expires_at)
        )
        conn.commit()

        email_status = send_otp_email(email, generated_otp, 'registration')
        if not email_status.get('success'):
            return jsonify({'success': False, 'message': email_status.get('message', 'Unable to send OTP') }), 500

        return jsonify({'success': True, 'message': 'OTP sent to your email. It is valid for 10 minutes.', 'requires_otp': True})

    if action == 'verify_register':
        if not email or not otp:
            return jsonify({'success': False, 'message': 'Email and OTP are required'}), 400

        cur.execute('SELECT id FROM users WHERE email = ? LIMIT 1', (email,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'Email already registered'}), 400

        cur.execute(
            'SELECT id, name, email, password_hash, otp_hash, expires_at, used FROM registration_otps WHERE email = ? ORDER BY id DESC LIMIT 1',
            (email,)
        )
        otp_row = cur.fetchone()
        if not otp_row:
            return jsonify({'success': False, 'message': 'No OTP request found. Please request OTP first.'}), 400
        if int(otp_row.get('used') or 0) == 1:
            return jsonify({'success': False, 'message': 'OTP already used. Please request a new OTP.'}), 400
        expires_at = otp_row.get('expires_at')
        if not expires_at:
            return jsonify({'success': False, 'message': 'OTP expired. Please request a new OTP.'}), 400
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at < datetime.now():
            return jsonify({'success': False, 'message': 'OTP expired. Please request a new OTP.'}), 400
        if not check_password_hash(otp_row['otp_hash'], otp):
            return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

        try:
            cur.execute(
                'INSERT INTO users (name, email, password, role, status, last_login) VALUES (?, ?, ?, ?, ?, ?)',
                (otp_row['name'], otp_row['email'], otp_row['password_hash'], 'user', 'approved', None)
            )
            cur.execute('UPDATE registration_otps SET used = 1 WHERE email = ? AND used = 0', (email,))
            conn.commit()
        except MySQLError as exc:
            conn.rollback()
            if getattr(exc, 'errno', None) == 1062:
                return jsonify({'success': False, 'message': 'Email already registered'}), 400
            raise

        return jsonify({'success': True, 'message': 'Registration successful'})

    return jsonify({'success': False, 'message': 'Invalid action'}), 400

def manage_users():
    # support ?action=list and approve/reject/delete/update_role
    conn = get_db()
    cur = conn.cursor()
    action = request.args.get('action') or request.get_json().get('action') if request.is_json else request.args.get('action')
    if action == 'list':
        cur.execute('SELECT id, name, email, role, status, last_login FROM users')
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify({'success': True, 'users': rows})
    if action == 'approve':
        uid = int(request.args.get('user_id') or request.get_json().get('user_id'))
        role = request.args.get('role') or request.get_json().get('role')
        cur.execute('UPDATE users SET status = ?, role = ? WHERE id = ?', ('approved', role or 'user', uid))
        conn.commit()
        return jsonify({'success': True})
    if action == 'reject':
        uid = int(request.args.get('user_id') or request.get_json().get('user_id'))
        cur.execute('DELETE FROM users WHERE id = ?', (uid,))
        conn.commit()
        return jsonify({'success': True})
    if action == 'delete':
        uid = int(request.args.get('user_id') or request.get_json().get('user_id'))
        cur.execute('DELETE FROM users WHERE id = ?', (uid,))
        conn.commit()
        return jsonify({'success': True})
    if action == 'update_role':
        uid = int(request.args.get('user_id') or request.get_json().get('user_id'))
        role = request.args.get('role') or request.get_json().get('role')
        cur.execute('UPDATE users SET role = ? WHERE id = ?', (role, uid))
        conn.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid action'}), 400

def settings():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    role = user.get('role', 'user')
    owner_key = 'admin' if role == 'admin' else user.get('email')

    data = request.get_json(force=True, silent=True) or {}
    action = data.get('action', '')

    conn = get_db()
    cur = conn.cursor()

    if action == 'get':
        cur.execute(
            "SELECT setting_key, setting_value FROM settings_store WHERE role = ? AND owner_key = ?",
            (role, owner_key)
        )
        rows = {r['setting_key']: r['setting_value'] for r in cur.fetchall()}
        cur.close()
        conn.close()
        return jsonify({'success': True, 'settings': rows, 'role': role})

    elif action == 'save':
        settings_data = data.get('settings', {})
        for k, v in settings_data.items():
            clean_key = "".join([c for c in str(k) if c.isalnum() or c in ('_', '-', '.')])
            if not clean_key:
                continue
            clean_value = '1' if v is True else ('0' if v is False else str(v).strip())
            cur.execute(
                'INSERT INTO settings_store (role, owner_key, setting_key, setting_value) VALUES (?, ?, ?, ?) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)',
                (role, owner_key, clean_key, clean_value)
            )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Settings saved successfully'})

    cur.close()
    conn.close()
    return jsonify({'success': False, 'message': 'Invalid action'}), 400

def get_user_setting(email, key, default='0'):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT setting_value FROM settings_store WHERE role = 'user' AND owner_key = ? AND setting_key = ? LIMIT 1",
            (email, key)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row['setting_value'] if row else default
    except Exception:
        return default

def get_admin_setting(key, default='0'):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT setting_value FROM settings_store WHERE role = 'admin' AND owner_key = 'admin' AND setting_key = ? LIMIT 1",
            (key,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row['setting_value'] if row else default
    except Exception:
        return default

def send_scan_result_email(to_email, url, result_dict):
    import threading
    def _run():
        prediction = result_dict.get('prediction', 'Unknown')
        confidence = result_dict.get('confidence', 'N/A')
        risk_level = result_dict.get('risk_level', 'Low')
        explanation = result_dict.get('explanation', 'The ML scan completed.')
        reasons = result_dict.get('reasons', [])

        subject = f"[URLGuard Scan] Verdict: {prediction} - {url}"
        
        # Color styling
        verdict_color = "#10b981" if prediction == 'Safe' else ("#ef4444" if prediction == 'Malicious' else "#f59e0b")
        bg_verdict = "#e6f4ea" if prediction == 'Safe' else ("#fce8e6" if prediction == 'Malicious' else "#fef3c7")
        
        # Build HTML content
        reasons_list_html = ""
        for r in reasons:
            reasons_list_html += f"<li style='margin-bottom: 8px; color: #4b5563;'>{r}</li>"
        if not reasons_list_html:
            reasons_list_html = "<li style='color: #9ca3af;'>No feature flags triggered.</li>"

        html_content = f"""
        <html>
        <body style="font-family: 'Manrope', 'Segoe UI', Arial, sans-serif; background-color: #f3f4f6; padding: 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
                <div style="background-color: #1e293b; padding: 24px; text-align: center; color: #ffffff;">
                    <h1 style="margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">URLGuard Safety Report</h1>
                    <p style="margin: 4px 0 0 0; font-size: 14px; color: #94a3b8;">Automated Machine Learning Verdict</p>
                </div>
                <div style="padding: 32px;">
                    <div style="margin-bottom: 24px; border-bottom: 1px solid #e5e7eb; padding-bottom: 20px;">
                        <p style="margin: 0 0 8px 0; font-size: 13px; color: #6b7280; text-transform: uppercase; font-weight: 600;">Scanned URL</p>
                        <a href="{url}" style="font-size: 16px; color: #3b82f6; text-decoration: none; word-break: break-all; font-weight: 500;">{url}</a>
                    </div>
                    
                    <div style="background-color: {bg_verdict}; border-radius: 12px; padding: 20px; margin-bottom: 24px; text-align: center;">
                        <span style="display: inline-block; font-size: 13px; text-transform: uppercase; font-weight: 700; color: {verdict_color}; margin-bottom: 4px;">Verdict</span>
                        <h2 style="margin: 0; font-size: 28px; color: {verdict_color}; font-weight: 800;">{prediction}</h2>
                    </div>

                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
                        <tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #f3f4f6; color: #6b7280; font-size: 14px; width: 40%;">Confidence Score</td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #f3f4f6; color: #1f2937; font-size: 14px; font-weight: 600; text-align: right;">{confidence}%</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #f3f4f6; color: #6b7280; font-size: 14px;">Risk Level</td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #f3f4f6; color: #1f2937; font-size: 14px; font-weight: 600; text-align: right;">{risk_level}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #f3f4f6; color: #6b7280; font-size: 14px;">Scan Timestamp</td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #f3f4f6; color: #1f2937; font-size: 14px; font-weight: 600; text-align: right;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
                        </tr>
                    </table>

                    <div style="margin-bottom: 24px;">
                        <h3 style="margin: 0 0 8px 0; font-size: 15px; color: #1f2937; font-weight: 700;">ML Scan Reasoning:</h3>
                        <p style="margin: 0; font-size: 14px; color: #4b5563; line-height: 1.6; background-color: #f9fafb; padding: 16px; border-radius: 8px; border-left: 4px solid #94a3b8;">{explanation}</p>
                    </div>

                    <div>
                        <h3 style="margin: 0 0 8px 0; font-size: 15px; color: #1f2937; font-weight: 700;">Details & Feature Flags:</h3>
                        <ul style="margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.6;">
                            {reasons_list_html}
                        </ul>
                    </div>
                </div>
                <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af;">
                    <p style="margin: 0 0 4px 0;">This email was automatically sent because email notifications are enabled on your account settings.</p>
                    <p style="margin: 0;">&copy; {datetime.now().year} {APP_NAME}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg = EmailMessage()
        msg['From'] = f'{MAIL_FROM_NAME} <{MAIL_FROM_EMAIL}>'
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.set_content(f"Verdict: {prediction}\nURL: {url}\nConfidence: {confidence}%\nRisk Level: {risk_level}\nExplanation: {explanation}")
        msg.add_alternative(html_content, subtype='html')

        def try_send(host, port, use_tls=False, use_ssl=False):
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                    smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=15) as smtp:
                    smtp.ehlo()
                    if use_tls:
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                    smtp.send_message(msg)

        try:
            try_send(SMTP_HOST, SMTP_PORT, use_tls=SMTP_USE_TLS, use_ssl=SMTP_USE_SSL)
        except Exception:
            # Fallback to Gmail default options
            fallback_matrix = [
                ('smtp.gmail.com', 587, True, False),
                ('smtp.gmail.com', 465, False, True),
            ]
            for host, port, use_tls, use_ssl in fallback_matrix:
                if host == SMTP_HOST and port == SMTP_PORT and use_tls == SMTP_USE_TLS and use_ssl == SMTP_USE_SSL:
                    continue
                try:
                    try_send(host, port, use_tls=use_tls, use_ssl=use_ssl)
                    break
                except Exception:
                    pass

    threading.Thread(target=_run, daemon=True).start()

def ml_scan():
    data = request.get_json(force=True, silent=True) or {}
    url = str(data.get('url', '')).strip()
    if not url:
        return jsonify({'success': False, 'message': 'URL is required'}), 400

    user = session.get('user') or {}
    user_id = user.get('id')
    user_role = user.get('role')

    if user_role == 'admin':
        admin_email = user.get('email') or ADMIN_EMAIL
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute('SELECT id FROM users WHERE email = ? LIMIT 1', (admin_email,))
            u = cur.fetchone()
            if u:
                user_id = u['id']
            else:
                user_id = 31
            cur.close()
            conn.close()
        except Exception:
            user_id = 31
    else:
        try:
            user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            user_id = None

    try:
        from predict import scan_url
        result = scan_url(url, user_id=user_id, store=True)
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'message': 'ML model is not trained yet. Run python train.py first.'
        }), 503
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

    # Trigger email notification if enabled
    if user.get('email'):
        email = user.get('email')
        if get_user_setting(email, 'notifications') in ('1', 'true'):
            send_scan_result_email(email, url, result)

    status = 'malicious' if result['prediction'] == 'Malicious' else 'safe'
    signals = [
        {'label': 'Reason', 'value': reason, 'points': 1 if status == 'malicious' else 0}
        for reason in result.get('reasons', [])
    ]
    return jsonify({
        'success': True,
        'status': status,
        'status_label': result['prediction'],
        'pillClass': 'status-malicious' if status == 'malicious' else 'status-safe',
        'prediction': result['prediction'],
        'confidence': result['confidence'],
        'risk_level': result['risk_level'],
        'explanation': result['explanation'],
        'reasons': result['reasons'],
        'features': [
            {'label': key.replace('_', ' ').title(), 'value': str(value)}
            for key, value in result.get('feature_values', {}).items()
        ],
        'signals': signals,
        'score': result['malicious_probability'],
        'url': result['url'],
        'details': result,
    })

def get_system_logs():
    user = session.get('user')
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Query registrations, logins, and scans dynamically
        query = """
        (SELECT created_at AS timestamp, 'User Registration' AS event, email AS user, status AS status FROM users)
        UNION ALL
        (SELECT la.login_time AS timestamp, 'User Login' AS event, COALESCE(u.email, la.user_id) AS user, 'Success' AS status FROM login_activity la LEFT JOIN users u ON la.user_id = CAST(u.id AS CHAR))
        UNION ALL
        (SELECT sh.scan_time AS timestamp, CONCAT('URL Scan: ', sh.url) AS event, COALESCE(u.email, 'Guest') AS user, sh.prediction AS status FROM scan_history sh LEFT JOIN users u ON sh.user_id = u.id)
        ORDER BY timestamp DESC
        LIMIT 200
        """
        cur.execute(query)
        rows = cur.fetchall()
        
        logs = []
        for row in rows:
            t_str = ''
            if row.get('timestamp'):
                if isinstance(row['timestamp'], datetime):
                    t_str = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                else:
                    t_str = str(row['timestamp'])
            
            logs.append({
                'timestamp': t_str,
                'event': row.get('event'),
                'user': row.get('user'),
                'status': row.get('status')
            })
            
        cur.close()
        conn.close()
        return jsonify({'success': True, 'logs': logs})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

def admin_stats():
    # Require admin role to access
    user = session.get('user')
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Ensure scan_history table is created
        cur.execute('''CREATE TABLE IF NOT EXISTS scan_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            url VARCHAR(2048) NOT NULL,
            prediction VARCHAR(20) NOT NULL,
            confidence FLOAT NOT NULL,
            risk_level VARCHAR(20) NOT NULL,
            explanation TEXT NOT NULL,
            scan_time DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
        conn.commit()

        # Get total unique scans count
        cur.execute('SELECT COUNT(DISTINCT url) as total FROM scan_history')
        total_row = cur.fetchone()
        total = total_row['total'] if total_row else 0
        
        # Get count for Safe unique scans
        cur.execute('''
            SELECT COUNT(*) as safe 
            FROM scan_history sh
            INNER JOIN (
                SELECT url, MAX(id) as max_id 
                FROM scan_history 
                GROUP BY url
            ) latest ON sh.id = latest.max_id
            WHERE sh.prediction = 'Safe'
        ''')
        safe_row = cur.fetchone()
        safe = safe_row['safe'] if safe_row else 0
        
        # Get count for Malicious (High risk) unique scans
        cur.execute('''
            SELECT COUNT(*) as malicious 
            FROM scan_history sh
            INNER JOIN (
                SELECT url, MAX(id) as max_id 
                FROM scan_history 
                GROUP BY url
            ) latest ON sh.id = latest.max_id
            WHERE sh.prediction = 'Malicious' AND sh.risk_level = 'High'
        ''')
        malicious_row = cur.fetchone()
        malicious = malicious_row['malicious'] if malicious_row else 0
        
        # Get count for Suspicious (Medium or Low risk Malicious) unique scans
        cur.execute('''
            SELECT COUNT(*) as suspicious 
            FROM scan_history sh
            INNER JOIN (
                SELECT url, MAX(id) as max_id 
                FROM scan_history 
                GROUP BY url
            ) latest ON sh.id = latest.max_id
            WHERE sh.prediction = 'Malicious' AND sh.risk_level != 'High'
        ''')
        suspicious_row = cur.fetchone()
        suspicious = suspicious_row['suspicious'] if suspicious_row else 0
        
        # Fetch 5 most recent scans
        cur.execute('SELECT id, url, prediction, confidence, risk_level, scan_time FROM scan_history ORDER BY scan_time DESC LIMIT 5')
        recent_rows = cur.fetchall()
        
        recent_scans = []
        for row in recent_rows:
            scan_time_str = ''
            if row.get('scan_time'):
                if isinstance(row['scan_time'], datetime):
                    scan_time_str = row['scan_time'].strftime('%Y-%m-%d %H:%M:%S')
                else:
                    scan_time_str = str(row['scan_time'])
            
            recent_scans.append({
                'id': row.get('id'),
                'url': row.get('url'),
                'prediction': row.get('prediction'),
                'confidence': row.get('confidence'),
                'risk_level': row.get('risk_level'),
                'scan_time': scan_time_str
            })
            
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'stats': {
                'total': total,
                'safe': safe,
                'malicious': malicious,
                'suspicious': suspicious
            },
            'recent_scans': recent_scans
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

def get_model_performance():
    user = session.get('user')
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    summary_path = os.path.join(APP_ROOT, 'reports', 'model_training_summary.json')
    if not os.path.exists(summary_path):
        return jsonify({'success': False, 'message': 'Model training summary not found'}), 404

    try:
        import json
        with open(summary_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        best_model_name = data.get('best_model', 'XGBoost')
        best_metrics = None
        for m in data.get('metrics', []):
            if m.get('model') == best_model_name:
                best_metrics = m
                break
        
        if not best_metrics and data.get('metrics'):
            best_metrics = data['metrics'][0]

        mtime = os.path.getmtime(summary_path)
        last_updated = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            'success': True,
            'best_model': best_model_name,
            'metrics': best_metrics,
            'all_models': data.get('metrics', []),
            'last_updated': last_updated
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

def get_user_history():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'message': 'Access denied'}), 401
    
    user_role = user.get('role')
    user_id = user.get('id')
    is_admin = (user_role == 'admin')

    if not is_admin:
        try:
            user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            user_id = None

        if user_id is None:
            return jsonify({'success': True, 'scans': []})

    export_mode = request.args.get('export') == 'true'
    limit = 5000 if export_mode else 50

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Ensure scan_history table is created
        cur.execute('''CREATE TABLE IF NOT EXISTS scan_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            url VARCHAR(2048) NOT NULL,
            prediction VARCHAR(20) NOT NULL,
            confidence FLOAT NOT NULL,
            risk_level VARCHAR(20) NOT NULL,
            explanation TEXT NOT NULL,
            scan_time DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
        conn.commit()

        if is_admin:
            cur.execute(
                f'''SELECT sh.id, sh.user_id, u.name as user_name, u.email as user_email, u.role as user_role, 
                           sh.url, sh.prediction, sh.confidence, sh.risk_level, sh.explanation, sh.scan_time 
                    FROM scan_history sh 
                    LEFT JOIN users u ON sh.user_id = u.id 
                    ORDER BY sh.scan_time DESC LIMIT {limit}'''
            )
        else:
            cur.execute(
                f'SELECT id, url, prediction, confidence, risk_level, explanation, scan_time FROM scan_history WHERE user_id = ? ORDER BY scan_time DESC LIMIT {limit}',
                (user_id,)
            )
        rows = cur.fetchall()

        if export_mode and not is_admin and user.get('email'):
            try:
                user_name = user.get('name') or 'User'
                user_email = user.get('email')
                
                import csv
                import io
                
                csv_output = io.StringIO()
                csv_output.write('\ufeff')
                csv_writer = csv.writer(csv_output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                
                csv_writer.writerow(['Sl. No.', 'URL', 'Result', 'Confidence (%)', 'Risk Level', 'Reason/Explanation', 'Scan Time'])
                
                for index, row in enumerate(rows):
                    conf_str = f"{row.get('confidence'):.1f}%" if row.get('confidence') is not None else 'N/A'
                    scan_time_str = ''
                    if row.get('scan_time'):
                        if isinstance(row['scan_time'], datetime):
                            scan_time_str = row['scan_time'].strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            scan_time_str = str(row['scan_time'])
                            
                    csv_writer.writerow([
                        index + 1,
                        row.get('url', ''),
                        row.get('prediction', ''),
                        conf_str,
                        row.get('risk_level', ''),
                        row.get('explanation', ''),
                        scan_time_str
                    ])
                    
                csv_data = csv_output.getvalue()
                csv_output.close()
                
                subject = f"{APP_NAME} - Your URL Scan History Report"
                body = (
                    f"Hello {user_name},\n\n"
                    f"As requested, please find attached a copy of your URL safety scan history report from {APP_NAME}.\n\n"
                    f"Total URL Scans exported: {len(rows)}\n"
                    f"Export Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"Best regards,\n"
                    f"{APP_NAME} Team"
                )
                
                msg = EmailMessage()
                msg['From'] = f'{MAIL_FROM_NAME} <{MAIL_FROM_EMAIL}>'
                msg['To'] = user_email
                msg['Subject'] = subject
                msg.set_content(body)
                
                filename = f"urlguard_user_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                msg.add_attachment(
                    csv_data.encode('utf-8-sig'),
                    maintype='text',
                    subtype='csv',
                    filename=filename
                )
                
                def try_send(host, port, use_tls=False, use_ssl=False):
                    if use_ssl:
                        with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                            smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                            smtp.send_message(msg)
                    else:
                        with smtplib.SMTP(host, port, timeout=15) as smtp:
                            smtp.ehlo()
                            if use_tls:
                                smtp.starttls()
                                smtp.ehlo()
                            smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                            smtp.send_message(msg)

                try:
                    try_send(SMTP_HOST, SMTP_PORT, use_tls=SMTP_USE_TLS, use_ssl=SMTP_USE_SSL)
                except Exception:
                    try_send('smtp.gmail.com', 587, use_tls=True)
            except Exception:
                pass

        scans = []
        for row in rows:
            scan_time_str = ''
            if row.get('scan_time'):
                if isinstance(row['scan_time'], datetime):
                    scan_time_str = row['scan_time'].strftime('%Y-%m-%d %H:%M:%S')
                else:
                    scan_time_str = str(row['scan_time'])
            
            item = {
                'id': row.get('id'),
                'url': row.get('url'),
                'prediction': row.get('prediction'),
                'confidence': row.get('confidence'),
                'risk_level': row.get('risk_level'),
                'explanation': row.get('explanation'),
                'scan_time': scan_time_str
            }
            
            if is_admin:
                uid = row.get('user_id')
                if uid is None:
                    item['user_id'] = 'Guest'
                    item['user_name'] = 'Guest'
                    item['user_email'] = 'Guest'
                    item['user_role'] = 'Guest'
                else:
                    item['user_id'] = uid
                    item['user_name'] = row.get('user_name') or 'Unknown'
                    item['user_email'] = row.get('user_email') or 'Unknown'
                    item['user_role'] = (row.get('user_role') or 'user').capitalize()
                    
            scans.append(item)
            
        cur.close()
        conn.close()
        return jsonify({'success': True, 'scans': scans})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

def clear_user_history():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'message': 'Access denied'}), 401
    
    user_id = user.get('id')
    try:
        user_id = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        user_id = None

    if user_id is None:
        return jsonify({'success': False, 'message': 'Access denied'}), 401
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('DELETE FROM scan_history WHERE user_id = ?', (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Scan history cleared'})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

def delete_user_account():
    user = session.get('user')
    if not user:
        return jsonify({'success': False, 'message': 'Access denied'}), 401

    user_id = user.get('id')
    email = user.get('email')
    role = user.get('role', 'user')

    try:
        user_id = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        user_id = None

    if user_id is None:
        if user.get('id') == 'admin' or email == ADMIN_EMAIL:
            return jsonify({'success': False, 'message': 'Main admin account cannot be deleted via this endpoint'}), 400
        return jsonify({'success': False, 'message': 'Access denied'}), 401

    if email == ADMIN_EMAIL:
        return jsonify({'success': False, 'message': 'Main admin account cannot be deleted via this endpoint'}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # 1. Delete scan history
        cur.execute('DELETE FROM scan_history WHERE user_id = ?', (user_id,))
        
        # 2. Delete settings
        cur.execute("DELETE FROM settings_store WHERE role = 'user' AND owner_key = ?", (email,))
        
        # 3. Delete login activity
        cur.execute("DELETE FROM login_activity WHERE user_id = ?", (str(user_id),))
        
        # 4. Delete login OTPs
        cur.execute("DELETE FROM login_otps WHERE email = ?", (email,))
        
        # 5. Delete user account
        cur.execute('DELETE FROM users WHERE id = ?', (user_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Clear session
        session.clear()
        
        return jsonify({'success': True, 'message': 'Account deleted'})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

def generate_report():
    user = session.get('user')
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    report_type = request.args.get('type', 'daily')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    recipient_email = request.args.get('email')

    now = datetime.now()
    if report_type == 'daily':
        start_dt = datetime(now.year, now.month, now.day)
        end_dt = now
    elif report_type == 'weekly':
        start_dt = now - timedelta(days=7)
        end_dt = now
    elif report_type == 'monthly':
        start_dt = now - timedelta(days=30)
        end_dt = now
    elif report_type == 'custom':
        if not start_date_str or not end_date_str:
            return jsonify({'success': False, 'message': 'Start and end dates are required for custom range'}), 400
        try:
            start_parts = [int(x) for x in start_date_str.split('-')]
            start_dt = datetime(start_parts[0], start_parts[1], start_parts[2], 0, 0, 0)
            
            end_parts = [int(x) for x in end_date_str.split('-')]
            end_dt = datetime(end_parts[0], end_parts[1], end_parts[2], 23, 59, 59)
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
    else:
        return jsonify({'success': False, 'message': 'Invalid report type'}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(
            '''SELECT sh.user_id, u.name as user_name, u.email as user_email, u.role as user_role, 
                      sh.url, sh.prediction, sh.confidence, sh.risk_level, sh.explanation, sh.scan_time 
               FROM scan_history sh 
               LEFT JOIN users u ON sh.user_id = u.id 
               WHERE sh.scan_time BETWEEN ? AND ?
               ORDER BY sh.scan_time DESC''',
            (start_dt, end_dt)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        import csv
        import io
        from flask import Response
        
        output = io.StringIO()
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        writer.writerow(['User ID', 'Name', 'Role', 'Email', 'URL', 'Result', 'Confidence', 'Risk Level', 'Explanation', 'Scan Time'])
        
        for row in rows:
            uid = row.get('user_id')
            if uid is None:
                uid_str = 'Guest'
                name_str = 'Guest'
                email_str = 'Guest'
                role_str = 'Guest'
            else:
                uid_str = str(uid)
                name_str = row.get('user_name') or 'Unknown'
                email_str = row.get('user_email') or 'Unknown'
                role_str = (row.get('user_role') or 'user').capitalize()
                
            conf_str = f"{row.get('confidence'):.1f}%" if row.get('confidence') is not None else 'N/A'
            
            scan_time_str = ''
            if row.get('scan_time'):
                if isinstance(row['scan_time'], datetime):
                    scan_time_str = row['scan_time'].strftime('%Y-%m-%d %H:%M:%S')
                else:
                    scan_time_str = str(row['scan_time'])
                    
            writer.writerow([
                uid_str,
                name_str,
                role_str,
                email_str,
                row.get('url', ''),
                row.get('prediction', ''),
                conf_str,
                row.get('risk_level', ''),
                row.get('explanation', ''),
                scan_time_str
            ])
            
        csv_data = output.getvalue()
        output.close()
        
        filename = f"urlguard_report_{report_type}_{now.strftime('%Y%m%d_%H%M%S')}.csv"
        if report_type == 'custom':
            filename = f"urlguard_report_custom_{start_date_str}_to_{end_date_str}.csv"

        if recipient_email:
            recipient_email = recipient_email.strip()
            if recipient_email:
                try:
                    subject = f"{APP_NAME} - {report_type.capitalize()} Security Report"
                    body = (
                        f"Hello,\n\n"
                        f"Please find attached the {report_type} safety scan report generated on {now.strftime('%Y-%m-%d %H:%M:%S')}.\n\n"
                        f"Report Details:\n"
                        f"- Type: {report_type.capitalize()}\n"
                    )
                    if report_type == 'custom':
                        body += f"- Date Range: {start_date_str} to {end_date_str}\n"
                    body += f"\nBest regards,\n{APP_NAME} Team"

                    msg = EmailMessage()
                    msg['From'] = f'{MAIL_FROM_NAME} <{MAIL_FROM_EMAIL}>'
                    msg['To'] = recipient_email
                    msg['Subject'] = subject
                    msg.set_content(body)

                    msg.add_attachment(
                        csv_data.encode('utf-8-sig'),
                        maintype='text',
                        subtype='csv',
                        filename=filename
                    )

                    def try_send(host, port, use_tls=False, use_ssl=False):
                        if use_ssl:
                            with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                                smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                                smtp.send_message(msg)
                        else:
                            with smtplib.SMTP(host, port, timeout=15) as smtp:
                                smtp.ehlo()
                                if use_tls:
                                    smtp.starttls()
                                    smtp.ehlo()
                                smtp.login(MAIL_FROM_EMAIL, MAIL_APP_PASSWORD)
                                smtp.send_message(msg)

                    try:
                        try_send(SMTP_HOST, SMTP_PORT, use_tls=SMTP_USE_TLS, use_ssl=SMTP_USE_SSL)
                    except Exception:
                        try_send('smtp.gmail.com', 587, use_tls=True)
                except Exception:
                    pass
            
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500

@app.after_request
def add_header(response):
    if (request.path.endswith('.html') or 
        request.path == '/' or 
        not request.path or 
        request.path.startswith('/php/')):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def static_proxy(path):
    # serve files from project root
    target = os.path.join(APP_ROOT, path)
    if path == '' or path.endswith('/'):
        # redirect to user index like original index.php
        return redirect('/user/index.html')
    full = os.path.join(APP_ROOT, path)
    if os.path.exists(full) and os.path.isfile(full):
        return send_from_directory(APP_ROOT, path)
    # try user-facing path
    return send_from_directory(APP_ROOT, 'auth.html') if path == 'auth.html' else ('Not Found', 404)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=False, use_reloader=False)
