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


def under(pid, zone, title, cat, x0, x1, w, desc, stalls=0, src='政策原文項目，位置為本模型示意'):
    pts = line_along(x0, x1)
    xm = (x0 + x1) / 2
    mw = median_width(xm)
    dz = deck_z(xm)
    note = '長約 %.0f m、示意寬 %.0f m（面積約 %.0f m²）。此處橋面估計高 %.1f m、梁底淨高約 %.1f m（街景估計，誤差約 ±1.5 m）。' % (
        plen(pts), w, plen(pts) * w, dz, dz - GIRDER)
    if mw is not None:
        note += '依 OSM 平面車道中心線推估，兩向車道之間的橋下帶寬約 %.0f m' % mw
        note += '，放得下。' if mw >= w else '，小於示意寬度，需縮減量體或調整車道。'
    obs = [o for o in OBS if x0 - 50 <= o[0] <= x1 + 50]
    if obs:
        note += '街景判讀此段橋下現況：' + '；'.join(OBS_T[o[1]][0] + ('（' + o[2] + '）' if o[2] else '') for o in obs) + '。提案需先處理這些既有使用。'
    else:
        note += '此段橋下現況未抽樣判讀，須現勘。'
    P.append({'id': pid, 'zone': zone, 'title': title, 'cat': cat, 'kind': 'pad', 'pts': pts, 'w': w, 'stalls': stalls,
              'desc': desc, 'note': note, 'src': src, 'focus': [xm, civic_y(xm)]})


def bridge(pid, zone, title, pts, w, z, desc, extra='', src='政策原文項目，位置為本模型示意'):
    L = plen(pts)
    xm = sum(p[0] for p in pts) / len(pts)
    ym = sum(p[1] for p in pts) / len(pts)
    dz = deck_z(xm)
    inside = any(abs(p[1] - civic_y(p[0])) < deck_halfwidth(p[0]) for p in pts)
    note = '示意長度約 %.0f m、寬 %.0f m、橋面高 %.1f m。' % (L, w, z)
    if inside:
        clear = (dz - GIRDER) - z
        note += '穿過高架投影範圍：高架梁底估計約 %.1f m，陸橋面上方剩約 %.1f m' % (dz - GIRDER, clear)
        note += '，行人淨高足夠（需 ≥2.5 m）。' if clear >= 2.5 else '，行人淨高不足（需 ≥2.5 m），須改走高架外側或降低橋面。'
    else:
        note += '全程位於高架投影範圍外側，不受梁底淨高限制，但需占用人行道或路側空間落墩。'
    note += extra
    P.append({'id': pid, 'zone': zone, 'title': title, 'cat': '人行陸橋', 'kind': 'bridge', 'pts': pts, 'w': w, 'z': z,
              'desc': desc, 'note': note, 'src': src, 'focus': [xm, ym]})


def path(pid, zone, title, pts, w, desc, note, src='政策原文項目，路徑為本模型示意'):
    xm = sum(p[0] for p in pts) / len(pts)
    ym = sum(p[1] for p in pts) / len(pts)
    P.append({'id': pid, 'zone': zone, 'title': title, 'cat': '串聯動線', 'kind': 'path', 'pts': pts, 'w': w,
              'desc': desc, 'note': '示意長度約 %.0f m。' % plen(pts) + note, 'src': src, 'focus': [xm, ym]})


def site(pid, zone, title, cat, cx, cy, sx, sy, h, desc, note, src='政策原文項目，位置為本模型示意'):
    P.append({'id': pid, 'zone': zone, 'title': title, 'cat': cat, 'kind': 'box', 'c': [cx, cy], 's': [sx, sy], 'h': h,
              'desc': desc, 'note': note, 'src': src, 'focus': [cx, cy]})


ZA, ZB, ZC = 'A_華山', 'B_市民八德', 'C_市民敦化'

# ===== A 華山 =====
bridge('a1', ZA, '人行陸橋：華山公園 ↔ 中央藝文公園', [[-1236, 292], [-1228, 262], [-1214, 205], [-1206, 176]], 4.0, 6.0,
       '以人行陸橋跨越市民大道，連結北側華山公園與南側中央藝文公園、華山文創園區。',
       '南端落在中央藝文公園共融遊戲場旁，北端落在華山公園帶狀綠地。')
under('a2', ZA, '運動驛站', '橋下活化', -1120, -1050, 12, '橋下設置運動驛站，服務兩側公園的慢跑與球類使用者。', stalls=2)
under('a3', ZA, '兒童遊戲場', '橋下活化', -1035, -965, 12, '橋下全天候遮蔭遊戲場，延伸中央藝文公園既有共融遊戲場。', stalls=3)
under('a4', ZA, '寵物友善空間', '橋下活化', -950, -885, 12, '橋下寵物活動區。', stalls=1)
under('a5', ZA, '動漫廊道（往三創、光華）', '橋下活化', -840, -630, 8,
      '報導提及結合台北地下街、三創及光華商圈發展動漫廊道。', stalls=0, src='媒體報導項目，位置為本模型示意')

