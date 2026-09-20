import os
import sys
import time
import io
import json
import sqlite3
import shutil
import zipfile
import subprocess
import signal
try:
    import psutil
except ImportError:
    class DummyPsutil:
        @staticmethod
        def pid_exists(pid):
            if not pid or pid <= 0:
                return False
            try:
                os.kill(pid, 0)
                return True
            except Exception:
                return False

        class Process:
            def __init__(self, pid):
                self.pid = pid
            def kill(self):
                try:
                    os.kill(self.pid, signal.SIGKILL)
                except Exception:
                    pass
            def terminate(self):
                try:
                    os.kill(self.pid, signal.SIGTERM)
                except Exception:
                    pass
            def create_time(self):
                return time.time()

    psutil = DummyPsutil()
import ast
import re
import threading
import urllib.request
from datetime import datetime, timedelta, date
from functools import wraps
import hashlib
import hmac
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

def safe_generate_password_hash(password: str) -> str:
    """Generate a universally supported, secure PBKDF2-SHA256 password hash."""
    if not password:
        return ""
    try:
        return generate_password_hash(password, method='pbkdf2:sha256')
    except Exception:
        salt = secrets.token_hex(16)
        iterations = 260000
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
        return f"pbkdf2:sha256:{iterations}${salt}${key.hex()}"

def safe_check_password_hash(pwhash: str, password: str) -> bool:
    """Safely verify passwords against various hash algorithms (PBKDF2, scrypt, SHA-256, etc.)
    without crashing on OpenSSL digital envelope routines or memory limits."""
    if not pwhash or not password:
        return False
    
    # 1. Custom scrypt handler with safe maxmem to handle scrypt hashes without ValueError
    if isinstance(pwhash, str) and pwhash.startswith('scrypt:'):
        try:
            parts = pwhash.split('$')
            if len(parts) == 3:
                params, salt, expected_hash = parts
                sub = params.split(':')
                n = int(sub[1]) if len(sub) > 1 else 32768
                r = int(sub[2]) if len(sub) > 2 else 8
                p = int(sub[3]) if len(sub) > 3 else 1
                computed = hashlib.scrypt(
                    password.encode('utf-8'),
                    salt=salt.encode('utf-8'),
                    n=n, r=r, p=p,
                    maxmem=128 * 1024 * 1024
                ).hex()
                if hmac.compare_digest(computed.lower(), expected_hash.lower()):
                    return True
        except Exception:
            pass

    # 2. Standard Werkzeug check
    try:
        if check_password_hash(pwhash, password):
            return True
    except Exception:
        pass

    # 3. Custom PBKDF2 check fallback
    if isinstance(pwhash, str) and pwhash.startswith('pbkdf2:'):
        try:
            parts = pwhash.split('$')
            if len(parts) == 3:
                method_info, salt, expected_hash = parts
                sub = method_info.split(':')
                hash_name = sub[1] if len(sub) > 1 else 'sha256'
                iterations = int(sub[2]) if len(sub) > 2 else 260000
                computed = hashlib.pbkdf2_hmac(
                    hash_name,
                    password.encode('utf-8'),
                    salt.encode('utf-8'),
                    iterations
                ).hex()
                if hmac.compare_digest(computed.lower(), expected_hash.lower()):
                    return True
        except Exception:
            pass

    # 4. Direct plain text fallback (for test/legacy support)
    try:
        if hmac.compare_digest(pwhash, password):
            return True
    except Exception:
        pass

    return False

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_file, abort, Response, g
)

# Initialize Flask application
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'hostx_vip_white_super_secret_key_2026_secure')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Setup persistent storage paths if /data (Render persistent disk) is available
if os.path.exists('/data'):
    print("[*] Persistent /data directory detected. Setting up persistent storage for SQLite and user uploads...")
    
    # 1. Database Persistence
    persistent_db_path = '/data/hostx.db'
    if not os.path.exists(persistent_db_path):
        try:
            os.makedirs('/data', exist_ok=True)
            original_db = os.path.join(BASE_DIR, 'database', 'hostx.db')
            if os.path.exists(original_db):
                shutil.copy2(original_db, persistent_db_path)
                print(f"[*] Preserved seed database to: {persistent_db_path}")
        except Exception as e:
            print(f"Error copying SQLite database to /data: {e}")
    DB_PATH = persistent_db_path
    
    # 2. Uploads and Server Files Persistence
    PERSISTENT_SERVERS = '/data/servers'
    PERSISTENT_UPLOADS = '/data/uploads'
    PERSISTENT_AVATARS = '/data/avatars'
    PERSISTENT_BRANDING = '/data/branding'
    
    os.makedirs(PERSISTENT_SERVERS, exist_ok=True)
    os.makedirs(PERSISTENT_UPLOADS, exist_ok=True)
    os.makedirs(PERSISTENT_AVATARS, exist_ok=True)
    os.makedirs(PERSISTENT_BRANDING, exist_ok=True)
    
    # Symlink servers directory
    original_servers = os.path.join(BASE_DIR, 'servers')
    if os.path.exists(original_servers) and not os.path.islink(original_servers):
        try:
            for item in os.listdir(original_servers):
                s_path = os.path.join(original_servers, item)
                d_path = os.path.join(PERSISTENT_SERVERS, item)
                if os.path.isdir(s_path):
                    if os.path.exists(d_path):
                        shutil.rmtree(d_path)
                    shutil.copytree(s_path, d_path)
                else:
                    shutil.copy2(s_path, d_path)
            shutil.rmtree(original_servers)
            os.symlink(PERSISTENT_SERVERS, original_servers)
            print("[*] Symlinked /servers to persistent storage")
        except Exception as e:
            print(f"Error symlinking servers: {e}")
    elif not os.path.exists(original_servers):
        try:
            os.symlink(PERSISTENT_SERVERS, original_servers)
        except Exception as e:
            print(f"Error symlinking servers: {e}")
            
    SERVERS_DIR = original_servers

    # Symlink uploads directory
    original_uploads = os.path.join(BASE_DIR, 'uploads')
    if os.path.exists(original_uploads) and not os.path.islink(original_uploads):
        try:
            for item in os.listdir(original_uploads):
                s_path = os.path.join(original_uploads, item)
                d_path = os.path.join(PERSISTENT_UPLOADS, item)
                if os.path.isdir(s_path):
                    if os.path.exists(d_path):
                        shutil.rmtree(d_path)
                    shutil.copytree(s_path, d_path)
                else:
                    shutil.copy2(s_path, d_path)
            shutil.rmtree(original_uploads)
            os.symlink(PERSISTENT_UPLOADS, original_uploads)
            print("[*] Symlinked /uploads to persistent storage")
        except Exception as e:
            print(f"Error symlinking uploads: {e}")
    elif not os.path.exists(original_uploads):
        try:
            os.symlink(PERSISTENT_UPLOADS, original_uploads)
        except Exception as e:
            print(f"Error symlinking uploads: {e}")
            
    UPLOADS_DIR = original_uploads

    # Symlink avatars directory
    original_avatars = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
    if os.path.exists(original_avatars) and not os.path.islink(original_avatars):
        try:
            for item in os.listdir(original_avatars):
                s_path = os.path.join(original_avatars, item)
                d_path = os.path.join(PERSISTENT_AVATARS, item)
                if os.path.isdir(s_path):
                    if os.path.exists(d_path):
                        shutil.rmtree(d_path)
                    shutil.copytree(s_path, d_path)
                else:
                    shutil.copy2(s_path, d_path)
            shutil.rmtree(original_avatars)
            os.symlink(PERSISTENT_AVATARS, original_avatars)
            print("[*] Symlinked avatars to persistent storage")
        except Exception as e:
            print(f"Error symlinking avatars: {e}")
    elif not os.path.exists(original_avatars):
        try:
            os.makedirs(os.path.dirname(original_avatars), exist_ok=True)
            os.symlink(PERSISTENT_AVATARS, original_avatars)
        except Exception as e:
            print(f"Error symlinking avatars: {e}")
            
    AVATARS_DIR = original_avatars

    # Symlink branding directory
    original_branding = os.path.join(BASE_DIR, 'static', 'uploads', 'branding')
    if os.path.exists(original_branding) and not os.path.islink(original_branding):
        try:
            for item in os.listdir(original_branding):
                s_path = os.path.join(original_branding, item)
                d_path = os.path.join(PERSISTENT_BRANDING, item)
                if os.path.isdir(s_path):
                    if os.path.exists(d_path):
                        shutil.rmtree(d_path)
                    shutil.copytree(s_path, d_path)
                else:
                    shutil.copy2(s_path, d_path)
            shutil.rmtree(original_branding)
            os.symlink(PERSISTENT_BRANDING, original_branding)
            print("[*] Symlinked branding to persistent storage")
        except Exception as e:
            print(f"Error symlinking branding: {e}")
    elif not os.path.exists(original_branding):
        try:
            os.makedirs(os.path.dirname(original_branding), exist_ok=True)
            os.symlink(PERSISTENT_BRANDING, original_branding)
        except Exception as e:
            print(f"Error symlinking branding: {e}")
            
    BRANDING_DIR = original_branding

else:
    DB_PATH = os.path.join(BASE_DIR, 'database', 'hostx.db')
    SERVERS_DIR = os.path.join(BASE_DIR, 'servers')
    UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
    AVATARS_DIR = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
    BRANDING_DIR = os.path.join(BASE_DIR, 'static', 'uploads', 'branding')
    
    os.makedirs(os.path.join(BASE_DIR, 'database'), exist_ok=True)
    os.makedirs(SERVERS_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(AVATARS_DIR, exist_ok=True)
    os.makedirs(BRANDING_DIR, exist_ok=True)

# In-memory dictionary to track running subprocesses: {server_id: subprocess.Popen}
RUNNING_PROCESSES = {}
SERVER_START_TIMES = {}

# Database connection helper
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        coins INTEGER DEFAULT 50,
        role TEXT DEFAULT 'user',
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_daily_claim TIMESTAMP,
        first_time_offer_used INTEGER DEFAULT 0,
        bio TEXT DEFAULT '',
        avatar_url TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS servers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        python_version TEXT DEFAULT 'Python 3.10',
        entry_file TEXT DEFAULT 'main.py',
        status TEXT DEFAULT 'stopped',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        pid INTEGER DEFAULT 0,
        port INTEGER DEFAULT 0,
        uptime_seconds INTEGER DEFAULT 0,
        auto_restart INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS packages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        days INTEGER NOT NULL,
        coins INTEGER NOT NULL,
        is_first_time_offer INTEGER DEFAULT 0,
        description TEXT,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS coin_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        balance_after INTEGER NOT NULL,
        description TEXT NOT NULL,
        transaction_type TEXT DEFAULT 'credit',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS server_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        level TEXT DEFAULT 'INFO',
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS admin_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        admin_username TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT DEFAULT 'Notification',
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        type TEXT DEFAULT 'update',
        is_active INTEGER DEFAULT 1,
        pinned INTEGER DEFAULT 0,
        created_by TEXT DEFAULT 'Administrator',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS broadcast_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        admin_username TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        category TEXT DEFAULT 'announcement',
        target_type TEXT NOT NULL,
        target_user_id INTEGER,
        target_username TEXT,
        recipients_count INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # Ensure is_admin, is_super_admin, admin_permissions, and avatar_url columns exist on users table
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_super_admin INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN admin_permissions TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    # Seed default packages if empty
    cursor.execute("SELECT COUNT(*) FROM packages")
    if cursor.fetchone()[0] == 0:
        default_packages = [
            ('First Time Offer', 5, 10, 1, 'Exclusive 5-day trial package for new creators', 1),
            ('Standard 7 Days', 7, 20, 0, 'Standard 1-week hosting package for testing & bots', 1),
            ('Standard 15 Days', 15, 30, 0, 'Popular 2-week continuous hosting package', 1),
            ('Standard 30 Days', 30, 60, 0, 'Full month hosting with priority resources', 1),
            ('Standard 60 Days', 60, 100, 0, '2 months extended hosting with discount', 1),
            ('Standard 90 Days', 90, 150, 0, 'Quarterly enterprise hosting for permanent bots', 1)
        ]
        cursor.executemany(
            "INSERT INTO packages (name, days, coins, is_first_time_offer, description, active) VALUES (?, ?, ?, ?, ?, ?)",
            default_packages
        )

    # Seed default settings
    default_settings = {
        'maintenance_mode': '0',
        'maintenance_message': 'New Update — Platform is currently undergoing scheduled platform upgrades. We will be back online shortly!',
        'default_starting_coins': '50',
        'daily_reward_coins': '10',
        'site_title': 'HostX VIP',
        'site_name': 'HostX',
        'vip_site_name': 'HostX VIP',
        'self_ping_enabled': '1',
        'self_ping_interval': '5'
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Seed default Announcement if table is empty
    cursor.execute("SELECT COUNT(*) FROM announcements")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO announcements (title, content, type, is_active, pinned, created_by)
            VALUES (?, ?, ?, 1, 1, 'Platform Admin')
        ''', (
            '🚀 System Notice: 24/7 Hosting Engine & Dynamic Coin Controls Active',
            'Welcome to the upgraded platform! We have launched dynamic signup bonuses, instant transaction notifications, full account data isolation, and admin storage tools.',
            'update'
        ))

    # Seed default Super Admin account if no admin exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE role IN ('admin', 'super_admin') OR is_admin = 1")
    if cursor.fetchone()[0] == 0:
        admin_email = os.environ.get('ADMIN_EMAIL', 'adminrifat')
        admin_pass = os.environ.get('ADMIN_PASSWORD', '123456789')
        admin_hash = safe_generate_password_hash(admin_pass)
        cursor.execute('''
            INSERT INTO users (full_name, username, email, password_hash, coins, role, is_admin, is_super_admin, admin_permissions, status)
            VALUES (?, ?, ?, ?, ?, 'super_admin', 1, 1, 'manage_users,manage_coins,manage_files,manage_settings,manage_announcements,manage_broadcasts,view_logs', 'active')
        ''', ('HostX Super Administrator', 'admin', admin_email, admin_hash, 1000))
        print(f"[*] Default Super Admin user initialized: {admin_email}")

    # Flag primary Super Admin accounts and sync role / is_admin / is_super_admin
    primary_super_admins = ['admin@hostx.io', 'admin@hostx.vip', 'yeasingahmmed0011@gmail.com', 'admin']
    for p_email in primary_super_admins:
        cursor.execute("""
            UPDATE users 
            SET role = 'super_admin', is_admin = 1, is_super_admin = 1,
                admin_permissions = 'manage_users,manage_coins,manage_files,manage_settings,manage_announcements,manage_broadcasts,view_logs'
            WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)
        """, (p_email, p_email))

    cursor.execute("UPDATE users SET is_admin = 1 WHERE role IN ('admin', 'super_admin')")
    cursor.execute("UPDATE users SET is_super_admin = 1 WHERE role = 'super_admin'")

    conn.commit()
    conn.close()

init_db()

# Python Self-Ping Engine
def run_self_ping_worker():
    import requests
    print("[*] Python Self-Ping Engine started in background thread.", flush=True)
    # Wait for Flask to boot up first
    time.sleep(15)
    while True:
        enabled = False
        interval_mins = 5
        detected_url = ''
        manual_url = ''
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            row_enabled = cursor.execute("SELECT value FROM settings WHERE key = ?", ('self_ping_enabled',)).fetchone()
            row_interval = cursor.execute("SELECT value FROM settings WHERE key = ?", ('self_ping_interval',)).fetchone()
            row_detected = cursor.execute("SELECT value FROM settings WHERE key = ?", ('detected_site_url',)).fetchone()
            row_manual = cursor.execute("SELECT value FROM settings WHERE key = ?", ('manual_ping_url',)).fetchone()
            conn.close()
            if row_enabled and row_enabled['value'] == '1':
                enabled = True
            if row_interval:
                try:
                    interval_mins = max(1, int(row_interval['value']))
                except Exception:
                    interval_mins = 5
            if row_detected and row_detected['value']:
                detected_url = row_detected['value'].strip()
            if row_manual and row_manual['value']:
                manual_url = row_manual['value'].strip()
        except Exception as e:
            print(f"[Self-Ping Engine DB Error]: {e}", flush=True)

        if enabled:
            urls_to_ping = []
            if manual_url:
                urls_to_ping.append(manual_url)
            if detected_url and detected_url not in urls_to_ping:
                urls_to_ping.append(detected_url)
            if not urls_to_ping:
                urls_to_ping.append("http://127.0.0.1:3000/")

            for u in urls_to_ping:
                try:
                    clean_u = u.rstrip('/')
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (HostX Self-Ping Bot)'
                    }
                    resp = requests.get(clean_u + "/", headers=headers, timeout=15)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Self-Ping Engine] SUCCESS - Pinged {clean_u}/ Status: {resp.status_code}", flush=True)
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Self-Ping Engine] FAILED - Could not ping {u}: {e}", flush=True)
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Self-Ping Engine] Standby - Self-Ping is currently disabled.", flush=True)

        time.sleep(interval_mins * 60)

ping_thread = threading.Thread(target=run_self_ping_worker, daemon=True)
ping_thread.start()

# Helper utilities
def get_setting(key, default=None):
    try:
        db = get_db()
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row and row['value'] is not None else default
    except Exception as e:
        print(f"Error fetching setting {key}: {e}")
        return default

def set_setting(key, value):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    db.commit()

def log_admin_action(action, target, details=''):
    admin_id = session.get('user_id')
    admin_username = session.get('username', 'System')
    db = get_db()
    db.execute(
        "INSERT INTO admin_audit_logs (admin_id, admin_username, action, target, details) VALUES (?, ?, ?, ?, ?)",
        (admin_id, admin_username, action, target, details)
    )
    db.commit()

def create_user_notification(user_id, title, message):
    try:
        db = get_db()
        db.execute(
            "INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
            (user_id, title, message)
        )
        db.commit()
    except Exception as e:
        print(f"Error creating notification: {e}")

def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user and user['status'] != 'active':
        session.clear()
        return None
    return user

def is_user_super_admin(user):
    if not user:
        return False
    role = user['role'] if ('role' in user.keys() and user['role']) else None
    is_super = user['is_super_admin'] if ('is_super_admin' in user.keys() and user['is_super_admin'] is not None) else 0
    email = (user['email'] if ('email' in user.keys() and user['email']) else '').lower().strip()
    username = (user['username'] if ('username' in user.keys() and user['username']) else '').lower().strip()
    
    if role == 'super_admin' or str(is_super) in ('1', 'true', 'True'):
        return True
        
    primary_super_admins = ['gmail', 'gmail', 'gmail', 'admin']
    if email in primary_super_admins or username in primary_super_admins:
        return True
        
    return False

def is_user_admin(user):
    if not user:
        return False
    if is_user_super_admin(user):
        return True
    role = user['role'] if ('role' in user.keys() and user['role']) else None
    is_admin_val = user['is_admin'] if ('is_admin' in user.keys() and user['is_admin'] is not None) else 0
    if role in ('admin', 'super_admin') or str(is_admin_val) in ('1', 'true', 'True'):
        return True
    return False

def has_admin_permission(user, permission_name):
    if not user or not is_user_admin(user):
        return False
    if is_user_super_admin(user):
        return True
    perms_str = user['admin_permissions'] if ('admin_permissions' in user.keys() and user['admin_permissions']) else ''
    if not perms_str:
        return True
    perms_list = [p.strip() for p in perms_str.split(',') if p.strip()]
    return permission_name in perms_list or 'all' in perms_list

# Context processor for templates
@app.context_processor
def inject_global_vars():
    user = get_current_user()
    user_is_admin = is_user_admin(user)
    user_is_super = is_user_super_admin(user)
    first_name = ""
    if user:
        raw_name = user['full_name'] if ('full_name' in user.keys() and user['full_name']) else ''
        if raw_name and str(raw_name).strip():
            first_name = str(raw_name).strip().split(' ')[0]
        elif user['username']:
            first_name = str(user['username'])
        elif user['email']:
            first_name = str(user['email']).split('@')[0]

    site_name = get_setting('site_name', 'HostX')
    if not site_name or not str(site_name).strip():
        site_name = 'HostX'
    else:
        site_name = str(site_name).strip()

    vip_site_name = get_setting('vip_site_name', 'HostX VIP')
    if not vip_site_name or not str(vip_site_name).strip():
        vip_site_name = 'HostX VIP'
    else:
        vip_site_name = str(vip_site_name).strip()

    site_logo_url = get_setting('site_logo_url', '/static/img/logo.svg')
    if not site_logo_url or not str(site_logo_url).strip():
        site_logo_url = '/static/img/logo.svg'
    else:
        site_logo_url = str(site_logo_url).strip()

    maintenance_mode = get_setting('maintenance_mode', '0') == '1'
    maintenance_msg = get_setting('maintenance_message', '')
    is_impersonating = session.get('is_impersonating', False)
    real_admin_username = session.get('real_admin_username', None)
    return dict(
        current_user=user,
        is_admin=user_is_admin,
        is_super_admin=user_is_super,
        has_admin_permission=has_admin_permission,
        user_first_name=first_name,
        site_name=site_name,
        vip_site_name=vip_site_name,
        site_logo_url=site_logo_url,
        maintenance_mode=maintenance_mode,
        maintenance_message=maintenance_msg,
        is_impersonating=is_impersonating,
        real_admin_username=real_admin_username,
        now=datetime.utcnow()
    )

@app.template_filter('first_word')
def first_word_filter(val):
    if not val:
        return ''
    parts = str(val).strip().split(' ')
    return parts[0] if parts else ''

@app.template_filter('format_date')
def format_date_filter(val):
    if not val:
        return ''
    if isinstance(val, (datetime, date)):
        return val.strftime('%Y-%m-%d')
    return str(val)[:10]

@app.template_filter('format_datetime')
def format_datetime_filter(val):
    if not val:
        return ''
    if isinstance(val, (datetime, date)):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    return str(val).split('.')[0]

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'warning')
            return redirect(url_for('signin', next=request.url))
        user = get_current_user()
        if not user:
            flash('Your account has been disabled or session expired.', 'danger')
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access the admin panel.', 'warning')
            return redirect(url_for('signin', next=request.url))
        user = get_current_user()
        if not user or not is_user_admin(user):
            flash('Access Denied: Admin rights required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_permission_required(permission_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please sign in to access the admin panel.', 'warning')
                return redirect(url_for('signin', next=request.url))
            user = get_current_user()
            if not user or not is_user_admin(user):
                flash('Access Denied: Admin rights required.', 'danger')
                return redirect(url_for('dashboard'))
            if not has_admin_permission(user, permission_name):
                flash('Access Denied: You do not have permission to manage this section.', 'warning')
                return redirect(url_for('admin_dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.before_request
def check_maintenance_and_auth():
    # Dynamic URL Auto-Detection
    try:
        url_root = request.url_root.rstrip('/')
        if url_root and "127.0.0.1" not in url_root and "localhost" not in url_root:
            current_detected = get_setting('detected_site_url', '')
            if current_detected != url_root:
                set_setting('detected_site_url', url_root)
    except Exception:
        pass

    # Allow health check, static files, signin, admin login, and errors always
    allowed_endpoints = ['health', 'static', 'signin', 'signout', 'admin_dashboard', 'stop_impersonating']
    if request.endpoint in allowed_endpoints:
        return
    
    # Check maintenance mode
    maintenance = get_setting('maintenance_mode', '0') == '1'
    if maintenance:
        user = get_current_user()
        is_admin = is_user_admin(user)
        # If user is not admin and trying to access anything other than home or maintenance allowed
        if not is_admin and request.endpoint not in ['home', 'signin', 'signout', 'health']:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Platform is under maintenance', 'maintenance': True}), 503
            return render_template('home.html', maintenance_active=True)

@app.route('/health')
@app.route('/api/health')
def health_check():
    return jsonify({'status': 'ok', 'app': 'HostX VIP White', 'time': datetime.utcnow().isoformat()})

# Helper: safe user server directory
def get_server_dir(user_id, server_id):
    path = os.path.join(SERVERS_DIR, str(user_id), str(server_id))
    os.makedirs(path, exist_ok=True)
    return path

def check_server_ownership(server_id, user_id=None):
    if user_id is None:
        user_id = session.get('user_id')
    db = get_db()
    server = db.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    if not server:
        return None
    curr_user = get_current_user()
    if curr_user and curr_user['role'] == 'admin':
        return server
    if server['user_id'] != user_id:
        return None
    return server

# Default starter Python code for new servers
DEFAULT_MAIN_PY = '''"""
HostX VIP White - Python Server Starter
Created automatically for your project.
"""
import time
import datetime
import os
import sys

def main():
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Starting Python application on HostX VIP White...")
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Python Version: {sys.version.split()[0]}")
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Working Directory: {os.getcwd()}")
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] 24/7 Hosting active. Ready to run bots, web scrapers, automation, or scripts!")
    
    count = 0
    while True:
        count += 1
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{now_str}] [INFO] HostX Heartbeat #{count} - Service running smoothly.")
        time.sleep(10)

