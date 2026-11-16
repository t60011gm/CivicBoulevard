"""下載 Mapillary 試驗路段的影像位置與 SfM 點雲（CC BY-SA，來源 Mapillary）。
用法：MAPILLARY_TOKEN 設在環境變數；python3 scripts/mapillary_fetch.py x0 x1 y0 y1
輸出：data/mapillary/images.json、data/mapillary/clusters/<id>.json（不進版本庫）
"""
import json, math, os, sys, urllib.request, urllib.parse, zlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'data', 'mapillary')
LAT0, LON0 = 25.0450, 121.5390
KX = 111319.49 * math.cos(math.radians(LAT0))
KY = 111133.0
TOKEN = os.environ.get('MAPILLARY_TOKEN', '')
if not TOKEN:
    sys.exit('MAPILLARY_TOKEN 未設定')


def get(url, auth=True, raw=False):
    req = urllib.request.Request(url, headers={'User-Agent': 'viaduct-study/1.0'})
    if auth:
        req.add_header('Authorization', 'OAuth ' + TOKEN)
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
    return b if raw else json.loads(b)


def main():
    x0, x1, y0, y1 = [float(v) for v in sys.argv[1:5]]
    os.makedirs(os.path.join(OUT, 'clusters'), exist_ok=True)
    fields = ('id,computed_geometry,geometry,captured_at,is_pano,compass_angle,'
              'computed_compass_angle,computed_altitude,altitude,sequence,sfm_cluster,'
              'camera_type,height,width,computed_rotation')
    imgs = {}
    step = 100.0  # 分格查詢，避免單次上限截斷
    x = x0
    while x < x1:
        y = y0
        while y < y1:
            bb = '%.6f,%.6f,%.6f,%.6f' % (LON0 + x / KX, LAT0 + y / KY,
                                          LON0 + min(x + step, x1) / KX, LAT0 + min(y + step, y1) / KY)
            url = 'https://graph.mapillary.com/images?' + urllib.parse.urlencode(
                {'fields': fields, 'bbox': bb, 'limit': 2000})
            d = get(url)
            for it in d.get('data', []):
                imgs[it['id']] = it
            print('bbox', bb, len(d.get('data', [])))
            y += step
        x += step
    rows = []
    for it in imgs.values():
        g = it.get('computed_geometry') or it.get('geometry')
        if not g:
            continue
        lon, lat = g['coordinates']
        it['xy'] = [round((lon - LON0) * KX, 2), round((lat - LAT0) * KY, 2)]
        rows.append(it)
    json.dump(rows, open(os.path.join(OUT, 'images.json'), 'w'), ensure_ascii=False)
    print('images', len(rows), 'pano', sum(1 for r in rows if r.get('is_pano')))
    cl = {}
    for r in rows:
        c = r.get('sfm_cluster')
        if c and c.get('url'):
            cl[c['id']] = c['url']
    print('clusters', len(cl))
    for cid, url in cl.items():
        fp = os.path.join(OUT, 'clusters', cid + '.json')
        if os.path.exists(fp):
            continue
        try:
            b = get(url, auth=False, raw=True)
            try:
                b = zlib.decompress(b)
            except zlib.error:
                pass
            open(fp, 'wb').write(b)
            print(' cluster', cid, len(b))
        except Exception as e:
            print(' cluster', cid, 'ERR', e)


main()