# ===== B 市民八德 =====
under('b1', ZB, '藝文廊道（啤酒廠 ↔ 忠泰美術館）', '橋下活化', -330, -130, 10,
      '以建國啤酒廠與忠泰美術館為兩端節點，橋下作為藝文展示與步行廊道。', stalls=4)
site('b2', ZB, '文創市集（建國啤酒廠）', '節點活化', -372, 205, 70, 40, 4.5,
     '配合啤酒廠改造設置文創市集。',
     '示意占地約 2,800 m²。建國啤酒廠園區在 OSM 登錄面積約 49,210 m²，廠區為市定古蹟且仍在生產，可釋出範圍需與台酒公司及文資主管機關確認。')
site('b3', ZB, '展覽空間（啤酒貯藏庫）', '節點活化', -333, 163, 46, 24, 13.2,
     '利用啤酒廠既有廠房作為展覽空間。',
     '量體取自 OSM「啤酒貯藏庫」建物位置，高度為假設值（OSM 無樓層資料）。')
path('b4', ZB, '串聯八德市場', [[-237, 49], [-236, 5], [-232, -24], [-205, -58], [-182, -80]], 4.0,
     '由八德市場向南穿越市民大道，接到忠泰美術館所在街廓。',
     '八德市場位於建國高架橋下，穿越點需與建國南北路車流號誌整合。')
bridge('b5', ZB, '懷生國小人行陸橋優化', [[189, -70], [190, -47], [191, -24]], 4.0, 5.5,
       '優化既有跨越市民大道的人行陸橋，改善懷生國小學童通學。',
       'OSM 登錄此處有既有人行陸橋（安東街口附近）；優化內容（加寬、無障礙電梯、遮雨）政策未說明。',
       src='政策原文項目，位置取自 OSM 既有陸橋')
path('b6', ZB, '懷生國小通學路徑', [[189, -70], [186, -110], [178, -150], [168, -195]], 3.0,
     '由陸橋南端沿巷道接到懷生國小。',
     'OSM 未登錄懷生國小校地，學校位置依公開地址（安東街）推估，路徑僅供示意。')

# ===== C 市民敦化 =====
under('c1', ZC, '可撤收夜間市集', '橋下活化', 520, 760, 10, '復興南路至敦化南路間，橋下設置可撤收式夜間市集。', stalls=8)
under('c2', ZC, '音樂廣場', '橋下活化', 800, 900, 12, '橋下音樂廣場。', stalls=0)
under('c3', ZC, '小型展演空間', '橋下活化', 1055, 1150, 10, '橋下小型展演空間。', stalls=1)
cb = line_along(1189, 1414, off=-17.0, step=15.0)
bridge('c4', ZC, '人行陸橋評估：181 巷 ↔ 延吉街', cb, 4.0, 5.5,
       '政策提出評估 181 巷至延吉街約 300 公尺路段設置人行陸橋，串聯忠孝復興與敦化兩商圈。',
       '模型量得 181 巷口到延吉街口約 %.0f m，政策文字為約 300 公尺。此段為低層橋，梁底估計約 %.1f m；陸橋若走高架正下方，橋面上方只剩約 %.1f m，扣掉估計誤差後淨高沒有把握，且中央分隔帶有橋墩與地下停車場出入口，故示意放在南側外緣。' % (plen(cb), deck_z(1300) - GIRDER, deck_z(1300) - GIRDER - 5.5))
for i, x in enumerate([663, 781, 920, 1077, 1201, 1310]):
    P.append({'id': 'c5_%d' % i, 'zone': ZC, 'title': '平面穿越改善 %d/6' % (i + 1), 'cat': '平面穿越', 'kind': 'marker',
              'c': [x, round(civic_y(x), 1)], 'r': 16,
              'desc': '政策提出優先改善六處平面穿越（行穿線、號誌、庇護島）。',
              'note': '政策未指明是哪六處；此處取 OSM 既有行穿線中、復興南路至延吉街之間的六個位置作為示意。',
              'src': '政策原文項目，位置為本模型示意', 'focus': [x, civic_y(x)]})

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

json.dump({'proposals': P, 'stats': stats, 'labels': labels, 'zones': M['zones'], 'assumptions': M['assumptions'], 'girder': GIRDER},
          open(os.path.join(OUT, 'overlay.json'), 'w'), ensure_ascii=False)


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

for p in P:
    print(p['id'], p['title'], '|', p['note'][:110])
for z, s in stats.items():
    print(z, {k: v for k, v in s.items() if k not in ('cross_x', 'gap_line')})
print({f: os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)})
