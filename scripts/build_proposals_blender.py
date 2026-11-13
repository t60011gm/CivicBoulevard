"""在 Blender 內依 web/data/overlay.json 的 parts 重建「提案示意量體」。需先執行 make_overlay.py。"""
import bpy, json, math

BASE = '/Users/linjacky/CivicBoulevard'
OV = json.load(open(BASE + '/web/data/overlay.json'))
ROLE = {'pad': (.85, .82, .76), 'rubber': (.91, .64, .36), 'grassy': (.55, .76, .48), 'court': (.25, .56, .69),
        'usezone': (.96, .76, .42), 'equip': (.85, .28, .23), 'fence': (.30, .34, .39), 'gate': (.13, .14, .16),
        'walk': (.79, .71, .54), 'stall': (1, .48, .10), 'stage': (.48, .31, .82), 'seat': (.69, .55, .91),
        'deck': (.12, .61, .94), 'stair': (.42, .77, 1), 'railing': (.11, .44, .66), 'col': (.42, .45, .50),
        'lift': (.04, .37, .65), 'zebra': (1, 1, 1), 'island': (.60, .64, .68), 'curb': (.91, .88, .78),
        'bollard': (1, .8, 0), 'reuse': (.71, .33, .88), 'infeasible': (.90, .20, .12)}
MAT = {}
for k, c in ROLE.items():
    m = bpy.data.materials.get('提案_' + k) or bpy.data.materials.new('提案_' + k)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*c, 1)
    m.diffuse_color = (*c, 1)
    MAT[k] = m

root = bpy.data.collections['市民大道_城市縫合']
old = bpy.data.collections.get('提案示意量體')
if old:
    for o in list(old.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(old.children):
        bpy.data.collections.remove(c)
    bpy.data.collections.remove(old)
pc = bpy.data.collections.new('提案示意量體')
root.children.link(pc)
sub = {}


def add_rib(V, F, pts, w, thick):
    n, b = len(pts), len(V)
    for i, p in enumerate(pts):
        a, c = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        dx, dy = c[0] - a[0], c[1] - a[1]
        l = math.hypot(dx, dy) or 1
        nx, ny = -dy / l * w / 2, dx / l * w / 2
        V += [(p[0] + nx, p[1] + ny, p[2] - thick), (p[0] - nx, p[1] - ny, p[2] - thick),
              (p[0] - nx, p[1] - ny, p[2]), (p[0] + nx, p[1] + ny, p[2])]
    for i in range(n - 1):
        s, e = b + i * 4, b + (i + 1) * 4
        for j in range(4):
            F.append((s + j, s + (j + 1) % 4, e + (j + 1) % 4, e + j))
    F.append((b, b + 1, b + 2, b + 3))
    e = b + (n - 1) * 4
    F.append((e + 3, e + 2, e + 1, e))


def add_box(V, F, q):
    cx, cy = q['c']
    sx, sy = q['s']
    ca, sa = math.cos(q['a']), math.sin(q['a'])
    ring = [(cx + dx * ca - dy * sa, cy + dx * sa + dy * ca) for dx, dy in
            ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2))]
    b = len(V)
    V += [(x, y, q['z'][0]) for x, y in ring] + [(x, y, q['z'][1]) for x, y in ring]
    for i in range(4):
        j = (i + 1) % 4
        F.append((b + i, b + j, b + 4 + j, b + 4 + i))
    F.append((b + 4, b + 5, b + 6, b + 7))
    F.append((b + 3, b + 2, b + 1, b))


n_obj = 0
for p in OV['proposals']:
    zc = sub.get(p['zone'])
    if not zc:
        zc = bpy.data.collections.new('提案_' + p['zone'])
        pc.children.link(zc)
        sub[p['zone']] = zc
    pcoll = bpy.data.collections.new('提案_' + p['title'])
    zc.children.link(pcoll)
    by = {}
    for q in p['parts']:
        V, F = by.setdefault(q['r'], ([], []))
        if q['k'] == 'rib':
            add_rib(V, F, q['pts'], q['w'], q['t'])
        else:
            add_box(V, F, q)
    for r, (V, F) in by.items():
        me = bpy.data.meshes.new(p['title'] + '_' + r)
        me.from_pydata(V, [], F)
        me.materials.append(MAT[r])
        me.update()
        o = bpy.data.objects.new(p['title'] + '_' + r, me)
        pcoll.objects.link(o)
        o['說明'] = p['desc']
        o['試排結果'] = p['note']
        o['規範檢核'] = '\n'.join(('✓ ' if c[0] else '✗ ') + c[1] for c in p['checks'])
        o['來源'] = p['src']
        n_obj += 1
bpy.ops.wm.save_mainfile()
print('proposals', len(OV['proposals']), 'objects', n_obj)
