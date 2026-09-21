"""
HostX VIP — Python Hosting Platform
Single-file Flask app with inline HTML templates.
"""
import os, sys, time, io, json, sqlite3, shutil, zipfile, subprocess, signal, ast, re, threading, random, secrets, hashlib, hmac, jinja2
from datetime import datetime, timedelta, date
from functools import wraps

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

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import (Flask, render_template_string, render_template, request, redirect,
                   url_for, session, flash, jsonify, send_file, abort, Response, g)

# ============================================================
# APP INIT
# ============================================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hostx_vip_secret_key_2026_change_me')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'hostx.db')
SERVERS_DIR = os.path.join(BASE_DIR, 'servers')
AVATARS_DIR = os.path.join(BASE_DIR, 'static', 'avatars')
BRANDING_DIR = os.path.join(BASE_DIR, 'static', 'branding')

if os.path.exists('/data'):
    print("[*] /data detected — using persistent storage")
    DB_PATH = '/data/hostx.db'
    SERVERS_DIR = '/data/servers'
    AVATARS_DIR = '/data/avatars'
    BRANDING_DIR = '/data/branding'

for d in [os.path.dirname(DB_PATH), SERVERS_DIR, AVATARS_DIR, BRANDING_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# PASSWORD HASHING
# ============================================================
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
                comp = hashlib.scrypt(password.encode(), salt=salt.encode(), n=n, r=r, p=p, maxmem=128*1024*1024).hex()
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

# ============================================================
# DATABASE
# ============================================================
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
        avatar_url TEXT DEFAULT '',
        is_admin INTEGER DEFAULT 0,
        is_super_admin INTEGER DEFAULT 0,
        admin_permissions TEXT DEFAULT ''
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
        name TEXT NOT NULL, days INTEGER NOT NULL, coins INTEGER NOT NULL,
        is_first_time_offer INTEGER DEFAULT 0, description TEXT, active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS coin_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, amount INTEGER NOT NULL, balance_after INTEGER NOT NULL,
        description TEXT NOT NULL, transaction_type TEXT DEFAULT 'credit',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS server_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL, level TEXT DEFAULT 'INFO', message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS admin_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER, admin_username TEXT NOT NULL, action TEXT NOT NULL,
        target TEXT NOT NULL, details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, title TEXT DEFAULT 'Notification', message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, content TEXT NOT NULL, type TEXT DEFAULT 'update',
        is_active INTEGER DEFAULT 1, pinned INTEGER DEFAULT 0,
        created_by TEXT DEFAULT 'Administrator', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS broadcast_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER, admin_username TEXT NOT NULL, title TEXT NOT NULL,
        message TEXT NOT NULL, category TEXT DEFAULT 'announcement',
        target_type TEXT NOT NULL, target_user_id INTEGER, target_username TEXT,
        recipients_count INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    cur.execute("SELECT COUNT(*) FROM packages")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO packages (name, days, coins, is_first_time_offer, description, active) VALUES (?,?,?,?,?,?)",
            [('First Time Offer',5,10,1,'Exclusive 5-day trial for new users',1),
             ('Standard 7 Days',7,20,0,'1-week hosting for testing',1),
             ('Standard 15 Days',15,30,0,'2-week continuous hosting',1),
             ('Standard 30 Days',30,60,0,'Full month hosting',1),
             ('Standard 60 Days',60,100,0,'2 months with discount',1),
             ('Standard 90 Days',90,150,0,'Quarterly hosting',1)])

    defaults = {'maintenance_mode':'0','maintenance_message':'New Update — Platform is undergoing upgrades. Back shortly!',
        'default_starting_coins':'50','daily_reward_coins':'10','site_title':'HostX VIP',
        'site_name':'HostX','vip_site_name':'HostX VIP','self_ping_enabled':'1',
        'self_ping_interval':'5','site_logo_url':''}
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    cur.execute("SELECT COUNT(*) FROM announcements")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO announcements (title, content, type, is_active, pinned, created_by) VALUES (?,?,?,1,1,'Platform Admin')",
            ('🚀 Welcome to HostX VIP', 'Fast, secure, 24/7 Python hosting platform. Deploy your bots, scripts, and APIs in seconds!', 'update'))

    cur.execute("SELECT COUNT(*) FROM users WHERE is_super_admin = 1")
    if cur.fetchone()[0] == 0:
        ae = os.environ.get('ADMIN_EMAIL', 'admin@hostx.vip')
        ap = os.environ.get('ADMIN_PASSWORD', 'admin123')
        cur.execute("INSERT INTO users (full_name, username, email, password_hash, coins, role, is_admin, is_super_admin, admin_permissions, status) VALUES (?,?,?,?,?,?,1,1,'all','active')",
            ('Super Admin', 'admin', ae, safe_generate_password_hash(ap), 1000, 'super_admin'))
        print(f"[*] Super Admin: {ae} / {ap}")

    conn.commit(); conn.close()

init_db()

# ============================================================
# HELPERS
# ============================================================
def get_setting(key, default=None):
    try:
        db = get_db()
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row and row['value'] is not None else default
    except Exception: return default

def set_setting(key, value):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    db.commit()

def log_admin_action(action, target, details=''):
    try:
        db = get_db()
        db.execute("INSERT INTO admin_audit_logs (admin_id, admin_username, action, target, details) VALUES (?,?,?,?,?)",
            (session.get('user_id'), session.get('username','System'), action, target, details))
        db.commit()
    except Exception: pass

def create_notification(user_id, title, message):
    try:
        db = get_db()
        db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)", (user_id, title, message))
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
    except Exception: return None

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
    except Exception: return False

RUNNING_PROCESSES = {}
SERVER_START_TIMES = {}

def get_server_dir(user_id, server_id):
    path = os.path.join(SERVERS_DIR, str(user_id), str(server_id))
    os.makedirs(path, exist_ok=True)
    return path

def is_safe_path(base, path):
    base = os.path.realpath(base); target = os.path.realpath(path)
    return base == target or target.startswith(base + os.sep)

def write_server_log(server_id, level, message):
    try:
        db = get_db()
        db.execute("INSERT INTO server_logs (server_id, level, message) VALUES (?,?,?)", (server_id, level, message))
        db.commit()
        srv = db.execute("SELECT user_id FROM servers WHERE id=?", (server_id,)).fetchone()
        if srv:
            sdir = get_server_dir(srv['user_id'], server_id)
            with open(os.path.join(sdir, 'server.log'), 'a', encoding='utf-8') as lf:
                ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                lf.write(f"[{ts}] [{level}] {message}\n")
    except Exception: pass

# ============================================================
# CONTEXT PROCESSOR
# ============================================================
@app.context_processor
def inject_globals():
    user = get_current_user()
    first_name = ''
    if user:
        try:
            fn = (user['full_name'] or '').strip()
            first_name = fn.split(' ')[0] if fn else (user['username'] or 'User')
        except Exception: first_name = 'User'
    return dict(
        current_user=user, is_admin=is_user_admin(user),
        is_super_admin=is_user_super_admin(user),
        has_admin_permission=has_admin_permission,
        user_first_name=first_name,
        site_name=(get_setting('site_name','HostX') or 'HostX').strip(),
        vip_site_name=(get_setting('vip_site_name','HostX VIP') or 'HostX VIP').strip(),
        site_logo_url=(get_setting('site_logo_url','') or '').strip(),
        maintenance_mode=get_setting('maintenance_mode','0') == '1',
        maintenance_message=get_setting('maintenance_message',''),
        is_impersonating=session.get('is_impersonating', False),
        real_admin_username=session.get('real_admin_username'),
        now=datetime.utcnow()
    )

@app.template_filter('first_word')
def _fw(v):
    return str(v).split(' ')[0] if v else ''

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

# ============================================================
# DECORATORS
# ============================================================
def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if 'user_id' not in session:
            flash('Please sign in.', 'warning')
            return redirect(url_for('signin', next=request.url))
        u = get_current_user()
        if not u:
            flash('Session expired.', 'danger')
            return redirect(url_for('signin'))
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if 'user_id' not in session:
            flash('Please sign in.', 'warning')
            return redirect(url_for('signin', next=request.url))
        u = get_current_user()
        if not u or not is_user_admin(u):
            flash('Admin required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*a, **k)
    return w

def admin_permission_required(perm):
    def d(f):
        @wraps(f)
        def w(*a, **k):
            if 'user_id' not in session:
                flash('Please sign in.', 'warning')
                return redirect(url_for('signin', next=request.url))
            u = get_current_user()
            if not u or not is_user_admin(u):
                flash('Admin required.', 'danger')
                return redirect(url_for('dashboard'))
            if not has_admin_permission(u, perm):
                flash('Permission denied.', 'warning')
                return redirect(url_for('admin_dashboard'))
            return f(*a, **k)
        return w
    return d

@app.before_request
def _maint():
    if request.endpoint in ['static','health','signin','signup','signout','admin_dashboard','stop_impersonating']:
        return
    if get_setting('maintenance_mode','0') == '1':
        u = get_current_user()
        if not is_user_admin(u) and request.endpoint not in ['home','signin','signout','health']:
            if request.path.startswith('/api/'):
                return jsonify({'error':'maintenance','maintenance':True}), 503
            return redirect(url_for('home'))

@app.route('/health')
@app.route('/api/health')
def health():
    return jsonify({'status':'ok','app':'HostX VIP','time':datetime.utcnow().isoformat()})

# ============================================================
# AUTH ROUTES
# ============================================================
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if 'user_id' in session and get_current_user():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        identifier = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        if not identifier or not password:
            flash('Fill all fields.', 'danger')
            return render_template("signin", email=identifier)
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE LOWER(email)=? OR LOWER(username)=?", (identifier, identifier)).fetchone()
        if not user or user['status'] == 'disabled' or not safe_check_password_hash(user['password_hash'], password):
            flash('Invalid credentials.', 'danger')
            return render_template("signin", email=identifier)
        if not str(user['password_hash']).startswith('pbkdf2:sha256:'):
            try:
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (safe_generate_password_hash(password), user['id']))
                db.commit()
            except Exception: pass
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session.permanent = remember
        flash(f'Welcome back, {user["full_name"]}!', 'success')
        nxt = request.args.get('next')
        if nxt and nxt.startswith('/'): return redirect(nxt)
        return redirect(url_for('dashboard'))
    return render_template("signin")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session and get_current_user():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        fn = request.form.get('full_name','').strip()
        un = request.form.get('username','').strip().lower()
        em = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        cp = request.form.get('confirm_password','')
        if not all([fn, un, em, pw]):
            flash('All fields required.', 'danger')
            return render_template("signup", full_name=fn, username=un, email=em)
        if not em.endswith('@gmail.com') or em == '@gmail.com':
            flash('Only Gmail addresses allowed.', 'danger')
            return render_template("signup", full_name=fn, username=un, email=em)
        if len(un) < 3:
            flash('Username min 3 chars.', 'danger')
            return render_template("signup", full_name=fn, username=un, email=em)
        if len(pw) < 6:
            flash('Password min 6 chars.', 'danger')
            return render_template("signup", full_name=fn, username=un, email=em)
        if pw != cp:
            flash('Passwords do not match.', 'danger')
            return render_template("signup", full_name=fn, username=un, email=em)
        db = get_db()
        if db.execute("SELECT id FROM users WHERE LOWER(email)=?", (em,)).fetchone():
            flash('Gmail already registered.', 'danger')
            return render_template("signup", full_name=fn, username=un, email=em)
        if db.execute("SELECT id FROM users WHERE LOWER(username)=?", (un,)).fetchone():
            flash('Username taken.', 'danger')
            return render_template("signup", full_name=fn, username=un, email=em)
        try: starting = max(0, int(get_setting('default_starting_coins','50')))
        except Exception: starting = 50
        cur = db.cursor()
        cur.execute("INSERT INTO users (full_name, username, email, password_hash, coins, role, status) VALUES (?,?,?,?,?,'user','active')",
            (fn, un, em, safe_generate_password_hash(pw), starting))
        uid = cur.lastrowid
        if starting > 0:
            cur.execute("INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?,?,?,'Signup Welcome Bonus','credit')", (uid, starting, starting))
            cur.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, '🎁 Welcome Bonus', ?)", (uid, f'Welcome {fn}! You got {starting} coins.'))
        db.commit()
        session.clear()
        session['user_id'] = uid
        session['username'] = un
        session['role'] = 'user'
        session.permanent = True
        flash(f'Account created! You received {starting} welcome coins.', 'success')
        return redirect(url_for('dashboard'))
    return render_template("signup")

@app.route('/signout')
def signout():
    session.clear()
    flash('Signed out safely.', 'info')
    return redirect(url_for('home'))

# ============================================================
# FORGOT PASSWORD + GMAIL QUICK LOGIN
# ============================================================
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
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Enter a number.'})
    if session.get('fp_ans') is not None and ua == session.get('fp_ans'):
        session['fp_verified'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Incorrect.'})

@app.route('/api/forgot-password/verify-email', methods=['POST'])
def fp_ve():
    if not session.get('fp_verified'):
        return jsonify({'success': False, 'message': 'Complete captcha first.'})
    em = (request.get_json() or {}).get('email','').strip().lower()
    if not em: return jsonify({'success': False, 'message': 'Enter email.'})
    db = get_db()
    if db.execute("SELECT id FROM users WHERE LOWER(email)=?", (em,)).fetchone():
        session['fp_email'] = em
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Email not registered.'})

@app.route('/api/forgot-password/reset', methods=['POST'])
def fp_reset():
    if not session.get('fp_verified') or not session.get('fp_email'):
        return jsonify({'success': False, 'message': 'Session expired.'})
    d = request.get_json() or {}
    pw = d.get('password',''); cp = d.get('confirm_password','')
    if not pw or not cp: return jsonify({'success': False, 'message': 'Both fields required.'})
    if pw != cp: return jsonify({'success': False, 'message': 'Passwords do not match.'})
    if len(pw) < 6: return jsonify({'success': False, 'message': 'Min 6 chars.'})
    db = get_db()
    try:
        db.execute("UPDATE users SET password_hash=? WHERE LOWER(email)=?", (safe_generate_password_hash(pw), session.get('fp_email')))
        db.commit()
        session.pop('fp_ans', None); session.pop('fp_verified', None); session.pop('fp_email', None)
        return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'message': str(e)})

@app.route('/api/quick-gmail-login', methods=['POST'])
def quick_gmail():
    d = request.get_json() or {}
    em = (d.get('email') or '').strip().lower()
    name = (d.get('name') or '').strip()
    if not em or not em.endswith('@gmail.com') or em == '@gmail.com':
        return jsonify({'success': False, 'message': 'Enter valid Gmail.'})
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (em,)).fetchone()
    if user:
        if user['status'] == 'disabled':
            return jsonify({'success': False, 'message': 'Account suspended.'})
        session.clear()
        session['user_id'] = user['id']; session['username'] = user['username']; session['role'] = user['role']
        session.permanent = True
        return jsonify({'success': True, 'action': 'login', 'message': f'Welcome back, {user["full_name"]}!'})
    base = re.sub(r'[^a-z0-9_]', '', em.split('@')[0].lower()) or 'user'
    un = base; cnt = 1
    while db.execute("SELECT id FROM users WHERE LOWER(username)=?", (un,)).fetchone():
        un = f"{base}{cnt}"; cnt += 1
    fn = name or base.capitalize()
    try: starting = max(0, int(get_setting('default_starting_coins','50')))
    except Exception: starting = 50
    tp = secrets.token_urlsafe(16)
    cur = db.cursor()
    cur.execute("INSERT INTO users (full_name, username, email, password_hash, coins, role, status) VALUES (?,?,?,?,?,'user','active')",
        (fn, un, em, safe_generate_password_hash(tp), starting))
    uid = cur.lastrowid
    if starting > 0:
        cur.execute("INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?,?,?,'Signup Welcome Bonus','credit')", (uid, starting, starting))
    cur.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, '🎁 Welcome!', ?)", (uid, f'Account created via Gmail. You got {starting} coins!'))
    db.commit()
    session.clear()
    session['user_id'] = uid; session['username'] = un; session['role'] = 'user'
    session.permanent = True
    return jsonify({'success': True, 'action': 'signup', 'message': f'Account created! Welcome {fn}.'})

# ============================================================
# SELF-PING + MONITOR THREADS
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
            conn.commit(); conn.close()
            time.sleep(2)
            for sid, proc in list(RUNNING_PROCESSES.items()):
                if proc.poll() is not None:
                    code = proc.returncode
                    try:
                        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
                        srv = conn.execute("SELECT * FROM servers WHERE id=?", (sid,)).fetchone()
                        if srv:
                            sdir = os.path.join(SERVERS_DIR, str(srv['user_id']), str(sid))
                            logp = os.path.join(sdir, 'server.log')
                            missing = None
                            if os.path.exists(logp):
                                with open(logp, 'r', encoding='utf-8', errors='ignore') as lf:
                                    tail = ''.join(lf.readlines()[-30:])
                                    m = re.search(r"ModuleNotFoundError:\s+No module named\s+'([^']+)'", tail)
                                    if m: missing = m.group(1).split('.')[0]
                            if missing:
                                conn.execute("UPDATE servers SET status='package_required', pid=0 WHERE id=?", (sid,))
                                conn.execute("INSERT INTO server_logs (server_id, level, message) VALUES (?, 'ERROR', ?)",
                                    (sid, f"Missing module: {missing}"))
                            else:
                                ns = 'error' if code != 0 else 'stopped'
                                conn.execute("UPDATE servers SET status=?, pid=0 WHERE id=?", (ns, sid))
                            conn.commit()
                        conn.close()
                    except Exception: pass
                    finally:
                        RUNNING_PROCESSES.pop(sid, None); SERVER_START_TIMES.pop(sid, None)
        except Exception: pass
threading.Thread(target=_monitor, daemon=True).start()

# ============================================================
# SERVER PROCESS + PROJECT SCAN
# ============================================================
STDLIB = {'abc','aifc','argparse','array','ast','asynchat','asyncio','asyncore','atexit','audioop','base64','bdb','binascii','binhex','bisect','builtins','bz2','calendar','cgi','cgitb','chunk','cmath','cmd','code','codecs','codeop','collections','colorsys','compileall','concurrent','configparser','contextlib','contextvars','copy','copyreg','cProfile','crypt','csv','ctypes','curses','dataclasses','datetime','dbm','decimal','difflib','dis','distutils','doctest','email','encodings','enum','errno','faulthandler','fcntl','filecmp','fileinput','fnmatch','fractions','ftplib','functools','gc','getopt','getpass','gettext','glob','graphlib','grp','gzip','hashlib','heapq','hmac','html','http','imaplib','imghdr','imp','importlib','inspect','io','ipaddress','itertools','json','keyword','lib2to3','linecache','locale','logging','lzma','mailbox','mailcap','marshal','math','mimetypes','mmap','modulefinder','msilib','msvcrt','multiprocessing','netrc','nis','nntplib','numbers','operator','optparse','os','ossaudiodev','parser','pathlib','pdb','pickle','pickletools','pipes','pkgutil','platform','plistlib','poplib','posix','posixpath','pprint','profile','pstats','pty','pwd','py_compile','pyclbr','pydoc','queue','quopri','random','re','readline','reprlib','resource','rlcompleter','runpy','sched','secrets','select','selectors','shelve','shlex','shutil','signal','site','smtpd','smtplib','sndhdr','socket','socketserver','spwd','sqlite3','ssl','stat','statistics','string','stringprep','struct','subprocess','sunau','symbol','symtable','sys','sysconfig','syslog','tabnanny','tarfile','telnetlib','tempfile','termios','test','textwrap','threading','time','timeit','tkinter','token','tokenize','tomllib','trace','traceback','tracemalloc','tty','turtle','turtledemo','types','typing','unicodedata','unittest','urllib','uu','uuid','venv','warnings','wave','weakref','webbrowser','winreg','winsound','wsgiref','xdrlib','xml','xmlrpc','zipapp','zipfile','zipimport','zlib','zoneinfo'}

