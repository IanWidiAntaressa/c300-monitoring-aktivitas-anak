import sqlite3, hashlib, secrets, threading, time
from ..config import ROOT
DB = ROOT / "data" / "app.db"
_lock = threading.Lock()
CATS = ["depan", "belakang", "kanan", "kiri", "menunduk", "tidak_diketahui"]
def conn():
    # Pastikan folder data tersedia sebelum SQLite membuka/membuat database.
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c
def hash_pw(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120000).hex()
def init(admin_user, admin_pw):
    with _lock, conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt TEXT, pwhash TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS minutes(minute_ts INTEGER PRIMARY KEY, source TEXT, samples INTEGER, avg_total REAL, avg_front REAL,"
                  + ",".join(f"pct_{k} REAL" for k in CATS) + ")")
        cols = {r[1] for r in c.execute("PRAGMA table_info(minutes)")}
        if "avg_front" not in cols:
            c.execute("ALTER TABLE minutes ADD COLUMN avg_front REAL NOT NULL DEFAULT 0")
        c.execute("CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, start_ts INTEGER, end_ts INTEGER, source TEXT)")
        if not c.execute("SELECT 1 FROM users WHERE username=?", (admin_user,)).fetchone():
            s = secrets.token_hex(16)
            c.execute("INSERT INTO users VALUES(?,?,?)", (admin_user, s, hash_pw(admin_pw, s)))
def check_user(u, p):
    with conn() as c:
        r = c.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
    return bool(r) and secrets.compare_digest(r["pwhash"], hash_pw(p, r["salt"]))
def save_minute(ts, source, samples, avg_total, avg_front, pcts):
    with _lock, conn() as c:
        cols = ["minute_ts", "source", "samples", "avg_total", "avg_front"] + [f"pct_{k}" for k in CATS]
        marks = ",".join("?" for _ in cols)
        c.execute(f"INSERT OR REPLACE INTO minutes ({','.join(cols)}) VALUES({marks})",
                  (ts, source, samples, avg_total, avg_front, *[pcts[k] for k in CATS]))
def start_session(source):
    with _lock, conn() as c:
        return c.execute("INSERT INTO sessions(start_ts,source) VALUES(?,?)", (int(time.time()), source)).lastrowid
def end_session(sid):
    with _lock, conn() as c: c.execute("UPDATE sessions SET end_ts=? WHERE id=?", (int(time.time()), sid))
def history(start=None, end=None, limit=2000):
    q, a = "SELECT * FROM minutes WHERE 1=1", []
    if start: q += " AND minute_ts>=?"; a.append(start)
    if end: q += " AND minute_ts<=?"; a.append(end)
    with conn() as c: return [dict(r) for r in c.execute(q + " ORDER BY minute_ts DESC LIMIT ?", (*a, limit))][::-1]
def sessions(limit=100):
    with conn() as c: return [dict(r) for r in c.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,))]
