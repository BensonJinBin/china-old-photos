#!/usr/bin/env python3
"""Build the compressed publish tree from main HEAD and publish it.

gh-pages 不是 main 的镜像：馆藏原图（<city>/wiki|gamble/）长边压到 1200px，
其余文件原样。压缩结果缓存在 ~/.cache/china-old-photos-deploy，只压新增/变动的图。

用法:
  python3 tools/deploy.py ["提交信息"]          # 发 GitHub Pages（gh-pages 分支），默认
  python3 tools/deploy.py --cf ["提交信息"]     # 发 Cloudflare Pages（wrangler 直传发布树）
  python3 tools/deploy.py --both ["提交信息"]   # 两边都发

主站是 https://laozhaopian.pages.dev/ 。Cloudflare 直传不走构建容器、不用 clone 仓库，
wrangler 按内容 hash 去重，第二次起只上传新增/变动的图。项目名和分支可用环境变量覆盖：
  CF_PAGES_PROJECT=laozhaopian  CF_PAGES_BRANCH=main

首次准备（一次性，production-branch 必须和 CF_PAGES_BRANCH 一致，
否则每次直传都会落到 preview 而不是正式域名）:
  npx wrangler login
  npx wrangler pages project create laozhaopian --production-branch main
Pages 项目名不能改，它就是 pages.dev 子域；换名字只能新建项目重新全量上传。
换域名后记得重新生成页面里的 canonical / og 绝对地址（见 build_gallery2.py 的 SITE_URL）。
"""
import json, os, re, shutil, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.expanduser("~/.cache/china-old-photos-deploy")
BLOBS = os.path.join(CACHE, "blobs")
STAGE = os.path.join(CACHE, "stage")
MANIFEST = os.path.join(CACHE, "manifest.json")
MAXDIM = 1200
PHOTO_RE = re.compile(r"^[a-z]+/(wiki|gamble)/.+\.(jpe?g|png)$", re.I)

CF_PROJECT = os.environ.get("CF_PAGES_PROJECT", "laozhaopian")
CF_BRANCH = os.environ.get("CF_PAGES_BRANCH", "main")
CF_MAX_FILE = 25 * 1024 * 1024   # 单文件 25 MiB 上限
CF_MAX_FILES = 20_000            # 免费版单站文件数上限


def git(*args, env=None, cwd=BASE):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout.strip()


def probe_dims(paths):
    """Batch-probe max dimension for a list of absolute paths."""
    dims = {}
    for i in range(0, len(paths), 200):
        chunk = paths[i:i + 200]
        out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", *chunk],
                             capture_output=True, text=True).stdout
        cur = None
        for line in out.splitlines():
            if not line.startswith(" "):
                cur = line.strip()
                dims[cur] = 0
            elif cur and ("pixelWidth:" in line or "pixelHeight:" in line):
                try:
                    dims[cur] = max(dims[cur], int(line.split(":")[1]))
                except ValueError:
                    pass
    return dims


def push_gh_pages(msg):
    """临时 index 写树，commit-tree 挂到 origin/gh-pages 上再推。全程不碰工作区。"""
    git("fetch", "origin", "gh-pages")
    idx = tempfile.mktemp(prefix="deploy-index-")
    env = {**os.environ, "GIT_INDEX_FILE": idx, "GIT_WORK_TREE": STAGE,
           "GIT_DIR": os.path.join(BASE, ".git")}
    try:
        git("add", "-A", ".", env=env, cwd=STAGE)
        tree = git("write-tree", env=env, cwd=STAGE)
    finally:
        if os.path.exists(idx):
            os.remove(idx)
    parent = git("rev-parse", "origin/gh-pages")
    commit = git("commit-tree", tree, "-p", parent, "-m", msg)
    git("push", "origin", f"{commit}:refs/heads/gh-pages")
    print(f"pushed gh-pages {commit[:9]} ({msg})")


