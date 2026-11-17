"""針對四項批評，用模型資料逐一檢查所有提案。輸出文字報表與 web/data/critique.json。
需先執行 preprocess.py 與 make_overlay.py。"""
import json, math, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = json.load(open(os.path.join(BASE, 'data/model.json')))
SC = json.load(open(os.path.join(BASE, 'web/data/scene.json')))
OV = json.load(open(os.path.join(BASE, 'web/data/overlay.json')))

FIXED = {'ug': '地下停車場出入口或車道', 'ramp': '匝道引道', 'facility': '機房或管理建物', 'open': '路口（無分隔帶）'}
MOVABLE = {'parking': '收費停車場', 'uturn': '迴轉道與綠帶', 'green': '植栽綠帶', 'paved': '鋪面小廣場'}
PIER_KEEP = 3.0 + 2 * 2.5          # 柱順橋向最長 3.0 m 加前後各 2.5 m 淨空

medians = [(m['pts'][0][0], m['pts'][-1][0], m['t'], m['w']) for z in SC['data'].values() for m in z['det']['median']]
_px = sorted(q['p'][0] for z in SC['data'].values() for q in z['det']['piers'])
piers = []
for _x in _px:                      # 兩方向橋面各自落墩、x 相近的併成同一排
    if piers and _x - piers[-1] < 6:
        continue
    piers.append(_x)
# 每支實際立柱 (x, y, 半徑, 柱頂高)
COLS = []
for z in SC['data'].values():
    for q in z['det']['piers']:
        for o in q.get('offs', [0]):
            COLS.append((q['p'][0] - math.sin(q['a']) * o, q['p'][1] + math.cos(q['a']) * o, max(q.get('cs', [2.7, 2.7])) / 2, q['top']))


