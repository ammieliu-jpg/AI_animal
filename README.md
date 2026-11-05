# 毛孩日常哨兵（PetSentinel）

2026 法國皇家 AI for Pets 創新徵件計畫，「預防保健」主題提案。
- 提案進度、時程、Demo 腳本與合規檢查：[`docs/proposal-plan.md`](docs/proposal-plan.md)
- 初賽提案簡報（官方模板）：[`docs/proposal/PetSentinel_proposal.pdf`](docs/proposal/PetSentinel_proposal.pdf)、[`.pptx`](docs/proposal/PetSentinel_proposal.pptx)

| 模組 | 狀態 |
|---|---|
| ① 視覺模組：影片轉成行為時間軸 | ✅ 原型完成（`pet_vision/`） |
| ② 異常偵測：個體化基線、偏離提醒 | ✅ 原型完成（`pet_anomaly/`） |
| ③ 白話提醒＋就醫觀察紀錄（LLM，含用語護欄與免責聲明） | ✅ 原型完成（`pet_notify/`） |
| ④ 一鍵 Demo（① → ② → ③，產生總覽網頁） | ✅（`petsentinel/`） |

## Windows 一鍵使用（不用打指令）

在 `AI_animal` 資料夾裡雙擊：

| 檔案 | 做什麼 | 什麼時候用 |
|---|---|---|
| `setup.bat` | 檢查 Python、安裝套件、下載並轉換 YOLO 模型 | 第一次使用，只要一次 |
| `run_demo.bat` | 跑完整 Demo，跑完自動用瀏覽器打開 `output\demo\index.html` | 每次要看 Demo |
| `update.bat` | 下載最新版程式（`git pull`） | Claude 說「程式更新好了」的時候 |

資料夾裡有 `cat eating.mp4` 和 `cat_zones.json` 時，`run_demo.bat` 會自動把影片分析放進 Demo；有 `yolo11n.onnx` 時會自動改用 YOLO 偵測。

### 一鍵跑完整 Demo

```bash
python -m petsentinel demo --out output/demo
```

加上影片（會把影片分析一起放進總覽頁）：

```bash
python -m petsentinel demo --video "cat eating.mp4" --zones cat_zones.json --detector onnx --model yolo11n.onnx --out output/demo
```

完成後打開 `output/demo/index.html`。這一頁依照 ① → ② → ③ 排列，適合直接錄成 Demo 影片。影片片段不是一整天的紀錄，所以不會混進每日資料：影片用來展示「怎麼看懂行為」，60 天的模擬紀錄用來展示「長期下來會怎樣提醒」。

---

## ① 視覺模組 `pet_vision`

把居家攝影機影片轉成**每隻寵物各自的行為事件**（喝水、進食、如廁、休息、活動），以及每日統計摘要，交給模組 ② 做異常偵測。

支援多隻寵物：每隻寵物會被追蹤並編號（`cat_1`、`cat_2`、`dog_1`……），各自記錄行為。用 `motion` 偵測器時一律視為一隻（`pet_1`），要分辨多隻請用 `onnx` 偵測器。

```
影片 ─▶ 偵測寵物 ─▶ 逐格判斷行為 ─▶ 平滑與分段 ─▶ events.csv / summary.json / annotated.mp4
        (detector)   (behavior.py)     (events.py)
```

### 安裝

```bash
pip install -r requirements.txt
```

### 快速試跑（合成影片）

```bash
python -m pet_vision synth --out output/synthetic
```

```bash
python -m pet_vision run output/synthetic/synthetic.mp4 --zones output/synthetic/zones.json --out output/run1 --ground-truth output/synthetic/ground_truth.csv
```

### 用真實影片

1. 擷取一張帶座標格線的畫面，看水碗、食碗、砂盆的位置：
   ```bash
   python -m pet_vision snapshot my_cat.mp4 --at 3 --out snapshot.jpg
   ```
2. 參考 `examples/zones.example.json` 寫一個區域設定檔。`kind` 可以是 `water`、`food` 或 `litter`，形狀可以用 `rect` 或 `polygon`。
3. 執行分析：
   ```bash
   python -m pet_vision run my_cat.mp4 --zones my_zones.json --out output/my_cat
   ```

