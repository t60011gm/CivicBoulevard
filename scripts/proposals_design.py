# 提案設施細部設計：尺寸依人因與交通工程規範，形狀以 parts 基本形體輸出。
# 由 make_overlay.py 以 exec 載入，共用其全域變數（civic_y、deck_z、median_width、DET、stats、OBS…）。

# 規範數值。最後一欄為查證程度：
#   1 = 已對照條文原文；2 = 僅部分查證（二手引述，或只查到其中一部分）；0 = 查無規範依據，為本模型取值
SPEC_V = '市區道路及附屬工程設計規範（115 年 4 月 23 日修正）'
STD = {
    'walk':    ('人行道淨寬', '宜 2.5 m 以上，不得小於 1.5 m', SPEC_V + ' 6.1', 1),
    'head':    ('行人淨高', '人行道 2.1 m 以上；人行天橋上方宜 2.5 m、不得小於 2.1 m', SPEC_V + ' 6.2、11.4.2', 1),
    'share':   ('人車共用道淨寬', '宜 3.0 m 以上，最小 2.0 m', SPEC_V + ' 5.3', 1),
    'rail':    ('天橋欄杆', '不得低於 1.1 m，不得有可攀爬的水平橫條', SPEC_V + ' 11.4.4', 1),
    'bridge_w': ('人行天橋淨寬', '尖峰每小時 4000 人以下 2.0 m、4000–5000 人 2.5 m；不得小於 1.5 m', SPEC_V + ' 表 11.4.1；設計標準第 17 條', 1),
    'bridge_loc': ('天橋設置條件與位置', '以平面穿越為原則；雙向六車道以上且尖峰小時行人 580 人次、車輛 3,360 輛以上得設；與相鄰行穿線距離不宜小於 200 m', SPEC_V + ' 11.1–11.3', 1),
    'ramp':    ('無障礙坡道', '最大 1:12，每段水平長 9 m 內設 1.5 m 平臺', SPEC_V + ' 14.3', 1),
    'curb':    ('路緣斜坡', '坡度宜小於 1:12，淨寬宜 1.5 m 以上，坡頂平臺不小於 1.2 m', SPEC_V + ' 14.2', 1),
    'refuge':  ('行人庇護島', '穿越長度 15 m 以上宜設、25 m 以上應設；寬 1.5 m 以上；高 20 cm、屏障式緣石', SPEC_V + ' 15.2.5', 1),
    'zebra':   ('枕木紋行穿線', '線寬 40 cm、間隔 40–80 cm、線段長 2–8 m', '道路交通標誌標線號誌設置規則 第 185 條', 1),
    'speed':   ('行人步行速率', '一般 1.0 m/s、學童眾多地點 0.8 m/s、視障語音號誌處 0.5 m/s', '道路交通標誌標線號誌設置規則 第 231 條', 1),
    'veh':     ('車道淨高', '立體交叉處不得小於 4.6 m', '市區道路及附屬工程設計標準 第 14 條；' + SPEC_V + ' 4.3.3', 1),
    'stair':   ('天橋階梯', '級高 16 cm 以下、級深 26 cm 以上，55 ≦ 2R+T ≦ 65；垂直每 2–3 m 設深 1.5 m 平臺', SPEC_V + ' 11.4.3', 1),
    'fire':    ('消防車通行', '淨寬 3.5 m 以上（已查證）；淨高 4.5 m（未查到條文）', '臺北市政府消防通道劃設及管理作業程序；淨高部分查無原文', 2),
    'play':    ('遊具使用區', '遊具周圍 1.83 m', 'CNS 12642（付費標準，未取得原文；數值見標檢局釋疑研討會紀錄）', 2),
    'dog':     ('狗活動區面積', '最小 300 m²，大小犬分區合計 700 m²', '臺北市民間推動設置公園狗活動區相關要點', 1),
    'court':   ('3x3 籃球場', '場地 15 m × 11 m（已查證）；四周緩衝 1.5 m（未查到）', 'FIBA 3x3 規則（官方檔案無法開啟，尺寸為搜尋引述）', 2),
    'side':    ('設施與車道側向淨距', '0.5 m', '查無對應條文；規範僅對車輛轉向軌跡訂 0.25 m 側向淨距（4.2.4、15.2.3）。0.5 m 為本模型取值', 0),
    'crowd':   ('站立觀眾密度', '每人 0.5 m²', '我國查無法定值，0.5 m² 為本模型取值；臺北市大型活動建議表（引自美國 FEMA）以每人約 0.28 m² 為危險臨界，此表未能開啟原檔', 0),
}
SIDE, FENCE_T = 0.5, 0.15
DECK_W, DECK_TOP, DECK_D = 2.5, 5.5, 0.9      # 陸橋淨寬（表 11.4.1，尖峰 4000–5000 人/時）、橋面高、結構深（車道淨高 4.6 + 0.9）
RISE, TREAD = 0.153, 0.30                      # 5.5 m / 36 級
CARR = 7.0                                     # 單向平面車道寬（2 車道）
ZA, ZB, ZC = 'A_華山', 'B_市民八德', 'C_市民敦化'


