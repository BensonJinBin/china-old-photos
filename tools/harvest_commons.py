#!/usr/bin/env python3
"""从维基共享采集城市老照片：分类为主 + 搜索补充 + 分类校验。

为什么这么设计：早期采集只用全文搜索 + 年代/授权/尺寸三道过滤，没校验"这张图是否
真属于这座城市"，导致青岛的照片被采进武汉目录（2026-07-26 发现并修正）。
分类接口精度高但覆盖不均（青岛 500+ 候选，济南几乎为 0），所以两条路都要，
且搜索来的必须过分类校验。

用法：
  python3 tools/harvest_commons.py --city qingdao --dry-run          # 只看候选，不下载
  python3 tools/harvest_commons.py --city qingdao --limit 60         # 采最多 60 张
  python3 tools/harvest_commons.py --city qingdao --mode cat         # 只用分类接口
  python3 tools/harvest_commons.py --audit                           # 校验存量归属

采集完记得跑 tools/build_gallery2.py 重建页面、给新照片补中文标题
（规范见 tools/TITLES_ZH_STYLE.md），再跑 tools/deploy.py 发布。
"""
import argparse, json, os, re, subprocess, sys, time, urllib.parse, html as htmlmod
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(BASE, "tools")
DATA = os.path.join(TOOLS, "commons_cities.json")
API = "https://commons.wikimedia.org/w/api.php"
UA = "ChinaOldPhotos/1.1 (jinbin@pomogo.co; personal archive)"

# 城市 → (Commons 英文名, 校验别名, 额外搜索词)
# 别名用于分类校验：文件的分类或标题里必须出现其中之一，否则丢弃。
CITIES = {
 "beijing":  ("Beijing", ["beijing", "peking", "peiping", "pekin"], ["Peking 1900 photograph"]),
 "tianjin":  ("Tianjin", ["tianjin", "tientsin"], ["Tientsin concession photograph"]),
 "shanghai": ("Shanghai", ["shanghai"], ["Old Shanghai photograph"]),
 "hangzhou": ("Hangzhou", ["hangzhou", "hangchow"], ["Hangchow West Lake photograph"]),
 "nanjing":  ("Nanjing", ["nanjing", "nanking"], ["Nanking old photograph"]),
 "guangzhou":("Guangzhou", ["guangzhou", "canton"], ["Canton China photograph"]),
 "qingdao":  ("Qingdao", ["qingdao", "tsingtau", "tsingtao", "kiautschou", "kiaochow"],
              ["Tsingtau photograph", "Kiautschou photograph"]),
 "jinan":    ("Jinan", ["jinan", "tsinan", "tsinanfu"], ["Tsinan Shantung photograph"]),
 "fuzhou":   ("Fuzhou", ["fuzhou", "foochow"], ["Foochow China photograph"]),
 "xiamen":   ("Xiamen", ["xiamen", "amoy", "kulangsu", "gulangyu"], ["Amoy China photograph"]),
 "ningbo":   ("Ningbo", ["ningbo", "ningpo"], ["Ningpo China photograph"]),
 "suzhou":   ("Suzhou", ["suzhou", "soochow"], ["Soochow China photograph"]),
 "wuhan":    ("Wuhan", ["wuhan", "hankow", "hankou", "wuchang", "hanyang"],
              ["Hankow photograph", "Wuchang 1911"]),
 "chongqing":("Chongqing", ["chongqing", "chungking"], ["Chungking photograph"]),
 "chengdu":  ("Chengdu", ["chengdu", "chengtu"], ["Chengtu Szechuan photograph"]),
 "kunming":  ("Kunming", ["kunming", "yunnanfu"], ["Yunnanfu photograph"]),
 "dalian":   ("Dalian", ["dalian", "dairen", "dalny", "port arthur", "lushun"],
              ["Port Arthur 1904 photograph"]),
 "harbin":   ("Harbin", ["harbin", "kharbin"], ["Harbin Russian photograph"]),
 "shenyang": ("Shenyang", ["shenyang", "mukden", "fengtien"], ["Mukden photograph"]),
 "hongkong": ("Hong Kong", ["hong kong", "hongkong", "kowloon"], ["Hong Kong 1900s photograph"]),
 "macau":    ("Macau", ["macau", "macao"], ["Macao old photograph"]),
 "kaifeng":  ("Kaifeng", ["kaifeng", "kaifengfu"], ["Kaifeng Honan photograph"]),
 "xian":     ("Xi'an", ["xi'an", "xian", "sian", "sianfu"], ["Sianfu Shensi photograph"]),
 "taizhou":  ("Taizhou", ["taizhou", "taichow"], ["Taichow Chekiang photograph"]),
}

