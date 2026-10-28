"""把 LuzCrawl 任务目录整理成硬件选型可用的调研摘要。

用法：
  py -X utf8 scripts/hw_crawl_digest.py <TASK_FOLDER> [--out digest.json] [--md digest.md]
  py -X utf8 scripts/hw_crawl_digest.py <TASK_FOLDER> --text <关键词>   # 打印标题含关键词的已采集正文

输出两类记录：
  candidates  电商/搜索候选（1688 等），拆出 标题 / 价格 / 销量 / 供应商 / 链接，仅算候选
  sources     已打开并读到正文的页面（content.json status=captured|partial 且有正文）
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

PRICE_RE = re.compile(r"¥\s*\n?\s*([0-9]+)\s*\n?\s*(\.[0-9]+)?")
SALES_RE = re.compile(r"(全网[0-9万\+]+件|[0-9万\+]+件)")
SELLER_RE = re.compile(r"(.+?(?:有限公司|经营部|商行|厂|店|工作室|科技|电子))\s*$")


def parse_candidate(item: dict, query: str) -> dict | None:
    text = item.get("text") or ""
    url = item.get("url") or ""
    if not text or not url:
        return None
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    title = lines[0] if lines else ""
    m = PRICE_RE.search(text)
    price = None
    if m:
        try:
            price = float(m.group(1) + (m.group(2) or ""))
        except ValueError:
            price = None
    sales = SALES_RE.search(text)
    seller = ""
    for ln in reversed(lines):
        if SELLER_RE.match(ln):
            seller = ln
            break
    offer = re.search(r"offer/(\d+)\.html", url)
    clean_url = f"https://detail.1688.com/offer/{offer.group(1)}.html" if offer else url.split("?")[0]
    return {
        "query": query,
        "title": title,
        "price_cny": price,
        "sales": sales.group(1) if sales else "",
        "seller": seller,
        "url": clean_url,
        "status": "candidate",
    }


def load_json(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def collect(task: Path) -> dict:
    candidates, sources, failures = [], [], []
    seen = set()
    for f in sorted(glob.glob(str(task / "search-*.json"))):
        d = load_json(f)
        if not isinstance(d, dict):
            continue
        query = d.get("query") or d.get("keyword") or ""
        platform = d.get("platform") or ""
        items = d.get("candidates") or d.get("results") or d.get("items") or []
        for it in items:
            if not isinstance(it, dict):
                continue
            c = parse_candidate(it, query)
            if c and c["url"] not in seen and ("1688" in c["url"] or platform == "1688"):
                seen.add(c["url"])
                c["platform"] = platform or "1688"
                candidates.append(c)
    for f in sorted(glob.glob(str(task / "raw" / "*" / "raw" / "content.json"))):
        d = load_json(f)
        if not isinstance(d, dict):
            continue
        text = d.get("text") or ""
        rec = {
            "title": d.get("title") or "",
            "url": d.get("resolved_url") or d.get("canonical_url") or d.get("requested_url") or "",
            "platform": d.get("platform") or "",
            "status": d.get("status") or "",
            "chars": len(text),
            "folder": str(Path(f).parent.parent),
        }
        if rec["status"] in ("captured", "partial") and len(text) > 300:
            sources.append(rec)
        else:
            failures.append(rec)
    return {"task": str(task), "candidates": candidates, "sources": sources, "failures": failures}


def to_md(d: dict) -> str:
    out = [f"# 调研摘要", "", f"## 电商候选（{len(d['candidates'])}）", "",
           "| 查询 | 标题 | 价格（元） | 销量 | 供应商 | 链接 |", "|---|---|---|---|---|---|"]
    for c in d["candidates"]:
        out.append(f"| {c['query']} | {c['title'][:40]} | {c['price_cny'] or ''} | {c['sales']} | {c['seller']} | {c['url']} |")
    out += ["", f"## 已读正文（{len(d['sources'])}）", "", "| 标题 | 平台 | 字数 | 链接 |", "|---|---|---|---|"]
    for s in d["sources"]:
        out.append(f"| {s['title'][:50]} | {s['platform']} | {s['chars']} | {s['url'][:120]} |")
    out += ["", f"## 失败或无正文（{len(d['failures'])}）", ""]
    for s in d["failures"]:
        out.append(f"- {s['status']} {s['title'][:50]} {s['url'][:100]}")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--text", help="打印标题或链接包含该关键词的已采集正文")
    ap.add_argument("--max", type=int, default=6000, help="--text 每篇最多打印字数")
    a = ap.parse_args()
    task = Path(a.task)
    d = collect(task)
    if a.text:
        for f in sorted(glob.glob(str(task / "raw" / "*" / "raw" / "content.json"))):
            c = load_json(f) or {}
            if a.text in (c.get("title") or "") or a.text in f:
                print("=" * 8, c.get("title"), c.get("resolved_url") or c.get("requested_url"))
                print((c.get("text") or "")[: a.max])
        return 0
    if a.out:
        Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.md:
        Path(a.md).write_text(to_md(d), encoding="utf-8")
    print(json.dumps({"candidates": len(d["candidates"]), "sources": len(d["sources"]),
                      "failures": len(d["failures"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