def frame(x):
    y0, y1 = civic_y(x - 5), civic_y(x + 5)
    return civic_y(x), math.atan2(y1 - y0, 10)


def at(x, s=0.0, t=0.0):
    y, a = frame(x)
    return [round(x + math.cos(a) * s - math.sin(a) * t, 2), round(y + math.sin(a) * s + math.cos(a) * t, 2)]


def box(x, s, t, sx, sy, z0, z1, role, da=0.0):
    return {'k': 'box', 'c': at(x, s, t), 's': [round(sx, 2), round(sy, 2)], 'a': round(frame(x)[1] + da, 3), 'z': [z0, z1], 'r': role}


def rib(pts, w, top, thick, role):
    return {'k': 'rib', 'pts': [[q[0], q[1], (q[2] if len(q) > 2 else top)] for q in pts], 'w': round(w, 2), 't': thick, 'r': role}


def strip(x0, x1, t, w, top, thick, role, step=5.0):
    pts, x = [], x0
    while x < x1 - 1e-6:
        pts.append(at(x, 0, t))
        x += step
    pts.append(at(x1, 0, t))
    return rib(pts, w, top, thick, role)


ALL_CROSS = sorted(x for z in stats.values() for x in z['cross_x'])
ALL_PIERS = sorted(q['p'][0] for z in DET.values() for q in z['piers'])


def usable(x):
    mw = median_width(x)
    return None if mw is None else round(mw - 2 * SIDE - 2 * FENCE_T, 1)


def site_frame(x0, x1, U, fence_h, parts, role='pad'):
    parts.append(strip(x0, x1, 0, U, 0.25, 0.1, role))
    for sgn in (1, -1):
        parts.append(strip(x0, x1, sgn * (U / 2 + FENCE_T / 2), FENCE_T, fence_h, fence_h - 0.15, 'fence'))


def access_check(x0, x1, checks):
    near_c = [c for c in ALL_CROSS if x0 - 25 <= c <= x1 + 25]
    if near_c:
        checks.append([1, '可由既有行穿線進出（範圍內或 25 m 內有 %d 處）' % len(near_c)])
    else:
        d = min(abs(c - (x0 + x1) / 2) for c in ALL_CROSS)
        checks.append([0, '範圍 25 m 內沒有跨市民大道的行穿線（最近一處距中心約 %.0f m），必須新增行穿線與行人號誌，否則民眾無法安全進入分隔帶' % d])
    obs = [o for o in OBS if x0 - 40 < o[0] < x1 + 40]
    tail = {'parking': '，需協調停管單位釋出車位', 'ug': '，出入口與梯廳不可封閉，量體須避開',
            'uturn': '，需取消或移設迴轉道', 'open': '，此處無分隔帶可用', 'green': '，需移植既有植栽',
            'ramp': '，匝道結構占用分隔帶，無法設置設施', 'facility': '，既有建物須保留或遷移', 'paved': '，可直接利用'}
    for o in obs:
        checks.append([1 if o[1] == 'paved' else 0, '街景判讀現況：' + OBS_T[o[1]][0] + ('（' + o[2] + '）' if o[2] else '') + tail[o[1]]])
    if not obs:
        checks.append([0, '此段橋下現況未經街景判讀，須現勘'])


def slots(x0, x1, margin=2.5):
    ps = [p for p in ALL_PIERS if x0 < p < x1]
    edges = [x0] + ps + [x1]
    out = []
    for i in range(len(edges) - 1):
        a = edges[i] + (margin if i > 0 else 0)
        b = edges[i + 1] - (margin if i < len(edges) - 2 else 0)
        if b - a > 3:
            out.append((a, b))
    return out, len(ps)


def head_check(x, need, checks, what):
    clr = deck_z(x) - GIRDER
    checks.append([1 if clr >= need else 0, '%s需淨高 %.1f m，此處梁底估計 %.1f m（誤差約 ±1.5 m）' % (what, need, clr)])


def spec(*rows):
    return [[STD[k][0], v, STD[k][1] + '｜' + STD[k][2], STD[k][3]] for k, v in rows]


P.clear()


def add(pid, zone, title, cat, desc, parts, specs, checks, focus, summary, src='政策原文項目；位置與配置為本模型依規範試排'):
    P.append({'id': pid, 'zone': zone, 'title': title, 'cat': cat, 'kind': 'parts', 'parts': parts, 'desc': desc,
              'specs': specs, 'checks': checks, 'note': summary, 'src': src, 'focus': focus, 'ok': all(c[0] for c in checks)})