def clash(p):
    """提案量體（高度 0.3 m 以上的實體）與現況立柱在平面上重疊、且高度有交集的處數。鋪面與標線不算。"""
    hits = []
    for q in p['parts']:
        if q['k'] == 'box':
            if q['z'][1] - q['z'][0] < 0.3:
                continue
            ca, sa = math.cos(q['a']), math.sin(q['a'])
            for cx, cy, r, top in COLS:
                dx, dy = cx - q['c'][0], cy - q['c'][1]
                lx, ly = dx * ca + dy * sa, -dx * sa + dy * ca
                if abs(lx) < q['s'][0] / 2 + r and abs(ly) < q['s'][1] / 2 + r and q['z'][0] < top:
                    hits.append((round(cx, 1), round(cy, 1), q['r']))
        elif q['t'] >= 0.3 or q['pts'][0][2] >= 2:
            for cx, cy, r, top in COLS:
                for i in range(len(q['pts']) - 1):
                    a, b = q['pts'][i], q['pts'][i + 1]
                    ux, uy = b[0] - a[0], b[1] - a[1]
                    L2 = ux * ux + uy * uy or 1
                    t = max(0, min(1, ((cx - a[0]) * ux + (cy - a[1]) * uy) / L2))
                    if math.hypot(cx - a[0] - t * ux, cy - a[1] - t * uy) < q['w'] / 2 + r and min(a[2], b[2]) - q['t'] < top:
                        hits.append((round(cx, 1), round(cy, 1), q['r']))
                        break
    return hits
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
    _svf = os.path.join(BASE, 'data/survey/piers_surveyed.json')
    _sec = [t for t in (json.load(open(_svf))['sections'] if os.path.exists(_svf) else []) if t['range'][0] <= (x0 + x1) / 2 <= t['range'][1]]
    rows.append({'id': p['id'], 'title': p['title'], 'zone': p['zone'], 'L': round(L), 'piers': len(ps),
                 'sv': [_sec[0]['span'], _sec[0]['clear'], _sec[0].get('obs', '')] if _sec else None,
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

# ---------- 彙整成每個提案一筆，供網站顯示 ----------
LEVEL = {'放不下': 0, '大幅縮水': 1, '可容納，須協調': 2}
AIR = {'a2': (0, '高：運動時換氣量大，離車道邊約 0.65 m'), 'a3': (0, '高：兒童久留，離車道邊約 0.65 m'),
       'a4': (0, '高：飼主與寵物久留，離車道邊約 0.65 m'), 'c1': (1, '中：久留加上飲食，營業多在夜間'),
       'c2': (1, '中：活動期間久留'), 'c3': (1, '中：活動期間久留'),
       'a5': (2, '低：步行短暫通過'), 'b1a': (2, '低：步行短暫通過'), 'b1b': (2, '低：步行短暫通過')}
AIR_NOTE = '查無市民大道橋下的空氣品質實測與車流量資料，此為依停留時間與使用者所做的定性判斷，須實地量測 PM2.5 與 NO₂。'
by = {}
for r in rows:
    fx = sum(r['fixed'].values())
    c1 = '範圍內有 %d 排橋墩（間距約 30 m、柱寬 1.8–3.0 m，柱形依街景校正），橋墩之間無柱空間最長約 22 m。' % r['piers']
    if r.get('sv'):
        c1 = '範圍內有 %d 支橋柱（街景逐墩判讀、多點交會定位，南北兩排、同排柱距%s、柱寬約 2.5 m），橋墩之間無柱空間最長%s。' % (r['piers'], r['sv'][0], r['sv'][1])
        if r['sv'][2]:
            c1 += '【' + r['sv'][2].replace('：', '】', 1) + '。'
    if r['mode'] == 'clear':
        c1 += '此設施需要無柱淨空 %d m（%s），扣除後最長連續 %d m。' % (r['need'], r['why'], r['longest'])
    elif r['mode'] == 'area':
        c1 += '此設施可跨橋墩配置，橋墩只扣除占用面積。'
    else:
        c1 += '步道須繞過每支橋墩。'
    if fx:
        c2 = '不可移除：' + '、'.join('%s %d m' % kv for kv in r['fixed'].items()) + '，占範圍 %d%%。' % round(fx / r['L'] * 100)
    else:
        c2 = '範圍內沒有判讀到不可移除的設施。'
    if r['movable']:
        c2 += '需協調釋出：' + '、'.join('%s %d m' % kv for kv in r['movable'].items() if kv[1]) + '。'
    if r['unsurveyed'] > 5:
        c2 += '另有 %d m 未判讀。' % r['unsurveyed']
    if r['width_fail']:
        c2 += '分隔帶寬度也不足。'
    by[r['id']] = {'verdict': r['verdict'], 'level': LEVEL.get(r['verdict'], 3), 'c1': c1, 'c2': c2,
                   'c3': '不涉及人行天橋。', 'c4': AIR[r['id']][1] + '。' + AIR_NOTE, 'air': AIR[r['id']][0]}
BR = {'a1': (1, '設置條件存疑', '走陸橋約 %d 秒；繞到最近的行穿線約 203 秒再加等候，是三座中唯一有時間優勢的。但離最近行穿線僅約 85 m，不符規範「不宜小於 200 m」。'),
      'b5': (1, '效益存疑', '走陸橋約 %d 秒；13 m 外就有行穿線，遇綠燈時走平面約快一倍。'),
      'c4': (0, '位置須重排，預期少人使用', '走陸橋約 %d 秒；同一側走人行道只要約 222 秒，且不用爬 5.5 m。')}
for b in bridges:
    lv, vd, use = BR[b['id']]
    ln = b['line']
    c3 = '橋身取樣 %d 點中有 %d 點在車道上方，橋柱須避開車道。' % (ln['n'], ln['over_road'])
    for i, e in enumerate(b['ends']):
        where = '落在車道範圍，須轉向' if e['in_road'] >= 5 else ('與建物重疊' if e['in_building'] >= 5 else
                 '車道邊到建物面約 %.0f m，放階梯與電梯後約剩 %.0f m' % (e['gap'], e['left'] - 0.6))
        c3 += '端點 %d：%s。' % (i + 1, where)
    c3 += use % b['t_bridge'] + '（階梯速率以 0.5 m/s 假設；車道寬為估算值，誤差約 2 m。）'
    by[b['id']] = {'verdict': vd, 'level': lv, 'c1': '陸橋位於高架外側或下方穿越，橋柱須與既有橋墩錯開。', 'c2': '不占用橋下分隔帶。',
                   'c3': c3, 'c4': '低：通行短暫。' + AIR_NOTE, 'air': 2}
for p in OV['proposals']:
    if p['id'] in by:
        continue
    if p['cat'] == '平面穿越':
        by[p['id']] = {'verdict': '可行', 'level': 2, 'c1': '庇護島設在橋墩之間，橋墩會遮擋駕駛視線，停止線須退後。',
                       'c2': '利用既有行穿線位置，不需移除設施。', 'c3': '不涉及人行天橋；平面穿越符合規範「以平面穿越為原則」。',
                       'c4': '低：等候與通過時間短。' + AIR_NOTE, 'air': 2}
    else:
        by[p['id']] = {'verdict': '不在橋下，未列入此項檢查', 'level': 3, 'c1': '不在高架橋下。', 'c2': '不在高架橋下。',
                       'c3': '不涉及人行天橋。', 'c4': '離車道較遠，未評。', 'air': 3}
# 橋墩校正後的幾何複核：提案量體是否與現況立柱重疊
clashes = {}
for p in OV['proposals']:
    h = clash(p)
    if not h:
        continue
    pts = sorted(set((x, y) for x, y, _ in h))
    kinds = sorted(set(k for _, _, k in h))
    clashes[p['id']] = {'n': len(pts), 'pts': pts, 'kinds': kinds}
    by[p['id']]['c1'] += '【橋墩校正後複核】提案量體與 %d 支現況橋柱在平面上重疊，位置須重排。' % len(pts)
    by[p['id']]['clash'] = len(pts)
print('clashes', {k: (v['n'], v['kinds']) for k, v in clashes.items()})
cnt = {}
for v in by.values():
    cnt[v['level']] = cnt.get(v['level'], 0) + 1
print('levels', cnt)
json.dump({'under': rows, 'bridges': bridges, 'by': by, 'clashes': clashes}, open(os.path.join(BASE, 'web/data/critique.json'), 'w'), ensure_ascii=False, indent=1)
