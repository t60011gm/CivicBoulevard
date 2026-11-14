"""車流與人流的示意動線，以及提案造成的動線衝突點。輸出 web/data/flows.json。
需先執行 corridor.py、make_overlay.py、critique_check.py。
注意：沒有實際交通量資料，車輛與行人的數量、速度都是示意設定；衝突點則取自 critique_check.py 與提案規範檢核的結果。"""
import json, math, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(BASE, 'web/data')
CO = json.load(open(os.path.join(W, 'corridor.json')))
OV = json.load(open(os.path.join(W, 'overlay.json')))
CQ = json.load(open(os.path.join(W, 'critique.json')))

deck = [p for v in CO['vpaths'] if v['k'] == 'deck' for p in v['pts']]
surf = [p for v in CO['vpaths'] if v['k'] == 'surf' for p in v['pts']]


def mid(x):
    n = [p[1] for p in deck if abs(p[0] - x) < 25] or [min(deck, key=lambda p: abs(p[0] - x))[1]]
    return sum(n) / len(n)


def lanes_y(x):
    n = [p[1] for p in surf if abs(p[0] - x) < 25]
    return (min(n), max(n)) if n else (mid(x) - 10, mid(x) + 10)


def R(v):
    return round(v, 1)


veh = [{'k': v['k'], 'w': v.get('w', 0), 'pts': v['pts'][::2] + [v['pts'][-1]]} for v in CO['vpaths']]
ped_now = [{'pts': w[::2] + [w[-1]], 'loop': 0} for w in CO['wpaths'] if len(w) > 3]
# 既有行穿線：直接用圖資裡的行穿線線段（只取跨市民大道平面車道的），不另外畫直線
M = json.load(open(os.path.join(BASE, 'data/model.json')))
cross_paths = []
for z in M['data'].values():
    for r in z.get('crossing', []):
        m = r['pts'][len(r['pts']) // 2]
        if any(abs(p[0] - m[0]) < 14 and abs(p[1] - m[1]) < 14 for p in surf):
            cross_paths.append({'pts': [[R(q[0]), R(q[1]), .35] for q in r['pts']], 'loop': 1, 'n': 2, 'x': m[0]})
cross_x = sorted(c['x'] for c in cross_paths)

ped_prop, conflicts, unreachable = [], [], set()
ug = [(u['x'], u['x'] + u['dir'] * 45) for u in CO['ug']]


def xrange_of(p):
    xs = []
    for q in p['parts']:
        xs += [v[0] for v in q['pts']] if q['k'] == 'rib' else [q['c'][0]]
    return min(xs), max(xs)


under = {r['id']: r for r in CQ['under']}
for p in OV['proposals']:
    pid, cat = p['id'], p['cat']
    if cat == '橋下活化':
        x0, x1 = xrange_of(p)
        xm = (x0 + x1) / 2
        pts, x = [], x0 + 2
        while x < x1 - 1:
            pts.append([R(x), R(mid(x)), .5])
            x += 8
        bad = False
        fails = [c[1] for c in p['checks'] if not c[0]]
        no_cross = any('沒有跨市民大道的行穿線' in t for t in fails)
        ys, _ = lanes_y(xm)
        if no_cross:
            # 行人不任意穿越：只在人行道上徘徊，設施內不放行人
            ped_prop.append({'pts': [[R(xm - 9), R(ys - 5.5), .35], [R(xm + 9), R(ys - 5.5), .35]], 'loop': 1, 'n': 4, 'bad': 1, 'pid': pid})
            conflicts.append({'p': [R(xm), R(ys), 0], 'pid': pid, 't': '25 m 內沒有行穿線：行人到不了設施'})
            unreachable.add(pid)
        else:
            c = min(cross_x, key=lambda v: abs(v - xm))
            ysc, _ = lanes_y(c)
            ped_prop.append({'pts': [[c, R(ysc - 5.5), .35], [c, R(mid(c)), .4], [R(max(x0, min(x1, c))), R(mid(max(x0, min(x1, c)))), .5]],
                             'loop': 1, 'n': 3, 'bad': 0, 'pid': pid})
        for a, b in ug:
            lo, hi = max(x0, min(a, b)), min(x1, max(a, b))
            if hi - lo > 3:
                bad = True
                conflicts.append({'p': [R((lo + hi) / 2), R(mid((lo + hi) / 2)), 0], 'pid': pid, 't': '設施與地下停車場車道重疊，進出車輛動線衝突'})
        r = under.get(pid, {})
        if r.get('movable', {}).get('迴轉道與綠帶', 0) > 5:
            conflicts.append({'p': [R(xm + 12), R(mid(xm + 12)), 0], 'pid': pid, 't': '占用迴轉道：迴轉車流被阻斷'})
        if r.get('fixed', {}).get('匝道引道', 0) > 5:
            bad = True
            conflicts.append({'p': [R(xm), R(mid(xm)), 0], 'pid': pid, 't': '位置是匝道引道，設施無法設置'})
        if r.get('fixed', {}).get('路口（無分隔帶）', 0) > 5:
            conflicts.append({'p': [R(x0 + 8), R(mid(x0 + 8)), 0], 'pid': pid, 't': '範圍跨越路口，沒有分隔帶可用'})
        if any('外溢' in t for t in fails):
            conflicts.append({'p': [R(xm - 20), R(mid(xm - 20) - 6), 0], 'pid': pid, 't': '攤位人潮外溢到車道邊'})
        if len(pts) > 1 and pid not in unreachable:
            ped_prop.append({'pts': pts, 'loop': 1, 'n': max(3, int((x1 - x0) / 9)), 'bad': 1 if bad else 0, 'pid': pid})
    elif cat == '人行陸橋':
        d = next(q for q in p['parts'] if q['r'] == 'deck')
        ped_prop.append({'pts': [[R(q[0]), R(q[1]), q[2] + .1] for q in d['pts']], 'loop': 1, 'n': max(3, len(d['pts']) // 2), 'bad': 0, 'pid': pid})
        b = next(x for x in CQ['bridges'] if x['id'] == pid)
        ends = [d['pts'][0], d['pts'][-1]]
        for e, q in zip(b['ends'], ends):
            if e['in_road'] >= 5:
                conflicts.append({'p': [R(q[0]), R(q[1]), 0], 'pid': pid, 't': '階梯落在車道範圍'})
        if b['line']['over_road'] * 2 > b['line']['n']:
            m = d['pts'][len(d['pts']) // 2]
            conflicts.append({'p': [R(m[0]), R(m[1]), 0], 'pid': pid, 't': '橋身多在車道上方，橋柱會落在車道'})
    elif cat == '串聯動線':
        w = p['parts'][0]
        ped_prop.append({'pts': [[R(q[0]), R(q[1]), .5] for q in w['pts']], 'loop': 1, 'n': 4, 'bad': 0, 'pid': pid})
        if pid == 'b4':
            q = w['pts'][2]
            conflicts.append({'p': [R(q[0]), R(q[1]), 0], 'pid': pid, 't': '動線穿越建國高架下方大路口，需整合號誌'})

# ---------- 提案的橋柱、電梯塔是否落在車道上 ----------
RG = {}
for z in M['data'].values():
    for r in z['road']:
        pts = r['pts']
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            for gx in range(int(min(a[0], b[0]) // 30) - 1, int(max(a[0], b[0]) // 30) + 2):
                for gy in range(int(min(a[1], b[1]) // 30) - 1, int(max(a[1], b[1]) // 30) + 2):
                    RG.setdefault((gx, gy), []).append((a, b, r['w'] / 2))


def on_lane(x, y, r):
    for a, b, hw in RG.get((int(x // 30), int(y // 30)), ()):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
        if math.hypot(x - a[0] - t * dx, y - a[1] - t * dy) < hw + r:
            return True
    return False


col_report = {}
for p in OV['proposals']:
    cols = [q for q in p['parts'] if q['k'] == 'box' and q['r'] in ('col', 'lift')]
    hit = [q for q in cols if on_lane(q['c'][0], q['c'][1], max(q['s']) / 2)]
    if cols:
        col_report[p['id']] = [len(hit), len(cols)]
    for q in hit:
        conflicts.append({'p': [R(q['c'][0]), R(q['c'][1]), 0], 'pid': p['id'], 'small': 1,
                          't': ('電梯塔' if q['r'] == 'lift' else '橋柱') + '落在車道上'})
print('proposal columns on lanes [hit, total]', col_report)

# ---------- 行人只在行穿線穿越：把所有行人路徑落在車道上、又不在行穿線上的部分切掉 ----------
XG = {}
for z in M['data'].values():
    for r in z.get('crossing', []):
        pts = r['pts']
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            for gx in range(int(min(a[0], b[0]) // 30) - 1, int(max(a[0], b[0]) // 30) + 2):
                for gy in range(int(min(a[1], b[1]) // 30) - 1, int(max(a[1], b[1]) // 30) + 2):
                    XG.setdefault((gx, gy), []).append((a, b))


def on_crossing(x, y, tol=4.5):
    for a, b in XG.get((int(x // 30), int(y // 30)), ()):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
        if math.hypot(x - a[0] - t * dx, y - a[1] - t * dy) < tol:
            return True
    return False


def legalise(f):
    """回傳合法的子路徑清單。高於地面 2 m 的（陸橋上）不檢查。"""
    pts, out, cur, cut = f['pts'], [], [], 0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        n = max(1, int(math.dist(a[:2], b[:2]) // 2))
        for k in range(n + (1 if i == len(pts) - 2 else 0)):
            t = k / n
            q = [R(a[0] + (b[0] - a[0]) * t), R(a[1] + (b[1] - a[1]) * t), round(a[2] + (b[2] - a[2]) * t, 2)]
            bad = q[2] < 2 and on_lane(q[0], q[1], -0.6) and not on_crossing(q[0], q[1])
            if bad:
                cut += 1
                if len(cur) > 1:
                    out.append(cur)
                cur = []
            else:
                cur.append(q)
    if len(cur) > 1:
        out.append(cur)
    return [o for o in out if sum(math.dist(o[i][:2], o[i + 1][:2]) for i in range(len(o) - 1)) > 4], cut


def clean(paths):
    res, cuts = [], 0
    for f in paths:
        subs, cut = legalise(f)
        cuts += cut
        tot = sum(len(x) for x in subs) or 1
        for sub in subs:
            g = dict(f)
            g['pts'] = sub[::3] + ([sub[-1]] if (len(sub) - 1) % 3 else [])
            if 'n' in f:
                g['n'] = max(1, round(f['n'] * len(sub) / tot))
            res.append(g)
    return res, cuts


ped_now, c1 = clean(ped_now)
ped_now += [{k: v for k, v in c.items() if k != 'x'} for c in cross_paths]
ped_prop, c2 = clean(ped_prop)
print('jaywalking samples removed: now', c1, 'proposal', c2)

json.dump({'col_report': col_report, 'pier_fix': CO.get('pier_fix'), 'veh': veh, 'ped_now': ped_now, 'ped_prop': ped_prop, 'conflicts': conflicts},
          open(os.path.join(W, 'flows.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('veh', len(veh), 'ped_now', len(ped_now), 'ped_prop', len(ped_prop), 'conflicts', len(conflicts))
for c in conflicts:
    print(' ', c['pid'], c['t'])
