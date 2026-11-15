import asyncio, shutil
from fastapi import FastAPI, WebSocket, Request, Response, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import config
from .database import db
from .auth import session
from .cv.pipeline import pipeline
cfg = config.load(); db.init(cfg["admin"]["username"], cfg["admin"]["password"])
app = FastAPI(title="CCTV Monitoring Perhatian Siswa")
FE = config.ROOT / "frontend"
def pub_stats():
    s = pipeline.snapshot(); return {"status": s["status"], "total_available": s["total"] > 0, "avg_front_per_minute": s["avg_front_per_minute"]}
@app.get("/")
def guest(): return FileResponse(FE / "guest.html")
@app.get("/admin")
def admin(): return FileResponse(FE / "admin.html")
@app.get("/api/public/stats")
def api_pub(): return pub_stats()
def mjpeg(attr):
    async def gen():
        last = None
        while True:
            j = getattr(pipeline, attr)
            if j is not None and j is not last:
                last = j; yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + j + b"\r\n"
            await asyncio.sleep(0.05)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=f")
@app.get("/stream/public")
def sp(): return mjpeg("jpg_public")
@app.get("/stream/admin", dependencies=[Depends(session.require_admin)])
def sa(): return mjpeg("jpg_admin")
@app.websocket("/ws/public")
async def ws_pub(ws: WebSocket):
    await ws.accept()
    try:
        while True: await ws.send_json(pub_stats()); await asyncio.sleep(1)
    except Exception: pass
@app.websocket("/ws/admin")
async def ws_adm(ws: WebSocket):
    if not session.valid(ws.cookies.get("session")): await ws.close(code=4401); return
    await ws.accept()
    try:
        while True: await ws.send_json(pipeline.snapshot()); await asyncio.sleep(1)
    except Exception: pass
class Login(BaseModel): username: str; password: str
@app.post("/api/login")
def login(b: Login, resp: Response):
    if not db.check_user(b.username, b.password): raise HTTPException(401, "Username/password salah")
    resp.set_cookie("session", session.create(), httponly=True, samesite="lax"); return {"ok": True}
@app.post("/api/logout")
def logout(request: Request, resp: Response): session.drop(request.cookies.get("session")); resp.delete_cookie("session"); return {"ok": True}
A = [Depends(session.require_admin)]
@app.get("/api/admin/stats", dependencies=A)
def a_stats(): return pipeline.snapshot()
@app.get("/api/admin/history", dependencies=A)
def a_hist(start: int = None, end: int = None): return {"minutes": db.history(start, end), "sessions": db.sessions()}
@app.post("/api/admin/control/{action}", dependencies=A)
def a_ctl(action: str):
    if action == "start": pipeline.start()
    elif action == "stop": pipeline.stop()
    else: raise HTTPException(400, "action: start|stop")
    return pipeline.snapshot()
class Src(BaseModel): type: str; value: str
@app.post("/api/admin/source", dependencies=A)
def a_src(b: Src):
    if b.type not in ("mp4", "webcam", "rtsp"): raise HTTPException(400, "type: mp4|webcam|rtsp")
    c = config.load(); c["source"] = b.dict(); config.save(c)
    was = pipeline.running; pipeline.stop()
    if was: pipeline.start()
    return c["source"]
@app.post("/api/admin/upload", dependencies=A)
def a_up(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".mp4"): raise HTTPException(400, "Hanya .mp4")
    dst = config.ROOT / "videos" / file.filename.replace("/", "_").replace("\\", "_")
    with open(dst, "wb") as f: shutil.copyfileobj(file.file, f)
    c = config.load(); c["source"] = {"type": "mp4", "value": f"videos/{dst.name}"}; config.save(c); return c["source"]
app.mount("/static", StaticFiles(directory=FE), name="static")
