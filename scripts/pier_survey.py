"""街景逐墩判讀：由各觀測點對同一根柱子的方位角交會出柱位（最小平方）。
觀測值為人工判讀（畫面像素換算方位），非批次擷取。"""
import json, math, os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAT0, LON0 = 25.0450, 121.5390
KX = 111319.49 * math.cos(math.radians(LAT0)); KY = 111133.0
F = 248.5  # 800x497 畫面、垂直視角 90° 的焦距（像素）

def brg(h, px): return h + math.degrees(math.atan((px - 400) / F))
def xy(lat, lon): return ((lon - LON0) * KX, (lat - LAT0) * KY)

def solve(obs):
    # obs: [(x, y, bearing_deg)] → 最小平方交會點與各射線殘差（公尺）
    a11 = a12 = a22 = b1 = b2 = 0.0
    for x, y, b in obs:
        nx, ny = math.cos(math.radians(b)), -math.sin(math.radians(b))  # 射線法向
        c = nx * x + ny * y
        a11 += nx * nx; a12 += nx * ny; a22 += ny * ny; b1 += nx * c; b2 += ny * c
    det = a11 * a22 - a12 * a12
    px, py = (a22 * b1 - a12 * b2) / det, (a11 * b2 - a12 * b1) / det
    res = [abs(math.cos(math.radians(b)) * (px - x) - math.sin(math.radians(b)) * (py - y)) for x, y, b in obs]
    return px, py, res

if __name__ == '__main__':
    S = json.load(open(os.path.join(BASE, 'data/survey', sys.argv[1])))
    P = {k: xy(*v) for k, v in S['panos'].items()}
    out = []
    for name, c in S['cols'].items():
        obs = [(P[k][0], P[k][1], brg(h, px)) for k, h, px in c['obs']]
        x, y, res = solve(obs)
        out.append({'id': name, 'p': [round(x, 1), round(y, 1)], 'n': len(obs), 'res': round(max(res), 2), **{k: v for k, v in c.items() if k != 'obs'}})
        print('%-5s x %8.1f y %6.1f  n %d  max residual %.2f m  %s' % (name, x, y, len(obs), max(res), c.get('note', '')))
    json.dump(out, open(os.path.join(BASE, 'data/survey', sys.argv[1].replace('.json', '_result.json')), 'w'), ensure_ascii=False, indent=1)
