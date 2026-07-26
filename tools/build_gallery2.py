#!/usr/bin/env python3
"""Build the multi-city gallery: thumbs for new files, per-city indexes, gallery.html."""
import json, os, re, subprocess

SCRATCH = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRATCH)

CITY_ZH = {"hangzhou":"杭州","beijing":"北京","chengdu":"成都","chongqing":"重庆",
  "tianjin":"天津","shanghai":"上海","kaifeng":"开封","nanjing":"南京",
  "guangzhou":"广州","fuzhou":"福州","macau":"澳门","suzhou":"苏州","wuhan":"武汉",
  "xian":"西安","qingdao":"青岛","harbin":"哈尔滨","shenyang":"沈阳","taizhou":"台州","hongkong":"香港","dalian":"大连","xiamen":"厦门","ningbo":"宁波","kunming":"昆明","jinan":"济南"}

items = []

def era(datestr):
    m = re.search(r'\b(18[5-9]\d|19[0-4]\d)\b', datestr or "")
    if not m: return "其他"
    y = int(m.group(1))
    if y < 1900: return "1850–99"
    if y < 1910: return "1900–09"
    if y < 1920: return "1910–19"
    if y < 1930: return "1920–29"
    return "1930–49"

# 1. hangzhou wiki (from its index.md)
for line in open(f"{BASE}/hangzhou/wiki/index.md"):
    m = re.match(r'- \*\*(.+?)\*\* — 年代：(.*?)；授权：(.*?)；\[来源页面\]\((.*?)\)', line)
    if not m: continue
    f, date, lic, src = m.groups()
    name = re.sub(r'^\d+_', '', os.path.splitext(f)[0]).replace('_', ' ')
    items.append({"city":"hangzhou","f":f,"dir":"hangzhou/wiki/","t":name,"y":date,
                  "e":era(date),"src":src,"lic":lic,"s":"维基"})

# 2. hangzhou gamble
p = json.load(open(f"{SCRATCH}/gamble_progress.json"))
for iid in sorted(p):
    v = p[iid]
    if v.get("status") != "ok": continue
    t = re.sub(r'^Title on sleeve:\s*', '', v["title"])
    items.append({"city":"hangzhou","f":v["file"],"dir":"hangzhou/gamble/","t":t,
                  "y":v["date"] or "?","e":era(v["date"]),"lic":"No known copyright",
                  "src":f"https://repository.duke.edu/dc/gamble/{iid}","s":"甘博"})

# 3. other cities gamble
cp_file = f"{SCRATCH}/cities_progress.json"
if os.path.exists(cp_file):
    cp = json.load(open(cp_file))
    for key in sorted(cp):
        v = cp[key]
        if v.get("status") != "ok": continue
        city, iid = key.split("/", 1)
        t = re.sub(r'^Title on sleeve:\s*', '', v["title"])
        items.append({"city":city,"f":v["file"],"dir":f"{city}/gamble/","t":t,
                      "y":v["date"] or "?","e":era(v["date"]),"lic":"No known copyright",
                      "src":f"https://repository.duke.edu/dc/gamble/{iid}","s":"甘博"})

# 4. other cities wiki (commons)
cc_file = f"{SCRATCH}/commons_cities.json"
if os.path.exists(cc_file):
    cc = json.load(open(cc_file))
    for city, lst in cc.items():
        for it in lst:
            name = re.sub(r'^File:', '', it["title"])
            name = os.path.splitext(name)[0]
            page = "https://commons.wikimedia.org/wiki/" + re.sub(r' ', '_', it["title"])
            items.append({"city":city,"f":it["file"],"dir":f"{city}/wiki/","t":name[:110],
                          "y":it["date"],"e":era(it["date"]),"lic":it["lic"],"src":page,"s":"维基"})

print("total items:", len(items))

