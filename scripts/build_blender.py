"""在 Blender 內由 model.json 建立市民大道三示範區模型。1 unit = 1 m，X=東、Y=北。"""
import bpy, bmesh, json, math, os
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

BASE = '/Users/linjacky/CivicBoulevard'
M = json.load(open(os.path.join(BASE, 'data/model.json')))

# ---------- 清場 ----------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
for blk in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
    for b in list(blk):
        if b.users == 0:
            blk.remove(b)

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

# ---------- 材質 ----------
COL = {
    'ground': (0.78, 0.77, 0.74), 'bld': (0.86, 0.85, 0.82), 'bld_est': (0.80, 0.72, 0.62),
    'bld_key': (0.90, 0.45, 0.20), 'road': (0.28, 0.29, 0.31), 'civic': (0.16, 0.17, 0.20),
    'viaduct': (0.55, 0.56, 0.60), 'pier': (0.45, 0.45, 0.47), 'footway': (0.72, 0.66, 0.56),
    'crossing': (1.0, 0.85, 0.10), 'crossing_civic': (1.0, 0.15, 0.10), 'footbridge': (0.10, 0.55, 0.95),
    'cycleway': (0.75, 0.35, 0.30), 'steps': (0.55, 0.50, 0.45), 'park': (0.42, 0.66, 0.36),
    'grass': (0.52, 0.72, 0.42), 'playground': (0.95, 0.65, 0.30), 'pitch': (0.30, 0.60, 0.55),
    'parking': (0.50, 0.52, 0.58), 'school': (0.85, 0.80, 0.62), 'construction': (0.70, 0.60, 0.45),
    'site': (0.80, 0.70, 0.78), 'water': (0.35, 0.60, 0.85), 'plaza': (0.80, 0.76, 0.68),
    'rail': (0.60, 0.42, 0.25), 'tree': (0.22, 0.48, 0.22), 'label': (0.05, 0.05, 0.05),
    'metro': (0.85, 0.10, 0.45), 'bld_under': (0.60, 0.25, 0.75), 'zone': (0.9, 0.1, 0.1),
}
MAT = {}
for k, c in COL.items():
    m = bpy.data.materials.new('CB_' + k)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = 0.85
    m.diffuse_color = (*c, 1)
    MAT[k] = m


def coll(name, parent):
    c = bpy.data.collections.new(name)
    parent.children.link(c)
    return c


def mesh_obj(name, verts, faces, mat, c, edges=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, list(edges), faces)
    me.materials.append(MAT[mat])
    me.update()
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    return o


class Buf:
    def __init__(self):
        self.v, self.f = [], []

    def prism(self, pts, z0, z1):
        n = len(pts)
        b = len(self.v)
        self.v += [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
        for i in range(n):
            j = (i + 1) % n
            self.f.append((b + i, b + j, b + n + j, b + n + i))
        for tri in tessellate_polygon([[Vector((x, y, 0)) for x, y in pts]]):
            self.f.append((b + n + tri[0], b + n + tri[1], b + n + tri[2]))

    def flat(self, pts, z):
        b = len(self.v)
        self.v += [(x, y, z) for x, y in pts]
        for tri in tessellate_polygon([[Vector((x, y, 0)) for x, y in pts]]):
            self.f.append((b + tri[0], b + tri[1], b + tri[2]))

    def ribbon(self, pts, w, dz=0.0, thick=0.0):
        """pts: [(x,y,z)]；沿中心線左右各偏移 w/2，thick>0 則為實體板"""
        n = len(pts)
        if n < 2:
            return
        L, Rr = [], []
        for i in range(n):
            p = Vector(pts[i][:2])
            d = Vector((0, 0))
            if i > 0:
                a = p - Vector(pts[i - 1][:2])
                if a.length > 1e-6:
                    d += a.normalized()
            if i < n - 1:
                a = Vector(pts[i + 1][:2]) - p
                if a.length > 1e-6:
                    d += a.normalized()
            if d.length < 1e-6:
                d = Vector((1, 0))
            d.normalize()
            nrm = Vector((-d.y, d.x)) * (w / 2)
            z = pts[i][2] + dz
            L.append((p.x + nrm.x, p.y + nrm.y, z))
            Rr.append((p.x - nrm.x, p.y - nrm.y, z))
        b = len(self.v)
        self.v += L + Rr
        for i in range(n - 1):
            self.f.append((b + i, b + n + i, b + n + i + 1, b + i + 1))
        if thick > 0:
            b2 = len(self.v)
            self.v += [(x, y, z - thick) for x, y, z in L] + [(x, y, z - thick) for x, y, z in Rr]
            for i in range(n - 1):
                self.f.append((b2 + i + 1, b2 + n + i + 1, b2 + n + i, b2 + i))
                self.f.append((b + i + 1, b2 + i + 1, b2 + i, b + i))
                self.f.append((b + n + i, b2 + n + i, b2 + n + i + 1, b + n + i + 1))

    def box(self, cx, cy, sx, sy, z0, z1, ang=0.0):
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)
               for dx, dy in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2))]
        self.prism(pts, z0, z1)

    def make(self, name, mat, c):
        if self.v:
            return mesh_obj(name, self.v, self.f, mat, c)


