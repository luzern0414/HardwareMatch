"""硬件经验库：搜过的硬件、价格证据、参数、匹配关系、搜索词效果。先查库，查不到或过期再用 LuzCrawl。

用法：
  py -X utf8 scripts/hw_experience.py search "<关键词>" [--category 门禁通行] [--subsystem 人流监控]
  py -X utf8 scripts/hw_experience.py show <产品id>
  py -X utf8 scripts/hw_experience.py compat "<产品id或关键词>"          # 查与它相关的匹配规则
  py -X utf8 scripts/hw_experience.py queries "<关键词>" [--platform 1688] # 查以前搜过的词、效果、噪声
  py -X utf8 scripts/hw_experience.py suppliers "<品类或品牌>"              # 查采购渠道：官网、官方商城、1688、厂家直采、政采
  py -X utf8 scripts/hw_experience.py add <file.json>                      # 合并新条目（products / compat / queries / suppliers）
  py -X utf8 scripts/hw_experience.py check                                # 校验结构、标出超过 180 天的价格
  py -X utf8 scripts/hw_experience.py stats

数据文件（只通过本脚本修改）：
  experience/hardware/catalog.json        产品：参数、接口、协议、功耗、价格证据、结论
  experience/hardware/compatibility.json  两类设备之间能否直接相连、怎么连、注意什么
  experience/hardware/queries.json        搜索词记录：平台、日期、是否有用、噪声、更好的写法
  experience/hardware/suppliers.json      渠道：厂商官网、官方商城、批发、厂家直采/方案商、政府采购；怎么搜、能拿到什么、访问状态
add 的输入 JSON：{"products":[...], "compat":[...], "queries":[...], "suppliers":[...]}。
替换而不是追加：产品按 id 或“品牌 + 型号”合并；同一链接的价格以新样本替换旧样本，每款只留最近 5 个价格样本、10 个来源；
匹配规则按两端设备（不分先后）合并；搜索记录按“平台 + 搜索词”合并；渠道按 id 合并。各文件有上限，超出时 add 自动删掉最旧的条目，
check 对重复、超量和超过上限报错。教训写在 lessons.md：同一主题改写原条，不追加第二条。
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "experience" / "hardware"
FILES = {"products": "catalog.json", "compat": "compatibility.json", "queries": "queries.json", "suppliers": "suppliers.json"}
STALE_DAYS = 180
VERDICTS = ("首选", "可用", "备选", "不推荐")
PRICE_KEEP = 5
SOURCE_KEEP = 10
CAPS = {"products": 300, "compat": 200, "queries": 300, "suppliers": 100}
LESSON_CAP = 120
LESSONS = "lessons.md"


def norm(text) -> str:
    """Case, spaces and punctuation removed, for duplicate detection."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKC", str(text or "")).lower()
                   if not c.isspace() and unicodedata.category(c)[0] not in "PS")


def product_sig(p: dict) -> tuple:
    return (norm(p.get("brand")), norm(p.get("model")))


def compat_sig(c: dict) -> tuple:
    return tuple(sorted((norm(c.get("a")), norm(c.get("b")))))


def query_sig(q: dict) -> tuple:
    return (norm(q.get("platform")), norm(q.get("query")))


def trim_prices(prices: list[dict]) -> list[dict]:
    """One sample per URL (the newest wins), newest first, at most PRICE_KEEP."""
    by_url: dict[str, dict] = {}
    for pr in prices:
        key = pr.get("url") or json.dumps(pr, ensure_ascii=False, sort_keys=True)
        if key not in by_url or str(pr.get("date", "")) >= str(by_url[key].get("date", "")):
            by_url[key] = pr
    return sorted(by_url.values(), key=lambda x: str(x.get("date", "")), reverse=True)[:PRICE_KEEP]


def lesson_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("- ")]


# Individuals' contacts (mobile numbers, WeChat IDs, named contact persons) stay on this machine in
# experience/contacts.local.json, which git ignores; company hotlines, websites and stores stay public.
LOCAL_CONTACTS = "contacts.local.json"
PERSONAL_KEYS = ("wechat", "contact_person")
MOBILE = re.compile(r"^\+?(?:86)?1[3-9]\d{9}$")