# 5. thumbnails for any file lacking one
made = 0
for it in items:
    src_path = os.path.join(BASE, it["dir"], it["f"])
    th_rel = f"thumbs/{it['dir']}{it['f']}"
    th_path = os.path.join(BASE, th_rel)
    it["th"] = th_rel
    if not os.path.exists(th_path) and os.path.exists(src_path):
        os.makedirs(os.path.dirname(th_path), exist_ok=True)
        subprocess.run(["sips","-Z","400","--out",th_path,src_path],
                       capture_output=True)
        made += 1
items = [it for it in items if os.path.exists(os.path.join(BASE, it["dir"], it["f"]))]
print("thumbs made:", made, "| items with files:", len(items))

# 6. per-city gamble index.md
cp = json.load(open(cp_file)) if os.path.exists(cp_file) else {}
by_city = {}
for key, v in cp.items():
    if v.get("status") != "ok": continue
    city, iid = key.split("/", 1)
    by_city.setdefault(city, []).append((iid, v))
for city, lst in by_city.items():
    lines = [f"# 甘博（Sidney D. Gamble）{CITY_ZH.get(city, city)}照片集\n",
             "来源：杜克大学图书馆 Sidney D. Gamble Photographs 数字馆藏，原始分辨率。馆方声明无已知版权限制。\n"]
    for iid, v in sorted(lst):
        lines.append(f"- **{v['file']}** — {v['date'] or '?'} — [{v['title'][:90]}](https://repository.duke.edu/dc/gamble/{iid})")
    open(os.path.join(BASE, city, "gamble", "index.md"), "w").write("\n".join(lines)+"\n")

# 7. per-city wiki index.md
cc = json.load(open(cc_file)) if os.path.exists(cc_file) else {}
for city, lst in cc.items():
    lines = [f"# {CITY_ZH.get(city, city)}老照片（维基共享）\n",
             "来源：Wikimedia Commons，按 1850–1949 拍摄年代与公版/CC0/CC BY 授权自动筛选。\n"]
    for it in lst:
        page = "https://commons.wikimedia.org/wiki/" + re.sub(r' ', '_', it["title"])
        lines.append(f"- **{it['file']}** — 年代：{it['date']}；授权：{it['lic']}；[来源页面]({page})")
    open(os.path.join(BASE, city, "wiki", "index.md"), "w").write("\n".join(lines)+"\n")

# 8. gallery.html — sidebar layout
counts = {}
for it in items:
    counts[it["city"]] = counts.get(it["city"], 0) + 1
present = sorted(counts, key=lambda c: -counts[c])
city_rows = '<div class="city on" data-c="全部"><span>全部</span><span class="n">%d</span></div>' % len(items)
city_rows += "".join(
    f'<div class="city" data-c="{c}"><span>{CITY_ZH[c]}</span><span class="n">{counts[c]}</span></div>'
    for c in present)

