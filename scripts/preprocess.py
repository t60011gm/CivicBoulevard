"""OSM (Overpass JSON) -> 以公尺為單位的區域平面座標 model.json
座標：以 (LAT0, LON0) 為原點的局部等距投影，X=東、Y=北，單位公尺（1 Blender unit = 1 m）。
"""
import json, math, sys, collections

SRC, DST = sys.argv[1], sys.argv[2]
LAT0, LON0 = 25.0450, 121.5390
R = 6378137.0
KX = math.radians(1) * R * math.cos(math.radians(LAT0))
KY = math.radians(1) * 6367449.0  # 子午線平均半徑


def xy(p):
    return (round((p['lon'] - LON0) * KX, 2), round((p['lat'] - LAT0) * KY, 2))


# 三個示範區（以經度切分，南北取同一範圍）
ZONES = [
    ('A_華山', 121.5220, 121.5338),
    ('B_市民八德', 121.5338, 121.5432),
    ('C_市民敦化', 121.5432, 121.5565),
]
LAT_S, LAT_N = 25.0405, 25.0495
ZX = [(n, (a - LON0) * KX, (b - LON0) * KX) for n, a, b in ZONES]
YS, YN = (LAT_S - LAT0) * KY, (LAT_N - LAT0) * KY

# 假設值（OSM 無實測資料者）
LEVEL_H = 3.3          # 每層樓高
DEFAULT_LEVELS = 4     # 無樓層資料之建物
DECK_H = {1: 10.5, 2: 15.5, 3: 22.0}   # 高架橋面高度（依 OSM layer；數值由街景照片比對鄰房樓層估計，誤差約 ±1.5 m）
FOOTBRIDGE_H = 5.5
RAMP_GRADE = 0.06

ROAD_W = {  # (單向, 雙向) 預設寬度 m
    'trunk': (10.5, 14), 'trunk_link': (5.5, 7), 'primary': (11, 18), 'primary_link': (5, 7),
    'secondary': (9, 14), 'secondary_link': (5, 7), 'tertiary': (7, 10), 'tertiary_link': (4.5, 6.5),
    'residential': (5, 6), 'unclassified': (5, 6), 'living_street': (4, 5), 'service': (3.5, 4),
    'busway': (3.5, 7), 'pedestrian': (4, 4), 'footway': (2, 2), 'path': (1.5, 1.5),
    'cycleway': (2, 2), 'steps': (2, 2),
}
VEHICLE = {'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary',
           'tertiary_link', 'residential', 'unclassified', 'living_street', 'service', 'busway'}


def fnum(s):
    try:
        return float(str(s).replace('m', '').split(';')[0].strip())
    except Exception:
        return None


def zone_of(x):
    for n, a, b in ZX:
        if a <= x < b:
            return n
    return None


def clip_axis(pts3, ax, a, b):
    """將 3D 折線依某軸範圍 [a,b) 切段"""
    res, cur = [], []
    for i in range(len(pts3) - 1):
        p, q = pts3[i], pts3[i + 1]
        d = q[ax] - p[ax]
        t0, t1 = 0.0, 1.0
        if abs(d) < 1e-9:
            if not (a <= p[ax] < b):
                t0 = 2
        else:
            ta, tb = (a - p[ax]) / d, (b - p[ax]) / d
            t0, t1 = max(t0, min(ta, tb)), min(t1, max(ta, tb))
        if t0 >= t1:
            if len(cur) > 1:
                res.append(cur)
            cur = []
            continue
        pa = tuple(p[k] + (q[k] - p[k]) * t0 for k in range(3))
        pb = tuple(p[k] + (q[k] - p[k]) * t1 for k in range(3))
        if not cur:
            cur = [pa]
        cur.append(pb)
        if t1 < 1.0:
            res.append(cur)
            cur = []
    if len(cur) > 1:
        res.append(cur)
    return res


def clip_line(pts, zs):
    """將折線依示範區矩形切段，回傳 {zone: [polyline,...]}"""
    out = collections.defaultdict(list)
    p3 = [(p[0], p[1], z) for p, z in zip(pts, zs)]
    for n, a, b in ZX:
        for ln in clip_axis(p3, 0, a, b):
            out[n] += clip_axis(ln, 1, YS, YN)
    return out


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def area(pts):
    s = 0
    for i in range(len(pts)):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return s / 2


def ring(geom):
    pts = [xy(p) for p in geom]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    # 去除連續重複點
    o = []
    for p in pts:
        if not o or p != o[-1]:
            o.append(p)
    if len(o) >= 3 and area(o) < 0:
        o.reverse()
    return o if len(o) >= 3 else None


