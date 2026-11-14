"""針對四項批評，用模型資料逐一檢查所有提案。輸出文字報表與 web/data/critique.json。
需先執行 preprocess.py 與 make_overlay.py。"""
import json, math, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = json.load(open(os.path.join(BASE, 'data/model.json')))
SC = json.load(open(os.path.join(BASE, 'web/data/scene.json')))
OV = json.load(open(os.path.join(BASE, 'web/data/overlay.json')))

FIXED = {'ug': '地下停車場出入口或車道', 'ramp': '匝道引道', 'facility': '機房或管理建物', 'open': '路口（無分隔帶）'}
MOVABLE = {'parking': '收費停車場', 'uturn': '迴轉道與綠帶', 'green': '植栽綠帶', 'paved': '鋪面小廣場'}
PIER_KEEP = 2.7 + 2 * 2.5          # 柱徑 2.7 m 加前後各 2.5 m 淨空

medians = [(m['pts'][0][0], m['pts'][-1][0], m['t'], m['w']) for z in SC['data'].values() for m in z['det']['median']]
piers = sorted(q['p'][0] for z in SC['data'].values() for q in z['det']['piers'])
bld = [b for z in M['data'].values() for b in z['buildings']]
roads = [r for z in M['data'].values() for r in z['road'] if r['hw'] not in ('service',)]


def xrange_of(p):
    xs = []
    for q in p['parts']:
        if q['k'] == 'rib':
            xs += [v[0] for v in q['pts']]
        else:
            xs.append(q['c'][0])
    return min(xs), max(xs)


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


# 各設施成立的最低條件。mode：
#   clear = 需要一段沒有橋墩的淨空（球場、遊具、舞臺視線）；area = 可跨橋墩配置，只看扣除後總長；walk = 步道須全線連續
NEED = {'a2': ('clear', 19, '一座 3x3 球場加兩端緩衝，或兩張桌球桌'), 'a3': ('clear', 12, '一組遊具加使用區'),
        'a4': ('area', 24, '300 m² 最小狗活動區'), 'a5': ('walk', None, '步道須全線連續'),
        'b1a': ('walk', None, '步道須全線連續'), 'b1b': ('walk', None, '步道須全線連續'),
        'c1': ('area', 30, '十個攤位加通道'), 'c2': ('clear', 15, '舞臺加前排觀眾區'), 'c3': ('clear', 15, '舞臺加四排座位')}

rows = []
print('=' * 30, '批評 1、2：橋墩與不可移除設施', '=' * 30)
for p in OV['proposals']:
    if p['cat'] != '橋下活化':
        continue
    x0, x1 = xrange_of(p)
    L = x1 - x0
    ps = [q for q in piers if x0 <= q <= x1]
    fixed = {}
    mov = {}
    covered = 0.0
    blocked = []                       # 不可用區間
    for a, b, t, w in medians:
        o = overlap(x0, x1, a, b)
        if o <= 0:
            continue
        covered += o
        if t in FIXED:
            fixed[t] = fixed.get(t, 0) + o
            blocked.append((max(x0, a), min(x1, b)))
        else:
            mov[t] = mov.get(t, 0) + o
    for q in ps:
        blocked.append((q - PIER_KEEP / 2, q + PIER_KEEP / 2))
    blocked.sort()
    # 最大連續可用長度
    cur, best, free_total = x0, 0.0, 0.0
    for a, b in blocked:
        if a > cur:
            best = max(best, a - cur)
            free_total += a - cur
        cur = max(cur, b)
    if x1 > cur:
        best = max(best, x1 - cur)
        free_total += x1 - cur
    fx = sum(fixed.values())
    mode, need, why = NEED[p['id']]
    width_fail = any((not c[0]) and ('放不下' in c[1] or '不足以' in c[1]) for c in p['checks'])
    # 不計橋墩時的可用總長（供可跨橋墩配置的設施使用）
    free_nopier = L - fx - (L - covered)
    if mode == 'walk':
        verdict = '放不下' if (fx > 0 or width_fail) else '可容納，須協調'
    elif mode == 'clear':
        verdict = '放不下' if best < need else ('大幅縮水' if (fx + (L - covered)) / L > 0.3 or width_fail else '可容納，須協調')
    else:
        verdict = '放不下' if free_nopier < need else ('大幅縮水' if (fx + (L - covered)) / L > 0.3 else '可容納，須協調')
    if not fx and not mov and covered == 0:
        verdict += '（未判讀）'
    rows.append({'id': p['id'], 'title': p['title'], 'zone': p['zone'], 'L': round(L), 'piers': len(ps),
                 'fixed': {FIXED[k]: round(v) for k, v in fixed.items()}, 'movable': {MOVABLE[k]: round(v) for k, v in mov.items()},
                 'unsurveyed': round(L - covered), 'free_total': round(free_total), 'free_nopier': round(free_nopier), 'longest': round(best), 'mode': mode,
                 'need': need, 'why': why, 'width_fail': width_fail, 'verdict': verdict})
    print('%-4s %s｜長 %d m｜橋墩 %d 支｜不可移除 %s（共 %d m，占 %d%%）｜需協調 %s｜未判讀 %d m｜扣除後可用 %d m，最長連續 %d m｜需求 %s｜→ %s%s' % (
        p['id'], p['title'], L, len(ps), rows[-1]['fixed'] or '無', fx, fx / L * 100, rows[-1]['movable'] or '無', L - covered,
        free_total, best, ('%d m（%s，%s）' % (need, why, {'clear': '需無柱淨空', 'area': '可跨橋墩'}[mode])) if need else why, verdict, '（寬度也不足）' if width_fail else ''))


