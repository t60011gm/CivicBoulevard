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
         'open': ('路口淨空', 0), 'ug': ('地下停車場出入口、車道或梯廳', 0), 'ramp': ('匝道引道與擋土牆', 0),
         'facility': ('橋下機房或管理設施建物', 0), 'paved': ('鋪面小廣場與公共藝術', 0)}
# 全線每約 100 m 一點；1550、1650 兩點只取得橋面或室內影像，無法判讀，未列入
OBS = [(-1700, 'green', ''), (-1562, 'green', '林森北路口，有通風設施'), (-1500, 'open', '林森北路口'), (-1400, 'parking', ''),
       (-1300, 'ug', '林森–金山地下停車場車道口'), (-1230, 'green', ''), (-1150, 'green', '路口旁'), (-1050, 'ug', '地下車道引道'),
       (-900, 'uturn', ''), (-800, 'green', '金山北路口'), (-700, 'green', ''), (-600, 'open', '路口'), (-520, 'green', ''),
       (-450, 'open', '新生北路、松江路口'), (-350, 'parking', ''), (-250, 'open', '建國高架下方路口'), (-170, 'ramp', ''),
       (-80, 'ramp', ''), (0, 'ramp', '匝道下方另有圍籬圈圍空間'), (100, 'parking', ''), (200, 'uturn', ''),
       (300, 'facility', '安東街口'), (400, 'facility', '通風機房'), (500, 'open', '復興南路口'), (600, 'uturn', ''),
       (700, 'open', '路口'), (780, 'parking', ''), (850, 'ug', '市民地下停車場'), (950, 'paved', '敦化南路口'),
       (1050, 'ug', '車道引道擋土牆'), (1150, 'ug', ''), (1250, 'ug', ''), (1350, 'ug', '車道出入口'),
       (1450, 'green', '延吉街口'), (1750, 'green', '')]

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


# 橋墩形式分段：(x 起, x 訖, 是否圓柱, 雙柱中心距 m（0 為單柱）, 依據)
# 依街景與簡報現況照片判讀；每段只有一到數張照片為據，段界為推估
PIER_FORM = [
    (-9999, -1250, 1, 0, '林森北路口街景：單支圓柱'),
    (-1250, -600, 0, 0, '中央藝文公園北側街景：單支矩形高柱'),
    (-600, 420, 0, 9.0, '懷生陸橋與建國高架旁現況照片：左右兩支矩形柱加橫梁（部分為鋼構門型）'),
    (420, 650, 1, 0, '復興南路以東街景：單支圓柱'),
    (650, 820, 1, 9.0, '大安路口現況照片：每排左右兩支圓柱'),
    (820, 1300, 1, 0, '181 巷口與敦化南路以東街景：單支圓柱加懸臂帽梁'),
    (1300, 1480, 1, 9.0, '四段 145–146 號現況照片：每排左右兩支圓柱'),
    (1480, 9999, 1, 0, '延吉街以東街景：單支圓柱'),
]
COL_D = 2.7


def pier_form(x):
    for a, b, rnd, gap, why in PIER_FORM:
        if a <= x < b:
            return rnd, gap, why
    return 1, 0, ''


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
                rnd, gap, _ = pier_form(x)
                det['piers'].append({'p': [x, round(cy, 1)], 'a': round(ang, 3), 'top': round(zt - GIRDER, 2),
                                     'cap': round(max(span, gap + 5), 1), 'hi': 1 if zt > 13 else 0, 'r': rnd, 'g': gap})
        x += 30
    for oi, (ox, typ, extra) in enumerate(OBS):
        if not (Z['x0'] <= ox < Z['x1']):
            continue
        mw = median_width(ox)
        mw = max(5.0, min(14.0, mw if mw else 8.0))
        lo = (ox + OBS[oi - 1][0]) / 2 if oi > 0 else ox - 60          # 各點涵蓋到與相鄰點的中點，最多前後 60 m
        hi = (ox + OBS[oi + 1][0]) / 2 if oi < len(OBS) - 1 else ox + 60
        a, b = max(Z['x0'] + 1, lo, ox - 60), min(Z['x1'] - 1, hi, ox + 60)
        if b - a < 4:
            continue
        det['median'].append({'t': typ, 'w': round(mw, 1), 'pts': line_along(a, b, 0.0, 10.0), 'x': ox,
                              'label': '街景判讀：' + OBS_T[typ][0] + ('（' + extra + '）' if extra else '')})
    DET[zn] = det