def join_rings(members):
    """將 relation 的 outer way 片段接成封閉環"""
    segs = [[(p['lon'], p['lat']) for p in m['geometry']] for m in members
            if m.get('role') in ('outer', '') and m.get('type') == 'way' and m.get('geometry')]
    rings = []
    while segs:
        cur = segs.pop(0)
        changed = True
        while cur[0] != cur[-1] and changed:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == cur[-1]:
                    cur += s[1:]; segs.pop(i); changed = True; break
                if s[-1] == cur[-1]:
                    cur += s[-2::-1]; segs.pop(i); changed = True; break
        if cur[0] == cur[-1] and len(cur) >= 4:
            rings.append([{'lon': a, 'lat': b} for a, b in cur])
    return rings


d = json.load(open(SRC))
E = d['elements']
model = {n: collections.defaultdict(list) for n, _, _ in ZONES}
stats = collections.Counter()

# ---------- 建物 ----------
def add_building(tags, geom):
    r = ring(geom)
    if not r:
        return
    z = zone_of(centroid(r)[0])
    if not z or not (YS - 20 <= centroid(r)[1] <= YN + 20):
        return
    h = fnum(tags.get('height'))
    lv = fnum(tags.get('building:levels'))
    src = 'height'
    if h is None:
        if lv:
            h, src = lv * LEVEL_H, 'levels'
        else:
            h, src = DEFAULT_LEVELS * LEVEL_H, 'default'
    if tags.get('building') == 'roof':
        h = min(h, 5.0)
    stats['bld_' + src] += 1
    model[z]['buildings'].append({'name': tags.get('name', ''), 'h': round(h, 1), 'src': src,
                                  'levels': lv, 'kind': tags.get('building'), 'pts': r})


for e in E:
    t = e.get('tags', {})
    if 'building' not in t:
        continue
    if t.get('location') == 'underground' or (fnum(t.get('layer')) or 0) < 0:
        continue
    if e['type'] == 'way' and e.get('geometry'):
        add_building(t, e['geometry'])
    elif e['type'] == 'relation':
        for rg in join_rings(e.get('members', [])):
            add_building(t, rg)

# ---------- 面狀土地使用 ----------
AREA_KIND = [
    ('park', lambda t: t.get('leisure') in ('park', 'garden')),
    ('grass', lambda t: t.get('landuse') in ('grass', 'village_green', 'recreation_ground', 'meadow') or t.get('natural') in ('grassland', 'scrub', 'wood')),
    ('playground', lambda t: t.get('leisure') in ('playground', 'dog_park', 'fitness_station')),
    ('pitch', lambda t: t.get('leisure') in ('pitch', 'track', 'sports_centre') and 'building' not in t),
    ('parking', lambda t: t.get('amenity') in ('parking', 'motorcycle_parking', 'bicycle_parking') and t.get('parking') not in ('underground', 'multi-storey') and 'building' not in t),
    ('school', lambda t: t.get('amenity') in ('school', 'university', 'college', 'kindergarten') and 'building' not in t),
    ('construction', lambda t: t.get('landuse') in ('construction', 'brownfield')),
    ('site', lambda t: t.get('landuse') in ('industrial', 'retail') or t.get('amenity') in ('arts_centre', 'marketplace') and 'building' not in t),
    ('water', lambda t: t.get('natural') == 'water'),
    ('plaza', lambda t: t.get('highway') == 'pedestrian' and t.get('area') == 'yes'),
]


def add_area(tags, geom):
    for kind, f in AREA_KIND:
        if f(tags):
            r = ring(geom)
            if not r:
                return
            z = zone_of(centroid(r)[0])
            if z and YS - 20 <= centroid(r)[1] <= YN + 20:
                model[z]['areas'].append({'kind': kind, 'name': tags.get('name', ''), 'pts': r,
                                          'area': round(abs(area(r)))})
                stats['area_' + kind] += 1
            return


for e in E:
    t = e.get('tags', {})
    if 'building' in t:
        continue
    if e['type'] == 'way' and e.get('geometry') and len(e['geometry']) > 3 \
            and e['geometry'][0] == e['geometry'][-1]:
        add_area(t, e['geometry'])
    elif e['type'] == 'relation':
        for rg in join_rings(e.get('members', [])):
            add_area(t, rg)

# ---------- 道路 / 高架 ----------
ways = [e for e in E if e['type'] == 'way' and 'highway' in e.get('tags', {}) and e.get('nodes')
        and e.get('geometry') and e['tags'].get('area') != 'yes']
