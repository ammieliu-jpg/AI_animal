# 毛孩日常哨兵（PetSentinel）

2026 法國皇家 AI for Pets 創新徵件計畫，「預防保健」主題提案。
提案架構、Demo 規劃與資料集清單見 [`docs/proposal-plan.md`](docs/proposal-plan.md)。

| 模組 | 狀態 |
|---|---|
| ① 視覺模組：影片轉成行為時間軸 | ✅ 原型完成（`pet_vision/`） |
| ② 異常偵測：個體化基線、偏離提醒 | 待開發 |
| ③ LLM 白話摘要（含護欄與免責聲明） | 待開發 |
| ④ 儀表板 | 待開發 |

---

## ① 視覺模組 `pet_vision`

把居家攝影機影片轉成寵物的**行為事件**（喝水、進食、如廁、休息、活動），以及每日統計摘要，交給模組 ② 做異常偵測。

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
| `events.csv` | 行為事件：`pet_id, behavior, behavior_zh, start_s, end_s, duration_s, zone, confidence` |
| `summary.json` | 各行為的次數、總時長、平均時長，作為模組 ② 的每日輸入 |
| `frames.csv` | 逐格判斷與偵測框（除錯用） |
| `annotated.mp4` | 疊上區域、偵測框與行為標籤的影片，可直接放進 Demo |

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
   - 如果有姿態模型提供 `nose` 關鍵點，就改用鼻子位置判斷，最準
4. 其他情況依速度判斷 → **活動**或**休息**

速度的單位是「每秒移動幾個身體對角線長」，所以不受解析度和距離影響。逐格結果經過 1 秒多數決平滑，太短的片段會併入相鄰事件。例如只是經過水碗 1 秒，不會算成喝水。最短時長：喝水 3 秒、進食 5 秒、如廁 8 秒。

### 測試

```bash
python -m pytest -q
```

目前有 15 項測試，涵蓋區域判斷、行為規則、事件平滑、ONNX 後處理，以及合成影片的端到端測試。

**目前驗證結果（請誠實看待）**：在合成影片上，逐格準確率是 100%（不計入行為轉換前後各 1 秒）。合成影片背景乾淨、只有一隻寵物、動作是照腳本走的，比真實情況簡單很多，**這個數字不代表真實場景的表現**。下一步要用有授權的真實貓狗影片（見 `docs/proposal-plan.md` §3）人工標註約 10 段片段，重新評估。

### 已知限制

- `motion` 偵測器假設**固定鏡頭、單一寵物**；有人走動或光線劇烈變化時會誤判，這時請改用 `onnx` 偵測器
- 碗區判斷用的是身體框，「站在碗旁邊但沒在喝」也可能被判成喝水。之後加入姿態模型（DeepLabCut SuperAnimal-Quadruped）的鼻子關鍵點可以改善
- 長時間躺在砂盆裡會被判成「休息」（這是刻意的設計）

### 合規提醒

- 這個模組只輸出「觀察到的行為」，不做任何健康判斷（注意事項第 33 點）
- 合成影片要標示為模擬資料；真實影片要確認授權和飼主同意（第 31 點）