# ---------- 批評 3：陸橋階梯與人行道 ----------
def seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def inside(p, poly):
    c = False
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]:
            c = not c
    return c


def d_building(p):
    best = 1e9
    for b in bld:
        pts = b['pts']
        if abs(pts[0][0] - p[0]) > 120 or abs(pts[0][1] - p[1]) > 120:
            continue
        if inside(p, pts):
            return 0.0
        for i in range(len(pts)):
            best = min(best, seg_d(p, pts[i], pts[(i + 1) % len(pts)]))
    return best


def d_road_edge(p):
    best = 1e9
    for r in roads:
        pts = r['pts']
        if abs(pts[0][0] - p[0]) > 400:
            continue
        for i in range(len(pts) - 1):
            best = min(best, seg_d(p, pts[i], pts[i + 1]) - r['w'] / 2)
    return best


print()
print('=' * 30, '批評 3：陸橋階梯、電梯與人行道', '=' * 30)
bridges = []
for p in OV['proposals']:
    if p['cat'] != '人行陸橋':
        continue
    ends = []
    stairs = [q for q in p['parts'] if q['r'] == 'stair']
    lifts = [q for q in p['parts'] if q['r'] == 'lift']
    for k in range(0, len(stairs), 2):
        a, b = stairs[k]['pts'][0], stairs[k + 1]['pts'][-1]
        samples = [(a[0] + (b[0] - a[0]) * t / 8, a[1] + (b[1] - a[1]) * t / 8) for t in range(9)]
        lf = lifts[k // 2]['c']
        samples.append(tuple(lf))
        in_b = sum(1 for s in samples if d_building(s) < 1.0)
        in_r = sum(1 for s in samples if d_road_edge(s) < 1.0)
        mid = samples[4]
        gap = d_building(mid) + max(0.0, d_road_edge(mid))
        ends.append({'in_building': in_b, 'in_road': in_r, 'n': len(samples), 'gap': round(gap, 1),
                     'left': round(gap - 2.0, 1), 'd_road': round(d_road_edge(mid), 1), 'd_bld': round(d_building(mid), 1)})
    deck = next(q for q in p['parts'] if q['r'] == 'deck')
    gaps, over_road, over_bld, ns = [], 0, 0, 0
    for i in range(len(deck['pts']) - 1):
        a, b = deck['pts'][i], deck['pts'][i + 1]
        k = max(1, int(math.dist(a[:2], b[:2]) // 8))
        for j in range(k):
            s_ = (a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k)
            dr, db = d_road_edge(s_), d_building(s_)
            ns += 1
            over_road += dr < 0
            over_bld += db < 0.5
            if dr >= 0:
                gaps.append(dr + db)
    gaps.sort()
    line = {'n': ns, 'over_road': over_road, 'over_bld': over_bld,
            'gap_min': round(gaps[0], 1) if gaps else None, 'gap_med': round(gaps[len(gaps) // 2], 1) if gaps else None}
    Ld = sum(math.dist(deck['pts'][i][:2], deck['pts'][i + 1][:2]) for i in range(len(deck['pts']) - 1))
    t_bridge = 2 * 12.3 / 0.5 + Ld / 1.0          # 階梯水平速率約 0.5 m/s，平路 1.0 m/s
    bridges.append({'id': p['id'], 'title': p['title'], 'deck_len': round(Ld), 't_bridge': round(t_bridge), 'ends': ends, 'line': line})
    print(p['id'], p['title'], '｜橋長 %d m，走陸橋約 %d 秒' % (Ld, t_bridge))
    print('    橋身取樣 %(n)d 點：在車道上方 %(over_road)d 點、與建物重疊 %(over_bld)d 點；不在車道上方的點，車道邊到建物面的距離最小 %(gap_min)s m、中位數 %(gap_med)s m' % line)
    for i, e in enumerate(ends):
        print('    端點 %d：階梯與電梯取樣 %d 點，落在建物範圍 %d 點、落在車道範圍 %d 點；此處車道邊到建物面約 %.1f m（距車道邊 %.1f、距建物 %.1f），放 2 m 寬階梯後剩 %.1f m' % (
            i + 1, e['n'], e['in_building'], e['in_road'], e['gap'], e['d_road'], e['d_bld'], e['left']))

json.dump({'under': rows, 'bridges': bridges}, open(os.path.join(BASE, 'web/data/critique.json'), 'w'), ensure_ascii=False, indent=1)