data_js = json.dumps(items, ensure_ascii=False)
zh_js = json.dumps(CITY_ZH, ensure_ascii=False)

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中国城市老照片 · 1850–1949</title>
<meta name="description" content="__DESC__">
<meta property="og:type" content="website">
<meta property="og:site_name" content="中国城市老照片">
<meta property="og:title" content="中国城市老照片 · 1850–1949">
<meta property="og:description" content="__DESC__">
<meta property="og:image" content="https://bensonjinbin.github.io/china-old-photos/assets/share.jpg">
<meta property="og:url" content="https://bensonjinbin.github.io/china-old-photos/">
<meta itemprop="name" content="中国城市老照片 · 1850–1949">
<meta itemprop="description" content="__DESC__">
<meta itemprop="image" content="https://bensonjinbin.github.io/china-old-photos/assets/share.jpg">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="中国城市老照片 · 1850–1949">
<meta name="twitter:description" content="__DESC__">
<meta name="twitter:image" content="https://bensonjinbin.github.io/china-old-photos/assets/share.jpg">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%239a5b2f'/%3E%3Ctext x='50' y='58' font-size='64' text-anchor='middle' dominant-baseline='middle' fill='%23f5f2ec' font-family='PingFang SC,Hiragino Sans GB,serif'%3E城%3C/text%3E%3C/svg%3E">
<style>
:root {
  --bg: #f5f2ec; --card: #fff; --ink: #2b2620; --sub: #8a8074;
  --line: #e3ddd2; --accent: #9a5b2f; --hd: 96px;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #17150f; --card: #221f18; --ink: #ece5d8; --sub: #9a9184; --line: #353026; --accent: #d09758; }
}
* { margin: 0; padding: 0; box-sizing: border-box; }
img { -webkit-touch-callout: none; -webkit-user-drag: none; user-select: none; }
body { background: var(--bg); color: var(--ink); font: 15px/1.6 -apple-system, "PingFang SC", "Hiragino Sans GB", sans-serif; }
header { position: sticky; top: 0; z-index: 10; background: var(--bg); border-bottom: 1px solid var(--line); padding: 12px 24px 10px; }
h1 { font-size: 20px; font-weight: 700; letter-spacing: .04em; }
h1 small { font-weight: 400; color: var(--sub); font-size: 13px; margin-left: 10px; }
.bar { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin-top: 8px; }
.bar .lab { font-size: 12px; color: var(--sub); margin-right: 2px; }
input[type=search] { flex: 1 1 180px; max-width: 300px; padding: 5px 12px; border: 1px solid var(--line); border-radius: 20px; background: var(--card); color: var(--ink); font-size: 14px; outline: none; }
input[type=search]:focus { border-color: var(--accent); }
.chip { padding: 4px 12px; border: 1px solid var(--line); border-radius: 20px; background: var(--card); color: var(--sub); font-size: 13px; cursor: pointer; user-select: none; white-space: nowrap; }
.chip.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.count { color: var(--sub); font-size: 13px; margin-left: auto; }
.layout { display: flex; align-items: flex-start; }
aside { width: 170px; flex-shrink: 0; position: sticky; top: var(--hd); max-height: calc(100vh - var(--hd)); overflow-y: auto; padding: 0 8px 40px 16px; }
#cq { position: sticky; top: 0; z-index: 2; width: 100%; margin: 0 0 8px; padding: 14px 12px 6px; border: none; border-bottom: 1px solid var(--line); background: var(--bg); color: var(--ink); font-size: 13px; outline: none; }
#cq::placeholder { color: var(--sub); }
.city { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 5px 12px; border-radius: 8px; cursor: pointer; color: var(--ink); font-size: 14px; user-select: none; }
.city:hover { background: var(--card); }
.city .n { color: var(--sub); font-size: 12px; }
.city.on { background: var(--accent); color: #fff; }
.city.on .n { color: rgba(255,255,255,.85); }
main { flex: 1; min-width: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 14px; padding: 20px 24px 60px 12px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; cursor: zoom-in; transition: transform .12s ease; }
.card:hover { transform: translateY(-2px); }
.card img { width: 100%; aspect-ratio: 4/3; object-fit: cover; display: block; background: #d8d2c6; }
.cap { padding: 8px 10px 10px; }
.cap .t { font-size: 13px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.8em; }
.cap .y { font-size: 12px; color: var(--sub); margin-top: 3px; }
@media (max-width: 800px) {
  header { position: relative; padding: 10px 16px 8px; }
  h1 small { display: none; }
  #ab-top { top: 12px; right: 16px; }
  .layout { display: block; }
  aside { position: static; width: auto; max-height: none; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 12px 16px 0; }
  #cq { position: static; flex: 1 1 100%; border: 1px solid var(--line); border-radius: 16px; padding: 5px 12px; background: var(--card); margin: 0 0 2px; }
  .city { border: 1px solid var(--line); border-radius: 16px; padding: 4px 12px; background: var(--card); }
  .grid { padding: 16px; }
}
#top { position: fixed; right: 16px; bottom: 28px; width: 42px; height: 42px; border-radius: 50%; background: var(--accent); color: #fff; display: none; align-items: center; justify-content: center; font-size: 20px; cursor: pointer; z-index: 20; box-shadow: 0 2px 8px rgba(0,0,0,.3); }
#top.show { display: flex; }
#lb { position: fixed; inset: 0; background: rgba(10,8,5,.92); display: none; z-index: 100; flex-direction: column; }
#lb.open { display: flex; }
#lb .stage { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; padding: 16px; }
#lb img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 4px; }
#lb .info { color: #d8d0c2; text-align: center; padding: 0 60px 18px; font-size: 14px; }
#lb .info a { color: #e8b478; }
#lb .nav { position: fixed; top: 50%; transform: translateY(-50%); font-size: 34px; color: #cbc2b2; cursor: pointer; padding: 20px 16px; user-select: none; }
#lb .nav:hover { color: #fff; }
#prev { left: 4px; } #next { right: 4px; }
#close { position: fixed; top: 10px; right: 18px; font-size: 30px; color: #cbc2b2; cursor: pointer; }
#close:hover { color: #fff; }
.ab-link { color: var(--sub); font-size: 13px; cursor: pointer; white-space: nowrap; border-bottom: 1px dashed var(--sub); user-select: none; }
.ab-link:hover { color: var(--accent); border-color: var(--accent); }
#ab-top { position: absolute; top: 16px; right: 24px; }
footer { text-align: center; padding: 20px 16px 44px; color: var(--sub); font-size: 13px; }
#pv { display: none; }
#ab { position: fixed; inset: 0; background: rgba(10,8,5,.65); display: none; z-index: 120; align-items: center; justify-content: center; padding: 18px; }
#ab.open { display: flex; }
.abc { background: var(--bg); border: 1px solid var(--line); border-radius: 14px; max-width: 480px; width: 100%; max-height: 88vh; overflow-y: auto; padding: 24px 26px 28px; position: relative; box-shadow: 0 12px 40px rgba(0,0,0,.35); }
.abc h2 { font-size: 18px; margin-bottom: 8px; }
.abx { position: absolute; top: 10px; right: 16px; font-size: 26px; color: var(--sub); cursor: pointer; line-height: 1; }
.abx:hover { color: var(--ink); }
.abi { color: var(--sub); font-size: 13.5px; margin-bottom: 14px; }
.absec { font-size: 14px; font-weight: 600; margin: 14px 0 10px; }
.abgroup { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 12px 12px; margin-bottom: 12px; }
.abrow { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.abrow .abqr { flex: 1 1 110px; }
.abrow2 { display: flex; gap: 12px; flex-wrap: wrap; }
.abrow2 .abgroup { flex: 1 1 180px; margin-bottom: 0; }
.abqr { text-align: center; }
.abqr img, .abpay img { -webkit-touch-callout: default; -webkit-user-drag: auto; user-select: auto; }
.abqr img { width: 110px; height: 110px; border-radius: 8px; display: block; margin: 0 auto; background: #fff; }
.abqr b { display: block; font-size: 13px; margin-top: 6px; font-weight: 600; }
.abqr i { display: block; font-style: normal; font-size: 11px; color: var(--sub); }
.abd { text-align: center; color: var(--sub); font-size: 12.5px; margin-top: 8px; line-height: 1.5; }
.abpay { text-align: center; border-top: 1px solid var(--line); margin-top: 16px; padding-top: 2px; }
.abpay img { width: 132px; border-radius: 8px; margin: 2px auto 0; display: block; }
</style>
</head>
<body>
<img src="assets/share.jpg" alt="" style="display:none">
<header>
  <h1>中国城市老照片<small>__SUBTITLE__</small></h1>
  <span class="ab-link" id="ab-top" onclick="openAb()">关于作者</span>
  <div class="bar">
    <span class="lab">年代</span>
    <span class="chip e on" data-e="全部">全部</span>
    <span class="chip e" data-e="1850–99">1850–99</span>
    <span class="chip e" data-e="1900–09">1900–09</span>
    <span class="chip e" data-e="1910–19">1910–19</span>
    <span class="chip e" data-e="1920–29">1920–29</span>
    <span class="chip e" data-e="1930–49">1930–49</span>
    <input type="search" id="q" placeholder="搜索：宝塔 / 城门 / 寺庙 / 街景 / 西湖 …">
    <span class="chip" id="lucky" title="随机看一张">&#127922; 随便看看</span>
    <span class="count" id="count"></span>
  </div>
</header>
<div class="layout">
  <aside id="cities"><input type="search" id="cq" placeholder="过滤城市…">__CITY_ROWS__</aside>
  <main><div class="grid" id="grid"></div></main>
</div>
<footer>图片均来自公有领域馆藏 · <span class="ab-link" onclick="openAb()">关于作者 ☕</span><span id="pv"> · 本站访问量 <span id="pvn"></span></span></footer>

<div id="ab">
  <div class="abc">
    <span class="abx" id="abclose">&times;</span>
    <h2>关于作者</h2>
    <p class="abi">你好，我是本站作者 Benson，一个互联网时代的非遗传承人。业余收集 1850–1949 年间散落在公有领域馆藏里的中国城市老照片，纯属兴趣。平时还捣鼓了下面这些小东西 &#128071;</p>
    <div class="abgroup">
      <div class="abrow">
        <div class="abqr"><img src="assets/gzh_speak.jpg" alt="公众号：公众演讲助手"><b>公众演讲助手</b><i>公众号</i></div>
        <div class="abqr"><img src="assets/mini_speak.jpg" alt="小程序：头马演讲助手Pro"><b>头马演讲助手Pro</b><i>小程序</i></div>
      </div>
      <p class="abd">头马演讲俱乐部入门必备，完整收录最全冠军演讲视频和讲稿</p>
    </div>
    <div class="abrow2">
      <div class="abgroup">
        <div class="abqr"><img src="assets/gzh_ai.jpg" alt="公众号：AI生菜"><b>AI生菜</b><i>公众号</i></div>
        <p class="abd">关于AI的日常实践和随机发言</p>
      </div>
      <div class="abgroup">
        <div class="abqr"><img src="assets/game_tank.jpg" alt="小游戏：坦克纵队"><b>坦克纵队</b><i>小游戏</i></div>
        <p class="abd">经典坦克大战复刻版本</p>
      </div>
    </div>
    <div class="abpay">
      <div class="absec">觉得本站不错？请作者喝杯咖啡 &#9749;</div>
      <img src="assets/pay.jpg" alt="微信赞赏码">
    </div>
  </div>
</div>

<div id="top" title="回到顶部">&#8593;</div>
<div id="lb">
  <span id="close">&times;</span>
  <span class="nav" id="prev">&#10094;</span>
  <span class="nav" id="next">&#10095;</span>
  <div class="stage"><img id="lbimg" alt=""></div>
  <div class="info" id="lbinfo"></div>
</div>

<script>
const ITEMS = __DATA__;
const ZH = __ZH__;
const KW = [["宝塔","pagoda"],["塔","pagoda"],["城门","gate"],["门","gate"],["寺庙","temple"],
  ["寺","temple"],["庙","temple"],["街","street road"],["桥","bridge"],["湖","lake"],
  ["船","boat junk"],["城墙","wall"],["和尚","monk"],["道士","priest taoist"],
  ["轿","sedan chair"],["运河","canal"],["教堂","church cathedral"],["火车","railway train"],
  ["车站","station"],["码头","wharf pier bund"],["市场","market"],["人力车","rickshaw"],
  ["士兵","soldier"],["学校","school college"],["医院","hospital"],["地图","map"],
  ["明信片","postcard"],["墓","tomb grave"],["山","mountain hill"],["河","river"],["岛","island"]];
const grid = document.getElementById('grid'), count = document.getElementById('count');
let shown = [];

function enc(p) { return p.split('/').map(encodeURIComponent).join('/'); }

function render() {
  const q = document.getElementById('q').value.trim().toLowerCase();
  const c = document.querySelector('.city.on').dataset.c;
  const e = document.querySelector('.chip.e.on').dataset.e;
  let terms = [];
  if (q) {
    terms = [q];
    for (const [zh, en] of KW) if (q.includes(zh)) terms.push(...en.split(' '));
  }
  shown = ITEMS.filter(it => {
    if (c !== '全部' && it.city !== c) return false;
    if (e !== '全部' && it.e !== e) return false;
    if (!q) return true;
    const hay = (it.t + ' ' + it.f + ' ' + it.y + ' ' + ZH[it.city]).toLowerCase();
    return terms.some(t => hay.includes(t));
  });
  grid.innerHTML = shown.map((it, i) => `
    <div class="card" onclick="openLb(${i})">
      <img src="${enc(it.th)}" loading="lazy" alt="">
      <div class="cap"><div class="t">${it.t}</div><div class="y">${ZH[it.city]} · ${it.y} · ${it.s}</div></div>
    </div>`).join('');
  count.textContent = shown.length + ' / ' + ITEMS.length + ' 张';
  updateHash();
  window.scrollTo({top: 0});
}

let cur = 0, showSeq = 0;
const lb = document.getElementById('lb');
function openLb(i) { cur = i; lb.classList.add('open'); show(); }
function closeLb() { lb.classList.remove('open'); updateHash(); }
function show() {
  const it = shown[cur], seq = ++showSeq;
  const lbimg = document.getElementById('lbimg');
  lbimg.src = enc(it.th);
  const full = new Image();
  full.onload = () => { if (seq === showSeq) lbimg.src = full.src; };
  full.src = enc(it.dir + it.f);
  for (const d of [1, -1]) {
    const n = shown[(cur + d + shown.length) % shown.length];
    if (n && n !== it) (new Image()).src = enc(n.dir + n.f);
  }
  document.getElementById('lbinfo').innerHTML =
    `${ZH[it.city]} · ${it.t} &nbsp;·&nbsp; ${it.y} &nbsp;·&nbsp; ${it.lic} &nbsp;·&nbsp; <a href="${it.src}" target="_blank">馆藏来源</a> &nbsp;(${cur + 1}/${shown.length})`;
  updateHash();
}
function step(d) { cur = (cur + d + shown.length) % shown.length; show(); }
let tX = 0, tY = 0;
lb.addEventListener('touchstart', e => { tX = e.touches[0].clientX; tY = e.touches[0].clientY; }, {passive: true});
lb.addEventListener('touchend', e => {
  const dx = e.changedTouches[0].clientX - tX, dy = e.changedTouches[0].clientY - tY;
  if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 2) step(dx < 0 ? 1 : -1);
}, {passive: true});
document.getElementById('prev').onclick = e => { e.stopPropagation(); step(-1); };
document.getElementById('next').onclick = e => { e.stopPropagation(); step(1); };
document.getElementById('close').onclick = closeLb;
lb.onclick = e => { if (e.target === lb || e.target.className === 'stage') closeLb(); };
const ab = document.getElementById('ab');
function openAb() { ab.classList.add('open'); }
document.getElementById('abclose').onclick = () => ab.classList.remove('open');
ab.onclick = e => { if (e.target === ab) ab.classList.remove('open'); };
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && ab.classList.contains('open')) { ab.classList.remove('open'); return; }
  if (!lb.classList.contains('open')) return;
  if (e.key === 'Escape') closeLb();
  if (e.key === 'ArrowLeft') step(-1);
  if (e.key === 'ArrowRight') step(1);
});
const topBtn = document.getElementById('top');
topBtn.onclick = () => window.scrollTo({top: 0, behavior: 'smooth'});
window.addEventListener('scroll', () => topBtn.classList.toggle('show', window.scrollY > 800), {passive: true});
document.addEventListener('contextmenu', e => { if (e.target.tagName === 'IMG' && !e.target.closest('#ab')) e.preventDefault(); });
document.addEventListener('dragstart', e => { if (e.target.tagName === 'IMG' && !e.target.closest('#ab')) e.preventDefault(); });
document.getElementById('q').addEventListener('input', render);
document.querySelectorAll('.city').forEach(el => el.onclick = () => {
  document.querySelector('.city.on').classList.remove('on');
  el.classList.add('on'); render();
});
document.getElementById('cq').addEventListener('input', e => {
  const v = e.target.value.trim().toLowerCase();
  document.querySelectorAll('.city').forEach(el => {
    const slug = el.dataset.c, zh = el.textContent;
    const hit = slug === '全部' || !v || zh.toLowerCase().includes(v) || slug.includes(v);
    el.style.display = hit ? '' : 'none';
  });
});
document.querySelectorAll('.chip.e').forEach(ch => ch.onclick = () => {
  document.querySelector('.chip.e.on').classList.remove('on');
  ch.classList.add('on'); render();
});

