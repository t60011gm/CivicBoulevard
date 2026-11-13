"""由 data/model.json 產生網站用資料：web/data/scene.json（現況）與 web/data/overlay.json（提案示意量體、標註、統計）。
提案量體的「位置與尺寸」是依政策文字在模型上推估的示意，並非官方設計圖。
"""
import json, math, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = json.load(open(os.path.join(BASE, 'data/model.json')))
D = M['data']
OUT = os.path.join(BASE, 'web/data')
os.makedirs(OUT, exist_ok=True)

# ---------- 市民大道高架中心線 / 橋面高 ----------
civ_pts = sorted(p for z in D for v in D[z]['viaduct'] if '市民' in v['name'] and v['hw'] == 'trunk' for p in v['pts'])
surf_pts = [p for z in D for r in D[z]['road'] if r['name'].startswith('市民大道') and '巷' not in r['name'] for p in r['pts']]


def near(x, pts, win=22):
    return [p for p in pts if abs(p[0] - x) < win]


def civic_y(x):
    n = near(x, civ_pts) or near(x, civ_pts, 60)
    return sum(p[1] for p in n) / len(n)


def deck_z(x):
    n = near(x, civ_pts) or near(x, civ_pts, 60)
    return min(p[2] for p in n)


def deck_halfwidth(x):
    n = near(x, civ_pts) or near(x, civ_pts, 60)
    ys = [p[1] for p in n]
    return (max(ys) - min(ys)) / 2 + 5.4


def median_width(x):
    """平面車道（兩方向中心線）之間扣掉車道後的橋下帶寬估計"""
    n = near(x, surf_pts, 30)
    if len(n) < 2:
        return None
    ys = [p[1] for p in n]
    return max(0.0, (max(ys) - min(ys)) - 7.0)


def line_along(x0, x1, off=0.0, step=10.0):
    pts = []
    x = x0
    while x < x1 + 1e-6:
        # 法向偏移（近似：中心線近東西向）
        y0, y1 = civic_y(x - 5), civic_y(x + 5)
        ang = math.atan2(y1 - y0, 10)
        pts.append([round(x - math.sin(ang) * off, 1), round(civic_y(x) + math.cos(ang) * off, 1)])
        x += step
    return pts


