"""在 Blender 內以 web/data/scene.json 的街景判讀細部，重建高架橋體與橋下現況。
需先執行 preprocess.py 與 make_overlay.py，並已用 build_blender.py 建立基本模型。"""
import bpy, json, math

BASE = '/Users/linjacky/CivicBoulevard'
SC = json.load(open(BASE + '/web/data/scene.json'))
OV = json.load(open(BASE + '/web/data/overlay.json'))
GD = OV.get('girder', 2.3)


def mat(name, col, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Alpha'].default_value = alpha
    m.diffuse_color = (*col, alpha)
    return m


M = {'deck': mat('CB_橋面板', (.62, .64, .68)), 'girder': mat('CB_箱型梁', (.52, .54, .58)),
     'pier': mat('CB_橋墩帽梁', (.45, .46, .49)), 'parapet': mat('CB_護欄', (.70, .71, .74)),
     'wall': mat('CB_隔音牆', (.55, .75, .66), .55), 'parking': mat('CB_橋下停車場', (.40, .47, .57)),
     'green': mat('CB_橋下綠帶', (.28, .58, .26)), 'open': mat('CB_橋下路口淨空', (.84, .80, .70)),
     'ug': mat('CB_地下停車場出入口', (.58, .40, .80)), 'car': mat('CB_停放車輛示意', (.80, .82, .85)),
     'ramp': mat('CB_匝道引道', (.55, .57, .60)), 'facility': mat('CB_橋下機房設施', (.62, .42, .26)), 'paved': mat('CB_鋪面小廣場', (.80, .75, .62))}


class Buf:
    def __init__(self):
        self.v, self.f = [], []

    def ribbon(self, pts, w, dz, thick):
        """pts: [x,y,z]；頂面在 z+dz，向下厚 thick 的實體帶"""
        n = len(pts)
        if n < 2:
            return
        b = len(self.v)
        for i, p in enumerate(pts):
            a, c = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
            dx, dy = c[0] - a[0], c[1] - a[1]
            l = math.hypot(dx, dy) or 1
            nx, ny = -dy / l * w / 2, dx / l * w / 2
            zt = (p[2] if len(p) > 2 else 0) + dz
            self.v += [(p[0] + nx, p[1] + ny, zt - thick), (p[0] - nx, p[1] - ny, zt - thick),
                       (p[0] - nx, p[1] - ny, zt), (p[0] + nx, p[1] + ny, zt)]
        for i in range(n - 1):
            s, e = b + i * 4, b + (i + 1) * 4
            for j in range(4):
                self.f.append((s + j, s + (j + 1) % 4, e + (j + 1) % 4, e + j))
        self.f.append((b, b + 1, b + 2, b + 3))
        e = b + (n - 1) * 4
        self.f.append((e + 3, e + 2, e + 1, e))

    def prism(self, ring, z0, z1):
        b, n = len(self.v), len(ring)
        self.v += [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
        for i in range(n):
            j = (i + 1) % n
            self.f.append((b + i, b + j, b + n + j, b + n + i))
        self.f.append(tuple(b + n + i for i in range(n)))
        self.f.append(tuple(b + n - 1 - i for i in range(n)))

    def box(self, cx, cy, sx, sy, z0, z1, a=0.0):
        ca, sa = math.cos(a), math.sin(a)
        self.prism([(cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)
                    for dx, dy in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2))], z0, z1)

    def make(self, name, m, coll):
        if not self.v:
            return
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.materials.append(M[m])
        me.update()
        o = bpy.data.objects.new(name, me)
        coll.objects.link(o)