IMAP = {'telebot':'pyTelegramBotAPI','telegram':'python-telegram-bot','aiogram':'aiogram','discord':'discord.py','PIL':'Pillow','bs4':'beautifulsoup4','yaml':'PyYAML','dotenv':'python-dotenv','dateutil':'python-dateutil','cv2':'opencv-python-headless','jwt':'PyJWT','sklearn':'scikit-learn','flask_cors':'flask-cors','fitz':'PyMuPDF','psycopg2':'psycopg2-binary','pymysql':'PyMySQL','sqlalchemy':'SQLAlchemy','pandas':'pandas','numpy':'numpy','requests':'requests','flask':'Flask','fastapi':'fastapi','uvicorn':'uvicorn','colorama':'colorama','aiohttp':'aiohttp','schedule':'schedule','pytz':'pytz','rich':'rich','tqdm':'tqdm','pydantic':'pydantic','cryptography':'cryptography','websockets':'websockets','pymongo':'pymongo','redis':'redis','paramiko':'paramiko','qrcode':'qrcode','gspread':'gspread','pyrogram':'pyrogram','tgcrypto':'tgcrypto','tweepy':'tweepy','matplotlib':'matplotlib','scipy':'scipy','selenium':'selenium','playwright':'playwright','openpyxl':'openpyxl','docx':'python-docx','pypdf':'pypdf','httpx':'httpx','stripe':'stripe','yt_dlp':'yt-dlp'}

def _is_installed(sdir, mod):
    pdir = os.path.join(sdir, 'packages')
    if os.path.exists(pdir):
        key = mod.lower().replace('-','_')
        for it in os.listdir(pdir):
            il = it.lower().replace('-','_')
            if il == key or il.startswith(key+'-') or il.startswith(key+'.'):
                return True
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{sdir}:{pdir}:" + env.get('PYTHONPATH','')
        r = subprocess.run([sys.executable, '-c', f"import {mod}"], cwd=sdir, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.5)
        return r.returncode == 0
    except Exception: return False

def scan_project(sdir):
    if not os.path.exists(sdir):
        return {'ready':True,'entry_file':'main.py','py_files':[],'has_requirements':False,'missing_packages':[],'installed_packages':[],'all_detected_imports':[]}
    py_files = []; local = set()
    for root, dirs, files in os.walk(sdir):
        dirs[:] = [d for d in dirs if d not in ('packages','__pycache__','.venv','.git','venv','node_modules')]
        for f in files:
            if f.endswith('.py'):
                rel = os.path.relpath(os.path.join(root, f), sdir)
                py_files.append(rel); local.add(os.path.splitext(f)[0])
                if f == '__init__.py': local.add(os.path.basename(root))
    entry = 'main.py'
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
    return {'ready':len(missing)==0,'entry_file':entry,'has_entry_file':bool(py_files),
        'py_files':py_files,'has_requirements':has_req,'missing_packages':missing,
        'installed_packages':installed,'all_detected_imports':sorted(imports)}

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
    write_server_log(server_id, 'INFO', 'Server stopped.')
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
        return False, "Server expired. Renew.", [], False
    sdir = get_server_dir(server['user_id'], server_id)
    write_server_log(server_id, 'INFO', 'Checking project...')
    scan = scan_project(sdir)
    entry = server['entry_file'] or scan['entry_file'] or 'main.py'
    if not os.path.exists(os.path.join(sdir, entry)):
        if scan['py_files']:
            entry = scan['py_files'][0]
            db.execute("UPDATE servers SET entry_file=? WHERE id=?", (entry, server_id)); db.commit()
        else:
            write_server_log(server_id, 'ERROR', 'No Python entry file found.')
            return False, "Please upload your project files first.", [], True
    pdir = os.path.join(sdir, 'packages'); os.makedirs(pdir, exist_ok=True)
    req = os.path.join(sdir, 'requirements.txt')
    if os.path.isfile(req):
        write_server_log(server_id, 'INFO', 'Installing requirements.txt...')
        try:
            r = subprocess.run([sys.executable,'-m','pip','install','-r',req,'--target',pdir,'--no-cache-dir','--disable-pip-version-check'],
                cwd=sdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
            for line in (r.stdout or '').splitlines()[-5:]:
                if line.strip(): write_server_log(server_id, 'INFO', f"[pip] {line.strip()}")
        except Exception as e: write_server_log(server_id, 'WARNING', f"pip error: {e}")
        scan = scan_project(sdir)
    if not scan['ready'] and scan['missing_packages']:
        for pkg in scan['missing_packages']:
            spec = pkg['name']
            if pkg['version'] and pkg['version'] != 'latest' and '==' not in spec:
                spec = f"{pkg['name']}=={pkg['version']}"
            write_server_log(server_id, 'INFO', f"Auto-installing {spec}...")
            try:
                subprocess.run([sys.executable,'-m','pip','install',spec,'--target',pdir,'--no-cache-dir','--disable-pip-version-check'],
                    cwd=sdir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            except Exception: pass
        scan = scan_project(sdir)
    if not scan['ready']:
        names = [p['name'] for p in scan['missing_packages']]
        write_server_log(server_id, 'ERROR', f"Missing: {', '.join(names)}")
        db.execute("UPDATE servers SET status='package_required', pid=0 WHERE id=?", (server_id,)); db.commit()
        return False, f"Missing: {', '.join(names)}", scan['missing_packages'], False
    stop_server_process(server_id)
    logp = os.path.join(sdir, 'server.log')
    logf = open(logp, 'a', encoding='utf-8')
    logf.write(f"\n--- Started {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    logf.flush()
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    env['PYTHONPATH'] = f"{sdir}:{pdir}:" + env.get('PYTHONPATH','')
    kwargs = {}
    if hasattr(os, 'setsid'): kwargs['preexec_fn'] = os.setsid
    try:
        proc = subprocess.Popen([sys.executable, entry], cwd=sdir, stdout=logf, stderr=subprocess.STDOUT, env=env, **kwargs)
        RUNNING_PROCESSES[server_id] = proc
        SERVER_START_TIMES[server_id] = time.time()
        db.execute("UPDATE servers SET status='running', pid=? WHERE id=?", (proc.pid, server_id)); db.commit()
        write_server_log(server_id, 'INFO', f"Started (PID {proc.pid}) — {entry}")
        return True, "Server started successfully.", [], False
    except Exception as e:
        write_server_log(server_id, 'ERROR', f"Launch failed: {e}")
        db.execute("UPDATE servers SET status='error', pid=0 WHERE id=?", (server_id,)); db.commit()
        return False, str(e), [], False

# ============================================================
# USER ROUTES
# ============================================================
@app.route('/')
def home():
    db = get_db()
    try:
        db.execute("UPDATE servers SET status='expired' WHERE expires_at < ? AND status != 'expired'",
            (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),))
        db.commit()
    except Exception: pass
    pkgs = db.execute("SELECT * FROM packages WHERE active=1 ORDER BY days ASC").fetchall()
    ts = db.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
    tu = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return render_template("home", packages=pkgs, total_servers=ts, total_users=tu)

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
    can_claim = True
    if user['last_daily_claim']:
        try:
            lc = user['last_daily_claim']
            if isinstance(lc, str): lc = datetime.strptime(lc.split('.')[0], '%Y-%m-%d %H:%M:%S')
            if (datetime.utcnow() - lc).total_seconds() < 86400: can_claim = False
        except Exception: pass
    txs = db.execute("SELECT * FROM coin_transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (user['id'],)).fetchall()
    anns = db.execute("SELECT * FROM announcements WHERE is_active=1 ORDER BY pinned DESC, id DESC LIMIT 5").fetchall()
    return render_template("dashboard", servers=servers, total_files=tf, storage_formatted=storage,
        can_claim_daily=can_claim, recent_transactions=txs, announcements=anns)

@app.route('/coins')
@login_required
def coins():
    user = get_current_user(); db = get_db()
    txs = db.execute("SELECT * FROM coin_transactions WHERE user_id=? ORDER BY created_at DESC", (user['id'],)).fetchall()
    can_claim = True
    now_bd = datetime.utcnow() + timedelta(hours=6)
    if user['last_daily_claim']:
        try:
            lc = user['last_daily_claim']
            if isinstance(lc, str): lc = datetime.strptime(lc.split('.')[0], '%Y-%m-%d %H:%M:%S')
            if now_bd.date() == (lc + timedelta(hours=6)).date(): can_claim = False
        except Exception: pass
    reward = int(get_setting('daily_reward_coins','10'))
    return render_template("coins", transactions=txs, can_claim_daily=can_claim, daily_reward=reward)

@app.route('/api/coins/claim-daily', methods=['POST'])
@login_required
def claim_daily():
    user = get_current_user(); db = get_db()
    now_bd = datetime.utcnow() + timedelta(hours=6)
    if user['last_daily_claim']:
        try:
            lc = user['last_daily_claim']
            if isinstance(lc, str): lc = datetime.strptime(lc.split('.')[0], '%Y-%m-%d %H:%M:%S')
            if now_bd.date() == (lc + timedelta(hours=6)).date():
                return jsonify({'success': False, 'message': 'Already claimed today!'}), 400
        except Exception: pass
    reward = int(get_setting('daily_reward_coins','10'))
    nb = user['coins'] + reward
    db.execute("UPDATE users SET coins=?, last_daily_claim=? WHERE id=?",
        (nb, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), user['id']))
    db.execute("INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?,?,?,?,'credit')",
        (user['id'], reward, nb, f"+{reward} Daily Bonus"))
    db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, 'Daily Bonus', ?)",
        (user['id'], f'You claimed +{reward} coins!'))
    db.commit()
    return jsonify({'success': True, 'message': f'Claimed +{reward} coins!', 'new_balance': nb})

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = get_current_user(); db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'upload_avatar':
            f = request.files.get('avatar')
            if not f or not f.filename:
                flash('No file.', 'warning'); return redirect(url_for('account'))
            ext = f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
            if ext not in {'png','jpg','jpeg','webp','gif','svg'}:
                flash('Invalid format.', 'danger'); return redirect(url_for('account'))
            udir = os.path.join(AVATARS_DIR, f"u_{user['id']}"); os.makedirs(udir, exist_ok=True)
            for old in os.listdir(udir):
                try: os.remove(os.path.join(udir, old))
                except Exception: pass
            fname = f"a_{int(time.time())}.{ext}"
            f.save(os.path.join(udir, fname))
            url = f"/static/avatars/u_{user['id']}/{fname}"
            db.execute("UPDATE users SET avatar_url=? WHERE id=?", (url, user['id'])); db.commit()
            flash('Avatar updated!', 'success'); return redirect(url_for('account'))
        elif action == 'remove_avatar':
            udir = os.path.join(AVATARS_DIR, f"u_{user['id']}")
            if os.path.exists(udir):
                for old in os.listdir(udir):
                    try: os.remove(os.path.join(udir, old))
                    except Exception: pass
            db.execute("UPDATE users SET avatar_url='' WHERE id=?", (user['id'],)); db.commit()
            flash('Avatar removed.', 'info'); return redirect(url_for('account'))
        elif action == 'update_profile':
            fn = request.form.get('full_name','').strip()
            bio = request.form.get('bio','').strip()
            if not fn:
                flash('Name required.', 'danger'); return redirect(url_for('account'))
            db.execute("UPDATE users SET full_name=?, bio=? WHERE id=?", (fn, bio, user['id'])); db.commit()
            flash('Profile updated!', 'success'); return redirect(url_for('account'))
        elif action == 'change_password':
            cur = request.form.get('current_password',''); new = request.form.get('new_password',''); cf = request.form.get('confirm_new_password','')
            if not safe_check_password_hash(user['password_hash'], cur):
                flash('Wrong current password.', 'danger'); return redirect(url_for('account'))
            if len(new) < 6:
                flash('Min 6 chars.', 'danger'); return redirect(url_for('account'))
            if new != cf:
                flash('Passwords do not match.', 'danger'); return redirect(url_for('account'))
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (safe_generate_password_hash(new), user['id'])); db.commit()
            flash('Password changed!', 'success'); return redirect(url_for('account'))
    return render_template("account", user=user)

@app.route('/packages')
@login_required
def packages():
    user = get_current_user(); db = get_db()
    pkgs = db.execute("SELECT * FROM packages WHERE active=1 ORDER BY days ASC").fetchall()
    return render_template("packages", packages=pkgs, user=user)

DEFAULT_MAIN = '''"""HostX VIP Starter"""\nimport time, datetime, os, sys\n\ndef main():\n    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] HostX VIP starting...")\n    print(f"[INFO] Python: {sys.version.split()[0]}")\n    count = 0\n    while True:\n        count += 1\n        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Heartbeat #{count}")\n        time.sleep(10)\n\nif __name__ == '__main__':\n    main()\n'''

@app.route('/servers/create', methods=['GET', 'POST'])
@login_required
def create_server():
    user = get_current_user(); db = get_db()
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        pkg_id = request.form.get('package_id')
        pyv = request.form.get('python_version','Python 3.10')
        if not name:
            flash('Name required.', 'danger'); return redirect(url_for('create_server'))
        pkg = db.execute("SELECT * FROM packages WHERE id=?", (pkg_id,)).fetchone()
        if not pkg:
            flash('Invalid package.', 'danger'); return redirect(url_for('create_server'))
        if pkg['is_first_time_offer'] and user['first_time_offer_used']:
            flash('First Time Offer already used.', 'danger'); return redirect(url_for('create_server'))
        if user['coins'] < pkg['coins']:
            flash(f"Need {pkg['coins']} coins. You have {user['coins']}.", 'danger'); return redirect(url_for('coins'))
        now = datetime.utcnow(); exp = now + timedelta(days=pkg['days'])
        nb = user['coins'] - pkg['coins']
        if pkg['is_first_time_offer']:
            db.execute("UPDATE users SET coins=?, first_time_offer_used=1 WHERE id=?", (nb, user['id']))
        else:
            db.execute("UPDATE users SET coins=? WHERE id=?", (nb, user['id']))
        db.execute("INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?,?,?,?,'debit')",
            (user['id'], -pkg['coins'], nb, f"-{pkg['coins']} coins for {name}"))
        cur = db.cursor()
        cur.execute("INSERT INTO servers (user_id, name, python_version, entry_file, status, created_at, expires_at) VALUES (?,?,?,'main.py','stopped',?,?)",
            (user['id'], name, pyv, now, exp))
        sid = cur.lastrowid
        cur.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, 'Server Created', ?)",
            (user['id'], f"Server '{name}' created!"))
        sdir = get_server_dir(user['id'], sid)
        with open(os.path.join(sdir, 'main.py'), 'w') as f: f.write(DEFAULT_MAIN)
        with open(os.path.join(sdir, 'requirements.txt'), 'w') as f: f.write("requests>=2.31.0\ncolorama>=0.4.6\n")
        write_server_log(sid, 'INFO', f"Server '{name}' created.")
        db.commit()
        flash(f"Server '{name}' created!", 'success')
        return redirect(url_for('server_manage', server_id=sid))
    pkgs = db.execute("SELECT * FROM packages WHERE active=1 ORDER BY days ASC").fetchall()
    sel = request.args.get('pkg', type=int)
    return render_template("create_server", packages=pkgs, user=user, selected_pkg_id=sel)

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
    db = get_db()
    pkgs = db.execute("SELECT * FROM packages WHERE active=1 AND is_first_time_offer=0 ORDER BY days ASC").fetchall()
    return render_template("server_manage", server=server, scan=scan,
        remaining_days=rd, remaining_hours=rh, uptime_display='0m', start_time=st, packages=pkgs)