def _personal(item: dict) -> dict:
    out = {k: item[k] for k in PERSONAL_KEYS if item.get(k)}
    if item.get("phone") and MOBILE.match(str(item["phone"]).replace("-", "").replace(" ", "")):
        out["phone"] = item["phone"]
        if item.get("phone_source"):
            out["phone_source"] = item["phone_source"]
    return out


def load(kind: str) -> list:
    p = ROOT / FILES[kind]
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    local = ROOT / LOCAL_CONTACTS
    if kind == "suppliers" and local.exists():
        extra = json.loads(local.read_text(encoding="utf-8"))
        data = [{**x, **extra.get(x.get("id"), {})} for x in data]
    return data


def save(kind: str, data: list) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    if kind == "suppliers":
        local = ROOT / LOCAL_CONTACTS
        extra = json.loads(local.read_text(encoding="utf-8")) if local.exists() else {}
        public = []
        for x in data:
            personal = _personal(x)
            if personal:
                extra[x["id"]] = {**extra.get(x["id"], {}), **personal}
            public.append({k: v for k, v in x.items() if k not in personal})
        if extra:
            local.write_text(json.dumps(extra, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        data = public
    (ROOT / FILES[kind]).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def flat(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).lower()


def fmt_product(p: dict, full: bool = False) -> str:
    prices = p.get("prices", [])
    pr = "、".join(f"{x.get('cny')}" for x in prices if x.get("cny") is not None) or "无"
    line = f"[{p['id']}] {p.get('category','')}/{p.get('subsystem','')} {p.get('brand','')} {p.get('model','')}｜{p.get('verdict','')}｜价格样本：{pr}"
    if not full:
        s = p.get("specs", {})
        brief = "；".join(f"{k}:{v}" for k, v in list(s.items())[:4])
        return line + (f"\n    {brief}" if brief else "")
    return line + "\n" + json.dumps(p, ensure_ascii=False, indent=2)


def cmd_search(args: list[str]) -> int:
    text, cat, sub = "", None, None
    i = 0
    while i < len(args):
        if args[i] == "--category":
            cat = args[i + 1]; i += 2
        elif args[i] == "--subsystem":
            sub = args[i + 1]; i += 2
        else:
            text += " " + args[i]; i += 1
    words = [w.lower() for w in text.split() if w]
    hits = []
    for p in load("products"):
        if cat and p.get("category") != cat:
            continue
        if sub and sub not in (p.get("subsystem") or ""):
            continue
        blob = flat(p)
        if all(w in blob for w in words):
            hits.append(p)
    order = {v: i for i, v in enumerate(VERDICTS)}
    hits.sort(key=lambda p: order.get(p.get("verdict"), 9))
    for p in hits:
        print(fmt_product(p))
    print(f"共 {len(hits)} 条")
    return 0


def cmd_show(args: list[str]) -> int:
    for p in load("products"):
        if p["id"] == args[0]:
            print(fmt_product(p, full=True))
            return 0
    print("未找到")
    return 1


def cmd_compat(args: list[str]) -> int:
    key = " ".join(args).lower()
    n = 0
    for c in load("compat"):
        if key in flat(c):
            n += 1
            ok = {True: "可直连", False: "不可直连"}.get(c.get("ok"), "有条件")
            print(f"- {c['a']} ⇄ {c['b']}：{ok}；{c.get('via','')}；{c.get('note','')}")
    print(f"共 {n} 条")
    return 0


def cmd_queries(args: list[str]) -> int:
    plat = None
    if "--platform" in args:
        j = args.index("--platform"); plat = args[j + 1]; args = args[:j] + args[j + 2:]
    key = " ".join(args).lower()
    for q in load("queries"):
        if plat and q.get("platform") != plat:
            continue
        if key in flat(q):
            mark = "有用" if q.get("useful") else "无用"
            print(f"- [{q.get('platform')}] {q['query']}｜{mark}｜{q.get('date','')}｜{q.get('note','')}")
    return 0


def cmd_suppliers(args: list[str]) -> int:
    key = " ".join(args).lower()
    n = 0
    for x in load("suppliers"):
        if key in flat(x):
            n += 1
            print(f"[{x['id']}] {x.get('name')}｜{x.get('channel')}｜{x.get('url')}｜访问：{x.get('access','')}")
            print(f"    品类：{'、'.join(x.get('categories', []))}｜采购方式：{x.get('procurement','')}")
            contact = "；".join(f"{k}：{x[k]}" for k, k2 in (("phone", 0), ("wechat", 0), ("buy_url", 0)) if x.get(k))
            if contact:
                print(f"    联系：{contact}（来源：{x.get('phone_source', x.get('url'))}）")
            if x.get("how"):
                print(f"    怎么用：{x['how']}")
    print(f"共 {n} 条")
    return 0


def merge_product(old: dict, new: dict) -> dict:
    """New facts replace old ones; prices keep the newest sample per URL and the latest PRICE_KEEP."""
    out = dict(old)
    for k, v in new.items():
        if k == "id" and old.get("id"):
            continue
        if k == "prices":
            out["prices"] = trim_prices(list(v) + out.get("prices", []))
        elif k == "sources":
            merged = list(dict.fromkeys(list(v) + out.get("sources", [])))
            out["sources"] = merged[:SOURCE_KEEP]
        elif k == "specs":
            out["specs"] = {**out.get("specs", {}), **v}
        else:
            out[k] = v
    return out


def merge_items(kind: str, cur: list[dict], items: list[dict]) -> list[dict]:
    """Upsert items into cur; one entry per id or natural key, newest data wins, cap enforced."""
    def sigs(x: dict) -> list:
        if kind == "products":
            return [("id", x.get("id")), ("model", product_sig(x))] if norm(x.get("model")) else [("id", x.get("id"))]
        if kind == "suppliers":
            return [("id", x.get("id"))]
        return [compat_sig(x)] if kind == "compat" else [query_sig(x)]

    for it in items:
        target = next((i for i, x in enumerate(cur) if set(map(str, sigs(x))) & set(map(str, sigs(it)))), None)
        if target is None:
            if kind == "products" and it.get("prices"):
                it = {**it, "prices": trim_prices(it["prices"])}
            cur.append(it)
        elif kind in ("products", "suppliers"):
            cur[target] = merge_product(cur[target], it)
        else:
            cur[target] = {**cur[target], **it}
    over = len(cur) - CAPS[kind]
    if over > 0:
        # Oldest first: queries by date, others by their last check or price date; ties keep list order.
        def age_key(x: dict) -> str:
            dates = [x.get("date"), x.get("checked")] + [p.get("date") for p in x.get("prices", [])]
            return max((d for d in dates if d), default="")
        for x in sorted(cur, key=age_key)[:over]:
            cur.remove(x)
            print(f"  已删除最旧的 {kind} 条目：{x.get('id') or x.get('query') or x.get('a')}")
    return cur


def cmd_add(args: list[str]) -> int:
    data = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    for kind in ("products", "suppliers", "compat", "queries"):
        items = data.get(kind, [])
        if not items:
            continue
        cur = merge_items(kind, load(kind), items)
        save(kind, cur)
        print(f"{kind}: 现有 {len(cur)} 条")
    return cmd_check([])


def cmd_check(_args: list[str]) -> int:
    errs, warns = [], []
    today = dt.date.today()
    ids = set()
    for p in load("products"):
        for k in ("id", "category", "subsystem", "brand", "model", "verdict", "specs"):
            if not p.get(k):
                errs.append(f"{p.get('id')} 缺 {k}")
        if p.get("id") in ids:
            errs.append(f"重复 id {p['id']}")
        ids.add(p.get("id"))
        if p.get("verdict") not in VERDICTS:
            errs.append(f"{p.get('id')} verdict 必须是 {VERDICTS}")
        for pr in p.get("prices", []):
            if not pr.get("url") or not pr.get("date"):
                errs.append(f"{p.get('id')} 价格缺 url 或 date")
                continue
            age = (today - dt.date.fromisoformat(pr["date"])).days
            if age > STALE_DAYS:
                warns.append(f"{p['id']} 价格 {pr['date']} 已超过 {STALE_DAYS} 天，使用前重新核价")
    for c in load("compat"):
        if not c.get("a") or not c.get("b") or "ok" not in c:
            errs.append(f"匹配规则缺字段：{c}")
    for x in load("suppliers"):
        for k in ("id", "name", "channel", "url", "categories", "procurement", "access"):
            if not x.get(k):
                errs.append(f"渠道 {x.get('id')} 缺 {k}")
    for q in load("queries"):
        if not q.get("platform") or not q.get("query") or "useful" not in q:
            errs.append(f"搜索记录缺字段：{q}")
    errs.extend(duplicate_errors())
    for w in lesson_warnings():
        warns.append(w)
    for w in warns:
        print("  WARN ", w)
    for e in errs:
        print("  ERROR", e)
    print(f"经验库检查：{len(errs)} 错误，{len(warns)} 警告")
    return 1 if errs else 0


def duplicate_errors() -> list[str]:
    """One entry per topic: duplicates and overflow are errors, never silently kept."""
    errs = []
    checks = {
        "products": (product_sig, "产品（品牌 + 型号）"),
        "compat": (compat_sig, "匹配规则（两端设备）"),
        "queries": (query_sig, "搜索记录（平台 + 搜索词）"),
        "suppliers": (lambda x: norm(x.get("url")), "渠道（网址）"),
    }
    for kind, (sig, label) in checks.items():
        items = load(kind)
        seen: dict = {}
        for x in items:
            s = sig(x)
            if kind == "products" and not s[1]:
                continue
            if s in seen:
                errs.append(f"重复的{label}：{x.get('id') or x.get('query') or x.get('a')} 与 {seen[s]}，应合并为一条")
            seen.setdefault(s, x.get("id") or x.get("query") or x.get("a"))
        if len(items) > CAPS[kind]:
            errs.append(f"{kind} 共 {len(items)} 条，超过上限 {CAPS[kind]}")
    for p in load("products"):
        if len(p.get("prices", [])) > PRICE_KEEP:
            errs.append(f"{p.get('id')} 有 {len(p['prices'])} 个价格样本，只保留最近 {PRICE_KEEP} 个")
        urls = [x.get("url") for x in p.get("prices", []) if x.get("url")]
        if len(urls) != len(set(urls)):
            errs.append(f"{p.get('id')} 同一链接有多个价格样本，只留最新一个")
        if len(p.get("sources", [])) > SOURCE_KEEP:
            errs.append(f"{p.get('id')} 来源超过 {SOURCE_KEEP} 个")
    return errs


def lesson_warnings() -> list[str]:
    path = ROOT / LESSONS
    if not path.exists():
        return []
    lines = lesson_lines(path.read_text(encoding="utf-8"))
    out, seen = [], {}
    for line in lines:
        body = re.sub(r"^- \d{4}-\d{2}-\d{2}\s*", "", line)
        key = norm(body)
        if key in seen:
            out.append(f"lessons.md 有重复教训：{body[:30]}…，改写原条而不是追加")
        seen[key] = True
    if len(lines) > LESSON_CAP:
        out.append(f"lessons.md 有 {len(lines)} 条，超过 {LESSON_CAP}，合并同主题或删掉过时条目")
    return out


def cmd_stats(_args: list[str]) -> int:
    ps = load("products")
    by = {}
    for p in ps:
        by.setdefault(p.get("subsystem", ""), []).append(p)
    for k, v in by.items():
        print(f"{k}：{len(v)} 款（首选 {sum(1 for p in v if p.get('verdict') == '首选')}）")
    print(f"产品 {len(ps)}，渠道 {len(load('suppliers'))}，匹配规则 {len(load('compat'))}，搜索记录 {len(load('queries'))}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cmd, args = sys.argv[1], sys.argv[2:]
    return {"search": cmd_search, "show": cmd_show, "compat": cmd_compat, "queries": cmd_queries,
            "suppliers": cmd_suppliers, "add": cmd_add, "check": cmd_check, "stats": cmd_stats}.get(cmd, lambda a: (print(__doc__), 2)[1])(args)


if __name__ == "__main__":
    sys.exit(main())
