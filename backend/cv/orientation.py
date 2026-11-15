"""Klasifikasi orientasi BERBASIS ATURAN dari keypoint pose (YOLO-pose). HEURISTIK, bukan model terlatih; akurasi belum diuji.
Kamera di belakang siswa: 'depan' = kepala membelakangi kamera (menghadap papan)."""
CATS = ["depan", "belakang", "kanan", "kiri", "menunduk", "tidak_diketahui"]
def classify(kp, t):
    nose, le, re, lear, rear, ls, rs = kp[0], kp[1], kp[2], kp[3], kp[4], kp[5], kp[6]
    ts = min(t, 0.3)  # ambang bahu lebih longgar
    if ls[2] < ts or rs[2] < ts: return "tidak_diketahui"
    sw = abs(ls[0] - rs[0]) + 1e-6; sy = (ls[1] + rs[1]) / 2; cx = (ls[0] + rs[0]) / 2
    ears = [e for e in (lear, rear) if e[2] >= t]
    face_nose = nose[2] >= t; eyes = int(le[2] >= t) + int(re[2] >= t)
    if face_nose and eyes == 2: return "belakang"            # wajah menghadap kamera
    if face_nose and eyes == 1: return "kanan" if nose[0] > cx else "kiri"   # profil (arah di gambar)
    if face_nose: return "tidak_diketahui"
    # hidung tidak terlihat -> kepala membelakangi kamera
    if ears and sum(e[1] for e in ears)/len(ears) > sy - 0.2*sw: return "menunduk"
    if eyes == 0: return "depan"                              # telinga 0/1/2 terlihat tetap dianggap depan
    return "tidak_diketahui"