rails = [e for e in E if e['type'] == 'way' and e.get('tags', {}).get('railway') in ('subway', 'rail', 'light_rail')
         and e.get('geometry') and e.get('nodes')]


def is_bridge(t):
    return t.get('bridge') not in (None, 'no')


def is_tunnel(t):
    return t.get('tunnel') not in (None, 'no') or (fnum(t.get('layer')) or 0) < 0 or t.get('indoor') == 'yes'


def target_h(t):
    hw = t.get('highway') or 'rail'
    if hw in ('footway', 'steps', 'path', 'cycleway', 'pedestrian'):
        return FOOTBRIDGE_H
    L = int(fnum(t.get('layer')) or 1)
    return DECK_H.get(max(1, min(3, L)), 9.0)


# 節點高度：接觸到平面道路者為 0，否則取所接高架段目標高度平均
node_ground = set()
node_br = collections.defaultdict(list)
for w in ways + rails:
    t = w['tags']
    if is_tunnel(t):
        continue
    if is_bridge(t):
        for n in (w['nodes'][0], w['nodes'][-1]):
            node_br[n].append(target_h(t))
    else:
        for n in w['nodes']:
            node_ground.add(n)


def end_h(n, own):
    if n in node_ground:
        return 0.0
    v = node_br.get(n) or [own]
    return sum(v) / len(v)


def profile(w):
    t = w['tags']
    pts = [xy(p) for p in w['geometry']]
    if not is_bridge(t):
        return pts, [0.0] * len(pts)
    H = target_h(t)
    h1, h2 = end_h(w['nodes'][0], H), end_h(w['nodes'][-1], H)
    s = [0.0]
    for i in range(1, len(pts)):
        s.append(s[-1] + math.dist(pts[i - 1], pts[i]))
    Ltot = s[-1] or 1.0
    g = RAMP_GRADE if t.get('highway') not in ('footway', 'steps', 'path', 'cycleway', 'pedestrian') else 0.5
    zs = []
    for si in s:
        a, b = h1 + g * si, h2 + g * (Ltot - si)
        c, e2 = h1 - g * si, h2 - g * (Ltot - si)
        z = min(H, a, b) if (h1 <= H and h2 <= H) else max(min(H, a, b), min(max(H, c), max(H, e2)))
        zs.append(round(max(0.0, z), 2))
    return pts, zs


