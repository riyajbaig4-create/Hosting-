"""
HostX VIP — Python Hosting Platform
Licence Protected · Premium Multi-Language Hosting
"""
import os
import sys
import hashlib

# ============================================================
# ============================================================
# LICENCE VERIFICATION
# ============================================================
VALID_LICENCE_HASHES = [
    "d9c5387921eb203ba99d9b6adbe852db48a63e7b41c1847732270d5cfb0ad426",   # riyajmughal
    "d9b86c7410b80c2c4847ab9a62ab1536e679444b25aacef0db687882fce1d6a4",   # riyaj
    "97828747c7789f565bb0e61dc267183ab5727e0965d90420be3515d8322e0c9b",   # riyajbaig
    "3d05ba07263b6fee38f046fe22a0400cb5c333de30f990306fd98042b0195113",   # ryjmg_the_boss_2026
    "c76786198d837fb6bfe021b8d6950e89c713ad56d52f7bc6819425c154be11b2",   # Host-bot-hai-lala
]
LICENCE_ENV_VAR = "HOSTX_LICENCE_KEY"


def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        return False
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        return True
    except Exception:
        return False


def _verify_licence():
    _load_dotenv()
    key = os.environ.get(LICENCE_ENV_VAR, "").strip()
    if not key:
        print("\n" + "=" * 60)
        print("  HOSTX VIP — Licence Verification Required")
        print("=" * 60)
        print("  This software is protected by a licence key.")
        print("  Please contact the vendor to obtain a valid key.")
        print()
        try:
            key = input("  Enter your licence key: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  [X] No key provided. Exiting.")
            sys.exit(1)
    if not key:
        print("  [X] Empty key. Exiting.")
        sys.exit(1)
    key_hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
    if key_hash not in VALID_LICENCE_HASHES:
        print("\n  [X] INVALID LICENCE KEY")
        print("  [X] Please contact support.")
        sys.exit(1)
    print("  [OK] Licence verified successfully.")
    print("=" * 60 + "\n")


_verify_licence()
# ============================================================
# IMPORTS
# ============================================================
import time
import io
import json
import sqlite3
import shutil
import zipfile
import subprocess
import signal
import ast
import re
import threading
import random
import secrets
import hmac
import string
from datetime import datetime, timedelta, date
from functools import wraps
from urllib.parse import quote

try:
    import psutil
except ImportError:
    class DummyPsutil:
        @staticmethod
        def pid_exists(pid):
            if not pid or pid <= 0: return False
            try: os.kill(pid, 0); return True
            except Exception: return False
        class Process:
            def __init__(self, pid): self.pid = pid
            def kill(self):
                try: os.kill(self.pid, signal.SIGKILL)
                except Exception: pass
            def terminate(self):
                try: os.kill(self.pid, signal.SIGTERM)
                except Exception: pass
            def create_time(self): return time.time()
    psutil = DummyPsutil()

try:
    import requests
except ImportError:
    requests = None

try:
    from authlib.integrations.flask_client import OAuth
    AUTHLIB_AVAILABLE = True
except ImportError:
    AUTHLIB_AVAILABLE = False
    OAuth = None

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from flask import (Flask, render_template_string, request, redirect,
    url_for, session, flash, jsonify, send_file, abort, Response,
    g, stream_with_context)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hostx_vip_secret_key_2026_change_me')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'hostx.db')
SERVERS_DIR = os.path.join(BASE_DIR, 'servers')
AVATARS_DIR = os.path.join(BASE_DIR, 'static', 'avatars')
BRANDING_DIR = os.path.join(BASE_DIR, 'static', 'branding')

if os.path.exists('/data'):
    DB_PATH = '/data/hostx.db'
    SERVERS_DIR = '/data/servers'
    AVATARS_DIR = '/data/avatars'
    BRANDING_DIR = '/data/branding'

for d in [os.path.dirname(DB_PATH), SERVERS_DIR, AVATARS_DIR, BRANDING_DIR]:
    os.makedirs(d, exist_ok=True)

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '926455144408-247npcmo0tm7e3bj5o0uukosdilgk7i4.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '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')

oauth = None
google = None
if AUTHLIB_AVAILABLE and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    try:
        oauth = OAuth(app)
        google = oauth.register(
            name='google',
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
        print("[*] Google OAuth ready")
    except Exception as e:
        print(f"[!] OAuth setup failed: {e}")

def safe_generate_password_hash(password):
    if not password: return ""
    try:
        return generate_password_hash(password, method='pbkdf2:sha256')
    except Exception:
        salt = secrets.token_hex(16)
        it = 260000
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), it)
        return f"pbkdf2:sha256:{it}${salt}${key.hex()}"