### 輸出

| 檔案 | 內容 |
|---|---|
| `events.csv` | 行為事件：`pet_id, behavior, behavior_zh, start_s, end_s, duration_s, zone, confidence`（UTF-8 BOM，Excel 可直接開） |
| `summary.json` | 每隻寵物各行為的次數、總時長、平均時長，作為模組 ② 的每日輸入 |
| `frames.csv` | 逐格判斷與偵測框（除錯用） |
| `annotated.mp4` | 疊上區域、偵測框與行為標籤的影片（寬度縮到 1280），可直接放進 Demo |
| `overview.jpg` | 從影片平均挑 6 個畫面拼成的一張總覽圖，方便快速檢查或分享結果 |

### 偵測器

| `--detector` | 說明 | 適用 |
|---|---|---|
| `motion`（預設） | 背景相減，**不需要模型權重**。背景只在寵物不在的地方更新，所以睡著的寵物不會被當成背景；寵物完全靜止時會沿用牠最後的位置 | 固定鏡頭、單一寵物；原型開發、Demo |
| `onnx --model x.onnx` | COCO 預訓練 YOLO（ONNX 格式），只保留 cat、dog 類別 | 有其他移動物體（人、掃地機器人）的真實場景 |

ONNX 模型可以在自己電腦上這樣產生：`pip install ultralytics`，再執行 `yolo export model=yolo11n.pt format=onnx`。⚠️ Ultralytics 權重採 **AGPL-3.0** 授權，請在提案附錄註明（注意事項第 16 點）。

### 行為判斷規則

規則刻意寫得可以解釋，提案的「AI 應用方法」才能清楚交代輸入如何變成輸出：

1. 沒偵測到寵物 → **不在畫面**
2. 寵物完全靜止、偵測器沿用最後位置 → **休息**
3. 寵物在區域內，而且沒有在走動 → **喝水**、**進食**、**如廁**
   - 碗：寵物的身體框蓋住碗區 ≥ 50%
   - 砂盆：寵物身體中心落在砂盆區內
   - 寵物身體框同時蓋住好幾個碗時（鏡頭很近、寵物很大），選**畫面變化最多的那一碗**：正在吃或喝的寵物頭會一直動，沒被碰的碗則幾乎不變
   - 如果有姿態模型提供 `nose` 關鍵點，就改用鼻子位置判斷，最準
4. 其他情況依速度判斷 → **活動**或**休息**

速度的單位是「每秒移動幾個身體對角線長」，所以不受解析度和距離影響。逐格結果經過 1 秒多數決平滑，太短的片段會併入相鄰事件。例如只是經過水碗 1 秒，不會算成喝水。最短時長：喝水 3 秒、進食 5 秒、如廁 8 秒。

### 測試

```bash
python -m pytest -q
```

目前有 18 項測試，涵蓋區域判斷、行為規則、多碗判斷、多寵物追蹤、事件平滑、ONNX 後處理，以及合成影片的端到端測試。

**目前驗證結果（請誠實看待）**：在合成影片上，逐格準確率是 100%（不計入行為轉換前後各 1 秒）。合成影片背景乾淨、只有一隻寵物、動作是照腳本走的，比真實情況簡單很多，**這個數字不代表真實場景的表現**。下一步要用有授權的真實貓狗影片（見 `docs/proposal-plan.md` §3）人工標註約 10 段片段，重新評估。

### 已知限制

- `motion` 偵測器假設**固定鏡頭、單一寵物，而且影片開頭房間是空的**；寵物一開始就在畫面裡、有人走動或鏡頭移動時會誤判，這時請改用 `onnx` 偵測器
- 寵物編號只在**同一支影片內**有效：今天的 `cat_1` 不一定是昨天的 `cat_1`。要跨天認出同一隻貓，需要加入個體辨識（依毛色、花紋），這是之後要做的部分
- 兩隻寵物擠在一起或互相遮擋時，編號可能會互換
- 碗區判斷用的是身體框，「站在碗旁邊但沒在喝」也可能被判成喝水。之後加入姿態模型（DeepLabCut SuperAnimal-Quadruped）的鼻子關鍵點可以改善
- 長時間躺在砂盆裡會被判成「休息」（這是刻意的設計）