@app.route('/api/servers/<int:server_id>/action', methods=['POST'])
@login_required
def server_action(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    d = request.get_json() if request.is_json else request.form
    action = d.get('action')
    if action == 'start':
        ok, msg, missing, no_entry = start_server_process(server_id)
        if not ok:
            if no_entry:
                return jsonify({'success': False, 'no_entry_file': True, 'message': msg,
                    'redirect_url': url_for('file_manager', server_id=server_id), 'pid': 0})
            if missing:
                return jsonify({'success': False, 'package_required': True, 'missing_packages': missing,
                    'message': msg, 'status': 'package_required', 'pid': 0})
            return jsonify({'success': False, 'message': msg, 'status': 'stopped', 'pid': 0})
        s = check_ownership(server_id)
        return jsonify({'success': True, 'message': msg, 'status': 'running',
            'pid': s['pid'] if s else 0, 'start_time': SERVER_START_TIMES.get(server_id, time.time())})
    elif action == 'stop':
        stop_server_process(server_id)
        return jsonify({'success': True, 'message': 'Stopped.', 'status': 'stopped', 'pid': 0, 'start_time': 0})
    elif action == 'restart':
        stop_server_process(server_id); time.sleep(0.5)
        ok, msg, missing, no_entry = start_server_process(server_id)
        if not ok:
            if no_entry:
                return jsonify({'success': False, 'no_entry_file': True, 'message': msg,
                    'redirect_url': url_for('file_manager', server_id=server_id), 'pid': 0})
            if missing:
                return jsonify({'success': False, 'package_required': True, 'missing_packages': missing,
                    'message': msg, 'status': 'package_required', 'pid': 0})
            return jsonify({'success': False, 'message': msg, 'status': 'stopped', 'pid': 0})
        s = check_ownership(server_id)
        return jsonify({'success': True, 'message': 'Restarted.', 'status': 'running',
            'pid': s['pid'] if s else 0, 'start_time': SERVER_START_TIMES.get(server_id, time.time())})
    return jsonify({'success': False, 'message': 'Invalid'}), 400

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
    return jsonify({'raw_logs': raw, 'db_logs': db_list, 'status': server['status'],
        'pid': server['pid'] if server['status'] == 'running' else 0, 'start_time': st})

@app.route('/api/servers/<int:server_id>/logs/clear', methods=['POST'])
@login_required
def clear_logs(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'error': 'Not found'}), 404
    sdir = get_server_dir(server['user_id'], server_id)
    logp = os.path.join(sdir, 'server.log')
    try:
        with open(logp, 'w', encoding='utf-8') as f:
            f.write(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Logs cleared.\n")
        db = get_db()
        db.execute("DELETE FROM server_logs WHERE server_id=?", (server_id,)); db.commit()
        return jsonify({'success': True, 'message': 'Logs cleared.'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/renew', methods=['POST'])
@login_required
def renew_server(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    user = get_current_user(); db = get_db()
    d = request.get_json() if request.is_json else request.form
    pkg_id = d.get('package_id')
    pkg = db.execute("SELECT * FROM packages WHERE id=? AND is_first_time_offer=0", (pkg_id,)).fetchone()
    if not pkg: return jsonify({'success': False, 'message': 'Invalid'}), 400
    if user['coins'] < pkg['coins']:
        return jsonify({'success': False, 'message': f"Need {pkg['coins']} coins"}), 400
    exp = server['expires_at']
    if isinstance(exp, str): exp = datetime.strptime(exp.split('.')[0], '%Y-%m-%d %H:%M:%S')
    base = max(datetime.utcnow(), exp)
    ne = base + timedelta(days=pkg['days'])
    nb = user['coins'] - pkg['coins']
    db.execute("UPDATE users SET coins=? WHERE id=?", (nb, user['id']))
    db.execute("UPDATE servers SET expires_at=?, status=CASE WHEN status='expired' THEN 'stopped' ELSE status END WHERE id=?", (ne, server_id))
    db.execute("INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?,?,?,?,'debit')",
        (user['id'], -pkg['coins'], nb, f"-{pkg['coins']} renewal (+{pkg['days']}d)"))
    write_server_log(server_id, 'INFO', f"Renewed +{pkg['days']} days")
    db.commit()
    return jsonify({'success': True, 'message': f"Extended {pkg['days']} days!",
        'new_expiration': ne.strftime('%Y-%m-%d %H:%M:%S'), 'new_coins': nb})

@app.route('/servers/<int:server_id>/files')
@login_required
def file_manager(server_id):
    server = check_ownership(server_id)
    if not server: abort(404)
    db = get_db()
    packages = db.execute("SELECT * FROM packages WHERE active=1 AND is_first_time_offer=0 ORDER BY days ASC").fetchall()
    rp = request.args.get('path', '').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, rp)
    if not is_safe_path(sdir, t) or not os.path.exists(t):
        flash('Invalid path.', 'danger')
        return redirect(url_for('file_manager', server_id=server_id))
    items = []
    try:
        for e in os.scandir(t):
            st = e.stat(); is_dir = e.is_dir(); size = st.st_size
            if size < 1024: sz = f"{size} B"
            elif size < 1024*1024: sz = f"{size/1024:.1f} KB"
            else: sz = f"{size/(1024*1024):.1f} MB"
            items.append({'name': e.name, 'is_dir': is_dir, 'size': sz if not is_dir else '-',
                'modified': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'is_zip': e.name.lower().endswith('.zip'), 'is_py': e.name.lower().endswith('.py'),
                'is_entry': e.name == server['entry_file']})
    except Exception as ex: flash(f'Error: {ex}', 'danger')
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    crumbs = []
    if rp:
        acc = ''
        for p in rp.split('/'):
            acc = f"{acc}/{p}" if acc else p
            crumbs.append({'name': p, 'path': acc})
    return render_template("file_manager", server=server, items=items,
        current_path=rp, breadcrumbs=crumbs, packages=packages)

@app.route('/api/servers/<int:server_id>/files/upload', methods=['POST'])
@login_required
def upload_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    rp = request.form.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    td = os.path.join(sdir, rp)
    if not is_safe_path(sdir, td): return jsonify({'success': False, 'message': 'Bad path'}), 403
    if 'files' not in request.files: return jsonify({'success': False, 'message': 'No files'}), 400
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
                                os.remove(sp); return jsonify({'success': False, 'message': f'Unsafe: {m}'}), 400
                        zf.extractall(td)
                    zips += 1; os.remove(sp)
                except Exception: cnt += 1
            else: cnt += 1
    write_server_log(server_id, 'INFO', f"Uploaded {cnt} file(s), extracted {zips} zip(s).")
    scan = scan_project(sdir)
    db = get_db()
    if scan['entry_file'] and (not server['entry_file'] or server['entry_file'] not in scan['py_files']):
        db.execute("UPDATE servers SET entry_file=? WHERE id=?", (scan['entry_file'], server_id)); db.commit()
    return jsonify({'success': True, 'message': f'Uploaded {cnt} file(s), extracted {zips} zip(s).', 'scan': scan})

@app.route('/api/servers/<int:server_id>/files/create-folder', methods=['POST'])
@login_required
def create_folder(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    path = request.form.get('path','').strip('/')
    name = secure_filename(request.form.get('folder_name','').strip())
    if not name: return jsonify({'success': False, 'message': 'Invalid'}), 400
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path, name)
    if not is_safe_path(sdir, t): return jsonify({'success': False, 'message': 'Bad path'}), 403
    try:
        os.makedirs(t, exist_ok=False)
        return jsonify({'success': True, 'message': f'Folder "{name}" created.'})
    except FileExistsError: return jsonify({'success': False, 'message': 'Exists'}), 400
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/create-file', methods=['POST'])
@login_required
def create_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    path = request.form.get('path','').strip('/')
    name = secure_filename(request.form.get('file_name','').strip())
    if not name: return jsonify({'success': False, 'message': 'Invalid'}), 400
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path, name)
    if not is_safe_path(sdir, t): return jsonify({'success': False, 'message': 'Bad path'}), 403
    try:
        if os.path.exists(t): return jsonify({'success': False, 'message': 'Exists'}), 400
        with open(t, 'w', encoding='utf-8') as f: f.write('')
        return jsonify({'success': True, 'message': f'"{name}" created.'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/read')
@login_required
def read_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    path = request.args.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t) or not os.path.isfile(t):
        return jsonify({'success': False, 'message': 'Not found'}), 404
    try:
        with open(t, 'r', encoding='utf-8', errors='ignore') as f:
            return jsonify({'success': True, 'content': f.read(), 'filename': os.path.basename(t)})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/save', methods=['POST'])
@login_required
def save_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    d = request.get_json() or {}
    path = d.get('path','').strip('/')
    content = d.get('content','')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t): return jsonify({'success': False, 'message': 'Bad path'}), 403
    try:
        with open(t, 'w', encoding='utf-8') as f: f.write(content)
        return jsonify({'success': True, 'message': 'Saved.'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/delete', methods=['POST'])
@login_required
def delete_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    d = request.get_json() or {}
    path = d.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t) or t == sdir:
        return jsonify({'success': False, 'message': 'Bad path'}), 403
    try:
        if os.path.isdir(t): shutil.rmtree(t)
        elif os.path.isfile(t): os.remove(t)
        return jsonify({'success': True, 'message': 'Deleted.'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/rename', methods=['POST'])
@login_required
def rename_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    d = request.get_json() or {}
    old = d.get('old_path','').strip('/')
    new = secure_filename(d.get('new_name','').strip())
    if not new: return jsonify({'success': False, 'message': 'Invalid'}), 400
    sdir = get_server_dir(server['user_id'], server_id)
    src = os.path.join(sdir, old)
    dst = os.path.join(os.path.dirname(src), new)
    if not is_safe_path(sdir, src) or not is_safe_path(sdir, dst):
        return jsonify({'success': False, 'message': 'Bad path'}), 403
    try:
        os.rename(src, dst)
        return jsonify({'success': True, 'message': f'Renamed to {new}'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/files/unzip', methods=['POST'])
@login_required
def unzip_file(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    d = request.get_json() or {}
    zp = d.get('path','').strip('/')
    sdir = get_server_dir(server['user_id'], server_id)
    t = os.path.join(sdir, zp)
    ed = os.path.dirname(t)
    if not is_safe_path(sdir, t) or not os.path.isfile(t):
        return jsonify({'success': False, 'message': 'Zip not found'}), 404
    try:
        with zipfile.ZipFile(t, 'r') as zf:
            for m in zf.namelist():
                mp = os.path.abspath(os.path.join(ed, m))
                if not is_safe_path(sdir, mp):
                    return jsonify({'success': False, 'message': f'Unsafe: {m}'}), 400
            zf.extractall(ed)
        scan = scan_project(sdir)
        return jsonify({'success': True, 'message': 'Extracted!', 'scan': scan})
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

@app.route('/servers/<int:server_id>/startup', methods=['GET', 'POST'])
@login_required
def server_startup(server_id):
    server = check_ownership(server_id)
    if not server: abort(404)
    sdir = get_server_dir(server['user_id'], server_id)
    db = get_db()
    packages = db.execute("SELECT * FROM packages WHERE active=1 AND is_first_time_offer=0 ORDER BY days ASC").fetchall()
    if request.method == 'POST':
        entry = secure_filename(request.form.get('entry_file','main.py').strip())
        pyv = request.form.get('python_version','Python 3.10')
        ar = 1 if request.form.get('auto_restart') == 'on' else 0
        db.execute("UPDATE servers SET entry_file=?, python_version=?, auto_restart=? WHERE id=?", (entry, pyv, ar, server_id))
        db.commit()
        write_server_log(server_id, 'INFO', f"Startup: {entry} / {pyv}")
        flash('Startup saved!', 'success')
        return redirect(url_for('server_startup', server_id=server_id))
    py_files = [f for f in os.listdir(sdir) if f.endswith('.py') and os.path.isfile(os.path.join(sdir, f))] if os.path.exists(sdir) else []
    detected = 'main.py'
    for c in ['main.py','app.py','bot.py','server.py']:
        if c in py_files: detected = c; break
    if not py_files: py_files = ['main.py']
    return render_template("startup", server=server, py_files=py_files, detected_entry=detected,
        system_python=f"Python {sys.version.split()[0]}", packages=packages)

@app.route('/api/servers/<int:server_id>/packages/install', methods=['POST'])
@login_required
def install_package(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    d = request.get_json() if request.is_json else request.form
    pkg = (d.get('package_name') or '').strip()
    ver = (d.get('version') or '').strip()
    if not pkg: return jsonify({'success': False, 'message': 'Name required'}), 400
    sdir = get_server_dir(server['user_id'], server_id)
    pdir = os.path.join(sdir, 'packages'); os.makedirs(pdir, exist_ok=True)
    target = IMAP.get(pkg, pkg)
    spec = f"{target}=={ver}" if ver and ver != 'latest' and '==' not in target else target
    try:
        r = subprocess.run([sys.executable,'-m','pip','install','--target',pdir,spec],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
        out = (r.stdout or '')[-2000:]
        if r.returncode == 0:
            write_server_log(server_id, 'INFO', f"Installed {spec}")
            scan = scan_project(sdir)
            db = get_db()
            if scan['ready']:
                db.execute("UPDATE servers SET status='stopped' WHERE id=? AND status='package_required'", (server_id,))
                db.commit()
            return jsonify({'success': True, 'message': f'{spec} installed.', 'output': out, 'scan': scan})
        return jsonify({'success': False, 'message': 'Install failed', 'output': out}), 400
    except subprocess.TimeoutExpired: return jsonify({'success': False, 'message': 'Timeout'}), 408
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/packages/scan')
@login_required
def scan_packages(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    sdir = get_server_dir(server['user_id'], server_id)
    scan = scan_project(sdir)
    return jsonify({'success': True, 'scan': scan, 'ready': scan['ready'],
        'missing_count': len(scan['missing_packages']), 'installed_count': len(scan['installed_packages'])})

@app.route('/api/servers/<int:server_id>/packages/delete', methods=['POST'])
@login_required
def delete_package(server_id):
    server = check_ownership(server_id)
    if not server: return jsonify({'success': False, 'message': 'Not found'}), 404
    d = request.get_json() or {}
    pkg = (d.get('package_name') or '').strip()
    if not pkg: return jsonify({'success': False, 'message': 'Name required'}), 400
    sdir = get_server_dir(server['user_id'], server_id)
    pdir = os.path.join(sdir, 'packages')
    if not os.path.exists(pdir): return jsonify({'success': True, 'message': 'No packages folder'})
    key = pkg.lower().replace('-','_')
    for item in os.listdir(pdir):
        il = item.lower().replace('-','_')
        if il == key or il.startswith(key+'-') or il.startswith(key+'.'):
            try:
                p = os.path.join(pdir, item)
                if os.path.isdir(p): shutil.rmtree(p)
                else: os.remove(p)
            except Exception: pass
    return jsonify({'success': True, 'message': f'{pkg} removed.', 'scan': scan_project(sdir)})

# ============================================================
# NOTIFICATIONS API
# ============================================================
@app.route('/api/notifications')
@login_required
def get_notifs():
    user = get_current_user(); db = get_db()
    cnt = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=?", (user['id'],)).fetchone()[0]
    if cnt == 0:
        db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)",
            (user['id'], f"Welcome to {get_setting('vip_site_name','HostX VIP')}",
             f"Hi {user['full_name']}! You have {user['coins']} coins."))
        db.commit()
    rows = db.execute("SELECT id, title, message, is_read, created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user['id'],)).fetchall()
    un = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user['id'],)).fetchone()[0]
    return jsonify({'success': True,
        'notifications': [{'id': r['id'], 'title': r['title'], 'message': r['message'], 'is_read': r['is_read'], 'created_at': str(r['created_at'])} for r in rows],
        'unread_count': un})

@app.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_read():
    user = get_current_user(); db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user['id'],)); db.commit()
    return jsonify({'success': True})

@app.route('/api/notifications/clear-all', methods=['POST'])
@login_required
def clear_notifs():
    user = get_current_user(); db = get_db()
    db.execute("DELETE FROM notifications WHERE user_id=?", (user['id'],)); db.commit()
    return jsonify({'success': True, 'unread_count': 0})

@app.route('/api/notifications/<int:nid>/delete', methods=['POST'])
@login_required
def del_notif(nid):
    user = get_current_user(); db = get_db()
    db.execute("DELETE FROM notifications WHERE id=? AND user_id=?", (nid, user['id'])); db.commit()
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
    tc = db.execute("SELECT COALESCE(SUM(coins),0) FROM users").fetchone()[0]
    tf = 0; tb = 0
    if os.path.exists(SERVERS_DIR):
        for root, _, files in os.walk(SERVERS_DIR):
            tf += len(files)
            for f in files:
                try: tb += os.path.getsize(os.path.join(root, f))
                except Exception: pass
    if tb < 1024*1024: st = f"{tb/1024:.1f} KB"
    elif tb < 1024*1024*1024: st = f"{tb/(1024*1024):.1f} MB"
    else: st = f"{tb/(1024*1024*1024):.2f} GB"
    ru = db.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 6").fetchall()
    rl = db.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT 8").fetchall()
    return render_template("admin_dashboard", total_users=tu, total_servers=ts,
        active_users=au, disabled_users=du, running_servers=rs, total_coins=tc,
        total_files=tf, total_storage_formatted=st, recent_users=ru, recent_logs=rl)

@app.route('/admin/users')
@admin_permission_required('manage_users')
def admin_users():
    q = request.args.get('q','').strip()
    db = get_db()
    if q:
        users = db.execute("""SELECT u.*, (SELECT COUNT(*) FROM servers WHERE user_id=u.id) as server_count
            FROM users u WHERE u.email LIKE ? OR u.username LIKE ? OR u.full_name LIKE ? ORDER BY u.id DESC""",
            (f'%{q}%', f'%{q}%', f'%{q}%')).fetchall()
    else:
        users = db.execute("""SELECT u.*, (SELECT COUNT(*) FROM servers WHERE user_id=u.id) as server_count
            FROM users u ORDER BY u.id DESC""").fetchall()
    return render_template("admin_users", users=users, search_query=q)

@app.route('/admin/users/<int:user_id>/update', methods=['POST'])
@admin_permission_required('manage_users')
def admin_update_user(user_id):
    db = get_db()
    ca = get_current_user(); cs = is_user_super_admin(ca)
    t = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not t: flash('Not found.', 'danger'); return redirect(url_for('admin_users'))
    ts = is_user_super_admin(t)
    if ts and not cs:
        flash('Only Super Admin can edit Super Admin.', 'danger'); return redirect(url_for('admin_users'))
    fn = request.form.get('full_name','').strip()
    un = request.form.get('username','').strip().lower()
    em = request.form.get('email','').strip().lower()
    bio = request.form.get('bio','').strip()
    st = request.form.get('status', t['status']).strip().lower()
    ri = request.form.get('role', t['role']).strip().lower()
    cr = request.form.get('coins')
    np_ = request.form.get('new_password','').strip()
    if cs:
        if ri == 'super_admin':
            fr, fi, fs_, fp = 'super_admin', 1, 1, 'all'
        elif ri == 'admin':
            fr, fi, fs_ = 'admin', 1, 0
            perms = request.form.getlist('permissions')
            fp = ','.join(perms) if perms else 'manage_users,manage_coins,manage_files,manage_settings,manage_announcements,manage_broadcasts,view_logs'
        else: fr, fi, fs_, fp = 'user', 0, 0, ''
    else:
        fr, fi, fs_, fp = t['role'], t['is_admin'], t['is_super_admin'], t['admin_permissions']
    if not fn or not un or not em: flash('Name, username, email required.', 'danger'); return redirect(url_for('admin_users'))
    if not em.endswith('@gmail.com') or em == '@gmail.com':
        flash('Only Gmail.', 'danger'); return redirect(url_for('admin_users'))
    if len(un) < 3: flash('Username min 3.', 'danger'); return redirect(url_for('admin_users'))
    ex = db.execute("SELECT id FROM users WHERE LOWER(email)=? AND id!=?", (em, user_id)).fetchone()
    if ex: flash(f"Gmail '{em}' in use.", 'danger'); return redirect(url_for('admin_users'))
    ex = db.execute("SELECT id FROM users WHERE LOWER(username)=? AND id!=?", (un, user_id)).fetchone()
    if ex: flash(f"Username '@{un}' taken.", 'danger'); return redirect(url_for('admin_users'))
    try: coins = max(0, int(cr)) if cr not in (None, '') else t['coins']
    except ValueError: coins = t['coins']
    if coins != t['coins']:
        diff = coins - t['coins']
        title = "🪙 Coins Credited" if diff > 0 else "🪙 Coins Deducted"
        msg = f"Admin adjusted balance ({diff:+d}). New: {coins}"
        db.execute("INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?,?,?,?,?)",
            (user_id, diff, coins, f"Admin edit ({diff:+d})", 'credit' if diff > 0 else 'debit'))
        db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)", (user_id, title, msg))
    if np_:
        if len(np_) < 6: flash('Password min 6.', 'danger'); return redirect(url_for('admin_users'))
        db.execute("""UPDATE users SET full_name=?, username=?, email=?, bio=?, coins=?, status=?, role=?, is_admin=?, is_super_admin=?, admin_permissions=?, password_hash=? WHERE id=?""",
            (fn, un, em, bio, coins, st, fr, fi, fs_, fp, safe_generate_password_hash(np_), user_id))
    else:
        db.execute("""UPDATE users SET full_name=?, username=?, email=?, bio=?, coins=?, status=?, role=?, is_admin=?, is_super_admin=?, admin_permissions=? WHERE id=?""",
            (fn, un, em, bio, coins, st, fr, fi, fs_, fp, user_id))
    db.commit()
    if st == 'disabled' and t['status'] != 'disabled':
        for s in db.execute("SELECT id FROM servers WHERE user_id=?", (user_id,)).fetchall():
            stop_server_process(s['id'])
    log_admin_action('Updated User', f"User #{user_id} (@{un})", f"Coins={coins}, Status={st}, Role={fr}")
    flash(f'User @{un} updated.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_permission_required('manage_users')
def admin_toggle_status(user_id):
    db = get_db()
    ca = get_current_user(); cs = is_user_super_admin(ca)
    t = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not t: flash('Not found.', 'danger'); return redirect(url_for('admin_users'))
    if is_user_admin(t) and not cs:
        flash('Only Super Admin can toggle admins.', 'danger'); return redirect(url_for('admin_users'))
    ns = 'disabled' if t['status'] == 'active' else 'active'
    db.execute("UPDATE users SET status=? WHERE id=?", (ns, user_id)); db.commit()
    if ns == 'disabled':
        for s in db.execute("SELECT id FROM servers WHERE user_id=?", (user_id,)).fetchall():
            stop_server_process(s['id'])
    log_admin_action(f"User → {ns}", f"User #{user_id}", f"@{t['username']}")
    flash(f"@{t['username']} is now {ns}.", 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/impersonate')
@admin_permission_required('manage_users')
def admin_impersonate(user_id):
    db = get_db()
    t = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not t: flash('Not found.', 'danger'); return redirect(url_for('admin_users'))
    log_admin_action('Support Login', f"User #{user_id} (@{t['username']})", 'Impersonation')
    session['real_admin_id'] = session['user_id']
    session['real_admin_username'] = session['username']
    session['is_impersonating'] = True
    session['user_id'] = t['id']; session['username'] = t['username']; session['role'] = t['role']
    flash(f"Viewing as @{t['username']}.", 'info')
    return redirect(url_for('dashboard'))

@app.route('/admin/stop-impersonate')
def stop_impersonating():
    if not session.get('is_impersonating'): return redirect(url_for('dashboard'))
    rid = session.get('real_admin_id')
    db = get_db()
    a = db.execute("SELECT * FROM users WHERE id=?", (rid,)).fetchone()
    if a:
        session.clear()
        session['user_id'] = a['id']; session['username'] = a['username']; session['role'] = a['role']
        flash('Returned to Admin.', 'success')
        return redirect(url_for('admin_users'))
    session.clear()
    return redirect(url_for('signin'))

@app.route('/admin/coins', methods=['GET', 'POST'])
@admin_permission_required('manage_coins')
def admin_coins():
    db = get_db()
    if request.method == 'POST':
        te = (request.form.get('email') or request.form.get('user_identifier') or '').strip().lower()
        ar = request.form.get('amount','0').strip()
        at = request.form.get('action_type','').strip()
        rn = (request.form.get('reason') or 'Admin adjustment').strip()
        try: amt = int(ar)
        except ValueError: amt = 0
        if not te: flash('Email required.', 'danger'); return redirect(url_for('admin_coins'))
        t = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (te,)).fetchone()
        if not t: flash(f"User '{te}' not found.", 'danger'); return redirect(url_for('admin_coins'))
        if amt == 0: flash('Amount cannot be 0.', 'danger'); return redirect(url_for('admin_coins'))
        adj = -abs(amt) if at == 'remove' else (abs(amt) if at == 'add' else amt)
        cb = int(t['coins'] or 0); nb = max(0, cb + adj)
        if adj < 0: desc = f"Admin deduction ({adj}): {rn}"; tx = 'debit'; op = 'deducted'
        else: desc = f"Admin grant (+{adj}): {rn}"; tx = 'credit'; op = 'added'
        db.execute("UPDATE users SET coins=? WHERE id=?", (nb, t['id']))
        db.execute("INSERT INTO coin_transactions (user_id, amount, balance_after, description, transaction_type) VALUES (?,?,?,?,?)",
            (t['id'], adj, nb, desc, tx))
        title = "🪙 Coins Credited" if adj > 0 else "🪙 Coins Deducted"
        db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)",
            (t['id'], title, f"Admin {op} {abs(adj)} coins. {rn}. Balance: {nb}"))
        log_admin_action(f"Coin {op}", f"User #{t['id']} ({t['email']})", f"{adj:+d}, Balance: {nb}")
        db.commit()
        flash(f"{op.capitalize()} {abs(adj)} coins for {t['full_name']}. New: {nb}", 'success')
        return redirect(url_for('admin_coins'))
    rt = db.execute("""SELECT ct.*, u.username, u.email, u.full_name FROM coin_transactions ct
        JOIN users u ON ct.user_id=u.id ORDER BY ct.id DESC LIMIT 25""").fetchall()
    ul = db.execute("SELECT id, full_name, username, email, coins, status FROM users ORDER BY coins DESC LIMIT 30").fetchall()
    tt = db.execute("SELECT COALESCE(SUM(coins),0) FROM users").fetchone()[0]
    return render_template("admin_coins", recent_transactions=rt, users=ul, total_system_coins=tt)

@app.route('/admin/files')
@admin_permission_required('manage_files')
def admin_files():
    q = request.args.get('q','').strip().lower()
    db = get_db()
    try:
        if q:
            servers = db.execute("""SELECT s.*, u.username, u.email, u.full_name FROM servers s
                JOIN users u ON s.user_id=u.id
                WHERE LOWER(s.name) LIKE ? OR LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ? ORDER BY s.id DESC""",
                (f'%{q}%', f'%{q}%', f'%{q}%')).fetchall()
        else:
            servers = db.execute("""SELECT s.*, u.username, u.email, u.full_name FROM servers s
                JOIN users u ON s.user_id=u.id ORDER BY s.id DESC""").fetchall()
        stats = []; tf = 0; tb = 0
        for s in servers:
            sdir = os.path.join(SERVERS_DIR, str(s['user_id']), str(s['id']))
            fc = 0; tsz = 0; fl = []
            if os.path.exists(sdir):
                for root, _, files in os.walk(sdir):
                    fc += len(files)
                    for f in files:
                        try:
                            fp = os.path.join(root, f); sz = os.path.getsize(fp); tsz += sz
                            rel = os.path.relpath(fp, sdir).replace('\\', '/')
                            if sz < 1024: szs = f"{sz} B"
                            elif sz < 1024*1024: szs = f"{sz/1024:.1f} KB"
                            else: szs = f"{sz/(1024*1024):.2f} MB"
                            ext = f.rsplit('.',1)[-1].lower() if '.' in f else ''
                            fl.append({'name': rel, 'filename': f, 'size': sz, 'size_formatted': szs,
                                'modified': datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M'),
                                'ext': ext,
                                'is_text': ext in {'py','txt','json','md','env','sh','csv','yaml','yml','html','css','js','log','ini','cfg','conf'}})
                        except Exception: pass
            tf += fc; tb += tsz
            if tsz < 1024*1024: ssz = f"{tsz/1024:.1f} KB"
            else: ssz = f"{tsz/(1024*1024):.2f} MB"
            fl.sort(key=lambda x: (0 if x['filename']=='main.py' else 1, x['name']))
            stats.append({'server': s, 'file_count': fc, 'storage_mb': ssz, 'files': fl})
        if tb < 1024*1024: tot = f"{tb/1024:.1f} KB"
        elif tb < 1024*1024*1024: tot = f"{tb/(1024*1024):.2f} MB"
        else: tot = f"{tb/(1024*1024*1024):.2f} GB"
        return render_template("admin_files", stats=stats, total_files=tf,
            total_storage_formatted=tot, total_servers=len(servers), query=q)
    except Exception as e:
        flash(f'Error: {e}', 'warning')
        return render_template("admin_files", stats=[], total_files=0,
            total_storage_formatted='0 KB', total_servers=0, query=q)

@app.route('/admin/servers/<int:server_id>/download-zip')
@admin_permission_required('manage_files')
def admin_download_zip(server_id):
    db = get_db()
    s = db.execute("SELECT s.*, u.username FROM servers s JOIN users u ON s.user_id=u.id WHERE s.id=?", (server_id,)).fetchone()
    if not s: flash('Not found.', 'danger'); return redirect(url_for('admin_files'))
    sdir = os.path.join(SERVERS_DIR, str(s['user_id']), str(s['id']))
    if not os.path.exists(sdir): flash('Dir not found.', 'warning'); return redirect(url_for('admin_files'))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(sdir):
            for f in files:
                ap = os.path.join(root, f)
                zf.write(ap, arcname=os.path.relpath(ap, sdir))
    buf.seek(0)
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', s['name'])
    fn = f"server_{server_id}_{clean}_{s['username']}.zip"
    log_admin_action('Download ZIP', f"Server #{server_id}", f"Owner: {s['username']}")
    return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=fn)

@app.route('/admin/servers/<int:server_id>/files/download')
@admin_permission_required('manage_files')
def admin_download_file(server_id):
    db = get_db()
    s = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
    if not s: abort(404)
    path = request.args.get('path','').strip('/')
    sdir = os.path.join(SERVERS_DIR, str(s['user_id']), str(s['id']))
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t) or not os.path.isfile(t): abort(404)
    log_admin_action('Download File', f"Server #{server_id}", f"File: {path}")
    return send_file(t, as_attachment=True)

@app.route('/admin/api/servers/<int:server_id>/files/read')
@admin_permission_required('manage_files')
def admin_read_file(server_id):
    db = get_db()
    s = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
    if not s: return jsonify({'success': False, 'message': 'Not found'}), 404
    path = request.args.get('path','').strip('/')
    sdir = os.path.join(SERVERS_DIR, str(s['user_id']), str(s['id']))
    t = os.path.join(sdir, path)
    if not is_safe_path(sdir, t) or not os.path.isfile(t):
        return jsonify({'success': False, 'message': 'Not found'}), 404
    try:
        sz = os.path.getsize(t)
        if sz > 512 * 1024: return jsonify({'success': False, 'message': 'File too large.'}), 400
        with open(t, 'r', encoding='utf-8', errors='replace') as f: c = f.read()
        return jsonify({'success': True, 'content': c, 'filename': os.path.basename(t),
            'path': path, 'size': sz, 'server_name': s['name']})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/announcements', methods=['GET'])
@admin_permission_required('manage_announcements')
def admin_announcements():
    db = get_db()
    anns = db.execute("SELECT * FROM announcements ORDER BY pinned DESC, id DESC").fetchall()
    return render_template("admin_announcements", announcements=anns)

@app.route('/admin/announcements/create', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_create_ann():
    title = request.form.get('title','').strip()
    content = request.form.get('content','').strip()
    atype = request.form.get('type','update').strip().lower()
    if atype not in ('update','info','warning','maintenance'): atype = 'update'
    active = 1 if request.form.get('is_active') in ('1','true','on') else 0
    pinned = 1 if request.form.get('pinned') in ('1','true','on') else 0
    if not title or not content: flash('Title & content required.', 'danger'); return redirect(url_for('admin_announcements'))
    u = get_current_user(); creator = u['full_name'] if u else 'Administrator'
    db = get_db()
    db.execute("INSERT INTO announcements (title, content, type, is_active, pinned, created_by) VALUES (?,?,?,?,?,?)",
        (title, content, atype, active, pinned, creator))
    db.commit()
    log_admin_action('Created Announcement', f"Notice: {title}", f"Type: {atype}")
    flash('Announcement published!', 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:aid>/toggle', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_toggle_ann(aid):
    db = get_db()
    a = db.execute("SELECT * FROM announcements WHERE id=?", (aid,)).fetchone()
    if not a: flash('Not found.', 'danger'); return redirect(url_for('admin_announcements'))
    new = 0 if a['is_active'] else 1
    db.execute("UPDATE announcements SET is_active=? WHERE id=?", (new, aid)); db.commit()
    flash(f"Announcement #{aid} {'activated' if new else 'deactivated'}.", 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:aid>/toggle-pin', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_toggle_pin(aid):
    db = get_db()
    a = db.execute("SELECT * FROM announcements WHERE id=?", (aid,)).fetchone()
    if not a: flash('Not found.', 'danger'); return redirect(url_for('admin_announcements'))
    new = 0 if a['pinned'] else 1
    db.execute("UPDATE announcements SET pinned=? WHERE id=?", (new, aid)); db.commit()
    flash(f"Announcement #{aid} {'pinned' if new else 'unpinned'}.", 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:aid>/delete', methods=['POST'])
@admin_permission_required('manage_announcements')
def admin_delete_ann(aid):
    db = get_db()
    a = db.execute("SELECT * FROM announcements WHERE id=?", (aid,)).fetchone()
    if not a: flash('Not found.', 'danger'); return redirect(url_for('admin_announcements'))
    db.execute("DELETE FROM announcements WHERE id=?", (aid,)); db.commit()
    log_admin_action('Deleted Announcement', f"Notice #{aid}", a['title'])
    flash('Deleted.', 'info')
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
        cat = request.form.get('category','announcement').strip()
        if not title or not msg: flash('Title & message required.', 'danger'); return redirect(url_for('admin_broadcast'))
        if tt == 'all':
            users = db.execute("SELECT id FROM users WHERE status='active'").fetchall()
            for u in users:
                db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)", (u['id'], title, msg))
            db.execute("""INSERT INTO broadcast_logs (admin_id, admin_username, title, message, category, target_type, recipients_count)
                VALUES (?,?,?,?,?,'all',?)""", (ca['id'], ca['username'], title, msg, cat, len(users)))
            db.commit()
            log_admin_action('Broadcast All', f"{len(users)} users", f"Title: {title}")
            flash(f"Sent to {len(users)} users.", 'success')
            return redirect(url_for('admin_broadcast'))
        elif tt == 'specific':
            try: uid = int(tuid)
            except ValueError: flash('Invalid user.', 'danger'); return redirect(url_for('admin_broadcast'))
            tu = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not tu: flash('Not found.', 'danger'); return redirect(url_for('admin_broadcast'))
            db.execute("INSERT INTO notifications (user_id, title, message) VALUES (?,?,?)", (tu['id'], title, msg))
            db.execute("""INSERT INTO broadcast_logs (admin_id, admin_username, title, message, category, target_type, target_user_id, target_username, recipients_count)
                VALUES (?,?,?,?,?,'specific',?,?,1)""", (ca['id'], ca['username'], title, msg, cat, tu['id'], tu['username']))
            db.commit()
            log_admin_action('Direct Notification', f"User @{tu['username']}", f"Title: {title}")
            flash(f"Sent to @{tu['username']}.", 'success')
            return redirect(url_for('admin_broadcast'))
    users = db.execute("SELECT id, full_name, username, email FROM users WHERE status='active' ORDER BY username ASC").fetchall()
    logs = db.execute("SELECT * FROM broadcast_logs ORDER BY id DESC LIMIT 30").fetchall()
    return render_template("admin_broadcast", users=users, broadcasts=logs)

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_permission_required('manage_settings')
def admin_settings():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action','')
        if action == 'upload_logo':
            f = request.files.get('logo')
            if not f or not f.filename: flash('No file.', 'warning'); return redirect(url_for('admin_settings'))
            ext = f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
            if ext not in {'png','jpg','jpeg','webp','gif','svg','ico'}:
                flash('Invalid format.', 'danger'); return redirect(url_for('admin_settings'))
            for old in os.listdir(BRANDING_DIR):
                try: os.remove(os.path.join(BRANDING_DIR, old))
                except Exception: pass
            fname = f"logo_{int(time.time())}.{ext}"
            f.save(os.path.join(BRANDING_DIR, fname))
            set_setting('site_logo_url', f"/static/branding/{fname}")
            log_admin_action('Uploaded Logo', 'Branding', fname)
            flash('Logo updated!', 'success')
            return redirect(url_for('admin_settings'))
        elif action == 'reset_logo':
            for old in os.listdir(BRANDING_DIR):
                try: os.remove(os.path.join(BRANDING_DIR, old))
                except Exception: pass
            set_setting('site_logo_url', '')
            flash('Logo reset.', 'info')
            return redirect(url_for('admin_settings'))
        elif action == 'update_branding':
            sn = request.form.get('site_name','HostX').strip() or 'HostX'
            vn = request.form.get('vip_site_name','HostX VIP').strip() or 'HostX VIP'
            set_setting('site_name', sn); set_setting('vip_site_name', vn)
            log_admin_action('Updated Branding', 'Settings', f"{sn} / {vn}")
            flash('Branding updated!', 'success')
            return redirect(url_for('admin_settings'))
        elif action in ('update_signup_bonus','update_coin_economy'):
            try: dc = max(0, int(request.form.get('default_starting_coins','50')))
            except ValueError: dc = 50
            try: dr = max(0, int(request.form.get('daily_reward_coins','10')))
            except ValueError: dr = 10
            set_setting('default_starting_coins', str(dc)); set_setting('daily_reward_coins', str(dr))
            log_admin_action('Updated Coin Economy', 'Settings', f"Signup: {dc}, Daily: {dr}")
            flash(f"Signup: {dc}, Daily: {dr}.", 'success')
            return redirect(url_for('admin_settings'))
        elif action == 'update_maintenance':
            mm = '1' if request.form.get('maintenance_mode') in ('1','true','on') else '0'
            msg = request.form.get('maintenance_message','').strip()
            set_setting('maintenance_mode', mm); set_setting('maintenance_message', msg)
            log_admin_action('Updated Maintenance', 'Settings', f"Mode: {mm}")
            flash('Maintenance saved.', 'success')
            return redirect(url_for('admin_settings'))
        elif action == 'update_self_ping':
            en = '1' if request.form.get('self_ping_enabled') in ('1','true','on') else '0'
            try: iv = max(1, int(request.form.get('self_ping_interval','5')))
            except ValueError: iv = 5
            set_setting('self_ping_enabled', en); set_setting('self_ping_interval', str(iv))
            log_admin_action('Updated Self-Ping', 'Settings', f"Enabled: {en}, Interval: {iv}")
            flash('Self-ping saved.', 'success')
            return redirect(url_for('admin_settings'))
    settings = {
        'maintenance_mode': get_setting('maintenance_mode','0'),
        'maintenance_message': get_setting('maintenance_message',''),
        'default_starting_coins': get_setting('default_starting_coins','50'),
        'daily_reward_coins': get_setting('daily_reward_coins','10'),
        'site_name': get_setting('site_name','HostX'),
        'vip_site_name': get_setting('vip_site_name','HostX VIP'),
        'site_logo_url': get_setting('site_logo_url',''),
        'self_ping_enabled': get_setting('self_ping_enabled','1'),
        'self_ping_interval': get_setting('self_ping_interval','5'),
    }
    pkgs = db.execute("SELECT * FROM packages ORDER BY id ASC").fetchall()
    return render_template("admin_settings", settings=settings, packages=pkgs)

@app.route('/admin/packages/update', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_update_pkg():
    db = get_db()
    pid = request.form.get('id')
    name = request.form.get('name','').strip() or 'Package'
    try: days = max(1, int(request.form.get('days',1)))
    except ValueError: days = 1
    try: coins = max(0, int(request.form.get('coins',0)))
    except ValueError: coins = 0
    desc = request.form.get('description','').strip() or f"{days} Days"
    fto = 1 if request.form.get('is_first_time_offer') in ('1','true','on') else 0
    act = 1 if request.form.get('active') in ('1','true','on') else 0
    db.execute("UPDATE packages SET name=?, days=?, coins=?, description=?, is_first_time_offer=?, active=? WHERE id=?",
        (name, days, coins, desc, fto, act, pid))
    db.commit()
    log_admin_action('Updated Package', f"Package #{pid}", f"{name}: {days}d/{coins}c")
    flash('Package updated!', 'success')
    return redirect(url_for('admin_settings'))

@app.route('/admin/packages/create', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_create_pkg():
    db = get_db()
    name = request.form.get('name','').strip() or 'New Package'
    try: days = max(1, int(request.form.get('days',1)))
    except ValueError: days = 1
    try: coins = max(0, int(request.form.get('coins',0)))
    except ValueError: coins = 0
    desc = request.form.get('description','').strip() or f"{days} Days"
    fto = 1 if request.form.get('is_first_time_offer') in ('1','true','on') else 0
    act = 1 if request.form.get('active') in ('1','true','on') else 0
    db.execute("INSERT INTO packages (name, days, coins, description, is_first_time_offer, active) VALUES (?,?,?,?,?,?)",
        (name, days, coins, desc, fto, act))
    db.commit()
    log_admin_action('Created Package', name, f"{days}d/{coins}c")
    flash(f"Package '{name}' created!", 'success')
    return redirect(url_for('admin_settings'))

@app.route('/admin/packages/<int:pid>/delete', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_delete_pkg(pid):
    db = get_db()
    p = db.execute("SELECT * FROM packages WHERE id=?", (pid,)).fetchone()
    if p:
        db.execute("DELETE FROM packages WHERE id=?", (pid,)); db.commit()
        log_admin_action('Deleted Package', f"Package #{pid}", p['name'])
        flash(f"Package '{p['name']}' deleted.", 'info')
    return redirect(url_for('admin_settings'))

@app.route('/admin/packages/reset', methods=['POST'])
@admin_permission_required('manage_settings')
def admin_reset_pkgs():
    db = get_db()
    db.execute("DELETE FROM packages")
    default = [('First Time Offer',5,10,1,'Exclusive 5-day trial for new users',1),
        ('Standard 7 Days',7,20,0,'1-week hosting for testing',1),
        ('Standard 15 Days',15,30,0,'2-week continuous hosting',1),
        ('Standard 30 Days',30,60,0,'Full month hosting',1),
        ('Standard 60 Days',60,100,0,'2 months with discount',1),
        ('Standard 90 Days',90,150,0,'Quarterly hosting',1)]
    db.executemany("INSERT INTO packages (name, days, coins, is_first_time_offer, description, active) VALUES (?,?,?,?,?,?)", default)
    db.commit()
    log_admin_action('Reset Packages', 'Packages', '6 default tiers')
    flash('Packages reset.', 'info')
    return redirect(url_for('admin_settings'))

@app.route('/admin/logs')
@admin_permission_required('view_logs')
def admin_logs():
    db = get_db()
    logs = db.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT 100").fetchall()
    return render_template("admin_logs", logs=logs)

# ============================================================
# TEMPLATES (inline)
# ============================================================
BASE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{% block title %}{{ vip_site_name }}{% endblock %}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
{% if site_logo_url %}<link rel="icon" href="{{ site_logo_url }}">{% endif %}
</head>
<body>
<div id="loader" class="loader-screen"><div class="loader-box"><div class="loader-spinner"></div><div class="loader-title">{{ site_name }}</div></div></div>
{% if is_impersonating %}<div class="impersonate-banner"><span>🛡️ Support Mode: <b>{{ current_user.username }}</b></span><a href="{{ url_for('stop_impersonating') }}" class="btn-xs">Return to Admin</a></div>{% endif %}
<header class="topnav">
  <div class="wrap topnav-inner">
    <a href="{{ url_for('dashboard') if current_user else url_for('home') }}" class="brand">
      <div class="brand-icon">{% if site_logo_url %}<img src="{{ site_logo_url }}" alt="" onerror="this.style.display='none';this.parentNode.textContent='⚡';">{% else %}⚡{% endif %}</div>
      <span>{{ site_name }}</span>
    </a>
    <nav class="desktop-nav">
      {% if current_user %}
        <a href="{{ url_for('dashboard') }}" class="dlink">Dashboard</a>
        <a href="{{ url_for('packages') }}" class="dlink">Packages</a>
        <a href="{{ url_for('coins') }}" class="dlink">Coins</a>
        <a href="{{ url_for('account') }}" class="dlink">Account</a>
        {% if is_admin %}<a href="{{ url_for('admin_dashboard') }}" class="dlink admin-link">👑 Admin</a>{% endif %}
      {% else %}
        <a href="{{ url_for('home') }}" class="dlink">Home</a>
        <a href="{{ url_for('signin') }}" class="dlink">Sign In</a>
      {% endif %}
    </nav>
    <div class="header-actions">
      {% if current_user %}
        <a href="{{ url_for('coins') }}" class="coin-pill"><span>🪙</span><b>{{ current_user.coins }}</b></a>
        <div class="dd-wrap">
          <button class="dd-trigger bell-btn" onclick="toggleDropdown(event, this)">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            <span id="notif-badge" class="nbadge" style="display:none;">0</span>
          </button>
          <div class="dd-popover notif-pop">
            <div class="notif-head"><span>🔔 Notifications</span><button onclick="clearAllNotifs(event)" class="link-btn">Clear All</button></div>
            <div id="notif-list" class="notif-body"><div class="empty-mini">Loading...</div></div>
          </div>
        </div>
        <div class="dd-wrap">
          <button class="dd-trigger avatar-btn" onclick="toggleDropdown(event, this)">
            {% if current_user.avatar_url %}<img src="{{ current_user.avatar_url }}" alt="">{% else %}{{ (current_user.full_name or current_user.username)[0]|upper }}{% endif %}
          </button>
          <div class="dd-popover">
            <div class="user-mini"><div class="avatar-mini">{% if current_user.avatar_url %}<img src="{{ current_user.avatar_url }}" alt="">{% else %}{{ (current_user.full_name or current_user.username)[0]|upper }}{% endif %}</div><div class="um-info"><b>{{ current_user.full_name }}</b><span>@{{ current_user.username }}</span></div></div>
            <a href="{{ url_for('dashboard') }}" class="dd-item">📊 Dashboard</a>
            <a href="{{ url_for('account') }}" class="dd-item">⚙️ Account</a>
            <a href="{{ url_for('coins') }}" class="dd-item">🪙 Coins</a>
            {% if is_admin %}<a href="{{ url_for('admin_dashboard') }}" class="dd-item admin-link">👑 Admin Console</a>{% endif %}
            <div class="dd-divider"></div>
            <a href="{{ url_for('signout') }}" class="dd-item danger">🚪 Sign Out</a>
          </div>
        </div>
      {% else %}
        <a href="{{ url_for('signin') }}" class="btn-primary btn-sm">Sign In</a>
      {% endif %}
    </div>
  </div>
</header>
{% with msgs = get_flashed_messages(with_categories=true) %}{% if msgs %}
<div class="wrap" style="margin-top:8px;">{% for cat, msg in msgs %}
<div class="flash flash-{{ cat }}"><span>{% if cat=='success' %}✓{% elif cat=='danger' %}✕{% elif cat=='warning' %}⚠{% else %}ℹ{% endif %}</span><span>{{ msg }}</span><button onclick="this.parentElement.remove()" class="flash-x">&times;</button></div>
{% endfor %}</div>{% endif %}{% endwith %}
<main>{% block content %}{% endblock %}</main>
{% if current_user and request.endpoint not in ['server_manage','file_manager','server_startup'] %}
<nav class="bottomnav">
  {% if request.endpoint and 'admin' in request.endpoint %}
    <a href="{{ url_for('admin_dashboard') }}" class="bn-item"><span>👑</span>Overview</a>
    <a href="{{ url_for('admin_users') }}" class="bn-item"><span>👥</span>Users</a>
    <a href="{{ url_for('admin_coins') }}" class="bn-item"><span>🪙</span>Coins</a>
    <a href="{{ url_for('admin_files') }}" class="bn-item"><span>📁</span>Files</a>
    <a href="{{ url_for('admin_settings') }}" class="bn-item"><span>⚙️</span>Settings</a>
  {% else %}
    <a href="{{ url_for('dashboard') }}" class="bn-item"><span>⚡</span>Home</a>
    <a href="{{ url_for('packages') }}" class="bn-item"><span>🖥️</span>Servers</a>
    <a href="{{ url_for('coins') }}" class="bn-item"><span>🪙</span>Coins</a>
    <a href="{{ url_for('account') }}" class="bn-item"><span>👤</span>Account</a>
  {% endif %}
</nav>
{% endif %}
<div id="toasts"></div>
<script src="/script.js"></script>
{% block scripts %}{% endblock %}
</body>
</html>"""

SIGNIN_HTML = """{% extends "base" %}{% block title %}Sign In{% endblock %}{% block content %}
<div class="wrap auth-wrap"><div class="auth-card">
<div class="auth-head"><div class="auth-logo">{% if site_logo_url %}<img src="{{ site_logo_url }}" alt="">{% else %}⚡{% endif %}</div><h1>Welcome Back 👋</h1><p>Sign in to continue</p></div>
<button type="button" onclick="openGmailModal()" class="btn-google"><svg width="20" height="20" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.1-11.3-7.9l-6.5 5C9.6 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.5l6.2 5.2C36.8 39.2 44 34 44 24c0-1.3-.1-2.3-.4-3.5z"/></svg><span>Continue with Google</span></button>
<div class="auth-divider"><span>or sign in with email</span></div>
<form method="POST" action="{{ url_for('signin') }}">
<div class="field"><label>Email or Username</label><input type="text" name="email" value="{{ email or '' }}" placeholder="you@gmail.com" required></div>
<div class="field"><label>Password</label><div class="pass-wrap"><input type="password" name="password" id="signin-pass" placeholder="••••••••" required><button type="button" class="pass-toggle" onclick="togglePass('signin-pass', this)">👁️</button></div></div>
<div class="auth-row"><label class="check"><input type="checkbox" name="remember" checked><span>Remember me</span></label><a href="javascript:void(0)" onclick="openForgotModal()" class="link-sm">Forgot password?</a></div>
<button type="submit" class="btn-primary btn-block btn-lg">Sign In</button></form>
<div class="auth-foot">Don't have an account? <a href="{{ url_for('signup') }}">Create one</a></div>
</div></div>
<div id="gmail-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:400px;"><button class="modal-x" onclick="closeGmailModal()">&times;</button>
<div style="text-align:center;margin-bottom:18px;"><h2 style="font-size:1.25rem;font-weight:800;margin:0;">Sign in with Google</h2><p style="font-size:0.825rem;color:var(--muted);">Enter your Gmail to continue</p></div>
<div class="field"><label>Gmail Address</label><input type="email" id="gmail-quick-email" placeholder="you@gmail.com"><div id="gmail-quick-err" class="inline-err" style="display:none;"></div></div>
<div class="field"><label>Full Name (for new accounts)</label><input type="text" id="gmail-quick-name" placeholder="John Doe"></div>
<button type="button" onclick="submitGmailQuick()" class="btn-primary btn-block">Continue</button>
</div></div>
<div id="forgot-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:420px;"><button class="modal-x" onclick="closeForgotModal()">&times;</button>
<h2 style="font-size:1.2rem;font-weight:800;margin:0 0 4px;">Reset Password</h2><p style="font-size:0.8rem;color:var(--muted);margin:0 0 18px;">Verify in 3 steps.</p>
<div class="step-badges"><div class="stepb" id="sb1"><span>1</span>Challenge</div><div class="stepb" id="sb2"><span>2</span>Email</div><div class="stepb" id="sb3"><span>3</span>Password</div></div>
<div id="fp-step1"><div class="captcha-box" id="fp-captcha">Loading...</div><div class="field"><label>Your Answer</label><input type="number" id="fp-captcha-answer"><div id="fp-cap-err" class="inline-err" style="display:none;"></div></div><button type="button" onclick="fpSubmitCaptcha()" class="btn-primary btn-block">Verify →</button></div>
<div id="fp-step2" style="display:none;"><div class="field"><label>Registered Gmail</label><input type="email" id="fp-email"><div id="fp-email-err" class="inline-err" style="display:none;"></div></div><button type="button" onclick="fpSubmitEmail()" class="btn-primary btn-block">Verify Email →</button></div>
<div id="fp-step3" style="display:none;"><div class="field"><label>New Password</label><input type="password" id="fp-new-pass"></div><div class="field"><label>Confirm</label><input type="password" id="fp-conf-pass"><div id="fp-pw-err" class="inline-err" style="display:none;"></div></div><button type="button" onclick="fpSubmitReset()" class="btn-success btn-block">Change Password ✓</button></div>
</div></div>
{% endblock %}"""

SIGNUP_HTML = """{% extends "base" %}{% block title %}Sign Up{% endblock %}{% block content %}
<div class="wrap auth-wrap"><div class="auth-card">
<div class="auth-head"><div class="auth-logo">{% if site_logo_url %}<img src="{{ site_logo_url }}" alt="">{% else %}⚡{% endif %}</div><h1>Create Account</h1><p>Join and get free coins</p></div>
<button type="button" onclick="openGmailModal()" class="btn-google"><svg width="20" height="20" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.1-11.3-7.9l-6.5 5C9.6 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.5l6.2 5.2C36.8 39.2 44 34 44 24c0-1.3-.1-2.3-.4-3.5z"/></svg><span>Sign up with Google</span></button>
<div class="auth-divider"><span>or sign up with email</span></div>
<form method="POST" action="{{ url_for('signup') }}">
<div class="field"><label>Full Name</label><input type="text" name="full_name" value="{{ full_name or '' }}" required></div>
<div class="field"><label>Username</label><input type="text" name="username" value="{{ username or '' }}" required minlength="3"></div>
<div class="field"><label>Gmail Address</label><input type="email" name="email" value="{{ email or '' }}" required><small>Only @gmail.com</small></div>
<div class="field"><label>Password</label><div class="pass-wrap"><input type="password" name="password" id="su-pass" required minlength="6"><button type="button" class="pass-toggle" onclick="togglePass('su-pass', this)">👁️</button></div></div>
<div class="field"><label>Confirm Password</label><div class="pass-wrap"><input type="password" name="confirm_password" id="su-cpass" required minlength="6"><button type="button" class="pass-toggle" onclick="togglePass('su-cpass', this)">👁️</button></div></div>
<button type="submit" class="btn-primary btn-block btn-lg">Create Account</button></form>
<div class="auth-foot">Already have an account? <a href="{{ url_for('signin') }}">Sign in</a></div>
</div></div>
<div id="gmail-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:400px;"><button class="modal-x" onclick="closeGmailModal()">&times;</button>
<h2 style="font-size:1.25rem;font-weight:800;margin:0 0 6px;text-align:center;">Sign up with Google</h2>
<div class="field"><label>Gmail Address</label><input type="email" id="gmail-quick-email"><div id="gmail-quick-err" class="inline-err" style="display:none;"></div></div>
<div class="field"><label>Full Name</label><input type="text" id="gmail-quick-name"></div>
<button type="button" onclick="submitGmailQuick()" class="btn-primary btn-block">Continue</button></div></div>
{% endblock %}"""

HOME_HTML = """{% extends "base" %}{% block title %}{{ vip_site_name }}{% endblock %}{% block content %}
<div class="wrap">
<section class="hero-card">
<div class="hero-badge">🚀 PYTHON HOSTING PLATFORM</div>
<div class="hero-logo">{% if site_logo_url %}<img src="{{ site_logo_url }}" alt="">{% else %}⚡{% endif %}</div>
<h1 class="hero-title">{{ vip_site_name }}</h1>
<p class="hero-sub">Fast • Secure • 24/7 Uptime</p>
<p class="hero-desc">Deploy Python bots, APIs, scrapers. Real-time logs, file manager, auto-package installer.</p>
<div class="hero-actions">{% if current_user %}<a href="{{ url_for('dashboard') }}" class="btn-primary btn-lg">⚡ Enter Dashboard</a><a href="{{ url_for('create_server') }}" class="btn-secondary btn-lg">+ Create Server</a>{% else %}<a href="{{ url_for('signup') }}" class="btn-primary btn-lg">Create Free Account →</a><a href="{{ url_for('signin') }}" class="btn-secondary btn-lg">Sign In</a>{% endif %}</div>
<div class="hero-stats"><div>🟢 99.9% Uptime</div><div>⚡ Python 3.8–3.12</div><div>🪙 Daily Coin Rewards</div></div>
</section>
<section id="pricing" class="section"><div class="section-head"><h2 class="section-title">Hosting Packages</h2><p class="section-desc">Coin-based pricing. No credit card required.</p></div>
<div class="grid grid-3">{% for pkg in packages %}
<div class="pkg-card {% if pkg.is_first_time_offer %}pkg-featured{% endif %}">{% if pkg.is_first_time_offer %}<div class="pkg-ribbon">★ FIRST TIME OFFER</div>{% endif %}
<h3>{{ pkg.name }}</h3><p class="pkg-desc">{{ pkg.description }}</p>
<div class="pkg-price"><span class="pkg-coin">{{ pkg.coins }}</span><span class="pkg-unit">Coins</span><span class="pkg-days">/ {{ pkg.days }} Days</span></div>
<ul class="pkg-list"><li>✓ {{ pkg.days }} Days Runtime</li><li>✓ Live Logs</li><li>✓ File Manager</li><li>✓ Unlimited Restarts</li></ul>
{% if current_user %}<a href="{{ url_for('create_server', pkg=pkg.id) }}" class="btn-primary btn-block">Deploy with {{ pkg.coins }} Coins</a>{% else %}<a href="{{ url_for('signup') }}" class="btn-primary btn-block">Get Started</a>{% endif %}
</div>{% endfor %}</div></section>
<section class="cta-card"><h2>Ready to host your Python bot?</h2><p>Register now and get instant welcome coins.</p>{% if not current_user %}<a href="{{ url_for('signup') }}" class="btn-primary btn-lg">Create Free Account →</a>{% else %}<a href="{{ url_for('create_server') }}" class="btn-primary btn-lg">Launch Server →</a>{% endif %}</section>
</div>
{% endblock %}"""

DASHBOARD_HTML = """{% extends "base" %}{% block title %}Dashboard{% endblock %}{% block content %}
<div class="wrap">
<div class="welcome-card"><div class="welcome-avatar">{% if current_user.avatar_url %}<img src="{{ current_user.avatar_url }}" alt="">{% else %}{{ (current_user.full_name or current_user.username)[0]|upper }}{% endif %}</div>
<div><div class="welcome-hi">Welcome back,</div><h1 class="welcome-name">{{ current_user.full_name }}</h1><div class="status-live"><span class="dot-live"></span> Active Account</div></div></div>
{% if announcements %}<div class="ann-stack">{% for a in announcements %}
<div class="ann-card ann-{{ a.type }} {% if a.pinned %}ann-pinned{% endif %}">
<div class="ann-head"><div class="ann-badges">{% if a.pinned %}<span class="badge badge-warn">📌 PINNED</span>{% endif %}<strong>{{ a.title }}</strong></div><span class="ann-date">{{ a.created_at|format_date }}</span></div>
<p class="ann-body">{{ a.content }}</p></div>{% endfor %}</div>{% endif %}
<div class="stats-grid">
<div class="stat-card"><div class="stat-label">Total Servers</div><div class="stat-value">{{ servers|length }}</div><div class="stat-hint hint-green">⚡ Ready</div></div>
<div class="stat-card"><div class="stat-label">Total Files</div><div class="stat-value">{{ total_files }}</div><div class="stat-hint hint-blue">📁 {{ storage_formatted }}</div></div>
<div class="stat-card"><div class="stat-label">Platform</div><div class="stat-value">100%</div><div class="stat-hint hint-gray">🟢 Active</div></div>
<div class="stat-card"><div class="stat-label">Daily Reward</div><div class="stat-value">+10</div><div class="stat-hint hint-amber">🪙 per 24h</div></div>
</div>
<div class="section-head-row"><div><h2 class="section-title" style="margin:0;">My Python Servers</h2><p class="section-desc">Manage your hosted bots.</p></div><a href="{{ url_for('create_server') }}" class="btn-primary">+ Create New Server</a></div>
{% if servers %}<div class="grid grid-2">{% for s in servers %}
<div class="server-card server-{{ s.status }}">
<div class="server-top"><div class="server-id"><div class="server-icon">🐍</div><div><h3>{{ s.name }}</h3><span class="server-py">{{ s.python_version }}</span></div></div>
{% if s.status == 'running' %}<span class="status status-running"><span class="dot"></span> Running</span>{% elif s.status == 'expired' %}<span class="status status-expired"><span class="dot"></span> Expired</span>{% else %}<span class="status status-stopped"><span class="dot"></span> Stopped</span>{% endif %}
</div>
<div class="server-info"><div><span>Entry:</span><b>{{ s.entry_file }}</b></div><div><span>Created:</span><span>{{ s.created_at|format_date }}</span></div><div><span>Expires:</span><b>{{ s.expires_at|format_date }}</b></div></div>
<a href="{{ url_for('server_manage', server_id=s.id) }}" class="btn-primary btn-block">⚙️ Manage Server</a>
</div>{% endfor %}</div>
{% else %}<div class="empty-card"><div style="font-size:3rem;">🚀</div><h3>No Python Servers Yet</h3><p>You have <b>{{ current_user.coins }}</b> coins. Launch your first project!</p><a href="{{ url_for('create_server') }}" class="btn-primary">+ Create Your First Server</a></div>{% endif %}
</div>
{% endblock %}"""

COINS_HTML = """{% extends "base" %}{% block title %}Coins{% endblock %}{% block content %}
<div class="wrap">
<div class="coin-hero"><div class="coin-hero-left"><div class="coin-hero-icon">🪙</div><div><span class="coin-hero-label">Coin Economy</span><h1><span id="coin-bal">{{ current_user.coins }}</span> Coins</h1><p>Earn daily rewards and deploy servers.</p></div></div>
<div>{% if can_claim_daily %}<button id="claim-btn" onclick="claimDaily()" class="btn-gold btn-lg">🎁 Claim +{{ daily_reward }} Coins</button>{% else %}<div class="claim-disabled">Next claim at 12:00 AM</div>{% endif %}</div></div>
<div class="info-card"><h3>💡 How Coins Work</h3><div class="grid grid-3"><div class="info-item"><b>1. Daily Rewards</b><span>Claim +{{ daily_reward }} every 24h.</span></div><div class="info-item"><b>2. Deploy Servers</b><span>Run 24/7 Python bots.</span></div><div class="info-item"><b>3. Extend Anytime</b><span>Add days to any server.</span></div></div></div>
<div class="card"><h2 style="margin-bottom:16px;">Transaction History</h2>
{% if transactions %}<div class="tx-list">{% for tx in transactions %}
<div class="tx-item"><div class="tx-left"><div class="tx-icon tx-{{ 'in' if tx.amount > 0 else 'out' }}">{{ '📥' if tx.amount > 0 else '📤' }}</div><div><div class="tx-desc">{{ tx.description }}</div><div class="tx-time">{{ tx.created_at|format_datetime }}</div></div></div>
<div class="tx-right"><div class="tx-amt {% if tx.amount > 0 %}amt-in{% else %}amt-out{% endif %}">{% if tx.amount > 0 %}+{{ tx.amount }}{% else %}{{ tx.amount }}{% endif %}</div><div class="tx-bal">Bal: {{ tx.balance_after }}</div></div>
</div>{% endfor %}</div>{% else %}<div class="empty-mini">No transactions yet.</div>{% endif %}</div>
</div>
{% endblock %}"""

ACCOUNT_HTML = """{% extends "base" %}{% block title %}Account{% endblock %}{% block content %}
<div class="wrap" style="max-width:680px;">
<div class="card"><div class="acc-head"><div class="acc-avatar-wrap"><label for="quick_avatar" style="cursor:pointer;"><div class="acc-avatar">{% if user.avatar_url %}<img src="{{ user.avatar_url }}" alt="">{% else %}{{ (user.full_name or user.username)[0]|upper }}{% endif %}</div><div class="acc-cam">📷</div></label>
<form id="quick_avatar_form" action="{{ url_for('account') }}" method="POST" enctype="multipart/form-data" style="display:none;"><input type="hidden" name="action" value="upload_avatar"><input type="file" id="quick_avatar" name="avatar" accept="image/*" onchange="document.getElementById('quick_avatar_form').submit();"></form></div>
<div class="acc-info"><h1>{{ user.full_name }}</h1><span class="status-pill">● {{ user.status|capitalize }}</span></div></div>
<div class="acc-grid"><div><span>Registered:</span><b>{{ user.created_at|format_date }}</b></div><div><span>Coins:</span><b class="gold-text">🪙 {{ user.coins }}</b></div><div><span>Role:</span><b class="primary-text">{{ user.role|capitalize }}</b></div></div></div>
<div class="card"><h2 style="margin-bottom:6px;">Profile Picture</h2><p class="muted">Upload a custom avatar.</p>
<div class="upload-box"><div class="up-preview">{% if user.avatar_url %}<img id="av-preview-img" src="{{ user.avatar_url }}" alt="">{% else %}<span id="av-preview-letter">{{ (user.full_name or user.username)[0]|upper }}</span><img id="av-preview-img" src="" style="display:none;" alt="">{% endif %}</div>
<div class="up-actions"><form action="{{ url_for('account') }}" method="POST" enctype="multipart/form-data" style="display:flex;gap:8px;flex-wrap:wrap;"><input type="hidden" name="action" value="upload_avatar"><label class="btn-secondary">📁 Choose<input type="file" name="avatar" accept="image/*" style="display:none;" onchange="previewAvatar(this)"></label><button type="submit" class="btn-primary">⬆️ Upload</button></form></div></div>
{% if user.avatar_url %}<form action="{{ url_for('account') }}" method="POST" onsubmit="return confirm('Remove?');" style="margin-top:12px;"><input type="hidden" name="action" value="remove_avatar"><button type="submit" class="btn-danger-outline">🗑️ Remove</button></form>{% endif %}</div>
<div class="card"><h2>Edit Profile</h2><form action="{{ url_for('account') }}" method="POST"><input type="hidden" name="action" value="update_profile">
<div class="field"><label>Full Name</label><input type="text" name="full_name" value="{{ user.full_name }}" required></div>
<div class="field"><label>Username</label><input type="text" value="{{ user.username }}" readonly class="readonly"></div>
<div class="field"><label>Gmail</label><input type="email" value="{{ user.email }}" readonly class="readonly"></div>
<div class="field"><label>Bio</label><input type="text" name="bio" value="{{ user.bio or '' }}"></div>
<button type="submit" class="btn-primary">Save Changes</button></form></div>
<div class="card"><h2>Change Password</h2><form action="{{ url_for('account') }}" method="POST"><input type="hidden" name="action" value="change_password">
<div class="field"><label>Current Password</label><input type="password" name="current_password" required></div>
<div class="field"><label>New Password</label><input type="password" name="new_password" required minlength="6"></div>
<div class="field"><label>Confirm</label><input type="password" name="confirm_new_password" required minlength="6"></div>
<button type="submit" class="btn-primary">Update Password</button></form></div>
</div>
{% endblock %}"""

PACKAGES_HTML = """{% extends "base" %}{% block title %}Packages{% endblock %}{% block content %}
<div class="wrap">
<div class="card" style="text-align:center;padding:28px;"><span class="badge badge-primary">HOSTING PLANS</span><h1 style="margin:8px 0 4px;">Python Server Packages</h1><p class="muted">Choose duration for your hosting needs.</p><div class="coin-pill" style="margin-top:8px;">Your Coins: <b>{{ user.coins }}</b></div></div>
<div class="grid grid-3" style="margin-top:20px;">{% for pkg in packages %}
<div class="pkg-card {% if pkg.is_first_time_offer %}pkg-featured{% endif %}">{% if pkg.is_first_time_offer %}<div class="pkg-ribbon">★ FIRST TIME OFFER</div>{% endif %}
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;"><h3>{{ pkg.name }}</h3><span style="font-size:1.25rem;">🐍</span></div>
<p class="pkg-desc">{{ pkg.description }}</p>
<div class="pkg-price-block"><span class="pkg-coin">{{ pkg.coins }}</span><span class="pkg-unit">Coins</span><span class="pkg-days">/ {{ pkg.days }} Days</span></div>
<ul class="pkg-list"><li>✓ {{ pkg.days }} Days Uptime</li><li>✓ Auto entry</li><li>✓ Live logs</li><li>✓ File manager</li></ul>
{% if pkg.is_first_time_offer and user.first_time_offer_used %}<button class="btn-secondary btn-block" disabled>Already Claimed</button>
{% elif user.coins < pkg.coins %}<a href="{{ url_for('coins') }}" class="btn-secondary btn-block gold-border">Need {{ pkg.coins - user.coins }} More</a>
{% else %}<a href="{{ url_for('create_server', pkg=pkg.id) }}" class="btn-primary btn-block">Select →</a>{% endif %}
</div>{% endfor %}</div>
</div>
{% endblock %}"""

CREATE_SERVER_HTML = """{% extends "base" %}{% block title %}Create Server{% endblock %}{% block content %}
<div class="wrap" style="max-width:540px;">
<div class="card" style="padding:28px 24px;">
<h1 style="margin:0 0 4px;">Create New Server</h1><p class="muted" style="margin-bottom:22px;">Deploy an isolated 24/7 Python instance.</p>
<form action="{{ url_for('create_server') }}" method="POST">
<div class="field"><label>Server Name</label><input type="text" name="name" placeholder="My Telegram Bot" required><small>Give your project a clear identifier.</small></div>
<div class="field"><label>Hosting Package</label><select name="package_id" required>{% for pkg in packages %}{% if not (pkg.is_first_time_offer and user.first_time_offer_used) %}<option value="{{ pkg.id }}" {% if selected_pkg_id == pkg.id %}selected{% endif %}>{{ pkg.name }} — {{ pkg.days }} Days ({{ pkg.coins }} Coins){% if pkg.is_first_time_offer %} [★]{% endif %}</option>{% endif %}{% endfor %}</select></div>
<div class="field"><label>Python Version</label><select name="python_version"><option value="Python 3.12">Python 3.12</option><option value="Python 3.11">Python 3.11</option><option value="Python 3.10" selected>Python 3.10 (Standard)</option><option value="Python 3.9">Python 3.9</option><option value="Python 3.8">Python 3.8</option></select></div>
<div class="feature-list-box"><b>Included:</b><div class="grid grid-2" style="gap:6px;margin-top:8px;"><div>✓ Starter main.py</div><div>✓ Live logs</div><div>✓ ZIP upload</div><div>✓ 24/7 runtime</div></div></div>
<button type="submit" class="btn-primary btn-block btn-lg">🚀 Create & Launch</button>
</form>
<div style="text-align:center;margin-top:16px;"><a href="{{ url_for('dashboard') }}" class="muted">← Back</a></div>
</div></div>
{% endblock %}"""

SERVER_MANAGE_HTML = """{% extends "base" %}{% block title %}{{ server.name }}{% endblock %}{% block content %}
<div class="wrap">
<div class="back-row"><a href="{{ url_for('dashboard') }}" class="back-btn">← Back</a></div>
<div class="card server-header-card"><div><div class="server-tag">Server #{{ server.id }}</div><h1>Server: <span class="gradient-text">{{ server.name }}</span></h1></div>
<div class="server-header-right"><span id="status-badge" class="status status-{{ server.status }}">{% if server.status=='running' %}🟢 RUNNING{% elif server.status=='package_required' %}🟡 SETUP{% else %}🔴 STOPPED{% endif %}</span><button onclick="document.getElementById('renew-modal').style.display='flex'" class="btn-secondary btn-sm">⏳ Extend</button></div></div>
<div class="subnav"><a href="{{ url_for('server_manage', server_id=server.id) }}" class="subnav-item active">📊 Logs</a><a href="{{ url_for('file_manager', server_id=server.id) }}" class="subnav-item">📁 Files</a><a href="{{ url_for('server_startup', server_id=server.id) }}" class="subnav-item">⚙️ Startup</a></div>
<div class="card"><div class="ops-head"><h2>Server Operations</h2><span id="pid-badge" class="pid-badge {% if server.status=='running' and server.pid %}pid-on{% endif %}">PID: {% if server.status=='running' and server.pid %}{{ server.pid }}{% else %}Offline{% endif %}</span></div>
<div class="ops-grid">
<button id="btn-start" onclick="serverAction({{ server.id }}, 'start')" class="btn-success" {% if server.status == 'running' or server.status == 'expired' %}disabled{% endif %}>🟢 START</button>
<button id="btn-restart" onclick="serverAction({{ server.id }}, 'restart')" class="btn-warning" {% if server.status == 'expired' %}disabled{% endif %}>🟠 RESTART</button>
<button id="btn-stop" onclick="serverAction({{ server.id }}, 'stop')" class="btn-danger" {% if server.status in ['stopped','package_required','expired'] %}disabled{% endif %}>🔴 STOP</button>
</div></div>
<div class="card"><div class="ops-head"><div style="display:flex;align-items:center;gap:8px;"><h2 style="margin:0;">📜 Logs (Live)</h2><span class="dot-pulse"></span></div><button onclick="clearLogs({{ server.id }})" class="btn-secondary btn-sm">🧹 Clear</button></div>
<div id="terminal" class="terminal"><div class="log-line log-info">[INFO] Connecting to log engine...</div></div></div>
<div class="meta-grid">
<div class="stat-card"><div class="stat-label">Entry File</div><div class="stat-value mono">{{ server.entry_file }}</div></div>
<div class="stat-card"><div style="display:flex;justify-content:space-between;"><div class="stat-label">Status</div><div id="uptime-tick" class="mono-tick">00:00:00</div></div><div style="display:flex;align-items:center;gap:6px;margin-top:3px;"><span id="status-dot" class="status-dot {% if server.status=='running' %}on{% endif %}"></span><span id="status-text" class="status-text {% if server.status=='running' %}on{% endif %}">{% if server.status=='running' %}Running{% else %}Offline{% endif %}</span></div></div>
<div class="stat-card"><div class="stat-label">Remaining</div><div class="stat-value {% if remaining_days < 2 %}danger-text{% endif %}">{{ remaining_days }} Days</div></div>
<div class="stat-card"><div class="stat-label">Expires</div><div class="stat-value" style="font-size:0.9rem;">{{ server.expires_at|format_date }}</div></div>
</div>
<div id="renew-modal" class="modal-overlay" style="display:none;"><div class="modal-card"><button class="modal-x" onclick="document.getElementById('renew-modal').style.display='none'">&times;</button>
<h3 style="margin-bottom:12px;">Extend Server</h3><p class="muted" style="margin-bottom:16px;">Coins: <b>{{ current_user.coins }}</b></p>
<div class="renew-list">{% for p in packages %}<label class="renew-item"><input type="radio" name="renew_pkg" value="{{ p.id }}" {% if loop.first %}checked{% endif %}><div><b>+{{ p.days }} Days</b><span>{{ p.name }}</span></div><div class="renew-coin">{{ p.coins }} Coins</div></label>{% endfor %}</div>
<button onclick="submitRenew({{ server.id }})" class="btn-primary btn-block">Confirm Extension</button></div></div>
{% if server.status == 'expired' %}<div class="modal-overlay" style="display:flex;"><div class="modal-card" style="max-width:480px;">
<div style="display:flex;gap:12px;align-items:center;margin-bottom:14px;"><div class="warn-icon">⚠️</div><div><h3 style="margin:0;">Update Server</h3><span class="danger-text" style="font-size:0.75rem;font-weight:700;">SERVER EXPIRED</span></div></div>
<p style="background:#FFF5F5;padding:12px;border-radius:10px;border-left:4px solid #EF4444;font-size:0.85rem;"><b>Server Expired!</b> Please renew to continue.</p>
<div class="renew-list" style="margin:16px 0;">{% for p in packages %}<label class="renew-item"><input type="radio" name="renew_pkg_exp" value="{{ p.id }}" {% if loop.first %}checked{% endif %}><div><b>+{{ p.days }} Days</b></div><div class="renew-coin">{{ p.coins }} Coins</div></label>{% endfor %}</div>
<button onclick="submitRenew({{ server.id }}, true)" class="btn-primary btn-block">🔄 Update Now</button></div></div>{% endif %}
<div id="no-entry-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="text-align:center;max-width:420px;"><div style="font-size:2.5rem;">⚠️</div><h3>Entry File Missing</h3><p class="muted">Upload your project files first.</p><div style="display:flex;gap:10px;justify-content:center;margin-top:16px;"><button onclick="document.getElementById('no-entry-modal').style.display='none'" class="btn-secondary">Close</button><a href="{{ url_for('file_manager', server_id=server.id) }}" class="btn-primary">📁 Upload</a></div></div></div>
</div>
{% endblock %}
{% block scripts %}<script>startLogStream({{ server.id }}, {{ start_time or 0 }});</script>{% endblock %}"""

FILE_MANAGER_HTML = """{% extends "base" %}{% block title %}Files: {{ server.name }}{% endblock %}{% block content %}
<div class="wrap">
<div class="back-row"><a href="{{ url_for('dashboard') }}" class="back-btn">← Back</a></div>
<div class="card server-header-card"><div><div class="server-tag">Server #{{ server.id }}</div><h1>Files: <span class="gradient-text">{{ server.name }}</span></h1></div><span class="status status-{{ server.status }}">{% if server.status=='running' %}🟢 RUNNING{% else %}🔴 STOPPED{% endif %}</span></div>
<div class="subnav"><a href="{{ url_for('server_manage', server_id=server.id) }}" class="subnav-item">📊 Logs</a><a href="{{ url_for('file_manager', server_id=server.id) }}" class="subnav-item active">📁 Files</a><a href="{{ url_for('server_startup', server_id=server.id) }}" class="subnav-item">⚙️ Startup</a></div>
<div class="card"><div class="fm-toolbar"><div class="breadcrumbs"><a href="{{ url_for('file_manager', server_id=server.id) }}">🏠 root</a>{% for bc in breadcrumbs %}<span>/</span><a href="{{ url_for('file_manager', server_id=server.id, path=bc.path) }}">{{ bc.name }}</a>{% endfor %}</div>
<div class="fm-actions"><label class="btn-primary btn-sm" style="cursor:pointer;">📦 Upload ZIP<input type="file" accept=".zip" style="display:none;" onchange="uploadFile({{ server.id }}, this, true)"></label>
<label class="btn-secondary btn-sm" style="cursor:pointer;">📤 Upload File<input type="file" multiple style="display:none;" onchange="uploadFile({{ server.id }}, this, false)"></label>
<button onclick="promptFolder({{ server.id }})" class="btn-secondary btn-sm">📁 Folder</button>
<button onclick="promptFile({{ server.id }})" class="btn-secondary btn-sm">➕ File</button></div></div></div>
<div class="card" style="padding:0;overflow:hidden;">
<div class="fm-head"><div>Name</div><div>Actions</div></div>
{% if items %}{% for item in items %}
<div class="fm-row"><div class="fm-info"><div class="fm-icon">{% if item.is_dir %}📁{% elif item.is_zip %}📦{% elif item.is_py %}🐍{% elif item.name.endswith('.json') %}⚙️{% elif item.name.endswith(('.png','.jpg','.jpeg','.svg','.gif','.webp')) %}🖼️{% else %}📄{% endif %}</div>
<div class="fm-meta">{% if item.is_dir %}<a href="{{ url_for('file_manager', server_id=server.id, path=(current_path + '/' + item.name) if current_path else item.name) }}" class="fm-name">{{ item.name }}</a>{% else %}<span class="fm-name" onclick="openEditor({{ server.id }}, '{{ (current_path + '/' + item.name) if current_path else item.name }}')">{{ item.name }}</span>{% endif %}
{% if item.is_entry %}<span class="entry-tag">ENTRY</span>{% endif %}<div class="fm-sub">{{ item.modified }} • {{ item.size }}</div></div></div>
<div class="dd-wrap"><button class="dd-trigger">⋮</button><div class="dd-popover">{% set fp = (current_path + '/' + item.name) if current_path else item.name %}
{% if item.is_zip %}<button onclick="unzipItem({{ server.id }}, '{{ fp }}')" class="dd-item primary-text">📦 Unzip</button>{% endif %}
{% if not item.is_dir %}<button onclick="openEditor({{ server.id }}, '{{ fp }}')" class="dd-item">✏️ Edit</button><a href="{{ url_for('download_file', server_id=server.id, path=fp) }}" class="dd-item">⬇️ Download</a>{% endif %}
<button onclick="renameItem({{ server.id }}, '{{ fp }}')" class="dd-item">🏷️ Rename</button>
<button onclick="deleteItem({{ server.id }}, '{{ fp }}')" class="dd-item danger">🗑️ Delete</button></div></div></div>
{% endfor %}{% else %}<div class="empty-mini" style="padding:36px;">Empty folder.</div>{% endif %}</div>
<div id="up-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:420px;text-align:center;"><div class="up-icon" id="up-icon">📤</div><h3 id="up-title">Uploading...</h3><p id="up-sub" class="muted">Please wait.</p><div class="progress-track"><div id="up-bar" class="progress-bar" style="width:0%;"></div></div><div style="display:flex;justify-content:space-between;font-size:0.8rem;font-weight:700;margin-top:8px;"><span id="up-pct" class="primary-text">0%</span><span id="up-size">0 KB / 0 KB</span></div></div></div>
<div id="editor-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:780px;height:85vh;display:flex;flex-direction:column;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;"><h3 id="ed-file" style="margin:0;">File Editor</h3><button onclick="document.getElementById('editor-modal').style.display='none'" class="modal-x" style="position:static;">&times;</button></div>
<input type="hidden" id="ed-path"><textarea id="ed-content" class="code-editor" spellcheck="false"></textarea>
<div style="display:flex;justify-content:flex-end;gap:10px;margin-top:14px;"><button onclick="document.getElementById('editor-modal').style.display='none'" class="btn-secondary btn-sm">Cancel</button><button onclick="saveEditor({{ server.id }})" class="btn-primary btn-sm">💾 Save</button></div></div></div>
</div>
{% endblock %}"""

STARTUP_HTML = """{% extends "base" %}{% block title %}Startup: {{ server.name }}{% endblock %}{% block content %}
<div class="wrap" style="max-width:680px;">
<div class="back-row"><a href="{{ url_for('dashboard') }}" class="back-btn">← Back</a></div>
<div class="card server-header-card"><div><div class="server-tag">Server #{{ server.id }}</div><h1>Startup: <span class="gradient-text">{{ server.name }}</span></h1></div><span class="status status-{{ server.status }}">{% if server.status=='running' %}🟢 RUNNING{% else %}🔴 STOPPED{% endif %}</span></div>
<div class="subnav"><a href="{{ url_for('server_manage', server_id=server.id) }}" class="subnav-item">📊 Logs</a><a href="{{ url_for('file_manager', server_id=server.id) }}" class="subnav-item">📁 Files</a><a href="{{ url_for('server_startup', server_id=server.id) }}" class="subnav-item active">⚙️ Startup</a></div>
<div class="card"><h2 style="margin-bottom:4px;">Startup Configuration</h2><p class="muted" style="margin-bottom:20px;">Configure how your app boots.</p>
<form action="{{ url_for('server_startup', server_id=server.id) }}" method="POST">
<div class="field"><label>Python Version</label><select name="python_version"><option value="Python 3.12" {% if server.python_version=='Python 3.12' %}selected{% endif %}>Python 3.12</option><option value="Python 3.11" {% if server.python_version=='Python 3.11' %}selected{% endif %}>Python 3.11</option><option value="Python 3.10" {% if server.python_version=='Python 3.10' %}selected{% endif %}>Python 3.10 (Recommended)</option><option value="Python 3.9" {% if server.python_version=='Python 3.9' %}selected{% endif %}>Python 3.9</option><option value="Python 3.8" {% if server.python_version=='Python 3.8' %}selected{% endif %}>Python 3.8</option></select></div>
<div class="field"><label>Main Startup File</label><input type="text" name="entry_file" value="{{ server.entry_file }}" required class="mono"><div class="py-hints"><span>Detected:</span>{% for f in py_files %}<button type="button" onclick="document.querySelector('[name=entry_file]').value='{{ f }}'" class="chip">{{ f }}</button>{% endfor %}</div></div>
<div class="toggle-box"><label class="toggle-label"><div><b>Auto-Restart on Crash</b><span class="muted">Restart if process terminates.</span></div><input type="checkbox" name="auto_restart" {% if server.auto_restart %}checked{% endif %} class="toggle-input"></label></div>
<button type="submit" class="btn-primary" {% if server.status=='expired' %}disabled{% endif %}>Save Startup Settings</button></form></div>
</div>
{% endblock %}"""

ADMIN_DASHBOARD_HTML = """{% extends "base" %}{% block title %}Admin Console{% endblock %}{% block content %}
<div class="wrap">
<div class="admin-hero"><div style="display:flex;align-items:center;gap:14px;"><div class="admin-hero-icon">👑</div><div><span class="admin-hero-label">ROOT ADMINISTRATION</span><h1>{{ site_name }} Control Center</h1></div></div>
<div style="display:flex;gap:8px;"><a href="{{ url_for('admin_users') }}" class="btn-glass">👥 Users</a><a href="{{ url_for('admin_coins') }}" class="btn-glass">🪙 Coins</a><a href="{{ url_for('admin_settings') }}" class="btn-glass-solid">⚙️ Settings</a></div></div>
<div class="stats-grid">
<div class="stat-card"><div class="stat-label">Total Users</div><div class="stat-value">{{ total_users }}</div><div class="stat-hint hint-green">{{ active_users }} active • {{ disabled_users }} disabled</div></div>
<div class="stat-card"><div class="stat-label">Total Servers</div><div class="stat-value">{{ total_servers }}</div><div class="stat-hint hint-blue">{{ running_servers }} running</div></div>
<div class="stat-card"><div class="stat-label">Total Files</div><div class="stat-value">{{ total_files }}</div><div class="stat-hint hint-purple">{{ total_storage_formatted }}</div></div>
<div class="stat-card"><div class="stat-label">System Coins</div><div class="stat-value gold-text">🪙 {{ total_coins }}</div><div class="stat-hint hint-amber">Circulating</div></div></div>
<div class="grid grid-3" style="margin-bottom:20px;">
{% if is_super_admin or has_admin_permission(current_user, 'manage_users') %}<a href="{{ url_for('admin_users') }}" class="quick-link"><span style="font-size:1.5rem;">👥</span><div><b>Users</b><span>Roles & balances</span></div></a>{% endif %}
{% if is_super_admin or has_admin_permission(current_user, 'manage_coins') %}<a href="{{ url_for('admin_coins') }}" class="quick-link"><span style="font-size:1.5rem;">🪙</span><div><b>Coins</b><span>Grant or deduct</span></div></a>{% endif %}
{% if is_super_admin or has_admin_permission(current_user, 'manage_broadcasts') %}<a href="{{ url_for('admin_broadcast') }}" class="quick-link" style="border-color:#C7D2FE;background:#EEF2FF;"><span style="font-size:1.5rem;">⚡</span><div><b>Broadcast</b><span>Push alerts</span></div></a>{% endif %}
{% if is_super_admin or has_admin_permission(current_user, 'manage_files') %}<a href="{{ url_for('admin_files') }}" class="quick-link"><span style="font-size:1.5rem;">📁</span><div><b>Storage</b><span>All files</span></div></a>{% endif %}
{% if is_super_admin or has_admin_permission(current_user, 'manage_announcements') %}<a href="{{ url_for('admin_announcements') }}" class="quick-link" style="border-color:#DDD6FE;background:#FAF5FF;"><span style="font-size:1.5rem;">📢</span><div><b>Notices</b><span>Announcements</span></div></a>{% endif %}
{% if is_super_admin or has_admin_permission(current_user, 'manage_settings') %}<a href="{{ url_for('admin_settings') }}" class="quick-link"><span style="font-size:1.5rem;">⚙️</span><div><b>Settings</b><span>Bonus & packages</span></div></a>{% endif %}
</div>
<div class="grid grid-2">
<div class="card"><div style="display:flex;justify-content:space-between;margin-bottom:14px;"><h3 style="margin:0;">Recent Users</h3><a href="{{ url_for('admin_users') }}" class="link-sm">All →</a></div>
<div style="display:flex;flex-direction:column;gap:8px;">{% for u in recent_users %}<div class="mini-row"><div><div style="font-weight:700;">{{ u.full_name }} <span class="muted">@{{ u.username }}</span></div><div class="muted-sm">{{ u.email }}</div></div><div style="text-align:right;"><div class="gold-text"><b>🪙 {{ u.coins }}</b></div><span class="status-pill-sm {% if u.status=='active' %}on{% endif %}">{{ u.status|upper }}</span></div></div>{% endfor %}</div></div>
<div class="card"><div style="display:flex;justify-content:space-between;margin-bottom:14px;"><h3 style="margin:0;">Audit Events</h3></div>
<div style="display:flex;flex-direction:column;gap:8px;max-height:340px;overflow-y:auto;">{% for log in recent_logs %}<div class="mini-row" style="flex-direction:column;align-items:stretch;"><div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#64748B;"><b class="primary-text">{{ log.action }}</b><span>{{ log.created_at|format_datetime }}</span></div><div style="font-size:0.8rem;">{{ log.details }}</div></div>{% endfor %}</div></div>
</div>
</div>
{% endblock %}"""

ADMIN_USERS_HTML = """{% extends "base" %}{% block title %}Users — Admin{% endblock %}{% block content %}
<div class="wrap">
<div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>User Management</h1></div><div class="stat-chip">Total: <b>{{ users|length }}</b></div></div>
<div class="card"><form method="GET" style="display:flex;gap:10px;"><input type="text" name="q" value="{{ search_query or '' }}" placeholder="🔍 Search..." class="input-flex"><button type="submit" class="btn-primary">Search</button>{% if search_query %}<a href="{{ url_for('admin_users') }}" class="btn-secondary">Clear</a>{% endif %}</form></div>
<div style="display:flex;flex-direction:column;gap:12px;">{% for u in users %}
{% set u_super = u.role == 'super_admin' or u.is_super_admin %}
{% set u_admin = u_super or u.role == 'admin' or u.is_admin %}
<div class="user-card {% if u.status=='disabled' %}user-disabled{% elif u_super %}user-super{% elif u_admin %}user-admin{% endif %}">
<div class="user-head"><div class="user-id"><div class="user-avatar-lg {% if u_super %}av-super{% elif u_admin %}av-admin{% endif %}">{% if u.avatar_url %}<img src="{{ u.avatar_url }}" alt="">{% elif u_super %}👑{% elif u_admin %}🛡️{% else %}{{ u.username[0]|upper }}{% endif %}</div>
<div><div class="user-name-row"><h3>{{ u.full_name }}</h3><span class="status-pill-sm {% if u.status=='active' %}on{% else %}off{% endif %}">{{ u.status|upper }}</span>{% if u_super %}<span class="role-badge role-super">👑 SUPER</span>{% elif u_admin %}<span class="role-badge role-admin">🛡️ ADMIN</span>{% endif %}</div>
<div class="muted-sm">@{{ u.username }} • {{ u.email }}</div></div></div>
<div class="user-metrics"><div class="metric gold">🪙 {{ u.coins }}</div><div class="metric">🖥️ {{ u.server_count }}</div>
{% if is_super_admin or not u_super %}<button type="button" class="btn-secondary btn-sm" onclick="openEditUser({{ u.id }}, '{{ u.full_name|e }}', '{{ u.username|e }}', '{{ u.email|e }}', '{{ (u.bio or '')|e }}', {{ u.coins }}, '{{ u.role }}', '{{ u.status }}', '{{ (u.admin_permissions or '')|e }}', {{ 'true' if u_super else 'false' }})">✏️ Edit</button>{% endif %}
{% if u.id != current_user.id %}<a href="{{ url_for('admin_impersonate', user_id=u.id) }}" class="btn-secondary btn-sm">🛡️ Open</a>
{% if is_super_admin or not u_admin %}<form action="{{ url_for('admin_toggle_status', user_id=u.id) }}" method="POST" style="display:inline;">{% if u.status == 'active' %}<button type="submit" class="btn-danger btn-sm" onclick="return confirm('Disable?')">🔒</button>{% else %}<button type="submit" class="btn-success btn-sm" onclick="return confirm('Activate?')">🔓</button>{% endif %}</form>{% endif %}{% endif %}
</div></div></div>{% else %}<div class="card" style="text-align:center;padding:40px;"><h3>No users found</h3></div>{% endfor %}</div>
</div>
<div id="edit-user-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="max-width:580px;max-height:90vh;overflow-y:auto;">
<div style="display:flex;justify-content:space-between;margin-bottom:16px;"><h2 style="margin:0;">Edit User</h2><button onclick="closeEditUser()" class="modal-x" style="position:static;">✕</button></div>
<form id="edit-user-form" method="POST"><div class="grid grid-2" style="gap:12px;">
<div class="field span-2"><label>Full Name</label><input type="text" id="eu_name" name="full_name" required></div>
<div class="field"><label>Username</label><input type="text" id="eu_user" name="username" required minlength="3"></div>
<div class="field"><label>Gmail</label><input type="email" id="eu_email" name="email" required></div>
<div class="field"><label>Coins</label><input type="number" id="eu_coins" name="coins" min="0" required></div>
<div class="field"><label>Role</label>{% if is_super_admin %}<select id="eu_role" name="role" onchange="togglePermBlock(this.value)"><option value="user">Standard User</option><option value="admin">Sub-Admin</option><option value="super_admin">Super Admin</option></select>{% else %}<select disabled><option>User</option></select>{% endif %}</div>
{% if is_super_admin %}<div id="perm-block" class="field span-2" style="display:none;background:#F8FAFC;padding:14px;border-radius:10px;"><label>Permissions</label><div class="grid grid-2" style="gap:8px;"><label class="check"><input type="checkbox" name="permissions" value="manage_users" id="p_users"> 👥 Users</label><label class="check"><input type="checkbox" name="permissions" value="manage_coins" id="p_coins"> 🪙 Coins</label><label class="check"><input type="checkbox" name="permissions" value="manage_files" id="p_files"> 📁 Files</label><label class="check"><input type="checkbox" name="permissions" value="manage_settings" id="p_settings"> ⚙️ Settings</label><label class="check"><input type="checkbox" name="permissions" value="manage_announcements" id="p_ann"> 📢 Ann</label><label class="check"><input type="checkbox" name="permissions" value="manage_broadcasts" id="p_bcast"> ⚡ Bcast</label><label class="check span-2"><input type="checkbox" name="permissions" value="view_logs" id="p_logs"> 📜 Logs</label></div></div>{% endif %}
<div class="field span-2"><label>Status</label><select id="eu_status" name="status"><option value="active">Active</option><option value="disabled">Disabled</option></select></div>
<div class="field span-2"><label>Bio</label><input type="text" id="eu_bio" name="bio"></div>
<div class="field span-2" style="background:#F8FAFC;padding:12px;border-radius:8px;"><label>Password Reset</label><input type="password" id="eu_pass" name="new_password" minlength="6" placeholder="Leave blank"></div>
</div>
<div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;"><button type="button" onclick="closeEditUser()" class="btn-secondary">Cancel</button><button type="submit" class="btn-primary">Save</button></div></form>
</div></div>
{% endblock %}"""

ADMIN_COINS_HTML = """{% extends "base" %}{% block title %}Coins — Admin{% endblock %}{% block content %}
<div class="wrap">
<div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>Coin Management</h1></div><div class="stat-chip">Circulating: <b>🪙 {{ total_system_coins }}</b></div></div>
<div class="grid grid-2">
<div class="card"><h2 style="margin:0 0 4px;">Adjust Balance</h2><p class="muted" style="margin-bottom:20px;">Add or deduct user coins.</p>
<form method="POST" action="{{ url_for('admin_coins') }}">
<div class="field"><label>Target Email</label><input type="email" name="user_identifier" placeholder="user@gmail.com" required></div>
<div class="field"><label>Amount</label><input type="number" name="amount" placeholder="50 or -20" required><small>Positive adds, negative deducts.</small></div>
<div class="field"><label>Reason</label><input type="text" name="reason" placeholder="VIP reward" required></div>
<button type="submit" class="btn-primary btn-block">Confirm</button></form></div>
<div class="card"><h3 style="margin-bottom:12px;">Top Balances</h3><div style="display:flex;flex-direction:column;gap:8px;max-height:400px;overflow-y:auto;">{% for u in users %}<div class="mini-row"><div><div style="font-weight:700;">{{ u.full_name }}</div><div class="muted-sm">@{{ u.username }}</div></div><button type="button" onclick="document.querySelector('[name=user_identifier]').value='{{ u.email }}'" class="coin-chip">🪙 {{ u.coins }}</button></div>{% endfor %}</div></div>
</div>
<div class="card" style="margin-top:20px;"><h3 style="margin-bottom:14px;">Recent Transactions</h3><div style="display:flex;flex-direction:column;gap:8px;">{% for tx in recent_transactions %}<div class="mini-row"><div><div style="font-weight:700;">{{ tx.username }} <span class="muted">{{ tx.description }}</span></div><div class="muted-sm">{{ tx.created_at|format_datetime }}</div></div><div class="{% if tx.amount > 0 %}green-text{% else %}red-text{% endif %}" style="font-weight:800;">{% if tx.amount > 0 %}+{{ tx.amount }}{% else %}{{ tx.amount }}{% endif %}</div></div>{% endfor %}</div></div>
</div>
{% endblock %}"""

ADMIN_FILES_HTML = """{% extends "base" %}{% block title %}Files — Admin{% endblock %}{% block content %}
<div class="wrap">
<div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>📁 Central File Management</h1></div><div class="stat-chip">Storage: <b>{{ total_storage_formatted }}</b> ({{ total_files }} files)</div></div>
<div class="card"><form method="GET" style="display:flex;gap:10px;"><input type="text" name="q" value="{{ query or '' }}" placeholder="🔍 Search..." class="input-flex"><button type="submit" class="btn-primary">Search</button>{% if query %}<a href="{{ url_for('admin_files') }}" class="btn-secondary">Clear</a>{% endif %}</form></div>
{% if stats %}<div style="display:flex;flex-direction:column;gap:16px;">{% for item in stats %}{% set s = item.server %}
<div class="card"><div class="file-server-head"><div style="display:flex;gap:14px;"><div class="file-server-icon">🐍</div><div><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;"><h3 style="margin:0;">{{ s.name }}</h3><span class="status-pill-sm {% if s.status=='running' %}on{% endif %}">● {{ s.status|upper }}</span></div><div class="muted-sm">👤 <b>{{ s.full_name or s.username }}</b> — <code>{{ s.email }}</code></div></div></div>
<div style="display:flex;gap:8px;align-items:center;"><a href="{{ url_for('admin_download_zip', server_id=s.id) }}" class="btn-primary btn-sm">📦 ZIP</a><a href="{{ url_for('server_manage', server_id=s.id) }}" class="btn-secondary btn-sm">🖥️ Console</a></div></div>
{% if item.files %}<div style="margin-top:14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;"><table style="width:100%;border-collapse:collapse;font-size:0.82rem;"><thead><tr style="background:#F1F5F9;text-align:left;font-size:0.75rem;"><th style="padding:10px 14px;">File</th><th style="padding:10px 14px;width:110px;">Size</th><th style="padding:10px 14px;text-align:right;width:180px;">Actions</th></tr></thead><tbody>
{% for f in item.files %}<tr style="border-top:1px solid #E2E8F0;"><td style="padding:10px 14px;"><div style="display:flex;gap:8px;align-items:center;"><span>{% if f.filename=='main.py' %}🐍{% elif f.ext=='py' %}📜{% else %}📄{% endif %}</span><code>{{ f.name }}</code></div></td>
<td style="padding:10px 14px;color:#64748B;font-family:monospace;">{{ f.size_formatted }}</td>
<td style="padding:10px 14px;text-align:right;">{% if f.is_text and f.size <= 524288 %}<button onclick="adminPreview({{ s.id }}, '{{ f.name|e }}', '{{ s.name|e }}')" class="btn-secondary btn-sm" style="background:#fff;">👁️</button>{% endif %}<a href="{{ url_for('admin_download_file', server_id=s.id, path=f.name) }}" class="btn-secondary btn-sm" style="background:#fff;color:#4338CA;">⬇️</a></td></tr>{% endfor %}
</tbody></table></div>{% else %}<div style="margin-top:14px;padding:20px;text-align:center;color:#64748B;">No files.</div>{% endif %}</div>
{% endfor %}</div>{% else %}<div class="card" style="text-align:center;padding:50px;"><div style="font-size:2.5rem;">📂</div><h3>No Files Found</h3></div>{% endif %}
</div>
<div id="admin-preview-modal" class="modal-overlay" style="display:none;"><div class="modal-card" style="background:#0F172A;color:#F8FAFC;max-width:860px;max-height:88vh;display:flex;flex-direction:column;padding:0;">
<div style="padding:16px 20px;background:#1E293B;display:flex;justify-content:space-between;align-items:center;"><div><code id="ap-file" style="color:#38BDF8;"></code><div id="ap-sub" style="font-size:0.75rem;color:#94A3B8;"></div></div>
<div style="display:flex;gap:8px;"><a id="ap-dl" href="#" class="btn-primary btn-sm" style="background:#38BDF8;color:#0F172A;">⬇️</a><button onclick="document.getElementById('admin-preview-modal').style.display='none'" style="background:none;border:none;color:#94A3B8;font-size:1.4rem;cursor:pointer;">✕</button></div></div>
<pre id="ap-content" style="margin:0;padding:16px;overflow-y:auto;flex:1;font-family:monospace;font-size:0.85rem;background:#090D16;color:#E2E8F0;white-space:pre-wrap;"></pre></div></div>
{% endblock %}"""

ADMIN_ANNOUNCEMENTS_HTML = """{% extends "base" %}{% block title %}Announcements — Admin{% endblock %}{% block content %}
<div class="wrap">
<div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>📢 System Announcements</h1></div></div>
<div class="card" style="border:1.5px solid #DDD6FE;"><h2 style="margin:0 0 4px;">Publish New</h2>
<form action="{{ url_for('admin_create_ann') }}" method="POST">
<div class="grid grid-2" style="gap:16px;margin-bottom:16px;"><div class="field"><label>Title</label><input type="text" name="title" required></div><div class="field"><label>Type</label><select name="type"><option value="update">🚀 Update</option><option value="info">ℹ️ Info</option><option value="warning">⚠️ Warning</option><option value="maintenance">🛠️ Maintenance</option></select></div></div>
<div class="field"><label>Content</label><textarea name="content" rows="4" required></textarea></div>
<div class="ann-options"><div style="display:flex;gap:24px;"><label class="check"><input type="checkbox" name="is_active" value="1" checked> Active</label><label class="check"><input type="checkbox" name="pinned" value="1"> Pin</label></div><button type="submit" class="btn-primary">📢 Publish</button></div>
</form></div>
<div class="card" style="margin-top:20px;"><h3 style="margin-bottom:16px;">Existing ({{ announcements|length }})</h3>
{% if announcements %}<div style="display:flex;flex-direction:column;gap:14px;">{% for a in announcements %}<div class="ann-admin-card ann-{{ a.type }}"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:10px;"><div><div style="display:flex;gap:6px;margin-bottom:4px;"><span class="badge badge-primary">{{ a.type|upper }}</span>{% if a.pinned %}<span class="badge badge-warn">📌</span>{% endif %}{% if a.is_active %}<span class="badge badge-success">● LIVE</span>{% endif %}</div><h3 style="margin:0;">{{ a.title }}</h3></div>
<div style="display:flex;gap:6px;"><form action="{{ url_for('admin_toggle_ann', aid=a.id) }}" method="POST" style="margin:0;"><button class="btn-secondary btn-sm">{% if a.is_active %}Hide{% else %}Show{% endif %}</button></form>
<form action="{{ url_for('admin_toggle_pin', aid=a.id) }}" method="POST" style="margin:0;"><button class="btn-secondary btn-sm">{% if a.pinned %}Unpin{% else %}Pin{% endif %}</button></form>
<form action="{{ url_for('admin_delete_ann', aid=a.id) }}" method="POST" style="margin:0;" onsubmit="return confirm('Delete?');"><button class="btn-danger btn-sm">🗑️</button></form></div></div>
<p style="font-size:0.875rem;color:#334155;line-height:1.6;white-space:pre-line;">{{ a.content }}</p></div>{% endfor %}</div>{% else %}<div style="text-align:center;padding:40px;"><h3>No Announcements</h3></div>{% endif %}</div>
</div>
{% endblock %}"""

ADMIN_BROADCAST_HTML = """{% extends "base" %}{% block title %}Broadcast{% endblock %}{% block content %}
<div class="wrap">
<div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>⚡ Notification Broadcast</h1></div><div class="stat-chip">Active: <b>{{ users|length }}</b></div></div>
<div class="card"><h2 style="margin-bottom:16px;">Create Broadcast</h2>
<form method="POST" action="{{ url_for('admin_broadcast') }}">
<div class="field"><label>Target</label><div class="grid grid-2" style="gap:12px;"><label class="target-box"><input type="radio" name="target_type" value="all" checked onchange="pickTarget('all')"><div><b>🌐 All Users</b></div></label><label class="target-box"><input type="radio" name="target_type" value="specific" onchange="pickTarget('specific')"><div><b>👤 Specific</b></div></label></div></div>
<div id="specific-user" class="field" style="display:none;background:#EEF2FF;padding:14px;border-radius:10px;"><label>User</label><select name="target_user_id"><option value="">-- Choose --</option>{% for u in users %}<option value="{{ u.id }}">{{ u.full_name }} (@{{ u.username }})</option>{% endfor %}</select></div>
<div class="grid grid-2" style="gap:12px;margin-bottom:16px;"><div class="field"><label>Title</label><input type="text" name="title" required></div><div class="field"><label>Category</label><select name="category"><option value="announcement">📢</option><option value="system">⚙️</option><option value="warning">⚠️</option><option value="info">ℹ️</option></select></div></div>
<div class="field"><label>Message</label><textarea name="message" rows="4" required></textarea></div>
<div style="display:flex;justify-content:flex-end;"><button type="submit" class="btn-primary">🚀 Send</button></div></form></div>
<div class="card" style="margin-top:20px;"><h3 style="margin-bottom:16px;">History</h3>{% if broadcasts %}<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.82rem;"><thead><tr style="background:#F8FAFC;text-align:left;font-size:0.75rem;"><th style="padding:10px;">ID</th><th style="padding:10px;">Admin</th><th style="padding:10px;">Target</th><th style="padding:10px;">Title</th><th style="padding:10px;">Sent</th></tr></thead><tbody>{% for b in broadcasts %}<tr style="border-bottom:1px solid #F1F5F9;"><td style="padding:10px;">#{{ b.id }}</td><td style="padding:10px;">@{{ b.admin_username }}</td><td style="padding:10px;">{% if b.target_type=='all' %}<span class="badge badge-primary">🌐 All ({{ b.recipients_count }})</span>{% else %}<span class="badge badge-success">👤 @{{ b.target_username }}</span>{% endif %}</td><td style="padding:10px;"><b>{{ b.title }}</b></td><td style="padding:10px;color:#94A3B8;">{{ b.created_at|format_datetime }}</td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="empty-mini">No broadcasts.</div>{% endif %}</div>
</div>
{% endblock %}"""

ADMIN_SETTINGS_HTML = """{% extends "base" %}{% block title %}Settings{% endblock %}{% block content %}
<div class="wrap" style="max-width:700px;">
<div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>Platform Settings</h1></div></div>
<div class="card"><h2 style="margin:0 0 4px;">🎨 Logo & Branding</h2>
<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:14px;padding:18px;margin:16px 0;"><div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;">
<div class="logo-preview-frame">{% if settings.site_logo_url %}<img id="logo-preview" src="{{ settings.site_logo_url }}" alt="">{% else %}<span>⚡</span>{% endif %}</div>
<form action="{{ url_for('admin_settings') }}" method="POST" enctype="multipart/form-data" style="flex:1;"><input type="hidden" name="action" value="upload_logo">
<div style="display:flex;gap:8px;flex-wrap:wrap;"><label class="btn-secondary">📁 Choose<input type="file" name="logo" accept="image/*" style="display:none;" onchange="previewLogo(this)" required></label><button type="submit" class="btn-primary">⬆️ Upload</button></div></form></div></div>
{% if settings.site_logo_url %}<form action="{{ url_for('admin_settings') }}" method="POST" onsubmit="return confirm('Reset?');"><input type="hidden" name="action" value="reset_logo"><button type="submit" class="btn-danger-outline">🗑️ Reset Logo</button></form>{% endif %}</div>
<div class="card"><h2 style="margin:0 0 4px;">🏷️ Site Branding</h2>
<form action="{{ url_for('admin_settings') }}" method="POST"><input type="hidden" name="action" value="update_branding">
<div class="field"><label>Site Name</label><input type="text" name="site_name" value="{{ settings.site_name }}" required></div>
<div class="field"><label>VIP Name</label><input type="text" name="vip_site_name" value="{{ settings.vip_site_name }}" required></div>
<button type="submit" class="btn-primary">💾 Save</button></form></div>
<div class="card" style="border:1.5px solid #DDD6FE;"><h2 style="margin:0 0 4px;">🎁 Signup & Daily</h2>
<form action="{{ url_for('admin_settings') }}" method="POST"><input type="hidden" name="action" value="update_signup_bonus">
<div class="grid grid-2" style="gap:16px;margin-bottom:16px;"><div class="field"><label>Signup Bonus</label><input type="number" name="default_starting_coins" value="{{ settings.default_starting_coins }}" min="0" required></div>
<div class="field"><label>Daily Reward</label><input type="number" name="daily_reward_coins" value="{{ settings.daily_reward_coins }}" min="0" required></div></div>
<button type="submit" class="btn-primary">💾 Save</button></form></div>
<div class="card"><h2 style="margin:0 0 4px;">Maintenance Mode</h2>
<form action="{{ url_for('admin_settings') }}" method="POST"><input type="hidden" name="action" value="update_maintenance">
<div class="toggle-box"><label class="toggle-label"><div><b>Enable</b></div><input type="checkbox" name="maintenance_mode" {% if settings.maintenance_mode == '1' %}checked{% endif %} class="toggle-input"></label></div>
<div class="field"><label>Message</label><textarea name="maintenance_message" rows="3">{{ settings.maintenance_message }}</textarea></div>
<button type="submit" class="btn-primary">Save</button></form></div>
<div class="card" style="border:1px solid #BAE6FD;"><h2 style="margin:0 0 4px;">🔄 Self-Ping</h2>
<form action="{{ url_for('admin_settings') }}" method="POST"><input type="hidden" name="action" value="update_self_ping">
<div class="toggle-box"><label class="toggle-label"><div><b>Enable Self-Ping</b></div><input type="checkbox" name="self_ping_enabled" {% if settings.self_ping_enabled == '1' %}checked{% endif %} class="toggle-input"></label></div>
<div class="field"><label>Interval (min)</label><input type="number" name="self_ping_interval" value="{{ settings.self_ping_interval }}" min="1" max="60" required></div>
<button type="submit" class="btn-primary">Save</button></form></div>
<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;"><h2 style="margin:0;">📦 Packages</h2><div style="display:flex;gap:8px;"><button type="button" onclick="toggleNewPkg()" class="btn-secondary btn-sm">➕ Add</button><form action="{{ url_for('admin_reset_pkgs') }}" method="POST" style="margin:0;" onsubmit="return confirm('Reset?');"><button type="submit" class="btn-secondary btn-sm">🔄 Reset</button></form></div></div>
<div id="new-pkg-form" style="display:none;background:#FAF5FF;border:1.5px dashed #C084FC;border-radius:14px;padding:18px;margin-bottom:20px;">
<form action="{{ url_for('admin_create_pkg') }}" method="POST"><div class="grid grid-3" style="gap:12px;margin-bottom:12px;"><div class="field" style="margin:0;"><label>Name</label><input type="text" name="name" required></div><div class="field" style="margin:0;"><label>Days</label><input type="number" name="days" min="1" required></div><div class="field" style="margin:0;"><label>Coins</label><input type="number" name="coins" min="0" required></div></div>
<div class="field"><label>Description</label><input type="text" name="description"></div>
<div style="display:flex;justify-content:space-between;"><div style="display:flex;gap:16px;"><label class="check"><input type="checkbox" name="active" value="1" checked> Active</label><label class="check"><input type="checkbox" name="is_first_time_offer" value="1"> One-Time</label></div><button type="submit" class="btn-primary">🚀 Create</button></div></form></div>
<div style="display:flex;flex-direction:column;gap:12px;">{% for pkg in packages %}<div class="pkg-edit-card {% if pkg.is_first_time_offer %}pkg-fto{% endif %}">
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px;"><div style="display:flex;gap:8px;align-items:center;"><b>{{ pkg.name }}</b>{% if pkg.is_first_time_offer %}<span class="badge badge-purple">★</span>{% endif %}{% if pkg.active %}<span class="badge badge-success">✓</span>{% endif %}</div><div><b class="primary-text">{{ pkg.coins }}</b> Coins / {{ pkg.days }}d</div></div>
<form action="{{ url_for('admin_update_pkg') }}" method="POST"><input type="hidden" name="id" value="{{ pkg.id }}">
<div class="grid grid-3" style="gap:10px;margin-bottom:10px;"><div class="field" style="margin:0;"><label>Name</label><input type="text" name="name" value="{{ pkg.name }}" required></div><div class="field" style="margin:0;"><label>Days</label><input type="number" name="days" value="{{ pkg.days }}" min="1" required></div><div class="field" style="margin:0;"><label>Coins</label><input type="number" name="coins" value="{{ pkg.coins }}" min="0" required></div></div>
<div class="field"><label>Desc</label><input type="text" name="description" value="{{ pkg.description }}"></div>
<div style="display:flex;justify-content:space-between;border-top:1px solid #F1F5F9;padding-top:10px;"><div style="display:flex;gap:14px;"><label class="check"><input type="checkbox" name="active" value="1" {% if pkg.active %}checked{% endif %}> Active</label><label class="check"><input type="checkbox" name="is_first_time_offer" value="1" {% if pkg.is_first_time_offer %}checked{% endif %}> One-Time</label></div><button type="submit" class="btn-primary btn-sm">💾</button></div></form>
{% if packages|length > 1 %}<form action="{{ url_for('admin_delete_pkg', pid=pkg.id) }}" method="POST" onsubmit="return confirm('Delete?');" style="text-align:right;margin-top:6px;"><button type="submit" style="background:none;border:none;color:#94A3B8;font-size:0.72rem;text-decoration:underline;cursor:pointer;">Remove</button></form>{% endif %}</div>{% endfor %}</div></div>
</div>
{% endblock %}"""

ADMIN_LOGS_HTML = """{% extends "base" %}{% block title %}Audit Logs{% endblock %}{% block content %}
<div class="wrap">
<div class="admin-hero"><div><a href="{{ url_for('admin_dashboard') }}" class="admin-back">← Admin</a><h1>📜 Audit Logs</h1></div></div>
<div class="card">{% if logs %}<div style="display:flex;flex-direction:column;gap:10px;">{% for log in logs %}<div class="mini-row" style="flex-direction:column;align-items:stretch;"><div style="display:flex;justify-content:space-between;"><div style="display:flex;gap:8px;"><span class="badge badge-primary">{{ log.action }}</span><b>@{{ log.admin_username }}</b></div><span class="muted-sm mono">{{ log.created_at|format_datetime }}</span></div><div style="font-size:0.82rem;color:#475569;"><b>Target:</b> {{ log.target }}{% if log.details %} • {{ log.details }}{% endif %}</div></div>{% endfor %}</div>{% else %}<div class="empty-mini">No logs.</div>{% endif %}</div>
</div>
{% endblock %}"""

ERROR_403 = """{% extends "base" %}{% block title %}403{% endblock %}{% block content %}<div class="wrap" style="max-width:480px;text-align:center;margin-top:40px;"><div class="card" style="padding:40px;"><div style="font-size:3.5rem;">🛡️</div><h1>Access Restricted</h1><p class="muted">Permission denied.</p><a href="{{ url_for('dashboard') }}" class="btn-primary btn-lg">← Back</a></div></div>{% endblock %}"""

ERROR_404 = """{% extends "base" %}{% block title %}404{% endblock %}{% block content %}<div class="wrap" style="max-width:480px;text-align:center;margin-top:40px;"><div class="card" style="padding:40px;"><div style="font-size:3.5rem;">🔍</div><h1>Page Not Found</h1><p class="muted">Doesn't exist.</p><a href="{{ url_for('dashboard') if current_user else url_for('home') }}" class="btn-primary btn-lg">← Home</a></div></div>{% endblock %}"""

ERROR_500 = """{% extends "base" %}{% block title %}500{% endblock %}{% block content %}<div class="wrap" style="max-width:480px;text-align:center;margin-top:40px;"><div class="card" style="padding:40px;"><div style="font-size:3.5rem;">⚠️</div><h1>Server Error</h1><p class="muted">Something broke.</p><a href="{{ url_for('dashboard') if current_user else url_for('home') }}" class="btn-primary btn-lg">← Home</a></div></div>{% endblock %}"""

# ============================================================
# LOADER
# ============================================================
class _DictLoader(jinja2.BaseLoader):
    def __init__(self, m): self.m = m
    def get_source(self, env, t):
        if t not in self.m: raise jinja2.TemplateNotFound(t)
        return self.m[t], f"{t}.html", lambda: False

_TEMPLATES = {
    "base": BASE_HTML, "home": HOME_HTML, "dashboard": DASHBOARD_HTML,
    "coins": COINS_HTML, "account": ACCOUNT_HTML, "packages": PACKAGES_HTML,
    "create_server": CREATE_SERVER_HTML, "server_manage": SERVER_MANAGE_HTML,
    "file_manager": FILE_MANAGER_HTML, "startup": STARTUP_HTML,
    "signin": SIGNIN_HTML, "signup": SIGNUP_HTML,
    "admin_dashboard": ADMIN_DASHBOARD_HTML, "admin_users": ADMIN_USERS_HTML,
    "admin_coins": ADMIN_COINS_HTML, "admin_files": ADMIN_FILES_HTML,
    "admin_announcements": ADMIN_ANNOUNCEMENTS_HTML, "admin_broadcast": ADMIN_BROADCAST_HTML,
    "admin_settings": ADMIN_SETTINGS_HTML, "admin_logs": ADMIN_LOGS_HTML,
    "403": ERROR_403, "404": ERROR_404, "500": ERROR_500,
}
app.jinja_loader = _DictLoader(_TEMPLATES)

@app.errorhandler(404)
def _e404(e): return render_template("404"), 404
@app.errorhandler(403)
def _e403(e): return render_template("403"), 403
@app.errorhandler(500)
def _e500(e): return render_template("500"), 500

# ============================================================
# STATIC FILES (style.css + script.js served from memory)
# ============================================================
# Read from disk if exists, else fallback
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
# MAIN
# ============================================================
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    print("=" * 55)
    print("  HOSTX VIP — Python Hosting Platform")
    print(f"  Running on http://0.0.0.0:{PORT}")
    print("=" * 55)
    app.run(host='0.0.0.0', port=PORT, debug=False)