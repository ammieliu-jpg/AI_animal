# App 互動原型

線上版本（私人連結，分享前需在頁面的 Share 選單開啟）：https://claude.ai/artifact/3bw1D2QZSS9H3APZVewwcL

- 四個分頁：今日、趨勢、提醒、就醫紀錄
- 上方可以拖動日期，看系統每天的判斷。預設停在 2026-10-13：高齡貓「小黑」喝水持續增加的第 3 天
- 畫面上的數字全部由模組 ② ③ 依模擬的 60 天資料實際計算產生（`pet_anomaly.simulate`，seed 7），沒有手動編寫的數字
- `app.template.html` 是頁面範本，裡面的 `__DATA__` 會換成模組 ② ③ 輸出的 JSON