function updateHash() {
  const p = new URLSearchParams();
  const c = document.querySelector('.city.on').dataset.c;
  const e = document.querySelector('.chip.e.on').dataset.e;
  const q = document.getElementById('q').value.trim();
  if (c !== '全部') p.set('c', c);
  if (e !== '全部') p.set('e', e);
  if (q) p.set('q', q);
  if (lb.classList.contains('open') && shown[cur]) p.set('p', ITEMS.indexOf(shown[cur]));
  const s = p.toString();
  history.replaceState(null, '', s ? '#' + s : location.pathname + location.search);
}
function applyHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const c = h.get('c'), e = h.get('e'), q = h.get('q');
  if (c) {
    const el = document.querySelector('.city[data-c="' + c + '"]');
    if (el) { document.querySelector('.city.on').classList.remove('on'); el.classList.add('on'); }
  }
  if (e) {
    const el = document.querySelector('.chip.e[data-e="' + e + '"]');
    if (el) { document.querySelector('.chip.e.on').classList.remove('on'); el.classList.add('on'); }
  }
  if (q) document.getElementById('q').value = q;
  return parseInt(h.get('p'));
}
const p0 = applyHash();
document.getElementById('lucky').onclick = () => {
  if (shown.length) openLb(Math.floor(Math.random() * shown.length));
};
fetch('https://jinbin.goatcounter.com/counter/TOTAL.json')
  .then(r => r.ok ? r.json() : Promise.reject())
  .then(d => {
    const n = parseInt(String(d.count).replace(/[^0-9]/g, ''), 10);
    if (n) {
      document.getElementById('pvn').textContent = n.toLocaleString();
      document.getElementById('pv').style.display = 'inline';
    }
  }).catch(() => {});