# ---- 橋墩改用 corridor.py 依街景校正後的實際立柱（取代上面每 30 m 一排的舊推估） ----
_corp = os.path.join(OUT, 'corridor.json')
COLS = []                                       # 每支立柱：(x, y, 橫向寬, r)
if os.path.exists(_corp):
    _piers = json.load(open(_corp))['piers']
    for Z in M['zones']:
        DET[Z['name']]['piers'] = []
    for q in _piers:
        for Z in M['zones']:
            if Z['x0'] <= q['p'][0] < Z['x1']:
                DET[Z['name']]['piers'].append({k: q[k] for k in ('p', 'a', 'top', 'r', 'g', 'offs', 'cs', 'cap')})
        for o in q['offs']:
            COLS.append((q['p'][0] - math.sin(q['a']) * o, q['p'][1] + math.cos(q['a']) * o, q['cs'][1] if not q['r'] else q['cs'][0], q['r']))
    _old_form = pier_form
    _svp = os.path.join(BASE, 'data/survey/piers_surveyed.json')
    _SVSEC = json.load(open(_svp))['sections'] if os.path.exists(_svp) else []

    # 同一排 = 同一座橋墩的立柱，加上另一方向橋面在 x 前後 8 m 內的立柱
    ROWS = []
    for c in sorted(COLS):
        if ROWS and c[0] - ROWS[-1][0][0] < 8:
            ROWS[-1].append(c)
        else:
            ROWS.append([c])

    def pier_form(x):
        """以 x 前後 18 m 內的實際橋墩排判斷：同一排內立柱橫向相距 4 m 以上才算左右兩支柱。
        回傳 (是否圓柱, 兩柱中心距, 說明)。"""
        global COL_D
        near = [r for r in ROWS if abs(r[0][0] - x) <= 18]
        if not near:
            return 1, 0, ''
        COL_D = max(c[2] for r in near for c in r)
        sp = []
        for r in near:
            lat = [c[1] - civic_y(c[0]) for c in r]
            sp.append(max(lat) - min(lat))
        tw = sorted(v for v in sp if v >= 4)
        why = _old_form(x)[2] or '街景判讀'
        for _t in _SVSEC:
            if _t['range'][0] <= x <= _t['range'][1]:
                why = _t['label'] + '街景逐墩判讀：南北兩排矩形柱'
        if len(tw) * 2 < len(sp):
            return near[0][0][3], 0, why
        return near[0][0][3], round(tw[len(tw) // 2], 1), why

# 已由 corridor.py 重建的路段（市民大道主線、相連匝道、平面車道）在此標記 x=1，網站與 Blender 不再重複繪製
_cor = json.load(open(os.path.join(OUT, 'corridor.json'))) if os.path.exists(os.path.join(OUT, 'corridor.json')) else {'centers': []}
_cg = {}
for _c in _cor['centers']:
    for _i in range(len(_c) - 1):
        _a, _b = _c[_i], _c[_i + 1]
        for _gx in range(int(min(_a[0], _b[0]) // 30) - 1, int(max(_a[0], _b[0]) // 30) + 2):
            for _gy in range(int(min(_a[1], _b[1]) // 30) - 1, int(max(_a[1], _b[1]) // 30) + 2):
                _cg.setdefault((_gx, _gy), []).append((_a, _b))


def _near_center(p, tol=3.0):
    for a, b in _cg.get((int(p[0] // 30), int(p[1] // 30)), ()):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        if math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy) < tol:
            return True
    return False


def _hidden(cat, r):
    if cat not in ('viaduct', 'road'):
        return 0
    civic = r['name'].startswith('市民大道') and '巷' not in r['name']
    if not (r.get('hw') in ('trunk', 'trunk_link') or civic):
        return 0
    pts = r['pts']
    probe = [pts[0], pts[len(pts) // 2], pts[-1]]
    return 1 if all(_near_center(q) for q in probe) else 0


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
                       't': 1 if r.get('hw') == 'trunk' else 0, 'W': real_w(r['w']) if cat == 'viaduct' else 0, 'x': _hidden(cat, r)} for r in d.get(cat, [])]
json.dump({'zones': M['zones'], 'data': S}, open(os.path.join(OUT, 'scene.json'), 'w'), ensure_ascii=False, separators=(',', ':'))

# 提案設施細部（依規範試排），並輸出 overlay.json
exec(compile(open(os.path.join(BASE, 'scripts/proposals_design.py'), encoding='utf-8').read(), 'proposals_design.py', 'exec'))
print({f: os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)})