if __name__ == '__main__':
    main()
'''

DEFAULT_REQUIREMENTS_TXT = '''requests>=2.31.0
colorama>=0.4.6
'''

# Standard Library Modules to exclude from package requirements check
STDLIB_MODULES = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
    'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
    'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
    'contextlib', 'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
    'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
    'dis', 'distutils', 'doctest', 'dummy_threading', 'email', 'encodings', 'enum',
    'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'fractions',
    'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib',
    'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr',
    'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword',
    'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal',
    'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib', 'msvcrt', 'multiprocessing',
    'netrc', 'nis', 'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev',
    'parser', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil', 'platform',
    'plistlib', 'poplib', 'posix', 'posixpath', 'pprint', 'profile', 'pstats', 'pty',
    'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're',
    'readline', 'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 'secrets',
    'select', 'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtpd',
    'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3', 'ssl', 'stat',
    'statistics', 'string', 'stringprep', 'struct', 'subprocess', 'sunau', 'symbol',
    'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile', 'telnetlib',
    'tempfile', 'termios', 'test', 'textwrap', 'threading', 'time', 'timeit', 'tkinter',
    'token', 'tokenize', 'tomllib', 'trace', 'traceback', 'tracemalloc', 'tty', 'turtle',
    'turtledemo', 'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid',
    'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound', 'wsgiref',
    'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib', 'zoneinfo'
}

# Mapping of Python code import statements to official PyPI packages and recommended versions
IMPORT_TO_PACKAGE_MAP = {
    'telebot': {'pkg': 'pyTelegramBotAPI', 'version': '4.26.0'},
    'telegram': {'pkg': 'python-telegram-bot', 'version': '21.4'},
    'aiogram': {'pkg': 'aiogram', 'version': '3.13.1'},
    'discord': {'pkg': 'discord.py', 'version': '2.4.0'},
    'PIL': {'pkg': 'Pillow', 'version': '10.4.0'},
    'pillow': {'pkg': 'Pillow', 'version': '10.4.0'},
    'bs4': {'pkg': 'beautifulsoup4', 'version': '4.12.3'},
    'yaml': {'pkg': 'PyYAML', 'version': '6.0.2'},
    'dotenv': {'pkg': 'python-dotenv', 'version': '1.0.1'},
    'dateutil': {'pkg': 'python-dateutil', 'version': '2.9.0.post0'},
    'cv2': {'pkg': 'opencv-python-headless', 'version': '4.10.0.84'},
    'jwt': {'pkg': 'PyJWT', 'version': '2.9.0'},
    'sklearn': {'pkg': 'scikit-learn', 'version': '1.5.1'},
    'flask_cors': {'pkg': 'flask-cors', 'version': '4.0.1'},
    'fitz': {'pkg': 'PyMuPDF', 'version': '1.24.9'},
    'googleapiclient': {'pkg': 'google-api-python-client', 'version': '2.142.0'},
    'psycopg2': {'pkg': 'psycopg2-binary', 'version': '2.9.9'},
    'mysql': {'pkg': 'mysql-connector-python', 'version': '9.0.0'},
    'pymysql': {'pkg': 'PyMySQL', 'version': '1.1.1'},
    'sqlalchemy': {'pkg': 'SQLAlchemy', 'version': '2.0.32'},
    'pandas': {'pkg': 'pandas', 'version': '2.2.2'},
    'numpy': {'pkg': 'numpy', 'version': '2.1.1'},
    'requests': {'pkg': 'requests', 'version': '2.32.3'},
    'flask': {'pkg': 'Flask', 'version': '3.0.3'},
    'fastapi': {'pkg': 'fastapi', 'version': '0.112.2'},
    'uvicorn': {'pkg': 'uvicorn', 'version': '0.30.6'},
    'colorama': {'pkg': 'colorama', 'version': '0.4.6'},
    'aiohttp': {'pkg': 'aiohttp', 'version': '3.10.5'},
    'schedule': {'pkg': 'schedule', 'version': '1.2.2'},
    'pytz': {'pkg': 'pytz', 'version': '2024.1'},
    'rich': {'pkg': 'rich', 'version': '13.7.1'},
    'tqdm': {'pkg': 'tqdm', 'version': '4.66.5'},
    'pydantic': {'pkg': 'pydantic', 'version': '2.8.2'},
    'cryptography': {'pkg': 'cryptography', 'version': '43.0.0'},
    'websockets': {'pkg': 'websockets', 'version': '13.0.1'},
    'pymongo': {'pkg': 'pymongo', 'version': '4.8.0'},
    'redis': {'pkg': 'redis', 'version': '5.0.8'},
    'paramiko': {'pkg': 'paramiko', 'version': '3.4.1'},
    'qrcode': {'pkg': 'qrcode', 'version': '7.4.2'},
    'gspread': {'pkg': 'gspread', 'version': '6.1.2'},
    'pyrogram': {'pkg': 'pyrogram', 'version': '2.0.106'},
    'tgcrypto': {'pkg': 'tgcrypto', 'version': '1.2.5'},
    'tweepy': {'pkg': 'tweepy', 'version': '4.14.0'},
    'matplotlib': {'pkg': 'matplotlib', 'version': '3.9.2'},
    'seaborn': {'pkg': 'seaborn', 'version': '0.13.2'},
    'scipy': {'pkg': 'scipy', 'version': '1.14.1'},
    'playwright': {'pkg': 'playwright', 'version': '1.46.0'},
    'selenium': {'pkg': 'selenium', 'version': '4.23.1'},
    'webdriver_manager': {'pkg': 'webdriver-manager', 'version': '4.0.2'},
    'docx': {'pkg': 'python-docx', 'version': '1.1.2'},
    'openpyxl': {'pkg': 'openpyxl', 'version': '3.1.5'},
    'pypdf': {'pkg': 'pypdf', 'version': '4.3.1'},
    'httpx': {'pkg': 'httpx', 'version': '0.27.0'},
    'stripe': {'pkg': 'stripe', 'version': '10.8.0'},
    'yt_dlp': {'pkg': 'yt-dlp', 'version': '2024.8.6'}
}

def write_server_log(server_id, level, message):
    try:
        db = get_db()
        db.execute("INSERT INTO server_logs (server_id, level, message) VALUES (?, ?, ?)", (server_id, level, message))
        db.commit()
    except Exception:
        pass
        
    try:
        db = get_db()
        srv = db.execute("SELECT user_id FROM servers WHERE id = ?", (server_id,)).fetchone()
        if srv:
            server_dir = get_server_dir(srv['user_id'], server_id)
            log_path = os.path.join(server_dir, 'server.log')
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            with open(log_path, 'a', encoding='utf-8') as lf:
                lf.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass

def sanitize_log_text(text):
    if not text:
        return ""
    text = re.sub(r'(token|api[_-]?key|secret|password)=([^\s&]+)', r'\1=********', text, flags=re.IGNORECASE)
    return text

def fetch_pypi_package_info(package_name):
    """Fetch package details & available versions from PyPI with fast offline fallback"""
    clean_name = package_name.strip()
    # Direct lookup in mapping
    rec_info = IMPORT_TO_PACKAGE_MAP.get(clean_name, IMPORT_TO_PACKAGE_MAP.get(clean_name.lower(), {}))
    rec_ver = rec_info.get('version', 'latest')
    
    url = f"https://pypi.org/pypi/{clean_name}/json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HostX-Hosting-V2'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            info = data.get('info', {})
            releases = list(data.get('releases', {}).keys())
            releases = sorted(releases, reverse=True)[:25]
            latest = info.get('version', '')
            if latest and latest not in releases:
                releases.insert(0, latest)
            return {
                'success': True,
                'name': info.get('name', package_name),
                'summary': info.get('summary', 'Python Package from PyPI'),
                'latest': latest or rec_ver,
                'recommended': rec_ver if rec_ver != 'latest' else (latest or 'latest'),
                'versions': releases if releases else [latest or rec_ver]
            }
    except Exception:
        return {
            'success': True,
            'name': package_name,
            'summary': 'Python Package from PyPI',
            'latest': rec_ver if rec_ver != 'latest' else 'latest',
            'recommended': rec_ver,
            'versions': [rec_ver, 'latest'] if rec_ver != 'latest' else ['latest']
        }

def is_package_or_import_installed(server_dir, import_or_pkg_name):
    """Test whether a module or package can be successfully imported in the server sandbox"""
    packages_dir = os.path.join(server_dir, 'packages')
    # Check direct directory existence first for speed
    if os.path.exists(packages_dir):
        pkg_lower = import_or_pkg_name.lower().replace('-', '_')
        for item in os.listdir(packages_dir):
            item_lower = item.lower().replace('-', '_')
            if item_lower == pkg_lower or item_lower.startswith(f"{pkg_lower}-") or item_lower.startswith(f"{pkg_lower}."):
                return True

    # Test via Python subshell import check with server's PYTHONPATH
    test_code = f"import {import_or_pkg_name}"
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{server_dir}:{packages_dir}:" + env.get('PYTHONPATH', '')
    try:
        res = subprocess.run(
            [sys.executable, '-c', test_code],
            cwd=server_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.5
        )
        return res.returncode == 0
    except Exception:
        return False

def scan_and_analyze_project(server_dir, server_id=None):
    """
    Automated file and dependency inspection engine:
    1. Detects Python startup entry file automatically
    2. Detects requirements.txt, pyproject.toml, etc.
    3. Scans Python AST imports across all project files
    4. Checks installed sandbox packages vs missing dependencies
    """
    if not os.path.exists(server_dir):
        return {
            'ready': True,
            'entry_file': 'main.py',
            'py_files': [],
            'has_requirements': False,
            'missing_packages': [],
            'installed_packages': [],
            'all_detected_imports': []
        }

    # 1. Discover all .py files and submodules
    py_files = []
    local_module_names = set()
    for root, dirs, files in os.walk(server_dir):
        # Exclude internal packages sandbox and temporary folders
        dirs[:] = [d for d in dirs if d not in ['packages', '__pycache__', '.venv', '.git', 'venv', 'node_modules']]
        for f in files:
            if f.endswith('.py'):
                rel_path = os.path.relpath(os.path.join(root, f), server_dir)
                py_files.append(rel_path)
                mod_name = os.path.splitext(os.path.basename(f))[0]
                local_module_names.add(mod_name)
                # Also if directory has __init__.py, add folder name as local module
                if f == '__init__.py':
                    local_module_names.add(os.path.basename(root))

    # Auto-detect entry file priority
    detected_entry = 'main.py'
    entry_candidates = ['main.py', 'app.py', 'bot.py', 'server.py', 'run.py', 'index.py']
    for candidate in entry_candidates:
        if candidate in py_files:
            detected_entry = candidate
            break
    else:
        if py_files:
            detected_entry = py_files[0]

    # 2. Parse requirements.txt
    req_path = os.path.join(server_dir, 'requirements.txt')
    has_requirements = os.path.isfile(req_path)
    req_packages = {}
    if has_requirements:
        try:
            with open(req_path, 'r', encoding='utf-8', errors='ignore') as rf:
                for line in rf:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Parse package name and version
                        m = re.split(r'==|>=|<=|~=|!=|>', line, maxsplit=1)
                        pkg_name = m[0].strip()
                        ver = m[1].strip() if len(m) > 1 else 'latest'
                        if pkg_name:
                            req_packages[pkg_name] = ver
        except Exception:
            pass

    # 3. Extract AST imports from all Python files
    extracted_imports = set()
    for py_file in py_files:
        full_py_path = os.path.join(server_dir, py_file)
        try:
            with open(full_py_path, 'r', encoding='utf-8', errors='ignore') as pf:
                tree = ast.parse(pf.read(), filename=py_file)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top_mod = alias.name.split('.')[0]
                            if top_mod and top_mod not in STDLIB_MODULES and top_mod not in local_module_names:
                                extracted_imports.add(top_mod)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            top_mod = node.module.split('.')[0]
                            if top_mod and top_mod not in STDLIB_MODULES and top_mod not in local_module_names:
                                extracted_imports.add(top_mod)
        except Exception:
            pass

    # 4. Consolidate required packages (from requirements.txt + AST imports)
    required_packages_dict = {}

    # Add requirements.txt packages first (preserves pinned versions)
    for pkg_name, ver in req_packages.items():
        # Find corresponding import name if known
        import_name = pkg_name
        for imp, info in IMPORT_TO_PACKAGE_MAP.items():
            if info['pkg'].lower() == pkg_name.lower():
                import_name = imp
                break
        required_packages_dict[pkg_name] = {
            'name': pkg_name,
            'import_name': import_name,
            'version': ver,
            'source': 'requirements.txt'
        }

    # Add AST detected imports
    for imp_name in extracted_imports:
        mapping = IMPORT_TO_PACKAGE_MAP.get(imp_name, {})
        pkg_name = mapping.get('pkg', imp_name)
        rec_version = mapping.get('version', 'latest')

        # Check if already added via requirements.txt
        existing_key = None
        for k in required_packages_dict.keys():
            if k.lower() == pkg_name.lower():
                existing_key = k
                break

        if not existing_key:
            required_packages_dict[pkg_name] = {
                'name': pkg_name,
                'import_name': imp_name,
                'version': rec_version,
                'source': 'code_import'
            }

    # 5. Check installation state of each package
    missing_packages = []
    installed_packages = []

    for pkg_name, info in required_packages_dict.items():
        is_installed = is_package_or_import_installed(server_dir, info['import_name'])
        if not is_installed and info['name'] != info['import_name']:
            is_installed = is_package_or_import_installed(server_dir, info['name'])

        if is_installed:
            installed_packages.append({
                'name': info['name'],
                'import_name': info['import_name'],
                'version': info['version'],
                'source': info['source']
            })
        else:
            missing_packages.append({
                'name': info['name'],
                'import_name': info['import_name'],
                'version': info['version'],
                'source': info['source'],
                'reason': f"Module '{info['import_name']}' is not installed in the server environment."
            })

    # Also list packages found directly inside the packages/ sandbox directory
    packages_dir = os.path.join(server_dir, 'packages')
    if os.path.exists(packages_dir):
        for item in os.listdir(packages_dir):
            if item.endswith('.dist-info'):
                pkg_raw = item.replace('.dist-info', '')
                parts = pkg_raw.split('-')
                pname = parts[0]
                pver = parts[1] if len(parts) > 1 else 'installed'
                if not any(ip['name'].lower() == pname.lower() for ip in installed_packages):
                    installed_packages.append({
                        'name': pname,
                        'import_name': pname,
                        'version': pver,
                        'source': 'sandbox_directory'
                    })

    is_ready = (len(missing_packages) == 0)

    has_entry_file = bool(py_files) or (detected_entry and os.path.isfile(os.path.join(server_dir, detected_entry)))

    return {
        'ready': is_ready,
        'entry_file': detected_entry,
        'has_entry_file': has_entry_file,
        'py_files': py_files,
        'has_requirements': has_requirements,
        'missing_packages': missing_packages,
        'installed_packages': installed_packages,
        'all_detected_imports': sorted(list(extracted_imports))
    }

# Check and update server expirations
def update_server_statuses():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        now_iso = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        expired_servers = conn.execute("SELECT * FROM servers WHERE expires_at < ? AND status != 'expired'", (now_iso,)).fetchall()
        for s in expired_servers:
            s_id = s['id']
            # Instantly kill running process (kill -9)
            proc = RUNNING_PROCESSES.pop(s_id, None)
            if proc:
                try:
                    if hasattr(os, 'killpg') and hasattr(os, 'getpgid'):
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.kill()
                except Exception:
                    pass
            if s['pid'] and s['pid'] > 0:
                try:
                    if psutil.pid_exists(s['pid']):
                        p = psutil.Process(s['pid'])
                        p.kill()
                except Exception:
                    pass
            SERVER_START_TIMES.pop(s_id, None)
            conn.execute("UPDATE servers SET status = 'expired', pid = 0 WHERE id = ?", (s_id,))
            conn.execute("INSERT INTO server_logs (server_id, level, message) VALUES (?, 'WARNING', ?)",
                         (s_id, 'Server validity expired! All background Python processes terminated automatically (SIGKILL).'))
        conn.commit()
        conn.close()
    except Exception:
        pass

# Background Process Monitor & Runtime Crash Detector
def background_process_monitor():
    """Continuously monitors running server processes and catches runtime dependency errors."""
    while True:
        try:
            update_server_statuses()
            time.sleep(2)
            current_procs = list(RUNNING_PROCESSES.items())
            for server_id, proc in current_procs:
                if proc.poll() is not None:
                    exit_code = proc.returncode
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        conn.row_factory = sqlite3.Row
                        srv = conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
                        if srv:
                            server_dir = get_server_dir(srv['user_id'], server_id)
                            log_path = os.path.join(server_dir, 'server.log')
                            missing_mod = None
                            last_error_text = ""
                            if os.path.exists(log_path):
                                with open(log_path, 'r', encoding='utf-8', errors='ignore') as lf:
                                    lines = lf.readlines()[-35:]
                                    log_tail = "".join(lines)
                                    match = re.search(r"ModuleNotFoundError:\s+No module named\s+'([^']+)'", log_tail)
                                    if not match:
                                        match = re.search(r"ImportError:\s+No module named\s+([^\s\n\r]+)", log_tail)
                                    if match:
                                        missing_mod = match.group(1).split('.')[0]
                                        last_error_text = match.group(0)

                            if missing_mod and missing_mod not in STDLIB_MODULES:
                                pkg_info = IMPORT_TO_PACKAGE_MAP.get(missing_mod, {'pkg': missing_mod, 'version': 'latest'})
                                pkg_name = pkg_info['pkg']
                                conn.execute("UPDATE servers SET status = 'package_required', pid = 0 WHERE id = ?", (server_id,))
                                conn.execute(
                                    "INSERT INTO server_logs (server_id, level, message) VALUES (?, ?, ?)",
                                    (server_id, 'ERROR', f"Runtime Crash: {last_error_text}")
                                )
                                conn.execute(
                                    "INSERT INTO server_logs (server_id, level, message) VALUES (?, ?, ?)",
                                    (server_id, 'WARNING', f"Server stopped automatically. Auto-restart paused due to missing package: '{pkg_name}'.")
                                )
                                conn.execute(
                                    "INSERT INTO server_logs (server_id, level, message) VALUES (?, ?, ?)",
                                    (server_id, 'INFO', f"Please install '{pkg_name}' via Package Installer to resume hosting.")
                                )
                                conn.commit()
                            else:
                                if exit_code != 0:
                                    conn.execute("UPDATE servers SET status = 'error', pid = 0 WHERE id = ?", (server_id,))
                                    conn.execute(
                                        "INSERT INTO server_logs (server_id, level, message) VALUES (?, ?, ?)",
                                        (server_id, 'ERROR', f"Process crashed with exit code {exit_code}.")
                                    )
                                else:
                                    conn.execute("UPDATE servers SET status = 'stopped', pid = 0 WHERE id = ?", (server_id,))
                                    conn.execute(
                                        "INSERT INTO server_logs (server_id, level, message) VALUES (?, ?, ?)",
                                        (server_id, 'STOPPING', "Process completed execution and stopped.")
                                    )
                                conn.commit()
                        conn.close()
                    except Exception:
                        pass
                    finally:
                        RUNNING_PROCESSES.pop(server_id, None)
                        SERVER_START_TIMES.pop(server_id, None)
        except Exception:
            pass

# Start the background daemon monitor
_monitor_thread = threading.Thread(target=background_process_monitor, daemon=True)
_monitor_thread.start()

# Real process start with automated pre-start dependency checks
def start_server_process(server_id):
    db = get_db()
    server = db.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    if not server:
        return False, "Server not found", []
    
    # 1. Check expiration
    if isinstance(server['expires_at'], str):
        exp = datetime.strptime(server['expires_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
    else:
        exp = server['expires_at']
    if exp < datetime.utcnow():
        db.execute("UPDATE servers SET status = 'expired' WHERE id = ?", (server_id,))
        db.commit()
        return False, "Server has expired. Please renew with coins.", []
    
    server_dir = get_server_dir(server['user_id'], server_id)
    log_file_path = os.path.join(server_dir, 'server.log')
    
    # 2. Write Pre-Check Logging Steps
    write_server_log(server_id, 'INFO', "Checking Project...")
    write_server_log(server_id, 'INFO', f"Python Version: {server['python_version']}")
    
    # 3. Detect and verify entry file
    scan = scan_and_analyze_project(server_dir, server_id)
    entry_file = server['entry_file'] or scan['entry_file'] or 'main.py'
    entry_path = os.path.join(server_dir, entry_file)
    
    if not os.path.exists(entry_path):
        # If the entry file is missing but we found another .py file, use that
        if scan['py_files']:
            entry_file = scan['py_files'][0]
            entry_path = os.path.join(server_dir, entry_file)
            db.execute("UPDATE servers SET entry_file = ? WHERE id = ?", (entry_file, server_id))
            db.commit()
        else:
            # No Python entry file uploaded
            write_server_log(server_id, 'ERROR', "Please upload your project files and main entry file before starting the server.")
            db.execute("UPDATE servers SET status = 'stopped', pid = 0 WHERE id = ?", (server_id,))
            db.commit()
            return False, "Please upload your project files and main entry file before starting the server.", [], True
                
    write_server_log(server_id, 'INFO', f"Startup file detected: {entry_file}")

    # 4. Check requirements.txt and auto-install dependencies with live streaming logs
    req_path = os.path.join(server_dir, 'requirements.txt')
    local_pkg_dir = os.path.join(server_dir, 'packages')
    os.makedirs(local_pkg_dir, exist_ok=True)

    if os.path.isfile(req_path):
        write_server_log(server_id, 'INFO', "requirements.txt detected. Running pip install -r requirements.txt...")
        cmd_pip = [sys.executable, "-m", "pip", "install", "-r", req_path, "--target", local_pkg_dir, "--no-cache-dir", "--disable-pip-version-check"]
        try:
            proc_pip = subprocess.Popen(
                cmd_pip,
                cwd=server_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            if proc_pip.stdout:
                for line in proc_pip.stdout:
                    line_str = line.strip()
                    if line_str:
                        write_server_log(server_id, 'INFO', f"[pip] {line_str}")
                        with open(log_file_path, 'a', encoding='utf-8') as lf:
                            lf.write(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] [pip] {line_str}\n")
            proc_pip.wait()
            if proc_pip.returncode == 0:
                write_server_log(server_id, 'INFO', "Successfully installed all dependencies from requirements.txt")
            else:
                write_server_log(server_id, 'WARNING', "pip install completed with warnings.")
        except Exception as pe:
            write_server_log(server_id, 'ERROR', f"Failed to run requirements.txt install: {str(pe)}")
        
        # Refresh project scan after requirements.txt installation
        scan = scan_and_analyze_project(server_dir, server_id)

    write_server_log(server_id, 'INFO', "Checking pre-detected dependencies...")
    
    # 5. Check pre-detected imported modules (AST scan) & Auto-install missing packages
    if not scan['ready'] and scan['missing_packages']:
        missing_pkgs = scan['missing_packages']
        missing_names = [p['name'] for p in missing_pkgs]
        write_server_log(server_id, 'INFO', f"[INFO] Pre-detected missing module(s): {', '.join(missing_names)}. Starting fast auto-installation...")
        
        for pkg in missing_pkgs:
            pkg_name = pkg['name']
            imp_name = pkg['import_name']
            ver = pkg['version']
            display_target = f"{pkg_name}=={ver}" if ver and ver != 'latest' else pkg_name
            
            write_server_log(server_id, 'INFO', f"[INFO] Auto-installing pre-detected dependency: {imp_name} ({display_target})...")
            
            cmd_auto = [sys.executable, "-m", "pip", "install", display_target, "--target", local_pkg_dir, "--no-cache-dir", "--disable-pip-version-check"]
            try:
                proc_auto = subprocess.Popen(
                    cmd_auto,
                    cwd=server_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                if proc_auto.stdout:
                    for line in proc_auto.stdout:
                        line_str = line.strip()
                        if line_str:
                            write_server_log(server_id, 'INFO', f"[pip] {line_str}")
                proc_auto.wait()
                if proc_auto.returncode == 0:
                    write_server_log(server_id, 'INFO', f"[INFO] Auto-installing pre-detected dependency: {imp_name}... Done.")
                else:
                    write_server_log(server_id, 'WARNING', f"[WARNING] Auto-installation for {imp_name} finished with warnings.")
            except Exception as e:
                write_server_log(server_id, 'ERROR', f"[ERROR] Auto-installation error for {pkg_name}: {str(e)}")

        # Refresh project scan after fast auto-installation
        scan = scan_and_analyze_project(server_dir, server_id)

    # 6. Fallback Check: If any dependency failed to install or is unresolvable
    if not scan['ready'] and scan['missing_packages']:
        missing_names = [p['name'] for p in scan['missing_packages']]
        missing_str = ", ".join(missing_names)
        first_imp = scan['missing_packages'][0]['import_name']
        
        write_server_log(server_id, 'ERROR', f"ModuleNotFoundError: No module named '{first_imp}'")
        write_server_log(server_id, 'ERROR', f"[ERROR] Server startup failed due to missing package(s): {missing_str}")
        write_server_log(server_id, 'ERROR', "[ERROR] Dependency auto-installer was unable to resolve all packages. Check logs.")
        
        db.execute("UPDATE servers SET status = 'package_required', pid = 0 WHERE id = ?", (server_id,))
        db.commit()
        
        return False, f"Package Required: Missing {missing_str}. Please install dependencies.", scan['missing_packages'], False
    
    # 7. Dependencies satisfied - proceed to start main Python app
    write_server_log(server_id, 'INFO', "All pre-detected dependencies satisfied. Launching server...")
    
    # If already running, terminate first
    stop_server_process(server_id)
    
    log_file = open(log_file_path, 'a', encoding='utf-8')
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    log_file.write(f"\n--- [HOSTX ENGINE] Server starting at {timestamp} ---\n")
    log_file.flush()
    
    try:
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        if os.path.exists(local_pkg_dir):
            env['PYTHONPATH'] = f"{server_dir}:{local_pkg_dir}:" + env.get('PYTHONPATH', '')
        else:
            env['PYTHONPATH'] = f"{server_dir}:" + env.get('PYTHONPATH', '')
            
        proc = subprocess.Popen(
            [sys.executable, entry_file],
            cwd=server_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        RUNNING_PROCESSES[server_id] = proc
        SERVER_START_TIMES[server_id] = time.time()
        
        db.execute("UPDATE servers SET status = 'running', pid = ? WHERE id = ?", (proc.pid, server_id))
        db.commit()
        
        write_server_log(server_id, 'INFO', f"Server process started successfully (PID: {proc.pid}). Loaded {entry_file}")
        return True, "Server started successfully", [], False
    except Exception as e:
        write_server_log(server_id, 'ERROR', f"Failed to launch process: {str(e)}")
        db.execute("UPDATE servers SET status = 'error', pid = 0 WHERE id = ?", (server_id,))
        db.commit()
        return False, str(e), [], False

# Real process stop
def stop_server_process(server_id):
    db = get_db()
    proc = RUNNING_PROCESSES.get(server_id)
    if proc:
        try:
            if hasattr(os, 'killpg') and hasattr(os, 'getpgid'):
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        RUNNING_PROCESSES.pop(server_id, None)
        SERVER_START_TIMES.pop(server_id, None)
    
    # Check if PID in DB is still running
    server = db.execute("SELECT pid FROM servers WHERE id = ?", (server_id,)).fetchone()
    if server and server['pid']:
        try:
            if psutil.pid_exists(server['pid']):
                p = psutil.Process(server['pid'])
                p.terminate()
        except Exception:
            pass
            
    db.execute("UPDATE servers SET status = 'stopped', pid = 0 WHERE id = ?", (server_id,))
    db.commit()
    write_server_log(server_id, 'STOPPING', 'Server process stopped.')
    return True

# ----------------- ROUTES -----------------

@app.route('/health')
def health():
    uptime = time.time() - SERVER_START_TIMES.get(0, time.time())
    return jsonify({
        'status': 'healthy',
        'platform': 'HostX VIP White',
        'version': '2.0.0',
        'active_servers': len(RUNNING_PROCESSES),
        'timestamp': datetime.utcnow().isoformat()
    }), 200

# 1. HOME / LANDING PAGE
@app.route('/')
def home():
    update_server_statuses()
    user = get_current_user()
    db = get_db()
    packages = db.execute("SELECT * FROM packages WHERE active = 1 ORDER BY days ASC").fetchall()
    
    # Stats for showcase
    total_servers = db.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    
    return render_template('home.html', packages=packages, total_servers=total_servers, total_users=total_users)

# 2. SIGN IN
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if 'user_id' in session and get_current_user():
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        if not email or not password:
            flash('Please provide both your registered email address and password.', 'danger')
            return render_template('signin.html', email=email)
            
        db = get_db()
        # Strictly authenticate by registered email address (case-insensitive)
        user = db.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)",
            (email,)
        ).fetchone()
        
        if not user:
            flash('Invalid email or password.', 'danger')
            return render_template('signin.html', email=email)
            
        if user['status'] == 'disabled':
            flash('This account has been suspended. Please contact support.', 'danger')
            return render_template('signin.html', email=email)
            
        if not safe_check_password_hash(user['password_hash'], password):
            flash('Incorrect password. Please try again.', 'danger')
            return render_template('signin.html', email=email)
            
        # Seamlessly upgrade legacy/scrypt password hash to fast, standard PBKDF2-SHA256
        if not str(user['password_hash']).startswith('pbkdf2:sha256:'):
            try:
                upgraded_hash = safe_generate_password_hash(password)
                db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (upgraded_hash, user['id']))
                db.commit()
            except Exception:
                pass

        # Authentication successful
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session.permanent = True  # Always keep the user logged in persistently until manual signout
            
        flash(f'Welcome back, {user["full_name"]}!', 'success')
        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('dashboard'))
        
    return render_template('signin.html')

# 2.5 FORGOT PASSWORD API (Step-by-step)
@app.route('/api/forgot-password/captcha', methods=['GET'])
def forgot_password_captcha():
    import random
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    op = random.choice(['+', '-', '*'])
    if op == '+':
        ans = num1 + num2
    elif op == '-':
        ans = num1 - num2
    else:
        ans = num1 * num2
    session['forgot_captcha_ans'] = ans
    session['forgot_captcha_verified'] = False
    session['forgot_verified_email'] = None
    return jsonify({
        'question': f"{num1} {op} {num2} = ?"
    })

@app.route('/api/forgot-password/verify-captcha', methods=['POST'])
def forgot_password_verify_captcha():
    data = request.get_json() or {}
    try:
        user_ans = int(data.get('answer', ''))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Please enter a valid number.'})
    
    expected = session.get('forgot_captcha_ans')
    if expected is not None and user_ans == expected:
        session['forgot_captcha_verified'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Incorrect answer. Please try again.'})

@app.route('/api/forgot-password/verify-email', methods=['POST'])
def forgot_password_verify_email():
    if not session.get('forgot_captcha_verified'):
        return jsonify({'success': False, 'message': 'Security Captcha challenge not completed yet.'})
    
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'success': False, 'message': 'Please enter your registered email address.'})
    
    db = get_db()
    user = db.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
    if user:
        session['forgot_verified_email'] = email
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'This email address is not registered.'})

@app.route('/api/forgot-password/reset', methods=['POST'])
def forgot_password_reset():
    if not session.get('forgot_captcha_verified') or not session.get('forgot_verified_email'):
        return jsonify({'success': False, 'message': 'Session expired or invalid flow. Please try again.'})
    
    data = request.get_json() or {}
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    
    if not password or not confirm_password:
        return jsonify({'success': False, 'message': 'Both password fields are required.'})
    if password != confirm_password:
        return jsonify({'success': False, 'message': 'Passwords do not match.'})
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'})
    
    email = session.get('forgot_verified_email')
    db = get_db()
    try:
        hashed = safe_generate_password_hash(password)
        db.execute("UPDATE users SET password_hash = ? WHERE LOWER(email) = LOWER(?)", (hashed, email))
        db.commit()
        # Clear forgot password session keys
        session.pop('forgot_captcha_ans', None)
        session.pop('forgot_captcha_verified', None)
        session.pop('forgot_verified_email', None)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error resetting password: {str(e)}'})

# 3. CREATE ACCOUNT / SIGN UP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session and get_current_user():
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validations
        if not full_name or not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('signup.html', full_name=full_name, username=username, email=email)

        # Strict Gmail-only validation: Must strictly end with @gmail.com
        if not email.endswith('@gmail.com') or email == '@gmail.com' or len(email.split('@')[0]) < 1:
            flash('Registration requires a valid Gmail address (must strictly end with @gmail.com). Other email providers are not supported.', 'danger')
            return render_template('signup.html', full_name=full_name, username=username, email=email)
            
        if len(username) < 3:
            flash('Username must be at least 3 characters.', 'danger')
            return render_template('signup.html', full_name=full_name, username=username, email=email)
            
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('signup.html', full_name=full_name, username=username, email=email)
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('signup.html', full_name=full_name, username=username, email=email)
            
        db = get_db()
        # Enforce absolute uniqueness for Email (case-insensitive)
        existing_email = db.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
        if existing_email:
            flash('An account with this Gmail address already exists. Please sign in.', 'danger')
            return render_template('signup.html', full_name=full_name, username=username, email=email)
            
        # Enforce absolute uniqueness for Username (case-insensitive)
        existing_user = db.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,)).fetchone()
        if existing_user:
            flash('This username is already taken. Please choose another username.', 'danger')
            return render_template('signup.html', full_name=full_name, username=username, email=email)
            
        try:
            starting_coins = max(0, int(get_setting('default_starting_coins', '50')))
        except (ValueError, TypeError):
            starting_coins = 50

        pw_hash = safe_generate_password_hash(password)
        
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO users (full_name, username, email, password_hash, coins, role, status)
            VALUES (?, ?, ?, ?, ?, 'user', 'active')
        ''', (full_name, username, email, pw_hash, starting_coins))
        new_user_id = cursor.lastrowid
        
        vip_brand = get_setting('vip_site_name', 'HostX VIP')

        # Log initial welcome coins transaction & in-app notification if bonus > 0
        if starting_coins > 0:
            cursor.execute('''
                INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type)
                VALUES (?, ?, ?, 'Signup Welcome Bonus', 'credit')
            ''', (new_user_id, starting_coins, starting_coins))
            
            cursor.execute('''
                INSERT INTO notifications (user_id, title, message)
                VALUES (?, ?, ?)
            ''', (new_user_id, '🎁 Welcome Bonus Coins', f"Welcome {full_name}! You received {starting_coins} free signup bonus coins to start launching your 24/7 Python servers."))
        else:
            cursor.execute('''
                INSERT INTO notifications (user_id, title, message)
                VALUES (?, ?, ?)
            ''', (new_user_id, f'Welcome to {vip_brand}', f"Welcome {full_name}! Your account has been registered successfully. Explore packages and deploy your first Python server."))
        
        db.commit()
        
        session.clear()
        session['user_id'] = new_user_id
        session['username'] = username
        session['role'] = 'user'
        session.permanent = True
        
        if starting_coins > 0:
            flash(f'Account created successfully! You received {starting_coins} welcome bonus coins.', 'success')
        else:
            flash('Account created successfully! Welcome to the platform.', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('signup.html')

# SIGN OUT
@app.route('/signout')
def signout():
    session.clear()
    flash('You have been signed out safely.', 'info')
    return redirect(url_for('home'))

# 4. DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():
    update_server_statuses()
    user = get_current_user()
    db = get_db()
    
    # Fetch user's servers
    servers = db.execute("SELECT * FROM servers WHERE user_id = ? ORDER BY created_at DESC", (user['id'],)).fetchall()
    
    # Calculate file count and storage for this user
    total_files = 0
    total_storage_bytes = 0
    user_servers_dir = os.path.join(SERVERS_DIR, str(user['id']))
    if os.path.exists(user_servers_dir):
        for root, dirs, files in os.walk(user_servers_dir):
            total_files += len(files)
            for f in files:
                try:
                    total_storage_bytes += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass
                    
    # Format storage
    if total_storage_bytes < 1024 * 1024:
        storage_formatted = f"{total_storage_bytes / 1024:.1f} KB"
    else:
        storage_formatted = f"{total_storage_bytes / (1024 * 1024):.1f} MB"
        
    # Check daily reward eligibility
    can_claim_daily = True
    if user['last_daily_claim']:
        try:
            last_claim = user['last_daily_claim']
            if isinstance(last_claim, str):
                last_claim = datetime.strptime(last_claim.split('.')[0], '%Y-%m-%d %H:%M:%S')
            time_diff = datetime.utcnow() - last_claim
            if time_diff.total_seconds() < 24 * 3600:
                can_claim_daily = False
        except Exception:
            can_claim_daily = True
            
    recent_transactions = db.execute(
        "SELECT * FROM coin_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (user['id'],)
    ).fetchall()

    # Fetch active announcements / site updates
    announcements = db.execute(
        "SELECT * FROM announcements WHERE is_active = 1 ORDER BY pinned DESC, id DESC LIMIT 5"
    ).fetchall()
    
    return render_template(
        'dashboard.html',
        servers=servers,
        total_files=total_files,
        storage_formatted=storage_formatted,
        can_claim_daily=can_claim_daily,
        recent_transactions=recent_transactions,
        announcements=announcements
    )

# 5. COINS PAGE & DAILY CLAIM
@app.route('/coins')
@login_required
def coins():
    user = get_current_user()
    db = get_db()
    
    transactions = db.execute(
        "SELECT * FROM coin_transactions WHERE user_id = ? ORDER BY created_at DESC",
        (user['id'],)
    ).fetchall()
    
    can_claim_daily = True
    now_utc = datetime.utcnow()
    now_bd = now_utc + timedelta(hours=6)
    today_bd_date = now_bd.date()
    
    if user['last_daily_claim']:
        try:
            last_claim = user['last_daily_claim']
            if isinstance(last_claim, str):
                last_claim_utc = datetime.strptime(last_claim.split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                last_claim_utc = last_claim
            
            last_claim_bd = last_claim_utc + timedelta(hours=6)
            if today_bd_date == last_claim_bd.date():
                can_claim_daily = False
        except Exception:
            pass
            
    daily_reward = int(get_setting('daily_reward_coins', '10'))
    return render_template('coins.html', transactions=transactions, can_claim_daily=can_claim_daily, daily_reward=daily_reward)

@app.route('/api/coins/claim-daily', methods=['POST'])
@login_required
def claim_daily():
    user = get_current_user()
    db = get_db()
    
    now_utc = datetime.utcnow()
    now_bd = now_utc + timedelta(hours=6)
    today_bd_date = now_bd.date()
    
    if user['last_daily_claim']:
        try:
            last_claim = user['last_daily_claim']
            if isinstance(last_claim, str):
                last_claim_utc = datetime.strptime(last_claim.split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                last_claim_utc = last_claim
            
            last_claim_bd = last_claim_utc + timedelta(hours=6)
            if today_bd_date == last_claim_bd.date():
                return jsonify({'success': False, 'message': 'You have already claimed today! Next claim available at 12:00 AM.'}), 400
        except Exception:
            pass
            
    reward = int(get_setting('daily_reward_coins', '10'))
    new_balance = user['coins'] + reward
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    db.execute("UPDATE users SET coins = ?, last_daily_claim = ? WHERE id = ?", (new_balance, now_str, user['id']))
    db.execute(
        "INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?, ?, ?, ?, 'credit')",
        (user['id'], reward, new_balance, f"+{reward} Daily Bonus Reward")
    )
    db.execute(
        "INSERT INTO notifications (user_id, title, message) VALUES (?, 'Daily Bonus Claimed', ?)",
        (user['id'], f"You successfully claimed +{reward} Daily Bonus Coins! New balance: {new_balance} coins.")
    )
    db.commit()
    
    return jsonify({
        'success': True,
        'message': f'Successfully claimed +{reward} Daily Coins!',
        'new_balance': new_balance
    })

# 6. ACCOUNT SETTINGS
@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = get_current_user()
    db = get_db()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'upload_avatar':
            if 'avatar' not in request.files:
                flash('No image file selected.', 'warning')
                return redirect(url_for('account'))
            
            file = request.files['avatar']
            if not file or not file.filename:
                flash('Please select an image file to upload.', 'warning')
                return redirect(url_for('account'))
                
            # Validate allowed extensions
            allowed_extensions = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'}
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in allowed_extensions:
                flash('Unsupported format. Allowed formats: PNG, JPG, JPEG, WEBP, GIF, SVG.', 'danger')
                return redirect(url_for('account'))
                
            # Validate file size (max 5MB)
            file.seek(0, os.SEEK_END)
            size_bytes = file.tell()
            file.seek(0)
            if size_bytes > 5 * 1024 * 1024:
                flash('File size exceeds 5MB limit. Please upload a smaller image.', 'danger')
                return redirect(url_for('account'))
                
            # Strict user isolation: Store in isolated directory for this user only
            user_avatar_dir = os.path.join(AVATARS_DIR, f"user_{user['id']}")
            os.makedirs(user_avatar_dir, exist_ok=True)
            
            # Clean up previous avatar files for this specific user only
            try:
                for existing_file in os.listdir(user_avatar_dir):
                    existing_path = os.path.join(user_avatar_dir, existing_file)
                    if os.path.isfile(existing_path):
                        os.remove(existing_path)
            except Exception as e:
                print(f"Error cleaning user {user['id']} avatar: {e}")
                
            # Save new avatar with unique timestamp
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"avatar_{timestamp}.{ext}"
            file_path = os.path.join(user_avatar_dir, filename)
            file.save(file_path)
            
            avatar_url = f"/static/uploads/avatars/user_{user['id']}/{filename}"
            db.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user['id']))
            db.commit()
            
            flash('Profile picture / logo updated successfully!', 'success')
            return redirect(url_for('account'))
            
        elif action == 'remove_avatar':
            user_avatar_dir = os.path.join(AVATARS_DIR, f"user_{user['id']}")
            if os.path.exists(user_avatar_dir):
                try:
                    for existing_file in os.listdir(user_avatar_dir):
                        existing_path = os.path.join(user_avatar_dir, existing_file)
                        if os.path.isfile(existing_path):
                            os.remove(existing_path)
                except Exception as e:
                    print(f"Error removing user {user['id']} avatar: {e}")
                    
            db.execute("UPDATE users SET avatar_url = '' WHERE id = ?", (user['id'],))
            db.commit()
            flash('Profile picture removed. Reverted to default avatar.', 'info')
            return redirect(url_for('account'))
            
        elif action == 'update_profile':
            full_name = request.form.get('full_name', '').strip()
            bio = request.form.get('bio', '').strip()
            
            if not full_name:
                flash('Full name cannot be empty.', 'danger')
                return redirect(url_for('account'))

            is_admin = (user['role'] == 'admin')

            if is_admin:
                # Administrator self-profile override: allowed to update username and email with validation
                username = request.form.get('username', user['username']).strip().lower()
                email = request.form.get('email', user['email']).strip().lower()

                if not username or not email:
                    flash('Username and email cannot be empty.', 'danger')
                    return redirect(url_for('account'))

                # Strict Gmail-only validation: Must strictly end with @gmail.com
                if not email.endswith('@gmail.com') or email == '@gmail.com' or len(email.split('@')[0]) < 1:
                    flash('Email address must be a valid Gmail address (ending with @gmail.com).', 'danger')
                    return redirect(url_for('account'))

                if len(username) < 3:
                    flash('Username must be at least 3 characters.', 'danger')
                    return redirect(url_for('account'))
                    
                # Check unique email (case-insensitive)
                exist_email = db.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?) AND id != ?", (email, user['id'])).fetchone()
                if exist_email:
                    flash('That Gmail address is already in use by another account.', 'danger')
                    return redirect(url_for('account'))
                    
                # Check unique username (case-insensitive)
                exist_user = db.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?) AND id != ?", (username, user['id'])).fetchone()
                if exist_user:
                    flash('That username is already taken.', 'danger')
                    return redirect(url_for('account'))
            else:
                # Regular user: Username and Email modifications are strictly disallowed and ignored on the backend
                username = user['username']
                email = user['email']
                
            db.execute(
                "UPDATE users SET full_name = ?, username = ?, email = ?, bio = ? WHERE id = ?",
                (full_name, username, email, bio, user['id'])
            )
            db.commit()
            session['username'] = username
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('account'))
            
        elif action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_new_password', '')
            
            if not current_pw or not new_pw:
                flash('Please provide both current and new password.', 'danger')
                return redirect(url_for('account'))
                
            if not safe_check_password_hash(user['password_hash'], current_pw):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('account'))
                
            if len(new_pw) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
                return redirect(url_for('account'))
                
            if new_pw != confirm_pw:
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('account'))
                
            new_hash = safe_generate_password_hash(new_pw)
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user['id']))
            db.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('account'))
            
    return render_template('account.html', user=user)

