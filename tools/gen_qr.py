#!/usr/bin/env python3
"""生成站点宣传二维码（圆点风格 + 城字印章）。

三个产物，地址统一取 SITE_URL，默认与 build_gallery2.py 的默认值一致：
  assets/qrcode.svg        圆点码，不含印章 —— qr_poster.html 用它，印章由页面 DOM 叠加
  assets/qrcode.png        圆点码 + 烤进去的印章，1440px，单独发群/朋友圈用
  assets/qrcode-plain.png  方块素码，540px，塞进别人版式里时用

用法（segno/Pillow 没装就让 uv 现装，不污染系统 python）:
  uv run --with segno --with pillow python3 tools/gen_qr.py
  SITE_URL=https://example.com/ uv run --with segno --with pillow python3 tools/gen_qr.py

纠错等级固定 H（可容 30% 损伤），所以中间盖印章仍能扫。段长变了版本会跟着变
（模块数少 = 单点更大 = 更好扫），几何全部按模块数推导，不写死画布尺寸。
改完二维码记得重截海报，见 qr_poster.html 顶部注释。
"""
import os
import subprocess
import sys

try:
    import segno
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError as e:
    sys.exit(f"缺依赖 {e.name}。用这条跑：\n"
             f"  uv run --with segno --with pillow python3 tools/gen_qr.py")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE, "assets")
SITE_URL = os.environ.get("SITE_URL", "https://laozhaopian.pages.dev/")

DARK = "#2b2620"     # 数据点：正文同色，不用纯黑
BRAND = "#9a5b2f"    # 定位角 + 印章：站点主色
BG = "#ffffff"

PITCH = 10           # SVG 里每模块的边长（用户单位）
QUIET = 4            # 静默区模块数，规范最少 4
DOT_R = 4.7          # 数据点半径，留一丝缝，不然糊成一片
PNG_SIZE = 1440      # 带印章 PNG
PLAIN_SIZE = 540     # 素码 PNG
LOGO_FRAC = 0.17     # 印章边长占码宽比例，遮挡约 3% 面积
SEAL_CHAR = "城"
SEAL_FONTS = [       # 印章字体候选，取第一个存在的；宋体优先，和站点标题同族
    "/System/Library/Fonts/Songti.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def seal_font_path():
    """开工前就把字体定下来，别等画到一半才炸——那会留下半新半旧的 assets/。"""
    for p in SEAL_FONTS:
        if os.path.exists(p):
            return p
    sys.exit("找不到可用的印章字体，候选都不存在：\n  " + "\n  ".join(SEAL_FONTS) +
             "\n装一个中文字体或改 SEAL_FONTS。")


def finder_origins(n):
    """三个定位角左上模块坐标（第四角没有，QR 就靠这个判方向）。"""
    return [(0, 0), (0, n - 7), (n - 7, 0)]


def is_finder(r, c, n):
    """落在定位角 8x8（含分隔带）里的模块交给圆角方框画，别再画点。"""
    return ((r < 8 and c < 8) or (r < 8 and c >= n - 8) or (r >= n - 8 and c < 8))


def build_svg(matrix, n):
    side = (n + 2 * QUIET) * PITCH
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}"'
           f' width="{side}" height="{side}">',
           f'<rect width="{side}" height="{side}" fill="{BG}"/>']
    # 定位角：外框 / 挖白 / 实心，三层圆角同心
    for r0, c0 in finder_origins(n):
        x, y = (QUIET + c0) * PITCH, (QUIET + r0) * PITCH
        for inset, span, rx, fill in ((0, 7, 1.2, BRAND), (1, 5, .84, BG), (2, 3, .54, BRAND)):
            out.append(f'<rect x="{x + inset * PITCH:g}" y="{y + inset * PITCH:g}"'
                       f' width="{span * PITCH}" height="{span * PITCH}"'
                       f' rx="{rx * PITCH:g}" fill="{fill}"/>')
    for r, row in enumerate(matrix):
        for c, on in enumerate(row):
            if not on or is_finder(r, c, n):
                continue
            cx = (QUIET + c) * PITCH + PITCH / 2
            cy = (QUIET + r) * PITCH + PITCH / 2
            out.append(f'<circle cx="{cx:g}" cy="{cy:g}" r="{DOT_R:g}" fill="{DARK}"/>')
    out.append("</svg>")
    return "".join(out)


