"""Fill the official AI for Pets template (frame.pptx) with the PetSentinel proposal."""
import copy
import sys

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

W = sys.argv[1]  # deck work dir
IMG = W + "/img/"
RED, DARK, GRAY, PINK, LIGHT, WHITE = "E2001A", "2D2D2D", "5B5C5F", "ECEFF2", "F6F7F8", "FFFFFF"
HEAD, MUTED = "3A3F45", "8A9096"  # table header, number circles
GREEN, AMBER, ORANGE = "3F9D6B", "D9A521", "E07A2E"
FONT = "Noto Sans TC"


def rgb(h):
    return RGBColor.from_string(h)


def style_run(run, size, color=DARK, bold=False):
    f = run.font
    f.size, f.bold = Pt(size), bold
    f.color.rgb = rgb(color)
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", FONT)


def text(slide, x, y, w, h, paras, size=12, color=DARK, bold=False, align="l", anchor="t",
         bullet=False, space_after=4, line=1.15, name=None, margin=0.04):
    """paras: list of str or list of runs [(text, {size,color,bold})]."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", Inches(margin))
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        p.space_after = Pt(space_after)
        p.line_spacing = line
        runs = para if isinstance(para, list) else [(para, {})]
        if bullet:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(Inches(0.18)))
            pPr.set("indent", str(-Inches(0.16)))
            bu = etree.SubElement(pPr, qn("a:buChar"))
            bu.set("char", "•")
        for t, o in runs:
            r = p.add_run()
            r.text = t
            style_run(r, o.get("size", size), o.get("color", color), o.get("bold", bold))
    return tb


def box(slide, x, y, w, h, fill=LIGHT, shape=MSO_SHAPE.RECTANGLE, line=None, name=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.12
    s.text_frame.text = ""
    return s


def circle_num(slide, x, y, d, label, fill=HEAD, size=12):
    c = box(slide, x, y, d, d, fill, MSO_SHAPE.OVAL)
    tf = c.text_frame
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", 0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    style_run(r, size, WHITE, True)
    return c


def card(slide, x, y, w, h, title, lines, fill=LIGHT, title_color=DARK, size=12, bullet=True, title_size=14):
    box(slide, x, y, w, h, fill)
    text(slide, x + 0.15, y + 0.1, w - 0.3, 0.35, [title], size=title_size, color=title_color, bold=True)
    text(slide, x + 0.15, y + 0.48, w - 0.3, h - 0.55, lines, size=size, bullet=bullet, space_after=3)


def picture(slide, path, x, y, w=None, h=None, border=True):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    pic = slide.shapes.add_picture(path, Inches(x), Inches(y), **kw)
    if border:
        pic.line.color.rgb = rgb("D9D9D9")
        pic.line.width = Pt(0.75)
    return pic


def table(slide, x, y, w, rows, col_w, header_fill=HEAD, size=11, row_h=0.32, first_col_bold=True):
    shp = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    tbl = shp.table
    tblPr = tbl._tbl.tblPr
    style = tblPr.find(qn("a:tableStyleId"))
    if style is not None:
        style.text = "{5940675A-B579-460E-94D1-54222C63F5DA}"  # No Style, Table Grid
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Inches(cw)
    for ri, row in enumerate(rows):
        tbl.rows[ri].height = Inches(row_h)
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.fill.solid()
            head = ri == 0
            cell.fill.fore_color.rgb = rgb(header_fill if head else (WHITE if ri % 2 else LIGHT))
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            runs = val if isinstance(val, list) else [(val, {})]
            p = tf.paragraphs[0]
            for t, o in runs:
                r = p.add_run()
                r.text = t
                style_run(r, o.get("size", size), o.get("color", WHITE if head else DARK),
                          o.get("bold", head or (first_col_bold and ci == 0)))
    return shp


def set_run_text(shape, value):
    runs = [r for p in shape.text_frame.paragraphs for r in p.runs]
    runs[0].text = value
    for r in runs[1:]:
        r.text = ""


def frame(slide, num, title, key, key_w=None):
    by_id = {s.shape_id: s for s in slide.shapes}
    ids = sorted(by_id)
    # frame shapes keep the order of slide 3: number, title, line, pill, pill text, 4 body boxes, logo
    num_s, title_s, _line, pill, pill_t = (by_id[i] for i in ids[:5])
    for i in ids[5:9]:
        el = by_id[i]._element
        el.getparent().remove(el)
    set_run_text(num_s, num)
    set_run_text(title_s, title)
    set_run_text(pill_t, key)
    for r in (r for p in pill_t.text_frame.paragraphs for r in p.runs):
        r.font.size = Pt(12)
    width = key_w or min(9.0, 0.45 + 0.175 * len(key))
    pill.fill.solid()
    pill.fill.fore_color.rgb = rgb(LIGHT)
    for r in (r for p in pill_t.text_frame.paragraphs for r in p.runs):
        r.font.color.rgb = rgb(DARK)
    pill.width = Inches(width)
    pill_t.width = Inches(width - 0.25)


def caption(slide, x, y, w, s, color=GRAY, size=10, align="l"):
    return text(slide, x, y, w, 0.3, [s], size=size, color=color, align=align)


prs = Presentation(W + "/frame.pptx")
S = list(prs.slides)

# ---------------------------------------------------------------- cover
cov = {s.shape_id: s for s in S[0].shapes}
set_run_text(cov[55], "毛孩日常哨兵 PetSentinel")
set_run_text(cov[57], "投稿主題：預防保健｜【團隊名稱】｜【團隊成員】")
set_run_text(cov[60], "上班時也能察覺貓犬「跟平常不一樣」的 AI 照護提醒")

# ---------------------------------------------------------------- 01 提案摘要
s = S[1]
frame(s, "01", "提案摘要", "從「有動靜才通知」，進化到「跟平常不一樣才提醒」")
card(s, 0.5, 1.75, 4.4, 1.9, "作品與問題", [
    [("投稿主題｜", {"bold": True}), ("預防保健：日常健康管理、行為觀察、年齡階段照護", {})],
    [("目標對象｜", {"bold": True}), ("白天上班、家中有室內貓犬的飼主", {})],
    [("核心問題｜", {"bold": True}), ("白天 8–12 小時無人照看，喝水、進食、如廁的早期變化，常要好幾天後才被察覺", {})],
])
card(s, 5.1, 1.75, 4.4, 1.9, "方案與價值", [
    "居家攝影機 + AI 自動記錄吃、喝、如廁、休息、活動",
    "學習「每隻寵物自己的正常模式」，持續偏離才分級提醒",
    "白話提醒 + 就醫觀察紀錄，引導及早諮詢獸醫",
], fill=PINK)
for i, (big, small) in enumerate([("3 層 AI", "看懂行為 → 和自己比 → 白話提醒"),
                                   ("90%", "模擬驗證抓到行為變化（固定門檻 60%）"),
                                   ("2.1 天", "模擬驗證中，變化開始後平均發現時間")]):
    x = 1.7 + i * 2.65
    text(s, x, 3.82, 2.5, 0.5, [big], size=24, color=RED, bold=True)
    text(s, x, 4.3, 2.5, 0.45, [small], size=10, color=GRAY)

# ---------------------------------------------------------------- 02 問題定義
s = S[2]
frame(s, "02", "問題定義與目標對象", "飼主不在家的 12 小時，是日常照護的空窗")
text(s, 0.5, 1.7, 4.3, 0.3, ["使用情境：一位上班族飼主的一天"], size=14, color=DARK, bold=True)
box(s, 0.6, 2.55, 4.1, 0.1, "D9D9D9")
box(s, 1.25, 2.55, 2.8, 0.1, HEAD)
for x, w, t, d, al in [(0.5, 1.3, "08:00", "出門上班", "l"), (1.85, 1.5, "白天", "12 小時無人觀察", "c"),
                       (3.4, 1.3, "20:00", "回家只看到當下", "r")]:
    text(s, x, 2.05, w, 0.45, [t], size=13, bold=True, color=DARK, align=al)
    text(s, x, 2.75, w, 0.5, [d], size=11, color=GRAY, align=al)
text(s, 0.5, 3.35, 4.3, 1.4, [
    [("為什麼重要｜", {"bold": True}),
     ("貓天性會隱藏不適，喝水、進食、如廁頻率的改變，是獸醫常用的日常觀察項目，但白天正是最容易錯過的時段。", {})],
    [("規模｜", {"bold": True}),
     ("台灣家貓約 174 萬隻、家犬約 146 萬隻，家貓首度超越家犬，養 2 隻以上貓的家庭也在增加。", {})],
], size=11, space_after=5)
caption(s, 0.5, 4.6, 4.3, "資料來源：農業部 114 年全國家犬家貓飼養數量調查（2026 年 4 月發布）", size=8.5)
for i, (t, d) in enumerate([
        ("看不到", "上班時沒人在家，行為變化只能靠運氣發現"),
        ("看不懂", "一般寵物攝影機靠移動或聲音觸發，通知太多，最後被關掉"),
        ("說不清", "就醫時只能憑記憶描述「最近好像喝比較多」")]):
    y = 1.75 + i * 1.0
    box(s, 5.1, y, 4.4, 0.88, LIGHT)
    circle_num(s, 5.25, y + 0.22, 0.44, str(i + 1))
    text(s, 5.85, y + 0.08, 3.5, 0.3, [t], size=14, bold=True)
    text(s, 5.85, y + 0.4, 3.55, 0.45, [d], size=11, color=GRAY)

# ---------------------------------------------------------------- 02 目標對象
s = S[3]
frame(s, "02", "目標對象與需求", "需要的不是更多影片，而是「什麼時候該注意」")
personas = [("上班族單寵飼主", "白天長時間不在家", "想知道牠今天過得好不好，又不想一直看監視畫面"),
            ("多貓／多犬家庭", "家貓 174 萬隻，多貓家庭增加", "需要每隻分開記錄，才知道是哪一隻不一樣"),
            ("高齡貓犬照顧者", "本來就比較少動、喝比較多", "一般標準常誤判，需要依牠自己的狀態來比較")]
for i, (t, sub, need) in enumerate(personas):
    x = 0.5 + i * 3.05
    box(s, x, 1.75, 2.85, 2.0, PINK if i == 1 else LIGHT)
    text(s, x + 0.15, 1.85, 2.6, 0.35, [t], size=14, bold=True, color=DARK)
    text(s, x + 0.15, 2.22, 2.6, 0.35, [sub], size=11, color=GRAY)
    text(s, x + 0.15, 2.65, 2.6, 1.0, [need], size=12)
text(s, 0.5, 3.95, 9.0, 0.3, ["共同需求 → 對應功能"], size=13, bold=True)
text(s, 0.5, 4.27, 9.0, 0.5, [
    "少打擾，只在重要時提醒 → 分級提醒　｜　每隻分開看 → 多寵物追蹤　｜　依自己的平常比較 → 個體化基線　｜　看診說得清楚 → 就醫觀察紀錄"],
    size=11, color=GRAY)

# ---------------------------------------------------------------- 03 解決方案與旅程
s = S[4]
frame(s, "03", "解決方案設計與使用情境", "裝好攝影機，兩週後它就認識你的毛孩")
steps = [("安裝", "對著碗與砂盆的\n居家攝影機"),
         ("學習 14 天", "建立這隻寵物\n自己的正常模式"),
         ("每天摘要", "下班前收到\n一句話報平安"),
         ("分級提醒", "持續不一樣時\n才提醒「留意」或\n「建議諮詢獸醫」"),
         ("就醫紀錄", "一鍵產生\n就醫觀察紀錄")]
for i, (t, d) in enumerate(steps):
    x = 0.5 + i * 1.84
    box(s, x, 1.8, 1.62, 1.75, PINK if i == 3 else LIGHT, MSO_SHAPE.ROUNDED_RECTANGLE)
    circle_num(s, x + 0.58, 1.92, 0.46, str(i + 1))
    text(s, x + 0.05, 2.45, 1.52, 0.35, [t], size=13, bold=True, align="c")
    text(s, x + 0.05, 2.8, 1.52, 0.75, d.split("\n"), size=10.5, color=GRAY, align="c", space_after=0)
    if i < 4:
        text(s, x + 1.6, 2.45, 0.26, 0.35, ["›"], size=20, color=MUTED, bold=True, align="c")
text(s, 0.5, 3.75, 9.0, 0.3, ["提醒長這樣（實際產生的範例，模擬資料）"], size=12, bold=True)
text(s, 0.5, 4.08, 9.0, 0.7, [
    [("🟠 小黑喝水總時間連續 9 天偏多　", {"bold": True, "color": ORANGE}),
     ("喝水總時間 15.6 分鐘，平常約 7.3 分鐘（多 115%）……　👉 建議近期聯絡獸醫，並帶上就醫觀察紀錄", {})]],
    size=11)

# ---------------------------------------------------------------- 03 功能與設計原則
s = S[5]
frame(s, "03", "主要功能與設計原則", "四個功能，一個原則：只觀察、不打擾、不診斷")
feats = [("行為時間軸", "自動記錄吃、喝、如廁、休息、活動的次數與時間"),
         ("個體化提醒", "和自己的平常比，分成正常／留意／建議諮詢獸醫"),
         ("多寵物分開記錄", "每隻寵物各自編號、各自建立基線"),
         ("就醫觀察紀錄", "行為統計表、提醒紀錄與趨勢圖，一頁帶去診所")]
for i, (t, d) in enumerate(feats):
    x = 0.5 + (i % 2) * 2.5
    y = 1.75 + (i // 2) * 1.5
    box(s, x, y, 2.35, 1.35, LIGHT)
    text(s, x + 0.12, y + 0.1, 2.15, 0.35, [t], size=13, bold=True, color=DARK)
    text(s, x + 0.12, y + 0.48, 2.15, 0.85, [d], size=11)
box(s, 5.65, 1.75, 3.85, 2.85, PINK)
text(s, 5.8, 1.85, 3.6, 0.35, ["設計原則"], size=14, bold=True, color=DARK)
text(s, 5.8, 2.25, 3.6, 2.3, [
    [("非接觸、最小干擾｜", {"bold": True}), ("不需穿戴裝置，只分析碗與砂盆等必要區域（注意事項第 36 點）", {})],
    [("隱私｜", {"bold": True}), ("影像可在家中電腦處理，只保留行為統計", {})],
    [("不診斷｜", {"bold": True}), ("只描述觀察到的變化，最高等級是「建議諮詢獸醫」（第 33 點）", {})],
], size=11, bullet=True, space_after=6)

# ---------------------------------------------------------------- 04 AI 應用方法總覽
s = S[6]
frame(s, "04", "AI 應用方法", "三層 AI 串接：看懂行為 → 和自己的平常比 → 說成白話")
table(s, 0.5, 1.72, 9.0, [
    ["", "使用的 AI 技術／模型", "資料輸入", "分析／推論方式", "產出結果"],
    ["① 看懂行為", "YOLO 物件偵測（cat／dog）＋多目標追蹤", "居家攝影機影像",
     "寵物位置 × 碗／砂盆區域 × 移動速度 → 行為；多碗時看哪一碗附近畫面變化最多", "每隻寵物的行為事件與每日統計"],
    ["② 和自己比", "個體化基線（中位數／MAD）＋Isolation Forest", "每日 8 項行為統計",
     "和這隻寵物自己過去 28 天比較，扣除週末作息差異；連續 2–3 天同方向偏移才升級", "提醒等級與原因（偏離 %、持續天數）"],
    ["③ 說成白話", "大型語言模型 Claude（結構化輸出）＋規則護欄", "② 的等級與數字",
     "只依數字措辭；禁用詞檢查不通過就重寫，再不通過改用系統範本", "手機提醒＋就醫觀察紀錄"],
], [1.05, 1.95, 1.2, 3.0, 1.8], size=10, row_h=0.6)
box(s, 0.5, 4.27, 9.0, 0.5, PINK)
text(s, 0.65, 4.3, 8.7, 0.45, [
    [("AI 對作品價值的貢獻｜", {"bold": True, "color": DARK}),
     ("把幾小時的影片變成「今天哪裡不一樣」，並依每隻寵物自己的平常判斷，抓到一般標準會漏掉的變化。", {})]],
    size=11, anchor="m")

# ---------------------------------------------------------------- 04-① 看懂行為
s = S[7]
frame(s, "04", "AI ① 看懂行為", "實測：兩隻貓、四個碗的真實影片，系統分開追蹤每一隻")
picture(s, IMG + "vision_cats.jpg", 0.5, 1.7, h=3.05)
text(s, 4.35, 1.7, 5.15, 0.3, ["怎麼做"], size=14, bold=True, color=DARK)
text(s, 4.35, 2.05, 5.15, 1.5, [
    "YOLO 找出畫面中的貓狗，追蹤器替每隻編號（cat_1、cat_2）",
    "在畫面上框出水碗、食碗、砂盆；寵物停在區域內且沒在走動 → 喝水／進食／如廁",
    "時間平滑：只經過碗旁 1 秒不算喝水（喝水 ≥ 3 秒、進食 ≥ 5 秒）",
], size=11, bullet=True, space_after=4)
text(s, 4.35, 3.55, 5.15, 0.3, ["實測觀察（素材影片）"], size=13, bold=True)
text(s, 4.35, 3.87, 5.15, 0.9, [
    "✔ 分出兩隻貓，進食行為判斷正確",
    "△ 剪接轉場後編號會換；碗在畫面上前後重疊時可能判錯碗 → 規劃加入動物姿態模型（鼻子位置）",
], size=10.5, color=GRAY, space_after=2)

# ---------------------------------------------------------------- 04-② 個體化基線
s = S[8]
frame(s, "04", "AI ② 和自己的平常比", "每隻寵物的平常都不同：用「牠自己的平常」才看得出變化")
picture(s, IMG + "trend_full.png", 0.5, 1.7, h=2.8)
text(s, 4.05, 1.7, 5.45, 0.3, ["方法"], size=14, bold=True, color=DARK)
text(s, 4.05, 2.05, 5.45, 1.75, [
    "前 14 天只學習：每項指標用中位數與 MAD 建立個體基線",
    "週末作息差異（主人在家較活潑）從自己的紀錄估計並扣除",
    "時間類指標取對數、次數類以 √平均 為自然波動下限",
    "Isolation Forest 找出「單項不誇張、組合很少見」的日子",
], size=11, bullet=True, space_after=3)
table(s, 4.05, 3.82, 5.45, [
    ["提醒等級", "條件"],
    ["🟡 留意", "單日明顯不同，或組合不尋常（例如家裡來客人）"],
    ["🟠 建議諮詢獸醫", "同一變化持續 2–3 天、或兩項指標一起偏移"],
], [1.45, 4.0], size=10, row_h=0.3)
text(s, 0.5, 4.52, 3.4, 0.36, ["高齡貓「小黑」趨勢圖（模擬資料）：喝水逐漸增加，第 3 天轉為建議諮詢"], size=9, color=GRAY)

# ---------------------------------------------------------------- 04-③ 白話提醒
s = S[9]
frame(s, "04", "AI ③ 白話提醒與用語護欄", "AI 只負責措辭；等級與數字都來自前一層，並通過規則檢查")
picture(s, IMG + "phone.png", 0.6, 1.7, h=3.1)
steps = [("事實整理", "只把 ② 算好的等級與數字交給模型"),
         ("Claude 撰寫", "標題／內容／下一步，結構化輸出"),
         ("用語檢查", "診斷、病名、器官、用藥、保證、換飼料、品牌 → 擋下重寫"),
         ("附上免責聲明", "第 35 點全文放在每則提醒的同一張卡片上")]
for i, (t, d) in enumerate(steps):
    y = 1.72 + i * 0.68
    circle_num(s, 2.75, y + 0.08, 0.4, str(i + 1))
    text(s, 3.3, y, 2.4, 0.3, [t], size=12.5, bold=True)
    text(s, 3.3, y + 0.3, 2.7, 0.38, [d], size=10, color=GRAY)
box(s, 6.15, 1.72, 3.35, 3.05, PINK)
text(s, 6.3, 1.82, 3.1, 0.3, ["安全設計"], size=14, bold=True, color=DARK)
text(s, 6.3, 2.2, 3.1, 2.5, [
    "等級由 ② 決定，模型不能調高或調低",
    "模型不得自行編造數字",
    "違規重寫一次；仍不通過、被婉拒或斷線 → 改用系統範本，提醒一定送出",
    "最高等級固定引導「近期聯絡獸醫，帶上就醫觀察紀錄」",
], size=10.5, bullet=True, space_after=4)

# ---------------------------------------------------------------- 05 Demo
s = S[10]
frame(s, "05", "Demo／Prototype 展示", "已完成可執行的原型：一個指令跑完 ① → ② → ③")
picture(s, IMG + "demo_top.png", 0.5, 1.7, h=2.8)
picture(s, IMG + "vet.png", 3.2, 1.7, h=2.4)
text(s, 3.2, 4.15, 2.5, 0.6, ["就醫觀察紀錄（可列印）"], size=10, color=GRAY)
text(s, 5.85, 1.7, 3.65, 0.3, ["目前完成程度"], size=14, bold=True, color=DARK)
table(s, 5.85, 2.05, 3.65, [
    ["模組", "狀態"],
    ["① 看懂行為", "✔ 真實影片實測（YOLO）"],
    ["② 和自己比", "✔ 模擬 60 天資料驗證"],
    ["③ 白話提醒", "✔ 範本模式；Claude 待實測"],
    ["一鍵 Demo 總覽頁", "✔ 可直接錄影"],
], [1.55, 2.1], size=10, row_h=0.32)
text(s, 5.85, 3.78, 3.65, 1.0, [
    "AI 輸入：攝影機影像 → 輸出：行為事件",
    "AI 輸入：每日統計 → 輸出：等級與原因",
    "AI 輸入：等級與數字 → 輸出：白話提醒",
], size=10, color=GRAY, bullet=True, space_after=1)
caption(s, 0.5, 4.53, 2.6, "Demo 總覽頁：依 ① → ② → ③ 排列", size=9)

# ---------------------------------------------------------------- 05 驗證結果
s = S[11]
frame(s, "05", "驗證結果（模擬資料）", "個體化基線抓到更多變化，也更早提醒")
stats = [("90%", "60%", "抓到真實行為變化", "27／30 vs 18／30"),
         ("2.1 天", "2.4 天", "變化開始後幾天提醒", "「建議諮詢獸醫」"),
         ("2.0%", "1.0%", "普通日誤發「建議諮詢」", "約每 50 天 1 次")]
for i, (ours, base, label, sub) in enumerate(stats):
    x = 0.5 + i * 3.05
    box(s, x, 1.75, 2.85, 1.7, LIGHT)
    text(s, x + 0.15, 1.82, 2.6, 0.3, [label], size=12, bold=True)
    text(s, x + 0.15, 2.15, 2.6, 0.6, [[(ours, {"size": 28, "bold": True, "color": RED}),
                                       ("　本方案", {"size": 10, "color": GRAY})]])
    text(s, x + 0.15, 2.78, 2.6, 0.3, [f"一般族群固定範圍：{base}"], size=11, color=GRAY)
    text(s, x + 0.15, 3.08, 2.6, 0.3, [sub], size=10, color=GRAY)
text(s, 0.5, 3.6, 9.0, 0.3, ["怎麼驗證"], size=13, bold=True, color=DARK)
text(s, 0.5, 3.9, 9.0, 0.9, [
    "10 組模擬 × 3 隻寵物 × 60 天，每組放入 3 段已知行為變化（食慾下降、喝水與如廁逐漸增加、如廁突增）與 1 段無害單日事件；"
    "對照組以 200 隻模擬健康貓狗訂出的物種正常範圍，套用完全相同的升級規則。",
    [("限制｜", {"bold": True}), ("資料與變化皆為我們自行設計的模擬，數字僅代表方法方向，不代表真實準確率；誤報稍多是換取更高發現率的代價。", {})],
], size=10.5, color=DARK, space_after=3)

# ---------------------------------------------------------------- 06 獨特性
s = S[12]
frame(s, "06", "獨特性與預期效益", "差別不在多一台攝影機，而在「依牠自己的平常」判斷")
table(s, 0.5, 1.72, 9.0, [
    ["", "現有做法", "本方案的差異", "預期改善"],
    ["察覺方式", "一般寵物攝影機：移動或聲音觸發，需要人看影片", "AI 自動把影像轉成行為紀錄", "飼主每天只要看一句話"],
    ["判斷標準", "固定門檻：「超過 X 就通知」", "個體化基線，持續偏離才升級", "更少漏掉變化（模擬：發現率 60% → 90%）"],
    ["多寵物", "混在一起，分不清是誰", "每隻分開追蹤、分開建立基線", "知道是哪一隻不一樣"],
    ["就醫溝通", "憑記憶描述", "自動產生就醫觀察紀錄", "看診時溝通更有效率"],
    ["用語安全", "—", "AI 措辭＋禁用詞護欄＋免責聲明", "引導及早諮詢，不取代獸醫"],
], [1.1, 2.6, 2.6, 2.7], size=10.5, row_h=0.5)

# ---------------------------------------------------------------- 06 可行性
s = S[13]
frame(s, "06", "可行性、限制與因應方式", "用現成攝影機與開源模型即可實作，已有可執行原型")
card(s, 0.5, 1.75, 4.4, 3.0, "技術與執行可行性", [
    "硬體：一般居家攝影機或舊手機即可",
    "模型：YOLO（cat／dog）、Isolation Forest、Claude API",
    "運算：家用電腦即可處理；無 API 金鑰時自動改用系統範本",
    "驗證：37 項自動測試；真實影片實測；模擬 60 天評估",
], size=11)
rows = [["可能限制", "因應方式"],
        ["碗在畫面上前後重疊時判錯碗", "加入動物姿態模型，以鼻子位置判斷"],
        ["寵物編號只在同一段影片有效", "加入毛色、花紋的個體辨識"],
        ["目前以模擬資料驗證", "招募飼主試用，以真實長期紀錄重新驗證"],
        ["「留意」約佔 1 成天數", "只推播「建議諮詢」，「留意」放在 App 內"],
        ["禁用詞清單可能有漏網之魚", "上線前請獸醫師審閱措辭"]]
table(s, 5.1, 1.75, 4.4, rows, [2.1, 2.3], size=10, row_h=0.5)

# ---------------------------------------------------------------- 07 後續發展
s = S[14]
frame(s, "07", "後續發展潛力", "從單一家庭，延伸到獸醫院與長期照護")
road = [("短期", "飼主試用", ["真實居家影片驗證與調整", "加入姿態模型判斷鼻子位置", "跨天個體辨識"]),
        ("中期", "結合感測", ["智慧水碗／荷重感測，精確飲水量", "手機 App 與每日推播", "多寵物家庭完整支援"]),
        ("長期", "照護網絡", ["飼主授權後分享紀錄給獸醫院", "高齡與慢性照護的長期追蹤", "與營養照護建議連結（經獸醫確認）"])]
for i, (when, t, items) in enumerate(road):
    x = 0.5 + i * 3.05
    box(s, x, 1.75, 2.85, 2.55, PINK if i == 2 else LIGHT)
    text(s, x + 0.15, 1.85, 2.6, 0.3, [when], size=11, color=GRAY, bold=True)
    text(s, x + 0.15, 2.12, 2.6, 0.35, [t], size=15, bold=True, color=DARK)
    text(s, x + 0.15, 2.55, 2.6, 1.7, items, size=11, bullet=True, space_after=4)
text(s, 0.5, 4.42, 9.0, 0.35, [
    [("合作對象｜", {"bold": True}), ("動物醫院、寵物攝影機與智慧碗廠商、寵物保險、高齡寵物照護社群", {})]], size=11)

# ---------------------------------------------------------------- 08 團隊與補充資料（附錄）
s = S[15]
frame(s, "08", "團隊與補充資料", "附錄（不計入頁數）：團隊、外部資源與授權揭露")
card(s, 0.5, 1.75, 3.2, 3.0, "團隊與作品基礎", [
    "【成員姓名】：分工",
    "【成員姓名】：分工",
    "既有作品基礎：無，本次全新開發",
    "原始碼：github.com/ammieliu-jpg/AI_animal",
], size=10.5)
table(s, 3.9, 1.75, 5.6, [
    ["外部資源", "用途", "授權"],
    ["Ultralytics YOLO11n", "貓狗偵測", "AGPL-3.0"],
    ["OpenCV、scikit-learn、matplotlib", "影像處理、異常偵測、圖表", "Apache-2.0／BSD／PSF"],
    ["Anthropic Claude API", "白話提醒措辭", "依服務條款，按用量計費"],
    ["Pexels 素材影片", "Demo 測試影片", "Pexels License"],
    ["模擬資料（自行產生）", "異常偵測驗證", "團隊自有"],
], [2.05, 1.85, 1.7], size=9.5, row_h=0.36)
text(s, 3.9, 4.0, 5.6, 0.8, [
    "飲水參考範圍：獸醫文獻約 40–60 ml/kg/天，僅用於設定模擬參數，不做任何病名推論。",
    "素材影片僅供測試，正式 Demo 將使用取得飼主同意的居家影片（注意事項第 31 點）。",
], size=9, color=GRAY, space_after=2)

prs.save(W + "/PetSentinel_proposal.pptx")
print("saved")