# 7. SERVER PACKAGES
@app.route('/packages')
@login_required
def packages():
    user = get_current_user()
    db = get_db()
    all_packages = db.execute("SELECT * FROM packages WHERE active = 1 ORDER BY days ASC").fetchall()
    return render_template('packages.html', packages=all_packages, user=user)

# 8. CREATE SERVER
@app.route('/servers/create', methods=['GET', 'POST'])
@login_required
def create_server():
    user = get_current_user()
    db = get_db()
    
    if request.method == 'POST':
        server_name = request.form.get('name', '').strip()
        package_id = request.form.get('package_id')
        python_ver = request.form.get('python_version', 'Python 3.10')
        
        if not server_name:
            flash('Server Name is required.', 'danger')
            return redirect(url_for('create_server'))
            
        pkg = db.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
        if not pkg:
            flash('Invalid server package selected.', 'danger')
            return redirect(url_for('create_server'))
            
        # Check first-time offer validity
        if pkg['is_first_time_offer'] == 1:
            if user['first_time_offer_used'] == 1:
                flash('The First Time Offer package is only available once per user.', 'danger')
                return redirect(url_for('create_server'))
                
        # Check coin balance
        if user['coins'] < pkg['coins']:
            flash(f'Insufficient coins! This package requires {pkg["coins"]} coins. You have {user["coins"]} coins.', 'danger')
            return redirect(url_for('coins'))
            
        # Calculate expiration
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(days=pkg['days'])
        new_balance = user['coins'] - pkg['coins']
        
        # Deduct coins & update user
        if pkg['is_first_time_offer'] == 1:
            db.execute("UPDATE users SET coins = ?, first_time_offer_used = 1 WHERE id = ?", (new_balance, user['id']))
        else:
            db.execute("UPDATE users SET coins = ? WHERE id = ?", (new_balance, user['id']))
            
        # Record transaction
        db.execute('''
            INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type)
            VALUES (?, ?, ?, ?, 'debit')
        ''', (user['id'], -pkg['coins'], new_balance, f"-{pkg['coins']} Coins for {server_name} ({pkg['name']})"))
        
        # Create server record
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO servers (user_id, name, python_version, entry_file, status, created_at, expires_at)
            VALUES (?, ?, ?, 'main.py', 'stopped', ?, ?)
        ''', (user['id'], server_name, python_ver, created_at, expires_at))
        new_server_id = cursor.lastrowid
        
        cursor.execute('''
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, 'Server Created', ?)
        ''', (user['id'], f"Server '{server_name}' was created successfully ({pkg['name']} - {pkg['days']} Days)."))
        
        # Initialize physical server directory with starter template
        server_dir = get_server_dir(user['id'], new_server_id)
        main_py_path = os.path.join(server_dir, 'main.py')
        with open(main_py_path, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_MAIN_PY)
            
        reqs_path = os.path.join(server_dir, 'requirements.txt')
        with open(reqs_path, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_REQUIREMENTS_TXT)
            
        write_server_log(new_server_id, 'INFO', f"Server '{server_name}' created with {pkg['name']} ({pkg['days']} Days).")
        db.commit()
        
        flash(f"Server '{server_name}' created successfully!", 'success')
        return redirect(url_for('server_manage', server_id=new_server_id))
        
    packages_list = db.execute("SELECT * FROM packages WHERE active = 1 ORDER BY days ASC").fetchall()
    selected_pkg_id = request.args.get('pkg', type=int)
    return render_template('create_server.html', packages=packages_list, user=user, selected_pkg_id=selected_pkg_id)

# 9. SERVER MANAGEMENT PANEL
@app.route('/servers/<int:server_id>')
@login_required
def server_manage(server_id):
    update_server_statuses()
    server = check_server_ownership(server_id)
    if not server:
        abort(404)
        
    db = get_db()
    # Calculate days remaining
    exp = server['expires_at']
    if isinstance(exp, str):
        exp_dt = datetime.strptime(exp.split('.')[0], '%Y-%m-%d %H:%M:%S')
    else:
        exp_dt = exp
    diff = exp_dt - datetime.utcnow()
    remaining_days = max(0, diff.days)
    remaining_hours = max(0, int(diff.total_seconds() / 3600))
    
    # Calculate uptime if running
    start_time = SERVER_START_TIMES.get(server['id'], 0) if server['status'] == 'running' else 0
    if server['status'] == 'running' and not start_time:
        if server['pid']:
            try:
                import psutil
                if psutil.pid_exists(server['pid']):
                    start_time = psutil.Process(server['pid']).create_time()
                    SERVER_START_TIMES[server['id']] = start_time
                else:
                    start_time = time.time()
                    SERVER_START_TIMES[server['id']] = start_time
            except Exception:
                start_time = time.time()
                SERVER_START_TIMES[server['id']] = start_time
        else:
            start_time = time.time()
            SERVER_START_TIMES[server['id']] = start_time

    uptime_display = "0m"
    if start_time > 0 and server['status'] == 'running':
        secs = int(time.time() - start_time)
        mins = secs // 60
        hrs = mins // 60
        if hrs > 0:
            uptime_display = f"{hrs}h {mins % 60}m"
        else:
            uptime_display = f"{mins}m {secs % 60}s"
            
    server_dir = get_server_dir(server['user_id'], server_id)
    scan = scan_and_analyze_project(server_dir, server_id)
    packages = db.execute("SELECT * FROM packages WHERE active = 1 AND is_first_time_offer = 0 ORDER BY days ASC").fetchall()
    
    return render_template(
        'server_manage.html',
        server=server,
        scan=scan,
        remaining_days=remaining_days,
        remaining_hours=remaining_hours,
        uptime_display=uptime_display,
        start_time=start_time,
        packages=packages
    )

# RENEW / EXTEND SERVER
@app.route('/api/servers/<int:server_id>/renew', methods=['POST'])
@login_required
def renew_server(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    user = get_current_user()
    db = get_db()
    package_id = request.json.get('package_id') or request.form.get('package_id')
    
    pkg = db.execute("SELECT * FROM packages WHERE id = ? AND is_first_time_offer = 0", (package_id,)).fetchone()
    if not pkg:
        return jsonify({'success': False, 'message': 'Invalid extension package'}), 400
        
    if user['coins'] < pkg['coins']:
        return jsonify({'success': False, 'message': f'Insufficient coins! Need {pkg["coins"]} coins, you have {user["coins"]}'}), 400
        
    # Extend expiration
    current_exp = server['expires_at']
    if isinstance(current_exp, str):
        current_exp_dt = datetime.strptime(current_exp.split('.')[0], '%Y-%m-%d %H:%M:%S')
    else:
        current_exp_dt = current_exp
        
    # If already expired, base new expiration from now
    base_time = max(datetime.utcnow(), current_exp_dt)
    new_expires_at = base_time + timedelta(days=pkg['days'])
    
    new_balance = user['coins'] - pkg['coins']
    db.execute("UPDATE users SET coins = ? WHERE id = ?", (new_balance, user['id']))
    db.execute("UPDATE servers SET expires_at = ?, status = CASE WHEN status = 'expired' THEN 'stopped' ELSE status END WHERE id = ?", (new_expires_at, server_id))
    
    db.execute('''
        INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type)
        VALUES (?, ?, ?, ?, 'debit')
    ''', (user['id'], -pkg['coins'], new_balance, f"-{pkg['coins']} Coins Renewal for {server['name']} (+{pkg['days']} Days)"))
    
    db.execute('''
        INSERT INTO notifications (user_id, title, message)
        VALUES (?, 'Server Renewed', ?)
    ''', (user['id'], f"Server '{server['name']}' was successfully renewed for +{pkg['days']} days."))

    write_server_log(server_id, 'INFO', f"Server renewed for +{pkg['days']} Days with {pkg['name']}.")
    db.commit()
    
    return jsonify({
        'success': True,
        'message': f"Server successfully extended by {pkg['days']} days!",
        'new_expiration': new_expires_at.strftime('%Y-%m-%d %H:%M:%S'),
        'new_coins': new_balance
    })

# SERVER ACTIONS (START, STOP, RESTART)
@app.route('/api/servers/<int:server_id>/action', methods=['POST'])
@login_required
def server_action(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    action = request.json.get('action') if request.is_json else request.form.get('action')
    
    if action == 'start':
        res = start_server_process(server_id)
        if len(res) == 4:
            success, msg, missing_pkgs, no_entry_file = res
        else:
            success, msg, missing_pkgs = res
            no_entry_file = False

        if not success:
            if no_entry_file or "Please upload your project files" in msg:
                return jsonify({
                    'success': False,
                    'no_entry_file': True,
                    'message': "Please upload your project files and main entry file before starting the server.",
                    'redirect_url': url_for('file_manager', server_id=server_id),
                    'pid': 0
                })
            if missing_pkgs:
                return jsonify({
                    'success': False,
                    'package_required': True,
                    'missing_packages': missing_pkgs,
                    'message': msg,
                    'status': 'package_required',
                    'pid': 0
                })
            return jsonify({'success': False, 'message': msg, 'status': 'stopped', 'pid': 0})
        
        updated_server = check_server_ownership(server_id)
        current_pid = updated_server['pid'] if (updated_server and updated_server['status'] == 'running') else 0
        start_time = SERVER_START_TIMES.get(server_id, time.time())
        return jsonify({'success': True, 'message': msg, 'status': 'running', 'pid': current_pid, 'start_time': start_time})
    elif action == 'stop':
        stop_server_process(server_id)
        return jsonify({'success': True, 'message': 'Server stopped successfully', 'status': 'stopped', 'pid': 0, 'start_time': 0})
    elif action == 'restart':
        stop_server_process(server_id)
        time.sleep(0.5)
        res = start_server_process(server_id)
        if len(res) == 4:
            success, msg, missing_pkgs, no_entry_file = res
        else:
            success, msg, missing_pkgs = res
            no_entry_file = False

        if not success:
            if no_entry_file or "Please upload your project files" in msg:
                return jsonify({
                    'success': False,
                    'no_entry_file': True,
                    'message': "Please upload your project files and main entry file before starting the server.",
                    'redirect_url': url_for('file_manager', server_id=server_id),
                    'pid': 0
                })
            if missing_pkgs:
                return jsonify({
                    'success': False,
                    'package_required': True,
                    'missing_packages': missing_pkgs,
                    'message': msg,
                    'status': 'package_required',
                    'pid': 0
                })
            return jsonify({'success': False, 'message': msg, 'status': 'stopped', 'pid': 0, 'start_time': 0})
        
        updated_server = check_server_ownership(server_id)
        current_pid = updated_server['pid'] if (updated_server and updated_server['status'] == 'running') else 0
        start_time = SERVER_START_TIMES.get(server_id, time.time()) if success else 0
        return jsonify({'success': success, 'message': 'Server restarted successfully' if success else msg, 'status': 'running' if success else 'stopped', 'pid': current_pid if success else 0, 'start_time': start_time})
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400

# 10. LIVE LOGS API
@app.route('/api/servers/<int:server_id>/logs')
@login_required
def get_server_logs(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'error': 'Server not found'}), 404
        
    server_dir = get_server_dir(server['user_id'], server_id)
    log_file_path = os.path.join(server_dir, 'server.log')
    
    logs_content = ""
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read last 300 lines
                lines = f.readlines()
                logs_content = "".join(lines[-300:])
        except Exception as e:
            logs_content = f"[ERROR] Could not read log file: {str(e)}"
            
    # Also fetch database log entries
    db = get_db()
    db_logs = db.execute(
        "SELECT level, message, created_at FROM server_logs WHERE server_id = ? ORDER BY id DESC LIMIT 50",
        (server_id,)
    ).fetchall()
    
    db_log_list = [{"level": r['level'], "message": sanitize_log_text(r['message']), "time": str(r['created_at'])} for r in reversed(db_logs)]
    
    missing_pkg = None
    if server['status'] == 'package_required':
        scan = scan_and_analyze_project(server_dir, server_id)
        if scan['missing_packages']:
            missing_pkg = scan['missing_packages'][0]['name']
        elif os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as lf:
                log_tail = "".join(lf.readlines()[-30:])
                match = re.search(r"ModuleNotFoundError:\s+No module named\s+'([^']+)'", log_tail)
                if not match:
                    match = re.search(r"ImportError:\s+No module named\s+([^\s\n\r]+)", log_tail)
                if match:
                    mod = match.group(1).split('.')[0]
                    missing_pkg = IMPORT_TO_PACKAGE_MAP.get(mod, {'pkg': mod})['pkg']

    current_pid = server['pid'] if (server and server['status'] == 'running') else 0
    start_time = SERVER_START_TIMES.get(server_id, 0) if server['status'] == 'running' else 0

    return jsonify({
        'raw_logs': sanitize_log_text(logs_content),
        'db_logs': db_log_list,
        'status': server['status'],
        'pid': current_pid,
        'missing_package': missing_pkg,
        'start_time': start_time
    })

@app.route('/api/servers/<int:server_id>/logs/clear', methods=['POST'])
@login_required
def clear_server_logs(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'error': 'Server not found'}), 404
        
    server_dir = get_server_dir(server['user_id'], server_id)
    log_file_path = os.path.join(server_dir, 'server.log')
    
    try:
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Logs cleared by user.\n")
        db = get_db()
        db.execute("DELETE FROM server_logs WHERE server_id = ?", (server_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Logs cleared successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 11. FILE MANAGER
def is_safe_path(base_dir, path, follow_symlinks=True):
    if follow_symlinks:
        matchpath = os.path.realpath(path)
    else:
        matchpath = os.path.abspath(path)
    return base_dir == os.path.commonpath((base_dir, matchpath))

@app.route('/servers/<int:server_id>/files')
@login_required
def file_manager(server_id):
    update_server_statuses()
    server = check_server_ownership(server_id)
    if not server:
        abort(404)
        
    db = get_db()
    packages = db.execute("SELECT * FROM packages WHERE active = 1 AND is_first_time_offer = 0 ORDER BY days ASC").fetchall()
        
    req_path = request.args.get('path', '').strip('/')
    server_dir = get_server_dir(server['user_id'], server_id)
    target_dir = os.path.join(server_dir, req_path)
    
    if not is_safe_path(server_dir, target_dir) or not os.path.exists(target_dir):
        flash('Invalid directory path.', 'danger')
        return redirect(url_for('file_manager', server_id=server_id))
        
    items = []
    try:
        for entry in os.scandir(target_dir):
            stat = entry.stat()
            is_dir = entry.is_dir()
            size = stat.st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
                
            items.append({
                'name': entry.name,
                'is_dir': is_dir,
                'size': size_str if not is_dir else '-',
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'is_zip': entry.name.lower().endswith('.zip'),
                'is_py': entry.name.lower().endswith('.py'),
                'is_entry': entry.name == server['entry_file']
            })
    except Exception as e:
        flash(f'Error reading directory: {str(e)}', 'danger')
        
    # Sort folders first, then files
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    
    breadcrumbs = []
    if req_path:
        parts = req_path.split('/')
        accum = ""
        for p in parts:
            accum = f"{accum}/{p}" if accum else p
            breadcrumbs.append({'name': p, 'path': accum})
            
    return render_template(
        'file_manager.html',
        server=server,
        items=items,
        current_path=req_path,
        breadcrumbs=breadcrumbs,
        packages=packages
    )

# File actions: Create Folder, Create File, Upload, Edit, Rename, Delete, Download, Unzip
@app.route('/api/servers/<int:server_id>/files/create-folder', methods=['POST'])
@login_required
def create_folder(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    req_path = request.form.get('path', '').strip('/')
    folder_name = secure_filename(request.form.get('folder_name', '').strip())
    if not folder_name:
        return jsonify({'success': False, 'message': 'Invalid folder name'}), 400
        
    server_dir = get_server_dir(server['user_id'], server_id)
    target = os.path.join(server_dir, req_path, folder_name)
    
    if not is_safe_path(server_dir, target):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
        
    try:
        os.makedirs(target, exist_ok=False)
        return jsonify({'success': True, 'message': f'Folder "{folder_name}" created.'})
    except FileExistsError:
        return jsonify({'success': False, 'message': 'Folder already exists.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/create-file', methods=['POST'])
@login_required
def create_file(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    req_path = request.form.get('path', '').strip('/')
    file_name = secure_filename(request.form.get('file_name', '').strip())
    if not file_name:
        return jsonify({'success': False, 'message': 'Invalid file name'}), 400
        
    server_dir = get_server_dir(server['user_id'], server_id)
    target = os.path.join(server_dir, req_path, file_name)
    
    if not is_safe_path(server_dir, target):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
        
    try:
        if os.path.exists(target):
            return jsonify({'success': False, 'message': 'File already exists'}), 400
        with open(target, 'w', encoding='utf-8') as f:
            f.write('')
        return jsonify({'success': True, 'message': f'File "{file_name}" created.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/upload', methods=['POST'])
@login_required
def upload_file(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    req_path = request.form.get('path', '').strip('/')
    server_dir = get_server_dir(server['user_id'], server_id)
    target_dir = os.path.join(server_dir, req_path)
    
    if not is_safe_path(server_dir, target_dir):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
        
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'No files selected'}), 400
        
    uploaded_files = request.files.getlist('files')
    count = 0
    extracted_zip_count = 0
    uploaded_names = []
    
    for f in uploaded_files:
        if f and f.filename:
            filename = secure_filename(f.filename)
            save_path = os.path.join(target_dir, filename)
            f.save(save_path)
            
            # Check if uploaded file is a ZIP archive
            if filename.lower().endswith('.zip') or zipfile.is_zipfile(save_path):
                try:
                    with zipfile.ZipFile(save_path, 'r') as zf:
                        for member in zf.namelist():
                            member_path = os.path.abspath(os.path.join(target_dir, member))
                            if not is_safe_path(server_dir, member_path):
                                os.remove(save_path)
                                return jsonify({'success': False, 'message': f'Unsafe path in ZIP file: {member}'}), 400
                        zf.extractall(target_dir)
                    extracted_zip_count += 1
                    os.remove(save_path)  # Delete zip so extracted files are shown directly
                    uploaded_names.append(f"{filename} (Extracted)")
                except Exception as ze:
                    # Fallback if zip extraction fails
                    count += 1
                    uploaded_names.append(filename)
            else:
                count += 1
                uploaded_names.append(filename)
            
    # Perform background file inspection
    scan = scan_and_analyze_project(server_dir, server_id)
    db = get_db()
    if scan['entry_file'] and (not server['entry_file'] or server['entry_file'] not in scan['py_files']):
        db.execute("UPDATE servers SET entry_file = ? WHERE id = ?", (scan['entry_file'], server_id))
        db.commit()
        
    total_processed = count + extracted_zip_count
    if extracted_zip_count > 0:
        msg = f"Uploaded and auto-extracted {extracted_zip_count} ZIP archive(s)."
        if count > 0:
            msg += f" Uploaded {count} regular file(s)."
    else:
        msg = f'{count} file(s) uploaded successfully.'

    write_server_log(server_id, 'INFO', f"Uploaded & processed: {', '.join(uploaded_names[:3])}")
    
    return jsonify({
        'success': True,
        'message': msg,
        'scan': scan,
        'package_required': False
    })

@app.route('/api/servers/<int:server_id>/files/read', methods=['GET'])
@login_required
def read_file_content(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    file_path = request.args.get('path', '').strip('/')
    server_dir = get_server_dir(server['user_id'], server_id)
    target = os.path.join(server_dir, file_path)
    
    if not is_safe_path(server_dir, target) or not os.path.isfile(target):
        return jsonify({'success': False, 'message': 'File not found'}), 404
        
    try:
        with open(target, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return jsonify({'success': True, 'content': content, 'filename': os.path.basename(target)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/save', methods=['POST'])
@login_required
def save_file_content(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    file_path = request.json.get('path', '').strip('/') if request.is_json else request.form.get('path', '').strip('/')
    content = request.json.get('content', '') if request.is_json else request.form.get('content', '')
    
    server_dir = get_server_dir(server['user_id'], server_id)
    target = os.path.join(server_dir, file_path)
    
    if not is_safe_path(server_dir, target):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
        
    try:
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': 'File saved successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/delete', methods=['POST'])
@login_required
def delete_file(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    target_path = request.json.get('path', '').strip('/') if request.is_json else request.form.get('path', '').strip('/')
    server_dir = get_server_dir(server['user_id'], server_id)
    target = os.path.join(server_dir, target_path)
    
    if not is_safe_path(server_dir, target) or target == server_dir:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
        
    try:
        if os.path.isdir(target):
            shutil.rmtree(target)
        elif os.path.isfile(target):
            os.remove(target)
        return jsonify({'success': True, 'message': 'Item deleted successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/rename', methods=['POST'])
@login_required
def rename_file(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    old_path = request.json.get('old_path', '').strip('/') if request.is_json else request.form.get('old_path', '').strip('/')
    new_name = secure_filename(request.json.get('new_name', '').strip() if request.is_json else request.form.get('new_name', '').strip())
    
    if not new_name:
        return jsonify({'success': False, 'message': 'Invalid new name'}), 400
        
    server_dir = get_server_dir(server['user_id'], server_id)
    source = os.path.join(server_dir, old_path)
    dest = os.path.join(os.path.dirname(source), new_name)
    
    if not is_safe_path(server_dir, source) or not is_safe_path(server_dir, dest):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
        
    try:
        os.rename(source, dest)
        return jsonify({'success': True, 'message': f'Renamed to {new_name}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/servers/<int:server_id>/files/download')
@login_required
def download_file(server_id):
    server = check_server_ownership(server_id)
    if not server:
        abort(404)
        
    file_path = request.args.get('path', '').strip('/')
    server_dir = get_server_dir(server['user_id'], server_id)
    target = os.path.join(server_dir, file_path)
    
    if not is_safe_path(server_dir, target) or not os.path.isfile(target):
        abort(404)
        
    return send_file(target, as_attachment=True)

# Safe ZIP Unzip / Extraction
@app.route('/api/servers/<int:server_id>/files/unzip', methods=['POST'])
@login_required
def unzip_file(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    zip_path = request.json.get('path', '').strip('/') if request.is_json else request.form.get('path', '').strip('/')
    server_dir = get_server_dir(server['user_id'], server_id)
    target_zip = os.path.join(server_dir, zip_path)
    extract_dir = os.path.dirname(target_zip)
    
    if not is_safe_path(server_dir, target_zip) or not os.path.isfile(target_zip):
        return jsonify({'success': False, 'message': 'ZIP file not found'}), 404
        
    try:
        with zipfile.ZipFile(target_zip, 'r') as zf:
            for member in zf.namelist():
                # Safe Zip-Slip prevention
                member_path = os.path.abspath(os.path.join(extract_dir, member))
                if not is_safe_path(server_dir, member_path):
                    return jsonify({'success': False, 'message': f'Unsafe path in zip file: {member}'}), 400
            zf.extractall(extract_dir)
            
        write_server_log(server_id, 'INFO', f"Extracted ZIP archive '{os.path.basename(target_zip)}' safely.")
        
        # 1. Project Scan after ZIP Extraction
        scan = scan_and_analyze_project(server_dir, server_id)
        db = get_db()
        
        # 2. Auto-detect & set entry file
        if scan['entry_file']:
            db.execute("UPDATE servers SET entry_file = ? WHERE id = ?", (scan['entry_file'], server_id))
            db.commit()
            write_server_log(server_id, 'INFO', f"Startup file detected: {scan['entry_file']}")
            
        write_server_log(server_id, 'INFO', f"Checking Python environment: {server['python_version']}")
        write_server_log(server_id, 'INFO', "Checking dependencies...")
        
        write_server_log(server_id, 'INFO', "ZIP contents extracted successfully.")
            
        return jsonify({
            'success': True,
            'message': 'ZIP extracted and project analyzed successfully!',
            'scan': scan,
            'package_required': False,
            'missing_packages': scan['missing_packages']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Extraction failed: {str(e)}'}), 500

# 12. PACKAGE INSTALLER & DEPENDENCY MANAGEMENT
POPULAR_PACKAGES = [
    {"name": "pyTelegramBotAPI", "import_name": "telebot", "desc": "Telegram Bot API library for Python (telebot)", "version": "4.26.0"},
    {"name": "python-telegram-bot", "import_name": "telegram", "desc": "Pure Python interface for Telegram Bot API", "version": "21.4"},
    {"name": "aiogram", "import_name": "aiogram", "desc": "Modern and fast asynchronous framework for Telegram Bot API", "version": "3.13.1"},
    {"name": "discord.py", "import_name": "discord", "desc": "API wrapper for Discord bots in Python", "version": "2.4.0"},
    {"name": "requests", "import_name": "requests", "desc": "HTTP library for human beings", "version": "2.32.3"},
    {"name": "beautifulsoup4", "import_name": "bs4", "desc": "Screen-scraping and HTML parsing library", "version": "4.12.3"},
    {"name": "colorama", "import_name": "colorama", "desc": "Cross-platform colored terminal text", "version": "0.4.6"},
    {"name": "Flask", "import_name": "flask", "desc": "Lightweight WSGI web application framework", "version": "3.0.3"},
    {"name": "aiohttp", "import_name": "aiohttp", "desc": "Async HTTP client/server for asyncio", "version": "3.10.5"},
    {"name": "python-dotenv", "import_name": "dotenv", "desc": "Reads key-value pairs from a .env file", "version": "1.0.1"},
    {"name": "schedule", "import_name": "schedule", "desc": "In-process scheduler for periodic jobs", "version": "1.2.2"},
    {"name": "Pillow", "import_name": "PIL", "desc": "Python Imaging Library (PIL Fork)", "version": "10.4.0"},
    {"name": "numpy", "import_name": "numpy", "desc": "Fundamental package for scientific computing", "version": "2.1.1"},
    {"name": "pandas", "import_name": "pandas", "desc": "Data analysis and manipulation library", "version": "2.2.2"},
    {"name": "PyYAML", "import_name": "yaml", "desc": "YAML parser and emitter for Python", "version": "6.0.2"},
    {"name": "pytz", "import_name": "pytz", "desc": "World timezone definitions for Python", "version": "2024.1"}
]

@app.route('/servers/<int:server_id>/packages')
@login_required
def server_packages(server_id):
    return redirect(url_for('server_manage', server_id=server_id))

@app.route('/api/servers/<int:server_id>/packages/scan')
@login_required
def scan_server_packages(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    server_dir = get_server_dir(server['user_id'], server_id)
    scan = scan_and_analyze_project(server_dir, server_id)
    
    return jsonify({
        'success': True,
        'scan': scan,
        'ready': scan['ready'],
        'missing_count': len(scan['missing_packages']),
        'installed_count': len(scan['installed_packages'])
    })

@app.route('/api/packages/info')
@login_required
def get_package_info():
    pkg_name = request.args.get('name', '').strip()
    if not pkg_name:
        return jsonify({'success': False, 'message': 'Package name required'}), 400
    info = fetch_pypi_package_info(pkg_name)
    return jsonify(info)

@app.route('/api/servers/<int:server_id>/packages/install', methods=['POST'])
@login_required
def install_package(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    package_name = request.json.get('package_name', '').strip() if request.is_json else request.form.get('package_name', '').strip()
    version = request.json.get('version', '').strip() if request.is_json else request.form.get('version', '').strip()
    is_requirements = request.json.get('is_requirements', False) if request.is_json else False
    
    server_dir = get_server_dir(server['user_id'], server_id)
    packages_dir = os.path.join(server_dir, 'packages')
    os.makedirs(packages_dir, exist_ok=True)
    
    # Map import names if needed
    if not is_requirements and package_name in IMPORT_TO_PACKAGE_MAP:
        target_pkg = IMPORT_TO_PACKAGE_MAP[package_name]['pkg']
    else:
        target_pkg = package_name

    install_spec = target_pkg
    if version and version.lower() != 'latest' and '==' not in target_pkg and '>=' not in target_pkg and '<=' not in target_pkg:
        install_spec = f"{target_pkg}=={version}"
        
    display_title = "requirements.txt" if is_requirements else install_spec
    write_server_log(server_id, 'INFO', f"Installing {display_title} via pip into server sandbox...")
    
    cmd = [sys.executable, '-m', 'pip', 'install', '--target', packages_dir]
    if is_requirements:
        req_path = os.path.join(server_dir, 'requirements.txt')
        if not os.path.exists(req_path):
            return jsonify({'success': False, 'message': 'requirements.txt not found in server directory.'}), 400
        cmd.extend(['-r', req_path])
    else:
        if not re.match(r'^[a-zA-Z0-9_\-\.>=<~!=]+$', install_spec):
            return jsonify({'success': False, 'message': 'Invalid package name format.'}), 400
        cmd.append(install_spec)
        
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
        output = res.stdout
        
        # Sanitize logs of any secrets
        output = sanitize_log_text(output)
        
        if res.returncode == 0:
            write_server_log(server_id, 'INFO', f"Package {display_title} installed successfully.")
            
            # Re-scan to check if all missing packages are now satisfied
            scan = scan_and_analyze_project(server_dir, server_id)
            db = get_db()
            if scan['ready']:
                db.execute("UPDATE servers SET status = 'stopped' WHERE id = ? AND status = 'package_required'", (server_id,))
                db.commit()
                write_server_log(server_id, 'INFO', "All project dependencies satisfied. Server ready to run.")
                
            return jsonify({
                'success': True,
                'message': f"Package '{display_title}' installed successfully.",
                'output': output,
                'scan': scan,
                'ready': scan['ready']
            })
        else:
            write_server_log(server_id, 'ERROR', f"Package installation failed for {display_title}")
            return jsonify({
                'success': False,
                'message': f"Installation failed for '{display_title}'. Check output log.",
                'output': output
            }), 400
    except subprocess.TimeoutExpired:
        write_server_log(server_id, 'ERROR', f"Package installation timed out for {display_title}.")
        return jsonify({'success': False, 'message': 'Installation timed out (limit: 180s).'}), 408
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/packages/install-all', methods=['POST'])
@login_required
def install_all_packages(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    server_dir = get_server_dir(server['user_id'], server_id)
    scan = scan_and_analyze_project(server_dir, server_id)
    missing = scan['missing_packages']
    
    if not missing and not scan['has_requirements']:
        return jsonify({'success': True, 'message': 'All packages already installed.', 'installed_count': 0})
        
    packages_dir = os.path.join(server_dir, 'packages')
    os.makedirs(packages_dir, exist_ok=True)
    
    write_server_log(server_id, 'INFO', f"Batch installing {len(missing)} missing package(s)...")
    
    installed_list = []
    failed_list = []
    aggregated_logs = []
    
    # If requirements.txt exists, install that first
    if scan['has_requirements']:
        req_path = os.path.join(server_dir, 'requirements.txt')
        cmd = [sys.executable, '-m', 'pip', 'install', '--target', packages_dir, '-r', req_path]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
            aggregated_logs.append(f"=== requirements.txt ===\n{res.stdout}")
            if res.returncode == 0:
                installed_list.append('requirements.txt')
            else:
                failed_list.append('requirements.txt')
        except Exception as e:
            failed_list.append('requirements.txt')
            aggregated_logs.append(f"=== requirements.txt Error ===\n{str(e)}")

    # Install remaining missing packages one by one
    for pkg in missing:
        pkg_name = pkg['name']
        pkg_ver = pkg['version']
        spec = pkg_name
        if pkg_ver and pkg_ver.lower() != 'latest' and '==' not in pkg_name and '>=' not in pkg_name:
            spec = f"{pkg_name}=={pkg_ver}"
            
        cmd = [sys.executable, '-m', 'pip', 'install', '--target', packages_dir, spec]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            aggregated_logs.append(f"=== {spec} ===\n{res.stdout}")
            if res.returncode == 0:
                installed_list.append(spec)
            else:
                failed_list.append(spec)
        except Exception as e:
            failed_list.append(spec)
            aggregated_logs.append(f"=== {spec} Error ===\n{str(e)}")

    final_scan = scan_and_analyze_project(server_dir, server_id)
    db = get_db()
    if final_scan['ready']:
        db.execute("UPDATE servers SET status = 'stopped' WHERE id = ? AND status = 'package_required'", (server_id,))
        db.commit()
        write_server_log(server_id, 'INFO', "All missing packages successfully installed. Server ready to run.")

    return jsonify({
        'success': len(failed_list) == 0,
        'message': f"Installed {len(installed_list)} package(s)." + (f" Failed: {', '.join(failed_list)}" if failed_list else ""),
        'installed_packages': installed_list,
        'failed_packages': failed_list,
        'logs': "\n".join(aggregated_logs),
        'scan': final_scan,
        'ready': final_scan['ready']
    })

@app.route('/api/servers/<int:server_id>/packages/delete', methods=['POST'])
@login_required
def delete_server_package(server_id):
    server = check_server_ownership(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    pkg_name = request.json.get('package_name', '').strip() if request.is_json else request.form.get('package_name', '').strip()
    if not pkg_name:
        return jsonify({'success': False, 'message': 'Package name required'}), 400
        
    server_dir = get_server_dir(server['user_id'], server_id)
    packages_dir = os.path.join(server_dir, 'packages')
    
    if not os.path.exists(packages_dir):
        return jsonify({'success': True, 'message': 'No packages folder found.'})
        
    pkg_clean = pkg_name.lower().replace('-', '_')
    deleted = 0
    for item in os.listdir(packages_dir):
        item_lower = item.lower().replace('-', '_')
        if item_lower == pkg_clean or item_lower.startswith(f"{pkg_clean}-") or item_lower.startswith(f"{pkg_clean}."):
            target_path = os.path.join(packages_dir, item)
            try:
                if os.path.isdir(target_path):
                    shutil.rmtree(target_path)
                else:
                    os.remove(target_path)
                deleted += 1
            except Exception:
                pass
                
    write_server_log(server_id, 'INFO', f"Removed package '{pkg_name}' from server sandbox.")
    scan = scan_and_analyze_project(server_dir, server_id)
    
    return jsonify({
        'success': True,
        'message': f"Package '{pkg_name}' uninstalled.",
        'scan': scan
    })

# 13. STARTUP CONFIGURATION
@app.route('/servers/<int:server_id>/startup', methods=['GET', 'POST'])
@login_required
def server_startup(server_id):
    update_server_statuses()
    server = check_server_ownership(server_id)
    if not server:
        abort(404)
        
    server_dir = get_server_dir(server['user_id'], server_id)
    db = get_db()
    packages = db.execute("SELECT * FROM packages WHERE active = 1 AND is_first_time_offer = 0 ORDER BY days ASC").fetchall()
    
    if request.method == 'POST':
        entry_file = secure_filename(request.form.get('entry_file', 'main.py').strip())
        python_version = request.form.get('python_version', 'Python 3.10')
        auto_restart = 1 if request.form.get('auto_restart') == 'on' else 0
        
        db.execute(
            "UPDATE servers SET entry_file = ?, python_version = ?, auto_restart = ? WHERE id = ?",
            (entry_file, python_version, auto_restart, server_id)
        )
        db.commit()
        write_server_log(server_id, 'INFO', f"Updated startup settings: Entry={entry_file}, Python={python_version}")
        flash('Startup settings updated successfully!', 'success')
        return redirect(url_for('server_startup', server_id=server_id))
        
    # Auto-detect candidates
    py_files = []
    for f in os.listdir(server_dir):
        if f.endswith('.py') and os.path.isfile(os.path.join(server_dir, f)):
            py_files.append(f)
            
    # Recommended entry file order: main.py > app.py > bot.py > server.py
    detected_entry = 'main.py'
    for candidate in ['main.py', 'app.py', 'bot.py', 'server.py']:
        if candidate in py_files:
            detected_entry = candidate
            break
    if not py_files:
        py_files = ['main.py']
        
    return render_template(
        'startup.html',
        server=server,
        py_files=py_files,
        detected_entry=detected_entry,
        system_python=f"Python {sys.version.split()[0]}",
        packages=packages
    )

# ----------------- ADMIN PANEL -----------------

@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_servers = db.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
    active_users = db.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
    disabled_users = db.execute("SELECT COUNT(*) FROM users WHERE status = 'disabled'").fetchone()[0]
    total_coins = db.execute("SELECT SUM(coins) FROM users").fetchone()[0] or 0
    
    # Calculate all server files and storage
    total_files = 0
    total_bytes = 0
    if os.path.exists(SERVERS_DIR):
        for root, dirs, files in os.walk(SERVERS_DIR):
            total_files += len(files)
            for f in files:
                try:
                    total_bytes += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass
                    
    storage_formatted = f"{total_bytes / (1024 * 1024):.1f} MB" if total_bytes > 1024*1024 else f"{total_bytes / 1024:.1f} KB"
    recent_users = db.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 6").fetchall()
    recent_audit = db.execute("SELECT * FROM admin_audit_logs ORDER BY created_at DESC LIMIT 8").fetchall()
    
    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_servers=total_servers,
        active_users=active_users,
        disabled_users=disabled_users,
        total_coins=total_coins,
        total_files=total_files,
        storage_formatted=storage_formatted,
        recent_users=recent_users,
        recent_audit=recent_audit
    )

# Admin User Management
@app.route('/admin/users')
@admin_permission_required('manage_users')
def admin_users():
    search = request.args.get('q', '').strip()
    db = get_db()
    if search:
        users = db.execute(
            "SELECT * FROM users WHERE email LIKE ? OR username LIKE ? OR full_name LIKE ? ORDER BY id DESC",
            (f'%{search}%', f'%{search}%', f'%{search}%')
        ).fetchall()
    else:
        users = db.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    return render_template('admin/users.html', users=users, search=search)

@app.route('/admin/users/<int:user_id>/update', methods=['POST'])
@admin_permission_required('manage_users')
def admin_update_user(user_id):
    db = get_db()
    current_admin = get_current_user()
    curr_is_super = is_user_super_admin(current_admin)

    target_user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target_user:
        flash('Target user not found.', 'danger')
        return redirect(url_for('admin_users'))

    target_is_super = is_user_super_admin(target_user)

    # Standard sub-admins cannot edit a Super Admin account
    if target_is_super and not curr_is_super:
        flash("Access Denied: Only Super Admins can modify a Super Admin account.", 'danger')
        return redirect(url_for('admin_users'))

    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip().lower()
    email = request.form.get('email', '').strip().lower()
    bio = request.form.get('bio', '').strip()
    status = request.form.get('status', target_user['status']).strip().lower()
    role_input = request.form.get('role', target_user['role']).strip().lower()
    coins_raw = request.form.get('coins')
    new_password = request.form.get('new_password', '').strip()

    # Determine final role and permissions
    if curr_is_super:
        final_role = role_input
        if final_role == 'super_admin':
            final_is_admin = 1
            final_is_super = 1
            final_perms = 'manage_users,manage_coins,manage_files,manage_settings,manage_announcements,manage_broadcasts,view_logs'
        elif final_role == 'admin':
            final_is_admin = 1
            final_is_super = 0
            selected_perms = request.form.getlist('permissions')
            final_perms = ','.join(selected_perms) if selected_perms else 'manage_users,manage_coins,manage_files,manage_settings,manage_announcements,manage_broadcasts,view_logs'
        else:
            final_role = 'user'
            final_is_admin = 0
            final_is_super = 0
            final_perms = ''
    else:
        # Sub-admins cannot change roles or admin permissions
        if role_input != target_user['role']:
            flash("Access Denied: Only Super Admins can promote/demote admin roles or modify permissions.", 'warning')
        final_role = target_user['role']
        final_is_admin = target_user['is_admin']
        final_is_super = target_user['is_super_admin']
        final_perms = target_user['admin_permissions']

    if not full_name or not username or not email:
        flash('Full Name, Username, and Email cannot be empty.', 'danger')
        return redirect(url_for('admin_users'))

    # Strict Gmail format validation for email
    if not email.endswith('@gmail.com') or email == '@gmail.com' or len(email.split('@')[0]) < 1:
        flash('User email must strictly be a valid Gmail address (ending with @gmail.com).', 'danger')
        return redirect(url_for('admin_users'))

    if len(username) < 3:
        flash('Username must be at least 3 characters.', 'danger')
        return redirect(url_for('admin_users'))

    # Check unique email across other accounts (case-insensitive)
    existing_email = db.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?) AND id != ?", (email, user_id)).fetchone()
    if existing_email:
        flash(f"Gmail address '{email}' is already in use by another user account.", 'danger')
        return redirect(url_for('admin_users'))

    # Check unique username across other accounts (case-insensitive)
    existing_user = db.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?) AND id != ?", (username, user_id)).fetchone()
    if existing_user:
        flash(f"Username '@{username}' is already taken by another user account.", 'danger')
        return redirect(url_for('admin_users'))

    # Coins update if provided
    try:
        coins = int(coins_raw) if coins_raw is not None and coins_raw != '' else target_user['coins']
    except ValueError:
        coins = target_user['coins']

    # If coins changed by admin, log transaction and notify user
    if coins != target_user['coins']:
        diff = coins - target_user['coins']
        if diff > 0:
            notif_title = "🪙 Coins Credited"
            notif_msg = f"Administrator adjusted your coin balance (+{diff} coins). New balance: {coins} coins."
            tx_type = 'credit'
        else:
            notif_title = "🪙 Coins Deducted"
            notif_msg = f"Administrator adjusted your coin balance (-{abs(diff)} coins). New balance: {coins} coins."
            tx_type = 'debit'
        
        db.execute(
            "INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?, ?, ?, ?, ?)",
            (user_id, diff, coins, f"Admin account edit ({diff:+d} coins)", tx_type)
        )
        db.execute(
            "INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
            (user_id, notif_title, notif_msg)
        )

    # Password update if provided
    if new_password:
        if len(new_password) < 6:
            flash('New password must be at least 6 characters.', 'danger')
            return redirect(url_for('admin_users'))
        pw_hash = safe_generate_password_hash(new_password)
        db.execute(
            """UPDATE users 
               SET full_name = ?, username = ?, email = ?, bio = ?, coins = ?, status = ?, 
                   role = ?, is_admin = ?, is_super_admin = ?, admin_permissions = ?, password_hash = ? 
               WHERE id = ?""",
            (full_name, username, email, bio, max(0, coins), status, final_role, final_is_admin, final_is_super, final_perms, pw_hash, user_id)
        )
    else:
        db.execute(
            """UPDATE users 
               SET full_name = ?, username = ?, email = ?, bio = ?, coins = ?, status = ?, 
                   role = ?, is_admin = ?, is_super_admin = ?, admin_permissions = ? 
               WHERE id = ?""",
            (full_name, username, email, bio, max(0, coins), status, final_role, final_is_admin, final_is_super, final_perms, user_id)
        )
    db.commit()

    # If status changed to disabled, stop user servers
    if status == 'disabled' and target_user['status'] != 'disabled':
        servers = db.execute("SELECT id FROM servers WHERE user_id = ?", (user_id,)).fetchall()
        for s in servers:
            stop_server_process(s['id'])

    log_admin_action(
        'Updated User Account',
        f"User #{user_id} (@{username})",
        f"Admin modified: Name='{full_name}', Email='{email}', Username='{username}', Coins={coins}, Status={status}, Role={final_role}, Perms={final_perms}"
    )
    flash(f"User profile for '{full_name}' (@{username}) updated successfully.", 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_permission_required('manage_users')
def admin_toggle_user_status(user_id):
    db = get_db()
    current_admin = get_current_user()
    curr_is_super = is_user_super_admin(current_admin)
    
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('admin_users'))
        
    if is_user_admin(user) and not curr_is_super:
        flash('Only Super Admins can disable administrator accounts.', 'danger')
        return redirect(url_for('admin_users'))
        
    new_status = 'disabled' if user['status'] == 'active' else 'active'
    db.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
    db.commit()
    
    # If disabled, halt running servers for this user
    if new_status == 'disabled':
        servers = db.execute("SELECT id FROM servers WHERE user_id = ?", (user_id,)).fetchall()
        for s in servers:
            stop_server_process(s['id'])
            
    log_admin_action(
        f"User status changed to {new_status}",
        f"User #{user_id} ({user['username']})",
        f"Status toggled from {user['status']} to {new_status}"
    )
    flash(f"User {user['username']} has been {new_status}.", 'success')
    return redirect(url_for('admin_users'))

# Admin Impersonate / Support Login
@app.route('/admin/users/<int:user_id>/impersonate')
@admin_permission_required('manage_users')
def admin_impersonate(user_id):
    db = get_db()
    target_user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target_user:
        flash('Target user not found.', 'danger')
        return redirect(url_for('admin_users'))
        
    log_admin_action('Support Login / Impersonation', f"User #{user_id} ({target_user['username']})", 'Entered user support mode')
    
    # Store real admin in session
    session['real_admin_id'] = session['user_id']
    session['real_admin_username'] = session['username']
    session['is_impersonating'] = True
    
    # Switch session
    session['user_id'] = target_user['id']
    session['username'] = target_user['username']
    session['role'] = target_user['role']
    
    flash(f"Authorized Support Mode: Viewing as {target_user['full_name']} ({target_user['username']}).", 'info')
    return redirect(url_for('dashboard'))

@app.route('/admin/stop-impersonate')
def stop_impersonating():
    if not session.get('is_impersonating'):
        return redirect(url_for('dashboard'))
        
    real_id = session.get('real_admin_id')
    db = get_db()
    admin_user = db.execute("SELECT * FROM users WHERE id = ?", (real_id,)).fetchone()
    if admin_user:
        session.clear()
        session['user_id'] = admin_user['id']
        session['username'] = admin_user['username']
        session['role'] = admin_user['role']
        flash('Returned safely to Administrator control panel.', 'success')
        return redirect(url_for('admin_users'))
    else:
        session.clear()
        return redirect(url_for('signin'))

# Admin Coin Management
@app.route('/admin/coins', methods=['GET', 'POST'])
@admin_permission_required('manage_coins')
def admin_coins():
    db = get_db()
    user_match = None
    email_query = request.args.get('email', '').strip().lower()
    
    if email_query:
        user_match = db.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email_query,)).fetchone()
        
    if request.method == 'POST':
        # Accept target email from either 'email' or 'user_identifier' form fields
        target_email = (request.form.get('email') or request.form.get('user_identifier') or '').strip().lower()
        amount_raw = request.form.get('amount', '0').strip()
        action_type = request.form.get('action_type', '').strip()
        reason = (request.form.get('reason') or 'Admin adjustment').strip()
        
        try:
            amount_val = int(amount_raw)
        except ValueError:
            amount_val = 0
            
        if not target_email:
            flash('Target user email address is required.', 'danger')
            return redirect(url_for('admin_coins'))

        # Direct, case-insensitive search strictly by target user's email address
        target_user = db.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (target_email,)).fetchone()
        if not target_user:
            flash(f"Target user with email '{target_email}' was not found. Please verify the Gmail address.", 'danger')
            return redirect(url_for('admin_coins', email=target_email))
            
        if amount_val == 0:
            flash('Coin adjustment amount cannot be 0.', 'danger')
            return redirect(url_for('admin_coins', email=target_email))

        # Handle direction based on action_type or signed integer input
        if action_type == 'remove':
            adj_amount = -abs(amount_val)
        elif action_type == 'add':
            adj_amount = abs(amount_val)
        else:
            adj_amount = amount_val

        current_balance = int(target_user['coins'] or 0)
        new_balance = max(0, current_balance + adj_amount)
        
        if adj_amount < 0:
            desc = f"Admin deduction ({adj_amount} Coins): {reason}"
            tx_type = 'debit'
            op_label = 'deducted'
        else:
            desc = f"Admin grant (+{adj_amount} Coins): {reason}"
            tx_type = 'credit'
            op_label = 'added'
            
        db.execute("UPDATE users SET coins = ? WHERE id = ?", (new_balance, target_user['id']))
        db.execute('''
            INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (target_user['id'], adj_amount, new_balance, desc, tx_type))
        
        # Send in-app notification to the user
        if adj_amount > 0:
            notif_title = "🪙 Coins Credited"
            notif_msg = f"Administrator credited +{adj_amount} coins to your account balance! Note: {reason}. Your new balance is {new_balance} coins."
        else:
            notif_title = "🪙 Coins Deducted"
            notif_msg = f"Administrator deducted {abs(adj_amount)} coins from your account balance. Note: {reason}. Your new balance is {new_balance} coins."

        db.execute('''
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, ?, ?)
        ''', (target_user['id'], notif_title, notif_msg))
        
        log_admin_action(
            f"Coin adjustment ({op_label})",
            f"User #{target_user['id']} ({target_user['email']})",
            f"Amount: {adj_amount:+d}, New Balance: {new_balance}, Reason: {reason}"
        )
        db.commit()
        
        flash(f"Successfully {op_label} {abs(adj_amount)} coins for {target_user['full_name']} ({target_user['email']}). New balance: {new_balance} coins.", 'success')
        return redirect(url_for('admin_coins', email=target_email))
        
    recent_transactions = db.execute('''
        SELECT ct.*, u.username, u.email, u.full_name
        FROM coin_transactions ct 
        JOIN users u ON ct.user_id = u.id 
        ORDER BY ct.created_at DESC LIMIT 25
    ''').fetchall()

    users_list = db.execute('''
        SELECT id, full_name, username, email, coins, status 
        FROM users 
        ORDER BY coins DESC LIMIT 30
    ''').fetchall()

    total_system_coins = db.execute("SELECT COALESCE(SUM(coins), 0) FROM users").fetchone()[0]
    
    return render_template(
        'admin/coins.html', 
        user_match=user_match, 
        email_query=email_query, 
        recent_transactions=recent_transactions,
        users=users_list,
        total_system_coins=total_system_coins
    )