for Z in SC['zones']:
    zn = Z['name']
    d = SC['data'][zn]
    vc = bpy.data.collections[zn + '_高架結構']
    for o in list(vc.objects):
        if any(k in o.name for k in ('高架橋面', '高架道路橋面', '橋墩', '箱型梁', '護欄', '隔音牆')):
            bpy.data.objects.remove(o, do_unlink=True)
    uc = bpy.data.collections.get(zn + '_橋下現況_街景判讀')
    if uc:
        for o in list(uc.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    else:
        uc = bpy.data.collections.new(zn + '_橋下現況_街景判讀')
        bpy.data.collections[zn].children.link(uc)

    dk, gd, pr, pp, nw = Buf(), Buf(), Buf(), Buf(), Buf()
    for r in d['viaduct']:
        W = r.get('W') or r['w']
        dk.ribbon(r['p'], W, 0, .35)
        gd.ribbon(r['p'], W * .55, -.35, GD - .35)
        if r['c'] and r['t']:
            continue
        acc = 14.0
        for i in range(1, len(r['p'])):
            a, b = r['p'][i - 1], r['p'][i]
            seg = math.dist(a, b)
            while acc < seg:
                t = acc / seg
                z = a[2] + (b[2] - a[2]) * t
                if z > 4.5:
                    pr.box(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, 1.6, min(W * .4, 3), 0, z - GD,
                           math.atan2(b[1] - a[1], b[0] - a[0]))
                acc += 30
            acc -= seg
    for l in d['det']['outer']:
        pp.ribbon(l, .4, 1.0, 1.0)
        nw.ribbon(l, .15, 3.2, 2.2)
    for l in d['det']['inner']:
        pp.ribbon(l, .4, .9, .9)
    for q in d['det']['piers']:
        x, y = q['p']
        for o in ([-q['g'] / 2, q['g'] / 2] if q.get('g') else [0]):
            cx, cy = x - math.sin(q['a']) * o, y + math.cos(q['a']) * o
            if not q.get('r'):
                pr.box(cx, cy, 2.4, 2.4 if q.get('g') else 3.2, 0, q['top'] - 1.8, q['a'])
            else:
                pr.prism([(cx + math.cos(i / 16 * math.tau) * 1.35, cy + math.sin(i / 16 * math.tau) * 1.35) for i in range(16)],
                         0, q['top'] - 1.8)
        pr.box(x, y, 2.8, q['cap'], q['top'] - 1.8, q['top'], q['a'])
    dk.make(zn + '_高架橋面板', 'deck', vc)
    gd.make(zn + '_高架箱型梁', 'girder', vc)
    pr.make(zn + '_橋墩與帽梁_街景估計', 'pier', vc)
    pp.make(zn + '_護欄', 'parapet', vc)
    nw.make(zn + '_隔音牆', 'wall', vc)

    for m in d['det']['median']:
        mb, ex = Buf(), Buf()
        pts, n = m['pts'], len(m['pts'])
        mb.ribbon(pts, m['w'], .32, .1)

        def at(i):
            a, c = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
            return pts[i][0], pts[i][1], math.atan2(c[1] - a[1], c[0] - a[0])
        if m['t'] == 'parking':
            for i in range(n):
                x, y, a = at(i)
                for s in (-1, 1):
                    off = s * m['w'] * .25
                    for k in (-3.2, 0, 3.2):
                        ex.box(x + math.cos(a) * k - math.sin(a) * off, y + math.sin(a) * k + math.cos(a) * off, 1.9, 4.4, .4, 1.9, a)
        elif m['t'] in ('green', 'uturn'):
            ex.ribbon(pts, m['w'] * .7, 1.3, .9)
        elif m['t'] == 'ug':
            for i in (int(n * .3), int(n * .7)):
                x, y, a = at(i)
                ex.box(x, y, 9, min(m['w'] * .6, 5), .4, 3.4, a)
        elif m['t'] == 'ramp':
            ex.ribbon(pts, min(m['w'] * .6, 7), 3.2, 2.9)
        elif m['t'] == 'facility':
            x, y, a = at(n // 2)
            ex.box(x, y, 16, min(m['w'] * .6, 7), .4, 5.5, a)
        key = 'green' if m['t'] in ('green', 'uturn') else m['t']
        nm = zn + '_%+05d_' % m['x'] + m['label'].replace('街景判讀：', '')
        mb.make(nm, key, uc)
        ex.make(nm + '_量體', 'car' if m['t'] == 'parking' else key, uc)
    print(zn, 'piers', len(d['det']['piers']), 'median', len(d['det']['median']))

bpy.ops.wm.save_mainfile()
print('saved', bpy.data.filepath)