def deploy_cf(msg, count, oversize):
    """wrangler 直传发布树到 Cloudflare Pages。"""
    if oversize:
        sys.exit("以下文件超过 Cloudflare Pages 单文件 25 MiB 上限，压缩后再发：\n  " +
                 "\n  ".join(f"{r} ({s/1024/1024:.1f} MB)" for r, s in oversize))
    if count > CF_MAX_FILES:
        sys.exit(f"发布树 {count} 个文件，超过免费版 {CF_MAX_FILES} 上限。")
    if not shutil.which("npx"):
        sys.exit("找不到 npx，先装 Node.js（或全局装 wrangler 后改用 wrangler 命令）。")
    # cwd 用 CACHE 而不是 STAGE：wrangler 会在 cwd 下写 .wrangler/ 本地状态目录，
    # 落在发布树里就成了要上传的内容。也不能用仓库根，那会把工作区弄脏。
    r = subprocess.run(["npx", "--yes", "wrangler@latest", "pages", "deploy", STAGE,
                        "--project-name", CF_PROJECT, "--branch", CF_BRANCH,
                        "--commit-dirty=true", "--commit-message", msg], cwd=CACHE)
    if r.returncode != 0:
        sys.exit(
            f"wrangler pages deploy 失败（exit {r.returncode}）。原因见 wrangler 日志：\n"
            f"  ls -t ~/Library/Preferences/.wrangler/logs/*.log | head -1\n"
            f"常见两类：未登录（先 `npx wrangler login` 或设 CLOUDFLARE_API_TOKEN）；\n"
            f"网络超时（UND_ERR_HEADERS_TIMEOUT）——直接重跑即可，已上传的资源按 hash 留在\n"
            f"项目里，重试只补没传上去的那部分。")
    print(f"deployed to Cloudflare Pages: {CF_PROJECT} / {CF_BRANCH} ({msg})")


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    rest = [a for a in sys.argv[1:] if not a.startswith("--")]
    unknown = flags - {"--cf", "--gh", "--both"}
    if unknown:
        sys.exit(f"未知参数: {' '.join(sorted(unknown))}\n{__doc__}")
    targets = set()
    if flags & {"--cf", "--both"}:
        targets.add("cf")
    if flags & {"--gh", "--both"} or not targets:
        targets.add("gh")

    msg = rest[0] if rest else f"deploy: {git('rev-parse', '--short', 'main')} 压缩发布"
    if git("status", "--porcelain"):
        sys.exit("工作区不干净，先提交或还原后再部署。")

    files = [f for f in git("ls-files", "-z").split("\0") if f]
    manifest = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
    os.makedirs(BLOBS, exist_ok=True)

    # 1. figure out which photos need probing (new or changed since manifest)
    photos, need_probe = [], []
    for rel in files:
        if not PHOTO_RE.match(rel):
            continue
        st = os.stat(os.path.join(BASE, rel))
        key = f"{st.st_size}:{int(st.st_mtime)}"
        photos.append((rel, key))
        m = manifest.get(rel)
        if not m or m["key"] != key:
            need_probe.append(rel)
    if need_probe:
        print(f"probing {len(need_probe)} new/changed photos ...")
        dims = probe_dims([os.path.join(BASE, r) for r in need_probe])
        for rel in need_probe:
            st = os.stat(os.path.join(BASE, rel))
            maxdim = dims.get(os.path.join(BASE, rel), 0)
            manifest[rel] = {"key": f"{st.st_size}:{int(st.st_mtime)}",
                             "action": "shrink" if maxdim > MAXDIM else "copy"}

    # 2. shrink into blob cache where missing
    to_shrink = [rel for rel, key in photos
                 if manifest[rel]["action"] == "shrink"
                 and not os.path.exists(os.path.join(BLOBS, rel))]
    for n, rel in enumerate(to_shrink, 1):
        dst = os.path.join(BLOBS, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        r = subprocess.run(["sips", "-Z", str(MAXDIM), "--out", dst, os.path.join(BASE, rel)],
                           capture_output=True)
        if r.returncode != 0 or not os.path.exists(dst):
            sys.exit(f"sips failed on {rel}")
        if n % 100 == 0 or n == len(to_shrink):
            print(f"  shrunk {n}/{len(to_shrink)}")
    json.dump(manifest, open(MANIFEST, "w"))

    # 3. assemble stage tree (APFS clones, no real copies)
    shutil.rmtree(STAGE, ignore_errors=True)
    shrunk = copied = 0
    for rel in files:
        src = os.path.join(BASE, rel)
        m = manifest.get(rel)
        if m and PHOTO_RE.match(rel) and m["action"] == "shrink":
            src = os.path.join(BLOBS, rel)
            shrunk += 1
        else:
            copied += 1
        dst = os.path.join(STAGE, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        subprocess.run(["cp", "-c", src, dst], check=True)
    total = count = 0
    oversize = []
    for dp, _, fs in os.walk(STAGE):
        for f in fs:
            size = os.path.getsize(os.path.join(dp, f))
            total += size
            count += 1
            if size > CF_MAX_FILE:
                oversize.append((os.path.relpath(os.path.join(dp, f), STAGE), size))
    # flush：管道里 python 是块缓冲，不刷的话这行会排到 wrangler 的输出后面
    print(f"stage: {shrunk} shrunk + {copied} as-is = {total/1e9:.2f} GB, {count} files",
          flush=True)

    # 4. publish
    if "gh" in targets:
        push_gh_pages(msg)
    if "cf" in targets:
        deploy_cf(msg, count, sorted(oversize, key=lambda x: -x[1]))


if __name__ == "__main__":
    main()
