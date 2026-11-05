"""Build the ~3-minute Demo draft: HTML scenes -> PNG -> ffmpeg clips -> burned-in subtitles."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

V = Path(sys.argv[1])
A = V / "assets"
OUT = V / "out"
OUT.mkdir(exist_ok=True)
W, H, FPS = 1920, 1080, 30

# crop the drinking panel from the high-res chart
t = Image.open(A / "trend.png")
t.crop((0, 0, t.width, int(t.height * 0.30))).save(A / "trend_drink.png")

CSS = """
* { box-sizing:border-box; margin:0; }
body { width:1920px; height:1080px; overflow:hidden; background:#ffffff; color:#2d2d2d;
       font-family:"Noto Sans TC","WenQuanYi Zen Hei",sans-serif; }
.wrap { position:absolute; inset:0; padding:90px 120px 200px; }
.kicker { font-size:30px; color:#8a9096; letter-spacing:2px; }
h1 { font-size:84px; font-weight:800; line-height:1.15; margin-top:14px; }
h2 { font-size:58px; font-weight:800; line-height:1.2; }
.red { color:#e2001a; }
p { font-size:34px; line-height:1.55; color:#5b5c5f; }
.tag { display:inline-block; font-size:26px; padding:8px 18px; border-radius:999px; background:#f2f3f5; color:#5b5c5f; }
.card { background:#f6f7f8; border-radius:24px; padding:34px 38px; }
.num { width:70px; height:70px; border-radius:50%; background:#3a3f45; color:#fff; font-size:36px; font-weight:800;
       display:flex; align-items:center; justify-content:center; flex:none; }
.row { display:flex; gap:36px; align-items:center; }
.sim { position:absolute; right:120px; top:60px; font-size:26px; color:#8a6d1f; background:#fff4d6; padding:8px 18px; border-radius:10px; }
"""


def page(body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"


def img(name: str) -> str:
    return (A / name).as_uri()


# Each scene: id, html, duration (s), subtitles [(text, seconds)], motion
SCENES = [
    dict(id="01_title", dur=8, motion="zoom", html=page("""
<div class="wrap" style="display:flex;flex-direction:column;justify-content:center">
  <div class="kicker">2026 法國皇家 AI for Pets 創新徵件計畫｜預防保健</div>
  <h1>毛孩日常哨兵 <span class="red">PetSentinel</span></h1>
  <p style="font-size:44px;margin-top:24px">上班時也能察覺貓犬「跟平常不一樣」的 AI 照護提醒</p>
</div>"""), subs=[("毛孩日常哨兵：上班時也能察覺毛孩「跟平常不一樣」", 8)]),

    dict(id="02_problem", dur=22, motion="zoom", html=page("""
<div class="wrap">
  <div class="kicker">問題</div>
  <h2 style="margin-top:10px">每天 <span class="red">12 小時</span>，沒有人看著牠</h2>
  <div class="row" style="margin-top:70px;gap:40px">
    <div class="card" style="flex:1"><div class="row" style="gap:22px"><div class="num">1</div><h2 style="font-size:46px">看不到</h2></div>
      <p style="margin-top:22px">上班時沒人在家，變化只能靠運氣發現</p></div>
    <div class="card" style="flex:1"><div class="row" style="gap:22px"><div class="num">2</div><h2 style="font-size:46px">看不懂</h2></div>
      <p style="margin-top:22px">一般攝影機有動靜就通知，通知太多最後被關掉</p></div>
    <div class="card" style="flex:1"><div class="row" style="gap:22px"><div class="num">3</div><h2 style="font-size:46px">說不清</h2></div>
      <p style="margin-top:22px">看診時只能說「好像喝比較多」</p></div>
  </div>
</div>"""), subs=[("早上八點出門，晚上八點回家", 4.5),
                  ("中間這 12 小時，毛孩過得好不好，我們其實不知道", 5.5),
                  ("貓天性會隱藏不適，喝水、吃飯、上廁所的變化很容易錯過", 6),
                  ("一般寵物攝影機有動靜就通知，通知太多，最後乾脆關掉", 6)]),

    dict(id="03_overview", dur=14, motion="zoom", html=page("""
<div class="wrap">
  <div class="kicker">解決方案</div>
  <h2 style="margin-top:10px">只在「跟平常不一樣」時提醒</h2>
  <div class="row" style="margin-top:90px;gap:28px;font-size:40px;font-weight:700">
    <div class="card" style="flex:1;text-align:center">📹<br>居家攝影機</div><div style="color:#8a9096">›</div>
    <div class="card" style="flex:1;text-align:center">① 看懂行為</div><div style="color:#8a9096">›</div>
    <div class="card" style="flex:1;text-align:center">② 和自己的<br>平常比</div><div style="color:#8a9096">›</div>
    <div class="card" style="flex:1;text-align:center">③ 說成白話</div>
  </div>
</div>"""), subs=[("毛孩日常哨兵用三層 AI，只在「跟平常不一樣」時才提醒", 7),
                  ("看懂行為、和牠自己的平常比，再說成飼主看得懂的話", 7)]),

    dict(id="04_vision", dur=30, motion="pan", html=page(f"""
<div class="wrap" style="padding-right:80px">
  <div class="kicker">① 看懂行為</div>
  <div class="row" style="margin-top:24px;align-items:flex-start;gap:56px">
    <img src="{img('vision.jpg')}" style="height:700px;border-radius:16px;border:1px solid #ddd">
    <div style="padding-top:20px">
      <h2 style="font-size:50px">影像 → 每隻寵物的<br>行為紀錄</h2>
      <p style="margin-top:30px">YOLO 找出每一隻貓並編號</p>
      <p>停在碗前、沒有走動 → 進食／喝水</p>
      <p>只經過碗旁 1 秒，不算喝水</p>
      <div class="tag" style="margin-top:30px">實測：兩隻貓、四個碗的素材影片</div>
    </div>
  </div>
</div>"""), subs=[("第一層：AI 看懂行為", 4),
                  ("YOLO 找出畫面中的每一隻貓，並替牠們編號", 6),
                  ("停在碗前、沒有走動，就記錄為進食或喝水；只是經過不算", 7),
                  ("這是兩隻貓、四個碗的實測畫面，每一隻分開記錄", 6.5),
                  ("影像就變成每天的行為紀錄：吃幾次、喝幾次、上廁所幾次", 6.5)]),

    dict(id="05_baseline", dur=18, motion="zoom", html=page(f"""
<div class="wrap" style="padding-top:70px">
  <div class="sim">⚠ 模擬資料</div>
  <div class="kicker">② 和牠自己的平常比</div>
  <div class="row" style="margin-top:20px;align-items:flex-start;gap:50px">
    <img src="{img('trend.png')}" style="height:760px;border-radius:12px;border:1px solid #ddd">
    <div style="padding-top:20px">
      <h2 style="font-size:50px">高齡貓「小黑」</h2>
      <p style="margin-top:24px">前 14 天先學習牠自己的作息</p>
      <p>藍色區域＝牠的平常範圍</p>
      <p>每隻寵物的平常都不一樣</p>
    </div>
  </div>
</div>"""), subs=[("第二層：和牠自己的平常比", 4),
                  ("前 14 天，系統先學習每一隻寵物自己的作息", 7),
                  ("高齡貓小黑本來就喝比較多水，要用牠自己的平常，才看得出變化", 7)]),

    dict(id="06_baseline_zoom", dur=17, motion="zoom", html=page(f"""
<div class="wrap" style="padding-top:70px">
  <div class="sim">⚠ 模擬資料</div>
  <div class="kicker">② 喝水次數的變化</div>
  <img src="{img('trend_drink.png')}" style="width:1680px;margin-top:30px;border-radius:12px;border:1px solid #ddd">
  <div class="row" style="margin-top:34px;gap:30px">
    <div class="tag" style="background:#fdf0e4;color:#a8551c;font-size:30px">橘色＝建議諮詢獸醫</div>
    <div class="tag" style="font-size:30px">斜線＝模擬中放入的變化（標準答案）</div>
  </div>
</div>"""), subs=[("從 10 月 9 日開始，小黑喝水和上廁所的次數逐漸增加", 6),
                  ("連續幾天都往同一個方向偏移，第 3 天系統轉為「建議諮詢獸醫」", 6.5),
                  ("只有一天特別不一樣，最多只會提醒「留意」", 4.5)]),

    dict(id="07_results", dur=16, motion="zoom", html=page("""
<div class="wrap">
  <div class="sim">⚠ 模擬驗證</div>
  <div class="kicker">驗證結果</div>
  <div class="row" style="margin-top:60px;gap:40px">
    <div class="card" style="flex:1"><p style="color:#2d2d2d;font-weight:700">抓到真實行為變化</p>
      <div style="font-size:120px;font-weight:800" class="red">90%</div><p>一般族群標準：60%</p></div>
    <div class="card" style="flex:1"><p style="color:#2d2d2d;font-weight:700">變化開始後幾天提醒</p>
      <div style="font-size:120px;font-weight:800" class="red">2.1 天</div><p>一般族群標準：2.4 天</p></div>
    <div class="card" style="flex:1"><p style="color:#2d2d2d;font-weight:700">普通日誤發「建議諮詢」</p>
      <div style="font-size:120px;font-weight:800;color:#5b5c5f">2.0%</div><p>一般族群標準：1.0%</p></div>
  </div>
</div>"""), subs=[("在模擬驗證中，個體化基線抓到 90% 的行為變化，一般標準只有 60%", 7),
                  ("代價是誤報稍多，大約每 50 天一次", 4.5),
                  ("這些是模擬數據，之後將用真實居家紀錄重新驗證", 4.5)]),

    dict(id="08_phone", dur=22, motion="scroll", overlay="phone.png", ov_x=180, ov_y=70, ov_w=560, ov_h=880,
         html=page("""
<div class="wrap" style="padding-left:860px">
  <div class="kicker">③ 說成白話</div>
  <h2 style="margin-top:16px;font-size:54px">下班前，手機收到<br>一句話的摘要</h2>
  <p style="margin-top:36px">等級由 ② 決定，AI 只負責措辭</p>
  <p>不診斷、不提病名、不建議用藥</p>
  <p>每則都附上規定的免責聲明</p>
</div>"""), subs=[("第三層：把數字說成白話", 4),
                  ("飼主下班前，手機收到每一隻毛孩的一句話摘要", 6),
                  ("AI 只描述觀察到的變化，不診斷、不提病名", 6),
                  ("每則提醒都附上免責聲明，引導飼主及早諮詢獸醫", 6)]),

    dict(id="09_vet", dur=18, motion="scroll", overlay="vet.png", ov_x=120, ov_y=60, ov_w=960, ov_h=900,
         html=page("""
<div class="wrap" style="padding-left:1180px">
  <div class="kicker">就醫觀察紀錄</div>
  <h2 style="margin-top:16px;font-size:54px">一頁帶去<br>給獸醫看</h2>
  <p style="margin-top:36px">平常值 vs 最近 3 天</p>
  <p>提醒紀錄與趨勢圖</p>
  <p>可直接列印</p>
</div>"""), subs=[("一鍵產生就醫觀察紀錄", 4),
                  ("平常值、最近三天的變化、趨勢圖，一頁帶去給獸醫看", 7),
                  ("看診時，不再只能說「好像喝比較多」", 7)]),

    dict(id="10_closing", dur=15, motion="zoom", html=page("""
<div class="wrap" style="display:flex;flex-direction:column;justify-content:center">
  <div class="row" style="gap:20px"><span class="tag">非接觸</span><span class="tag">不打擾</span><span class="tag">不取代獸醫</span></div>
  <h1 style="margin-top:30px;font-size:76px">讓每一位上班族飼主<br>都能<span class="red">及早察覺</span></h1>
  <p style="margin-top:30px;font-size:38px">毛孩日常哨兵 PetSentinel｜【團隊名稱】</p>
</div>"""), subs=[("非接觸、不打擾，也不取代獸醫", 6),
                  ("毛孩日常哨兵，讓每一位上班族飼主都能及早察覺", 9)]),
]


def render_html():
    html_dir = V / "html"
    html_dir.mkdir(exist_ok=True)
    for sc in SCENES:
        (html_dir / f"{sc['id']}.html").write_text(sc["html"], encoding="utf-8")
    js = V / "render.js"
    js.write_text("""
const { chromium } = require('playwright');
const ids = %s;
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  for (const id of ids) {
    await p.goto('file://%s/html/' + id + '.html'); await p.waitForTimeout(300);
    await p.screenshot({ path: '%s/out/' + id + '.png' });
  }
  await b.close();
})();""" % (json.dumps([s["id"] for s in SCENES]), V, V), encoding="utf-8")
    subprocess.run(["node", str(js)], check=True)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def make_clip(sc) -> Path:
    src, dst, d = OUT / f"{sc['id']}.png", OUT / f"{sc['id']}.mp4", sc["dur"]
    n = int(d * FPS)
    fade = f"fade=t=in:st=0:d=0.5:color=white,fade=t=out:st={d - 0.5}:d=0.5:color=white"
    if sc["motion"] == "scroll":
        ov = Image.open(A / sc["overlay"])
        scale = sc["ov_w"] / ov.width
        oh = int(ov.height * scale)
        travel = max(0, oh - sc["ov_h"])
        speed = travel / max(1, d - 4)  # hold 2 s at top and bottom
        f = (f"[1:v]scale={sc['ov_w']}:{oh},crop={sc['ov_w']}:{sc['ov_h']}:0:'min(max(0,(t-2)*{speed:.3f}),{travel})'[p];"
             f"[0:v][p]overlay={sc['ov_x']}:{sc['ov_y']},{fade},format=yuv420p")
        run(["ffmpeg", "-y", "-loop", "1", "-t", str(d), "-i", str(src), "-loop", "1", "-t", str(d), "-i", str(A / sc["overlay"]),
             "-filter_complex", f, "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "22", str(dst)])
    else:
        z = "zoom+0.00025" if sc["motion"] == "zoom" else "zoom+0.0004"
        f = (f"scale={W*2}:{H*2},zoompan=z='min({z},1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},"
             f"{fade},format=yuv420p")
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-vf", f, "-frames:v", str(n), "-c:v", "libx264",
             "-preset", "medium", "-crf", "22", str(dst)])
    return dst


def ts(sec: float, sep=".") -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if sep == ",":
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def subtitles():
    t, srt, ass = 0.0, [], []
    for sc in SCENES:
        total = sum(d for _, d in sc["subs"])
        assert abs(total - sc["dur"]) < 0.01, (sc["id"], total, sc["dur"])
        st = t
        for text, d in sc["subs"]:
            a, b = st + 0.15, st + d - 0.15
            srt.append(f"{len(srt) + 1}\n{ts(a, ',')} --> {ts(b, ',')}\n{text}\n")
            ass.append(f"Dialogue: 0,{ts(a)},{ts(b)},Sub,,0,0,0,,{text}")
            st += d
        t += sc["dur"]
    (V / "subtitles.srt").write_text("\n".join(srt), encoding="utf-8")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,WenQuanYi Zen Hei,52,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99262626,0,0,0,0,100,100,1,0,3,18,0,2,120,120,48,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    (V / "subtitles.ass").write_text(header + "\n".join(ass) + "\n", encoding="utf-8")
    return t


render_html()
clips = [make_clip(sc) for sc in SCENES]
total = subtitles()
lst = V / "clips.txt"
lst.write_text("".join(f"file '{c}'\n" for c in clips))
run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(V / "nosub.mp4")])
run(["ffmpeg", "-y", "-i", str(V / "nosub.mp4"), "-vf", f"ass={V / 'subtitles.ass'}", "-c:v", "libx264",
     "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(V / "PetSentinel_demo_draft.mp4")])
print(f"done: {total:.0f}s")