### 合規提醒

- 這個模組只輸出「觀察到的行為」，不做任何健康判斷（注意事項第 33 點）
- 合成影片要標示為模擬資料；真實影片要確認授權和飼主同意（第 31 點）

---

## ② 異常偵測模組 `pet_anomaly`

輸入每隻寵物**每天**的行為統計（喝水次數與時間、進食、如廁、活動、休息），學習**這隻寵物自己的正常模式**，在行為持續偏離時給出提醒。

```
daily.csv ─▶ 個體化基線 ─▶ 每項指標的偏離分數 ─▶ 持續性判斷 ─▶ 提醒等級 ─▶ alerts.json（給模組 ③）＋趨勢圖
```

### 快速試跑（模擬資料）

```bash
python -m pet_anomaly simulate --out output/sim
```

```bash
python -m pet_anomaly detect output/sim/daily.csv --out output/anomaly --episodes output/sim/episodes.csv --simulated
```

```bash
python -m pet_anomaly evaluate output/sim/daily.csv --episodes output/sim/episodes.csv
```

`detect` 會產生：
- `alerts.json`：每隻寵物每天的評估，含等級與原因
- `latest.json`：每隻寵物最新一天的評估，給每日推播用
- `trend_<pet_id>.png`：趨勢圖

把模組 ① 的結果加進每日資料：`python -m pet_anomaly ingest output/run1/events.csv --date 2026-11-05 --daily data/daily.csv`。這需要錄滿一整天的影片，短片段不能直接和全天的基線比較。

### 方法

| 步驟 | 做法 | 為什麼 |
|---|---|---|
| 建立基線 | 前 **14 天**只學習、不提醒；之後每天用最近 28 天的**中位數**與 **MAD** | 中位數和 MAD 不會被少數幾個怪日子拉偏 |
| 週末作息 | 從這隻寵物自己的紀錄估計「週末比平日多或少多少」，再扣掉這個差異 | 主人週末在家，寵物比較活潑，這是正常的 |
| 偏離分數 | 次數直接比較，最小波動以 √平均 為下限（次數的自然波動）；時間類指標先取對數 | 時間類指標右偏：偶爾吃比較久很正常 |
| 組合異常 | Isolation Forest（以這隻寵物自己的歷史訓練）找出「單項都不誇張，但組合很少見」的日子 | 只會升到「留意」 |
| 提醒等級 | **留意**：單日偏離大，或組合異常。**建議諮詢獸醫**：最近 2–3 天的累積偏離大，而且每天都往同一方向；或兩項指標一起偏移 | 單日突發事件（例如來客人）只會到「留意」，持續的變化才升級 |
| 不污染基線 | 最近 2 天不納入基線，被判為「建議諮詢」的日子也不納入 | 避免持續中的變化慢慢被當成新的正常 |

最高等級是「建議諮詢獸醫」，系統**不做任何診斷**（注意事項第 33 點），提醒文字只描述觀察到的變化。

### 驗證結果（⚠️ 模擬資料）

10 組隨機種子 × 3 隻寵物 × 60 天。每組放入 3 段真正的行為變化，加上 1 段無害的單日事件（來客人）。對照組是「一般族群的固定範圍」：用 200 隻隨機產生的健康貓狗算出物種的正常範圍，相當於常見的「超過 X 就通知」做法，並套用完全相同的升級規則。

| | 個體化基線（本方案） | 一般族群固定範圍 |
|---|---|---|
| 抓到的真實變化 | **27 / 30（90%）** | 18 / 30（60%） |
| 平均幾天後提醒「建議諮詢」 | **2.1 天** | 2.4 天 |
| 普通日誤發「建議諮詢」 | 2.0%（約每 50 天 1 次） | 1.0% |
| 普通日出現「留意」 | 10.9% | 8.7% |
| 無害單日事件被升級 | 2 / 10 | 0 / 10 |