def under_site(pid, zone, title, x0, x1, desc, build, src=None):
    xm = (x0 + x1) / 2
    us = sorted(u for u in (usable(x0 + (x1 - x0) * k / 6) for k in range(1, 6)) if u is not None)
    U = us[len(us) // 2] if us else None      # 沿線取樣 5 點的中位數
    checks, parts = [], []
    if U is None:
        U = 6.0
        checks.append([0, '此處 OSM 無雙向平面車道資料，分隔帶寬度以 7.3 m 保守假設，須現場量測'])
    else:
        checks.append([1, '分隔帶推估寬 %.1f m，扣除兩側各 %.1f m 側向淨距（本模型取值，規範無對應條文）與圍籬後，可用寬 %.1f m' % (U + 2 * SIDE + 2 * FENCE_T, SIDE, U)])
    sl, npier = slots(x0, x1)
    if npier:
        checks.append([1, '範圍內有 %d 支橋墩（推估位置），設施已避開橋墩前後各 2.5 m' % npier])
    specs, summary = build(x0, x1, U, sl, parts, checks)
    access_check(x0, x1, checks)
    kw = {'src': src} if src else {}
    add(pid, zone, title, '橋下活化', desc, parts, specs, checks, [xm, civic_y(xm)], summary, **kw)


# ---- 橋下設施 ----
def b_sport(x0, x1, U, sl, parts, checks):
    site_frame(x0, x1, U, 1.1, parts)
    if U >= 14:
        a, b = max(sl, key=lambda q: q[1] - q[0])
        xc = (a + b) / 2
        parts.append(box(xc, 0, 0, 15, 11, 0.25, 0.3, 'court'))
        parts.append(box(xc, -7.0, 0, 0.3, 1.8, 0.3, 3.05, 'equip'))
        checks.append([1, '可容納一座 3x3 籃球場（場地 15×11 m；四周 1.5 m 緩衝為本模型取值，合計需寬 14 m）'])
        summary = '配置一座 3x3 籃球場與伸展區。'
    else:
        n = 0
        for a, b in sl:
            x = a + 4.5
            while x + 4.5 <= b and n < 4:
                parts.append(box(x, 0, 0, 8.0, min(U, 4.5), 0.25, 0.3, 'court'))
                parts.append(box(x, 0, 0, 2.74, 1.525, 0.3, 1.06, 'equip'))
                n += 1
                x += 10
        checks.append([0, '可用寬 %.1f m 不足以放 3x3 籃球場（需 14 m）；改配置 %d 張桌球桌（每桌活動區 8×4.5 m）與體適能設施' % (U, n)])
        summary = '寬度放不下球場，改為 %d 張桌球桌與體適能設施。' % n
    head_check((x0 + x1) / 2, 7.0 if U >= 14 else 3.0, checks, '球類活動')
    return spec(('court', '需寬 14 m' if U >= 14 else '放不下，改桌球'), ('side', '兩側各 0.5 m'), ('rail', '圍欄 1.1 m'), ('head', '符合')), summary


def b_play(x0, x1, U, sl, parts, checks):
    site_frame(x0, x1, U, 1.2, parts, 'rubber')
    n = 0
    side = min(U - 0.6, 9.7)
    for a, b in sl:
        x = a + side / 2
        while x + side / 2 <= b:
            parts.append(box(x, 0, 0, side, side, 0.25, 0.32, 'usezone'))
            parts.append(box(x, 0, 0, side - 3.66, side - 3.66, 0.32, 2.6, 'equip'))
            n += 1
            x += side + 2.0
    checks.append([1, '可排 %d 組遊具，每組遊具本體 %.1f m 見方，四周留 1.83 m 使用區並鋪防護鋪面（實際使用區依遊具種類而異，須由合格檢驗機構依 CNS 12642 認定）' % (n, side - 3.66)])
    checks.append([0, '緊鄰雙向車道：圍籬需全周封閉、高 1.2 m 以上，出入口只能開在行穿線端並設門；另需評估車流噪音與廢氣對兒童久留的影響'])
    return spec(('play', '每組四周 1.83 m'), ('rail', '封閉圍籬 1.2 m'), ('side', '兩側各 0.5 m'), ('head', '符合')), '配置 %d 組遊具，全周封閉圍籬。' % n


def b_dog(x0, x1, U, sl, parts, checks):
    L = x1 - x0
    area = L * U
    site_frame(x0, x1, U, 1.5, parts, 'grassy')
    parts.append(box(x0 + L * 0.6, 0, 0, FENCE_T, U, 0.25, 1.5, 'fence'))
    for x in (x0 + 2, x1 - 2):
        parts.append(box(x, 0, 0, 3.0, 2.0, 0.25, 1.5, 'gate'))
    msg = '可分大犬區與小犬區（合計需 700 m²）' if area >= 700 else ('只夠單一分區（最小 300 m²）' if area >= 300 else '低於最小 300 m²')
    checks.append([1 if area >= 300 else 0, '面積約 %.0f m²；%s' % (area, msg)])
    checks.append([1, '兩端各設 3×2 m 雙重門緩衝區，圍籬高 1.5 m'])
    return spec(('dog', '約 %.0f m²' % area), ('side', '兩側各 0.5 m'), ('head', '符合')), '面積約 %.0f m²，%s。' % (area, '大小犬分區' if area >= 700 else '單一分區')


def b_walk(walk_w, panel):
    def f(x0, x1, U, sl, parts, checks):
        if U < walk_w + 1.5:
            parts.append(strip(x0, x1, 0, max(U, 1.0), 0.3, 0.1, 'infeasible'))
            checks.append([0, '步道 %.1f m 加展示帶共需寬 %.1f m，分隔帶可用寬只有 %.1f m，此段放不下；需改走兩側人行道或縮減車道' % (walk_w, walk_w + 1.5, U)])
            return spec(('share', '放不下'), ('side', '兩側各 0.5 m')), '分隔帶太窄，此段不可行。'
        parts.append(strip(x0, x1, 0, U, 0.25, 0.1, 'pad'))
        parts.append(strip(x0, x1, -(U / 2 - walk_w / 2 - 0.3), walk_w, 0.3, 0.05, 'walk'))
        for sgn in (1, -1):
            parts.append(strip(x0, x1, sgn * (U / 2 + FENCE_T / 2), FENCE_T, 1.1, 0.95, 'fence'))
        n = 0
        for a, b in sl:
            x = a + 3
            while x + 3 <= b:
                parts.append(box(x, 0, U / 2 - 0.8, panel, 0.6, 0.25, 2.4, 'equip'))
                n += 1
                x += panel + 3
        checks.append([1, '步道淨寬 %.1f m（共用道宜 3.0 m），另一側設 %d 面展示牆，牆深 0.6 m、高 2.15 m' % (walk_w, n)])
        checks.append([1 if U >= walk_w + 1.5 else 0, '步道加展示帶需寬 %.1f m，可用寬 %.1f m' % (walk_w + 1.5, U)])
        return spec(('share', '%.1f m' % walk_w), ('head', '符合'), ('rail', '兩側 1.1 m'), ('side', '兩側各 0.5 m')), '%.1f m 寬步道加 %d 面展示牆。' % (walk_w, n)
    return f


def b_market(x0, x1, U, sl, parts, checks):
    parts.append(strip(x0, x1, 0, U, 0.25, 0.1, 'pad'))
    aisle = 4.0
    rows = 2 if U >= aisle + 6 else 1
    n = 0
    for a, b in sl:
        x = a + 1.5
        while x + 1.5 <= b:
            for sgn in ((1, -1) if rows == 2 else (1,)):
                parts.append(box(x, 0, sgn * (aisle / 2 + 1.5), 2.9, 3.0, 0.3, 2.8, 'stall'))
                n += 1
            x += 3.0
    parts.append(strip(x0, x1, 0, aisle, 0.31, 0.02, 'walk'))
    checks.append([1, '可排 %d 個 3×3 m 可撤收攤位（%s），中央通道 %.1f m，可供消防車通行（需 3.5 m）' % (n, '雙排' if rows == 2 else '單排', aisle)])
    checks.append([1 if U >= aisle + 3 * rows else 0, '%s攤位加通道需寬 %.0f m，可用寬 %.1f m' % ('雙排' if rows == 2 else '單排', aisle + 3 * rows, U)])
    head_check((x0 + x1) / 2, 4.5, checks, '消防車通行（4.5 m 為未查到條文的慣用值）')
    checks.append([0, '攤位人潮會外溢到車道邊：兩側需設可移動式護欄，營業時段需交通管制或縮減車道'])
    return spec(('fire', '通道 %.1f m' % aisle), ('side', '兩側各 0.5 m'), ('head', '符合')), '%d 個 3×3 m 攤位，中央 %.0f m 通道。' % (n, aisle)


def b_stage(sw, sd, seated):
    def f(x0, x1, U, sl, parts, checks):
        site_frame(x0, x1, U, 1.1, parts)
        a, b = max(sl, key=lambda q: q[1] - q[0])
        parts.append(box(a + sd / 2 + 1, 0, 0, sd, min(sw, U - 1), 0.25, 1.15, 'stage'))
        ax0, ax1 = a + sd + 3, b - 1
        if seated:
            n = 0
            for i in range(4):
                x = ax0 + i * 0.9
                if x < ax1:
                    parts.append(box(x, 0, 0, 0.8, U - 2.4, 0.25, 0.25 + 0.225 * (i + 1), 'seat'))
                    n += int((U - 2.4) / 0.5)
            checks.append([1, '舞臺 %.0f×%.0f m；階梯座位 4 排（每階高 22.5 cm、深 80 cm），每席寬 0.5 m，約 %d 席' % (min(sw, U - 1), sd, n)])
            cap = n
        else:
            area = max(0, (ax1 - ax0)) * (U - 2.4)
            parts.append(box((ax0 + ax1) / 2, 0, 0, ax1 - ax0, U - 2.4, 0.25, 0.31, 'court'))
            cap = int(area / 0.5)
            checks.append([1, '舞臺 %.0f×%.0f m、高 0.9 m；觀眾區約 %.0f m²，以每人 0.5 m² 計約 %d 人（0.5 m² 為本模型取值，我國查無法定密度；每人低於約 0.28 m² 屬危險擁擠）' % (min(sw, U - 1), sd, area, cap)])
        checks.append([1, '兩側各留 1.2 m 疏散通道'])
        head_check((x0 + x1) / 2, 4.5, checks, '舞臺與燈架')
        checks.append([0, '高架車流噪音與梁底反射會影響演出，也會把音量反射到鄰房；需做聲學評估並限制時段'])
        return spec(('crowd', '上限約 %d 人' % cap), ('rail', '周邊 1.1 m'), ('side', '兩側各 0.5 m'), ('head', '符合')), '舞臺加觀眾區，容量約 %d 人。' % cap
    return f


under_site('a2', ZA, '運動驛站', -1120, -1050, '橋下設置運動驛站，服務兩側公園使用者。', b_sport)
under_site('a3', ZA, '兒童遊戲場', -1035, -965, '橋下全天候遮蔭遊戲場。', b_play)
under_site('a4', ZA, '寵物友善空間', -950, -885, '橋下寵物活動區。', b_dog)
under_site('a5', ZA, '動漫廊道（往三創、光華）', -840, -660, '結合三創、光華商圈的動漫主題步行廊道。', b_walk(3.0, 6.0),
           src='媒體報導項目；位置與配置為本模型依規範試排')
under_site('b1a', ZB, '藝文廊道・西段（啤酒廠側）', -330, -290, '以建國啤酒廠與忠泰美術館為兩端節點的橋下藝文步行廊道。', b_walk(3.0, 4.0))
under_site('b1b', ZB, '藝文廊道・東段（忠泰側）', -195, -130, '藝文廊道東段。建國高架下方的大路口沒有分隔帶，廊道在此中斷，需以行穿線銜接兩段。', b_walk(3.0, 4.0))
under_site('c1', ZC, '可撤收夜間市集', 520, 760, '復興南路至敦化南路間的橋下可撤收夜間市集。', b_market)
under_site('c2', ZC, '音樂廣場', 905, 960, '橋下音樂廣場。原示意位置正對市民地下停車場出入口，已東移避開。', b_stage(8, 5, False))
under_site('c3', ZC, '小型展演空間', 1055, 1150, '橋下小型展演空間，階梯座位。', b_stage(6, 4, True))


# ---- 人行陸橋 ----
def stair_parts(end, direction, parts, w=2.0):
    """由橋端往 direction 方向下降：兩段各 18 級，中間 1.5 m 平臺。回傳水平長。"""
    ca, sa = math.cos(direction), math.sin(direction)
    run = 18 * TREAD
    h_mid = DECK_TOP / 2
    p0 = end
    p1 = [p0[0] + ca * run, p0[1] + sa * run]
    p2 = [p1[0] + ca * 1.5, p1[1] + sa * 1.5]
    p3 = [p2[0] + ca * run, p2[1] + sa * run]
    parts.append({'k': 'rib', 'pts': [[p0[0], p0[1], DECK_TOP], [p1[0], p1[1], h_mid]], 'w': w, 't': 0.25, 'r': 'stair'})
    parts.append({'k': 'rib', 'pts': [[p1[0], p1[1], h_mid], [p2[0], p2[1], h_mid]], 'w': w, 't': 0.25, 'r': 'deck'})
    parts.append({'k': 'rib', 'pts': [[p2[0], p2[1], h_mid], [p3[0], p3[1], 0.15]], 'w': w, 't': 0.25, 'r': 'stair'})
    parts.append({'k': 'box', 'c': [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2], 's': [0.5, 0.5], 'a': direction, 'z': [0, h_mid - 0.25], 'r': 'col'})
    return 2 * run + 1.5


def footbridge(pid, zone, title, pts, stair_dirs, desc, extra_checks=(), col_step=20.0, cross_x=None, src='政策原文項目；位置與配置為本模型依規範試排'):
    parts, checks = [], []
    L = plen(pts)
    parts.append(rib([[q[0], q[1], DECK_TOP] for q in pts], DECK_W + 0.4, DECK_TOP, DECK_D, 'deck'))
    for sgn in (1, -1):
        off = []
        for i, q in enumerate(pts):
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
            l = math.dist(a, b) or 1
            off.append([q[0] - (b[1] - a[1]) / l * sgn * (DECK_W / 2 + 0.1), q[1] + (b[0] - a[0]) / l * sgn * (DECK_W / 2 + 0.1), DECK_TOP + 1.1])
        parts.append({'k': 'rib', 'pts': off, 'w': 0.1, 't': 1.1, 'r': 'railing'})
    acc, nxt, ncol = 0.0, 0.0, 0
    for i in range(len(pts) - 1):
        seg = math.dist(pts[i], pts[i + 1])
        while nxt <= acc + seg:
            t = (nxt - acc) / seg if seg else 0
            parts.append({'k': 'box', 'c': [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t],
                          's': [0.8, 0.8], 'a': 0, 'z': [0, DECK_TOP - DECK_D], 'r': 'col'})
            ncol += 1
            nxt += col_step
        acc += seg
    fl = 0
    for end, d in zip((pts[0], pts[-1]), stair_dirs):
        fl = stair_parts(end, d, parts)
        parts.append({'k': 'box', 'c': [end[0] - math.sin(d) * 2.6, end[1] + math.cos(d) * 2.6], 's': [2.6, 2.4], 'a': d, 'z': [0, DECK_TOP + 2.6], 'r': 'lift'})
    ramp_len = DECK_TOP * 12
    ramp_total = ramp_len + (math.ceil(ramp_len / 9) + 1) * 1.5
    checks.append([1, '橋面淨寬 %.1f m：規範表 11.4.1 尖峰每小時 4000–5000 人的等級（4000 人以下只需 2.0 m）；此處行人流量未調查，取較寬一級' % DECK_W])
    checks.append([1, '兩側欄杆 1.1 m，採直立桿件，不設可攀爬的水平橫條'])
    checks.append([1, '橋面高 %.1f m：車道淨高 4.6 m 加結構深 %.1f m' % (DECK_TOP, DECK_D)])
    checks.append([1, '兩端階梯各 36 級：級高 15.3 cm、級深 30 cm（2R+T＝60.6，符合 55–65）；每升高 2.75 m 設一處深 1.5 m 平臺；每座階梯水平長 %.1f m、寬 2.0 m' % fl])
    checks.append([1, '無障礙改以兩端電梯處理：1:12 坡道連同平臺需水平長約 %.0f m，市區路側放不下' % ramp_total])
    inside = [q for q in pts if abs(q[1] - civic_y(q[0])) < deck_halfwidth(q[0])]
    if inside:
        clr = min(deck_z(q[0]) for q in inside) - GIRDER - DECK_TOP
        checks.append([1 if clr >= 2.5 else 0, '穿過高架下方：陸橋面到高架梁底估計 %.1f m（規範宜 2.5 m、不得小於 2.1 m；估計誤差約 ±1.5 m）' % clr])
    else:
        checks.append([1, '全程在高架投影範圍外，不受梁底淨高限制'])
    checks.append([1, '共 %d 支橋柱（0.8 m 見方，間距 %.0f m），另需兩端各一座 2.6×2.4 m 電梯塔' % (ncol, col_step)])
    if cross_x is not None:
        d = min(abs(c - cross_x) for c in ALL_CROSS)
        checks.append([1 if d >= 200 else 0, '規範 11.3：天橋與相鄰行穿線距離不宜小於 200 m；此處最近的行穿線只有約 %.0f m' % d if d < 200
                       else '與最近的行穿線相距約 %.0f m，符合規範 11.3 不宜小於 200 m' % d])
    checks.append([0, '規範 11.1–11.2：人行穿越以平面為原則；設天橋需雙向六車道以上，且尖峰小時行人 580 人次、車輛 3,360 輛以上。此處流量未調查，是否達設置條件無法判斷'])
    checks.extend(extra_checks)
    xm = sum(q[0] for q in pts) / len(pts)
    ym = sum(q[1] for q in pts) / len(pts)
    specs = spec(('bridge_w', '%.1f m' % DECK_W), ('bridge_loc', '流量未調查'), ('veh', '橋下 4.6 m'), ('rail', '1.1 m'), ('stair', '15.3 / 30 cm'),
                 ('ramp', '需 %.0f m，改用電梯' % ramp_total), ('head', '符合'))
    add(pid, zone, title, '人行陸橋', desc, parts, specs, checks, [xm, ym],
        '長 %.0f m、淨寬 %.1f m、橋面高 %.1f m，兩端階梯加電梯。' % (L, DECK_W, DECK_TOP), src=src)


E_, W_ = 0.0, math.pi
footbridge('a1', ZA, '人行陸橋：華山公園 ↔ 中央藝文公園', [[-1236, 292], [-1228, 262], [-1214, 205], [-1206, 176]], (W_, E_),
           '以人行陸橋跨越市民大道，連結北側華山公園與南側中央藝文公園、華山文創園區。',
           [[1, '南北兩端都落在公園綠地內，階梯與電梯有空間可放'],
            [0, '橋柱不能落在車道上：跨越兩向車道各需約 %.0f m 無柱跨距，示意的等距橋柱須依車道位置重排' % (CARR + 1)]], col_step=28.0, cross_x=-1220)
footbridge('b5', ZB, '懷生國小人行陸橋優化', [[189, -68], [190, -45], [191, -18]], (W_, W_),
           '優化既有跨越市民大道的人行陸橋，改善懷生國小學童通學。',
           [[1, '學童多的地點，行人速率以 0.8 m/s 計；陸橋可完全避開車流'],
            [0, '既有陸橋的實際寬度、階梯與有無電梯未經查證；此為依規範重排的目標配置，非現況'],
            [0, '兩端落在既有人行道上：階梯水平長約 12 m、寬 2 m，加上電梯塔後，人行道剩餘淨寬須現場量測（至少留 1.5 m）']],
           col_step=25.0, cross_x=190, src='政策原文項目；位置取自 OSM 既有陸橋，配置為本模型依規範試排')
cb = line_along(1189, 1414, off=-17.0, step=15.0)
footbridge('c4', ZC, '人行陸橋評估：181 巷 ↔ 延吉街', cb, (W_, E_),
           '政策提出評估 181 巷至延吉街約 300 公尺路段設置人行陸橋，串聯忠孝復興與敦化兩商圈。',
           [[1, '模型量得 181 巷口到延吉街口約 %.0f m（政策文字為約 300 公尺）' % plen(cb)],
            [0, '沿南側人行道上方架設：橋柱與兩座電梯塔都落在人行道，南側人行道實際寬度未量測；柱寬 0.8 m 加側向淨距後，人行道至少要有 2.8 m 才能保留 1.5 m 通行淨寬'],
            [0, '平行於道路的陸橋不解決「跨越」問題，仍須搭配平面穿越；上下一次要爬 5.5 m，短程行人多半不會使用'],
            [0, '設計標準第 14 條：高架結構與建築物外緣的側向淨距不得小於 4.5 m（匝道 3 m）。人行天橋是否比照須由主管機關認定；若比照，沿人行道架設的陸橋與鄰房距離很可能不足']])


# ---- 平面穿越（6 處）----
def crossing(i, x):
    n = near(x, surf_pts, 30)
    ys = [q[1] for q in n]
    sep = (max(ys) - min(ys)) if len(n) >= 2 else 16.0
    mw = max(0.0, sep - CARR)
    isl = max(mw, 1.5)
    total = sep + CARR
    cw = 4.0
    parts, checks = [], []
    for sgn in (1, -1):
        tc = sgn * sep / 2
        t = tc - CARR / 2 + 0.2
        while t < tc + CARR / 2:
            parts.append(box(x, 0, t, cw, 0.4, 0.17, 0.2, 'zebra'))
            t += 1.0
        parts.append(box(x, 0, sgn * (sep / 2 + CARR / 2 + 0.9), 1.5, 1.8, 0.0, 0.22, 'curb'))
    parts.append(box(x, 0, 0, cw + 2.0, isl, 0.0, 0.2, 'island'))
    parts.append(box(x, 0, 0, cw, isl, 0.2, 0.22, 'walk'))
    for sgn in (1, -1):
        for s in (-(cw / 2 + 0.6), cw / 2 + 0.6):
            parts.append(box(x, s, sgn * (isl / 2 - 0.3), 0.25, 0.25, 0.2, 1.0, 'bollard'))
    checks.append([1, '行穿線寬 %.1f m（枕木紋線寬 40 cm、間隔 60 cm）' % cw])
    need = '依規範應' if total >= 25 else ('宜' if total >= 15 else '可不')
    checks.append([1 if mw >= 1.5 else 0, '全程穿越約 %.0f m，%s設置庇護島；中央分隔帶寬約 %.1f m，%s' % (
        total, need, mw, '可兼作庇護島（需 1.5 m）' if mw >= 1.5 else '不足 1.5 m，需縮減車道寬度來補足')])
    checks.append([1, '一次通過的行人時相：1.0 m/s 需 %.0f 秒，0.8 m/s 需 %.0f 秒；改兩段式穿越後每段約 %.0f m，只需 %.0f–%.0f 秒' % (
        total, total / 0.8, CARR, CARR, CARR / 0.8)])
    checks.append([1, '兩側設路緣斜坡（坡度 1:12、淨寬 1.5 m）；庇護島採屏障式緣石、高 20 cm，端部設反光導標與防撞桿，行人穿越部分與路面順平'])
    checks.append([0, '庇護島位在橋墩之間：橋墩會遮擋駕駛視線，需把停止線退後並在島端補照明'])
    add('c5_%d' % i, ZC, '平面穿越改善 %d/6' % (i + 1), '平面穿越', '政策提出優先改善六處平面穿越。此處以兩段式穿越加中央庇護島配置。',
        parts, spec(('zebra', '寬 %.1f m' % cw), ('refuge', '寬 %.1f m' % isl), ('curb', '1:12、1.5 m'), ('speed', '%.0f / %.0f 秒' % (total, total / 0.8))),
        checks, [x, civic_y(x)], '穿越長約 %.0f m，兩段式加庇護島。' % total,
        src='政策原文項目；政策未指明是哪六處，位置取自 OSM 既有行穿線')


for i, x in enumerate([663, 781, 920, 1077, 1201, 1310]):
    crossing(i, x)


# ---- 節點與串聯動線 ----
def grid_market(pid, cx, cy, sx, sy):
    parts, n = [], 0
    parts.append({'k': 'box', 'c': [cx, cy], 's': [sx, sy], 'a': 0, 'z': [0.0, 0.12], 'r': 'pad'})
    y = cy - sy / 2 + 1.5
    row = 0
    while y + 1.5 <= cy + sy / 2:
        x = cx - sx / 2 + 1.5
        while x + 1.5 <= cx + sx / 2:
            parts.append({'k': 'box', 'c': [x, y], 's': [2.9, 3], 'a': 0, 'z': [0.12, 2.7], 'r': 'stall'})
            n += 1
            x += 3
        row += 1
        y += 3 if row % 2 else 7     # 兩排背對背，排間留 4 m 通道
    add(pid, ZB, '文創市集（建國啤酒廠）', '節點活化', '配合啤酒廠改造設置文創市集。', parts,
        spec(('fire', '通道 4.0 m'), ('walk', '通道 4.0 m')),
        [[1, '%.0f×%.0f m 範圍可排 %d 個 3×3 m 攤位，兩排背對背、排間通道 4.0 m' % (sx, sy, n)],
         [0, '建國啤酒廠為市定古蹟且仍在生產，可釋出範圍需與臺酒公司及文資主管機關確認；此配置僅示意容量']],
        [cx, cy], '%d 個 3×3 m 攤位，通道 4 m。' % n)


grid_market('b2', -372, 205, 70, 40)
add('b3', ZB, '展覽空間（啤酒貯藏庫）', '節點活化', '利用啤酒廠既有廠房作為展覽空間。',
    [{'k': 'box', 'c': [-333, 163], 's': [46, 24], 'a': 0, 'z': [0, 13.5], 'r': 'reuse'}], spec(('walk', '出入口通道宜 2.5 m')),
    [[0, '量體取自 OSM「啤酒貯藏庫」位置，高度為假設值；室內改作展覽需符合建築技術規則的出入口、逃生與無障礙規定，須由建築師檢討']],
    [-333, 163], '既有廠房再利用，未做室內檢討。')


def route(pid, title, pts, w, desc, checks):
    add(pid, ZB, title, '串聯動線', desc, [rib(pts, w, 0.3, 0.08, 'walk')],
        spec(('walk', '%.1f m' % w), ('head', '符合'), ('curb', '路口處 1:12')),
        [[1, '路徑長約 %.0f m，淨寬 %.1f m（人行道宜 2.5 m 以上）' % (plen(pts), w)]] + checks,
        [sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)], '長 %.0f m、淨寬 %.1f m。' % (plen(pts), w),
        src='政策原文項目；路徑為本模型示意')


route('b4', '串聯八德市場', [[-237, 49], [-236, 5], [-232, -24], [-205, -58], [-182, -80]], 2.5,
      '由八德市場向南穿越市民大道，接到忠泰美術館所在街廓。',
      [[0, '路徑穿越建國高架下方的大路口，需與建國南北路號誌整合，並確認既有人行道能否拓寬到 2.5 m']])
route('b6', '懷生國小通學路徑', [[189, -68], [186, -110], [178, -150], [168, -195]], 2.5,
      '由陸橋南端沿巷道接到懷生國小。',
      [[0, 'OSM 未登錄懷生國小校地，學校位置依公開地址推估；巷道若無實體人行道，需設標線型人行道並做車速管理']])

json.dump({'proposals': P, 'stats': stats, 'labels': labels, 'zones': M['zones'], 'assumptions': M['assumptions'], 'girder': GIRDER,
           'std': [list(v) for v in STD.values()]},
          open(os.path.join(OUT, 'overlay.json'), 'w'), ensure_ascii=False)

for p in P:
    print(p['id'], p['title'], '|', len(p['parts']), 'parts |', 'OK' if p['ok'] else '有待解決', '|', p['note'])
    for c in p['checks']:
        if not c[0]:
            print('     ✗', c[1][:80])
