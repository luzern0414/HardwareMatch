"""为产品找实物图：LuzCrawl 打开必应图片搜索 → 从快照取原图地址 → 下载候选 → 人工挑选 → 存入经验库。

用法：
  py -X utf8 scripts/hw_fetch_images.py search <产品id> "<品牌 型号>" [--n 6] [--via http|luzcrawl --task <任务目录> --profile <Edge 配置>]
      下载候选到 experience/hardware/images/_candidates/<产品id>/，打印每张的来源与尺寸
      默认 http：一次请求必应图片结果页读原图地址，快；luzcrawl：真实浏览器，但图片页会嵌入几十张缩略图，
      一次就用掉站点 40 次/10 分钟的预算，约 10 分钟一个产品，只在 http 取不到时用
  py -X utf8 scripts/hw_fetch_images.py pick <产品id> <候选序号> [--crop x0,y0,x1,y1]
      --crop 用 0–1 的比例框只保留设备本体（去掉海报文字）
      裁成白底方图 480×480 存为 experience/hardware/images/<产品id>.jpg，并写入 catalog.json 的 image 字段
  py -X utf8 scripts/hw_fetch_images.py clean
      删除全部候选

挑图标准：产品正面或 45° 实物照、白底或干净背景、无大面积水印与广告字、能看出接口或外形；不用效果图拼图、场景海报。
"""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
IMG = SKILL / "experience" / "hardware" / "images"
CAND = IMG / "_candidates"
LUZ = Path(r"D:\Codes\Luz-Crawl")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
PREFER = ("alicdn.com", "360buyimg.com", "hikvision", "dahuatech", "suning", "jd.com")


ENGINES = {
    "so360": "https://image.so.com/i?q={q}&t={t}",
    "bing": "https://cn.bing.com/images/search?q={q}&form=HDRSC2&t={t}",
}
SO360 = r'(https?://p\d+\.ssl\.qhimgs\d?\.com/[^"\s&\\]+?\.(?:jpg|jpeg|png|webp))'


def capture(query: str, task: str, profile: str | None, engine: str = "bing") -> Path:
    import time
    url = ENGINES[engine].format(q=urllib.parse.quote(query), t=int(time.time()))
    cmd = ["node", "scripts/luz-crawl.mjs", "capture", url, "--scrolls", "0", "--out", task]
    if profile:
        cmd += ["--profile", profile]
    out = subprocess.run(cmd, cwd=LUZ, capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
    m = re.search(r'"folder":\s*"([^"]+)"', out) or re.search(r'Archive already exists: ([^"]+?)\. Use --resume', out)
    if not m:
        raise SystemExit("LuzCrawl 未返回 folder：\n" + out[-800:])
    return Path(json.loads('"' + m.group(1) + '"'))


MURL = r'murl(?:&quot;|")\s*:\s*(?:&quot;|")(https?://[^"&]+?\.(?:jpg|jpeg|png|webp))'


def bing_http(query: str) -> list[str]:
    """一次请求必应图片结果页，读出原图地址（不嵌入缩略图，不占 LuzCrawl 站点预算）。"""
    url = "https://cn.bing.com/images/search?q=" + urllib.parse.quote(query) + "&form=HDRSC2"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN"})
    h = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    return _rank(re.findall(MURL, h, re.I))


def _rank(urls: list[str]) -> list[str]:
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    out.sort(key=lambda u: 0 if any(p in u for p in PREFER) else 1)
    return out


def image_urls(folder: Path) -> list[str]:
    urls = []
    for snap in sorted((folder / "raw" / "snapshots").glob("*.html")):
        h = snap.read_text(encoding="utf-8", errors="ignore")
        found = re.findall(MURL, h, re.I)
        if not found:
            found = re.findall(SO360, h, re.I)
        urls += found
    return _rank(urls)


def download(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://cn.bing.com/"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        return data if len(data) > 5000 else None
    except Exception:
        return None


def cmd_search(args: list[str]) -> int:
    pid, query = args[0], args[1]
    task = args[args.index("--task") + 1] if "--task" in args else ""
    profile = args[args.index("--profile") + 1] if "--profile" in args else None
    n = int(args[args.index("--n") + 1]) if "--n" in args else 6
    from PIL import Image
    import time
    via = args[args.index("--via") + 1] if "--via" in args else "http"
    if via == "luzcrawl":
        # 各搜索引擎的站点预算独立：轮流用 360 图片与必应图片，耗尽时换另一个
        urls = []
        for attempt in range(12):
            engine = ("so360", "bing")[attempt % 2]
            urls = image_urls(capture(query, task, profile, engine))
            if urls:
                print(f"来源：{engine}", flush=True)
                break
            if attempt % 2 == 1:
                print(f"两个引擎都未取到（多为站点请求窗口耗尽），等待 90 秒重试", flush=True)
                time.sleep(90)
    else:
        urls = bing_http(query)
    d = CAND / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    got = []
    for u in urls:
        if len(got) >= n:
            break
        data = download(u)
        if not data:
            continue
        try:
            im = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:
            continue
        if min(im.size) < 180:
            continue
        i = len(got) + 1
        im.save(d / f"{i}.jpg", quality=88)
        got.append({"n": i, "url": u, "size": im.size})
    (d / "sources.json").write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    for g in got:
        print(f"{g['n']}  {g['size'][0]}×{g['size'][1]}  {g['url'][:110]}")
    print(f"候选目录：{d}")
    return 0


def square(im, size=480):
    from PIL import Image
    im = im.convert("RGB")
    w, h = im.size
    s = max(w, h)
    canvas = Image.new("RGB", (s, s), (255, 255, 255))
    canvas.paste(im, ((s - w) // 2, (s - h) // 2))
    return canvas.resize((size, size), Image.LANCZOS)


def cmd_pick(args: list[str]) -> int:
    from PIL import Image
    pid, n = args[0], int(args[1])
    crop = [float(x) for x in args[args.index("--crop") + 1].split(",")] if "--crop" in args else None
    d = CAND / pid
    src = json.loads((d / "sources.json").read_text(encoding="utf-8"))
    meta = next(x for x in src if x["n"] == n)
    IMG.mkdir(parents=True, exist_ok=True)
    out = IMG / f"{pid}.jpg"
    im = Image.open(d / f"{n}.jpg")
    if crop:
        w, h = im.size
        im = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
    square(im).save(out, quality=85)
    cat_p = SKILL / "experience" / "hardware" / "catalog.json"
    cat = json.loads(cat_p.read_text(encoding="utf-8"))
    for p in cat:
        if p["id"] == pid:
            p["image"] = f"images/{pid}.jpg"
            p["image_source"] = meta["url"]
            break
    else:
        print(f"注意：catalog.json 里没有 {pid}，图片已保存但未登记")
    cat_p.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已保存 {out}")
    return 0


def cmd_clean(_a) -> int:
    shutil.rmtree(CAND, ignore_errors=True)
    print("候选已清理")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit({"search": cmd_search, "pick": cmd_pick, "clean": cmd_clean}[sys.argv[1]](sys.argv[2:]))
