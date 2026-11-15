import secrets, time
from fastapi import Request, HTTPException
_sessions = {}  # token -> expiry
def create(): t = secrets.token_urlsafe(32); _sessions[t] = time.time() + 8*3600; return t
def valid(t): return bool(t) and _sessions.get(t, 0) > time.time()
def drop(t): _sessions.pop(t, None)
def require_admin(request: Request):
    if not valid(request.cookies.get("session")): raise HTTPException(401, "Login admin diperlukan")
