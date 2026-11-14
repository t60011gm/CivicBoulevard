"""為每個衝突點產生示意圖資料（由 flows.py 以 exec 載入，共用其變數）。
格式與 deck_review.py 的 DIAG 相同，由網站的 diagramSVG() 繪製。全部是本站依模型量測數字自繪的線圖。"""
G1, G2, DK_, RED, GRN, BLU, YEL = '#c3c8cf', '#6b7280', '#2f3640', '#d50000', '#1b8a4b', '#2563eb', '#b88600'
GDR = CO.get('girder', 2.3)
PROP = {p['id']: p for p in OV['proposals']}
SURF = [v for v in CO['vpaths'] if v['k'] == 'surf']


def near_pier(x, y=None):
    return min(CO['piers'], key=lambda q: abs(q['p'][0] - x) + (abs(q['p'][1] - y) * .3 if y is not None else 0))


def sect(x, y=None):
    """x 處的橫斷面：回傳 (els, 資訊)。橫軸是離橋墩中心的橫向距離，縱軸是高度。"""
    q = near_pier(x, y)
    nx, ny = -math.sin(q['a']), math.cos(q['a'])
    lanes = []
    for v in SURF:
        p = min(v['pts'], key=lambda p: (p[0] - q['p'][0]) ** 2 + (p[1] - q['p'][1]) ** 2)
        lat = (p[0] - q['p'][0]) * nx + (p[1] - q['p'][1]) * ny
        if abs(lat) < 40:
            lanes.append((lat - v['w'] / 2, lat + v['w'] / 2))
    lanes.sort()
    soff, ext = q['top'], q['ext']
    lo = min([a for a, b in lanes] + [-ext]) - 5.5
    hi = max([b for a, b in lanes] + [ext]) + 5.5
    els = [{'t': 'r', 'x0': -ext, 'x1': ext, 'y0': soff, 'y1': soff + GDR, 'c': G1},
           {'t': 't', 'x': -ext + .3, 'y': soff + GDR + .5, 's': '高架橋（梁底約 %.1f m）' % soff, 'c': G2}]
    cw = q['cs'][0] if q['r'] else q['cs'][1]
    for o in q['offs']:
        els.append({'t': 'r', 'x0': o - cw / 2, 'x1': o + cw / 2, 'y0': 0, 'y1': soff, 'c': G2})
    for a, b in lanes:
        els.append({'t': 'r', 'x0': a, 'x1': b, 'y0': -.5, 'y1': 0, 'c': DK_})
        els.append({'t': 't', 'x': (a + b) / 2, 'y': -1.6, 's': '車道 %.1f m' % (b - a), 'a': 'middle', 'c': DK_})
    inner = None
    if len(lanes) >= 2:
        gaps = [(lanes[i + 1][0] - lanes[i][1], lanes[i][1], lanes[i + 1][0]) for i in range(len(lanes) - 1)]
        g = max(gaps)
        if g[0] > 1:
            inner = (g[1], g[2])
    return els, {'q': q, 'lanes': lanes, 'lo': lo, 'hi': hi, 'soff': soff, 'ext': ext, 'cw': cw, 'inner': inner,
                 'ytop': soff + GDR + 2.6}


def wrap(els, lo, hi, y0, y1, cap, ng=0):
    return {'x': [R(lo), R(hi)], 'y': [R(y0), R(y1)], 'cap': cap, 'els': els, 'ng': ng}


def facility_band(i):
    """設施在分隔帶上的橫向範圍（兩側離車道邊各 0.65 m）；沒有分隔帶資料時取橋墩中心兩側各 3 m。"""
    if i['inner']:
        return i['inner'][0] + .65, i['inner'][1] - .65
    return -3.0, 3.0


