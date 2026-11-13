# 市民大道「城市縫合」現況與提案 3D 模型

台北市市民大道三個示範區（華山、市民八德、市民敦化）的現況 3D 模型，以及依政策文字推估的提案示意量體。

- `web/`：3D 互動網站（`python3 -m http.server 8765 --directory web` 後開啟 http://localhost:8765）
- `CivicBoulevard_城市縫合_現況模型.blend`：Blender 模型（1 單位＝1 公尺，X 向東、Y 向北）
- `scripts/preprocess.py`：OSM 圖資 → 公尺座標；假設值集中在檔案開頭
- `scripts/build_blender.py`：在 Blender 內建立現況模型
- `scripts/make_overlay.py`：產生網站資料與提案示意量體
- `data/`：原始 OSM 圖資與轉換結果
- `renders/`：檢視圖

## 資料限制

平面位置來自 OpenStreetMap。高架橋面高度、橋墩位置、無資料建物的高度（約四成）與道路寬度為假設值；橋下既有設施與地下隧道未建模。提案量體的位置與尺寸為依政策文字推估的示意，非官方設計。

地圖資料 © OpenStreetMap contributors，依 ODbL 授權。
