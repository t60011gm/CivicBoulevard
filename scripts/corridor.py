"""市民大道廊道細部建模：連續的高架主線、匝道、平面車道、人行道、分隔島與地下停車場車道。
輸入 data/osm.json、data/model.json；輸出 web/data/corridor.json。
執行順序：preprocess.py → corridor.py → make_overlay.py。

做法重點
- 主線：把同方向的 OSM 路段依節點串成一條連續折線，每 5 m 取樣；高度取各段目標高度的坡度限制包絡（不再逐段各自建模，
  也不依示範區切開，避免接頭出現缺口）；寬度在車道數改變處漸變；兩方向相鄰且同高時，內緣在中線相接成為一片橋面。
- 匝道：由主線節點沿 trunk_link 路段展開，節點高度以主線高度、地面 0 為錨點，其餘依路段長度內插。
- 平面車道、人行道、分隔島：沿市民大道平面路段取樣；人行道寬度取車道外緣到最近建物的距離（上限 5 m），非實測。
- 地下停車場車道：位置取自 OSM 的 parking_entrance 節點，形式依街景判讀，方向為朝該停車場中心推定。
"""
import json, math, os, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = json.load(open(os.path.join(BASE, 'data/osm.json')))['elements']
M = json.load(open(os.path.join(BASE, 'data/model.json')))
LAT0, LON0 = M['origin']['lat'], M['origin']['lon']
KX = math.radians(1) * 6378137.0 * math.cos(math.radians(LAT0))
KY = math.radians(1) * 6367449.0
XA, XB = M['zones'][0]['x0'], M['zones'][-1]['x1']
YA, YB = M['zones'][0]['y0'], M['zones'][0]['y1']
DECK_H = {int(k): v for k, v in M['assumptions']['DECK_H'].items()}
GD, GRADE, STEP = 2.3, 0.035, 5.0
COL_D = 2.7
PIER_FORM = [(-9999, -1250, 1, 0), (-1250, -600, 0, 0), (-600, 420, 0, 9.0), (420, 650, 1, 0),
             (650, 820, 1, 9.0), (820, 1300, 1, 0), (1300, 1480, 1, 9.0), (1480, 9999, 1, 0)]
# 地下停車場車道口：(x, 坡道下降方向)。位置取自 OSM，方向為朝停車場中心推定
UG_ENT = [(-1601, 1), (664, 1), (862, -1), (954, -1), (1118, 1), (1349, 1)]


def xy(p):
    return ((p['lon'] - LON0) * KX, (p['lat'] - LAT0) * KY)


def isbr(t):
    return t.get('bridge') not in (None, 'no')


def fnum(v, d=None):
    try:
        return float(str(v).split(';')[0])
    except Exception:
        return d


ways = [e for e in E if e['type'] == 'way' and 'highway' in e.get('tags', {}) and e.get('nodes') and e.get('geometry')]
for w in ways:
    w['pts'] = [xy(p) for p in w['geometry']]
node_ways = collections.defaultdict(list)
for w in ways:
    for n in w['nodes']:
        node_ways[n].append(w)

strips, boxes, piers, centers = [], [], [], []


def R2(v):
    return round(v, 2)


def add_strip(L, Rr, t, role):
    if len(L) >= 2:
        strips.append({'L': [[R2(a), R2(b), R2(c)] for a, b, c in L], 'R': [[R2(a), R2(b), R2(c)] for a, b, c in Rr], 't': R2(t), 'r': role})


def add_box(x, y, sx, sy, z0, z1, a, role):
    boxes.append({'c': [R2(x), R2(y)], 's': [R2(sx), R2(sy)], 'z': [R2(z0), R2(z1)], 'a': round(a, 3), 'r': role})


# ---------- 折線工具 ----------
def resample(pts, vals, step=STEP):
    """pts: [(x,y)]；vals: 每個頂點的屬性 tuple（取所在線段起點的值）。回傳 [(x,y,s,vals)]"""
    out, acc, s_next, s_tot = [], 0.0, 0.0, 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = math.dist(a, b)
        while s_next <= acc + seg + 1e-9:
            t = (s_next - acc) / seg if seg else 0
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, s_next, vals[i]))
            s_next += step
        acc += seg
    if out and math.dist(out[-1][:2], pts[-1]) > 0.5:
        out.append((pts[-1][0], pts[-1][1], acc, vals[-1]))
    return out