FONT = None
for fp in ('/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc',
           '/System/Library/Fonts/Hiragino Sans GB.ttc', '/Library/Fonts/Arial Unicode.ttf'):
    if os.path.exists(fp):
        try:
            FONT = bpy.data.fonts.load(fp)
            break
        except Exception as ex:
            print('font fail', fp, ex)
print('FONT', FONT)


def label(text, x, y, z, size, c, mat='label', rot=0.0):
    cu = bpy.data.curves.new('T_' + text, 'FONT')
    cu.body = text
    cu.size = size
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    if FONT:
        cu.font = FONT
    cu.materials.append(MAT[mat])
    o = bpy.data.objects.new('標註_' + text, cu)
    o.location = (x, y, z)
    o.rotation_euler = (0, 0, rot)
    c.objects.link(o)
    return o


KEY_NAMES = ['華山', '三創', '光華', '忠泰', '啤酒', '八德市場', '懷生', '微風', 'SOGO', '太平洋崇光', '國父紀念館',
             '中央藝文', '台北科技大學', '臺北科技大學', '車站']
AREA_Z = {'site': 0.02, 'school': 0.03, 'construction': 0.04, 'park': 0.06, 'grass': 0.08, 'parking': 0.07,
          'plaza': 0.07, 'pitch': 0.10, 'playground': 0.12, 'water': 0.10}
report = {}
root = coll('市民大道_城市縫合', scene.collection)

