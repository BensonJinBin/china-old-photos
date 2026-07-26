#!/usr/bin/env python3
"""Build the compressed publish tree from main HEAD and push it to gh-pages.

gh-pages 不是 main 的镜像：馆藏原图（<city>/wiki|gamble/）长边压到 1200px，
其余文件原样。压缩结果缓存在 ~/.cache/china-old-photos-deploy，只压新增/变动的图。
用法: python3 tools/deploy.py ["提交信息"]
"""
import json, os, re, shutil, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.expanduser("~/.cache/china-old-photos-deploy")
BLOBS = os.path.join(CACHE, "blobs")
STAGE = os.path.join(CACHE, "stage")
MANIFEST = os.path.join(CACHE, "manifest.json")
MAXDIM = 1200
PHOTO_RE = re.compile(r"^[a-z]+/(wiki|gamble)/.+\.(jpe?g|png)$", re.I)


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


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else f"deploy: {git('rev-parse', '--short', 'main')} 压缩发布"
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
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(STAGE) for f in fs)
    print(f"stage: {shrunk} shrunk + {copied} as-is = {total/1e9:.2f} GB")

    # 4. write tree via temp index, commit on top of gh-pages, push
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


if __name__ == "__main__":
    main()
