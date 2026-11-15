import cv2, threading, time, os, statistics
from collections import deque
from .. import config
from ..database import db
from .orientation import classify, CATS
COLORS = {"depan": (80,200,80), "belakang": (60,60,230), "kanan": (230,160,40), "kiri": (200,100,230), "menunduk": (40,200,230), "tidak_diketahui": (150,150,150)}
class Pipeline:
    def __init__(self):
        self.running = False; self.status = "stopped"; self.error = None
        self.counts = {k: 0 for k in CATS}; self.total = 0
        self.jpg_public = None; self.jpg_admin = None
        self._t = None; self._stop = threading.Event()
        self.history_live = deque(maxlen=300); self._acc = []; self._cur_min = None; self.sid = None
        self.votes = {}; self.track_obs = {}; self.excluded = set(); self.static_ex = []
    def start(self):
        if self.running: return
        self._stop.clear(); self.running = True; self._t = threading.Thread(target=self._run, daemon=True); self._t.start()
    def stop(self):
        self._stop.set()
        if self._t: self._t.join(timeout=5)
        self.running = False; self.status = "stopped"; self.total = 0; self.counts = {k: 0 for k in CATS}
        self.jpg_public = self.jpg_admin = None
    def snapshot(self):
        t = self.total
        pct = {k: (round(v*100/t, 1) if t else None) for k, v in self.counts.items()}
        avg_front = (sum(s[0]["depan"] for s in self._acc) / len(self._acc)) if self._acc else 0.0
        return {"status": self.status, "error": self.error, "total": t, "counts": self.counts, "pct": pct, "avg_front_per_minute": round(avg_front, 2)}
    def _flush(self):
        if not self._acc or self._cur_min is None: return
        n = len(self._acc)
        valid = [s for s in self._acc if s[1] > 0]
        pcts = {k: (sum(s[0][k] * 100 / s[1] for s in valid) / len(valid) if valid else 0.0) for k in CATS}
        avg_total = sum(s[1] for s in self._acc) / n
        avg_front = sum(s[0]["depan"] for s in self._acc) / n
        db.save_minute(self._cur_min*60, config.load()["source"]["type"], n, avg_total, avg_front, pcts); self._acc = []
    def _open(self, cfg):
        s = cfg["source"]; v = s["value"]
        if s["type"] == "webcam":
            # Windows: coba DirectShow terlebih dahulu, lalu backend default OpenCV.
            camera_index = int(v or 0)
            if os.name == "nt":
                cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    return cap
                cap.release()
            return cv2.VideoCapture(camera_index)
        if s["type"] == "mp4": return cv2.VideoCapture(v if os.path.isabs(v) else str(config.ROOT / v))
        return cv2.VideoCapture(v)  # rtsp://...
    def _auto_excluded(self, tid, b, raw, W, H, cfg):
        """Kecualikan guru & poster/potret secara otomatis (bukan siswa).
        Ciri: berada di area depan kelas (bagian atas frame) dan terus-menerus menghadap KAMERA ('belakang').
        Poster yang diam diingat posisinya, sehingga tetap diabaikan walau ID tracking berganti."""
        if not cfg.get("auto_exclude", True): return False
        cx = (b[0]+b[2])/2/W; cy = (b[1]+b[3])/2/H; h = (b[3]-b[1])/H
        for sx, sy, sh in self.static_ex:
            if abs(cx-sx) < 0.03 and abs(cy-sy) < 0.03 and abs(h-sh) < 0.05: return True
        if tid is None: return False
        if tid in self.excluded: return True
        d = self.track_obs.setdefault(tid, deque(maxlen=60)); d.append((cx, cy, h, raw))
        if len(d) >= cfg.get("auto_min_obs", 30):
            facing = sum(1 for o in d if o[3] == "belakang") / len(d)
            mcy = sum(o[1] for o in d) / len(d)
            if facing >= cfg.get("auto_facing_ratio", 0.8) and mcy < cfg.get("auto_front_band", 0.5):
                self.excluded.add(tid)
                if statistics.pstdev(o[0] for o in d) < 0.01 and statistics.pstdev(o[1] for o in d) < 0.01:
                    self.static_ex.append((sum(o[0] for o in d)/len(d), mcy, sum(o[2] for o in d)/len(d)))  # poster diam
                return True
        if len(self.track_obs) > 500: self.track_obs.clear()
        return False
    def _run(self):
        cfg = config.load()
        try:
            from ultralytics import YOLO
            mp = config.ROOT / cfg["model_path"]
            model = YOLO(str(mp) if mp.exists() else "yolov8n-pose.pt")
        except Exception as e:
            self.error = f"Gagal memuat model: {e}"; self.status = "error"; self.running = False; return
        cap = self._open(cfg)
        if not cap.isOpened():
            self.error = "Sumber video tidak dapat dibuka"; self.status = "error"; self.running = False; return
        self.track_obs = {}; self.excluded = set(); self.static_ex = []; self.votes = {}
        self.error = None; self.status = "running"; self.sid = db.start_session(cfg["source"]["type"]); i = 0
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                if cfg["source"]["type"] == "mp4": cap.set(cv2.CAP_PROP_POS_FRAMES, 0); continue
                self.status = "reconnecting"; cap.release(); time.sleep(2); cap = self._open(cfg); continue
            self.status = "running"; i += 1
            if i % cfg["process_every_n_frames"]: continue
            r = model.track(frame, persist=True, classes=[0], conf=cfg["person_conf"], verbose=False)[0]
            counts = {k: 0 for k in CATS}; pub = frame.copy(); adm = frame.copy()
            if r.boxes is not None and r.keypoints is not None:
                ids = r.boxes.id.int().cpu().tolist() if r.boxes.id is not None else [None]*len(r.boxes)
                for b, kp, tid in zip(r.boxes.xyxy.cpu().numpy(), r.keypoints.data.cpu().numpy(), ids):
                    x1, y1, x2, y2 = map(int, b)
                    c = classify(kp, cfg["keypoint_conf"])
                    if self._auto_excluded(tid, b, c, frame.shape[1], frame.shape[0], cfg):
                        cv2.rectangle(adm, (x1,y1), (x2,y2), (90,90,90), 1); cv2.putText(adm, "diabaikan (guru/poster)", (x1, max(12,y1-4)), 0, 0.45, (150,150,150), 1); continue
                    if tid is not None:  # smoothing: suara terbanyak dari 7 observasi terakhir per siswa
                        d = self.votes.setdefault(tid, deque(maxlen=7)); d.append(c); c = max(set(d), key=d.count)
                    counts[c] += 1
                    cv2.rectangle(adm, (x1,y1), (x2,y2), COLORS[c], 2); cv2.putText(adm, c, (x1, max(12,y1-4)), 0, 0.5, COLORS[c], 1)
            if len(self.votes) > 500: self.votes.clear()
            tot = sum(counts.values()); self.counts, self.total = counts, tot
            m = int(time.time()//60)
            if self._cur_min is not None and m != self._cur_min: self._flush()
            self._cur_min = m
            self._acc.append((counts.copy(), tot))
            self.history_live.append({"t": time.time(), "pct": self.snapshot()["pct"]})
            self.jpg_public = cv2.imencode(".jpg", pub)[1].tobytes(); self.jpg_admin = cv2.imencode(".jpg", adm)[1].tobytes()
        cap.release(); self._flush(); db.end_session(self.sid)
pipeline = Pipeline()