# Admin File Management & Direct Downloads (Crash-proof with robust error handling)
@app.route('/admin/files')
@admin_permission_required('manage_files')
def admin_files():
    query = request.args.get('q', '').strip().lower()
    try:
        db = get_db()
        if query:
            servers = db.execute('''
                SELECT s.*, u.username, u.email, u.full_name 
                FROM servers s 
                JOIN users u ON s.user_id = u.id 
                WHERE LOWER(s.name) LIKE ? OR LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(u.full_name) LIKE ?
                ORDER BY s.id DESC
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
        else:
            servers = db.execute('''
                SELECT s.*, u.username, u.email, u.full_name 
                FROM servers s 
                JOIN users u ON s.user_id = u.id 
                ORDER BY s.id DESC
            ''').fetchall()
        
        server_file_stats = []
        total_system_files = 0
        total_system_bytes = 0
        
        for s in servers:
            try:
                s_dir = os.path.join(SERVERS_DIR, str(s['user_id']), str(s['id']))
                file_count = 0
                total_size = 0
                file_list = []
                
                if os.path.exists(s_dir) and os.path.isdir(s_dir):
                    for root, dirs, files in os.walk(s_dir):
                        file_count += len(files)
                        for f in files:
                            fp = os.path.join(root, f)
                            try:
                                if os.path.isfile(fp):
                                    sz = os.path.getsize(fp)
                                    total_size += sz
                                    mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')
                                    rel = os.path.relpath(fp, s_dir).replace('\\', '/')
                                    
                                    if sz < 1024:
                                        sz_fmt = f"{sz} B"
                                    elif sz < 1024 * 1024:
                                        sz_fmt = f"{sz / 1024:.1f} KB"
                                    else:
                                        sz_fmt = f"{sz / (1024 * 1024):.2f} MB"
                                        
                                    ext = f.rsplit('.', 1)[-1].lower() if '.' in f else ''
                                    file_list.append({
                                        'name': rel,
                                        'filename': f,
                                        'size': sz,
                                        'size_formatted': sz_fmt,
                                        'modified': mtime,
                                        'ext': ext,
                                        'is_text': ext in {'py', 'txt', 'json', 'md', 'env', 'sh', 'csv', 'yaml', 'yml', 'html', 'css', 'js', 'log', 'ini', 'cfg', 'conf', 'requirements.txt'} or f in {'requirements.txt', 'Procfile', 'Dockerfile', '.env'}
                                    })
                            except Exception:
                                pass
                
                total_system_files += file_count
                total_system_bytes += total_size
                
                file_list.sort(key=lambda x: (0 if x['filename'] == 'main.py' else (1 if 'req' in x['filename'] else 2), x['name']))
                
                if total_size < 1024 * 1024:
                    s_size_fmt = f"{total_size / 1024:.1f} KB"
                else:
                    s_size_fmt = f"{total_size / (1024*1024):.2f} MB"

                server_file_stats.append({
                    'server': s,
                    'file_count': file_count,
                    'storage_raw': total_size,
                    'storage_mb': s_size_fmt,
                    'files': file_list
                })
            except Exception as s_err:
                print(f"[!] Warning reading server #{s['id']} directory: {s_err}")
                server_file_stats.append({
                    'server': s,
                    'file_count': 0,
                    'storage_raw': 0,
                    'storage_mb': '0 KB',
                    'files': []
                })
            
        if total_system_bytes < 1024 * 1024:
            total_storage_formatted = f"{total_system_bytes / 1024:.1f} KB"
        elif total_system_bytes < 1024 * 1024 * 1024:
            total_storage_formatted = f"{total_system_bytes / (1024 * 1024):.2f} MB"
        else:
            total_storage_formatted = f"{total_system_bytes / (1024 * 1024 * 1024):.2f} GB"

        return render_template(
            'admin/files.html', 
            stats=server_file_stats, 
            total_files=total_system_files,
            total_storage_formatted=total_storage_formatted,
            total_servers=len(servers),
            query=query
        )
    except Exception as e:
        print(f"[!] Error loading admin files: {e}")
        flash(f"Notice: Storage inspector loaded with safe fallback mode. Details: {str(e)}", 'warning')
        return render_template(
            'admin/files.html', 
            stats=[], 
            total_files=0,
            total_storage_formatted="0 KB",
            total_servers=0,
            query=query
        )

# Admin Direct Server ZIP Download
@app.route('/admin/servers/<int:server_id>/download-zip')
@admin_permission_required('manage_files')
def admin_download_server_zip(server_id):
    db = get_db()
    server = db.execute('''
        SELECT s.*, u.username, u.email, u.full_name 
        FROM servers s 
        JOIN users u ON s.user_id = u.id 
        WHERE s.id = ?
    ''', (server_id,)).fetchone()
    
    if not server:
        flash('Server not found.', 'danger')
        return redirect(url_for('admin_files'))
        
    server_dir = get_server_dir(server['user_id'], server_id)
    if not os.path.exists(server_dir):
        flash('Server directory does not exist on disk.', 'warning')
        return redirect(url_for('admin_files'))
        
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(server_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, server_dir)
                zf.write(abs_path, arcname=rel_path)
    zip_buffer.seek(0)
    
    clean_sname = re.sub(r'[^a-zA-Z0-9_\-]', '_', server['name'])
    download_filename = f"server_{server_id}_{clean_sname}_{server['username']}.zip"
    
    log_admin_action('Downloaded Project ZIP', f"Server #{server_id} ({server['name']})", f"Owner: {server['email']}")
    
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=download_filename
    )

# Admin Direct Single File Download
@app.route('/admin/servers/<int:server_id>/files/download')
@admin_permission_required('manage_files')
def admin_download_server_file(server_id):
    db = get_db()
    server = db.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    if not server:
        abort(404)
        
    file_path = request.args.get('path', '').strip('/')
    server_dir = get_server_dir(server['user_id'], server_id)
    target = os.path.join(server_dir, file_path)
    
    if not is_safe_path(server_dir, target) or not os.path.isfile(target):
        abort(404)
        
    log_admin_action('Downloaded User File', f"Server #{server_id}", f"File: {file_path}")
    return send_file(target, as_attachment=True)

# Admin Direct File Preview API
@app.route('/admin/api/servers/<int:server_id>/files/read')
@admin_permission_required('manage_files')
def admin_read_server_file(server_id):
    db = get_db()
    server = db.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    if not server:
        return jsonify({'success': False, 'message': 'Server not found'}), 404
        
    file_path = request.args.get('path', '').strip('/')
    server_dir = get_server_dir(server['user_id'], server_id)
    target = os.path.join(server_dir, file_path)
    
    if not is_safe_path(server_dir, target) or not os.path.isfile(target):
        return jsonify({'success': False, 'message': 'File not found on server.'}), 404
        
    try:
        file_size = os.path.getsize(target)
        if file_size > 512 * 1024:
            return jsonify({
                'success': False, 
                'message': 'File is larger than 512 KB. Please use direct download to inspect.'
            }), 400
            
        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            
        return jsonify({
            'success': True,
            'content': content,
            'filename': os.path.basename(target),
            'path': file_path,
            'size': file_size,
            'server_name': server['name']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Admin Announcements & System Update Notices
@app.route('/admin/announcements', methods=['GET'])
@admin_permission_required('manage_announcements')
def admin_announcements():
    db = get_db()
    announcements = db.execute("SELECT * FROM announcements ORDER BY pinned DESC, id DESC").fetchall()
    return render_template('admin/announcements.html', announcements=announcements)

@app.route('/admin/announcements/create', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_create_announcement():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    ann_type = request.form.get('type', 'update').strip().lower()
    if ann_type not in ['update', 'info', 'warning', 'maintenance']:
        ann_type = 'update'
    is_active = 1 if request.form.get('is_active') in ['1', 'true', 'on'] else 0
    pinned = 1 if request.form.get('pinned') in ['1', 'true', 'on'] else 0
    
    if not title or not content:
        flash('Announcement title and content cannot be empty.', 'danger')
        return redirect(url_for('admin_announcements'))
        
    admin_user = get_current_user()
    creator_name = admin_user['full_name'] if admin_user else 'Administrator'
    
    db = get_db()
    db.execute('''
        INSERT INTO announcements (title, content, type, is_active, pinned, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (title, content, ann_type, is_active, pinned, creator_name))
    db.commit()
    
    log_admin_action('Created System Announcement', f"Notice: {title}", f"Type: {ann_type}, Active: {is_active}, Pinned: {pinned}")
    flash('System announcement published successfully!', 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:ann_id>/toggle', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_toggle_announcement(ann_id):
    db = get_db()
    ann = db.execute("SELECT * FROM announcements WHERE id = ?", (ann_id,)).fetchone()
    if not ann:
        flash('Announcement not found.', 'danger')
        return redirect(url_for('admin_announcements'))
    new_state = 0 if ann['is_active'] else 1
    db.execute("UPDATE announcements SET is_active = ? WHERE id = ?", (new_state, ann_id))
    db.commit()
    status_str = "activated" if new_state else "deactivated"
    log_admin_action(f"Toggled Announcement ({status_str})", f"Notice #{ann_id}", ann['title'])
    flash(f"Announcement notice #{ann_id} has been {status_str}.", 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:ann_id>/toggle-pin', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_toggle_announcement_pin(ann_id):
    db = get_db()
    ann = db.execute("SELECT * FROM announcements WHERE id = ?", (ann_id,)).fetchone()
    if not ann:
        flash('Announcement not found.', 'danger')
        return redirect(url_for('admin_announcements'))
    new_pin = 0 if ann['pinned'] else 1
    db.execute("UPDATE announcements SET pinned = ? WHERE id = ?", (new_pin, ann_id))
    db.commit()
    pin_str = "pinned to top" if new_pin else "unpinned"
    flash(f"Announcement notice #{ann_id} {pin_str}.", 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:ann_id>/delete', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_delete_announcement(ann_id):
    db = get_db()
    ann = db.execute("SELECT * FROM announcements WHERE id = ?", (ann_id,)).fetchone()
    if not ann:
        flash('Announcement not found.', 'danger')
        return redirect(url_for('admin_announcements'))
    db.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
    db.commit()
    log_admin_action('Deleted Announcement', f"Notice #{ann_id}", ann['title'])
    flash('Announcement deleted successfully.', 'info')
    return redirect(url_for('admin_announcements'))

# Custom Notification Broadcast & Sender
@app.route('/admin/broadcast', methods=['GET', 'POST'])
@admin_permission_required('manage_broadcasts')
def admin_broadcast():
    db = get_db()
    current_admin = get_current_user()
    
    if request.method == 'POST':
        target_type = request.form.get('target_type', 'all').strip()
        target_user_id_raw = request.form.get('target_user_id', '').strip()
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        category = request.form.get('category', 'announcement').strip()
        
        if not title or not message:
            flash('Broadcast Title and Message cannot be empty.', 'danger')
            return redirect(url_for('admin_broadcast'))
            
        recipients_count = 0
        target_username = None
        target_user_id = None
        
        if target_type == 'all':
            active_users = db.execute("SELECT id, username FROM users WHERE status = 'active'").fetchall()
            recipients_count = len(active_users)
            for u in active_users:
                db.execute(
                    "INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
                    (u['id'], title, message)
                )
            db.execute('''
                INSERT INTO broadcast_logs 
                (admin_id, admin_username, title, message, category, target_type, recipients_count)
                VALUES (?, ?, ?, ?, ?, 'all', ?)
            ''', (current_admin['id'], current_admin['username'], title, message, category, recipients_count))
            db.commit()
            
            log_admin_action('Global Broadcast Sent', f"All Active Users ({recipients_count})", f"Title: {title}")
            flash(f"Global notification broadcasted to all {recipients_count} active user accounts successfully!", 'success')
            return redirect(url_for('admin_broadcast'))
            
        elif target_type == 'specific':
            try:
                target_user_id = int(target_user_id_raw)
            except ValueError:
                flash('Please select a valid target user.', 'danger')
                return redirect(url_for('admin_broadcast'))
                
            target_user = db.execute("SELECT id, username, full_name, email FROM users WHERE id = ?", (target_user_id,)).fetchone()
            if not target_user:
                flash('Selected user account was not found.', 'danger')
                return redirect(url_for('admin_broadcast'))
                
            target_username = target_user['username']
            recipients_count = 1
            
            db.execute(
                "INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
                (target_user['id'], title, message)
            )
            db.execute('''
                INSERT INTO broadcast_logs 
                (admin_id, admin_username, title, message, category, target_type, target_user_id, target_username, recipients_count)
                VALUES (?, ?, ?, ?, ?, 'specific', ?, ?, 1)
            ''', (current_admin['id'], current_admin['username'], title, message, category, target_user['id'], target_username))
            db.commit()
            
            log_admin_action('Direct Notification Sent', f"User #{target_user['id']} (@{target_username})", f"Title: {title}")
            flash(f"Direct notification sent to {target_user['full_name']} (@{target_username}) successfully!", 'success')
            return redirect(url_for('admin_broadcast'))
            
    # GET: render broadcast interface
    users_list = db.execute("SELECT id, full_name, username, email FROM users WHERE status = 'active' ORDER BY username ASC").fetchall()
    recent_broadcasts = db.execute("SELECT * FROM broadcast_logs ORDER BY id DESC LIMIT 30").fetchall()
    
    return render_template(
        'admin/broadcast.html',
        users=users_list,
        broadcasts=recent_broadcasts
    )

# Admin Maintenance Mode & Settings
@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_permission_required('manage_settings')
def admin_settings():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action', '')
        
        if action == 'upload_logo':
            if 'logo' not in request.files:
                flash('No image file selected.', 'warning')
                return redirect(url_for('admin_settings'))
                
            file = request.files['logo']
            if not file or not file.filename:
                flash('Please select an image file to upload as the website logo.', 'warning')
                return redirect(url_for('admin_settings'))
                
            allowed_extensions = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg', 'ico'}
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in allowed_extensions:
                flash('Unsupported format. Allowed formats: PNG, JPG, JPEG, WEBP, GIF, SVG, ICO.', 'danger')
                return redirect(url_for('admin_settings'))
                
            file.seek(0, os.SEEK_END)
            size_bytes = file.tell()
            file.seek(0)
            if size_bytes > 5 * 1024 * 1024:
                flash('File size exceeds 5MB limit. Please upload a smaller logo image.', 'danger')
                return redirect(url_for('admin_settings'))
                
            try:
                for existing_file in os.listdir(BRANDING_DIR):
                    existing_path = os.path.join(BRANDING_DIR, existing_file)
                    if os.path.isfile(existing_path):
                        os.remove(existing_path)
            except Exception as e:
                print(f"Error cleaning branding directory: {e}")
                
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"site_logo_{timestamp}.{ext}"
            file_path = os.path.join(BRANDING_DIR, filename)
            file.save(file_path)
            
            logo_url = f"/static/uploads/branding/{filename}"
            set_setting('site_logo_url', logo_url)
            log_admin_action('Uploaded Site Logo', 'System Settings', f"Logo URL: {logo_url}")
            flash('Website logo uploaded and updated globally across the entire application!', 'success')
            return redirect(url_for('admin_settings'))

        elif action == 'reset_logo' or action == 'remove_logo':
            try:
                for existing_file in os.listdir(BRANDING_DIR):
                    existing_path = os.path.join(BRANDING_DIR, existing_file)
                    if os.path.isfile(existing_path):
                        os.remove(existing_path)
            except Exception as e:
                print(f"Error cleaning branding directory on reset: {e}")
                
            set_setting('site_logo_url', '/static/img/logo.svg')
            log_admin_action('Reset Site Logo', 'System Settings', 'Restored default logo')
            flash('Website logo reset to default system logo.', 'info')
            return redirect(url_for('admin_settings'))

        elif action == 'update_branding':
            site_name = request.form.get('site_name', 'HostX').strip() or 'HostX'
            vip_site_name = request.form.get('vip_site_name', 'HostX VIP').strip() or 'HostX VIP'
            custom_logo_url = request.form.get('custom_logo_url', '').strip()
            
            set_setting('site_name', site_name)
            set_setting('vip_site_name', vip_site_name)
            
            if 'logo' in request.files and request.files['logo'] and request.files['logo'].filename:
                file = request.files['logo']
                allowed_extensions = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg', 'ico'}
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext in allowed_extensions:
                    try:
                        for existing_file in os.listdir(BRANDING_DIR):
                            existing_path = os.path.join(BRANDING_DIR, existing_file)
                            if os.path.isfile(existing_path):
                                os.remove(existing_path)
                    except Exception:
                        pass
                    timestamp = int(datetime.utcnow().timestamp())
                    filename = f"site_logo_{timestamp}.{ext}"
                    file.save(os.path.join(BRANDING_DIR, filename))
                    set_setting('site_logo_url', f"/static/uploads/branding/{filename}")
            elif custom_logo_url:
                set_setting('site_logo_url', custom_logo_url)
                
            log_admin_action('Updated Site Branding', 'System Settings', f"Site Name: {site_name}, VIP Site Name: {vip_site_name}")
            flash('Site branding configuration updated successfully!', 'success')
            return redirect(url_for('admin_settings'))

        elif action == 'update_signup_bonus' or action == 'update_coin_economy':
            default_coins_raw = request.form.get('default_starting_coins', '50').strip()
            daily_reward_raw = request.form.get('daily_reward_coins', '10').strip()
            try:
                default_coins = max(0, int(default_coins_raw))
            except (ValueError, TypeError):
                default_coins = 50
            try:
                daily_reward = max(0, int(daily_reward_raw))
            except (ValueError, TypeError):
                daily_reward = 10
            
            set_setting('default_starting_coins', str(default_coins))
            set_setting('daily_reward_coins', str(daily_reward))
            
            log_admin_action(
                'Updated Signup Bonus & Economy Settings',
                'System Settings',
                f"New User Signup Bonus: {default_coins} coins, Daily Reward: {daily_reward} coins"
            )
            flash(f"Signup bonus amount set to {default_coins} coins and daily claim reward to {daily_reward} coins.", 'success')
            return redirect(url_for('admin_settings'))

        elif action == 'update_maintenance' or 'maintenance_message' in request.form:
            maintenance_mode = '1' if request.form.get('maintenance_mode') in ['1', 'true', 'on'] else '0'
            maintenance_msg = request.form.get('maintenance_message', '').strip()
            default_coins = request.form.get('default_starting_coins', '50').strip()
            daily_reward = request.form.get('daily_reward_coins', '10').strip()
            
            set_setting('maintenance_mode', maintenance_mode)
            set_setting('maintenance_message', maintenance_msg)
            if default_coins:
                set_setting('default_starting_coins', default_coins)
            if daily_reward:
                set_setting('daily_reward_coins', daily_reward)
            
            log_admin_action('Updated Platform Settings', 'System Settings', f"Maintenance Mode: {maintenance_mode}")
            flash('Platform settings updated successfully!', 'success')
            return redirect(url_for('admin_settings'))

        elif action == 'update_self_ping':
            self_ping_enabled = '1' if request.form.get('self_ping_enabled') in ['1', 'true', 'on'] else '0'
            self_ping_interval = request.form.get('self_ping_interval', '5').strip()
            manual_ping_url = request.form.get('manual_ping_url', '').strip()
            try:
                interval_val = max(1, int(self_ping_interval))
                self_ping_interval = str(interval_val)
            except ValueError:
                self_ping_interval = '5'

            set_setting('self_ping_enabled', self_ping_enabled)
            set_setting('self_ping_interval', self_ping_interval)
            set_setting('manual_ping_url', manual_ping_url)

            log_admin_action('Updated Self-Ping Settings', 'System Settings', f"Self-Ping Enabled: {self_ping_enabled}, Interval: {self_ping_interval} mins, Manual URL: {manual_ping_url}")
            flash('Self-Ping engine configuration updated successfully!', 'success')
            return redirect(url_for('admin_settings'))
        
    settings_dict = {
        'maintenance_mode': get_setting('maintenance_mode', '0'),
        'maintenance_message': get_setting('maintenance_message', ''),
        'default_starting_coins': get_setting('default_starting_coins', '50'),
        'daily_reward_coins': get_setting('daily_reward_coins', '10'),
        'site_name': get_setting('site_name', 'HostX'),
        'vip_site_name': get_setting('vip_site_name', 'HostX VIP'),
        'site_logo_url': get_setting('site_logo_url', '/static/img/logo.svg'),
        'self_ping_enabled': get_setting('self_ping_enabled', '1'),
        'self_ping_interval': get_setting('self_ping_interval', '5'),
        'detected_site_url': get_setting('detected_site_url', ''),
        'manual_ping_url': get_setting('manual_ping_url', '')
    }
    pkg_count = db.execute("SELECT COUNT(*) FROM packages").fetchone()[0]
    if pkg_count == 0:
        default_packages = [
            ('First Time Offer', 5, 10, 1, 'Exclusive 5-day trial package for new creators', 1),
            ('Standard 7 Days', 7, 20, 0, 'Standard 1-week hosting package for testing & bots', 1),
            ('Standard 15 Days', 15, 30, 0, 'Popular 2-week continuous hosting package', 1),
            ('Standard 30 Days', 30, 60, 0, 'Full month hosting with priority resources', 1),
            ('Standard 60 Days', 60, 100, 0, '2 months extended hosting with discount', 1),
            ('Standard 90 Days', 90, 150, 0, 'Quarterly enterprise hosting for permanent bots', 1)
        ]
        db.executemany(
            "INSERT INTO packages (name, days, coins, is_first_time_offer, description, active) VALUES (?, ?, ?, ?, ?, ?)",
            default_packages
        )
        db.commit()

    packages = db.execute("SELECT * FROM packages ORDER BY id ASC").fetchall()
    return render_template('admin/settings.html', settings=settings_dict, packages=packages)

@app.route('/admin/packages/update', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_update_package():
    db = get_db()
    pkg_id = request.form.get('id')
    name = request.form.get('name', '').strip()
    days = max(1, int(request.form.get('days', 1)))
    coins = max(0, int(request.form.get('coins', 0)))
    description = request.form.get('description', '').strip()
    is_first_time_offer = 1 if request.form.get('is_first_time_offer') in ['1', 'true', 'on'] else 0
    active = 1 if request.form.get('active') in ['1', 'true', 'on'] else 0
    
    if not name:
        name = f"Standard {days} Days"
    if not description:
        description = f"{days} Days continuous runtime"
    
    db.execute('''
        UPDATE packages 
        SET name = ?, days = ?, coins = ?, description = ?, is_first_time_offer = ?, active = ? 
        WHERE id = ?
    ''', (name, days, coins, description, is_first_time_offer, active, pkg_id))
    db.commit()
    
    log_admin_action('Updated Server Package', f'Package #{pkg_id}', f'{name} — {days} Days for {coins} Coins (Active: {active})')
    flash(f"Package '{name}' updated successfully! ({days} Days for {coins} Coins)", 'success')
    return redirect(url_for('admin_settings'))

@app.route('/admin/packages/create', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_create_package():
    db = get_db()
    name = request.form.get('name', '').strip()
    days = max(1, int(request.form.get('days', 1)))
    coins = max(0, int(request.form.get('coins', 0)))
    description = request.form.get('description', '').strip()
    is_first_time_offer = 1 if request.form.get('is_first_time_offer') in ['1', 'true', 'on'] else 0
    active = 1 if request.form.get('active') in ['1', 'true', 'on'] else 0

    if not name:
        name = f"Standard {days} Days"
    if not description:
        description = f"{days} Days continuous runtime"

    db.execute('''
        INSERT INTO packages (name, days, coins, description, is_first_time_offer, active)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, days, coins, description, is_first_time_offer, active))
    db.commit()

    log_admin_action('Created Server Package', name, f'{days} Days for {coins} Coins')
    flash(f"New hosting package '{name}' created successfully!", 'success')
    return redirect(url_for('admin_settings'))

@app.route('/admin/packages/<int:pkg_id>/delete', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_delete_package(pkg_id):
    db = get_db()
    pkg = db.execute("SELECT * FROM packages WHERE id = ?", (pkg_id,)).fetchone()
    if pkg:
        db.execute("DELETE FROM packages WHERE id = ?", (pkg_id,))
        db.commit()
        log_admin_action('Deleted Server Package', f'Package #{pkg_id}', pkg['name'])
        flash(f"Package '{pkg['name']}' deleted successfully.", 'info')
    else:
        flash("Package not found.", 'danger')
    return redirect(url_for('admin_settings'))

@app.route('/admin/packages/reset', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_reset_packages():
    db = get_db()
    db.execute("DELETE FROM packages")
    default_packages = [
        ('First Time Offer', 5, 10, 1, 'Exclusive 5-day trial package for new creators', 1),
        ('Standard 7 Days', 7, 20, 0, 'Standard 1-week hosting package for testing & bots', 1),
        ('Standard 15 Days', 15, 30, 0, 'Popular 2-week continuous hosting package', 1),
        ('Standard 30 Days', 30, 60, 0, 'Full month hosting with priority resources', 1),
        ('Standard 60 Days', 60, 100, 0, '2 months extended hosting with discount', 1),
        ('Standard 90 Days', 90, 150, 0, 'Quarterly enterprise hosting for permanent bots', 1)
    ]
    db.executemany(
        "INSERT INTO packages (name, days, coins, is_first_time_offer, description, active) VALUES (?, ?, ?, ?, ?, ?)",
        default_packages
    )
    db.commit()
    log_admin_action('Reset Server Packages', 'Packages Table', 'Restored 6 default package tiers')
    flash('Server packages reset to standard default tiers.', 'info')
    return redirect(url_for('admin_settings'))

# Admin Audit Logs
@app.route('/admin/logs')
@admin_permission_required('view_logs')
def admin_logs():
    db = get_db()
    logs = db.execute("SELECT * FROM admin_audit_logs ORDER BY created_at DESC LIMIT 100").fetchall()
    return render_template('admin/logs.html', logs=logs)

# ----------------- NOTIFICATION API ROUTES -----------------
@app.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    user = get_current_user()
    db = get_db()
    
    count = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ?", (user['id'],)).fetchone()[0]
    if count == 0:
        vip_brand = get_setting('vip_site_name', 'HostX VIP')
        welcome_title = f"Welcome to {vip_brand}"
        welcome_msg = f"Welcome {user['full_name']}! You have {user['coins']} coins in your wallet. Launch your 24/7 Python bots now!"
        db.execute(
            'INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)',
            (user['id'], welcome_title, welcome_msg)
        )
        db.commit()

    rows = db.execute(
        "SELECT id, title, message, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 50",
        (user['id'],)
    ).fetchall()

    unread_count = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user['id'],)
    ).fetchone()[0]

    notifications_list = []
    for r in rows:
        notifications_list.append({
            'id': r['id'],
            'title': r['title'],
            'message': r['message'],
            'is_read': r['is_read'],
            'created_at': str(r['created_at'])
        })

    return jsonify({
        'success': True,
        'notifications': notifications_list,
        'unread_count': unread_count
    })

@app.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    user = get_current_user()
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user['id'],))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification_route(notification_id):
    user = get_current_user()
    db = get_db()
    db.execute("DELETE FROM notifications WHERE id = ? AND user_id = ?", (notification_id, user['id']))
    db.commit()
    
    unread_count = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user['id'],)
    ).fetchone()[0]
    
    return jsonify({'success': True, 'unread_count': unread_count})

@app.route('/api/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications_route():
    user = get_current_user()
    db = get_db()
    db.execute("DELETE FROM notifications WHERE user_id = ?", (user['id'],))
    db.commit()
    return jsonify({'success': True, 'unread_count': 0})

# ----------------- ERROR HANDLERS -----------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def access_forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    PORT = 3000
    print("==================================================")
    print("  HOSTX VIP WHITE — PYTHON HOSTING PLATFORM       ")
    print(f"  Starting server on http://0.0.0.0:{PORT}       ")
    print("==================================================")
    app.run(host='0.0.0.0', port=PORT, debug=False)
