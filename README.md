# 市民大道「城市縫合」現況與提案 3D 模型

台北市市民大道三個示範區（華山、市民八德、市民敦化）的現況 3D 模型，以及依政策文字推估的提案示意量體。

- `web/`：3D 互動網站（`python3 -m http.server 8765 --directory web` 後開啟 http://localhost:8765）
- `CivicBoulevard_城市縫合_現況模型.blend`：Blender 模型（1 單位＝1 公尺，X 向東、Y 向北）
- `scripts/preprocess.py`：OSM 圖資 → 公尺座標；假設值集中在檔案開頭
- `scripts/build_blender.py`：在 Blender 內建立現況模型
- `scripts/make_overlay.py`：產生網站資料、提案示意量體與高架橋細部（街景判讀參數在此）
- `scripts/build_detail_blender.py`：在 Blender 內重建高架橋體與橋下現況
- `data/`：原始 OSM 圖資與轉換結果
- `renders/`：檢視圖

## 資料限制

平面位置來自 OpenStreetMap。高架橋體的斷面、橋墩形式與高度是比對街景照片估計的（低層段橋面約 10.5 m、高層段約 15.5 m、梁深約 2.3 m，誤差約 ±1.5 m），橋墩為每 30 m 一支的推估位置。橋下現況只在 10 個街景抽樣點各標示前後 50 m。無資料建物的高度（約四成）與道路寬度為假設值；地下隧道與地下停車場未建模。提案量體的位置與尺寸為依政策文字推估的示意，非官方設計。

街景照片僅作為目視判讀的參考，本儲存庫不含任何街景影像。

地圖資料 © OpenStreetMap contributors，依 ODbL 授權。