def dg_nocross(c):
    els, i = sect(c['p'][0], c['p'][1])
    a, b = facility_band(i)
    els.append({'t': 'r', 'x0': a, 'x1': b, 'y0': 0, 'y1': 2.6, 'c': GRN, 'o': .3, 'k': GRN})
    els.append({'t': 't', 'x': (a + b) / 2, 'y': 3.0, 's': '提案設施', 'a': 'middle', 'c': GRN})
    ln = i['lanes'][0] if i['lanes'] else (-10, -4)
    els.append({'t': 'p', 'x': ln[0] - 1.6, 'b': 0, 'h': 1.7, 'c': RED})
    els.append({'t': 'dh', 'x0': ln[0], 'x1': ln[1], 'y': 4.4, 's': '無行穿線，須橫越 %.1f m 車道' % (ln[1] - ln[0]), 'c': RED})
    d = min(abs(v - c['p'][0]) for v in cross_x)
    els.append({'t': 't', 'x': i['lo'] + .3, 'y': i['ytop'] + .2, 's': '最近的行穿線在約 %d m 外' % round(d), 'c': RED})
    return wrap(els, i['lo'], i['hi'], -2.4, i['ytop'] + 1.2, '橫斷面：行人從人行道到橋下設施，中間隔著車道')


def dg_spill(c):
    els, i = sect(c['p'][0], c['p'][1])
    a, b = facility_band(i)
    els.append({'t': 'r', 'x0': a, 'x1': b, 'y0': 0, 'y1': 2.8, 'c': GRN, 'o': .3, 'k': GRN})
    els.append({'t': 't', 'x': (a + b) / 2, 'y': 3.2, 's': '攤位與通道', 'a': 'middle', 'c': GRN})
    for k in range(3):
        els.append({'t': 'p', 'x': a - .2 + k * .45, 'b': 0, 'h': 1.7, 'c': RED})
    els.append({'t': 'dh', 'x0': a - .65, 'x1': a, 'y': 5.0, 's': '離車道邊 0.65 m', 'c': RED})
    els.append({'t': 't', 'x': i['lo'] + .3, 'y': i['ytop'] + .2, 's': '分隔帶可用寬約 %.1f m，沒有排隊等候的餘裕' % (b - a), 'c': RED})
    return wrap(els, i['lo'], i['hi'], -2.4, i['ytop'] + 1.2, '橫斷面：攤位前的人潮緊貼車道邊')


def dg_bridge_cols(c, text):
    els, i = sect(c['p'][0], c['p'][1])
    els.append({'t': 'r', 'x0': i['lo'], 'x1': i['hi'], 'y0': 4.6, 'y1': 5.5, 'c': BLU, 'o': .85})
    els.append({'t': 't', 'x': i['hi'] - .3, 'y': 5.9, 's': '提案陸橋（橋面 5.5 m、梁底 4.6 m）', 'a': 'end', 'c': BLU})
    ln = max(i['lanes'], key=lambda l: l[1] - l[0]) if i['lanes'] else (-9, -3)
    m = (ln[0] + ln[1]) / 2
    els.append({'t': 'r', 'x0': m - .4, 'x1': m + .4, 'y0': 0, 'y1': 4.6, 'c': RED})
    els.append({'t': 'dv', 'x': m + 2.2, 'y0': 0, 'y1': 4.6, 's': '車道淨高需 4.6 m', 'c': RED})
    els.append({'t': 't', 'x': i['lo'] + .3, 'y': i['ytop'] + .2, 's': text, 'c': RED})
    return wrap(els, i['lo'], i['hi'], -2.4, i['ytop'] + 1.2, '橫斷面：陸橋橋柱（紅）落在車道上')