def plen(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


GIRDER = 2.3   # 橋面到梁底（街景估計）
# 街景抽樣判讀的橋下中央分隔帶現況：(x, 類型, 補充)
OBS_T = {'parking': ('橋下平面收費停車場', 0), 'green': ('植栽綠帶', 0), 'uturn': ('植栽綠帶與迴轉道', 0),
         'open': ('路口淨空', 0), 'ug': ('地下停車場出入口與梯廳', 0)}
OBS = [(-1562, 'green', '林森北路口，有通風設施'), (-1400, 'parking', ''), (-1150, 'green', '路口旁'), (-900, 'uturn', ''),
       (-450, 'open', '新生北路、松江路口'), (-250, 'open', '建國高架下方路口'), (100, 'parking', ''), (600, 'uturn', ''),
       (850, 'ug', '市民地下停車場'), (1250, 'ug', '')]

P = []


# ---------- 行穿線統計（市民大道平面車道上） ----------
stats = {}
for Z in M['zones']:
    zn = Z['name']
    civr = [p for r in D[zn]['road'] if r['name'].startswith('市民大道') and '巷' not in r['name'] for p in r['pts']]
    xs = sorted(r['pts'][len(r['pts']) // 2][0] for r in D[zn]['crossing']
                if any(math.dist(r['pts'][len(r['pts']) // 2][:2], q[:2]) < 14 for q in civr))
    cl = []
    for x in xs:
        if cl and x - cl[-1][-1] < 40:
            cl[-1].append(x)
        else:
            cl.append([x])
    cx = [sum(c) / len(c) for c in cl]
    gaps = [cx[i + 1] - cx[i] for i in range(len(cx) - 1)]
    gi = gaps.index(max(gaps))
    b = D[zn]['buildings']
    stats[zn] = {
        'ew': round(Z['x1'] - Z['x0']), 'buildings': len(b),
        'bld_known': sum(1 for x in b if x['src'] != 'default'),
        'cross_n': len(cx), 'gap_avg': round(sum(gaps) / len(gaps)), 'gap_max': round(max(gaps)),
        'gap_max_at': [round(cx[gi]), round(cx[gi + 1])], 'cross_x': [round(c) for c in cx],
        'footbridges': len(D[zn].get('footbridge', [])), 'metro': len(D[zn].get('subway_entrances', [])),
    }
    # 最大間距的標示線
    stats[zn]['gap_line'] = [[round(cx[gi]), round(civic_y(cx[gi]))], [round(cx[gi + 1]), round(civic_y(cx[gi + 1]))]]

# ---------- 標註 ----------
labels = []
KEY = ['華山', '三創', '光華', '忠泰', '啤酒', '八德市場', '微風', 'SOGO']
seen = set()
for zn in D:
    for a in D[zn]['areas']:
        if a['name'] and a['area'] > 2500 and a['name'] not in seen and a['kind'] in ('park', 'site', 'playground'):
            seen.add(a['name'])
            labels.append({'t': a['name'], 'p': [round(sum(p[0] for p in a['pts']) / len(a['pts'])),
                                                 round(sum(p[1] for p in a['pts']) / len(a['pts'])), 6], 'k': 'place'})
    for b in D[zn]['buildings']:
        if b['name'] and any(k in b['name'] for k in KEY) and b['name'] not in seen and '換氣' not in b['name']:
            seen.add(b['name'])
            labels.append({'t': b['name'], 'p': [round(sum(p[0] for p in b['pts']) / len(b['pts'])),
                                                 round(sum(p[1] for p in b['pts']) / len(b['pts'])), b['h'] + 4], 'k': 'place'})
    best = {}
    for r in D[zn]['road']:
        if r['name'] and r['hw'] in ('primary', 'secondary', 'tertiary') and '巷' not in r['name']:
            ln = plen([p[:2] for p in r['pts']])
            if ln > best.get(r['name'], (0,))[0]:
                best[r['name']] = (ln, r['pts'][len(r['pts']) // 2])
    for nm, (ln, p) in best.items():
        if ln > 90 and nm not in seen:
            seen.add(nm)
            labels.append({'t': nm, 'p': [round(p[0]), round(p[1]), 3], 'k': 'road'})
labels.append({'t': '忠泰美術館', 'p': [-182, -89, 44], 'k': 'place'})
labels.append({'t': '懷生國小（位置推估）', 'p': [168, -200, 8], 'k': 'place'})



# ---------- 高架橋體細部（街景判讀參數） ----------
def offset_line(pts, d):
    out = []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]; l = math.hypot(dx, dy) or 1
        nx, ny = -dy / l, dx / l
        if ny * (p[1] - civic_y(p[0])) < 0:
            nx, ny = -nx, -ny           # 讓正向永遠朝外側
        out.append([round(p[0] + nx * d, 2), round(p[1] + ny * d, 2), p[2]])
    return out


def real_w(w):
    return round((w - 1) / 3.25) * 3.5 + 1.5


mains = [v for z in D for v in D[z]['viaduct'] if '市民' in v['name'] and v['hw'] == 'trunk']
cross = [r['pts'] for z in D for r in D[z]['road'] if r['hw'] in ('primary', 'secondary', 'tertiary', 'trunk')
         and not r['name'].startswith('市民大道')]


def seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def decks_at(x):
    res = []
    for v in mains:
        p = v['pts']
        for i in range(len(p) - 1):
            a, b = p[i], p[i + 1]
            if min(a[0], b[0]) <= x <= max(a[0], b[0]) and a[0] != b[0]:
                t = (x - a[0]) / (b[0] - a[0])
                y, zz = a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t
                if not any(abs(y - r[0]) < 3 for r in res):
                    res.append((y, zz, real_w(v['w'])))
                break
    return res


DET = {}
for Z in M['zones']:
    zn = Z['name']
    det = {'outer': [], 'inner': [], 'piers': [], 'median': []}
    for v in D[zn]['viaduct']:
        if '市民' in v['name'] and v['hw'] == 'trunk':
            W = real_w(v['w'])
            det['outer'].append(offset_line(v['pts'], W / 2 - 0.2))
            det['inner'].append(offset_line(v['pts'], -(W / 2 - 0.2)))
    x = math.ceil(Z['x0'] / 30) * 30 + 15
    while x < Z['x1']:
        dk = decks_at(x)
        if dk:
            ys = [d[0] for d in dk]; cy = sum(ys) / len(ys); zt = min(d[1] for d in dk)
            if zt > 6 and not any(seg_d((x, cy), c[i], c[i + 1]) < 11 for c in cross for i in range(len(c) - 1)):
                ang = math.atan2(civic_y(x + 5) - civic_y(x - 5), 10)
                span = (max(ys) - min(ys)) + max(d[2] for d in dk) * 0.8
                det['piers'].append({'p': [x, round(cy, 1)], 'a': round(ang, 3), 'top': round(zt - GIRDER, 2),
                                     'cap': round(span, 1), 'hi': 1 if zt > 13 else 0})
        x += 30
    for ox, typ, extra in OBS:
        if not (Z['x0'] <= ox < Z['x1']):
            continue
        mw = median_width(ox)
        mw = max(5.0, min(14.0, mw if mw else 8.0))
        a, b = max(Z['x0'] + 1, ox - 50), min(Z['x1'] - 1, ox + 50)
        det['median'].append({'t': typ, 'w': round(mw, 1), 'pts': line_along(a, b, 0.0, 10.0), 'x': ox,
                              'label': '街景判讀：' + OBS_T[typ][0] + ('（' + extra + '）' if extra else '')})
    DET[zn] = det
    print(zn, 'piers', len(det['piers']), 'median obs', len(det['median']))

# ---------- 現況（精簡欄位） ----------
S = {}
for zn in D:
    d = D[zn]
    S[zn] = {
        'buildings': [{'p': b['pts'], 'h': b['h'], 'e': 1 if b['src'] == 'default' else 0,
                       'k': 1 if (b['name'] and any(k in b['name'] for k in KEY)) else 0} for b in d['buildings']],
        'areas': [{'k': a['kind'], 'p': a['pts']} for a in d['areas']],
        'trees': d.get('trees', []), 'metro': [s['p'] for s in d.get('subway_entrances', [])], 'det': DET[zn],
    }
    for cat in ('road', 'viaduct', 'footway', 'crossing', 'footbridge', 'cycleway', 'steps', 'rail_elevated'):
        S[zn][cat] = [{'p': r['pts'], 'w': r['w'], 'c': 1 if (r['name'].startswith('市民大道') and '巷' not in r['name']) else 0,
                       't': 1 if r.get('hw') == 'trunk' else 0, 'W': real_w(r['w']) if cat == 'viaduct' else 0} for r in d.get(cat, [])]
json.dump({'zones': M['zones'], 'data': S}, open(os.path.join(OUT, 'scene.json'), 'w'), ensure_ascii=False, separators=(',', ':'))

# 提案設施細部（依規範試排），並輸出 overlay.json
exec(compile(open(os.path.join(BASE, 'scripts/proposals_design.py'), encoding='utf-8').read(), 'proposals_design.py', 'exec'))
print({f: os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)})