- 個體化基線抓到的變化明顯較多，尤其是「食慾下降、活動減少」：固定範圍 10 次裡漏掉 7 次，因為每隻貓的正常值差很多，族群範圍太寬
- 代價是誤報稍多。漏掉的 3 次都是只持續 3 天的「如廁次數突增」，因為次數本身的天天波動就很大
- 這些數字來自**我們自己設計的模擬資料**，只能說明方法的方向是對的，不能當成真實世界的準確率。上線前需要真實的長期紀錄重新驗證

趨勢圖範例（模擬資料）：[`docs/images/trend_cat_2.png`](docs/images/trend_cat_2.png)。高齡貓「小黑」的喝水和如廁次數逐漸增加，系統在第 3 天轉為「建議諮詢獸醫」。

### 已知限制

- 目前只有模擬資料。真實資料需要每天錄影，並經過模組 ① 轉成每日統計
- 「留意」約佔 1 成天數，對每天推播來說偏多。實際產品可以設定成只在「建議諮詢」時推播，「留意」只顯示在 App 裡
- 寵物編號要能跨天對應同一隻（見模組 ① 已知限制），每隻的基線才有意義

---

## ③ 白話提醒模組 `pet_notify`

把模組 ② 的數字變成飼主在手機上看得懂的提醒，並產生可以帶去給獸醫看的「就醫觀察紀錄」。

```
alerts.json ─▶ 事實整理（只用模組 ② 算好的數字）─▶ Claude 撰寫 或 系統範本 ─▶ 用語檢查 ─▶ 加上免責聲明 ─▶ 提醒／預覽頁
```

### 用法

```bash
python -m pet_notify daily output/anomaly/alerts.json --daily output/sim/daily.csv --date 2026-10-19 --out output/notify --simulated
```

```bash
python -m pet_notify vet-report output/sim/daily.csv --pet cat_2 --date 2026-10-14 --out output/notify/vet_report.html --simulated
```

- `daily` 會產生 `notifications.json` 和手機樣式的 `preview.html`（可以直接截圖放進 Demo）
- `vet-report` 會產生一頁可列印的 HTML，內容有行為統計表、提醒紀錄和趨勢圖
- 範例：[`docs/images/notify_preview.png`](docs/images/notify_preview.png)、[`docs/images/vet_report_cat_2.png`](docs/images/vet_report_cat_2.png)

### 兩種撰寫方式

| | 系統範本（預設） | Claude 撰寫（加 `--llm`） |
|---|---|---|
| 需要什麼 | 不需要任何東西 | Anthropic API 金鑰（`ANTHROPIC_API_KEY`），依用量計費 |
| 文字 | 固定句型，穩定 | 更自然，能把多項變化串成一句話 |
| 規則檢查 | 有（測試保證每一天都通過） | 有。不通過就請模型重寫一次，再不通過就改用範本 |

使用的模型是 `claude-opus-5-5`，effort 設為 `low`（短文案用 low 就夠），並以結構化輸出取得 `title`、`body`、`next_step` 三個欄位。另外開啟了 server-side fallback（`fallbacks: "default"`）：模型的安全機制婉拒時，API 會自動改用建議的備用模型重試。如果仍然被婉拒，或連線失敗，就改用範本，**提醒一定會送出**。

### 用語護欄（注意事項第 33–35 點）

- **提醒等級由模組 ② 決定**，模型不能自行提高或降低；模型只負責措辭
- 模型只會拿到模組 ② 算好的數字，並被要求不能自己編數字
- **禁用詞檢查**（`pet_notify/rules.py`）：診斷類詞語、器官與病名、治療或用藥、保證性說法（例如「不用擔心」「不用看醫生」）、換飼料、品牌名稱。寧可誤擋，也不放過
- 每則提醒的同一張卡片上，都附上第 35 點規定的免責聲明全文，不是放在頁尾或連結裡
- 等級最高的提醒固定引導「近期聯絡獸醫，並帶上就醫觀察紀錄」，不會勸飼主延後就醫

### 已知限制

- 這個雲端開發環境沒有 API 金鑰，**Claude 撰寫路徑只用模擬的 client 測試過**（確認了請求格式、重試和備援流程）。真正的文字品質需要有金鑰時實際跑一次再檢查
- 禁用詞清單是人工整理的，可能有漏網之魚；正式上線前建議請獸醫師審閱措辭