def dg_clash(pid, n):
    c = CQ['clashes'][pid]
    x, y = c['pts'][len(c['pts']) // 2]
    els, i = sect(x, y)
    a, b = facility_band(i)
    a, b = min(a, min(i['q']['offs']) - 1.5), max(b, max(i['q']['offs']) + 1.5)
    els.append({'t': 'r', 'x0': a, 'x1': b, 'y0': 0, 'y1': 2.2, 'c': GRN, 'o': .3, 'k': GRN})
    els.append({'t': 't', 'x': a + .2, 'y': 2.6, 's': '提案設施範圍', 'c': GRN})
    for o in i['q']['offs']:
        els.append({'t': 'r', 'x0': o - i['cw'] / 2, 'x1': o + i['cw'] / 2, 'y0': 0, 'y1': 2.2, 'c': RED})
    o = i['q']['offs'][0]
    els.append({'t': 'dh', 'x0': o - i['cw'] / 2, 'x1': o + i['cw'] / 2, 'y': 4.2, 's': '柱寬 %.1f m' % i['cw'], 'c': RED})
    els.append({'t': 't', 'x': i['lo'] + .3, 'y': i['ytop'] + .2, 's': '設施範圍內有 %d 支現況橋柱，圍籬或設備須讓開' % n, 'c': RED})
    return wrap(els, i['lo'], i['hi'], -2.4, i['ytop'] + 1.2, '橫斷面：現況橋柱（紅）站在提案設施的範圍內')


def dg_stair(c):
    b = next(x for x in CQ['bridges'] if x['id'] == c['pid'])
    e = max(b['ends'], key=lambda e: e['in_road'])
    gap = e['gap']
    els = [{'t': 'r', 'x0': -7.5, 'x1': 0, 'y0': -.5, 'y1': 0, 'c': DK_}, {'t': 't', 'x': -3.7, 'y': -1.5, 's': '車道', 'a': 'middle', 'c': DK_},
           {'t': 'r', 'x0': gap, 'x1': gap + 4, 'y0': 0, 'y1': 9, 'c': G1}, {'t': 't', 'x': gap + .2, 'y': 9.4, 's': '建物', 'c': G2},
           {'t': 'r', 'x0': e['d_road'] - 1.25, 'x1': e['d_road'] + 1.25, 'y0': 0, 'y1': 5.5, 'c': RED, 'o': .45, 'k': RED},
           {'t': 't', 'x': e['d_road'] - 1.4, 'y': 6.0, 's': '階梯（寬 2.5 m、高 5.5 m）', 'a': 'end' if e['d_road'] > 2 else 'start', 'c': RED},
           {'t': 'dh', 'x0': 0, 'x1': gap, 'y': 7.4, 's': '車道邊到建物面 %.1f m' % gap, 'c': G2},
           {'t': 'p', 'x': gap - 1.0, 'b': 0, 'h': 1.7, 'c': GRN},
           {'t': 't', 'x': -7.3, 'y': 10.6, 's': '陸橋端點取樣 %d 點中有 %d 點在車道範圍內' % (e['n'], e['in_road']), 'c': RED}]
    return wrap(els, -7.8, gap + 4.3, -2.2, 11.6, '橫斷面：陸橋端點的階梯壓到車道')


def dg_ug(c):
    p = PROP[c['pid']]
    x0, x1 = xrange_of(p)
    a, b = min(((a, b) for a, b in ug), key=lambda u: abs((u[0] + u[1]) / 2 - c['p'][0]))
    lo, hi = max(x0, min(a, b)), min(x1, max(a, b))
    # 只畫車道口前後各 20 m 的範圍，設施超出的部分裁掉
    w0, w1 = min(a, b) - 20, max(a, b) + 20
    X = lambda v: max(w0, min(w1, v)) - w0
    f0, f1 = X(x0), X(x1)
    els = [{'t': 'pl', 'pts': [[X(a), 0], [X(b), 0], [X(b), -4.5]], 'c': G2},
           {'t': 't', 'x': X((a + b) / 2), 'y': -6.3, 's': '地下停車場車道（坡道長約 45 m，降約 4.5 m）', 'a': 'middle', 'c': G2},
           {'t': 'r', 'x0': f0, 'x1': f1, 'y0': 0, 'y1': 2.8, 'c': GRN, 'o': .3, 'k': GRN},
           {'t': 'r', 'x0': X(lo), 'x1': X(hi), 'y0': 0, 'y1': 2.8, 'c': RED, 'o': .35},
           {'t': 'dh', 'x0': X(lo), 'x1': X(hi), 'y': 5.0, 's': '重疊 %d m' % round(hi - lo), 'c': RED},
           {'t': 't', 'x': .5, 'y': 9.6, 's': '綠色虛線框：提案設施（全長 %d m%s）' % (round(x1 - x0), '，此圖只畫車道口附近' if x1 - x0 > w1 - w0 else ''), 'c': GRN}]
    return wrap(els, 0, w1 - w0, -8, 11.5, '縱斷面（沿市民大道方向）：設施壓在地下停車場車道口上方，車輛無法進出')


def dg_ramp(c):
    p = PROP[c['pid']]
    x0, x1 = xrange_of(p)
    L = x1 - x0
    n = under[c['pid']]['fixed'].get('匝道引道', 0)
    h = near_pier(c['p'][0], c['p'][1])['top']
    els = [{'t': 'pl', 'pts': [[4, 0], [4 + n, 0], [4 + n, h * .7]], 'c': G2},
           {'t': 't', 'x': 4 + n * .55, 'y': -1.6, 's': '匝道引道實體（擋土牆）', 'a': 'middle', 'c': G2},
           {'t': 'r', 'x0': 4, 'x1': 4 + L, 'y0': 0, 'y1': 2.6, 'c': GRN, 'o': .3, 'k': GRN},
           {'t': 't', 'x': 4.5, 'y': 3.2, 's': '提案步道範圍 %d m' % round(L), 'c': GRN},
           {'t': 'dh', 'x0': 4, 'x1': 4 + n, 'y': h * .7 + 1.5, 's': '其中 %d m 是匝道本體' % round(n), 'c': RED}]
    return wrap(els, 0, L + 8, -2.6, h * .7 + 4, '縱斷面（沿市民大道方向）：提案位置被匝道引道占滿，橋下沒有空間')


def plan(c, L, cap):
    """沿路方向的平面示意：上下兩條車道、中間分隔帶。回傳 (els, 分隔帶半寬, 車道寬)。"""
    _, i = sect(c['p'][0], c['p'][1])
    lw = sum(b - a for a, b in i['lanes']) / len(i['lanes']) if i['lanes'] else 7.0
    mh = (i['inner'][1] - i['inner'][0]) / 2 if i['inner'] else 4.0
    els = [{'t': 'r', 'x0': 0, 'x1': L, 'y0': mh, 'y1': mh + lw, 'c': DK_}, {'t': 'r', 'x0': 0, 'x1': L, 'y0': -mh - lw, 'y1': -mh, 'c': DK_},
           {'t': 'r', 'x0': 0, 'x1': L, 'y0': -mh, 'y1': mh, 'c': '#cfe3c4'},
           {'t': 't', 'x': .8, 'y': mh + lw / 2 - .8, 's': '車道 %.1f m →' % lw, 'c': '#fff'},
           {'t': 't', 'x': L - .8, 'y': -mh - lw / 2 - .8, 's': '← 車道 %.1f m' % lw, 'a': 'end', 'c': '#fff'}]
    return els, mh, lw


def dg_uturn(c):
    p = PROP[c['pid']]
    x0, x1 = xrange_of(p)
    L = min(x1 - x0, 90)
    els, mh, lw = plan(c, L, '')
    u = L * .62
    els += [{'t': 'r', 'x0': 2, 'x1': L - 2, 'y0': -mh + .65, 'y1': mh - .65, 'c': GRN, 'o': .35, 'k': GRN},
            {'t': 't', 'x': 3, 'y': mh + lw + 1.2, 's': '提案設施占用分隔帶 %d m' % round(under[c['pid']]['movable'].get('迴轉道與綠帶', 0)), 'c': GRN},
            {'t': 'r', 'x0': u - 4, 'x1': u + 4, 'y0': -mh, 'y1': mh, 'c': RED, 'o': .6},
            {'t': 't', 'x': u, 'y': -mh - lw - 2.6, 's': '既有迴轉道缺口被設施堵住，車輛無法迴轉', 'a': 'middle', 'c': RED}]
    return wrap(els, 0, L, -mh - lw - 4.2, mh + lw + 3.4, '平面示意（俯視）：分隔帶寬約 %.1f m，迴轉道位置為示意' % (2 * mh), ng=1)


def dg_junction(c):
    p = PROP[c['pid']]
    x0, x1 = xrange_of(p)
    n = under[c['pid']]['fixed'].get('路口（無分隔帶）', 0)
    L = min(x1 - x0, 110)
    k = L / (x1 - x0)
    els, mh, lw = plan(c, L, '')
    w = min(n * k, L * .6)
    els += [{'t': 'r', 'x0': 6, 'x1': 6 + w, 'y0': -mh - lw - 3, 'y1': mh + lw + 3, 'c': DK_},
            {'t': 't', 'x': 6 + w / 2, 'y': mh + lw + 3.6, 's': '橫交道路路口', 'a': 'middle', 'c': DK_},
            {'t': 'r', 'x0': 2, 'x1': L - 2, 'y0': -mh + .65, 'y1': mh - .65, 'c': GRN, 'o': .35, 'k': GRN},
            {'t': 'dh', 'x0': 6, 'x1': 6 + w, 'y': 0, 's': '路口占 %d m，沒有分隔帶' % round(n), 'c': RED},
            {'t': 't', 'x': L - 1, 'y': -mh - lw - 5.2, 's': '提案範圍全長 %d m' % round(x1 - x0), 'a': 'end', 'c': GRN}]
    return wrap(els, 0, L, -mh - lw - 6.6, mh + lw + 5.6, '平面示意（俯視）：提案範圍跨過路口，路口內無法設置設施', ng=1)


def dg_bigx(c):
    els = [{'t': 'r', 'x0': 0, 'x1': 80, 'y0': -9, 'y1': 9, 'c': DK_}, {'t': 'r', 'x0': 22, 'x1': 58, 'y0': -24, 'y1': 24, 'c': DK_},
           {'t': 'r', 'x0': 27, 'x1': 53, 'y0': -24, 'y1': 24, 'c': G1, 'o': .55},
           {'t': 't', 'x': 40, 'y': 20, 's': '建國高架（上方）', 'a': 'middle', 'c': '#fff'},
           {'t': 't', 'x': 2, 'y': 5, 's': '市民大道', 'c': '#fff'},
           {'t': 'r', 'x0': 4, 'x1': 76, 'y0': -13.5, 'y1': -11, 'c': GRN, 'o': .6, 'k': GRN},
           {'t': 't', 'x': 4, 'y': -17, 's': '提案動線', 'c': GRN},
           {'t': 'dh', 'x0': 22, 'x1': 58, 'y': -20.5, 's': '須穿越建國南北路平面車道（寬度未量測）', 'c': RED}]
    return wrap(els, 0, 80, -26, 26, '平面示意（俯視，未依比例）：動線要過高架下方的大路口，需號誌配合', ng=1)


for c in conflicts:
    t = c['t']
    try:
        if c.get('small'):
            continue
        if '沒有行穿線' in t:
            c['dg'] = dg_nocross(c)
        elif '地下停車場' in t:
            c['dg'] = dg_ug(c)
        elif '迴轉道' in t:
            c['dg'] = dg_uturn(c)
        elif '匝道引道' in t:
            c['dg'] = dg_ramp(c)
        elif '路口，沒有分隔帶' in t:
            c['dg'] = dg_junction(c)
        elif '外溢' in t:
            c['dg'] = dg_spill(c)
        elif '階梯' in t:
            c['dg'] = dg_stair(c)
        elif '橋身' in t:
            b = next(x for x in CQ['bridges'] if x['id'] == c['pid'])
            c['dg'] = dg_bridge_cols(c, '橋身取樣 %d 點中有 %d 點在車道正上方' % (b['line']['n'], b['line']['over_road']))
        elif '建國高架' in t:
            c['dg'] = dg_bigx(c)
    except Exception as ex:                      # 示意圖是附加資訊，缺資料時不影響主流程
        print('  diagram skipped', c['pid'], t, repr(ex))
dg_sum = {}
for pid, rep in col_report.items():
    sm = [c for c in conflicts if c['pid'] == pid and c.get('small') and not c.get('clash')]
    if sm:
        dg_sum.setdefault(pid, {})['col'] = dg_bridge_cols(sm[len(sm) // 2], '%d 支橋柱與電梯塔中有 %d 支落在車道上' % (rep[1], rep[0]))
for pid, cl in CQ.get('clashes', {}).items():
    dg_sum.setdefault(pid, {})['clash'] = dg_clash(pid, cl['n'])
print('diagrams', sum(1 for c in conflicts if 'dg' in c), 'of', sum(1 for c in conflicts if not c.get('small')), 'summary', {k: list(v) for k, v in dg_sum.items()})