DECADES = [f"{d}s" for d in range(1850, 1950, 10)]
OK_LIC = re.compile(r"(public domain|pd-|cc0|cc by(?! .*sa)|attribution\b|no restrictions)", re.I)
YEAR = re.compile(r"\b(18[5-9]\d|19[0-4]\d)\b")
SKIP_EXT = re.compile(r"\.(pdf|djvu|tiff?|svg|ogg|webm|stl|gif|xcf)$", re.I)
MIN_W, MAX_BYTES, MIN_BYTES = 400, 40_000_000, 15_000


def api(**params):
    q = urllib.parse.urlencode({"format": "json", **params})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:
            if attempt == 2:
                print(f"  ! API 失败: {e}", file=sys.stderr)
                return {}
            time.sleep(2 * (attempt + 1))


def strip_tags(v):
    return re.sub(r"<[^>]+>", "", htmlmod.unescape(v or "")).strip()


def sanitize(name):
    t = os.path.splitext(re.sub(r"^File:", "", name))[0]
    t = re.sub(r"[^\w\s()一-鿿-]", "", t).strip()
    return re.sub(r"\s+", "_", t)[:70] or "untitled"


def existing_categories(en):
    """探测该城市实际存在的分类（年代分类 + 常见命名 + 一层子分类）。"""
    cands = [f"Category:{en} in the {d}" for d in DECADES]
    cands += [f"Category:History of {en}", f"Category:Old photographs of {en}",
              f"Category:Black and white photographs of {en}",
              f"Category:Historical images of {en}"]
    live = []
    for i in range(0, len(cands), 20):
        d = api(action="query", titles="|".join(cands[i:i + 20]), prop="categoryinfo")
        for p in d.get("query", {}).get("pages", {}).values():
            ci = p.get("categoryinfo") or {}
            if ci.get("files", 0) or ci.get("subcats", 0):
                live.append(p["title"])
        time.sleep(0.25)
    # 一层子分类（只取名字里带城市名或年代的，避免飘走）
    subs = []
    for c in live:
        d = api(action="query", list="categorymembers", cmtitle=c, cmtype="subcat", cmlimit="60")
        for m in d.get("query", {}).get("categorymembers", []):
            t = m["title"]
            low = t.lower()
            if en.lower() in low or YEAR.search(t):
                subs.append(t)
        time.sleep(0.25)
    return live, sorted(set(subs) - set(live))


def cat_files(cat):
    out, cont = [], None
    while True:
        kw = dict(action="query", list="categorymembers", cmtitle=cat,
                  cmtype="file", cmlimit="500")
        if cont:
            kw["cmcontinue"] = cont
        d = api(**kw)
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        cont = d.get("continue", {}).get("cmcontinue")
        time.sleep(0.25)
        if not cont:
            break
    return out


def search_files(term, limit=50):
    d = api(action="query", list="search", srsearch=term, srnamespace="6", srlimit=str(limit))
    return [r["title"] for r in d.get("query", {}).get("search", [])]


def file_meta(titles):
    """批量取 imageinfo + categories，返回 {title: {...}}。"""
    out = {}
    for i in range(0, len(titles), 40):
        batch = titles[i:i + 40]
        d = api(action="query", titles="|".join(batch), prop="imageinfo|categories",
                iiprop="url|size|extmetadata", cllimit="500")
        for p in d.get("query", {}).get("pages", {}).values():
            if "imageinfo" not in p:
                continue
            ii = p["imageinfo"][0]
            em = ii.get("extmetadata", {})
            g = lambda k: strip_tags(em.get(k, {}).get("value", ""))
            out[p["title"]] = {
                "url": ii["url"], "w": ii.get("width", 0), "bytes": ii.get("size", 0),
                "date": g("DateTimeOriginal").split("date QS")[0].strip()[:40],
                "lic": g("LicenseShortName"),
                "cats": [c["title"] for c in p.get("categories", [])],
            }
        time.sleep(0.25)
    return out


def belongs(title, meta, aliases):
    """城市校验：标题或分类里出现本城别名，且标题未点名别的城市。

    两道都必要：只看分类会漏（成套系列的分类挂着 A 城，个别照片其实拍在 B 城，
    如「Prince Henry of Prussia in Qingdao」里混着 Peking 的照片）；只看标题会漏
    （大量照片标题不含城市名，只靠分类归属）。
    """
    low_title = title.lower()
    hay = (title + " " + " ".join(meta["cats"])).lower()
    if not any(a in hay for a in aliases):
        return False
    for c, (_, al, _) in CITIES.items():
        if al is aliases:
            continue
        if any(a in low_title for a in al) and not any(a in low_title for a in aliases):
            return False   # 标题点名了别的城市
    return True


def passes(meta):
    if not YEAR.search(meta["date"]):
        return "无 1850–1949 年代"
    if not OK_LIC.search(meta["lic"]):
        return f"授权不合: {meta['lic'][:24]}"
    if meta["w"] < MIN_W:
        return f"宽度 {meta['w']}"
    if meta["bytes"] > MAX_BYTES:
        return "文件过大"
    return None


