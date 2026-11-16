"""把 Mapillary SfM 點雲轉成模型座標，輸出試驗路段的平面密度圖並與現有橋墩比對。
需 numpy（用 Blender 內建的 Python 執行）。資料來源 Mapillary，CC BY-SA。
用法：python scripts/mapillary_pilot.py x0 x1 y0 y1 out.png
"""
import glob, json, math, os, struct, sys, zlib
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(BASE, 'data', 'mapillary')
LAT0, LON0 = 25.0450, 121.5390
KX = 111319.49 * math.cos(math.radians(LAT0))
KY = 111133.0
X0, X1, Y0, Y1 = [float(v) for v in sys.argv[1:5]]
OUT = sys.argv[5]
RES = 0.2


def rot(R):
    th = np.linalg.norm(R)
    if th < 1e-9:
        return np.eye(3)
    k = R / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


P, CAM, info = [], [], []
for ci, f in enumerate(sorted(glob.glob(D + '/clusters/*.json'))):
    d = json.load(open(f))
    r = d[0] if isinstance(d, list) else d
    ref = r.get('reference_lla')
    if not ref or not r.get('points'):
        continue
    ox = (ref['longitude'] - LON0) * KX
    oy = (ref['latitude'] - LAT0) * KY
    cams = []
    for s in r['shots'].values():
        c = -rot(np.array(s['rotation'])).T @ np.array(s['translation'])
        cams.append((c[0] + ox, c[1] + oy, c[2], s.get('capture_time', 0)))
    cams = np.array(cams)
    inside = (cams[:, 0] > X0) & (cams[:, 0] < X1) & (cams[:, 1] > Y0) & (cams[:, 1] < Y1)
    if not inside.any():
        continue
    a = np.array([p['coordinates'] for p in r['points'].values()])
    a[:, 0] += ox
    a[:, 1] += oy
    m = (a[:, 0] > X0) & (a[:, 0] < X1) & (a[:, 1] > Y0) & (a[:, 1] < Y1)
    a = a[m]
    if len(a) < 200:
        continue
    camz = float(np.median(cams[inside, 2]))
    # 地面：相機下方 0.5–4 m 內最密的高度層
    below = a[(a[:, 2] < camz - 0.5) & (a[:, 2] > camz - 4.5), 2]
    if len(below) > 50:
        h, e = np.histogram(below, bins=40)
        g = float(e[h.argmax()] + (e[1] - e[0]) / 2)
    else:
        g = camz - 1.8
    yr = 1970 + int(np.median(cams[inside, 3])) // 31557600
    P.append(np.c_[a, np.full(len(a), g), np.full(len(a), ci)])
    CAM.append(np.c_[cams[inside, :3], np.full(inside.sum(), ci)])
    info.append((os.path.basename(f)[:-5], len(a), int(inside.sum()), camz - g, yr))
P = np.vstack(P)
CAM = np.vstack(CAM)
np.save(D + '/pilot_pts.npy', P)
print('clusters', len(info), 'points', len(P), 'cameras', len(CAM))
for i in sorted(info, key=lambda t: -t[1])[:14]:
    print('  %s pts %6d cams %3d cam-above-ground %.1f yr %d' % i)

W = int((X1 - X0) / RES)
H = int((Y1 - Y0) / RES)
img = np.full((H, W, 3), 255, np.uint8)


def px(x, y):
    return ((x - X0) / RES).astype(int), (H - 1 - (y - Y0) / RES).astype(int)


hz = P[:, 2] - P[:, 3]
for lo, hi, col in ((-0.5, 0.6, (225, 225, 225)), (1.2, 6.5, (40, 60, 150))):
    m = (hz > lo) & (hz < hi)
    i, j = px(P[m, 0], P[m, 1])
    ok = (i >= 0) & (i < W) & (j >= 0) & (j < H)
    img[j[ok], i[ok]] = col
i, j = px(CAM[:, 0], CAM[:, 1])
ok = (i >= 1) & (i < W - 1) & (j >= 1) & (j < H - 1)
for di in (-1, 0, 1):
    for dj in (-1, 0, 1):
        img[j[ok] + dj, i[ok] + di] = (60, 170, 60)

cor = json.load(open(os.path.join(BASE, 'web/data/corridor.json')))
cols = []
for q in cor['piers']:
    x, y = q['p']
    if not (X0 - 5 < x < X1 + 5):
        continue
    ca, sa = math.cos(q['a']), math.sin(q['a'])
    for o in q['offs']:
        cx, cy = x - sa * o, y + ca * o
        cols.append((cx, cy, q['cs'][0] / 2, q['r']))
        n = 80
        for t in range(n):
            a = 2 * math.pi * t / n
            for rr in (q['cs'][0] / 2, q['cs'][0] / 2 + RES):
                ii = int((cx + rr * math.cos(a) - X0) / RES)
                jj = int(H - 1 - (cy + rr * math.sin(a) - Y0) / RES)
                if 0 <= ii < W and 0 <= jj < H:
                    img[jj, ii] = (220, 30, 30)
# 每 20 m 格線刻度
for gx in np.arange(math.ceil(X0 / 20) * 20, X1, 20):
    ii = int((gx - X0) / RES)
    img[H - 12:H, ii] = (0, 0, 0)
    if gx % 100 == 0:
        img[H - 30:H, ii] = (0, 0, 0)

raw = b''.join(b'\x00' + img[r].tobytes() for r in range(H))


def chunk(t, d):
    return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))


open(OUT, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
                      + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))
print('png', OUT, W, H)

# 各模型柱位周圍 2.5 m 內、離地 1.2–6.5 m 的點數，以及點雲質心相對柱心的偏移
m = (hz > 1.2) & (hz < 6.5)
Q = P[m]
print('model columns in section', len(cols), '| mid-height points', len(Q))
for cx, cy, r, form in sorted(cols):
    dd = np.hypot(Q[:, 0] - cx, Q[:, 1] - cy)
    n1 = int((dd < r + 0.8).sum())
    near = Q[dd < 5.0]
    off = (near[:, :2].mean(0) - (cx, cy)) if len(near) > 20 else (float('nan'),) * 2
    print('  col x %8.1f y %6.1f r %.1f | pts within r+0.8: %4d | within 5 m: %4d centroid off (%.1f, %.1f) clusters %d' % (
        cx, cy, r, n1, len(near), off[0], off[1], len(set(near[:, 4])) if len(near) else 0))