render();
if (!isNaN(p0) && ITEMS[p0]) {
  let idx = shown.indexOf(ITEMS[p0]);
  if (idx < 0) {
    document.querySelector('.city.on').classList.remove('on');
    document.querySelector('.city[data-c="全部"]').classList.add('on');
    document.querySelector('.chip.e.on').classList.remove('on');
    document.querySelector('.chip.e[data-e="全部"]').classList.add('on');
    document.getElementById('q').value = '';
    render();
    idx = shown.indexOf(ITEMS[p0]);
  }
  if (idx >= 0) openLb(idx);
}
</script>
<script data-goatcounter="https://jinbin.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
</body>
</html>
"""

subtitle = f"清末民国 · {len(present)} 城 {len(items)} 张 · 杜克甘博档案 + 维基共享馆藏"
desc = f"清末民国 {len(present)} 城 {len(items)} 张公有领域老照片，杜克甘博档案 + 维基共享馆藏，可按城市、年代、关键词浏览。"
html = (html.replace("__DATA__", data_js).replace("__ZH__", zh_js)
            .replace("__CITY_ROWS__", city_rows).replace("__SUBTITLE__", subtitle)
            .replace("__DESC__", desc))
open(f"{BASE}/gallery.html", "w").write(html)
open(f"{BASE}/index.html", "w").write(html)
print("gallery.html + index.html written:", len(html)//1024, "KB |", len(present), "cities, sidebar layout")