def harvest(city, mode, limit, dry):
    en, aliases, extra = CITIES[city]
    store = json.load(open(DATA)) if os.path.exists(DATA) else {}
    have = {r["title"] for r in store.get(city, [])}
    print(f"== {city} ({en})  已有 {len(have)} 张")

    cand = []
    if mode in ("cat", "both"):
        live, subs = existing_categories(en)
        print(f"  分类命中 {len(live)} 个主分类 + {len(subs)} 个子分类")
        for c in live + subs:
            fs = cat_files(c)
            cand += fs
            if fs:
                print(f"    {c.replace('Category:','')}: {len(fs)}")
    if mode in ("search", "both"):
        for t in extra:
            fs = search_files(t)
            cand += fs
            print(f"  搜索「{t}」: {len(fs)}")
            time.sleep(0.3)

    cand = [t for t in dict.fromkeys(cand) if not SKIP_EXT.search(t) and t not in have]
    print(f"  去重后候选 {len(cand)} 张，开始取元数据…")
    meta = file_meta(cand)

    picked, rejected = [], {}
    for t in cand:
        m = meta.get(t)
        if not m:
            rejected["无元数据"] = rejected.get("无元数据", 0) + 1
            continue
        if not belongs(t, m, aliases):
            rejected["城市校验不通过"] = rejected.get("城市校验不通过", 0) + 1
            continue
        why = passes(m)
        if why:
            k = why.split(":")[0]
            rejected[k] = rejected.get(k, 0) + 1
            continue
        picked.append((t, m))
        if len(picked) >= limit:
            break
    print(f"  通过 {len(picked)} 张 | 淘汰: {rejected}")

    if dry:
        for t, m in picked[:25]:
            print(f"    · {m['date'][:18]:18s} {m['w']:5d}px  {t.replace('File:','')[:72]}")
        if len(picked) > 25:
            print(f"    … 另 {len(picked)-25} 张")
        print("  (--dry-run，未下载)")
        return

    ddir = os.path.join(BASE, city, "wiki")
    os.makedirs(ddir, exist_ok=True)
    nums = [int(m.group(1)) for f in os.listdir(ddir)
            if (m := re.match(r"(\d+)_", f))]
    n = max(nums, default=0)
    kept = []
    for t, m in picked:
        n += 1
        ext = os.path.splitext(urllib.parse.urlparse(m["url"]).path)[1].lower() or ".jpg"
        fname = f"{n:02d}_{sanitize(t)}{ext}"
        dest = os.path.join(ddir, fname)
        r = subprocess.run(["curl", "-sL", "--fail", "--retry", "2", "--max-time", "300",
                            "-H", f"User-Agent: {UA}", "-o", dest, m["url"]],
                           capture_output=True)
        size = os.path.getsize(dest) if os.path.exists(dest) else 0
        if r.returncode == 0 and size > MIN_BYTES:
            kept.append({"title": t, "url": m["url"], "date": m["date"], "lic": m["lic"],
                         "w": m["w"], "file": fname, "bytes": size})
        else:
            if os.path.exists(dest):
                os.remove(dest)
            n -= 1
        time.sleep(0.3)
    store.setdefault(city, []).extend(kept)
    json.dump(store, open(DATA, "w"), ensure_ascii=False, indent=1)
    print(f"  下载 {len(kept)} 张 → {city}/wiki/，commons_cities.json 已更新")
    print("  下一步: python3 tools/build_gallery2.py（并给新照片补中文标题）")


def audit():
    """校验存量归属：查每张维基照片的 Commons 分类，标出城市校验不通过的。"""
    store = json.load(open(DATA))
    bad = []
    for city, recs in store.items():
        if city not in CITIES:
            print(f"! 未知城市键: {city}")
            continue
        aliases = CITIES[city][1]
        titles = [r["title"] for r in recs]
        meta = file_meta(titles)
        for r in recs:
            m = meta.get(r["title"])
            if not m:
                continue
            if not belongs(r["title"], m, aliases):
                bad.append((city, r["file"], r["title"], m["cats"][:6]))
        print(f"{city}: {len(recs)} 张已校验")
    print(f"\n城市校验不通过 {len(bad)} 张:")
    for city, f, t, cats in bad:
        print(f"  [{city}] {f}")
        print(f"        分类: {', '.join(c.replace('Category:','') for c in cats)}")
    if not bad:
        print("  （无）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", choices=sorted(CITIES))
    ap.add_argument("--mode", choices=["cat", "search", "both"], default="both")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--audit", action="store_true")
    a = ap.parse_args()
    if a.audit:
        audit()
    elif a.city:
        harvest(a.city, a.mode, a.limit, a.dry_run)
    else:
        ap.error("需要 --city 或 --audit")