def frames(S):
    """每個取樣點的切線與左法線"""
    fr = []
    n = len(S)
    for i in range(n):
        a, b = S[max(i - 1, 0)], S[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        l = math.hypot(dx, dy) or 1
        fr.append((dx / l, dy / l, -dy / l, dx / l))
    return fr


def chain_ways(ws):
    first = {}
    for w in ws:
        first.setdefault(w['nodes'][0], w)
    lasts = {w['nodes'][-1] for w in ws}
    used, chains = set(), []
    starts = [w for w in ws if w['nodes'][0] not in lasts] or ws[:1]
    for st in starts + ws:
        if st['id'] in used:
            continue
        c = [st]
        used.add(st['id'])
        while c[-1]['nodes'][-1] in first and first[c[-1]['nodes'][-1]]['id'] not in used:
            c.append(first[c[-1]['nodes'][-1]])
            used.add(c[-1]['id'])
        chains.append(c)
    return chains


def in_box(p, m=0.0):
    return XA - m <= p[0] <= XB + m and YA - m <= p[1] <= YB + m


def clip_run(S):
    """只留在廊道範圍內的最長連續段"""
    best, cur = [], []
    for q in S:
        if in_box(q):
            cur.append(q)
        else:
            if len(cur) > len(best):
                best = cur
            cur = []
    return cur if len(cur) > len(best) else best


# ---------- 橫交道路（用來讓橋墩、分隔島、人行道讓開路口） ----------
cross = [(r['pts'], r['w']) for z in M['data'].values() for r in z['road']
         if r['hw'] in ('primary', 'secondary', 'tertiary') and not r['name'].startswith('市民大道')]


def seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


CG = collections.defaultdict(list)
for pts, w in cross:
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        for gx in range(int(min(a[0], b[0]) // 40) - 1, int(max(a[0], b[0]) // 40) + 2):
            for gy in range(int(min(a[1], b[1]) // 40) - 1, int(max(a[1], b[1]) // 40) + 2):
                CG[(gx, gy)].append((a, b, w))


def on_cross(p, extra=2.0):
    return any(seg_d(p, a, b) < w / 2 + extra for a, b, w in CG.get((int(p[0] // 40), int(p[1] // 40)), ()))


BG = collections.defaultdict(list)
for z in M['data'].values():
    for b in z['buildings']:
        pts = b['pts']
        for i in range(len(pts)):
            a, c = pts[i], pts[(i + 1) % len(pts)]
            for gx in range(int(min(a[0], c[0]) // 20), int(max(a[0], c[0]) // 20) + 1):
                for gy in range(int(min(a[1], c[1]) // 20), int(max(a[1], c[1]) // 20) + 1):
                    BG[(gx, gy)].append((a, c))


def d_building(p, cap=12.0):
    best = cap
    gx, gy = int(p[0] // 20), int(p[1] // 20)
    for ix in (gx - 1, gx, gx + 1):
        for iy in (gy - 1, gy, gy + 1):
            for a, c in BG.get((ix, iy), ()):
                best = min(best, seg_d(p, a, c))
    return best


# =====================================================================
# 1. 高架主線
# =====================================================================
mains = [w for w in ways if w['tags']['highway'] == 'trunk' and '市民' in w['tags'].get('name', '')]
MAIN = []           # 每條鏈：取樣點 dict
main_node_z = {}
for ci, ch in enumerate(chain_ways(mains)):
    pts, vals, node_s = [], [], {}
    acc = 0.0
    for w in ch:
        t = w['tags']
        H = DECK_H.get(int(fnum(t.get('layer'), 1)), DECK_H[1])
        Wd = (fnum(t.get('lanes'), 3) or 3) * 3.5 + 1.5
        p = w['pts'] if not pts else w['pts'][1:]
        nd = w['nodes'] if not pts else w['nodes'][1:]
        for q, n in zip(p, nd):
            if pts:
                acc += math.dist(pts[-1], q)
            pts.append(q)
            vals.append((H, Wd))
            node_s[n] = acc
        centers.append([[R2(a), R2(b)] for a, b in w['pts']])
    S = resample(pts, vals)
    n = len(S)
    Hs = [q[3][0] for q in S]
    ss = [q[2] for q in S]
    zs = [min(Hs[j] + GRADE * abs(ss[i] - ss[j]) for j in range(max(0, i - 60), min(n, i + 61))) for i in range(n)]
    Ws = [q[3][1] for q in S]
    Ws = [sum(Ws[max(0, i - 4):i + 5]) / len(Ws[max(0, i - 4):i + 5]) for i in range(n)]
    full = [{'x': S[i][0], 'y': S[i][1], 's': ss[i], 'z': zs[i], 'w': Ws[i]} for i in range(n)]
    for nid, s in node_s.items():
        k = min(range(n), key=lambda i: abs(ss[i] - s))
        main_node_z[nid] = zs[k]
    run = clip_run([(q['x'], q['y'], q) for q in full])
    if len(run) > 3:
        MAIN.append([q[2] for q in run])

for ch in MAIN:
    fr = frames([(q['x'], q['y']) for q in ch])
    for q, f in zip(ch, fr):
        q['t'] = f

ALLM = [(q, ci) for ci, ch in enumerate(MAIN) for q in ch]


def civic_mid(x):
    near = [q for q, _ in ALLM if abs(q['x'] - x) < 25] or [min((q for q, _ in ALLM), key=lambda q: abs(q['x'] - x))]
    return sum(q['y'] for q in near) / len(near)


def nearest_other(q, ci):
    best, bd = None, 1e9
    for o, cj in ALLM:
        if cj != ci and abs(o['x'] - q['x']) < 40:
            d = math.hypot(o['x'] - q['x'], o['y'] - q['y'])
            if d < bd:
                best, bd = o, d
    return best, bd


for ci, ch in enumerate(MAIN):
    for q in ch:
        o, d = nearest_other(q, ci)
        half = q['w'] / 2
        q['oL'], q['oR'], q['merged'], q['inner'] = half, half, False, 0
        if o is not None:
            side = 1 if (q['t'][2] * (o['x'] - q['x']) + q['t'][3] * (o['y'] - q['y'])) > 0 else -1
            q['inner'] = side
            if d < (q['w'] + o['w']) / 2 + 4 and abs(q['z'] - o['z']) < 1.5:
                inn = max(half - 1.5, min(d / 2, half + 2.5))
                q['merged'] = True
                if side > 0:
                    q['oL'] = inn
                else:
                    q['oR'] = inn


def off(q, d, dz=0.0):
    return (q['x'] + q['t'][2] * d, q['y'] + q['t'][3] * d, q['z'] + dz)


def runs(ch, pred):
    out, cur = [], []
    for q in ch:
        if pred(q):
            cur.append(q)
        else:
            if len(cur) > 1:
                out.append(cur)
            cur = []
    if len(cur) > 1:
        out.append(cur)
    return out


for ci, ch in enumerate(MAIN):
    add_strip([off(q, q['oL']) for q in ch], [off(q, -q['oR']) for q in ch], 0.35, 'deck')
    add_strip([off(q, q['oL'] * .55, -.35) for q in ch], [off(q, -q['oR'] * .55, -.35) for q in ch], GD - .35, 'girder')
    for side in (1, -1):
        def edge(q, s=side):
            return q['oL'] if s > 0 else q['oR']
        # 外緣：護欄＋隔音牆；內緣未相接處：護欄；相接處：只由第一條鏈畫中央護欄
        for rn in runs(ch, lambda q, s=side: not (q['merged'] and q['inner'] == s)):
            add_strip([off(q, side * edge(q), 1.0) for q in rn], [off(q, side * (edge(q) - .4), 1.0) for q in rn], 1.0, 'parapet')
        for rn in runs(ch, lambda q, s=side: q['inner'] != s):
            add_strip([off(q, side * edge(q), 3.2) for q in rn], [off(q, side * (edge(q) - .15), 3.2) for q in rn], 2.2, 'nwall')
        if ci == 0:
            for rn in runs(ch, lambda q, s=side: q['merged'] and q['inner'] == s):
                add_strip([off(q, side * (edge(q) + .25), .9) for q in rn], [off(q, side * (edge(q) - .25), .9) for q in rn], .9, 'parapet')

# 主線橋墩：沿第一條鏈每 30 m 一排；另一方向若離得遠則各自落墩


def pier_form(x):
    for a, b, rnd, gap in PIER_FORM:
        if a <= x < b:
            return rnd, gap
    return 1, 0


def put_pier(x, y, ang, top, span, single_w=None):
    if top < 4.5 or on_cross((x, y), 2.0):
        return
    rnd, gap = pier_form(x)
    if single_w is not None:
        gap = 0
    piers.append({'p': [R2(x), R2(y)], 'a': round(ang, 3), 'top': R2(top), 'cap': R2(max(span, gap + 5)), 'r': rnd, 'g': gap})


done_far = set()
for ci, ch in enumerate(MAIN):
    nxt = 15.0
    s0 = ch[0]['s']
    for q in ch:
        if q['s'] - s0 < nxt:
            continue
        nxt += 30.0
        ang = math.atan2(q['t'][1], q['t'][0])
        o, d = nearest_other(q, ci)
        if o is not None and d < (q['w'] + o['w']) / 2 + 8:
            if ci == 0 or ALLM and min(ci, [cj for oo, cj in ALLM if oo is o][0]) == ci:
                put_pier((q['x'] + o['x']) / 2, (q['y'] + o['y']) / 2, ang, min(q['z'], o['z']) - GD, d + max(q['w'], o['w']) * .8)
        else:
            put_pier(q['x'], q['y'], ang, q['z'] - GD, q['w'] * .8, single_w=q['w'])

# =====================================================================
# 2. 匝道
# =====================================================================
links = [w for w in ways if w['tags']['highway'] == 'trunk_link']
sel, frontier = {}, [w for w in links if any(n in main_node_z for n in w['nodes'])]
while frontier:
    w = frontier.pop()
    if w['id'] in sel:
        continue
    sel[w['id']] = w
    for n in (w['nodes'][0], w['nodes'][-1]):
        for v in node_ways[n]:
            if v['tags']['highway'] == 'trunk_link' and v['id'] not in sel:
                frontier.append(v)
sel = {k: w for k, w in sel.items() if any(in_box(p, 5) for p in w['pts'])}

nz, fixed = {}, set()
for w in sel.values():
    for n in w['nodes']:
        if n in main_node_z:
            nz[n] = main_node_z[n]
            fixed.add(n)
            continue
        if not isbr(w['tags']):
            nz[n] = 0.0
            fixed.add(n)
            continue
        for v in node_ways[n]:
            vt = v['tags']
            if v['id'] in sel:
                continue
            if vt['highway'] == 'trunk' and isbr(vt):
                nz[n] = DECK_H.get(int(fnum(vt.get('layer'), 1)), DECK_H[1])
                fixed.add(n)
            elif not isbr(vt) and vt.get('tunnel') in (None, 'no') and n not in fixed:
                nz[n] = 0.0
                fixed.add(n)
adj = collections.defaultdict(list)
for w in sel.values():
    for i in range(len(w['nodes']) - 1):
        a, b = w['nodes'][i], w['nodes'][i + 1]
        l = math.dist(w['pts'][i], w['pts'][i + 1]) or .1
        adj[a].append((b, l))
        adj[b].append((a, l))
for n in adj:
    nz.setdefault(n, 6.0)
for _ in range(600):
    for n in adj:
        if n not in fixed:
            ws_ = sum(1 / l for _, l in adj[n])
            nz[n] = sum(nz[m] / l for m, l in adj[n]) / ws_

for w in sel.values():
    t = w['tags']
    Wd = (fnum(t.get('lanes'), 1) or 1) * 3.5 + 1.5
    S = resample(w['pts'], list(range(len(w['pts']))))
    # 每個取樣點的高度：依所在線段兩端節點內插
    cum = [0.0]
    for i in range(1, len(w['pts'])):
        cum.append(cum[-1] + math.dist(w['pts'][i - 1], w['pts'][i]))
    out = []
    for x, y, s, i in S:
        j = min(i + 1, len(w['pts']) - 1)
        seg = (cum[j] - cum[i]) or 1
        f = max(0, min(1, (s - cum[i]) / seg))
        z = nz[w['nodes'][i]] * (1 - f) + nz[w['nodes'][j]] * f
        out.append({'x': x, 'y': y, 's': s, 'z': z, 'w': Wd})
    out = [q for q in out if in_box((q['x'], q['y']))]
    if len(out) < 2:
        continue
    centers.append([[R2(a), R2(b)] for a, b in w['pts']])
    for q, f in zip(out, frames([(q['x'], q['y']) for q in out])):
        q['t'] = f
    h = Wd / 2
    if not isbr(t):
        add_strip([(q['x'] + q['t'][2] * h, q['y'] + q['t'][3] * h, .17) for q in out], [(q['x'] - q['t'][2] * h, q['y'] - q['t'][3] * h, .17) for q in out], .17, 'croad')
        continue
    add_strip([off(q, h) for q in out], [off(q, -h) for q in out], .35, 'deck')
    for rn in runs(out, lambda q: q['z'] >= 4.6):
        add_strip([off(q, h * .55, -.35) for q in rn], [off(q, -h * .55, -.35) for q in rn], GD - .35, 'girder')
    for rn in runs(out, lambda q: q['z'] < 4.8):       # 接地段：擋土牆式引道，橋面下方填實
        L_ = [(q['x'] + q['t'][2] * h, q['y'] + q['t'][3] * h, max(q['z'] - .35, .05)) for q in rn]
        R_ = [(q['x'] - q['t'][2] * h, q['y'] - q['t'][3] * h, max(q['z'] - .35, .05)) for q in rn]
        strips.append({'L': [[R2(a), R2(b), R2(c)] for a, b, c in L_], 'R': [[R2(a), R2(b), R2(c)] for a, b, c in R_], 't': -1, 'r': 'rampfill'})
    for side in (1, -1):
        add_strip([off(q, side * h, 1.0) for q in out], [off(q, side * (h - .35), 1.0) for q in out], 1.0, 'parapet')
    nxt = 12.0
    for q in out:
        if q['s'] >= nxt:
            nxt += 25.0
            if q['z'] >= 4.8 and not on_cross((q['x'], q['y']), 1.5):
                add_box(q['x'], q['y'], 1.6, min(Wd * .4, 3), 0, q['z'] - GD, math.atan2(q['t'][1], q['t'][0]), 'pier')

# =====================================================================
# 3. 平面車道、標線、人行道、分隔島
# =====================================================================
surf = [w for w in ways if w['tags'].get('name', '').startswith('市民大道') and '巷' not in w['tags']['name']
        and w['tags']['highway'] in ('tertiary', 'tertiary_link') and not isbr(w['tags'])]
SURF = []
for ch in chain_ways(surf):
    pts, vals = [], []
    for w in ch:
        lanes = fnum(w['tags'].get('lanes'), 2) or 2
        p = w['pts'] if not pts else w['pts'][1:]
        pts += p
        vals += [(lanes, w['tags']['highway'])] * len(p)
        centers.append([[R2(a), R2(b)] for a, b in w['pts']])
    S = clip_run([(x, y, (s, v)) for x, y, s, v in resample(pts, vals)])
    if len(S) < 2:
        continue
    out = [{'x': x, 'y': y, 's': sv[0], 'lanes': sv[1][0], 'w': sv[1][0] * 3.25 + .5, 'link': sv[1][1] == 'tertiary_link'} for x, y, sv in S]
    for q, f in zip(out, frames([(q['x'], q['y']) for q in out])):
        q['t'] = f
        q['z'] = 0.0
    SURF.append(out)

ALLS = [(q, ci) for ci, ch in enumerate(SURF) for q in ch if not q['link']]
SG = collections.defaultdict(list)
for q, ci in ALLS:
    SG[int(q['x'] // 30)].append((q, ci))

n_walk = 0
for ci, ch in enumerate(SURF):
    add_strip([off(q, q['w'] / 2, .17) for q in ch], [off(q, -q['w'] / 2, .17) for q in ch], .17, 'croad')
    if ch[0]['link']:
        continue
    for side in (1, -1):
        add_strip([off(q, side * (q['w'] / 2 - .2), .19) for q in ch], [off(q, side * (q['w'] / 2 - .35), .19) for q in ch], .02, 'mark')
    # 車道線：虛線 4 m 線段、6 m 間隔
    i = 0
    while i + 1 < len(ch):
        q0, q1 = ch[i], ch[i + 1]
        for k in range(1, int(q0['lanes'])):
            o = -q0['w'] / 2 + .25 + k * (q0['w'] - .5) / q0['lanes']
            add_strip([off(q0, o + .07, .19), off(q1, o + .07, .19)], [off(q0, o - .07, .19), off(q1, o - .07, .19)], .02, 'mark')
        i += 2
    # 外側人行道
    for q in ch:
        out_side = 1 if q['t'][3] * (q['y'] - civic_mid(q['x'])) > 0 else -1
        q['out'] = out_side
        e = off(q, out_side * q['w'] / 2)
        db = d_building(e)
        q['sw'] = 0.0 if on_cross(e[:2], 1.0) else max(0.0, min(db - .3, 5.0))
    for rn in runs(ch, lambda q: q['sw'] >= 1.2):
        add_strip([off(q, q['out'] * q['w'] / 2, .32) for q in rn], [off(q, q['out'] * (q['w'] / 2 + q['sw']), .32) for q in rn], .32, 'walk')
        add_strip([off(q, q['out'] * q['w'] / 2, .34) for q in rn], [off(q, q['out'] * (q['w'] / 2 + .2), .34) for q in rn], .04, 'curb')
        n_walk += 1
    # 分隔島：只由往東的車道負責畫，避免重複
    if ch[len(ch) // 2]['t'][0] <= 0:
        continue
    isl = []
    for q in ch:
        best, bd = None, 1e9
        for gx in (int(q['x'] // 30) - 1, int(q['x'] // 30), int(q['x'] // 30) + 1):
            for o, cj in SG.get(gx, ()):
                if cj != ci and o['t'][0] * q['t'][0] + o['t'][1] * q['t'][1] < -0.5:
                    d = math.hypot(o['x'] - q['x'], o['y'] - q['y'])
                    if d < bd and (o['x'] - q['x']) * q['t'][2] * -q['out'] + (o['y'] - q['y']) * q['t'][3] * -q['out'] > 0:
                        best, bd = o, d
        q['isl'] = None
        if best is not None and bd < 45:
            gap = bd - q['w'] / 2 - best['w'] / 2
            mid = ((q['x'] + best['x']) / 2, (q['y'] + best['y']) / 2)
            if gap > 1.5 and not on_cross(mid, 3.0):
                ux, uy = (best['x'] - q['x']) / bd, (best['y'] - q['y']) / bd
                h = gap / 2 - .3
                q['isl'] = ((mid[0] - ux * h, mid[1] - uy * h, .26), (mid[0] + ux * h, mid[1] + uy * h, .26))
    for rn in runs(ch, lambda q: q.get('isl') is not None):
        add_strip([q['isl'][0] for q in rn], [q['isl'][1] for q in rn], .26, 'island')
        isl.append(rn)

# =====================================================================
# 4. 地下停車場車道
# =====================================================================
for x0, dr in UG_ENT:
    pts = []
    for k in range(0, 46, 5):
        x = x0 + dr * k
        y0, y1 = civic_mid(x - 5), civic_mid(x + 5)
        a = math.atan2(y1 - y0, 10)
        pts.append((x + math.sin(a) * 3.5, civic_mid(x) - math.cos(a) * 3.5, a))
    fr = frames([(p[0], p[1]) for p in pts])
    Q = [{'x': p[0], 'y': p[1], 'z': 0.0, 't': f} for p, f in zip(pts, fr)]
    add_strip([off(q, 2.5, .36) for q in Q], [off(q, -2.5, .36) for q in Q], .08, 'ugramp')
    for side in (1, -1):
        add_strip([off(q, side * 2.85, 1.3) for q in Q], [off(q, side * 2.55, 1.3) for q in Q], 1.0, 'ugwall')
    add_box(Q[-1]['x'], Q[-1]['y'], 7, 6.2, .3, 3.2, pts[-1][2], 'ugportal')
    add_box(Q[0]['x'] - dr * 3, Q[0]['y'], 2.2, 2.2, .3, 2.9, pts[0][2], 'kiosk')

json.dump({'strips': strips, 'boxes': boxes, 'piers': piers, 'centers': centers, 'girder': GD,
           'ug': [{'x': x, 'dir': d} for x, d in UG_ENT]},
          open(os.path.join(BASE, 'web/data/corridor.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
by = collections.Counter(s['r'] for s in strips)
print('main chains', [(len(c), round(c[0]['x']), round(c[-1]['x'])) for c in MAIN])
print('links', len(sel), 'surface chains', len(SURF), 'sidewalk runs', n_walk)
print('strips', dict(by), 'boxes', len(boxes), 'piers', len(piers))
print('size', os.path.getsize(os.path.join(BASE, 'web/data/corridor.json')))
zs = [q['z'] for c in MAIN for q in c]
print('main z range', round(min(zs), 1), round(max(zs), 1), 'merged share', round(sum(q['merged'] for c in MAIN for q in c) / len(zs), 2))