def safe_check_password_hash(pwhash, password):
    if not pwhash or not password: return False
    if pwhash.startswith('scrypt:'):
        try:
            parts = pwhash.split('$')
            if len(parts) == 3:
                params, salt, expected = parts
                sub = params.split(':')
                n = int(sub[1]) if len(sub) > 1 else 32768
                r = int(sub[2]) if len(sub) > 2 else 8
                p = int(sub[3]) if len(sub) > 3 else 1
                comp = hashlib.scrypt(password.encode(), salt=salt.encode(),
                    n=n, r=r, p=p, maxmem=128*1024*1024).hex()
                if hmac.compare_digest(comp.lower(), expected.lower()): return True
        except Exception: pass
    try:
        if check_password_hash(pwhash, password): return True
    except Exception: pass
    if pwhash.startswith('pbkdf2:'):
        try:
            parts = pwhash.split('$')
            if len(parts) == 3:
                mi, salt, expected = parts
                sub = mi.split(':')
                hn = sub[1] if len(sub) > 1 else 'sha256'
                it = int(sub[2]) if len(sub) > 2 else 260000
                comp = hashlib.pbkdf2_hmac(hn, password.encode(), salt.encode(), it).hex()
                if hmac.compare_digest(comp.lower(), expected.lower()): return True
        except Exception: pass
    try:
        if hmac.compare_digest(pwhash, password): return True
    except Exception: pass
    return False

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None: db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT DEFAULT 'user', status TEXT DEFAULT 'active', plan_id INTEGER DEFAULT 0, plan_expires_at TIMESTAMP, project_limit INTEGER DEFAULT 0, trial_used INTEGER DEFAULT 0, signup_ip TEXT DEFAULT '', trial_expires_at TIMESTAMP, avatar_url TEXT DEFAULT '', bio TEXT DEFAULT '', is_admin INTEGER DEFAULT 0, is_super_admin INTEGER DEFAULT 0, admin_permissions TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_login TIMESTAMP);
    CREATE TABLE IF NOT EXISTS servers (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, slug TEXT UNIQUE, runtime TEXT DEFAULT 'python', entry_file TEXT DEFAULT '', status TEXT DEFAULT 'stopped', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP NOT NULL, pid INTEGER DEFAULT 0, port INTEGER DEFAULT 0, auto_restart INTEGER DEFAULT 1, FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS packages (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price INTEGER NOT NULL, days INTEGER NOT NULL, project_limit INTEGER NOT NULL, features TEXT, is_trial INTEGER DEFAULT 0, trial_hours INTEGER DEFAULT 6, is_popular INTEGER DEFAULT 0, active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, package_id INTEGER NOT NULL, amount INTEGER NOT NULL, status TEXT DEFAULT 'pending', payment_method TEXT DEFAULT '', payment_id TEXT DEFAULT '', payment_ref TEXT DEFAULT '', customer_name TEXT DEFAULT '', customer_email TEXT DEFAULT '', customer_phone TEXT DEFAULT '', admin_notes TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, paid_at TIMESTAMP, expires_at TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (package_id) REFERENCES packages(id));
    CREATE TABLE IF NOT EXISTS plan_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, package_id INTEGER NOT NULL, action TEXT NOT NULL, old_expires_at TIMESTAMP, new_expires_at TIMESTAMP, amount INTEGER DEFAULT 0, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS trial_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, ip_address TEXT, started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP, converted_to_plan INTEGER DEFAULT 0, converted_at TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS trial_ips (id INTEGER PRIMARY KEY AUTOINCREMENT, ip_address TEXT UNIQUE NOT NULL, username TEXT, email TEXT, first_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS server_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, server_id INTEGER NOT NULL, level TEXT DEFAULT 'INFO', message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS admin_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, admin_username TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, details TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS admin_notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, title TEXT NOT NULL, message TEXT NOT NULL, user_id INTEGER, order_id INTEGER, is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT DEFAULT 'Notification', message TEXT NOT NULL, is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT NOT NULL, type TEXT DEFAULT 'update', is_active INTEGER DEFAULT 1, pinned INTEGER DEFAULT 0, created_by TEXT DEFAULT 'Administrator', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS broadcast_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, admin_username TEXT NOT NULL, title TEXT NOT NULL, message TEXT NOT NULL, category TEXT DEFAULT 'announcement', target_type TEXT NOT NULL, target_user_id INTEGER, target_username TEXT, recipients_count INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    ''')
    cur.execute("SELECT COUNT(*) FROM packages")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO packages (name, price, days, project_limit, features, is_trial, trial_hours, is_popular, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            ('Free Trial', 0, 0, 1, '6-hour trial,1 Project,Full Feature Access,No Credit Card', 1, 6, 0, 1),
            ('Starter', 49, 30, 2, '30 days validity,2 Projects,Free SSL,Auto Deploy,Live Logs,24x7 Support', 0, 0, 0, 2),
            ('Pro', 99, 30, 4, '30 days validity,4 Projects,Custom Domains,Priority Support,Everything in Starter', 0, 0, 1, 3),
            ('Business', 149, 30, 12, '30 days validity,12 Projects,Team Access,Fast Support,Everything in Pro', 0, 0, 0, 4),
            ('Unlimited', 199, 30, -1, '30 days validity,Unlimited Projects,Unlimited Storage,VIP Support,Everything in Business', 0, 0, 1, 5)])
    defaults = {'maintenance_mode': '0', 'maintenance_message': 'New Update — Platform is upgrading. Back shortly!', 'site_name': 'HostX', 'vip_site_name': 'HostX VIP', 'site_logo_url': '', 'trial_enabled': '1', 'trial_hours': '6', 'trial_project_limit': '1', 'self_ping_enabled': '1', 'self_ping_interval': '5', 'payment_manual_enabled': '1', 'payment_autodetect_enabled': '0', 'upi_phonepe': '', 'upi_gpay': '', 'upi_paytm': '', 'upi_fampay': '', 'upi_bhim': '', 'upi_amazonpay': '', 'fampay_api_key': '', 'razorpay_key_id': '', 'razorpay_key_secret': '', 'primary_upi': 'manual'}
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    cur.execute("SELECT COUNT(*) FROM announcements")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO announcements (title, content, type, is_active, pinned, created_by) VALUES (?, ?, 'update', 1, 1, 'Platform Admin')", ('🚀 Welcome to HostX VIP', 'Fast, secure, 24/7 Python & multi-language hosting. Deploy your projects in seconds!'))
    cur.execute("SELECT COUNT(*) FROM users WHERE is_super_admin = 1")
    if cur.fetchone()[0] == 0:
        ae = os.environ.get('ADMIN_EMAIL', 'admin@hostx.vip')
        ap = os.environ.get('ADMIN_PASSWORD', 'admin123')
        cur.execute("INSERT INTO users (full_name, username, email, password_hash, role, status, is_admin, is_super_admin, admin_permissions, project_limit) VALUES (?, ?, ?, ?, 'super_admin', 'active', 1, 1, 'all', -1)", ('Super Admin', 'admin', ae, safe_generate_password_hash(ap)))
        print(f"[*] Super Admin created: {ae} / {ap}")
    conn.commit()
    conn.close()
    print("[*] Database ready")

init_db()

def get_setting(key, default=None):
    try:
        db = get_db()
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row and row['value'] is not None else default
    except Exception:
        return default

def set_setting(key, value):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    db.commit()

def log_admin_action(action, target, details=''):
    try:
        db = get_db()
        db.execute("INSERT INTO admin_audit_logs (admin_id, admin_username, action, target, details) VALUES (?, ?, ?, ?, ?)", (session.get('user_id'), session.get('username', 'System'), action, target, details))
        db.commit()
    except Exception: pass

def notify_admin(notif_type, title, message, user_id=None, order_id=None):
    try:
        db = get_db()
        db.execute("INSERT INTO admin_notifications (type, title, message, user_id, order_id) VALUES (?, ?, ?, ?, ?)", (notif_type, title, message, user_id, order_id))
        db.commit()
    except Exception: pass

def create_user_notification(user_id, title, message):
    try:
        db = get_db()
        db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)", (user_id, title, message))
        db.commit()
    except Exception: pass

def get_current_user():
    uid = session.get('user_id')
    if not uid: return None
    try:
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if user and user['status'] != 'active':
            session.clear(); return None
        return user
    except Exception:
        return None

def is_user_super_admin(user):
    if not user: return False
    try:
        if user['role'] == 'super_admin' or user['is_super_admin']: return True
    except Exception: pass
    return False

def is_user_admin(user):
    if not user: return False
    if is_user_super_admin(user): return True
    try:
        if user['role'] == 'admin' or user['is_admin']: return True
    except Exception: pass
    return False

def has_admin_permission(user, perm):
    if not user or not is_user_admin(user): return False
    if is_user_super_admin(user): return True
    try:
        perms = (user['admin_permissions'] or '').strip()
        if not perms: return True
        plist = [p.strip() for p in perms.split(',') if p.strip()]
        return perm in plist or 'all' in plist
    except Exception:
        return False

def has_active_access(user):
    if not user: return False, "Not logged in"
    if is_user_admin(user): return True, "Admin — Unlimited"
    now = datetime.utcnow()
    if user['plan_id'] and user['plan_expires_at']:
        try:
            pe = user['plan_expires_at']
            if isinstance(pe, str): pe = datetime.strptime(pe.split('.')[0], '%Y-%m-%d %H:%M:%S')
            if pe > now:
                days = (pe - now).days
                return True, f"Plan active · {days} days left"
        except Exception: pass
    if user['trial_expires_at']:
        try:
            te = user['trial_expires_at']
            if isinstance(te, str): te = datetime.strptime(te.split('.')[0], '%Y-%m-%d %H:%M:%S')
            if te > now:
                h = int((te - now).total_seconds() / 3600)
                return True, f"Trial — {h}h left"
        except Exception: pass
    return False, "No active plan"

def check_project_limit(user):
    if not user: return False, "Not logged in"
    if is_user_admin(user): return True, "Admin — Unlimited"
    if user['trial_expires_at'] and not user['plan_id']:
        try:
            te = user['trial_expires_at']
            if isinstance(te, str): te = datetime.strptime(te.split('.')[0], '%Y-%m-%d %H:%M:%S')
            if te < datetime.utcnow(): return False, "Trial expired"
        except Exception: pass
    if user['plan_expires_at']:
        try:
            pe = user['plan_expires_at']
            if isinstance(pe, str): pe = datetime.strptime(pe.split('.')[0], '%Y-%m-%d %H:%M:%S')
            if pe < datetime.utcnow(): return False, "Plan expired"
        except Exception: pass
    db = get_db()
    cur = db.execute("SELECT COUNT(*) FROM servers WHERE user_id=?", (user['id'],)).fetchone()[0]
    lim = user['project_limit'] if user['project_limit'] != 0 else 0
    if lim == -1: return True, f"{cur} / Unlimited"
    if lim == 0: return False, "No active plan"
    if cur >= lim: return False, f"Limit reached ({cur}/{lim})"
    return True, f"{cur} / {lim}"

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if 'user_id' not in session:
            flash('Please sign in to continue', 'warning')
            return redirect(url_for('signin', next=request.url))
        u = get_current_user()
        if not u:
            flash('Your session has expired. Please sign in again.', 'danger')
            return redirect(url_for('signin'))
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if 'user_id' not in session:
            flash('Please sign in', 'warning')
            return redirect(url_for('signin', next=request.url))
        u = get_current_user()
        if not u or not is_user_admin(u):
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*a, **k)
    return w

def admin_permission_required(perm):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if 'user_id' not in session:
                flash('Please sign in', 'warning')
                return redirect(url_for('signin', next=request.url))
            u = get_current_user()
            if not u or not is_user_admin(u):
                flash('Admin access required', 'danger')
                return redirect(url_for('dashboard'))
            if not has_admin_permission(u, perm):
                flash('You do not have permission for this action', 'warning')
                return redirect(url_for('admin_dashboard'))
            return f(*a, **k)
        return w
    return deco

def require_plan(f):
    @wraps(f)
    def w(*a, **k):
        u = get_current_user()
        if not u: return redirect(url_for('signin'))
        ok, msg = has_active_access(u)
        if not ok:
            flash('Choose a plan to continue', 'warning')
            return redirect(url_for('packages'))
        return f(*a, **k)
    return w

@app.template_filter('first_word')
def _fw(v): return str(v).split(' ')[0] if v else ''

@app.template_filter('format_date')
def _fd(v):
    if not v: return ''
    if isinstance(v, (datetime, date)): return v.strftime('%Y-%m-%d')
    return str(v)[:10]

@app.template_filter('format_datetime')
def _fdt(v):
    if not v: return ''
    if isinstance(v, (datetime, date)): return v.strftime('%Y-%m-%d %H:%M')
    return str(v).split('.')[0]

@app.context_processor
def inject_globals():
    user = get_current_user()
    fn = ''
    if user:
        try:
            n = (user['full_name'] or '').strip()
            fn = n.split(' ')[0] if n else (user['username'] or 'User')
        except Exception: fn = 'User'
    has_access, access_msg = has_active_access(user) if user else (False, '')
    trial_active = False
    trial_hours_left = 0
    if user and user['trial_expires_at'] and not user['plan_id']:
        try:
            te = user['trial_expires_at']
            if isinstance(te, str): te = datetime.strptime(te.split('.')[0], '%Y-%m-%d %H:%M:%S')
            if te > datetime.utcnow():
                trial_active = True
                trial_hours_left = int((te - datetime.utcnow()).total_seconds() / 3600)
        except Exception: pass
    return dict(
        current_user=user, is_admin=is_user_admin(user),
        is_super_admin=is_user_super_admin(user),
        has_admin_permission=has_admin_permission,
        user_first_name=fn,
        site_name=(get_setting('site_name', 'HostX') or 'HostX').strip(),
        vip_site_name=(get_setting('vip_site_name', 'HostX VIP') or 'HostX VIP').strip(),
        site_logo_url=(get_setting('site_logo_url', '') or '').strip(),
        maintenance_mode=get_setting('maintenance_mode', '0') == '1',
        maintenance_message=get_setting('maintenance_message', ''),
        is_impersonating=session.get('is_impersonating', False),
        real_admin_username=session.get('real_admin_username'),
        has_access=has_access, access_msg=access_msg,
        trial_active=trial_active, trial_hours_left=trial_hours_left,
        trial_enabled=get_setting('trial_enabled', '1') == '1',
        now=datetime.utcnow())

@app.before_request
def _before():
    skip = {'static','health','signin','signup','signout','home','auth_google','auth_google_callback'}
    if request.endpoint in skip: return
    if get_setting('maintenance_mode', '0') == '1':
        u = get_current_user()
        if not is_user_admin(u) and request.endpoint not in ['home','signin','signout','health']:
            if request.path.startswith('/api/'):
                return jsonify({'error':'maintenance','maintenance':True}), 503
            return redirect(url_for('home'))
    if 'user_id' in session:
        u = get_current_user()
        if u and not is_user_admin(u):
            db = get_db()
            now = datetime.utcnow()
            expired = False
            if u['trial_expires_at'] and not u['plan_id']:
                try:
                    te = u['trial_expires_at']
                    if isinstance(te, str): te = datetime.strptime(te.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    if te < now: expired = True
                except Exception: pass
            if u['plan_expires_at']:
                try:
                    pe = u['plan_expires_at']
                    if isinstance(pe, str): pe = datetime.strptime(pe.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    if pe < now: expired = True
                except Exception: pass
            if expired:
                try:
                    db.execute("UPDATE users SET project_limit=0 WHERE id=?", (u['id'],))
                    for s in db.execute("SELECT id FROM servers WHERE user_id=?", (u['id'],)).fetchall():
                        try: stop_server_process(s['id'])
                        except Exception: pass
                    db.execute("UPDATE servers SET status='stopped' WHERE user_id=?", (u['id'],))
                    db.commit()
                except Exception: pass

@app.route('/health')
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'app': 'HostX VIP', 'licence': 'verified', 'time': datetime.utcnow().isoformat()})

RUNNING_PROCESSES = {}
SERVER_START_TIMES = {}

def get_server_dir(user_id, server_id):
    path = os.path.join(SERVERS_DIR, str(user_id), str(server_id))
    os.makedirs(path, exist_ok=True)
    return path

def is_safe_path(base, path):
    base = os.path.realpath(base)
    target = os.path.realpath(path)
    return base == target or target.startswith(base + os.sep)

def write_server_log(server_id, level, message):
    """Logs only to DB, not to server.log file. Terminal shows only user output."""
    try:
        db = get_db()
        db.execute("INSERT INTO server_logs (server_id, level, message) VALUES (?, ?, ?)", (server_id, level, message))
        db.commit()
    except Exception: pass

STDLIB = {'abc','aifc','argparse','array','ast','asynchat','asyncio','asyncore','atexit','audioop','base64','bdb','binascii','binhex','bisect','builtins','bz2','calendar','cgi','cgitb','chunk','cmath','cmd','code','codecs','codeop','collections','colorsys','compileall','concurrent','configparser','contextlib','contextvars','copy','copyreg','cProfile','crypt','csv','ctypes','curses','dataclasses','datetime','dbm','decimal','difflib','dis','distutils','doctest','email','encodings','enum','errno','faulthandler','fcntl','filecmp','fileinput','fnmatch','fractions','ftplib','functools','gc','getopt','getpass','gettext','glob','graphlib','grp','gzip','hashlib','heapq','hmac','html','http','imaplib','imghdr','imp','importlib','inspect','io','ipaddress','itertools','json','keyword','lib2to3','linecache','locale','logging','lzma','mailbox','mailcap','marshal','math','mimetypes','mmap','modulefinder','msilib','msvcrt','multiprocessing','netrc','nis','nntplib','numbers','operator','optparse','os','ossaudiodev','parser','pathlib','pdb','pickle','pickletools','pipes','pkgutil','platform','plistlib','poplib','posix','posixpath','pprint','profile','pstats','pty','pwd','py_compile','pyclbr','pydoc','queue','quopri','random','re','readline','reprlib','resource','rlcompleter','runpy','sched','secrets','select','selectors','shelve','shlex','shutil','signal','site','smtpd','smtplib','sndhdr','socket','socketserver','spwd','sqlite3','ssl','stat','statistics','string','stringprep','struct','subprocess','sunau','symbol','symtable','sys','sysconfig','syslog','tabnanny','tarfile','telnetlib','tempfile','termios','test','textwrap','threading','time','timeit','tkinter','token','tokenize','tomllib','trace','traceback','tracemalloc','tty','turtle','turtledemo','types','typing','unicodedata','unittest','urllib','uu','uuid','venv','warnings','wave','weakref','webbrowser','winreg','winsound','wsgiref','xdrlib','xml','xmlrpc','zipapp','zipfile','zipimport','zlib','zoneinfo'}

IMAP = {'telebot':'pyTelegramBotAPI','telegram':'python-telegram-bot','aiogram':'aiogram','discord':'discord.py','PIL':'Pillow','bs4':'beautifulsoup4','yaml':'PyYAML','dotenv':'python-dotenv','dateutil':'python-dateutil','cv2':'opencv-python-headless','jwt':'PyJWT','sklearn':'scikit-learn','flask_cors':'flask-cors','fitz':'PyMuPDF','psycopg2':'psycopg2-binary','pymysql':'PyMySQL','sqlalchemy':'SQLAlchemy','pandas':'pandas','numpy':'numpy','requests':'requests','flask':'Flask','fastapi':'fastapi','uvicorn':'uvicorn','colorama':'colorama','aiohttp':'aiohttp','schedule':'schedule','pytz':'pytz','rich':'rich','tqdm':'tqdm','pydantic':'pydantic','cryptography':'cryptography','websockets':'websockets','pymongo':'pymongo','redis':'redis','paramiko':'paramiko','qrcode':'qrcode','gspread':'gspread','pyrogram':'pyrogram','tgcrypto':'tgcrypto','tweepy':'tweepy','matplotlib':'matplotlib','scipy':'scipy','selenium':'selenium','playwright':'playwright','openpyxl':'openpyxl','docx':'python-docx','pypdf':'pypdf','httpx':'httpx','stripe':'stripe','yt_dlp':'yt-dlp'}

def _is_installed(sdir, mod):
    pdir = os.path.join(sdir, 'packages')
    if os.path.exists(pdir):
        key = mod.lower().replace('-','_')
        for it in os.listdir(pdir):
            il = it.lower().replace('-','_')
            if il == key or il.startswith(key+'-') or il.startswith(key+'.'): return True
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{sdir}:{pdir}:" + env.get('PYTHONPATH','')
        r = subprocess.run([sys.executable, '-c', f"import {mod}"], cwd=sdir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.5)
        return r.returncode == 0
    except Exception: return False

def scan_project(sdir):
    if not os.path.exists(sdir):
        return {'ready':True,'entry_file':'','py_files':[],'has_requirements':False,'missing_packages':[],'installed_packages':[],'all_detected_imports':[],'has_files':False}
    py_files = []; local = set(); total_files = 0
    for root, dirs, files in os.walk(sdir):
        dirs[:] = [d for d in dirs if d not in ('packages','__pycache__','.venv','.git','venv','node_modules')]
        for f in files:
            total_files += 1
            if f.endswith('.py'):
                rel = os.path.relpath(os.path.join(root, f), sdir)
                py_files.append(rel); local.add(os.path.splitext(f)[0])
                if f == '__init__.py': local.add(os.path.basename(root))
    entry = ''
    for c in ['main.py','app.py','bot.py','server.py','run.py','index.py']:
        if c in py_files: entry = c; break
    else:
        if py_files: entry = py_files[0]
    req = os.path.join(sdir, 'requirements.txt')
    has_req = os.path.isfile(req)
    req_pkgs = {}
    if has_req:
        try:
            with open(req, 'r', encoding='utf-8', errors='ignore') as rf:
                for line in rf:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        m = re.split(r'==|>=|<=|~=|!=|>', line, maxsplit=1)
                        n = m[0].strip(); v = m[1].strip() if len(m) > 1 else 'latest'
                        if n: req_pkgs[n] = v
        except Exception: pass
    imports = set()
    for pf in py_files:
        try:
            with open(os.path.join(sdir, pf), 'r', encoding='utf-8', errors='ignore') as f:
                tree = ast.parse(f.read(), filename=pf)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        t = a.name.split('.')[0]
                        if t and t not in STDLIB and t not in local: imports.add(t)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        t = node.module.split('.')[0]
                        if t and t not in STDLIB and t not in local: imports.add(t)
        except Exception: pass
    required = {}
    for pkg, ver in req_pkgs.items():
        imp = pkg
        for k, v in IMAP.items():
            if v.lower() == pkg.lower(): imp = k; break
        required[pkg] = {'name':pkg,'import_name':imp,'version':ver,'source':'requirements'}
    for imp in imports:
        pkg = IMAP.get(imp, imp)
        if not any(k.lower() == pkg.lower() for k in required):
            required[pkg] = {'name':pkg,'import_name':imp,'version':'latest','source':'code'}
    missing = []; installed = []
    for pkg, info in required.items():
        ok = _is_installed(sdir, info['import_name']) or (info['name'] != info['import_name'] and _is_installed(sdir, info['name']))
        (installed if ok else missing).append(info)
    return {'ready':len(missing)==0,'entry_file':entry,'has_entry_file':bool(py_files),'py_files':py_files,'has_requirements':has_req,'missing_packages':missing,'installed_packages':installed,'all_detected_imports':sorted(imports),'has_files':total_files>0,'total_files':total_files}

def detect_runtime_and_cmd(sdir, port):
    if os.path.exists(os.path.join(sdir, 'package.json')):
        try:
            with open(os.path.join(sdir, 'package.json'), 'r') as f:
                data = json.load(f)
            scripts = data.get('scripts', {})
            if 'start' in scripts: return ['npm','start'], 'nodejs', {'PORT':str(port),'NODE_ENV':'production'}
            mf = data.get('main')
            if mf and os.path.exists(os.path.join(sdir, mf)): return ['node', mf], 'nodejs', {'PORT':str(port)}
        except Exception: pass
    for fname in ['server.js','app.js','index.js','main.js','bot.js']:
        if os.path.exists(os.path.join(sdir, fname)): return ['node', fname], 'nodejs', {'PORT':str(port)}
    for fname in ['index.php','server.php','app.php']:
        if os.path.exists(os.path.join(sdir, fname)): return ['php','-S',f'0.0.0.0:{port}','-t',sdir], 'php', {}
    if os.path.exists(os.path.join(sdir, 'go.mod')): return ['go','run','.'], 'go', {}
    if os.path.exists(os.path.join(sdir, 'Gemfile')): return ['bundle','exec','ruby','app.rb'], 'ruby', {}
    if os.path.exists(os.path.join(sdir, 'pom.xml')): return ['mvn','spring-boot:run'], 'java', {}
    jars = [f for f in os.listdir(sdir) if f.endswith('.jar')]
    if jars: return ['java','-jar',jars[0]], 'java', {}
    for f in ['app.py','main.py','server.py','run.py','bot.py']:
        path = os.path.join(sdir, f)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                    if 'FastAPI' in content or 'uvicorn.run' in content:
                        return ['uvicorn','main:app','--host','0.0.0.0','--port',str(port)], 'fastapi', {}
                    if 'Flask' in content or 'app.run' in content:
                        return [sys.executable, f], 'flask', {}
            except Exception: pass
    if os.path.exists(os.path.join(sdir, 'manage.py')): return [sys.executable,'manage.py','runserver',f'0.0.0.0:{port}'], 'django', {}
    for f in os.listdir(sdir):
        if f.endswith('.py') and os.path.isfile(os.path.join(sdir, f)): return [sys.executable, f], 'python', {}
    if os.path.exists(os.path.join(sdir, 'index.html')): return [sys.executable,'-m','http.server',str(port),'--bind','0.0.0.0'], 'static', {}
    return None, None, {}

def stop_server_process(server_id):
    db = get_db()
    proc = RUNNING_PROCESSES.pop(server_id, None)
    if proc:
        try:
            if hasattr(os,'killpg'): os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else: proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try: proc.kill()
            except Exception: pass
    SERVER_START_TIMES.pop(server_id, None)
    row = db.execute("SELECT pid FROM servers WHERE id=?", (server_id,)).fetchone()
    if row and row['pid']:
        try:
            if psutil.pid_exists(row['pid']): psutil.Process(row['pid']).terminate()
        except Exception: pass
    db.execute("UPDATE servers SET status='stopped', pid=0 WHERE id=?", (server_id,))
    db.commit()
    return True

def start_server_process(server_id):
    db = get_db()
    server = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
    if not server: return False, "Server not found", [], False
    exp = server['expires_at']
    if isinstance(exp, str): exp = datetime.strptime(exp.split('.')[0], '%Y-%m-%d %H:%M:%S')
    if exp < datetime.utcnow():
        db.execute("UPDATE servers SET status='expired' WHERE id=?", (server_id,))
        db.commit()
        return False, "Server has expired. Please renew.", [], False
    sdir = get_server_dir(server['user_id'], server_id)
    if not os.path.exists(sdir) or not os.listdir(sdir):
        write_server_log(server_id, 'ERROR', 'Project folder is empty')
        return False, "Upload your project files first.", [], True
    write_server_log(server_id, 'INFO', 'Starting server...')
    user_port = server['port'] or (5001 + (server_id % 1000))
    if not server['port']:
        db.execute("UPDATE servers SET port=? WHERE id=?", (user_port, server_id))
        db.commit()
    write_server_log(server_id, 'INFO', f'Detecting runtime...')
    cmd, runtime, env_extra = detect_runtime_and_cmd(sdir, user_port)
    scan = scan_project(sdir)
    entry = server['entry_file'] or scan['entry_file'] or ''
    if not cmd:
        write_server_log(server_id, 'ERROR', 'No runnable file found')
        return False, "No runnable file found in project.", [], True
    write_server_log(server_id, 'INFO', f'Runtime: {runtime}')
    if entry: write_server_log(server_id, 'INFO', f'Entry: {entry}')
    pdir = os.path.join(sdir, 'packages')
    os.makedirs(pdir, exist_ok=True)
    req = os.path.join(sdir, 'requirements.txt')
    if os.path.isfile(req):
        write_server_log(server_id, 'INFO', 'Installing requirements.txt...')
        try:
            r = subprocess.run([sys.executable,'-m','pip','install','-r',req,'--target',pdir,'--no-cache-dir','--disable-pip-version-check'], cwd=sdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
            for line in (r.stdout or '').splitlines()[-3:]:
                if line.strip(): write_server_log(server_id, 'INFO', f'[pip] {line.strip()[:150]}')
        except Exception as e: write_server_log(server_id, 'WARNING', f'pip: {e}')
        scan = scan_project(sdir)
    if scan['missing_packages']:
        for pkg in scan['missing_packages']:
            spec = pkg['name']
            if pkg['version'] != 'latest' and '==' not in spec: spec = f"{pkg['name']}=={pkg['version']}"
            write_server_log(server_id, 'INFO', f'Installing {spec}...')
            try:
                subprocess.run([sys.executable,'-m','pip','install',spec,'--target',pdir,'--no-cache-dir','--disable-pip-version-check'], cwd=sdir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            except Exception: pass
    stop_server_process(server_id)
    logp = os.path.join(sdir, 'server.log')
    logf = open(logp, 'a', encoding='utf-8')
    logf.write(f"\n--- Started {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    logf.flush()
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    env['PORT'] = str(user_port)
    env['HOSTX_PORT'] = str(user_port)
    env['HOSTX_SERVER_ID'] = str(server_id)
    env['PYTHONPATH'] = f"{sdir}:{pdir}:" + env.get('PYTHONPATH','')
    env.update(env_extra)
    kwargs = {}
    if hasattr(os, 'setsid'): kwargs['preexec_fn'] = os.setsid
    try:
        proc = subprocess.Popen(cmd, cwd=sdir, stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, **kwargs)
        RUNNING_PROCESSES[server_id] = proc
        SERVER_START_TIMES[server_id] = time.time()
        db.execute("UPDATE servers SET status='running', pid=?, runtime=? WHERE id=?", (proc.pid, runtime, server_id))
        db.commit()
        base_url = request.url_root.rstrip('/') if request else 'http://localhost:3000'
        server_url = f"{base_url}/{server['slug']}/" if server['slug'] else f"{base_url}/"
        write_server_log(server_id, 'SUCCESS', '━' * 45)
        write_server_log(server_id, 'SUCCESS', f'🎉 SERVER IS RUNNING')
        write_server_log(server_id, 'SUCCESS', f'🌐 URL: {server_url}')
        write_server_log(server_id, 'SUCCESS', f'🔌 Port: {user_port} (PID: {proc.pid})')
        write_server_log(server_id, 'SUCCESS', '━' * 45)
        return True, f"Running on port {user_port}", [], False
    except Exception as e:
        write_server_log(server_id, 'ERROR', f'Launch failed: {e}')
        db.execute("UPDATE servers SET status='error', pid=0 WHERE id=?", (server_id,))
        db.commit()
        return False, str(e), [], False

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session and get_current_user(): return redirect(url_for('dashboard'))
    if request.method == 'POST':
        fn = request.form.get('full_name','').strip()
        un = request.form.get('username','').strip().lower()
        em = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        cp = request.form.get('confirm_password','')
        selected_plan = request.form.get('selected_plan', type=int)
        if not all([fn, un, em, pw]):
            flash('All fields are required', 'danger')
            return render_template_string(SIGNUP_HTML, full_name=fn, username=un, email=em)
        if not em.endswith('@gmail.com') or em == '@gmail.com':
            flash('Sign up with a Gmail address', 'danger')
            return render_template_string(SIGNUP_HTML, full_name=fn, username=un, email=em)
        if len(un) < 3:
            flash('Username must be at least 3 characters', 'danger')
            return render_template_string(SIGNUP_HTML, full_name=fn, username=un, email=em)
        if len(pw) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template_string(SIGNUP_HTML, full_name=fn, username=un, email=em)
        if pw != cp:
            flash('Passwords do not match', 'danger')
            return render_template_string(SIGNUP_HTML, full_name=fn, username=un, email=em)
        db = get_db()
        if db.execute("SELECT id FROM users WHERE LOWER(email)=?", (em,)).fetchone():
            flash('This Gmail is already registered', 'danger')
            return render_template_string(SIGNUP_HTML, full_name=fn, username=un, email=em)
        if db.execute("SELECT id FROM users WHERE LOWER(username)=?", (un,)).fetchone():
            flash('This username is already taken', 'danger')
            return render_template_string(SIGNUP_HTML, full_name=fn, username=un, email=em)
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or ''
        if client_ip: client_ip = client_ip.split(',')[0].strip()
        trial_enabled = get_setting('trial_enabled', '1') == '1'
        trial_hours = int(get_setting('trial_hours', '6'))
        trial_limit = int(get_setting('trial_project_limit', '1'))
        trial_used_ip = False
        if trial_enabled:
            if db.execute("SELECT id FROM trial_ips WHERE ip_address=?", (client_ip,)).fetchone():
                trial_used_ip = True
        trial_expires = None
        if trial_enabled and not trial_used_ip:
            trial_expires = datetime.utcnow() + timedelta(hours=trial_hours)
        plim = trial_limit if (trial_enabled and not trial_used_ip) else 0
        cur = db.cursor()
        cur.execute("INSERT INTO users (full_name, username, email, password_hash, role, status, trial_used, signup_ip, trial_expires_at, project_limit) VALUES (?, ?, ?, ?, 'user', 'active', ?, ?, ?, ?)", (fn, un, em, safe_generate_password_hash(pw), 1 if trial_used_ip else 0, client_ip, trial_expires, plim))
        uid = cur.lastrowid
        if trial_enabled and not trial_used_ip:
            try: cur.execute("INSERT INTO trial_ips (ip_address, username, email) VALUES (?, ?, ?)", (client_ip, un, em))
            except sqlite3.IntegrityError: pass
            cur.execute("INSERT INTO trial_history (user_id, ip_address, expires_at) VALUES (?, ?, ?)", (uid, client_ip, trial_expires))
            cur.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, 'Trial Activated', ?)", (uid, f'Your {trial_hours}-hour free trial is now active!'))
        db.commit()
        session.clear()
        session['user_id'] = uid
        session['username'] = un
        session['role'] = 'user'
        session.permanent = True
        if trial_enabled and not trial_used_ip:
            flash(f'Welcome! Your {trial_hours}-hour trial is active.', 'success')
        else:
            flash('Account created. Choose a plan to get started.', 'success')
        if selected_plan:
            return redirect(url_for('buy_redirect', pkg_id=selected_plan))
        return redirect(url_for('dashboard'))
    return render_template_string(SIGNUP_HTML)

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if 'user_id' in session and get_current_user(): return redirect(url_for('dashboard'))
    if request.method == 'POST':
        identifier = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        if not identifier or not password:
            flash('Please fill in all fields', 'danger')
            return render_template_string(SIGNIN_HTML, email=identifier)
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE LOWER(email)=? OR LOWER(username)=?", (identifier, identifier)).fetchone()
        if not user or user['status'] == 'disabled' or not safe_check_password_hash(user['password_hash'], password):
            flash('Incorrect email or password', 'danger')
            return render_template_string(SIGNIN_HTML, email=identifier)
        if not str(user['password_hash']).startswith('pbkdf2:sha256:'):
            try:
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (safe_generate_password_hash(password), user['id']))
                db.commit()
            except Exception: pass
        db.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), user['id']))
        db.commit()
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session.permanent = remember
        flash(f'Welcome back, {user["full_name"]}!', 'success')
        nxt = request.args.get('next')
        if nxt and nxt.startswith('/'): return redirect(nxt)
        return redirect(url_for('dashboard'))
    return render_template_string(SIGNIN_HTML)

@app.route('/signout')
def signout():
    session.clear()
    flash('You have been signed out', 'info')
    return redirect(url_for('home'))

@app.route('/auth/google')
def auth_google():
    if not oauth or not google:
        flash('Google sign-in is not configured', 'warning')
        return redirect(url_for('signin'))
    redirect_uri = url_for('auth_google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google/callback')
def auth_google_callback():
    if not oauth or not google:
        flash('Google sign-in is not configured', 'danger')
        return redirect(url_for('signin'))
    try:
        token = google.authorize_access_token()
        userinfo = token.get('userinfo') or {}
        email = (userinfo.get('email') or '').lower()
        name = userinfo.get('name') or ''
        picture = userinfo.get('picture') or ''
        if not email.endswith('@gmail.com'):
            flash('Please use a Gmail account', 'danger')
            return redirect(url_for('signin'))
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (email,)).fetchone()
        if user:
            if user['status'] == 'disabled':
                flash('This account is suspended', 'danger')
                return redirect(url_for('signin'))
            db.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), user['id']))
            db.commit()
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session.permanent = True
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        base_un = re.sub(r'[^a-z0-9_]', '', email.split('@')[0].lower()) or 'user'
        un = base_un; counter = 1
        while db.execute("SELECT id FROM users WHERE LOWER(username)=?", (un,)).fetchone():
            un = f"{base_un}{counter}"; counter += 1
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or ''
        if client_ip: client_ip = client_ip.split(',')[0].strip()
        trial_enabled = get_setting('trial_enabled', '1') == '1'
        trial_hours = int(get_setting('trial_hours', '6'))
        trial_limit = int(get_setting('trial_project_limit', '1'))
        trial_used_ip = False
        if trial_enabled:
            if db.execute("SELECT id FROM trial_ips WHERE ip_address=?", (client_ip,)).fetchone():
                trial_used_ip = True
        trial_expires = None
        if trial_enabled and not trial_used_ip:
            trial_expires = datetime.utcnow() + timedelta(hours=trial_hours)
        plim = trial_limit if (trial_enabled and not trial_used_ip) else 0
        random_pass = secrets.token_urlsafe(32)
        cur = db.cursor()
        cur.execute("INSERT INTO users (full_name, username, email, password_hash, avatar_url, role, status, trial_used, signup_ip, trial_expires_at, project_limit) VALUES (?, ?, ?, ?, ?, 'user', 'active', ?, ?, ?, ?)", (name or base_un.capitalize(), un, email, safe_generate_password_hash(random_pass), picture, 1 if trial_used_ip else 0, client_ip, trial_expires, plim))
        uid = cur.lastrowid
        if trial_enabled and not trial_used_ip:
            try: cur.execute("INSERT INTO trial_ips (ip_address, username, email) VALUES (?, ?, ?)", (client_ip, un, email))
            except sqlite3.IntegrityError: pass
            cur.execute("INSERT INTO trial_history (user_id, ip_address, expires_at) VALUES (?, ?, ?)", (uid, client_ip, trial_expires))
        db.commit()
        session.clear()
        session['user_id'] = uid
        session['username'] = un
        session['role'] = 'user'
        session.permanent = True
        flash(f'Welcome {name or base_un}! Your account is ready.', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"OAuth error: {e}")
        flash('Google sign-in failed. Please try again.', 'danger')
        return redirect(url_for('signin'))

@app.route('/api/forgot-password/captcha')
def fp_captcha():
    n1 = random.randint(1,10); n2 = random.randint(1,10)
    op = random.choice(['+','-','*'])
    ans = n1+n2 if op=='+' else (n1-n2 if op=='-' else n1*n2)
    session['fp_ans'] = ans; session['fp_verified'] = False; session['fp_email'] = None
    return jsonify({'question': f"{n1} {op} {n2} = ?"})

@app.route('/api/forgot-password/verify-captcha', methods=['POST'])
def fp_vc():
    try: ua = int((request.get_json() or {}).get('answer',''))
    except (ValueError, TypeError): return jsonify({'success': False, 'message': 'Enter a valid number'})
    if session.get('fp_ans') is not None and ua == session.get('fp_ans'):
        session['fp_verified'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Incorrect answer'})

@app.route('/api/forgot-password/verify-email', methods=['POST'])
def fp_ve():
    if not session.get('fp_verified'):
        return jsonify({'success': False, 'message': 'Complete captcha first'})
    em = (request.get_json() or {}).get('email','').strip().lower()
    if not em: return jsonify({'success': False, 'message': 'Enter your email'})
    db = get_db()
    if db.execute("SELECT id FROM users WHERE LOWER(email)=?", (em,)).fetchone():
        session['fp_email'] = em
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Email not registered'})

@app.route('/api/forgot-password/reset', methods=['POST'])
def fp_reset():
    if not session.get('fp_verified') or not session.get('fp_email'):
        return jsonify({'success': False, 'message': 'Session expired. Please try again.'})
    d = request.get_json() or {}
    pw = d.get('password',''); cp = d.get('confirm_password','')
    if not pw or not cp: return jsonify({'success': False, 'message': 'Both fields are required'})
    if pw != cp: return jsonify({'success': False, 'message': 'Passwords do not match'})
    if len(pw) < 6: return jsonify({'success': False, 'message': 'Minimum 6 characters'})
    db = get_db()
    try:
        db.execute("UPDATE users SET password_hash=? WHERE LOWER(email)=?", (safe_generate_password_hash(pw), session.get('fp_email')))
        db.commit()
        session.pop('fp_ans', None); session.pop('fp_verified', None); session.pop('fp_email', None)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/')
def home():
    db = get_db()
    try:
        db.execute("UPDATE servers SET status='expired' WHERE expires_at < ? AND status != 'expired'", (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),))
        db.commit()
    except Exception: pass
    if get_setting('trial_enabled', '1') == '1':
        pkgs = db.execute("SELECT * FROM packages WHERE active=1 ORDER BY sort_order ASC").fetchall()
    else:
        pkgs = db.execute("SELECT * FROM packages WHERE active=1 AND is_trial=0 ORDER BY sort_order ASC").fetchall()
    ts = db.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
    tu = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    trial_enabled = get_setting('trial_enabled', '1') == '1'
    trial_hours = int(get_setting('trial_hours', '6'))
    return render_template_string(HOME_HTML, packages=pkgs, total_servers=ts, total_users=tu, trial_enabled=trial_enabled, trial_hours=trial_hours)

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user(); db = get_db()
    servers = db.execute("SELECT * FROM servers WHERE user_id=? ORDER BY created_at DESC", (user['id'],)).fetchall()
    tf = 0; tb = 0
    udir = os.path.join(SERVERS_DIR, str(user['id']))
    if os.path.exists(udir):
        for root, _, files in os.walk(udir):
            tf += len(files)
            for f in files:
                try: tb += os.path.getsize(os.path.join(root, f))
                except Exception: pass
    storage = f"{tb/1024:.1f} KB" if tb < 1024*1024 else f"{tb/(1024*1024):.1f} MB"
    anns = db.execute("SELECT * FROM announcements WHERE is_active=1 ORDER BY pinned DESC, id DESC LIMIT 5").fetchall()
    can_create, limit_msg = check_project_limit(user)
    current_pkg = None
    if user['plan_id']:
        current_pkg = db.execute("SELECT * FROM packages WHERE id=?", (user['plan_id'],)).fetchone()
    return render_template_string(DASHBOARD_HTML, servers=servers, total_files=tf, storage_formatted=storage, announcements=anns, can_create=can_create, limit_msg=limit_msg, current_pkg=current_pkg)

@app.route('/packages')
@login_required
def packages():
    user = get_current_user(); db = get_db()
    if get_setting('trial_enabled', '1') == '1':
        pkgs = db.execute("SELECT * FROM packages WHERE active=1 ORDER BY sort_order ASC").fetchall()
    else:
        pkgs = db.execute("SELECT * FROM packages WHERE active=1 AND is_trial=0 ORDER BY sort_order ASC").fetchall()
    trial_enabled = get_setting('trial_enabled', '1') == '1'
    trial_hours = int(get_setting('trial_hours', '6'))
    trial_limit = int(get_setting('trial_project_limit', '1'))
    return render_template_string(PACKAGES_HTML, packages=pkgs, user=user, trial_enabled=trial_enabled, trial_hours=trial_hours, trial_limit=trial_limit)

@app.route('/packages/<int:pkg_id>/buy')
def buy_redirect(pkg_id):
    if 'user_id' not in session or not get_current_user():
        return redirect(url_for('signin', next=url_for('checkout', pkg_id=pkg_id)))
    return redirect(url_for('checkout', pkg_id=pkg_id))

@app.route('/checkout/<int:pkg_id>', methods=['GET', 'POST'])
@login_required
def checkout(pkg_id):
    user = get_current_user(); db = get_db()
    pkg = db.execute("SELECT * FROM packages WHERE id=? AND active=1 AND is_trial=0", (pkg_id,)).fetchone()
    if not pkg:
        flash('Plan not found', 'danger')
        return redirect(url_for('packages'))
    if request.method == 'POST':
        pay_method = request.form.get('payment_method', 'primary')
        upis = {'phonepe': get_setting('upi_phonepe', ''), 'gpay': get_setting('upi_gpay', ''), 'paytm': get_setting('upi_paytm', ''), 'fampay': get_setting('upi_fampay', ''), 'bhim': get_setting('upi_bhim', ''), 'amazonpay': get_setting('upi_amazonpay', '')}
        primary = get_setting('primary_upi', 'manual')
        selected_upi = upis.get(primary, '') or next((v for v in upis.values() if v), '')
        if not selected_upi:
            flash('No payment method is configured. Please contact support.', 'warning')
            return redirect(url_for('checkout', pkg_id=pkg_id))
        cur = db.cursor()
        cur.execute("INSERT INTO orders (user_id, package_id, amount, status, payment_method, customer_name, customer_email, customer_phone) VALUES (?, ?, ?, 'pending', ?, ?, ?, '')", (user['id'], pkg['id'], pkg['price'], primary, user['full_name'], user['email']))
        order_id = cur.lastrowid
        db.commit()
        notify_admin('payment', 'New Order', f'@{user["username"]} started payment for {pkg["name"]} (₹{pkg["price"]})', user['id'], order_id)
        return redirect(url_for('payment_page', order_id=order_id))
    upis = {k: get_setting(f'upi_{k}', '') for k in ['phonepe','gpay','paytm','fampay','bhim','amazonpay']}
    primary = get_setting('primary_upi', 'manual')
    available = {k: v for k, v in upis.items() if v}
    auto_enabled = get_setting('payment_autodetect_enabled', '0') == '1'
    return render_template_string(CHECKOUT_HTML, pkg=pkg, user=user, available_methods=available, primary=primary, auto_enabled=auto_enabled)

@app.route('/payment/<int:order_id>')
@login_required
def payment_page(order_id):
    user = get_current_user(); db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user['id'])).fetchone()
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('dashboard'))
    pkg = db.execute("SELECT * FROM packages WHERE id=?", (order['package_id'],)).fetchone()
    upi_map = {'phonepe': get_setting('upi_phonepe', ''), 'gpay': get_setting('upi_gpay', ''), 'paytm': get_setting('upi_paytm', ''), 'fampay': get_setting('upi_fampay', ''), 'bhim': get_setting('upi_bhim', ''), 'amazonpay': get_setting('upi_amazonpay', '')}
    primary = get_setting('primary_upi', 'manual')
    selected_upi = upi_map.get(primary, '') or next((v for v in upi_map.values() if v), '')
    if not selected_upi:
        flash('No payment method configured', 'warning')
        return redirect(url_for('dashboard'))
    qr_data = f"upi://pay?pa={selected_upi}&pn=HostX&am={order['amount']}&cu=INR&tn=Order{order_id}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={quote(qr_data)}"
    auto_enabled = get_setting('payment_autodetect_enabled', '0') == '1'
    fampay_key = get_setting('fampay_api_key', '')
    upi_suffix = selected_upi.split('@')[-1].lower() if '@' in selected_upi else ''
    is_fampay = upi_suffix in ('fam', 'fam2', 'famapp')
    auto_verify = auto_enabled and (is_fampay and fampay_key)
    all_upis = {k: v for k, v in upi_map.items() if v}
    return render_template_string(PAYMENT_HTML, order=order, pkg=pkg, qr_url=qr_url, selected_upi=selected_upi, auto_verify=auto_verify, primary=primary, all_upis=all_upis)

@app.route('/api/payment/check/<int:order_id>')
@login_required
def payment_check(order_id):
    user = get_current_user(); db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user['id'])).fetchone()
    if not order: return jsonify({'success': False})
    return jsonify({'success': True, 'status': order['status'], 'redirect': url_for('dashboard')})

@app.route('/api/payment/manual/<int:order_id>/submit', methods=['POST'])
@login_required
def payment_manual_submit(order_id):
    user = get_current_user(); db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user['id'])).fetchone()
    if not order: return jsonify({'success': False, 'message': 'Order not found'}), 404
    data = request.get_json() or {}
    txn = (data.get('transaction_id') or '').strip()
    if not txn: return jsonify({'success': False, 'message': 'Transaction ID required'})
    db.execute("UPDATE orders SET payment_ref=?, status='pending' WHERE id=?", (txn, order_id))
    db.commit()
    notify_admin('payment', 'Payment Submitted', f'@{user["username"]} submitted TXN: {txn} for order #{order_id} (₹{order["amount"]})', user['id'], order_id)
    return jsonify({'success': True})

def activate_plan(user_id, pkg_id, amount=0, method='manual', notes=''):
    db = get_db()
    pkg = db.execute("SELECT * FROM packages WHERE id=?", (pkg_id,)).fetchone()
    if not pkg: return False, None, 0
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user: return False, None, 0
    now = datetime.utcnow()
    old_exp = user['plan_expires_at']
    if old_exp:
        try:
            if isinstance(old_exp, str): old_exp = datetime.strptime(old_exp.split('.')[0], '%Y-%m-%d %H:%M:%S')
        except Exception: old_exp = None
    base = max(now, old_exp) if old_exp else now
    new_exp = base + timedelta(days=pkg['days'])
    is_renew = old_exp and old_exp > now
    action = 'renewed' if is_renew else 'activated'
    db.execute("UPDATE users SET plan_id=?, plan_expires_at=?, project_limit=?, trial_expires_at=NULL WHERE id=?", (pkg['id'], new_exp, pkg['project_limit'], user_id))
    db.execute("INSERT INTO plan_history (user_id, package_id, action, old_expires_at, new_expires_at, amount, notes) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, pkg['id'], action, old_exp, new_exp, amount, notes or f'Method: {method}'))
    db.execute("UPDATE trial_history SET converted_to_plan=1, converted_at=? WHERE user_id=?", (now, user_id))
    db.commit()
    stopped_servers = db.execute("SELECT id FROM servers WHERE user_id=? AND status IN ('stopped', 'expired')", (user_id,)).fetchall()
    restarted = 0
    for s in stopped_servers:
        try:
            db.execute("UPDATE servers SET expires_at=?, status='stopped' WHERE id=?", (new_exp, s['id']))
            db.commit()
            ok, msg, _, _ = start_server_process(s['id'])
            if ok: restarted += 1
        except Exception: pass
    create_user_notification(user_id, f'Plan {action.capitalize()}', f'Your {pkg["name"]} plan is now active until {new_exp.strftime("%d %b %Y")}. {restarted} servers restarted.')
    return True, new_exp, restarted

@app.route('/servers/create', methods=['GET', 'POST'])
@login_required
def create_server():
    user = get_current_user(); db = get_db()
    can_create, msg = check_project_limit(user)
    if not can_create:
        flash(msg, 'danger')
        return redirect(url_for('packages'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Project name is required', 'danger')
            return redirect(url_for('create_server'))
        now = datetime.utcnow()
        if user['plan_expires_at']:
            try:
                pe = user['plan_expires_at']
                if isinstance(pe, str): pe = datetime.strptime(pe.split('.')[0], '%Y-%m-%d %H:%M:%S')
                exp = pe
            except Exception: exp = now + timedelta(days=1)
        elif user['trial_expires_at']:
            try:
                te = user['trial_expires_at']
                if isinstance(te, str): te = datetime.strptime(te.split('.')[0], '%Y-%m-%d %H:%M:%S')
                exp = te
            except Exception: exp = now + timedelta(hours=6)
        else:
            exp = now + timedelta(days=1)
        base_slug = re.sub(r'[^a-z0-9]', '', name.lower())[:20] or 'project'
        slug = base_slug; counter = 1
        while db.execute("SELECT id FROM servers WHERE slug=?", (slug,)).fetchone():
            slug = f"{base_slug}{counter}"; counter += 1
        cur = db.cursor()
        cur.execute("INSERT INTO servers (user_id, name, slug, runtime, entry_file, status, created_at, expires_at) VALUES (?, ?, ?, 'python', '', 'stopped', ?, ?)", (user['id'], name, slug, now, exp))
        sid = cur.lastrowid
        user_port = 5001 + (sid % 1000)
        cur.execute("UPDATE servers SET port=? WHERE id=?", (user_port, sid))
        db.commit()
        get_server_dir(user['id'], sid)
        write_server_log(sid, 'INFO', f'Project created — upload files to begin')
        create_user_notification(user['id'], 'Project Created', f'Your project "{name}" is ready. Upload files to start.')
        flash(f'Project "{name}" created', 'success')
        return redirect(url_for('server_manage', server_id=sid))
    return render_template_string(CREATE_SERVER_HTML, user=user, limit_msg=msg)

def check_ownership(server_id, user_id=None):
    if user_id is None: user_id = session.get('user_id')
    db = get_db()
    s = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
    if not s: return None
    u = get_current_user()
    if u and is_user_admin(u): return s
    if s['user_id'] != user_id: return None
    return s

@app.route('/servers/<int:server_id>')
@login_required
def server_manage(server_id):
    server = check_ownership(server_id)
    if not server: abort(404)
    exp = server['expires_at']
    if isinstance(exp, str): exp = datetime.strptime(exp.split('.')[0], '%Y-%m-%d %H:%M:%S')
    diff = exp - datetime.utcnow()
    rd = max(0, diff.days); rh = max(0, int(diff.total_seconds()/3600))
    st = SERVER_START_TIMES.get(server_id, 0) if server['status'] == 'running' else 0
    sdir = get_server_dir(server['user_id'], server_id)
    scan = scan_project(sdir)
    base_url = request.url_root.rstrip('/')
    server_url = f"{base_url}/{server['slug']}/" if server['slug'] else ''
    return render_template_string(SERVER_MANAGE_HTML, server=server, scan=scan, remaining_days=rd, remaining_hours=rh, start_time=st, server_url=server_url)

@app.route('/api/servers/<int:server_id>/action', methods=['POST'])
@login_required
def server_action(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    d = request.get_json() if request.is_json else request.form
    action = d.get('action')
    u = get_current_user()
    if action in ('start', 'restart'):
        ok, msg = has_active_access(u)
        if not ok:
            return jsonify({'success': False, 'plan_required': True, 'message': 'Choose a plan to start servers', 'redirect_url': url_for('packages')})
    if action == 'start':
        success, msg, missing, no_entry = start_server_process(server_id)
        if not success:
            if no_entry: return jsonify({'success': False, 'no_entry_file': True, 'message': msg, 'redirect_url': url_for('file_manager', server_id=server_id)})
            if missing: return jsonify({'success': False, 'package_required': True, 'missing_packages': missing, 'message': msg})
            return jsonify({'success': False, 'message': msg})
        s = check_ownership(server_id)
        return jsonify({'success': True, 'message': msg, 'status': 'running', 'pid': s['pid'] if s else 0})
    elif action == 'stop':
        stop_server_process(server_id)
        return jsonify({'success': True, 'message': 'Server stopped', 'status': 'stopped', 'pid': 0})
    elif action == 'restart':
        stop_server_process(server_id); time.sleep(0.5)
        success, msg, missing, no_entry = start_server_process(server_id)
        if not success:
            if no_entry: return jsonify({'success': False, 'no_entry_file': True, 'message': msg, 'redirect_url': url_for('file_manager', server_id=server_id)})
            if missing: return jsonify({'success': False, 'package_required': True, 'missing_packages': missing, 'message': msg})
            return jsonify({'success': False, 'message': msg})
        s = check_ownership(server_id)
        return jsonify({'success': True, 'message': 'Server restarted', 'status': 'running', 'pid': s['pid'] if s else 0})
    return jsonify({'success': False, 'message': 'Invalid action'}), 400

@app.route('/api/servers/<int:server_id>/delete', methods=['POST'])
@login_required
def server_delete(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    db = get_db()
    try: stop_server_process(server_id)
    except Exception: pass
    sdir = os.path.join(SERVERS_DIR, str(server['user_id']), str(server_id))
    if os.path.exists(sdir):
        try: shutil.rmtree(sdir, ignore_errors=True)
        except Exception: pass
    db.execute("DELETE FROM server_logs WHERE server_id=?", (server_id,))
    db.execute("DELETE FROM servers WHERE id=?", (server_id,))
    db.commit()
    log_admin_action('Deleted Server', f'Server #{server_id} ({server["name"]})', f'Owner: {server["user_id"]}')
    notify_admin('system', 'Server Deleted', f'Server "{server["name"]}" (ID #{server_id}) deleted by its owner.', server['user_id'])
    return jsonify({'success': True, 'message': 'Project deleted successfully'})

@app.route('/api/servers/<int:server_id>/logs')
@login_required
def get_logs(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'error': 'Not found'}), 404
    sdir = get_server_dir(server['user_id'], server_id)
    logp = os.path.join(sdir, 'server.log')
    raw = ""
    if os.path.exists(logp):
        try:
            with open(logp, 'r', encoding='utf-8', errors='ignore') as f:
                raw = ''.join(f.readlines()[-300:])
        except Exception as e: raw = f"[ERROR] {e}"
    db = get_db()
    dbl = db.execute("SELECT level, message, created_at FROM server_logs WHERE server_id=? ORDER BY id DESC LIMIT 50", (server_id,)).fetchall()
    db_list = [{'level': r['level'], 'message': r['message'], 'time': str(r['created_at'])} for r in reversed(dbl)]
    st = SERVER_START_TIMES.get(server_id, 0) if server['status'] == 'running' else 0
    base_url = request.url_root.rstrip('/')
    server_url = f"{base_url}/{server['slug']}/" if (server['status'] == 'running' and server['slug']) else ''
    return jsonify({'raw_logs': raw, 'db_logs': db_list, 'status': server['status'], 'pid': server['pid'] if server['status'] == 'running' else 0, 'start_time': st, 'server_url': server_url})

@app.route('/api/servers/<int:server_id>/logs/clear', methods=['POST'])
@login_required
def clear_logs(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'error': 'Not found'}), 404
    sdir = get_server_dir(server['user_id'], server_id)
    logp = os.path.join(sdir, 'server.log')
    try:
        with open(logp, 'w', encoding='utf-8') as f:
            f.write('')
        db = get_db()
        db.execute("DELETE FROM server_logs WHERE server_id=?", (server_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Logs cleared'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/terminal', methods=['POST'])
@login_required
def server_terminal(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    data = request.get_json() or {}
    cmd = (data.get('command') or '').strip()
    if not cmd: return jsonify({'success': False, 'message': 'Command required'})
    blocked = ['rm -rf /', 'shutdown', 'reboot', 'mkfs', 'dd if=', ':(){:|:&};:', 'sudo rm']
    for b in blocked:
        if b in cmd: return jsonify({'success': False, 'message': 'Command blocked for security'}), 403
    sdir = get_server_dir(server['user_id'], server_id)
    pdir = os.path.join(sdir, 'packages')
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{sdir}:{pdir}:" + env.get('PYTHONPATH','')
    env['PORT'] = str(server['port'] or 5001)
    try:
        result = subprocess.run(cmd, shell=True, cwd=sdir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        out = result.stdout or '(no output)'
        return jsonify({'success': True, 'output': out[:10000], 'code': result.returncode})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Command timed out (60s)'}), 408
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/servers/<int:server_id>/files')
@login_required
def file_manager(server_id):
    server = check_ownership(server_id)
    if not server: abort(404)
    rp = request.args.get('path', '').strip('/')
    page = max(1, request.args.get('page', 1, type=int))
    per_page = 100
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, rp)
    if not is_safe_path(sdir, t) or not os.path.exists(t):
        flash('Invalid path', 'danger')
        return redirect(url_for('file_manager', server_id=server_id))
    all_items = []
    try:
        for e in os.scandir(t):
            st = e.stat(); is_dir = e.is_dir(); size = st.st_size
            if is_dir:
                try: cnt = len(os.listdir(e.path)); sz = f"{cnt} items"
                except Exception: sz = '?'
            elif size < 1024: sz = f"{size} B"
            elif size < 1024*1024: sz = f"{size/1024:.1f} KB"
            else: sz = f"{size/(1024*1024):.1f} MB"
            all_items.append({'name': e.name, 'is_dir': is_dir, 'size': sz, 'modified': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M'), 'is_zip': e.name.lower().endswith('.zip'), 'is_py': e.name.lower().endswith('.py'), 'is_entry': e.name == server['entry_file']})
    except Exception as ex:
        flash(f'Error reading directory: {ex}', 'danger')
    all_items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    total = len(all_items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    items = all_items[start:start + per_page]
    crumbs = []
    if rp:
        acc = ''
        for p in rp.split('/'):
            acc = f"{acc}/{p}" if acc else p
            crumbs.append({'name': p, 'path': acc})
    return render_template_string(FILE_MANAGER_HTML, server=server, items=items, current_path=rp, breadcrumbs=crumbs, total_items=total, current_page=page, total_pages=total_pages)

@app.route('/api/servers/<int:server_id>/files/upload', methods=['POST'])
@login_required
def upload_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    rp = request.form.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    td = os.path.join(sdir, rp)
    if not is_safe_path(sdir, td): return jsonify({'success': False, 'message': 'Invalid path'}), 403
    if 'files' not in request.files: return jsonify({'success': False, 'message': 'No files uploaded'}), 400
    files = request.files.getlist('files')
    cnt = 0; zips = 0
    for f in files:
        if f and f.filename:
            fn = secure_filename(f.filename)
            sp = os.path.join(td, fn)
            f.save(sp)
            if fn.lower().endswith('.zip') or zipfile.is_zipfile(sp):
                try:
                    with zipfile.ZipFile(sp, 'r') as zf:
                        for m in zf.namelist():
                            mp = os.path.abspath(os.path.join(td, m))
                            if not is_safe_path(sdir, mp):
                                os.remove(sp); return jsonify({'success': False, 'message': f'Unsafe path in ZIP: {m}'}), 400
                        zf.extractall(td)
                    zips += 1; os.remove(sp)
                except Exception: cnt += 1
            else: cnt += 1
    write_server_log(server_id, 'INFO', f'Uploaded {cnt} file(s), extracted {zips} ZIP(s)')
    scan = scan_project(sdir)
    db = get_db()
    if scan['entry_file'] and (not server['entry_file'] or server['entry_file'] not in scan['py_files']):
        db.execute("UPDATE servers SET entry_file=? WHERE id=?", (scan['entry_file'], server_id))
        db.commit()
    msg = f'Uploaded {cnt} file(s)' + (f', extracted {zips} ZIP(s)' if zips else '')
    return jsonify({'success': True, 'message': msg, 'scan': scan})

@app.route('/api/servers/<int:server_id>/files/create-folder', methods=['POST'])
@login_required
def create_folder(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    path = request.form.get('path','').strip('/')
    name = secure_filename(request.form.get('folder_name','').strip())
    if not name: return jsonify({'success': False, 'message': 'Invalid folder name'}), 400
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path, name)
    if not is_safe_path(sdir, t): return jsonify({'success': False, 'message': 'Invalid path'}), 403
    try:
        os.makedirs(t, exist_ok=False)
        return jsonify({'success': True, 'message': f'Folder "{name}" created'})
    except FileExistsError: return jsonify({'success': False, 'message': 'Folder already exists'}), 400
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/create-file', methods=['POST'])
@login_required
def create_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    path = request.form.get('path','').strip('/')
    name = secure_filename(request.form.get('file_name','').strip())
    if not name: return jsonify({'success': False, 'message': 'Invalid file name'}), 400
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path, name)
    if not is_safe_path(sdir, t): return jsonify({'success': False, 'message': 'Invalid path'}), 403
    try:
        if os.path.exists(t): return jsonify({'success': False, 'message': 'File already exists'}), 400
        with open(t, 'w', encoding='utf-8') as f: f.write('')
        return jsonify({'success': True, 'message': f'File "{name}" created'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/read')
@login_required
def read_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    path = request.args.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t) or not os.path.isfile(t):
        return jsonify({'success': False, 'message': 'File not found'}), 404
    try:
        with open(t, 'r', encoding='utf-8', errors='ignore') as f:
            return jsonify({'success': True, 'content': f.read(), 'filename': os.path.basename(t)})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/save', methods=['POST'])
@login_required
def save_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    d = request.get_json() or {}
    path = d.get('path','').strip('/')
    content = d.get('content','')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t): return jsonify({'success': False, 'message': 'Invalid path'}), 403
    try:
        with open(t, 'w', encoding='utf-8') as f: f.write(content)
        return jsonify({'success': True, 'message': 'File saved successfully'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/delete', methods=['POST'])
@login_required
def delete_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    d = request.get_json() or {}
    path = d.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t) or t == sdir:
        return jsonify({'success': False, 'message': 'Invalid path'}), 403
    try:
        if os.path.isdir(t): shutil.rmtree(t)
        elif os.path.isfile(t): os.remove(t)
        return jsonify({'success': True, 'message': 'Deleted successfully'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/rename', methods=['POST'])
@login_required
def rename_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    d = request.get_json() or {}
    old = d.get('old_path','').strip('/')
    new = secure_filename(d.get('new_name','').strip())
    if not new: return jsonify({'success': False, 'message': 'Invalid name'}), 400
    sdir = get_server_dir(server['user_id'], server_id)
    src = os.path.join(sdir, old)
    dst = os.path.join(os.path.dirname(src), new)
    if not is_safe_path(sdir, src) or not is_safe_path(sdir, dst):
        return jsonify({'success': False, 'message': 'Invalid path'}), 403
    try:
        os.rename(src, dst)
        return jsonify({'success': True, 'message': f'Renamed to {new}'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/unzip', methods=['POST'])
@login_required
def unzip_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Server not found'}), 404
    d = request.get_json() or {}
    zp = d.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, zp)
    ed = os.path.dirname(t)
    if not is_safe_path(sdir, t) or not os.path.isfile(t):
        return jsonify({'success': False, 'message': 'ZIP file not found'}), 404
    try:
        with zipfile.ZipFile(t, 'r') as zf:
            for m in zf.namelist():
                mp = os.path.abspath(os.path.join(ed, m))
                if not is_safe_path(sdir, mp):
                    return jsonify({'success': False, 'message': f'Unsafe path: {m}'}), 400
            zf.extractall(ed)
        scan = scan_project(sdir)
        return jsonify({'success': True, 'message': 'Extracted successfully', 'scan': scan})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/servers/<int:server_id>/files/download')
@login_required
def download_file(server_id):
    server = check_ownership(server_id)
    if not server: abort(404)
    path = request.args.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t) or not os.path.isfile(t): abort(404)
    return send_file(t, as_attachment=True)

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = get_current_user(); db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'upload_avatar':
            f = request.files.get('avatar')
            if not f or not f.filename:
                flash('Please select a file', 'warning')
                return redirect(url_for('account'))
            ext = f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
            if ext not in {'png','jpg','jpeg','webp','gif','svg'}:
                flash('Invalid file format', 'danger')
                return redirect(url_for('account'))
            udir = os.path.join(AVATARS_DIR, f"u_{user['id']}")
            os.makedirs(udir, exist_ok=True)
            for old in os.listdir(udir):
                try: os.remove(os.path.join(udir, old))
                except Exception: pass
            fname = f"a_{int(time.time())}.{ext}"
            f.save(os.path.join(udir, fname))
            url = f"/static/avatars/u_{user['id']}/{fname}"
            db.execute("UPDATE users SET avatar_url=? WHERE id=?", (url, user['id']))
            db.commit()
            flash('Profile picture updated', 'success')
            return redirect(url_for('account'))
        elif action == 'remove_avatar':
            udir = os.path.join(AVATARS_DIR, f"u_{user['id']}")
            if os.path.exists(udir):
                for old in os.listdir(udir):
                    try: os.remove(os.path.join(udir, old))
                    except Exception: pass
            db.execute("UPDATE users SET avatar_url='' WHERE id=?", (user['id'],))
            db.commit()
            flash('Profile picture removed', 'info')
            return redirect(url_for('account'))
        elif action == 'update_profile':
            fn = request.form.get('full_name','').strip()
            bio = request.form.get('bio','').strip()
            if not fn:
                flash('Full name is required', 'danger')
                return redirect(url_for('account'))
            db.execute("UPDATE users SET full_name=?, bio=? WHERE id=?", (fn, bio, user['id']))
            db.commit()
            flash('Profile updated successfully', 'success')
            return redirect(url_for('account'))
        elif action == 'change_password':
            cur = request.form.get('current_password','')
            new = request.form.get('new_password','')
            cf = request.form.get('confirm_new_password','')
            if not safe_check_password_hash(user['password_hash'], cur):
                flash('Current password is incorrect', 'danger')
                return redirect(url_for('account'))
            if len(new) < 6:
                flash('Password must be at least 6 characters', 'danger')
                return redirect(url_for('account'))
            if new != cf:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('account'))
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (safe_generate_password_hash(new), user['id']))
            db.commit()
            flash('Password changed successfully', 'success')
            return redirect(url_for('account'))
    return render_template_string(ACCOUNT_HTML, user=user)

@app.route('/api/notifications')
@login_required
def get_notifs():
    user = get_current_user(); db = get_db()
    cnt = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=?", (user['id'],)).fetchone()[0]
    if cnt == 0:
        db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)", (user['id'], f'Welcome to {get_setting("vip_site_name", "HostX VIP")}', f'Hi {user["full_name"]}! Your account is ready.'))
        db.commit()
    rows = db.execute("SELECT id, title, message, is_read, created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user['id'],)).fetchall()
    un = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user['id'],)).fetchone()[0]
    return jsonify({'success': True, 'notifications': [{'id': r['id'], 'title': r['title'], 'message': r['message'], 'is_read': r['is_read'], 'created_at': str(r['created_at'])} for r in rows], 'unread_count': un})

@app.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_read():
    user = get_current_user(); db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user['id'],))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/notifications/clear-all', methods=['POST'])
@login_required
def clear_notifs():
    user = get_current_user(); db = get_db()
    db.execute("DELETE FROM notifications WHERE user_id=?", (user['id'],))
    db.commit()
    return jsonify({'success': True, 'unread_count': 0})

@app.route('/api/notifications/<int:nid>/delete', methods=['POST'])
@login_required
def del_notif(nid):
    user = get_current_user(); db = get_db()
    db.execute("DELETE FROM notifications WHERE id=? AND user_id=?", (nid, user['id']))
    db.commit()
    un = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user['id'],)).fetchone()[0]
    return jsonify({'success': True, 'unread_count': un})
    
    
# ============================================================
# ADMIN ROUTES
# ============================================================
@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    tu = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    ts = db.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
    au = db.execute("SELECT COUNT(*) FROM users WHERE status='active'").fetchone()[0]
    du = db.execute("SELECT COUNT(*) FROM users WHERE status='disabled'").fetchone()[0]
    rs = db.execute("SELECT COUNT(*) FROM servers WHERE status='running'").fetchone()[0]
    today_rev = db.execute("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='paid' AND DATE(paid_at)=DATE('now')").fetchone()[0]
    total_rev = db.execute("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='paid'").fetchone()[0]
    pending_orders = db.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]
    trial_users = db.execute("SELECT COUNT(*) FROM users WHERE trial_expires_at > ? AND plan_id=0", (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),)).fetchone()[0]
    total_trials = db.execute("SELECT COUNT(*) FROM trial_history").fetchone()[0]
    converted = db.execute("SELECT COUNT(*) FROM trial_history WHERE converted_to_plan=1").fetchone()[0]
    conv_rate = round((converted / total_trials * 100) if total_trials > 0 else 0, 1)
    tf = 0; tb = 0
    if os.path.exists(SERVERS_DIR):
        for root, _, files in os.walk(SERVERS_DIR):
            tf += len(files)
            for f in files:
                try: tb += os.path.getsize(os.path.join(root, f))
                except Exception: pass
    st = f"{tb/(1024*1024):.1f} MB" if tb > 1024*1024 else f"{tb/1024:.1f} KB"
    ru = db.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 6").fetchall()
    rl = db.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT 8").fetchall()
    rn = db.execute("SELECT * FROM admin_notifications WHERE is_read=0 ORDER BY id DESC LIMIT 10").fetchall()
    return render_template_string(ADMIN_DASHBOARD_HTML, total_users=tu, total_servers=ts, active_users=au, disabled_users=du, running_servers=rs, today_revenue=today_rev, total_revenue=total_rev, pending_orders=pending_orders, trial_users=trial_users, conversion_rate=conv_rate, total_files=tf, total_storage_formatted=st, recent_users=ru, recent_logs=rl, recent_notifications=rn)

@app.route('/admin/orders')
@admin_permission_required('manage_orders')
def admin_orders():
    db = get_db()
    status = request.args.get('status', 'all')
    if status == 'all':
        orders = db.execute("SELECT o.*, u.username, u.email, u.full_name, p.name as pkg_name FROM orders o JOIN users u ON o.user_id=u.id JOIN packages p ON o.package_id=p.id ORDER BY o.id DESC LIMIT 200").fetchall()
    else:
        orders = db.execute("SELECT o.*, u.username, u.email, u.full_name, p.name as pkg_name FROM orders o JOIN users u ON o.user_id=u.id JOIN packages p ON o.package_id=p.id WHERE o.status=? ORDER BY o.id DESC LIMIT 200", (status,)).fetchall()
    return render_template_string(ADMIN_ORDERS_HTML, orders=orders, current_status=status)

@app.route('/admin/orders/<int:order_id>/approve', methods=['POST'])
@admin_permission_required('manage_orders')
def admin_approve_order(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('admin_orders'))
    if order['status'] == 'paid':
        flash('This order is already approved', 'info')
        return redirect(url_for('admin_orders'))
    now = datetime.utcnow()
    db.execute("UPDATE orders SET status='paid', paid_at=? WHERE id=?", (now, order_id))
    db.commit()
    activate_plan(order['user_id'], order['package_id'], order['amount'], order['payment_method'], 'Admin approved')
    notify_admin('payment', 'Order Approved', f'Order #{order_id} approved by admin', order['user_id'], order_id)
    log_admin_action('Approved Order', f'Order #{order_id}', f'Amount: ₹{order["amount"]}')
    flash(f'Order #{order_id} approved', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/orders/<int:order_id>/reject', methods=['POST'])
@admin_permission_required('manage_orders')
def admin_reject_order(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('admin_orders'))
    db.execute("UPDATE orders SET status='failed' WHERE id=?", (order_id,))
    db.commit()
    create_user_notification(order['user_id'], 'Order Failed', f'Your order #{order_id} could not be processed. Please contact support.')
    log_admin_action('Rejected Order', f'Order #{order_id}', f'Amount: ₹{order["amount"]}')
    flash(f'Order #{order_id} rejected', 'info')
    return redirect(url_for('admin_orders'))

@app.route('/admin/plans')
@admin_permission_required('manage_orders')
def admin_plans():
    db = get_db()
    history = db.execute("SELECT ph.*, u.username, u.email, u.full_name, p.name as pkg_name FROM plan_history ph JOIN users u ON ph.user_id=u.id JOIN packages p ON ph.package_id=p.id ORDER BY ph.id DESC LIMIT 200").fetchall()
    return render_template_string(ADMIN_PLANS_HTML, history=history)

@app.route('/admin/trials')
@admin_permission_required('manage_orders')
def admin_trials():
    db = get_db()
    trials = db.execute("SELECT th.*, u.username, u.email, u.full_name FROM trial_history th JOIN users u ON th.user_id=u.id ORDER BY th.id DESC LIMIT 200").fetchall()
    total = db.execute("SELECT COUNT(*) FROM trial_history").fetchone()[0]
    converted = db.execute("SELECT COUNT(*) FROM trial_history WHERE converted_to_plan=1").fetchone()[0]
    return render_template_string(ADMIN_TRIALS_HTML, trials=trials, total=total, converted=converted)

@app.route('/admin/users')
@admin_permission_required('manage_users')
def admin_users():
    q = request.args.get('q','').strip()
    db = get_db()
    if q:
        users = db.execute("SELECT u.*, (SELECT COUNT(*) FROM servers WHERE user_id=u.id) as server_count FROM users u WHERE u.email LIKE ? OR u.username LIKE ? OR u.full_name LIKE ? ORDER BY u.id DESC", (f'%{q}%', f'%{q}%', f'%{q}%')).fetchall()
    else:
        users = db.execute("SELECT u.*, (SELECT COUNT(*) FROM servers WHERE user_id=u.id) as server_count FROM users u ORDER BY u.id DESC").fetchall()
    return render_template_string(ADMIN_USERS_HTML, users=users, search_query=q)

@app.route('/admin/users/<int:user_id>/update', methods=['POST'])
@admin_permission_required('manage_users')
def admin_update_user(user_id):
    db = get_db()
    ca = get_current_user(); cs = is_user_super_admin(ca)
    t = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not t:
        flash('User not found', 'danger')
        return redirect(url_for('admin_users'))
    ts = is_user_super_admin(t)
    if ts and not cs:
        flash('Only Super Admin can edit Super Admin accounts', 'danger')
        return redirect(url_for('admin_users'))
    fn = request.form.get('full_name','').strip()
    un = request.form.get('username','').strip().lower()
    em = request.form.get('email','').strip().lower()
    bio = request.form.get('bio','').strip()
    st = request.form.get('status', t['status']).strip().lower()
    ri = request.form.get('role', t['role']).strip().lower()
    pl_raw = request.form.get('project_limit')
    np_ = request.form.get('new_password','').strip()
    if cs:
        if ri == 'super_admin': fr, fi, fs_, fp = 'super_admin', 1, 1, 'all'
        elif ri == 'admin':
            fr, fi, fs_ = 'admin', 1, 0
            perms = request.form.getlist('permissions')
            fp = ','.join(perms) if perms else 'manage_users,manage_payments,manage_files,manage_settings,manage_announcements,manage_broadcasts,manage_orders,view_logs'
        else:
            fr, fi, fs_, fp = 'user', 0, 0, ''
    else:
        fr, fi, fs_, fp = t['role'], t['is_admin'], t['is_super_admin'], t['admin_permissions']
    if not fn or not un or not em:
        flash('Name, username and email are required', 'danger')
        return redirect(url_for('admin_users'))
    if not em.endswith('@gmail.com'):
        flash('Email must be a Gmail address', 'danger')
        return redirect(url_for('admin_users'))
    if len(un) < 3:
        flash('Username must be at least 3 characters', 'danger')
        return redirect(url_for('admin_users'))
    if db.execute("SELECT id FROM users WHERE LOWER(email)=? AND id!=?", (em, user_id)).fetchone():
        flash('This Gmail is already in use', 'danger')
        return redirect(url_for('admin_users'))
    if db.execute("SELECT id FROM users WHERE LOWER(username)=? AND id!=?", (un, user_id)).fetchone():
        flash('This username is already taken', 'danger')
        return redirect(url_for('admin_users'))
    try: plim = int(pl_raw) if pl_raw is not None and pl_raw != '' else t['project_limit']
    except ValueError: plim = t['project_limit']
    if np_:
        if len(np_) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return redirect(url_for('admin_users'))
        db.execute("UPDATE users SET full_name=?, username=?, email=?, bio=?, status=?, role=?, is_admin=?, is_super_admin=?, admin_permissions=?, project_limit=?, password_hash=? WHERE id=?", (fn, un, em, bio, st, fr, fi, fs_, fp, plim, safe_generate_password_hash(np_), user_id))
    else:
        db.execute("UPDATE users SET full_name=?, username=?, email=?, bio=?, status=?, role=?, is_admin=?, is_super_admin=?, admin_permissions=?, project_limit=? WHERE id=?", (fn, un, em, bio, st, fr, fi, fs_, fp, plim, user_id))
    db.commit()
    if st == 'disabled' and t['status'] != 'disabled':
        for s in db.execute("SELECT id FROM servers WHERE user_id=?", (user_id,)).fetchall():
            stop_server_process(s['id'])
    log_admin_action('Updated User', f'User #{user_id} (@{un})', f'Status={st}, Role={fr}, Limit={plim}')
    flash(f'User @{un} updated', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_permission_required('manage_users')
def admin_toggle_status(user_id):
    db = get_db()
    ca = get_current_user(); cs = is_user_super_admin(ca)
    t = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not t:
        flash('User not found', 'danger')
        return redirect(url_for('admin_users'))
    if is_user_admin(t) and not cs:
        flash('Only Super Admin can manage admin accounts', 'danger')
        return redirect(url_for('admin_users'))
    ns = 'disabled' if t['status'] == 'active' else 'active'
    db.execute("UPDATE users SET status=? WHERE id=?", (ns, user_id))
    db.commit()
    if ns == 'disabled':
        for s in db.execute("SELECT id FROM servers WHERE user_id=?", (user_id,)).fetchall():
            stop_server_process(s['id'])
    log_admin_action(f'User {ns}', f'User #{user_id}', f'@{t["username"]}')
    flash(f'@{t["username"]} is now {ns}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/impersonate')
@admin_permission_required('manage_users')
def admin_impersonate(user_id):
    db = get_db()
    t = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not t:
        flash('User not found', 'danger')
        return redirect(url_for('admin_users'))
    log_admin_action('Support Login', f'User #{user_id} (@{t["username"]})', 'Impersonation')
    session['real_admin_id'] = session['user_id']
    session['real_admin_username'] = session['username']
    session['is_impersonating'] = True
    session['user_id'] = t['id']
    session['username'] = t['username']
    session['role'] = t['role']
    flash(f'Now viewing as @{t["username"]}', 'info')
    return redirect(url_for('dashboard'))

@app.route('/admin/stop-impersonate')
def stop_impersonating():
    if not session.get('is_impersonating'):
        return redirect(url_for('dashboard'))
    rid = session.get('real_admin_id')
    db = get_db()
    a = db.execute("SELECT * FROM users WHERE id=?", (rid,)).fetchone()
    if a:
        session.clear()
        session['user_id'] = a['id']
        session['username'] = a['username']
        session['role'] = a['role']
        flash('Returned to admin panel', 'success')
        return redirect(url_for('admin_users'))
    session.clear()
    return redirect(url_for('signin'))

@app.route('/admin/payments', methods=['GET', 'POST'])
@admin_permission_required('manage_settings')
def admin_payments():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'update_upi':
            for k in ['phonepe','gpay','paytm','fampay','bhim','amazonpay']:
                val = request.form.get(f'upi_{k}', '').strip()
                set_setting(f'upi_{k}', val)
            primary = request.form.get('primary_upi', 'manual').strip()
            set_setting('primary_upi', primary)
            set_setting('payment_manual_enabled', '1' if request.form.get('payment_manual_enabled') in ('1','true','on') else '0')
            log_admin_action('Updated UPI settings', 'Payment', f'Primary: {primary}')
            flash('Payment settings saved', 'success')
            return redirect(url_for('admin_payments'))
        elif action == 'update_auto':
            set_setting('payment_autodetect_enabled', '1' if request.form.get('payment_autodetect_enabled') in ('1','true','on') else '0')
            set_setting('fampay_api_key', request.form.get('fampay_api_key', '').strip())
            set_setting('razorpay_key_id', request.form.get('razorpay_key_id', '').strip())
            set_setting('razorpay_key_secret', request.form.get('razorpay_key_secret', '').strip())
            log_admin_action('Updated auto-payment', 'Payment', 'FamPay / Razorpay settings')
            flash('Auto-payment settings saved', 'success')
            return redirect(url_for('admin_payments'))
    settings = {k: get_setting(k, '') for k in ['upi_phonepe','upi_gpay','upi_paytm','upi_fampay','upi_bhim','upi_amazonpay','fampay_api_key','razorpay_key_id','razorpay_key_secret','payment_manual_enabled','payment_autodetect_enabled','primary_upi']}
    qr_previews = {}
    for k in ['phonepe','gpay','paytm','fampay','bhim','amazonpay']:
        upi = settings.get(f'upi_{k}', '')
        if upi:
            qr_data = f"upi://pay?pa={upi}&pn=HostX&cu=INR"
            qr_previews[k] = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(qr_data)}"
    return render_template_string(ADMIN_PAYMENTS_HTML, settings=settings, qr_previews=qr_previews)

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_permission_required('manage_settings')
def admin_settings():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action','')
        if action == 'upload_logo':
            f = request.files.get('logo')
            if not f or not f.filename:
                flash('No file selected', 'warning')
                return redirect(url_for('admin_settings'))
            ext = f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
            if ext not in {'png','jpg','jpeg','webp','gif','svg','ico'}:
                flash('Invalid image format', 'danger')
                return redirect(url_for('admin_settings'))
            for old in os.listdir(BRANDING_DIR):
                try: os.remove(os.path.join(BRANDING_DIR, old))
                except Exception: pass
            fname = f"logo_{int(time.time())}.{ext}"
            f.save(os.path.join(BRANDING_DIR, fname))
            set_setting('site_logo_url', f"/static/branding/{fname}")
            flash('Logo updated', 'success')
            return redirect(url_for('admin_settings'))
        elif action == 'reset_logo':
            for old in os.listdir(BRANDING_DIR):
                try: os.remove(os.path.join(BRANDING_DIR, old))
                except Exception: pass
            set_setting('site_logo_url', '')
            flash('Logo reset to default', 'info')
            return redirect(url_for('admin_settings'))
        elif action == 'update_branding':
            sn = request.form.get('site_name','HostX').strip() or 'HostX'
            vn = request.form.get('vip_site_name','HostX VIP').strip() or 'HostX VIP'
            set_setting('site_name', sn)
            set_setting('vip_site_name', vn)
            flash('Branding updated', 'success')
            return redirect(url_for('admin_settings'))
        elif action == 'update_trial':
            en = '1' if request.form.get('trial_enabled') in ('1','true','on') else '0'
            try: th = max(1, int(request.form.get('trial_hours', '6')))
            except ValueError: th = 6
            try: tl = max(1, int(request.form.get('trial_project_limit', '1')))
            except ValueError: tl = 1
            set_setting('trial_enabled', en)
            set_setting('trial_hours', str(th))
            set_setting('trial_project_limit', str(tl))
            flash('Trial settings saved', 'success')
            return redirect(url_for('admin_settings'))
        elif action == 'update_maintenance':
            mm = '1' if request.form.get('maintenance_mode') in ('1','true','on') else '0'
            msg = request.form.get('maintenance_message','').strip()
            set_setting('maintenance_mode', mm)
            set_setting('maintenance_message', msg)
            flash('Maintenance settings saved', 'success')
            return redirect(url_for('admin_settings'))
        elif action == 'update_self_ping':
            en = '1' if request.form.get('self_ping_enabled') in ('1','true','on') else '0'
            try: iv = max(1, int(request.form.get('self_ping_interval','5')))
            except ValueError: iv = 5
            set_setting('self_ping_enabled', en)
            set_setting('self_ping_interval', str(iv))
            flash('Self-ping settings saved', 'success')
            return redirect(url_for('admin_settings'))
    settings = {
        'maintenance_mode': get_setting('maintenance_mode','0'),
        'maintenance_message': get_setting('maintenance_message',''),
        'site_name': get_setting('site_name','HostX'),
        'vip_site_name': get_setting('vip_site_name','HostX VIP'),
        'site_logo_url': get_setting('site_logo_url',''),
        'self_ping_enabled': get_setting('self_ping_enabled','1'),
        'self_ping_interval': get_setting('self_ping_interval','5'),
        'trial_enabled': get_setting('trial_enabled','1'),
        'trial_hours': get_setting('trial_hours','6'),
        'trial_project_limit': get_setting('trial_project_limit','1'),
    }
    pkgs = db.execute("SELECT * FROM packages ORDER BY sort_order ASC").fetchall()
    return render_template_string(ADMIN_SETTINGS_HTML, settings=settings, packages=pkgs)

@app.route('/admin/packages/update', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_update_pkg():
    db = get_db()
    pid = request.form.get('id')
    name = request.form.get('name','').strip() or 'Package'
    try: price = max(0, int(request.form.get('price',0)))
    except ValueError: price = 0
    try: days = max(1, int(request.form.get('days',1)))
    except ValueError: days = 1
    try: plim = int(request.form.get('project_limit',1))
    except ValueError: plim = 1
    features = request.form.get('features','').strip()
    pop = 1 if request.form.get('is_popular') in ('1','true','on') else 0
    act = 1 if request.form.get('active') in ('1','true','on') else 0
    db.execute("UPDATE packages SET name=?, price=?, days=?, project_limit=?, features=?, is_popular=?, active=? WHERE id=?", (name, price, days, plim, features, pop, act, pid))
    db.commit()
    flash(f'Package "{name}" updated', 'success')
    return redirect(url_for('admin_settings'))

@app.route('/admin/packages/create', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_create_pkg():
    db = get_db()
    name = request.form.get('name','').strip() or 'New Package'
    try: price = max(0, int(request.form.get('price',0)))
    except ValueError: price = 0
    try: days = max(1, int(request.form.get('days',1)))
    except ValueError: days = 1
    try: plim = int(request.form.get('project_limit',1))
    except ValueError: plim = 1
    features = request.form.get('features','').strip()
    db.execute("INSERT INTO packages (name, price, days, project_limit, features, active) VALUES (?,?,?,?,?,1)", (name, price, days, plim, features))
    db.commit()
    flash(f'Package "{name}" created', 'success')
    return redirect(url_for('admin_settings'))

@app.route('/admin/packages/<int:pid>/delete', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_delete_pkg(pid):
    db = get_db()
    p = db.execute("SELECT * FROM packages WHERE id=?", (pid,)).fetchone()
    if p:
        db.execute("DELETE FROM packages WHERE id=?", (pid,))
        db.commit()
        flash(f'Package "{p["name"]}" deleted', 'info')
    return redirect(url_for('admin_settings'))

@app.route('/admin/announcements', methods=['GET'])
@admin_permission_required('manage_announcements')
def admin_announcements():
    db = get_db()
    anns = db.execute("SELECT * FROM announcements ORDER BY pinned DESC, id DESC").fetchall()
    return render_template_string(ADMIN_ANNOUNCEMENTS_HTML, announcements=anns)

@app.route('/admin/announcements/create', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_create_ann():
    title = request.form.get('title','').strip()
    content = request.form.get('content','').strip()
    atype = request.form.get('type','update').strip().lower()
    if atype not in ('update','info','warning','maintenance'): atype = 'update'
    active = 1 if request.form.get('is_active') in ('1','true','on') else 0
    pinned = 1 if request.form.get('pinned') in ('1','true','on') else 0
    if not title or not content:
        flash('Title and content are required', 'danger')
        return redirect(url_for('admin_announcements'))
    u = get_current_user(); creator = u['full_name'] if u else 'Administrator'
    db = get_db()
    db.execute("INSERT INTO announcements (title, content, type, is_active, pinned, created_by) VALUES (?,?,?,?,?,?)", (title, content, atype, active, pinned, creator))
    db.commit()
    flash('Announcement published', 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:aid>/toggle', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_toggle_ann(aid):
    db = get_db()
    a = db.execute("SELECT * FROM announcements WHERE id=?", (aid,)).fetchone()
    if not a:
        flash('Announcement not found', 'danger')
        return redirect(url_for('admin_announcements'))
    new = 0 if a['is_active'] else 1
    db.execute("UPDATE announcements SET is_active=? WHERE id=?", (new, aid))
    db.commit()
    flash(f'Announcement {"activated" if new else "deactivated"}', 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:aid>/toggle-pin', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_toggle_pin(aid):
    db = get_db()
    a = db.execute("SELECT * FROM announcements WHERE id=?", (aid,)).fetchone()
    if not a:
        flash('Announcement not found', 'danger')
        return redirect(url_for('admin_announcements'))
    new = 0 if a['pinned'] else 1
    db.execute("UPDATE announcements SET pinned=? WHERE id=?", (new, aid))
    db.commit()
    flash(f'Announcement {"pinned" if new else "unpinned"}', 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:aid>/delete', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_delete_ann(aid):
    db = get_db()
    db.execute("DELETE FROM announcements WHERE id=?", (aid,))
    db.commit()
    flash('Announcement deleted', 'info')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/broadcast', methods=['GET', 'POST'])
@admin_permission_required('manage_broadcasts')
def admin_broadcast():
    db = get_db(); ca = get_current_user()
    if request.method == 'POST':
        tt = request.form.get('target_type','all').strip()
        tuid = request.form.get('target_user_id','').strip()
        title = request.form.get('title','').strip()
        msg = request.form.get('message','').strip()
        if not title or not msg:
            flash('Title and message are required', 'danger')
            return redirect(url_for('admin_broadcast'))
        if tt == 'all':
            users = db.execute("SELECT id FROM users WHERE status='active'").fetchall()
            for u in users:
                db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)", (u['id'], title, msg))
            db.execute("INSERT INTO broadcast_logs (admin_id, admin_username, title, message, category, target_type, recipients_count) VALUES (?,?,?,?,?,'all',?)", (ca['id'], ca['username'], title, msg, 'announcement', len(users)))
            db.commit()
            flash(f'Sent to {len(users)} users', 'success')
            return redirect(url_for('admin_broadcast'))
        elif tt == 'specific':
            try: uid = int(tuid)
            except ValueError:
                flash('Invalid user selected', 'danger')
                return redirect(url_for('admin_broadcast'))
            tu = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not tu:
                flash('User not found', 'danger')
                return redirect(url_for('admin_broadcast'))
            db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)", (tu['id'], title, msg))
            db.execute("INSERT INTO broadcast_logs (admin_id, admin_username, title, message, category, target_type, target_user_id, target_username, recipients_count) VALUES (?,?,?,?,?,'specific',?,?,1)", (ca['id'], ca['username'], title, msg, 'announcement', tu['id'], tu['username']))
            db.commit()
            flash(f'Sent to @{tu["username"]}', 'success')
            return redirect(url_for('admin_broadcast'))
    users = db.execute("SELECT id, full_name, username, email FROM users WHERE status='active' ORDER BY username ASC").fetchall()
    logs = db.execute("SELECT * FROM broadcast_logs ORDER BY id DESC LIMIT 30").fetchall()
    return render_template_string(ADMIN_BROADCAST_HTML, users=users, broadcasts=logs)

@app.route('/admin/logs')
@admin_permission_required('view_logs')
def admin_logs():
    db = get_db()
    logs = db.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT 200").fetchall()
    return render_template_string(ADMIN_LOGS_HTML, logs=logs)

@app.route('/admin/notifications')
@admin_permission_required('manage_orders')
def admin_notifications_page():
    db = get_db()
    notifs = db.execute("SELECT an.*, u.username, u.email, u.full_name FROM admin_notifications an LEFT JOIN users u ON an.user_id=u.id ORDER BY an.id DESC LIMIT 100").fetchall()
    db.execute("UPDATE admin_notifications SET is_read=1")
    db.commit()
    return render_template_string(ADMIN_NOTIFICATIONS_HTML, notifications=notifs)

# ============================================================
# SELF-PING + MONITOR
# ============================================================
def _self_ping():
    if requests is None: return
    time.sleep(15)
    while True:
        en = False; iv = 5
        try:
            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
            c = conn.cursor()
            re_ = c.execute("SELECT value FROM settings WHERE key='self_ping_enabled'").fetchone()
            ri = c.execute("SELECT value FROM settings WHERE key='self_ping_interval'").fetchone()
            conn.close()
            if re_ and re_['value'] == '1': en = True
            if ri:
                try: iv = max(1, int(ri['value']))
                except Exception: iv = 5
        except Exception: pass
        if en:
            url = os.environ.get('RENDER_EXTERNAL_URL') or os.environ.get('SELF_PING_URL') or 'http://127.0.0.1:3000'
            try:
                r = requests.get(url.rstrip('/') + '/health', timeout=15)
                print(f"[Self-Ping] {url} → {r.status_code}", flush=True)
            except Exception as e:
                print(f"[Self-Ping] Failed: {e}", flush=True)
        time.sleep(iv * 60)
threading.Thread(target=_self_ping, daemon=True).start()

def _monitor():
    while True:
        try:
            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
            now_iso = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            for s in conn.execute("SELECT * FROM servers WHERE expires_at < ? AND status != 'expired'", (now_iso,)).fetchall():
                sid = s['id']
                p = RUNNING_PROCESSES.pop(sid, None)
                if p:
                    try:
                        if hasattr(os, 'killpg'): os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                        else: p.kill()
                    except Exception: pass
                conn.execute("UPDATE servers SET status='expired', pid=0 WHERE id=?", (sid,))
            conn.commit()
            conn.close()
            time.sleep(2)
            for sid, proc in list(RUNNING_PROCESSES.items()):
                if proc.poll() is not None:
                    code = proc.returncode
                    try:
                        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
                        srv = conn.execute("SELECT * FROM servers WHERE id=?", (sid,)).fetchone()
                        if srv:
                            conn.execute("UPDATE servers SET status=?, pid=0 WHERE id=?", ('error' if code != 0 else 'stopped', sid))
                            conn.commit()
                        conn.close()
                    except Exception: pass
                    finally:
                        RUNNING_PROCESSES.pop(sid, None)
                        SERVER_START_TIMES.pop(sid, None)
        except Exception: pass
threading.Thread(target=_monitor, daemon=True).start()

# ============================================================
# TEMPLATES — BASE + AUTH
# ============================================================
BASE_HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{% block title %}{{ vip_site_name }}{% endblock %}</title><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet"><link rel="stylesheet" href="/style.css">{% if site_logo_url %}<link rel="icon" href="{{ site_logo_url }}">{% endif %}</head><body>{% if is_impersonating %}<div class="impersonate-banner"><span>🛡️ Support Mode: <b>{{ current_user.username }}</b></span><a href="{{ url_for('stop_impersonating') }}" class="btn-xs">Return to Admin</a></div>{% endif %}<header class="topnav"><div class="wrap topnav-inner"><a href="{{ url_for('dashboard') if current_user else url_for('home') }}" class="brand"><div class="brand-icon">{% if site_logo_url %}<img src="{{ site_logo_url }}" alt="" onerror="this.style.display='none';this.parentNode.textContent='⚡';">{% else %}⚡{% endif %}</div><span>{{ site_name }}</span></a><nav class="desktop-nav">{% if current_user %}<a href="{{ url_for('dashboard') }}" class="dlink {% if request.endpoint=='dashboard' %}active{% endif %}">Dashboard</a><a href="{{ url_for('packages') }}" class="dlink {% if request.endpoint=='packages' %}active{% endif %}">Packages</a><a href="{{ url_for('account') }}" class="dlink {% if request.endpoint=='account' %}active{% endif %}">Account</a>{% if is_admin %}<a href="{{ url_for('admin_dashboard') }}" class="dlink admin-link">👑 Admin</a>{% endif %}{% else %}<a href="{{ url_for('home') }}" class="dlink">Home</a><a href="{{ url_for('signin') }}" class="dlink">Sign In</a>{% endif %}</nav><div class="header-actions">{% if current_user %}{% if trial_active %}<span class="plan-pill trial">🎁 Trial · {{ trial_hours_left }}h</span>{% elif has_access %}<span class="plan-pill">✅ {{ access_msg }}</span>{% else %}<span class="plan-pill none">No Plan</span>{% endif %}<div class="dd-wrap"><button class="dd-trigger bell-btn" onclick="toggleDropdown(event, this)"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg><span id="notif-badge" class="nbadge" style="display:none;">0</span></button><div class="dd-popover notif-pop"><div class="notif-head"><span>🔔 Notifications</span><button onclick="clearAllNotifs(event)" class="link-btn">Clear All</button></div><div id="notif-list" class="notif-body"><div class="empty-mini">Loading...</div></div></div></div><div class="dd-wrap"><button class="dd-trigger avatar-btn" onclick="toggleDropdown(event, this)">{% if current_user.avatar_url %}<img src="{{ current_user.avatar_url }}" alt="">{% else %}{{ (current_user.full_name or current_user.username)[0]|upper }}{% endif %}</button><div class="dd-popover"><div class="user-mini"><div class="avatar-mini">{% if current_user.avatar_url %}<img src="{{ current_user.avatar_url }}" alt="">{% else %}{{ (current_user.full_name or current_user.username)[0]|upper }}{% endif %}</div><div class="um-info"><b>{{ current_user.full_name }}</b><span>@{{ current_user.username }}</span></div></div><a href="{{ url_for('dashboard') }}" class="dd-item">📊 Dashboard</a><a href="{{ url_for('account') }}" class="dd-item">⚙️ Account</a><a href="{{ url_for('packages') }}" class="dd-item">📦 Packages</a>{% if is_admin %}<a href="{{ url_for('admin_dashboard') }}" class="dd-item admin-link">👑 Admin Panel</a>{% endif %}<div class="dd-divider"></div><a href="{{ url_for('signout') }}" class="dd-item danger">🚪 Sign Out</a></div></div>{% else %}<a href="{{ url_for('signin') }}" class="btn-primary btn-sm">Sign In</a>{% endif %}</div></div></header>{% with msgs = get_flashed_messages(with_categories=true) %}{% if msgs %}<div class="wrap" style="margin-top:8px;">{% for cat, msg in msgs %}<div class="flash flash-{{ cat }}"><span>{% if cat=='success' %}✓{% elif cat=='danger' %}✕{% elif cat=='warning' %}⚠{% else %}ℹ{% endif %}</span><span>{{ msg }}</span><button onclick="this.parentElement.remove()" class="flash-x">&times;</button></div>{% endfor %}</div>{% endif %}{% endwith %}<main>{% block content %}{% endblock %}</main>{% if current_user and request.endpoint not in ['server_manage','file_manager'] %}<nav class="bottomnav">{% if request.endpoint and 'admin' in request.endpoint %}<a href="{{ url_for('admin_dashboard') }}" class="bn-item"><span>👑</span>Admin</a><a href="{{ url_for('admin_orders') }}" class="bn-item"><span>💳</span>Orders</a><a href="{{ url_for('admin_users') }}" class="bn-item"><span>👥</span>Users</a><a href="{{ url_for('admin_settings') }}" class="bn-item"><span>⚙️</span>Settings</a>{% else %}<a href="{{ url_for('dashboard') }}" class="bn-item"><span>⚡</span>Home</a><a href="{{ url_for('packages') }}" class="bn-item"><span>📦</span>Plans</a><a href="{{ url_for('account') }}" class="bn-item"><span>👤</span>Account</a>{% endif %}</nav>{% endif %}<div id="toasts"></div><script src="/script.js"></script>{% block scripts %}{% endblock %}</body></html>"""

HOME_HTML = """{% extends "base" %}{% block title %}{{ vip_site_name }} — Premium Hosting{% endblock %}{% block content %}<div class="wrap"><section class="hero-card"><div class="hero-badge">🚀 PREMIUM PYTHON HOSTING</div><div class="hero-logo">{% if site_logo_url %}<img src="{{ site_logo_url }}" alt="">{% else %}⚡{% endif %}</div><h1 class="hero-title">{{ vip_site_name }}</h1><p class="hero-sub">Deploy in seconds. Scale infinitely.</p><p class="hero-desc">Fast, secure, and reliable hosting for Python, Node.js, PHP, Java, Go, and 50+ languages. Real-time logs, file manager, and auto-install — everything you need to ship faster.</p><div class="hero-actions">{% if current_user %}<a href="{{ url_for('dashboard') }}" class="btn-primary btn-lg">⚡ Enter Dashboard</a>{% else %}<a href="{{ url_for('signup') }}" class="btn-primary btn-lg">{% if trial_enabled %}Start Free Trial ({{ trial_hours }}h) →{% else %}Get Started Free →{% endif %}</a><a href="{{ url_for('signin') }}" class="btn-secondary btn-lg">Sign In</a>{% endif %}</div><div class="hero-stats"><div>🟢 99.9% Uptime</div><div>⚡ 50+ Languages</div><div>🛟 24x7 Support</div></div></section><section id="pricing" class="section"><div class="section-head"><h2 class="section-title">Plans for Every Stage</h2><p class="section-desc">Simple, transparent pricing. Cancel anytime.</p></div><div class="grid grid-3">{% for pkg in packages %}{% if pkg.is_trial and trial_enabled %}<div class="pkg-card pkg-trial"><div class="pkg-ribbon pkg-ribbon-trial">🎁 FREE TRIAL</div><h3>{{ pkg.name }}</h3><div class="pkg-price-block"><span class="pkg-price" style="color:#10B981;">₹0</span><span class="pkg-period">/ {{ pkg.trial_hours }} hours</span></div><ul class="pkg-list">{% for f in pkg.features.split(',') %}<li>{{ f.strip() }}</li>{% endfor %}</ul><a href="{{ url_for('signup') }}" class="btn-success btn-block">Start Free Trial →</a></div>{% elif not pkg.is_trial %}<div class="pkg-card {% if pkg.is_popular %}pkg-featured{% endif %}">{% if pkg.is_popular %}<div class="pkg-ribbon">⭐ POPULAR</div>{% endif %}<h3>{{ pkg.name }}</h3><div class="pkg-price-block"><span class="pkg-price">₹{{ pkg.price }}</span><span class="pkg-period">/ {{ pkg.days }} days</span></div><ul class="pkg-list">{% for f in pkg.features.split(',') %}<li>{{ f.strip() }}</li>{% endfor %}</ul>{% if current_user %}<a href="{{ url_for('buy_redirect', pkg_id=pkg.id) }}" class="btn-primary btn-block">Choose Plan →</a>{% else %}<a href="{{ url_for('signup', plan=pkg.id) }}" class="btn-primary btn-block">Choose Plan →</a>{% endif %}</div>{% endif %}{% endfor %}</div></section><section class="cta-card"><h2>Ready to deploy?</h2><p>Start with a free trial. No credit card required.</p>{% if not current_user %}<a href="{{ url_for('signup') }}" class="btn-primary btn-lg">Create Free Account →</a>{% else %}<a href="{{ url_for('create_server') }}" class="btn-primary btn-lg">+ Create Project</a>{% endif %}</section></div>{% endblock %}"""

SIGNIN_HTML = """{% extends "base" %}{% block title %}Sign In{% endblock %}{% block content %}<div class="auth-page-wrap"><div class="auth-split"><div class="auth-card"><div class="auth-head"><div class="auth-logo">{% if site_logo_url %}<img src="{{ site_logo_url }}" alt="">{% else %}⚡{% endif %}</div><h1>Welcome Back</h1><p>Sign in to continue</p></div><a href="{{ url_for('auth_google') }}" class="btn-google"><svg width="20" height="20" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.1-11.3-7.9l-6.5 5C9.6 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.5l6.2 5.2C36.8 39.2 44 34 44 24c0-1.3-.1-2.3-.4-3.5z"/></svg><span>Continue with Google</span></a><div class="auth-divider"><span>or sign in with email</span></div><form method="POST" action="{{ url_for('signin') }}"><div class="field"><label>Email or Username</label><input type="text" name="email" value="{{ email or '' }}" placeholder="you@gmail.com" required></div><div class="field"><label>Password</label><div class="pass-wrap"><input type="password" name="password" id="signin-pass" required><button type="button" class="pass-toggle" onclick="togglePass('signin-pass', this)">👁️</button></div></div><div class="auth-row"><label class="check"><input type="checkbox" name="remember" checked><span>Remember me</span></label><a href="javascript:void(0)" onclick="openForgotModal()" class="link-sm">Forgot password?</a></div><button type="submit" class="btn-primary btn-block btn-lg">Sign In</button></form><div class="auth-foot">Don't have an account? <a href="{{ url_for('signup') }}">Create one</a></div></div></div></div><div id="forgot-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:420px;"><button class="modal-x" onclick="closeForgotModal()">&times;</button><h2 style="font-size:1.25rem;font-weight:800;margin:0 0 6px;">Reset Password</h2><p style="font-size:0.85rem;color:var(--muted);margin:0 0 20px;">Verify your identity in 3 quick steps.</p><div class="step-badges"><div class="stepb" id="sb1"><span>1</span>Challenge</div><div class="stepb" id="sb2"><span>2</span>Email</div><div class="stepb" id="sb3"><span>3</span>Password</div></div><div id="fp-step1"><div class="captcha-box" id="fp-captcha">Loading...</div><div class="field"><label>Your Answer</label><input type="number" id="fp-captcha-answer"><div id="fp-cap-err" class="inline-err" style="display:none;"></div></div><button type="button" onclick="fpSubmitCaptcha()" class="btn-primary btn-block">Verify →</button></div><div id="fp-step2" style="display:none;"><div class="field"><label>Registered Gmail</label><input type="email" id="fp-email"><div id="fp-email-err" class="inline-err" style="display:none;"></div></div><button type="button" onclick="fpSubmitEmail()" class="btn-primary btn-block">Verify →</button></div><div id="fp-step3" style="display:none;"><div class="field"><label>New Password</label><input type="password" id="fp-new-pass"></div><div class="field"><label>Confirm Password</label><input type="password" id="fp-conf-pass"><div id="fp-pw-err" class="inline-err" style="display:none;"></div></div><button type="button" onclick="fpSubmitReset()" class="btn-success btn-block">Change Password ✓</button></div></div></div>{% endblock %}"""

SIGNUP_HTML = """{% extends "base" %}{% block title %}Sign Up{% endblock %}{% block content %}<div class="auth-page-wrap"><div class="auth-split"><div class="auth-card"><div class="auth-head"><div class="auth-logo">{% if site_logo_url %}<img src="{{ site_logo_url }}" alt="">{% else %}⚡{% endif %}</div><h1>Create Account</h1><p>Start building in minutes</p></div><a href="{{ url_for('auth_google') }}" class="btn-google"><svg width="20" height="20" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.1-11.3-7.9l-6.5 5C9.6 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.5l6.2 5.2C36.8 39.2 44 34 44 24c0-1.3-.1-2.3-.4-3.5z"/></svg><span>Sign up with Google</span></a><div class="auth-divider"><span>or sign up with email</span></div><form method="POST" action="{{ url_for('signup') }}"><div class="field"><label>Full Name</label><input type="text" name="full_name" value="{{ full_name or '' }}" required></div><div class="field"><label>Username</label><input type="text" name="username" value="{{ username or '' }}" required minlength="3"></div><div class="field"><label>Gmail Address</label><input type="email" name="email" value="{{ email or '' }}" required><small>Only @gmail.com addresses are accepted</small></div><div class="field"><label>Password</label><div class="pass-wrap"><input type="password" name="password" id="su-pass" required minlength="6"><button type="button" class="pass-toggle" onclick="togglePass('su-pass', this)">👁️</button></div></div><div class="field"><label>Confirm Password</label><div class="pass-wrap"><input type="password" name="confirm_password" id="su-cpass" required minlength="6"><button type="button" class="pass-toggle" onclick="togglePass('su-cpass', this)">👁️</button></div></div><button type="submit" class="btn-primary btn-block btn-lg">Create Account</button></form><div class="auth-foot">Already have an account? <a href="{{ url_for('signin') }}">Sign in</a></div></div></div></div>{% endblock %}"""



# ============================================================
# TEMPLATES — USER PAGES
# ============================================================
DASHBOARD_HTML = """{% extends "base" %}{% block title %}Dashboard{% endblock %}{% block content %}<div class="wrap"><div class="welcome-card"><div class="welcome-avatar">{% if current_user.avatar_url %}<img src="{{ current_user.avatar_url }}" alt="">{% else %}{{ (current_user.full_name or current_user.username)[0]|upper }}{% endif %}</div><div><div class="welcome-hi">Welcome back,</div><h1 class="welcome-name">{{ current_user.full_name }}</h1><div class="status-live"><span class="dot-live"></span>Active</div></div></div>{% if trial_active %}<div class="trial-countdown"><div class="trial-countdown-icon">🎁</div><div class="trial-countdown-info"><div class="trial-countdown-title">FREE TRIAL ACTIVE</div><div class="trial-countdown-timer" id="trial-timer" data-expires="{{ current_user.trial_expires_at }}">--:--:--</div></div><button onclick="openRenewModal()" class="btn-primary btn-sm">Upgrade Plan →</button></div>{% endif %}{% if not is_admin %}{% if has_access and current_user.plan_id %}<div class="plan-status-card plan-active"><div class="plan-header"><span class="plan-name-badge active">✅ PLAN ACTIVE</span>{% if current_pkg and current_pkg.is_popular %}<span class="badge badge-purple">POPULAR</span>{% endif %}</div><h2 class="plan-title">{{ current_pkg.name if current_pkg else 'Plan' }}</h2><div class="plan-meta-row"><span>Projects: <b>{{ servers|length }} / {% if current_user.project_limit == -1 %}∞{% else %}{{ current_user.project_limit }}{% endif %}</b></span><span>{{ access_msg }}</span></div><div class="plan-actions"><button onclick="openRenewModal()" class="btn-primary">🔄 Renew or Upgrade</button><a href="{{ url_for('packages') }}" class="btn-secondary">📦 View All Plans</a></div></div>{% elif not has_access %}<div class="plan-status-card plan-none"><div class="plan-header"><span class="plan-name-badge none">⚠️ NO PLAN</span></div><h2 class="plan-title">Choose a Plan</h2><p class="muted" style="margin-bottom:20px;">Purchase a plan to start creating projects.</p><div class="plan-actions"><a href="{{ url_for('packages') }}" class="btn-primary">🚀 View Plans →</a></div></div>{% endif %}{% else %}<div class="plan-status-card plan-active" style="background:linear-gradient(135deg,#1E1B4B 0%,#312E81 100%);border-color:#4C1D95;color:#fff;"><div class="plan-header"><span class="plan-name-badge" style="background:linear-gradient(135deg,#F59E0B,#D97706);color:#fff;">👑 OWNER</span></div><h2 class="plan-title" style="color:#fff;">Unlimited Access</h2><div class="plan-meta-row" style="color:#C7D2FE;"><span>Projects: <b style="color:#fff;">{{ servers|length }} / ∞</b></span></div><div class="plan-actions" style="border-top-color:rgba(255,255,255,0.1);"><a href="{{ url_for('admin_dashboard') }}" class="btn-glass">👑 Admin Panel</a></div></div>{% endif %}{% if announcements %}<div class="ann-stack">{% for a in announcements %}<div class="ann-card ann-{{ a.type }} {% if a.pinned %}ann-pinned{% endif %}"><div class="ann-head"><div class="ann-badges">{% if a.pinned %}<span class="badge badge-warn">📌 PINNED</span>{% endif %}<strong>{{ a.title }}</strong></div><span class="ann-date">{{ a.created_at|format_date }}</span></div><p class="ann-body">{{ a.content }}</p></div>{% endfor %}</div>{% endif %}<div class="stats-grid"><div class="stat-card"><div class="stat-label">Total Projects</div><div class="stat-value">{{ servers|length }}</div></div><div class="stat-card"><div class="stat-label">Total Files</div><div class="stat-value">{{ total_files }}</div></div><div class="stat-card"><div class="stat-label">Storage</div><div class="stat-value" style="font-size:1.25rem;">{{ storage_formatted }}</div></div><div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" style="color:#10B981;font-size:1.25rem;">Ready</div></div></div><div class="section-head-row"><div><h2 class="section-title" style="margin:0;font-size:1.5rem;">My Projects ({{ servers|length }})</h2><p class="section-desc">{{ limit_msg }}</p></div>{% if can_create %}<a href="{{ url_for('create_server') }}" class="btn-primary">+ New Project</a>{% else %}<a href="{{ url_for('packages') }}" class="btn-primary">⬆️ Upgrade to Create</a>{% endif %}</div>{% if servers %}<div class="grid grid-2">{% for s in servers %}<div class="server-card server-{{ s.status }}"><div class="server-top"><div class="server-id"><div class="server-icon">🐍</div><div><h3>{{ s.name }}</h3><span class="server-py">{{ s.runtime }}</span></div></div>{% if s.status == 'running' %}<span class="status status-running"><span class="dot"></span>Running</span>{% elif s.status == 'expired' %}<span class="status status-expired"><span class="dot"></span>Expired</span>{% elif s.status == 'package_required' %}<span class="status status-warn"><span class="dot"></span>Setup</span>{% else %}<span class="status status-stopped"><span class="dot"></span>Stopped</span>{% endif %}</div><div class="server-info"><div><span>Entry:</span><b>{{ s.entry_file or 'Not set' }}</b></div><div><span>Created:</span><span>{{ s.created_at|format_date }}</span></div><div><span>Expires:</span><b class="{% if s.status=='expired' %}danger-text{% endif %}">{{ s.expires_at|format_date }}</b></div></div><a href="{{ url_for('server_manage', server_id=s.id) }}" class="btn-primary btn-block">⚙️ Manage</a></div>{% endfor %}</div>{% else %}<div class="empty-card"><div style="font-size:3rem;">🚀</div><h3>No Projects Yet</h3><p>Create your first project to get started.</p><a href="{{ url_for('create_server') }}" class="btn-primary">+ Create Project</a></div>{% endif %}<div id="renew-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:520px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;"><div><h2 style="font-size:1.35rem;font-weight:800;margin:0;">Renew or Upgrade</h2><p style="font-size:0.85rem;color:var(--muted);margin-top:4px;">Choose a plan to continue</p></div><button onclick="closeRenewModal()" class="modal-x" style="position:static;">✕</button></div><div style="display:flex;flex-direction:column;gap:10px;margin-bottom:20px;">{% for pkg in packages %}{% if not pkg.is_trial %}<label class="renew-plan-option {% if current_user.plan_id == pkg.id %}renew-current{% endif %}"><input type="radio" name="renew_pkg" value="{{ pkg.id }}" {% if current_user.plan_id == pkg.id %}checked{% endif %} onchange="updateRenewButton()"><div style="flex:1;"><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;"><b style="font-size:1rem;">{{ pkg.name }}</b>{% if current_user.plan_id == pkg.id %}<span class="badge badge-warn">⭐ Current</span>{% elif current_user.plan_id and pkg.price > 0 %}<span class="badge badge-success">Upgrade</span>{% endif %}{% if pkg.is_popular %}<span class="badge badge-purple">POPULAR</span>{% endif %}</div><div style="font-size:0.8rem;color:var(--muted);margin-top:2px;">{{ pkg.project_limit if pkg.project_limit > 0 else '∞' }} projects • {{ pkg.days }} days</div></div><div class="renew-price" style="font-weight:800;color:var(--primary);font-size:1.15rem;">₹{{ pkg.price }}</div></label>{% endif %}{% endfor %}</div><button id="renew-continue-btn" onclick="continueRenew()" class="btn-primary btn-block btn-lg">Continue →</button></div></div></div>{% endblock %}"""

PACKAGES_HTML = """{% extends "base" %}{% block title %}Packages{% endblock %}{% block content %}<div class="wrap"><div class="section-head"><h1 class="section-title">Choose Your Plan</h1><p class="section-desc">Simple, transparent pricing. Cancel anytime.</p></div><div class="grid grid-3">{% for pkg in packages %}{% if pkg.is_trial and trial_enabled %}<div class="pkg-card pkg-trial"><div class="pkg-ribbon pkg-ribbon-trial">🎁 FREE TRIAL</div><h3>{{ pkg.name }}</h3><div class="pkg-price-block"><span class="pkg-price" style="color:#10B981;">₹0</span><span class="pkg-period">/ {{ pkg.trial_hours }} hours</span></div><ul class="pkg-list">{% for f in pkg.features.split(',') %}<li>{{ f.strip() }}</li>{% endfor %}</ul>{% if user.trial_used %}<button class="btn-secondary btn-block" disabled>Trial Already Used</button>{% else %}<a href="{{ url_for('signup') }}" class="btn-success btn-block">Start Free Trial →</a>{% endif %}</div>{% elif not pkg.is_trial %}<div class="pkg-card {% if pkg.is_popular %}pkg-featured{% endif %}">{% if pkg.is_popular %}<div class="pkg-ribbon">⭐ POPULAR</div>{% endif %}<h3>{{ pkg.name }}</h3><div class="pkg-price-block"><span class="pkg-price">₹{{ pkg.price }}</span><span class="pkg-period">/ {{ pkg.days }} days</span></div><ul class="pkg-list">{% for f in pkg.features.split(',') %}<li>{{ f.strip() }}</li>{% endfor %}</ul>{% if user.plan_id == pkg.id %}<button class="btn-secondary btn-block" disabled>✅ Current Plan</button>{% else %}<a href="{{ url_for('buy_redirect', pkg_id=pkg.id) }}" class="btn-primary btn-block">{% if user.plan_id %}Choose Plan →{% else %}Get Started →{% endif %}</a>{% endif %}</div>{% endif %}{% endfor %}</div></div>{% endblock %}"""

CHECKOUT_HTML = """{% extends "base" %}{% block title %}Checkout{% endblock %}{% block content %}<div class="wrap"><div class="checkout-card"><div class="checkout-header"><h2 class="checkout-plan-name">{{ pkg.name }}</h2><div class="checkout-amount">₹{{ pkg.price }}</div><p class="muted">{{ pkg.days }} days • {{ pkg.project_limit if pkg.project_limit > 0 else '∞' }} projects</p></div><div class="checkout-details"><div class="checkout-detail-row"><span>Duration</span><b>{{ pkg.days }} days</b></div><div class="checkout-detail-row"><span>Projects</span><b>{{ pkg.project_limit if pkg.project_limit > 0 else '∞' }}</b></div><div class="checkout-detail-row"><span>Total Amount</span><b>₹{{ pkg.price }}</b></div></div><form method="POST" action="{{ url_for('checkout', pkg_id=pkg.id) }}"><h3 style="font-size:1.1rem;margin-bottom:16px;">Continue to Payment</h3><p style="font-size:0.875rem;color:var(--muted);margin-bottom:20px;">You will be redirected to a secure payment page.</p><button type="submit" class="btn-primary btn-block btn-lg">Pay ₹{{ pkg.price }} →</button></form><div style="text-align:center;margin-top:20px;"><a href="{{ url_for('packages') }}" class="muted">← Back to Plans</a></div></div></div>{% endblock %}"""

PAYMENT_HTML = """{% extends "base" %}{% block title %}Payment — ₹{{ order.amount }}{% endblock %}{% block content %}<div class="wrap"><div class="checkout-card"><div class="checkout-header"><h2 class="checkout-plan-name">Pay ₹{{ order.amount }}</h2><p class="muted">{{ pkg.name }} · {{ pkg.days }} days</p></div><div class="qr-container"><img src="{{ qr_url }}" alt="QR Code" class="qr-code-img"><div class="qr-upi-id" id="upi-id-display" data-upi="{{ selected_upi }}" onclick="copyUpiId()">{{ selected_upi }} <span style="opacity:0.6;">📋</span></div><div class="qr-amount-display" id="qr-amount" data-amount="{{ order.amount }}">₹{{ order.amount }}</div><p style="font-size:0.9rem;color:var(--muted);">Scan with any UPI app and pay ₹{{ order.amount }}</p><div class="qr-apps-row">{% if all_upis.get('phonepe') %}<button onclick="openUpiApp('phonepe')" class="qr-app-badge">📱 PhonePe</button>{% endif %}{% if all_upis.get('gpay') %}<button onclick="openUpiApp('gpay')" class="qr-app-badge">🅖 Google Pay</button>{% endif %}{% if all_upis.get('paytm') %}<button onclick="openUpiApp('paytm')" class="qr-app-badge">💳 Paytm</button>{% endif %}{% if all_upis.get('fampay') %}<button onclick="openUpiApp('fampay')" class="qr-app-badge">💰 FamPay</button>{% endif %}{% if all_upis.get('bhim') %}<button onclick="openUpiApp('bhim')" class="qr-app-badge">🇮🇳 BHIM</button>{% endif %}{% if all_upis.get('amazonpay') %}<button onclick="openUpiApp('amazonpay')" class="qr-app-badge">📦 Amazon Pay</button>{% endif %}</div></div>{% if auto_verify %}<div class="payment-status" id="payment-poll-order" data-order-id="{{ order.id }}"><div class="payment-status-text" id="payment-status-text"><span class="payment-spinner"></span> Verifying payment...</div><div class="payment-status-sub" id="payment-status-sub">Payment auto-verifies in a few seconds</div></div>{% else %}<div id="txn-form"><h3 style="font-size:1.1rem;margin-bottom:16px;">Enter Transaction ID</h3><p style="font-size:0.875rem;color:var(--muted);margin-bottom:16px;">After payment, enter the UTR / Transaction ID below.</p><div class="txn-input-group"><label>UTR / Transaction ID</label><input type="text" id="txn-id-input" placeholder="e.g. 123456789012" autocomplete="off"></div><button type="button" class="btn-primary btn-block btn-lg" id="txn-submit-btn" onclick="submitTransactionId({{ order.id }})">Submit Transaction ID</button></div><div id="txn-done" style="display:none;text-align:center;padding:32px 16px;"><div style="font-size:3.5rem;margin-bottom:12px;">✅</div><h3 style="font-size:1.25rem;font-weight:800;margin-bottom:8px;">Payment Submitted</h3><p class="muted" style="max-width:340px;margin:0 auto;">Your payment is being processed. Redirecting to dashboard...</p></div><div class="payment-status" id="payment-poll-order" data-order-id="{{ order.id }}" style="display:none;"><div class="payment-status-text" id="payment-status-text"></div><div class="payment-status-sub" id="payment-status-sub"></div></div>{% endif %}<div style="text-align:center;margin-top:20px;"><a href="{{ url_for('dashboard') }}" class="muted">← Back to Dashboard</a></div></div></div>{% endblock %}"""

CREATE_SERVER_HTML = """{% extends "base" %}{% block title %}Create Project{% endblock %}{% block content %}<div class="wrap" style="max-width:560px;"><div class="back-row"><a href="{{ url_for('dashboard') }}" class="back-btn">← Back</a></div><div class="card" style="padding:36px 32px;"><h1 style="font-size:1.6rem;font-weight:900;margin:0 0 6px;letter-spacing:-0.03em;">Create New Project</h1><p class="muted" style="margin-bottom:28px;">{{ limit_msg }}</p><form method="POST" action="{{ url_for('create_server') }}"><div class="field"><label>Project Name</label><input type="text" name="name" placeholder="e.g. My Telegram Bot" required autofocus><small>Give your project a clear, recognizable name.</small></div><div class="feature-list-box"><b>What's included</b><div class="grid grid-2" style="gap:8px;margin-top:10px;"><div>✓ Empty project folder</div><div>✓ Live terminal logs</div><div>✓ ZIP upload & extract</div><div>✓ Auto dependency install</div></div></div><button type="submit" class="btn-primary btn-block btn-lg">Create Project →</button></form></div></div>{% endblock %}"""

SERVER_MANAGE_HTML = """{% extends "base" %}{% block title %}{{ server.name }}{% endblock %}{% block content %}<div class="wrap"><div class="back-row"><a href="{{ url_for('dashboard') }}" class="back-btn">← Back to Dashboard</a></div><div class="card server-header-card"><div><div class="server-tag">PROJECT · #{{ server.id }}</div><h1>{{ server.name }}</h1></div><div class="server-header-right"><span id="status-badge" class="status status-{{ server.status }}">{% if server.status=='running' %}🟢 RUNNING{% elif server.status=='package_required' %}🟡 SETUP{% elif server.status=='expired' %}🔴 EXPIRED{% else %}🔴 STOPPED{% endif %}</span></div></div><div class="card" id="url-card" style="display:{% if server.status == 'running' %}block{% else %}none{% endif %};background:linear-gradient(135deg,#EEF2FF 0%,#E0E7FF 100%);border:1.5px solid #C7D2FE;"><div style="font-size:0.75rem;font-weight:800;color:#4338CA;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:10px;">🌐 Your Project URL</div><div style="display:flex;gap:8px;flex-wrap:wrap;"><input type="text" readonly value="{{ server_url }}" id="server-url-input" style="flex:1;min-width:240px;padding:14px 16px;border:1.5px solid #C7D2FE;border-radius:12px;font-family:var(--font-mono);font-size:0.9rem;background:#fff;color:#4338CA;font-weight:700;outline:none;"><button onclick="copyServerUrl()" class="btn-primary btn-sm">📋 Copy</button><a id="open-url-btn" href="{{ server_url }}" target="_blank" class="btn-secondary btn-sm">🔗 Open</a></div></div><div class="subnav"><a href="{{ url_for('server_manage', server_id=server.id) }}" class="subnav-item active">📊 Logs</a><a href="{{ url_for('file_manager', server_id=server.id) }}" class="subnav-item">📁 Files</a></div><div class="card"><div class="ops-head"><h2>Server Operations</h2><span id="pid-badge" class="pid-badge {% if server.status=='running' and server.pid %}pid-on{% endif %}">PID: {% if server.status=='running' and server.pid %}{{ server.pid }}{% else %}Offline{% endif %}</span></div><div class="ops-grid"><button id="btn-start" onclick="serverAction({{ server.id }}, 'start')" class="btn-success" {% if server.status == 'running' or server.status == 'expired' %}disabled{% endif %}>🟢 START</button><button id="btn-restart" onclick="serverAction({{ server.id }}, 'restart')" class="btn-warning" {% if server.status == 'expired' %}disabled{% endif %}>🟠 RESTART</button><button id="btn-stop" onclick="serverAction({{ server.id }}, 'stop')" class="btn-danger" {% if server.status in ['stopped','package_required','expired'] %}disabled{% endif %}>🔴 STOP</button></div></div><div class="card"><div class="ops-head"><div style="display:flex;align-items:center;gap:10px;"><h2 style="margin:0;">Server Console</h2>{% if server.status == 'running' %}<span class="dot-pulse"></span>{% endif %}</div><button onclick="clearLogs({{ server.id }})" class="btn-secondary btn-sm">Clear Logs</button></div><div id="terminal" class="terminal" data-server-id="{{ server.id }}" data-start-time="{{ start_time or 0 }}"><div class="log-line log-info">[INFO] Waiting for server output...</div></div><div style="display:flex;gap:10px;margin-top:14px;"><input type="text" id="terminal-input" placeholder="Type command..." style="flex:1;padding:14px 16px;border:1.5px solid var(--border);border-radius:var(--radius);font-family:var(--font-mono);font-size:0.9rem;outline:none;" onkeydown="if(event.key==='Enter'){sendTerminalCommand();}"><button onclick="sendTerminalCommand()" class="btn-primary">Run</button></div><div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;"><button onclick="quickCommand('pip install ')" class="btn-ghost btn-sm">📦 pip install</button><button onclick="quickCommand('pip list')" class="btn-ghost btn-sm">📋 pip list</button><button onclick="quickCommand('ls -la')" class="btn-ghost btn-sm">📁 ls</button><button onclick="quickCommand('python --version')" class="btn-ghost btn-sm">🐍 Python</button></div></div><div class="meta-grid"><div class="stat-card"><div class="stat-label">Entry File</div><div class="stat-value" style="font-family:var(--font-mono);font-size:0.95rem;">{{ server.entry_file or 'Not set' }}</div></div><div class="stat-card"><div style="display:flex;justify-content:space-between;align-items:center;"><div class="stat-label">Uptime</div><div id="uptime-tick" class="mono-tick">00:00:00</div></div><div style="display:flex;align-items:center;gap:8px;margin-top:8px;"><span id="status-dot" class="status-dot {% if server.status=='running' %}on{% endif %}"></span><span id="status-text" class="status-text {% if server.status=='running' %}on{% endif %}">{% if server.status=='running' %}Running{% else %}Offline{% endif %}</span></div></div><div class="stat-card"><div class="stat-label">Remaining</div><div class="stat-value {% if remaining_days < 2 %}danger-text{% endif %}">{{ remaining_days }} days</div></div><div class="stat-card"><div class="stat-label">Expires</div><div class="stat-value" style="font-size:0.95rem;">{{ server.expires_at|format_date }}</div></div></div><div class="card" style="border-color:#FECACA;background:#FEF2F2;"><div class="ops-head"><h2 style="color:#991B1B;">Danger Zone</h2></div><p class="muted" style="margin-bottom:16px;">Delete this project and all its files permanently. This cannot be undone.</p><button onclick="deleteServer({{ server.id }}, '{{ server.name|e }}')" class="btn-danger-outline">🗑️ Delete Project</button></div></div>{% endblock %}{% block scripts %}<script>startLogStream({{ server.id }}, {{ start_time or 0 }});</script>{% endblock %}"""

FILE_MANAGER_HTML = """{% extends "base" %}{% block title %}Files — {{ server.name }}{% endblock %}{% block content %}<div class="wrap"><div class="back-row"><a href="{{ url_for('server_manage', server_id=server.id) }}" class="back-btn">← Back to Server</a></div><div class="card server-header-card"><div><div class="server-tag">FILES · #{{ server.id }}</div><h1>{{ server.name }}</h1></div><span class="status status-{{ server.status }}">{% if server.status=='running' %}🟢 RUNNING{% else %}🔴 STOPPED{% endif %}</span></div><div class="card"><div class="fm-toolbar"><div class="breadcrumbs"><a href="{{ url_for('file_manager', server_id=server.id) }}">🏠 root</a>{% for bc in breadcrumbs %}<span>›</span><a href="{{ url_for('file_manager', server_id=server.id, path=bc.path) }}">{{ bc.name }}</a>{% endfor %}</div><div class="fm-actions"><label class="btn-primary btn-sm" style="cursor:pointer;">📦 Upload ZIP<input type="file" accept=".zip" style="display:none;" onchange="uploadFile({{ server.id }}, this, true)"></label><label class="btn-secondary btn-sm" style="cursor:pointer;">📤 Upload Files<input type="file" multiple style="display:none;" onchange="uploadFile({{ server.id }}, this, false)"></label><button onclick="promptFolder({{ server.id }})" class="btn-secondary btn-sm">📁 New Folder</button><button onclick="promptFile({{ server.id }})" class="btn-secondary btn-sm">+ New File</button></div></div></div><div class="card" style="padding:0;overflow:hidden;"><div class="fm-head"><div>Name ({{ total_items }})</div><div>Actions</div></div>{% if items %}{% for item in items %}<div class="fm-row"><div class="fm-info"><div class="fm-icon">{% if item.is_dir %}📁{% elif item.is_zip %}📦{% elif item.is_py %}🐍{% elif item.name.endswith('.json') %}⚙️{% elif item.name.endswith(('.png','.jpg','.jpeg','.svg','.gif','.webp')) %}🖼️{% elif item.name.endswith('.log') %}📋{% else %}📄{% endif %}</div><div class="fm-meta">{% if item.is_dir %}<a href="{{ url_for('file_manager', server_id=server.id, path=(current_path + '/' + item.name) if current_path else item.name) }}" class="fm-name">{{ item.name }}</a>{% else %}<span class="fm-name" onclick="openEditor({{ server.id }}, '{{ (current_path + '/' + item.name) if current_path else item.name }}')">{{ item.name }}</span>{% endif %}{% if item.is_entry %}<span class="entry-tag">ENTRY</span>{% endif %}<div class="fm-sub">{{ item.modified }} · {{ item.size }}</div></div></div><div class="dd-wrap"><button class="dd-trigger" style="padding:8px 12px;border-radius:8px;color:var(--muted);font-size:1.25rem;">⋮</button><div class="dd-popover">{% set fp = (current_path + '/' + item.name) if current_path else item.name %}{% if item.is_zip %}<button onclick="unzipItem({{ server.id }}, '{{ fp }}')" class="dd-item primary-text">📦 Extract</button>{% endif %}{% if not item.is_dir %}<button onclick="openEditor({{ server.id }}, '{{ fp }}')" class="dd-item">✏️ Edit</button><a href="{{ url_for('download_file', server_id=server.id, path=fp) }}" class="dd-item">⬇️ Download</a>{% endif %}<button onclick="renameItem({{ server.id }}, '{{ fp }}')" class="dd-item">🏷️ Rename</button><button onclick="deleteItem({{ server.id }}, '{{ fp }}')" class="dd-item danger">🗑️ Delete</button></div></div></div>{% endfor %}{% else %}<div class="empty-mini" style="padding:60px 20px;"><div style="font-size:3rem;margin-bottom:12px;">📁</div><div style="font-weight:700;color:var(--text);margin-bottom:4px;">Empty Folder</div><div>Upload files or ZIP to get started.</div></div>{% endif %}{% if total_pages > 1 %}<div class="pagination">{% if current_page > 1 %}<a href="?path={{ current_path }}&page={{ current_page - 1 }}" class="page-btn">← Prev</a>{% endif %}<span class="page-btn active">{{ current_page }} / {{ total_pages }}</span>{% if current_page < total_pages %}<a href="?path={{ current_path }}&page={{ current_page + 1 }}" class="page-btn">Next →</a>{% endif %}</div>{% endif %}</div><div id="up-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:420px;text-align:center;"><div class="up-icon" id="up-icon">📤</div><h3 id="up-title" style="font-size:1.15rem;font-weight:800;margin-bottom:6px;">Uploading...</h3><p id="up-sub" class="muted" style="margin-bottom:20px;">Please wait</p><div class="progress-track"><div id="up-bar" class="progress-bar" style="width:0%;"></div></div><div style="display:flex;justify-content:space-between;font-size:0.85rem;font-weight:700;margin-top:10px;"><span id="up-pct" class="primary-text">0%</span><span id="up-size">0 KB / 0 KB</span></div></div></div><div id="editor-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:820px;height:85vh;display:flex;flex-direction:column;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;"><h3 id="ed-file" style="margin:0;font-size:1.1rem;font-weight:800;">File Editor</h3><button onclick="document.getElementById('editor-modal').style.display='none'" class="modal-x" style="position:static;">&times;</button></div><input type="hidden" id="ed-path"><textarea id="ed-content" class="code-editor" spellcheck="false"></textarea><div style="display:flex;justify-content:flex-end;gap:10px;margin-top:16px;"><button onclick="document.getElementById('editor-modal').style.display='none'" class="btn-secondary">Cancel</button><button id="ed-save" onclick="saveEditor({{ server.id }})" class="btn-primary">💾 Save Changes</button></div></div></div></div>{% endblock %}"""

ACCOUNT_HTML = """{% extends "base" %}{% block title %}Account{% endblock %}{% block content %}<div class="wrap" style="max-width:680px;"><div class="card"><div class="acc-head"><div class="acc-avatar-wrap"><label for="quick_avatar" style="cursor:pointer;"><div class="acc-avatar">{% if user.avatar_url %}<img src="{{ user.avatar_url }}" alt="">{% else %}{{ (user.full_name or user.username)[0]|upper }}{% endif %}</div><div class="acc-cam">📷</div></label><form id="quick_avatar_form" action="{{ url_for('account') }}" method="POST" enctype="multipart/form-data" style="display:none;"><input type="hidden" name="action" value="upload_avatar"><input type="file" id="quick_avatar" name="avatar" accept="image/*" onchange="document.getElementById('quick_avatar_form').submit();"></form></div><div class="acc-info"><h1>{{ user.full_name }}</h1><span class="status-pill">● {{ user.status|capitalize }}</span></div></div><div class="acc-grid"><div><span>Member Since</span><b>{{ user.created_at|format_date }}</b></div><div><span>Role</span><b class="primary-text">{{ user.role|capitalize }}</b></div><div><span>Project Limit</span><b>{{ user.project_limit if user.project_limit >= 0 else '∞' }}</b></div></div></div><div class="card"><h2>Profile Picture</h2><p class="muted" style="margin-bottom:20px;">Upload a photo from your device. PNG, JPG, WEBP, GIF or SVG.</p><div class="upload-box"><div class="up-preview">{% if user.avatar_url %}<img id="av-preview-img" src="{{ user.avatar_url }}" alt="">{% else %}<span id="av-preview-letter">{{ (user.full_name or user.username)[0]|upper }}</span><img id="av-preview-img" src="" style="display:none;" alt="">{% endif %}</div><div class="up-actions"><form action="{{ url_for('account') }}" method="POST" enctype="multipart/form-data" style="display:flex;gap:10px;flex-wrap:wrap;"><input type="hidden" name="action" value="upload_avatar"><label class="btn-secondary">Choose Image<input type="file" name="avatar" accept="image/*" style="display:none;" onchange="previewAvatar(this)"></label><button type="submit" class="btn-primary">Upload</button></form><div class="file-info">Max 5 MB</div></div></div>{% if user.avatar_url %}<form action="{{ url_for('account') }}" method="POST" onsubmit="return confirm('Remove profile picture?');" style="margin-top:16px;"><input type="hidden" name="action" value="remove_avatar"><button type="submit" class="btn-danger-outline">🗑️ Remove Picture</button></form>{% endif %}</div><div class="card"><h2>Edit Profile</h2><form action="{{ url_for('account') }}" method="POST"><input type="hidden" name="action" value="update_profile"><div class="field"><label>Full Name</label><input type="text" name="full_name" value="{{ user.full_name }}" required></div><div class="field"><label>Username</label><input type="text" value="{{ user.username }}" readonly class="readonly"></div><div class="field"><label>Gmail Address</label><input type="email" value="{{ user.email }}" readonly class="readonly"></div><div class="field"><label>Bio</label><input type="text" name="bio" value="{{ user.bio or '' }}" placeholder="Tell us about you..."></div><button type="submit" class="btn-primary">Save Changes</button></form></div><div class="card"><h2>Change Password</h2><form action="{{ url_for('account') }}" method="POST"><input type="hidden" name="action" value="change_password"><div class="field"><label>Current Password</label><input type="password" name="current_password" required></div><div class="field"><label>New Password</label><input type="password" name="new_password" required minlength="6"></div><div class="field"><label>Confirm New Password</label><input type="password" name="confirm_new_password" required minlength="6"></div><button type="submit" class="btn-primary">Update Password</button></form></div></div>{% endblock %}"""

ADMIN_DASHBOARD_HTML = """{% extends "base" %}{% block title %}Admin Console{% endblock %}{% block content %}<div class="wrap"><div class="admin-hero"><div style="display:flex;align-items:center;gap:16px;"><div class="admin-hero-icon">👑</div><div><span class="admin-hero-label">ROOT ADMINISTRATION</span><h1>{{ site_name }} Control Center</h1></div></div><div style="display:flex;gap:8px;flex-wrap:wrap;"><a href="{{ url_for('admin_orders') }}" class="btn-glass">💳 Orders</a><a href="{{ url_for('admin_users') }}" class="btn-glass">👥 Users</a><a href="{{ url_for('admin_payments') }}" class="btn-glass">💰 Payments</a><a href="{{ url_for('admin_settings') }}" class="btn-glass-solid">⚙️ Settings</a></div></div><div class="stats-grid"><div class="stat-card"><div class="stat-label">Today's Revenue</div><div class="stat-value gold-text">₹{{ today_revenue }}</div></div><div class="stat-card"><div class="stat-label">Total Revenue</div><div class="stat-value gold-text">₹{{ total_revenue }}</div></div><div class="stat-card"><div class="stat-label">Total Users</div><div class="stat-value">{{ total_users }}</div><div class="stat-hint hint-green">{{ active_users }} active</div></div><div class="stat-card"><div class="stat-label">Total Projects</div><div class="stat-value">{{ total_servers }}</div><div class="stat-hint hint-blue">{{ running_servers }} running</div></div><div class="stat-card"><div class="stat-label">Trials</div><div class="stat-value">{{ trial_users }}</div></div><div class="stat-card"><div class="stat-label">Pending Orders</div><div class="stat-value">{{ pending_orders }}</div></div><div class="stat-card"><div class="stat-label">Conversion</div><div class="stat-value">{{ conversion_rate }}%</div></div><div class="stat-card"><div class="stat-label">Storage</div><div class="stat-value" style="font-size:1.15rem;">{{ total_storage_formatted }}</div></div></div><div class="grid grid-3" style="margin-bottom:24px;">{% if is_super_admin or has_admin_permission(current_user, 'manage_orders') %}<a href="{{ url_for('admin_orders') }}" class="quick-link"><span style="font-size:1.75rem;">💳</span><div><b>Orders & Payments</b><span>View and approve</span></div></a>{% endif %}{% if is_super_admin or has_admin_permission(current_user, 'manage_users') %}<a href="{{ url_for('admin_users') }}" class="quick-link"><span style="font-size:1.75rem;">👥</span><div><b>User Management</b><span>Roles & permissions</span></div></a>{% endif %}{% if is_super_admin or has_admin_permission(current_user, 'manage_orders') %}<a href="{{ url_for('admin_plans') }}" class="quick-link"><span style="font-size:1.75rem;">📋</span><div><b>Plan History</b><span>Activations</span></div></a>{% endif %}{% if is_super_admin or has_admin_permission(current_user, 'manage_orders') %}<a href="{{ url_for('admin_trials') }}" class="quick-link"><span style="font-size:1.75rem;">🎁</span><div><b>Trial Tracking</b><span>IP-based tracking</span></div></a>{% endif %}{% if is_super_admin or has_admin_permission(current_user, 'manage_orders') %}<a href="{{ url_for('admin_notifications_page') }}" class="quick-link" style="border-color:#C7D2FE;background:#EEF2FF;"><span style="font-size:1.75rem;">🔔</span><div><b>Notifications</b><span>Recent events</span></div></a>{% endif %}{% if is_super_admin or has_admin_permission(current_user, 'manage_settings') %}<a href="{{ url_for('admin_settings') }}" class="quick-link"><span style="font-size:1.75rem;">⚙️</span><div><b>System Settings</b><span>Branding & plans</span></div></a>{% endif %}</div>{% if recent_notifications %}<div class="card"><h3 style="margin-bottom:16px;">🔔 Recent Activity</h3><div style="display:flex;flex-direction:column;gap:8px;">{% for n in recent_notifications %}<div class="mini-row"><div><div style="font-weight:700;">{{ n.title }}</div><div class="muted-sm">{{ n.message }}</div></div></div>{% endfor %}</div></div>{% endif %}<div class="grid grid-2"><div class="card"><h3 style="margin-bottom:16px;">Recent Users</h3><div style="display:flex;flex-direction:column;gap:8px;">{% for u in recent_users %}<div class="mini-row"><div><div style="font-weight:700;">{{ u.full_name }} <span class="muted">@{{ u.username }}</span></div><div class="muted-sm">{{ u.email }}</div></div><span class="status-pill-sm {% if u.status=='active' %}on{% endif %}">{{ u.status|upper }}</span></div>{% endfor %}</div></div><div class="card"><h3 style="margin-bottom:16px;">Recent Activity</h3><div style="display:flex;flex-direction:column;gap:8px;max-height:340px;overflow-y:auto;">{% for log in recent_logs %}<div class="mini-row" style="flex-direction:column;align-items:stretch;"><div style="display:flex;justify-content:space-between;font-size:0.725rem;color:#64748B;"><b class="primary-text">{{ log.action }}</b><span>{{ log.created_at|format_datetime }}</span></div><div style="font-size:0.825rem;">{{ log.details }}</div></div>{% endfor %}</div></div></div></div>{% endblock %}"""

ADMIN_ORDERS_HTML = """{% extends "base" %}{% block title %}Orders — Admin{% endblock %}{% block content %}<div class="wrap"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>💳 Orders & Payments</h1></div><div class="stat-chip">{{ orders|length }} total</div></div><div class="card"><div style="display:flex;gap:8px;flex-wrap:wrap;"><a href="?status=all" class="btn-secondary btn-sm {% if current_status=='all' %}btn-primary{% endif %}">All</a><a href="?status=pending" class="btn-secondary btn-sm {% if current_status=='pending' %}btn-primary{% endif %}">Pending</a><a href="?status=paid" class="btn-secondary btn-sm {% if current_status=='paid' %}btn-primary{% endif %}">Paid</a><a href="?status=failed" class="btn-secondary btn-sm {% if current_status=='failed' %}btn-primary{% endif %}">Failed</a></div></div><div style="display:flex;flex-direction:column;gap:14px;">{% for o in orders %}<div class="order-card order-{{ o.status }}"><div class="order-head"><div style="display:flex;align-items:center;gap:10px;"><span class="order-id">#{{ o.id }}</span><span class="order-status {{ o.status }}">{{ o.status|upper }}</span></div><div class="order-amount">₹{{ o.amount }}</div></div><div class="order-row"><span>User</span><b>{{ o.full_name }} (@{{ o.username }})</b></div><div class="order-row"><span>Email</span><span>{{ o.email }}</span></div><div class="order-row"><span>Plan</span><b>{{ o.pkg_name }}</b></div><div class="order-row"><span>Method</span><b>{{ o.payment_method|capitalize }}</b></div>{% if o.payment_ref %}<div class="order-row"><span>Transaction ID</span><code>{{ o.payment_ref }}</code></div>{% endif %}<div class="order-row"><span>Created</span><span>{{ o.created_at|format_datetime }}</span></div>{% if o.status == 'pending' %}<div style="display:flex;gap:10px;margin-top:16px;"><form action="{{ url_for('admin_approve_order', order_id=o.id) }}" method="POST" style="flex:1;"><button type="submit" class="btn-success btn-block">✅ Approve & Activate</button></form><form action="{{ url_for('admin_reject_order', order_id=o.id) }}" method="POST" style="flex:1;" onsubmit="return confirm('Reject this order?');"><button type="submit" class="btn-danger-outline btn-block">❌ Reject</button></form></div>{% endif %}</div>{% else %}<div class="card" style="text-align:center;padding:60px 20px;"><div style="font-size:3rem;margin-bottom:12px;">📭</div><h3>No Orders</h3><p class="muted">Orders will appear here when users purchase plans.</p></div>{% endfor %}</div></div>{% endblock %}"""

ADMIN_PLANS_HTML = """{% extends "base" %}{% block title %}Plan History — Admin{% endblock %}{% block content %}<div class="wrap"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>📋 Plan Activation History</h1></div></div><div class="card">{% for h in history %}<div class="mini-row"><div><b>{{ h.full_name }}</b> <span class="muted">@{{ h.username }}</span><br><span class="muted-sm">{{ h.pkg_name }} · {{ h.action }} · ₹{{ h.amount }}</span></div><div style="text-align:right;"><div class="muted-sm">{{ h.created_at|format_datetime }}</div></div></div>{% else %}<div class="empty-mini">No plan history yet</div>{% endfor %}</div></div>{% endblock %}"""

ADMIN_TRIALS_HTML = """{% extends "base" %}{% block title %}Trials — Admin{% endblock %}{% block content %}<div class="wrap"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>🎁 Trial Tracking</h1></div><div class="stat-chip">{{ converted }}/{{ total }} converted</div></div><div class="card">{% for t in trials %}<div class="mini-row"><div><b>{{ t.full_name }}</b> <span class="muted">@{{ t.username }}</span><br><span class="muted-sm">IP: <code>{{ t.ip_address }}</code> · {{ t.started_at|format_datetime }}</span></div><div style="text-align:right;">{% if t.converted_to_plan %}<span class="badge badge-success">✅ Converted</span>{% else %}<span class="badge badge-gray">Not converted</span>{% endif %}</div></div>{% else %}<div class="empty-mini">No trials yet</div>{% endfor %}</div></div>{% endblock %}"""

ADMIN_NOTIFICATIONS_HTML = """{% extends "base" %}{% block title %}Notifications — Admin{% endblock %}{% block content %}<div class="wrap"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>🔔 Admin Notifications</h1></div></div><div class="card">{% for n in notifications %}<div class="mini-row"><div><div style="font-weight:700;">{{ n.title }}</div><div class="muted-sm">{{ n.message }}</div></div><div style="text-align:right;"><span class="muted-sm">{{ n.created_at|format_datetime }}</span></div></div>{% else %}<div class="empty-mini">No notifications</div>{% endfor %}</div></div>{% endblock %}"""

ADMIN_USERS_HTML = """{% extends "base" %}{% block title %}Users — Admin{% endblock %}{% block content %}<div class="wrap"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>👥 User Management</h1></div><div class="stat-chip">{{ users|length }} total</div></div><div class="card"><form method="GET" style="display:flex;gap:10px;"><input type="text" name="q" value="{{ search_query or '' }}" placeholder="Search by name, username or email" class="input-flex"><button type="submit" class="btn-primary">Search</button>{% if search_query %}<a href="{{ url_for('admin_users') }}" class="btn-secondary">Clear</a>{% endif %}</form></div><div style="display:flex;flex-direction:column;gap:14px;">{% for u in users %}{% set u_super = u.role == 'super_admin' or u.is_super_admin %}{% set u_admin = u_super or u.role == 'admin' or u.is_admin %}<div class="user-card {% if u.status=='disabled' %}user-disabled{% elif u_super %}user-super{% elif u_admin %}user-admin{% endif %}"><div class="user-head"><div class="user-id"><div class="user-avatar-lg {% if u_super %}av-super{% elif u_admin %}av-admin{% endif %}">{% if u.avatar_url %}<img src="{{ u.avatar_url }}" alt="">{% elif u_super %}👑{% elif u_admin %}🛡️{% else %}{{ u.username[0]|upper }}{% endif %}</div><div><div class="user-name-row"><h3>{{ u.full_name }}</h3><span class="status-pill-sm {% if u.status=='active' %}on{% else %}off{% endif %}">{{ u.status|upper }}</span>{% if u_super %}<span class="role-badge role-super">👑 SUPER</span>{% elif u_admin %}<span class="role-badge role-admin">🛡️ ADMIN</span>{% endif %}</div><div class="muted-sm">@{{ u.username }} · {{ u.email }} · Limit: {{ u.project_limit if u.project_limit >= 0 else '∞' }}</div></div></div><div class="user-metrics"><div class="metric">🖥️ {{ u.server_count }}</div>{% if is_super_admin or not u_super %}<button type="button" class="btn-secondary btn-sm" onclick="openEditUser({{ u.id }}, '{{ u.full_name|e }}', '{{ u.username|e }}', '{{ u.email|e }}', '{{ (u.bio or '')|e }}', {{ u.project_limit }}, '{{ u.role }}', '{{ u.status }}', '{{ (u.admin_permissions or '')|e }}', {{ 'true' if u_super else 'false' }})">✏️ Edit</button>{% endif %}{% if u.id != current_user.id %}<a href="{{ url_for('admin_impersonate', user_id=u.id) }}" class="btn-secondary btn-sm">🛡️ Open</a>{% if is_super_admin or not u_admin %}<form action="{{ url_for('admin_toggle_status', user_id=u.id) }}" method="POST" style="display:inline;">{% if u.status == 'active' %}<button type="submit" class="btn-danger btn-sm" onclick="return confirm('Disable this account?');">🔒</button>{% else %}<button type="submit" class="btn-success btn-sm" onclick="return confirm('Activate this account?');">🔓</button>{% endif %}</form>{% endif %}{% endif %}</div></div></div>{% else %}<div class="card" style="text-align:center;padding:60px 20px;"><h3>No users found</h3></div>{% endfor %}</div></div><div id="edit-user-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:600px;max-height:90vh;overflow-y:auto;"><div style="display:flex;justify-content:space-between;margin-bottom:20px;"><div><h2 style="margin:0;font-size:1.25rem;font-weight:800;">Edit User</h2><p class="muted-sm" style="margin-top:4px;">Update account details and permissions</p></div><button onclick="closeEditUser()" class="modal-x" style="position:static;">✕</button></div><form id="edit-user-form" method="POST"><div class="grid grid-2" style="gap:14px;"><div class="field span-2"><label>Full Name</label><input type="text" id="eu_name" name="full_name" required></div><div class="field"><label>Username</label><input type="text" id="eu_user" name="username" required minlength="3"></div><div class="field"><label>Gmail</label><input type="email" id="eu_email" name="email" required></div><div class="field"><label>Project Limit (-1 = ∞)</label><input type="number" id="eu_limit" name="project_limit" min="-1" required></div><div class="field"><label>Role</label>{% if is_super_admin %}<select id="eu_role" name="role" onchange="togglePermBlock(this.value)"><option value="user">Standard User</option><option value="admin">Sub-Admin</option><option value="super_admin">Super Admin</option></select>{% else %}<select disabled><option>User</option></select>{% endif %}</div>{% if is_super_admin %}<div id="perm-block" class="field span-2" style="display:none;background:var(--bg-2);padding:16px;border-radius:12px;"><label style="margin-bottom:12px;">Permissions</label><div class="grid grid-2" style="gap:10px;"><label class="check"><input type="checkbox" name="permissions" value="manage_users" id="p_users"> Users</label><label class="check"><input type="checkbox" name="permissions" value="manage_payments" id="p_payments"> Payments</label><label class="check"><input type="checkbox" name="permissions" value="manage_files" id="p_files"> Files</label><label class="check"><input type="checkbox" name="permissions" value="manage_settings" id="p_settings"> Settings</label><label class="check"><input type="checkbox" name="permissions" value="manage_announcements" id="p_announcements"> Announcements</label><label class="check"><input type="checkbox" name="permissions" value="manage_broadcasts" id="p_broadcasts"> Broadcast</label><label class="check"><input type="checkbox" name="permissions" value="manage_orders" id="p_orders"> Orders</label><label class="check"><input type="checkbox" name="permissions" value="view_logs" id="p_logs"> Logs</label></div></div>{% endif %}<div class="field span-2"><label>Status</label><select id="eu_status" name="status"><option value="active">Active</option><option value="disabled">Disabled</option></select></div><div class="field span-2"><label>Bio</label><input type="text" id="eu_bio" name="bio"></div><div class="field span-2" style="background:var(--bg-2);padding:14px;border-radius:10px;"><label>Password Reset (optional)</label><input type="password" id="eu_pass" name="new_password" minlength="6" placeholder="Leave blank to keep current password"></div></div><div style="display:flex;justify-content:flex-end;gap:10px;margin-top:24px;"><button type="button" onclick="closeEditUser()" class="btn-secondary">Cancel</button><button type="submit" class="btn-primary">Save Changes</button></div></form></div></div>{% endblock %}"""

ADMIN_PAYMENTS_HTML = """{% extends "base" %}{% block title %}Payment Settings — Admin{% endblock %}{% block content %}<div class="wrap" style="max-width:900px;"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>💰 Payment Settings</h1><p>Configure UPI IDs and auto-verification</p></div></div><div class="payment-owner-section"><h2>UPI Configuration</h2><p>Add UPI IDs for each payment app. The system auto-detects the app from the UPI suffix.</p><form method="POST"><input type="hidden" name="action" value="update_upi"><div class="payment-app-grid">{% for app_key, app_name, app_logo in [('phonepe','PhonePe','https://upload.wikimedia.org/wikipedia/commons/thumb/7/71/PhonePe_Logo.svg/120px-PhonePe_Logo.svg.png'),('gpay','Google Pay','https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/Google_Pay_Logo.svg/120px-Google_Pay_Logo.svg.png'),('paytm','Paytm','https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Paytm_Logo_%28standalone%29.svg/120px-Paytm_Logo_%28standalone%29.svg.png'),('fampay','FamPay','https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Fampay_logo.png/120px-Fampay_logo.png'),('bhim','BHIM','https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/BHIM_logo.svg/120px-BHIM_logo.svg.png'),('amazonpay','Amazon Pay','https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Amazon_Pay_logo.svg/120px-Amazon_Pay_logo.svg.png')] %}<div class="payment-app-item {% if settings['upi_' + app_key] %}enabled{% endif %}"><div class="payment-app-header"><div class="payment-app-name"><img src="{{ app_logo }}" alt="{{ app_name }}" class="payment-app-logo" onerror="this.style.display='none';"><span>{{ app_name }}</span></div></div><div class="payment-app-input"><input type="text" name="upi_{{ app_key }}" value="{{ settings['upi_' + app_key] }}" placeholder="example@{{ app_key }}"></div>{% if qr_previews.get(app_key) %}<div class="payment-app-qr-preview"><img src="{{ qr_previews[app_key] }}" alt="QR"><div class="qr-label">Auto-generated QR</div></div>{% endif %}</div>{% endfor %}</div><div class="field" style="margin-top:24px;"><label>Primary Payment App (default QR)</label><select name="primary_upi" style="font-weight:700;">{% for app_key, app_name in [('phonepe','PhonePe'),('gpay','Google Pay'),('paytm','Paytm'),('fampay','FamPay'),('bhim','BHIM'),('amazonpay','Amazon Pay')] %}<option value="{{ app_key }}" {% if settings.primary_upi == app_key %}selected{% endif %}>{{ app_name }}</option>{% endfor %}</select><small>This app's QR will be shown by default on checkout</small></div><button type="submit" class="btn-primary mt-2">Save UPI Settings</button></form></div><div class="payment-owner-section" style="border-color:#BAE6FD;background:linear-gradient(135deg,#F0F9FF 0%,#FFFFFF 100%);"><h2>Auto-Verify (Optional)</h2><p>Enable automatic payment verification for FamPay and Razorpay.</p><form method="POST"><input type="hidden" name="action" value="update_auto"><div class="toggle-box"><label class="toggle-label"><div><b>Enable Auto-Verify</b><span class="muted">Payments verify automatically without admin approval</span></div><input type="checkbox" name="payment_autodetect_enabled" {% if settings.payment_autodetect_enabled == '1' %}checked{% endif %} class="toggle-input"></label></div><div class="grid grid-2" style="gap:16px;"><div class="field"><label>FamPay API Key</label><input type="text" name="fampay_api_key" value="{{ settings.fampay_api_key }}" placeholder="FAM_xxxxx"><small>For FamPay auto-verify</small></div></div><div class="grid grid-2" style="gap:16px;"><div class="field"><label>Razorpay Key ID</label><input type="text" name="razorpay_key_id" value="{{ settings.razorpay_key_id }}" placeholder="rzp_live_xxxxx"><small>For PhonePe/GPay/Paytm auto-verify</small></div><div class="field"><label>Razorpay Key Secret</label><input type="password" name="razorpay_key_secret" value="{{ settings.razorpay_key_secret }}" placeholder="Your secret key"></div></div><button type="submit" class="btn-primary">Save Auto-Verify Settings</button></form></div></div>{% endblock %}"""







# ============================================================
# ADMIN SETTINGS HTML
# ============================================================
ADMIN_SETTINGS_HTML = """{% extends "base" %}{% block title %}Settings — Admin{% endblock %}{% block content %}<div class="wrap" style="max-width:800px;"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>⚙️ Platform Settings</h1></div></div><div class="card"><h2>🎨 Logo & Branding</h2><p class="muted" style="margin-bottom:20px;">Upload custom logo. Changes apply instantly.</p><div class="logo-preview-box"><div style="display:flex;flex-direction:column;align-items:center;gap:8px;"><div class="logo-preview-frame">{% if settings.site_logo_url %}<img id="admin_logo_preview" src="{{ settings.site_logo_url }}" alt="">{% else %}<span style="font-size:2rem;">⚡</span>{% endif %}</div><span class="muted-sm">Active Logo</span></div><div style="flex:1;min-width:240px;"><form action="{{ url_for('admin_settings') }}" method="POST" enctype="multipart/form-data"><input type="hidden" name="action" value="upload_logo"><div style="display:flex;gap:10px;flex-wrap:wrap;"><label class="btn-secondary">📁 Choose Logo<input type="file" name="logo" accept="image/*" style="display:none;" onchange="handleLogoPreview(this)" required></label><button type="submit" class="btn-primary">⬆️ Upload</button></div><div id="admin_logo_filename" class="muted-sm" style="margin-top:8px;">PNG, JPG, WEBP, GIF, SVG, ICO (Max 5MB)</div></form></div></div>{% if settings.site_logo_url %}<form action="{{ url_for('admin_settings') }}" method="POST" onsubmit="return confirm('Reset to default logo?');" style="margin-top:12px;"><input type="hidden" name="action" value="reset_logo"><button type="submit" class="btn-danger-outline">🗑️ Reset Logo</button></form>{% endif %}</div><div class="card"><h2>🏷️ Site Branding</h2><form action="{{ url_for('admin_settings') }}" method="POST"><input type="hidden" name="action" value="update_branding"><div class="field"><label>Standard Site Name</label><input type="text" name="site_name" value="{{ settings.site_name }}" required></div><div class="field"><label>VIP / Full Name</label><input type="text" name="vip_site_name" value="{{ settings.vip_site_name }}" required></div><button type="submit" class="btn-primary">Save Branding</button></form></div><div class="card" style="border-color:#FDE68A;background:#FFFBEB;"><h2>🎁 Free Trial</h2><form action="{{ url_for('admin_settings') }}" method="POST"><input type="hidden" name="action" value="update_trial"><div class="toggle-box"><label class="toggle-label"><div><b>Enable Free Trial</b><span class="muted">New users receive a free trial</span></div><input type="checkbox" name="trial_enabled" {% if settings.trial_enabled == '1' %}checked{% endif %} class="toggle-input"></label></div><div class="grid grid-2" style="gap:20px;"><div class="field"><label>Trial Duration (hours)</label><input type="number" name="trial_hours" value="{{ settings.trial_hours }}" min="1" max="720" required></div><div class="field"><label>Project Limit</label><input type="number" name="trial_project_limit" value="{{ settings.trial_project_limit }}" min="1" max="100" required></div></div><div class="badge badge-warn" style="padding:8px 12px;font-size:0.8rem;margin-bottom:16px;">⚠️ One trial per IP address</div><button type="submit" class="btn-primary">Save Trial Settings</button></form></div><div class="card"><h2>🛠️ Maintenance Mode</h2><form action="{{ url_for('admin_settings') }}" method="POST"><input type="hidden" name="action" value="update_maintenance"><div class="toggle-box"><label class="toggle-label"><div><b>Enable Maintenance</b></div><input type="checkbox" name="maintenance_mode" {% if settings.maintenance_mode == '1' %}checked{% endif %} class="toggle-input"></label></div><div class="field"><label>Message</label><textarea name="maintenance_message" rows="3" class="form-control">{{ settings.maintenance_message }}</textarea></div><button type="submit" class="btn-primary">Save</button></form></div><div class="card" style="border-color:#BAE6FD;background:#F0F9FF;"><h2>🔄 Self-Ping</h2><form action="{{ url_for('admin_settings') }}" method="POST"><input type="hidden" name="action" value="update_self_ping"><div class="toggle-box"><label class="toggle-label"><div><b>Enable Self-Ping</b></div><input type="checkbox" name="self_ping_enabled" {% if settings.self_ping_enabled == '1' %}checked{% endif %} class="toggle-input"></label></div><div class="field"><label>Interval (minutes)</label><input type="number" name="self_ping_interval" value="{{ settings.self_ping_interval }}" min="1" max="60" required></div><button type="submit" class="btn-primary">Save</button></form></div><div class="card"><h2>📦 Server Packages</h2><div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;"><button type="button" onclick="toggleNewPkg()" class="btn-secondary">➕ Add New Package</button></div><div id="new-pkg-form" style="display:none;background:var(--bg-2);padding:20px;border-radius:12px;margin-bottom:20px;border:1.5px dashed #C084FC;"><h3 style="margin:0 0 16px;">Add New Package</h3><form action="{{ url_for('admin_create_pkg') }}" method="POST"><div class="grid grid-3" style="gap:12px;"><div class="field"><label>Name</label><input type="text" name="name" required></div><div class="field"><label>Price (₹)</label><input type="number" name="price" min="0" required></div><div class="field"><label>Days</label><input type="number" name="days" min="1" required></div></div><div class="grid grid-2" style="gap:12px;"><div class="field"><label>Project Limit</label><input type="number" name="project_limit" min="-1" required></div><div class="field"><label>Description</label><input type="text" name="features"></div></div><button type="submit" class="btn-primary">Create Package</button></form></div><div style="display:flex;flex-direction:column;gap:14px;">{% for pkg in packages %}<div class="pkg-edit-card {% if pkg.is_popular %}pkg-fto{% endif %}"><form action="{{ url_for('admin_update_pkg') }}" method="POST"><input type="hidden" name="id" value="{{ pkg.id }}"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:16px;"><div><b style="font-size:1.1rem;">{{ pkg.name }}</b>{% if pkg.is_trial %}<span class="badge badge-success" style="margin-left:8px;">TRIAL</span>{% endif %}{% if pkg.is_popular %}<span class="badge badge-purple" style="margin-left:8px;">POPULAR</span>{% endif %}</div></div><div class="grid grid-3" style="gap:12px;"><div class="field"><label>Name</label><input type="text" name="name" value="{{ pkg.name }}" required></div><div class="field"><label>Price (₹)</label><input type="number" name="price" value="{{ pkg.price }}" min="0" required></div><div class="field"><label>Days</label><input type="number" name="days" value="{{ pkg.days }}" min="1" required></div></div><div class="grid grid-2" style="gap:12px;"><div class="field"><label>Project Limit (-1 = ∞)</label><input type="number" name="project_limit" value="{{ pkg.project_limit }}" min="-1" required></div><div class="field"><label>Description</label><input type="text" name="features" value="{{ pkg.features }}"></div></div><div style="display:flex;justify-content:space-between;align-items:center;padding-top:14px;border-top:1px solid var(--border-light);"><div style="display:flex;gap:16px;"><label class="check"><input type="checkbox" name="active" value="1" {% if pkg.active %}checked{% endif %}> Active</label><label class="check"><input type="checkbox" name="is_popular" value="1" {% if pkg.is_popular %}checked{% endif %}> Popular</label></div><button type="submit" class="btn-primary btn-sm">💾 Save</button></div></form>{% if packages|length > 1 and not pkg.is_trial %}<form action="{{ url_for('admin_delete_pkg', pid=pkg.id) }}" method="POST" onsubmit="return confirm('Delete this package?');" style="text-align:right;margin-top:10px;"><button type="submit" class="btn-ghost btn-sm" style="color:var(--danger);">Delete this tier</button></form>{% endif %}</div>{% endfor %}</div></div></div>{% endblock %}"""


# ============================================================
# ADMIN ANNOUNCEMENTS HTML
# ============================================================
ADMIN_ANNOUNCEMENTS_HTML = """{% extends "base" %}{% block title %}Announcements — Admin{% endblock %}{% block content %}<div class="wrap" style="max-width:900px;"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>📢 System Announcements</h1><p>Publish updates and notices for all users</p></div></div><div class="card" style="border-color:#DDD6FE;"><h2>Publish New Announcement</h2><form action="{{ url_for('admin_create_ann') }}" method="POST"><div class="grid grid-2" style="gap:16px;margin-bottom:16px;"><div class="field"><label>Title</label><input type="text" name="title" placeholder="e.g. System upgrade live" required></div><div class="field"><label>Type</label><select name="type"><option value="update">🚀 Update</option><option value="info">ℹ️ Info</option><option value="warning">⚠️ Warning</option><option value="maintenance">🛠️ Maintenance</option></select></div></div><div class="field"><label>Content</label><textarea name="content" rows="4" class="form-control" placeholder="Write your announcement..." required></textarea></div><div class="ann-options"><div style="display:flex;gap:24px;flex-wrap:wrap;"><label class="check"><input type="checkbox" name="is_active" value="1" checked> Active</label><label class="check"><input type="checkbox" name="pinned" value="1"> Pin to top</label></div><button type="submit" class="btn-primary">Publish Announcement</button></div></form></div><div style="display:flex;flex-direction:column;gap:14px;">{% for a in announcements %}<div class="ann-admin-card ann-{{ a.type }}"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:12px;"><div><div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px;"><span class="badge badge-primary">{{ a.type|upper }}</span>{% if a.pinned %}<span class="badge badge-warn">📌 PINNED</span>{% endif %}{% if a.is_active %}<span class="badge badge-success">● LIVE</span>{% else %}<span class="badge badge-gray">INACTIVE</span>{% endif %}</div><h3 style="margin:0;font-size:1.1rem;font-weight:800;">{{ a.title }}</h3></div><div style="display:flex;gap:8px;flex-wrap:wrap;"><form action="{{ url_for('admin_toggle_ann', aid=a.id) }}" method="POST" style="margin:0;"><button class="btn-secondary btn-sm">{% if a.is_active %}Hide{% else %}Show{% endif %}</button></form><form action="{{ url_for('admin_toggle_pin', aid=a.id) }}" method="POST" style="margin:0;"><button class="btn-secondary btn-sm">{% if a.pinned %}Unpin{% else %}Pin{% endif %}</button></form><form action="{{ url_for('admin_delete_ann', aid=a.id) }}" method="POST" style="margin:0;" onsubmit="return confirm('Delete this announcement?');"><button class="btn-danger btn-sm">🗑️</button></form></div></div><p style="font-size:0.9rem;color:var(--text-2);white-space:pre-line;margin:0;line-height:1.6;">{{ a.content }}</p></div>{% else %}<div class="card" style="text-align:center;padding:60px 20px;"><div style="font-size:3rem;margin-bottom:12px;">📢</div><h3>No Announcements Yet</h3></div>{% endfor %}</div></div>{% endblock %}"""


# ============================================================
# ADMIN BROADCAST HTML
# ============================================================
ADMIN_BROADCAST_HTML = """{% extends "base" %}{% block title %}Broadcast — Admin{% endblock %}{% block content %}<div class="wrap" style="max-width:900px;"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>⚡ Notification Broadcast</h1><p>Send in-app notifications to users</p></div><div class="stat-chip">{{ users|length }} Active</div></div><div class="card"><h2>Create Broadcast</h2><form method="POST" action="{{ url_for('admin_broadcast') }}"><div class="field"><label>Target Audience</label><div class="grid grid-2" style="gap:12px;"><label class="target-box" id="t-all"><input type="radio" name="target_type" value="all" checked onchange="pickTarget('all')"><div><b>🌐 All Users</b><span>Send to {{ users|length }} active users</span></div></label><label class="target-box" id="t-spec"><input type="radio" name="target_type" value="specific" onchange="pickTarget('specific')"><div><b>👤 Specific User</b><span>Send to one account</span></div></label></div></div><div id="specific-user" class="field" style="display:none;background:var(--bg-2);padding:16px;border-radius:12px;"><label>Select User</label><select name="target_user_id"><option value="">-- Choose User --</option>{% for u in users %}<option value="{{ u.id }}">{{ u.full_name }} (@{{ u.username }}) — {{ u.email }}</option>{% endfor %}</select></div><div class="grid grid-2" style="gap:16px;margin-bottom:16px;"><div class="field"><label>Title</label><input type="text" name="title" placeholder="e.g. System Update" required></div><div class="field"><label>Category</label><select name="category"><option value="announcement">📢 Announcement</option><option value="system">⚙️ System</option><option value="warning">⚠️ Warning</option><option value="info">ℹ️ Info</option></select></div></div><div class="field"><label>Message</label><textarea name="message" rows="4" class="form-control" placeholder="Type your message..." required></textarea></div><div style="display:flex;justify-content:flex-end;"><button type="submit" class="btn-primary btn-lg">🚀 Send Broadcast</button></div></form></div><div class="card" style="margin-top:24px;"><h3 style="margin-bottom:16px;">Recent Broadcasts</h3>{% if broadcasts %}<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.85rem;"><thead><tr style="background:var(--bg-2);text-align:left;font-size:0.75rem;font-weight:800;color:var(--muted);"><th style="padding:12px;">ID</th><th style="padding:12px;">Admin</th><th style="padding:12px;">Target</th><th style="padding:12px;">Title</th><th style="padding:12px;">Sent</th></tr></thead><tbody>{% for b in broadcasts %}<tr style="border-bottom:1px solid var(--border-light);"><td style="padding:12px;font-weight:700;color:var(--muted);">#{{ b.id }}</td><td style="padding:12px;font-weight:700;color:var(--primary);">@{{ b.admin_username }}</td><td style="padding:12px;">{% if b.target_type == 'all' %}<span class="badge badge-primary">🌐 All ({{ b.recipients_count }})</span>{% else %}<span class="badge badge-success">👤 @{{ b.target_username }}</span>{% endif %}</td><td style="padding:12px;"><b>{{ b.title }}</b></td><td style="padding:12px;color:var(--muted-2);">{{ b.created_at|format_datetime }}</td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="empty-mini">No broadcasts yet</div>{% endif %}</div></div>{% endblock %}"""


# ============================================================
# ADMIN LOGS HTML
# ============================================================
ADMIN_LOGS_HTML = """{% extends "base" %}{% block title %}Audit Logs — Admin{% endblock %}{% block content %}<div class="wrap" style="max-width:900px;"><div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>📜 Audit Logs</h1><p>Track all admin actions</p></div></div><div class="card">{% for log in logs %}<div class="mini-row" style="flex-direction:column;align-items:stretch;gap:6px;"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;"><div style="display:flex;gap:8px;align-items:center;"><span class="badge badge-primary">{{ log.action }}</span><b>@{{ log.admin_username }}</b></div><span class="muted-sm" style="font-family:var(--font-mono);">{{ log.created_at|format_datetime }}</span></div><div style="font-size:0.85rem;color:var(--text-2);"><b>Target:</b> {{ log.target }}{% if log.details %} · {{ log.details }}{% endif %}</div></div>{% else %}<div class="empty-mini">No audit logs yet</div>{% endfor %}</div></div>{% endblock %}"""


# ============================================================
# JINJA2 TEMPLATE LOADER
# ============================================================
import jinja2

_TEMPLATES = {
    'base': BASE_HTML,
    'home': HOME_HTML,
    'signin': SIGNIN_HTML,
    'signup': SIGNUP_HTML,
    'dashboard': DASHBOARD_HTML,
    'packages': PACKAGES_HTML,
    'checkout': CHECKOUT_HTML,
    'payment': PAYMENT_HTML,
    'create_server': CREATE_SERVER_HTML,
    'server_manage': SERVER_MANAGE_HTML,
    'file_manager': FILE_MANAGER_HTML,
    'account': ACCOUNT_HTML,
    'admin_dashboard': ADMIN_DASHBOARD_HTML,
    'admin_orders': ADMIN_ORDERS_HTML,
    'admin_plans': ADMIN_PLANS_HTML,
    'admin_trials': ADMIN_TRIALS_HTML,
    'admin_notifications': ADMIN_NOTIFICATIONS_HTML,
    'admin_users': ADMIN_USERS_HTML,
    'admin_payments': ADMIN_PAYMENTS_HTML,
    'admin_settings': ADMIN_SETTINGS_HTML,
    'admin_announcements': ADMIN_ANNOUNCEMENTS_HTML,
    'admin_broadcast': ADMIN_BROADCAST_HTML,
    'admin_logs': ADMIN_LOGS_HTML,
}

class _DictLoader(jinja2.BaseLoader):
    def __init__(self, mapping):
        self.mapping = mapping
    def get_source(self, environment, template):
        if template not in self.mapping:
            raise jinja2.TemplateNotFound(template)
        return self.mapping[template], f"{template}.html", lambda: False

app.jinja_loader = _DictLoader(_TEMPLATES)


# ============================================================
# STATIC FILE ROUTES
# ============================================================
@app.route('/style.css')
def _style():
    p = os.path.join(BASE_DIR, 'style.css')
    if os.path.exists(p):
        return send_file(p, mimetype='text/css')
    return "", 404

@app.route('/script.js')
def _script():
    p = os.path.join(BASE_DIR, 'script.js')
    if os.path.exists(p):
        return send_file(p, mimetype='application/javascript')
    return "", 404


# ============================================================
# PROXY ROUTE — User Project URLs
# ============================================================
@app.route('/<slug>/', defaults={'path': ''})
@app.route('/<slug>/<path:path>')
def proxy_server(slug, path):
    reserved = {'signin','signup','signout','dashboard','packages','account',
                'admin','servers','api','health','style.css','script.js','static',
                'checkout','payment','auth','favicon.ico','home'}
    if slug in reserved:
        abort(404)
    db = get_db()
    server = db.execute("SELECT * FROM servers WHERE slug=?", (slug,)).fetchone()
    if not server:
        return render_template_string("{% extends 'base' %}{% block content %}<div class='wrap' style='max-width:480px;text-align:center;margin-top:60px;'><div class='card' style='padding:60px 32px;'><div style='font-size:4rem;margin-bottom:16px;'>🔍</div><h1 style='font-size:1.75rem;font-weight:900;margin-bottom:8px;'>Project Not Found</h1><p class='muted' style='margin-bottom:24px;'>The project \"{{ slug }}\" doesn't exist.</p><a href='{{ url_for(\"home\") }}' class='btn-primary btn-lg'>Go Home</a></div></div>{% endblock %}"), 404
    if server['status'] != 'running':
        return render_template_string("{% extends 'base' %}{% block content %}<div class='wrap' style='max-width:480px;text-align:center;margin-top:60px;'><div class='card' style='padding:60px 32px;'><div style='font-size:4rem;margin-bottom:16px;'>⚠️</div><h1 style='font-size:1.75rem;font-weight:900;margin-bottom:8px;'>Project Offline</h1><p class='muted' style='margin-bottom:24px;'>This project is currently stopped.</p><a href='{{ url_for(\"home\") }}' class='btn-primary btn-lg'>Go Home</a></div></div>{% endblock %}"), 503
    port = server['port']
    if not port:
        return "Port not assigned", 500
    query = request.query_string.decode('utf-8')
    target_url = f"http://127.0.0.1:{port}/{path}"
    if query:
        target_url += f"?{query}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ('host', 'content-length', 'connection')}
    try:
        resp = requests.request(method=request.method, url=target_url, headers=headers,
                                 data=request.get_data(), cookies=request.cookies,
                                 allow_redirects=False, timeout=30, stream=True)
        excluded = ('content-encoding', 'content-length', 'transfer-encoding', 'connection')
        resp_headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded]
        return Response(stream_with_context(resp.iter_content(chunk_size=8192)),
                        status=resp.status_code, headers=resp_headers)
    except requests.exceptions.ConnectionError:
        db.execute("UPDATE servers SET status='error' WHERE id=?", (server['id'],))
        db.commit()
        return "Project crashed. Please restart.", 503
    except Exception as e:
        return f"Proxy error: {str(e)}", 500


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def _e404(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template_string("{% extends 'base' %}{% block title %}404 Not Found{% endblock %}{% block content %}<div class='wrap' style='max-width:480px;text-align:center;margin-top:60px;'><div class='card' style='padding:60px 32px;'><div style='font-size:4rem;margin-bottom:16px;'>🔍</div><h1 style='font-size:1.75rem;font-weight:900;margin-bottom:8px;'>Page Not Found</h1><p class='muted' style='margin-bottom:24px;'>The page you're looking for doesn't exist.</p><a href='{{ url_for(\"dashboard\") if current_user else url_for(\"home\") }}' class='btn-primary btn-lg'>Go Home</a></div></div>{% endblock %}"), 404

@app.errorhandler(500)
def _e500(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Server error'}), 500
    return render_template_string("{% extends 'base' %}{% block title %}500 Error{% endblock %}{% block content %}<div class='wrap' style='max-width:480px;text-align:center;margin-top:60px;'><div class='card' style='padding:60px 32px;'><div style='font-size:4rem;margin-bottom:16px;'>⚠️</div><h1 style='font-size:1.75rem;font-weight:900;margin-bottom:8px;'>Server Error</h1><p class='muted' style='margin-bottom:24px;'>Something went wrong. Please try again.</p><a href='{{ url_for(\"dashboard\") if current_user else url_for(\"home\") }}' class='btn-primary btn-lg'>Go Home</a></div></div>{% endblock %}"), 500

@app.errorhandler(403)
def _e403(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Forbidden'}), 403
    return render_template_string("{% extends 'base' %}{% block title %}403 Forbidden{% endblock %}{% block content %}<div class='wrap' style='max-width:480px;text-align:center;margin-top:60px;'><div class='card' style='padding:60px 32px;'><div style='font-size:4rem;margin-bottom:16px;'>🛡️</div><h1 style='font-size:1.75rem;font-weight:900;margin-bottom:8px;'>Access Denied</h1><p class='muted' style='margin-bottom:24px;'>You don't have permission to access this page.</p><a href='{{ url_for(\"dashboard\") if current_user else url_for(\"home\") }}' class='btn-primary btn-lg'>Go Home</a></div></div>{% endblock %}"), 403


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    print("=" * 60)
    print(f"  ⚡ HOSTX VIP — Running on http://0.0.0.0:{PORT}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=PORT, debug=False)
