def subdivide(pts, zs, step=15.0):
    op, oz = [pts[0]], [zs[0]]
    for i in range(1, len(pts)):
        dd = math.dist(pts[i - 1], pts[i])
        k = max(1, int(dd // step))
        for j in range(1, k + 1):
            f = j / k
            op.append((pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f))
            oz.append(zs[i - 1] + (zs[i] - zs[i - 1]) * f)
    return op, oz


for w in ways:
    t = w['tags']
    hw = t['highway']
    if hw not in ROAD_W or is_tunnel(t) or hw == 'corridor':
        continue
    oneway = t.get('oneway') in ('yes', '-1') or t.get('junction') == 'roundabout'
    width = fnum(t.get('width'))
    lanes = fnum(t.get('lanes'))
    wsrc = 'width'
    if width is None:
        if lanes and hw in VEHICLE:
            width, wsrc = lanes * 3.25 + (1.0 if hw.startswith('trunk') else 0.5), 'lanes'
        else:
            width, wsrc = ROAD_W[hw][0 if oneway else 1], 'default'
    br = is_bridge(t)
    if hw in VEHICLE:
        cat = 'viaduct' if br else 'road'
    elif t.get('footway') == 'crossing' or t.get('highway') == 'crossing' or t.get('crossing'):
        cat = 'crossing'
    elif br:
        cat = 'footbridge'
    elif hw == 'cycleway':
        cat = 'cycleway'
    elif hw == 'steps':
        cat = 'steps'
    else:
        cat = 'footway'
    pts, zs = profile(w)
    if br:
        pts, zs = subdivide(pts, zs)
    for z, lines in clip_line(pts, zs).items():
        for ln in lines:
            if any(YS <= p[1] <= YN for p in ln):
                model[z][cat].append({'name': t.get('name', ''), 'hw': hw, 'w': round(width, 2), 'wsrc': wsrc,
                                      'lanes': lanes, 'layer': t.get('layer'),
                                      'pts': [[round(c, 2) for c in p] for p in ln]})
                stats[cat] += 1

for w in rails:
    t = w['tags']
    if is_tunnel(t) or not is_bridge(t):
        stats['rail_skipped_underground_or_grade'] += 1
        continue
    pts, zs = profile(w)
    pts, zs = subdivide(pts, zs)
    for z, lines in clip_line(pts, zs).items():
        for ln in lines:
            model[z]['rail_elevated'].append({'name': t.get('name', ''), 'hw': 'rail', 'w': 4.5, 'wsrc': 'default',
                                              'pts': [[round(c, 2) for c in p] for p in ln]})
            stats['rail_elevated'] += 1

# ---------- 點狀 ----------
for e in E:
    if e['type'] != 'node':
        continue
    t = e.get('tags', {})
    p = xy(e)
    z = zone_of(p[0])
    if not z:
        continue
    if t.get('natural') == 'tree':
        model[z]['trees'].append(p)
    elif t.get('railway') == 'subway_entrance':
        model[z]['subway_entrances'].append({'name': t.get('name', ''), 'ref': t.get('ref', ''), 'p': p})
    elif t.get('highway') == 'traffic_signals':
        model[z]['signals'].append(p)
    elif t.get('highway') == 'crossing':
        model[z]['crossing_nodes'].append(p)


# ---------- 橋下建物判定（市民大道高架投影範圍內） ----------
def seg_d(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


for zn in model:
    civ = [v for v in model[zn]['viaduct'] if '市民' in v['name'] and v['hw'] == 'trunk']
    tot = 0.0
    for b in model[zn]['buildings']:
        c = centroid(b['pts'])
        for v in civ:
            if any(seg_d(c, v['pts'][i], v['pts'][i + 1]) < v['w'] / 2 + 1.0 and
                   min(v['pts'][i][2], v['pts'][i + 1][2]) > 5 for i in range(len(v['pts']) - 1)):
                b['under'] = True
                if b['src'] == 'default' or b['h'] > 6.5:
                    b['h'], b['src'] = 4.5, 'under_viaduct_assumed'
                tot += abs(area(b['pts']))
                break
    n = sum(1 for b in model[zn]['buildings'] if b.get('under'))
    print(zn, '橋下建物', n, '棟, 投影面積 %.0f m2' % tot, [b['name'] for b in model[zn]['buildings'] if b.get('under') and b['name']])

# ---------- 尺寸驗證 ----------
def road_x(nm, ylo=-80, yhi=80):
    xs = [p[0] for zn in model for r in model[zn]['road'] if r['name'] == nm for p in r['pts'] if ylo < p[1] < yhi]
    return (min(xs) + max(xs)) / 2 if xs else None
for a, b in [('市民大道四段181巷', '延吉街'), ('復興南路一段', '延吉街'), ('復興南路一段', '敦化南路一段'), ('金山北路', '建國南路一段'), ('林森北路', '金山北路')]:
    xa, xb = road_x(a, -150, 150), road_x(b, -150, 150)
    print('距離', a, '->', b, None if xa is None or xb is None else round(abs(xb - xa)))
print([r['name'] for zn in model for r in model[zn]['road'] if '181' in r['name']][:3])

out = {
    'origin': {'lat': LAT0, 'lon': LON0},
    'zones': [{'name': n, 'x0': a, 'x1': b, 'y0': YS, 'y1': YN} for n, a, b in ZX],
    'assumptions': {'LEVEL_H': LEVEL_H, 'DEFAULT_LEVELS': DEFAULT_LEVELS, 'DECK_H': DECK_H,
                    'FOOTBRIDGE_H': FOOTBRIDGE_H},
    'data': model,
}
json.dump(out, open(DST, 'w'), ensure_ascii=False)
print(dict(stats))
for n, a, b in ZX:
    print(n, 'EW %.0f m' % (b - a), 'NS %.0f m' % (YN - YS), {k: len(v) for k, v in model[n].items()})

# 參考道路經度位置檢查
for nm in ['林森北路', '金山北路', '新生高架道路', '新生北路一段', '松江路', '建國高架道路', '建國南路一段', '復興南路一段', '復興北路',
           '敦化南路一段', '敦化北路', '延吉街', '市民大道四段181巷', '安東街', '渭水路', '八德路二段']:
    xs = [p['lon'] for w in ways if w['tags'].get('name') == nm for p in w['geometry'] if 25.0440 < p['lat'] < 25.0460]
    if xs:
        print(nm, round(min(xs), 5), round(max(xs), 5), 'x= %.0f..%.0f' % ((min(xs) - LON0) * KX, (max(xs) - LON0) * KX))
