# 候選測試影片清單

> 整理日期：2026-11-05。來源是網路搜尋結果裡**實際出現的影片頁面網址**。
> ⚠️ 我沒有看過這些影片，「內容」欄是依照網站的標題和描述整理的。鏡頭是否固定、碗是否清楚、長度是否合適，**都要你點開確認**後才決定要不要用。
> 授權條款：[Pexels License](https://www.pexels.com/license/)、[Pixabay Content License](https://pixabay.com/service/license-summary/)。請手動逐支下載，不要用批次下載工具。

## A. 具體影片頁面（搜尋結果中確認存在）

| 代號 | 網站 | 影片頁面 | 網站上的標題／描述 | 可能適合測試 | 待確認 |
|---|---|---|---|---|---|
| C1 | Pexels | https://www.pexels.com/video/orange-cat-18242544/ | 「Orange cat」，橘貓在室內用餐，1080p | 貓進食 | 有沒有碗、鏡頭是否固定 |
| C2 | Pixabay | https://pixabay.com/videos/kitten-feed-bowl-sweet-siblings-133587/ | 「Kitten, Feed, Bowl」（sweet siblings），4K | 多隻幼貓一起吃 | 隻數、長度 |
| C3 | Pexels | https://www.pexels.com/video/a-cat-licking-the-crystal-glass-on-top-of-the-table-6869665/ | 白貓在桌上舔水晶杯，約 29 秒 | 喝水（容器是杯子，不是碗） | 杯子區域要手動框 |
| C4 | Pexels | https://www.pexels.com/video/a-cat-drinking-from-a-faucet-in-a-kitchen-sink-27895556/ | 貓在廚房水槽喝水龍頭的水，直式影片 | 不建議：搜尋結果顯示只有約 4 秒，也沒有碗 | — |
| D1 | Pexels | https://www.pexels.com/video/dog-eating-on-a-pet-bowl-8434087/ | 「Dog Eating on a Pet Bowl」，小狗在客廳吃碗裡的食物 | 狗進食 | 長度、角度 |
| D2 | Pexels | https://www.pexels.com/video/food-dog-pet-cute-4106998/ | 「A Dog Eating Food On A Pet Plate」 | 狗進食（盤子） | 內容與角度 |
| D3 | Pexels | https://www.pexels.com/video/a-dog-drinking-from-the-faucet-4094217/ | 「A Dog Drinking from the Faucet」 | 狗喝水（沒有碗） | 有沒有可以框的固定區域 |
| N1 | Pexels | https://www.pexels.com/video/pouring-dog-food-in-a-pet-bowl-8434094/ | 有人把狗飼料倒進碗裡 | **誤判測試**：手在碗旁邊不該算寵物進食 | 畫面中有沒有狗 |
| N2 | Pexels | https://www.pexels.com/video/pouring-dog-food-into-a-stainless-bowl-8434091/ | 有人把狗飼料倒進不鏽鋼碗，木地板 | 誤判測試 | 同上 |

## B. 還缺的情境：請用下面的搜尋頁自己挑

搜尋沒有找到「貓用碗喝水」「砂盆」「暗光」「監視器視角」「兩隻貓一起吃（成貓）」的具體影片頁面，請直接瀏覽：

| 缺的情境 | 搜尋頁 |
|---|---|
| 貓進食 | https://www.pexels.com/search/videos/cat%20eating/ ・ https://pixabay.com/videos/search/cat%20eating/ |
| 貓喝水 | https://pixabay.com/videos/search/cat%20drinking%20water/ |
| 餵貓（常有多隻） | https://www.pexels.com/search/videos/feeding%20cats/ |
| 狗進食 | https://www.pexels.com/search/videos/dog%20eating/ ・ https://pixabay.com/videos/search/dog%20eating/ |
| 狗喝水 | https://pixabay.com/videos/search/dog%20drinking/ |
| 狗碗 | https://pixabay.com/videos/search/dog%20bowl/ |
| 砂盆 | https://www.pexels.com/search/videos/litter%20box%20cats/ |

挑選提醒（詳見 `video_testing_guide.md`）：鏡頭固定、看得到碗、長度 10 秒到 2 分鐘。暗光和監視器視角的素材很少，最好的來源是**朋友家裡的監視器或手機錄影**，記得取得書面同意。

## C. 你手上已經有的影片

| 檔名 | 我知道的資訊 | 要補的資料 |
|---|---|---|
| `cat eating.mp4`（原檔名 5306163-uhd_3840_2160_30fps） | 4K，兩隻以上的貓、四個碗 | 來源網址與授權 |
| `dog drinking.mp4`（原檔名 15487490_3840_2160_24fps） | 4K，白色鬥牛犬類的狗、玻璃水碗 | 來源網址與授權 |
| 13495166_1920_1080_24fps | 1080p，白貓吃飼料，背景暗 | 來源網址與授權 |
| 6543600-uhd_4096_1974_30fps | 4K 特寫，兩隻虎斑貓吃地上的飼料 | 來源網址與授權；特寫加手持，不建議計入 |

這些原檔名的格式像是 Pexels 的影片編號，但**我沒有辦法確認**。請到你當初下載的網站，在下載紀錄或瀏覽紀錄裡找到影片頁面，把網址填進 `sources.csv`。

## D. 可以直接貼進 `sources.csv` 的列（下載後再填日期，確認後再填其他欄位）

```
video,source_url,license,downloaded_on,species,n_pets,lighting,camera,labels_done,note
cat_eat_C1.mp4,https://www.pexels.com/video/orange-cat-18242544/,Pexels License,,cat,1,,,,
kitten_eat_C2.mp4,https://pixabay.com/videos/kitten-feed-bowl-sweet-siblings-133587/,Pixabay Content License,,cat,,,,,
cat_drink_C3.mp4,https://www.pexels.com/video/a-cat-licking-the-crystal-glass-on-top-of-the-table-6869665/,Pexels License,,cat,1,,,,杯子不是碗
dog_eat_D1.mp4,https://www.pexels.com/video/dog-eating-on-a-pet-bowl-8434087/,Pexels License,,dog,1,,,,
dog_eat_D2.mp4,https://www.pexels.com/video/food-dog-pet-cute-4106998/,Pexels License,,dog,1,,,,
dog_drink_D3.mp4,https://www.pexels.com/video/a-dog-drinking-from-the-faucet-4094217/,Pexels License,,dog,1,,,,沒有碗
pour_food_N1.mp4,https://www.pexels.com/video/pouring-dog-food-in-a-pet-bowl-8434094/,Pexels License,,dog,,,,,誤判測試
pour_food_N2.mp4,https://www.pexels.com/video/pouring-dog-food-into-a-stainless-bowl-8434091/,Pexels License,,dog,,,,,誤判測試
```