def build_png(matrix, n, size, font_path):
    """圆点码 + 印章。4 倍超采样再缩，圆边才不锯齿。"""
    ss = 4
    big = size * ss
    unit = big / (n + 2 * QUIET)          # 一个模块多少像素
    img = Image.new("RGB", (big, big), BG)
    d = ImageDraw.Draw(img)
    for r0, c0 in finder_origins(n):
        x, y = (QUIET + c0) * unit, (QUIET + r0) * unit
        for inset, span, rx, fill in ((0, 7, 1.2, BRAND), (1, 5, .84, BG), (2, 3, .54, BRAND)):
            x0, y0 = x + inset * unit, y + inset * unit
            d.rounded_rectangle([x0, y0, x0 + span * unit, y0 + span * unit],
                                radius=rx * unit, fill=fill)
    rad = DOT_R / PITCH * unit
    for r, row in enumerate(matrix):
        for c, on in enumerate(row):
            if not on or is_finder(r, c, n):
                continue
            cx = (QUIET + c + .5) * unit
            cy = (QUIET + r + .5) * unit
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=DARK)
    # 印章：圆角方块直接压在点上，不留白圈——白圈会让码看着断开
    box = big * LOGO_FRAC
    x0 = y0 = (big - box) / 2
    d.rounded_rectangle([x0, y0, x0 + box, y0 + box], radius=box * .22, fill=BRAND)
    font = ImageFont.truetype(font_path, int(box * .62))
    d.text((big / 2, big / 2), SEAL_CHAR, font=font, fill=BG, anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


def build_plain_png(matrix, n, size):
    """方块素码。模块边界按 round 分摊到整像素，边缘保持利落，不做超采样。"""
    units = n + 2 * QUIET
    edge = [round(i * size / units) for i in range(units + 1)]
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    for r, row in enumerate(matrix):
        for c, on in enumerate(row):
            if on:
                d.rectangle([edge[QUIET + c], edge[QUIET + r],
                             edge[QUIET + c + 1] - 1, edge[QUIET + r + 1] - 1], fill=DARK)
    return img


def verify(paths):
    """双引擎回读：CoreImage（macOS 原生，微信/相机同源）+ OpenCV。可用的引擎都得读对。

    两个引擎各自可能不在（swift 要 Xcode CLT，cv2 要单独装），缺了就跳过并说明，
    不能因为校验工具缺席就抛栈——但也不能一个都没有还算通过。
    """
    got = None
    try:
        ci = subprocess.run(["swift", "-", *paths], input=CI_SWIFT,
                            capture_output=True, text=True)
        got = dict(l.split("\t", 1) for l in ci.stdout.splitlines() if "\t" in l)
    except (FileNotFoundError, OSError):
        print("  ! 找不到 swift（需 Xcode 命令行工具），跳过 CoreImage 引擎")
    try:
        import cv2
    except ModuleNotFoundError:
        cv2 = None
        print("  ! 没装 opencv，跳过 OpenCV 引擎（要用就加 --with opencv-python-headless）")
    if got is None and cv2 is None:
        print("  ! 两个引擎都不可用，本次没做回读校验——产物已写盘，请手动扫码确认。")
        return False
    ok = True
    for p in paths:
        rel = os.path.relpath(p, BASE)
        engines = []
        if got is not None:
            engines.append(("CoreImage", got.get(p, "读不出")))
        if cv2 is not None:
            data, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(p))
            engines.append(("OpenCV", data or "读不出"))
        bad = [f"{name}={val!r}" for name, val in engines if val != SITE_URL]
        if bad:
            ok = False
            print(f"  ✗ {rel}: " + "  ".join(bad))
        else:
            names = " + ".join(name for name, _ in engines)
            print(f"  ✓ {rel}: {names} {'均' if len(engines) > 1 else ''}读出目标地址")
    return ok


CI_SWIFT = """
import Foundation
import CoreImage
let d = CIDetector(ofType: CIDetectorTypeQRCode, context: nil,
                   options: [CIDetectorAccuracy: CIDetectorAccuracyHigh])!
for path in CommandLine.arguments.dropFirst() {
  guard let img = CIImage(contentsOf: URL(fileURLWithPath: path)) else { continue }
  let f = d.features(in: img).compactMap { ($0 as? CIQRCodeFeature)?.messageString }
  print("\\(path)\\t\\(f.first ?? "读不出")")
}
"""


def main():
    qr = segno.make(SITE_URL, error="h")
    matrix = [[bool(v) for v in row] for row in qr.matrix]
    n = len(matrix)
    print(f"SITE_URL={SITE_URL}  ({len(SITE_URL.encode())} bytes)")
    print(f"QR version {qr.version}-H, {n}x{n} 模块")

    # 三个产物先全部在内存里做好，再一起落盘。中途出错（缺字体等）不能只写一半，
    # 那会让 assets/ 里 svg 是新的、png 是旧的，海报和单发的码指向不同地址。
    svg_data = build_svg(matrix, n)
    png_img = build_png(matrix, n, PNG_SIZE, seal_font_path())
    plain_img = build_plain_png(matrix, n, PLAIN_SIZE)

    svg = os.path.join(ASSETS, "qrcode.svg")
    png = os.path.join(ASSETS, "qrcode.png")
    plain = os.path.join(ASSETS, "qrcode-plain.png")
    with open(svg, "w") as f:
        f.write(svg_data)
    png_img.save(png)
    plain_img.save(plain, optimize=True)
    for p in (svg, png, plain):
        print(f"wrote {os.path.relpath(p, BASE)} ({os.path.getsize(p) / 1024:.1f} KB)")

    print("回读校验（含印章那张是重点，遮挡后仍须可扫）:")
    if not verify([png, plain]):
        sys.exit("有产物扫不出或扫错，别提交。")


if __name__ == "__main__":
    main()