for Z in M['zones']:
    zn = Z['name']
    D = M['data'][zn]
    zc = coll(zn, root)
    rep = report.setdefault(zn, {})

    # 地面
    g = Buf()
    g.flat([(Z['x0'], Z['y0']), (Z['x1'], Z['y0']), (Z['x1'], Z['y1']), (Z['x0'], Z['y1'])], 0.0)
    g.make(zn + '_地面', 'ground', zc)

    # 面狀
    ac = coll(zn + '_土地使用', zc)
    bufs = {}
    for a in D.get('areas', []):
        bufs.setdefault(a['kind'], Buf()).flat(a['pts'], AREA_Z[a['kind']])
    AN = {'park': '公園', 'grass': '草地', 'playground': '遊戲場', 'pitch': '球場', 'parking': '平面停車場',
          'school': '校地', 'construction': '工地_待開發', 'site': '園區基地', 'water': '水域', 'plaza': '廣場'}
    for k, b in bufs.items():
        b.make(zn + '_' + AN[k], k, ac)

    # 建物
    bc = coll(zn + '_建物', zc)
    kc = coll(zn + '_地標建物', zc)
    b_known, b_est, b_under = Buf(), Buf(), Buf()
    nk = 0
    for bd in D.get('buildings', []):
        if bd['name'] and any(k in bd['name'] for k in KEY_NAMES):
            kb = Buf()
            kb.prism(bd['pts'], 0, bd['h'])
            o = kb.make('地標_' + bd['name'], 'bld_key', kc)
            o['height_m'] = bd['h']
            o['height_source'] = bd['src']
            nk += 1
        elif bd.get('under'):
            b_under.prism(bd['pts'], 0, bd['h'])
        elif bd['src'] == 'default':
            b_est.prism(bd['pts'], 0, bd['h'])
        else:
            b_known.prism(bd['pts'], 0, bd['h'])
    b_known.make(zn + '_建物_有樓層或高度資料', 'bld', bc)
    b_est.make(zn + '_建物_高度為假設值', 'bld_est', bc)
    b_under.make(zn + '_橋下既有建物_設施', 'bld_under', bc)
    rep['建物'] = len(D.get('buildings', []))
    rep['地標建物'] = nk

    # 道路
    rc = coll(zn + '_道路', zc)
    r_all, r_civic = Buf(), Buf()
    for r in D.get('road', []):
        (r_civic if r['name'].startswith('市民大道') and '巷' not in r['name'] else r_all).ribbon(r['pts'], r['w'], 0.15)
    r_all.make(zn + '_平面道路', 'road', rc)
    r_civic.make(zn + '_市民大道平面車道', 'civic', rc)
    for cat, nm, mat, dz in (('footway', '人行道_步道', 'footway', 0.20), ('cycleway', '自行車道', 'cycleway', 0.22),
                             ('steps', '階梯', 'steps', 0.22)):
        b = Buf()
        for r in D.get(cat, []):
            b.ribbon(r['pts'], r['w'], dz)
        b.make(zn + '_' + nm, mat, rc)

    # 市民大道走廊中心線（用來判定哪些行穿線跨越市民大道）
    civ = [Vector(p[:2]) for r in D.get('road', []) if r['name'].startswith('市民大道') and '巷' not in r['name']
           for p in r['pts']]

    def near_civic(pts, tol=14.0):
        mid = Vector(pts[len(pts) // 2][:2])
        return any((mid - q).length < tol for q in civ)

    b1, b2 = Buf(), Buf()
    n_civ = 0
    for r in D.get('crossing', []):
        if near_civic(r['pts']):
            b2.ribbon(r['pts'], 3.0, 0.28)
            n_civ += 1
        else:
            b1.ribbon(r['pts'], 3.0, 0.26)
    b1.make(zn + '_行人穿越道', 'crossing', rc)
    b2.make(zn + '_行人穿越道_市民大道上', 'crossing_civic', rc)
    rep['行穿線段_全部'] = len(D.get('crossing', []))
    rep['行穿線段_市民大道上'] = n_civ

    # 高架
    vc = coll(zn + '_高架結構', zc)
    civ_deck, oth_deck, piers = Buf(), Buf(), Buf()
    civ_len = 0.0
    for r in D.get('viaduct', []):
        is_civ = '市民' in r['name']
        tgt = civ_deck if is_civ else oth_deck
        tgt.ribbon(r['pts'], r['w'], 0.0, 1.8)
        # 橋墩（示意：每 35 m 一支，實際位置需現勘）
        acc = 17.0
        for i in range(1, len(r['pts'])):
            p0, p1 = Vector(r['pts'][i - 1]), Vector(r['pts'][i])
            seg = (p1 - p0).length
            if is_civ and r['hw'] == 'trunk':
                civ_len += seg
            while acc < seg:
                p = p0.lerp(p1, acc / seg)
                if p.z > 4.0:
                    ang = math.atan2(p1.y - p0.y, p1.x - p0.x)
                    piers.box(p.x, p.y, 2.0, min(r['w'] * 0.45, 3.5), 0, p.z - 1.8, ang)
                acc += 35.0
            acc -= seg
    civ_deck.make(zn + '_市民大道高架橋面', 'viaduct', vc)
    oth_deck.make(zn + '_其他高架道路橋面', 'viaduct', vc)
    piers.make(zn + '_橋墩_示意位置', 'pier', vc)
    rep['市民高架單向累計長_m'] = round(civ_len)
    fb = Buf()
    for r in D.get('footbridge', []):
        fb.ribbon(r['pts'], max(r['w'], 3.0), 0.0, 0.6)
    fb.make(zn + '_既有人行陸橋', 'footbridge', vc)
    rep['既有人行陸橋段'] = len(D.get('footbridge', []))
    rl = Buf()
    for r in D.get('rail_elevated', []):
        rl.ribbon([(p[0], p[1], 12.0) for p in r['pts']], 4.5, 0.0, 1.5)
    rl.make(zn + '_捷運文湖線高架', 'rail', vc)

    # 樹、捷運出入口
    pc = coll(zn + '_點狀設施', zc)
    tb = Buf()
    for x, y in D.get('trees', []):
        tb.box(x, y, 0.5, 0.5, 0, 3)
        tb.box(x, y, 4, 4, 3, 8)
    tb.make(zn + '_樹木_OSM登錄', 'tree', pc)
    mb = Buf()
    for s in D.get('subway_entrances', []):
        mb.box(s['p'][0], s['p'][1], 5, 5, 0, 4)
    mb.make(zn + '_捷運出入口', 'metro', pc)
    rep['捷運出入口'] = len(D.get('subway_entrances', []))

    # 標註
    lc = coll(zn + '_標註', zc)
    label(zn.split('_')[1] + '示範區', (Z['x0'] + Z['x1']) / 2, Z['y1'] + 45, 0.5, 50, lc, 'zone')
    seen = set()
    for a in D.get('areas', []):
        if a['name'] and a['area'] > 2500 and a['name'] not in seen and a['kind'] in ('park', 'site', 'school', 'construction', 'playground'):
            seen.add(a['name'])
            cx = sum(p[0] for p in a['pts']) / len(a['pts'])
            cy = sum(p[1] for p in a['pts']) / len(a['pts'])
            label(a['name'], cx, cy, 1.0, 12, lc)
    for o in kc.objects:
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        cx = sum(p.x for p in bb) / 8
        cy = sum(p.y for p in bb) / 8
        nm = o.name.replace('地標_', '').split('.')[0]
        if nm not in seen:
            seen.add(nm)
            label(nm, cx, cy, o['height_m'] + 1.0, 10, lc)
    # 路名：取每條具名主要道路最長的一段中點
    best = {}
    for r in D.get('road', []):
        if r['name'] and r['hw'] in ('primary', 'secondary', 'tertiary') and '巷' not in r['name']:
            ln = sum((Vector(r['pts'][i][:2]) - Vector(r['pts'][i - 1][:2])).length for i in range(1, len(r['pts'])))
            if ln > best.get(r['name'], (0,))[0]:
                best[r['name']] = (ln, r)
    for nm, (ln, r) in best.items():
        if ln < 60:
            continue
        i = len(r['pts']) // 2
        p0, p1 = Vector(r['pts'][i - 1][:2]), Vector(r['pts'][min(i, len(r['pts']) - 1)][:2])
        ang = math.atan2(p1.y - p0.y, p1.x - p0.x)
        if ang > math.pi / 2 + 0.01:
            ang -= math.pi
        if ang < -math.pi / 2 + 0.01:
            ang += math.pi
        label(nm, (p0.x + p1.x) / 2, (p0.y + p1.y) / 2, 0.6, 9, lc, 'crossing', ang)

    # 區界框
    x0, x1, y0, y1 = Z['x0'], Z['x1'], Z['y0'], Z['y1']
    mesh_obj(zn + '_區界', [(x0, y0, 0.5), (x1, y0, 0.5), (x1, y1, 0.5), (x0, y1, 0.5)], [], 'zone', zc,
             edges=[(0, 1), (1, 2), (2, 3), (3, 0)])

# 比例尺：100 m 黑白相間
sc = coll('比例尺_指北', root)
Z0 = M['zones'][0]
sb = Buf()
sw = Buf()
for i in range(5):
    (sb if i % 2 == 0 else sw).box(Z0['x0'] + 50 + i * 100, Z0['y0'] - 40, 100, 8, 0, 1)
sb.make('比例尺_500m_每格100m', 'label', sc)
sw.make('比例尺_500m_白格', 'ground', sc)
label('0        100       200       300       400      500 m', Z0['x0'] + 250, Z0['y0'] - 62, 0.5, 14, sc)
label('N ↑', Z0['x0'] + 600, Z0['y0'] - 45, 0.5, 30, sc)

# 視埠
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type == 'VIEW_3D':
        sp = area.spaces.active
        sp.clip_start, sp.clip_end = 1.0, 20000.0
        sp.shading.type = 'SOLID'
        sp.shading.color_type = 'MATERIAL'
        sp.shading.show_shadows = True
        sp.shading.show_cavity = True

print(json.dumps(report, ensure_ascii=False, indent=1))
print('objects', len(bpy.data.objects))
