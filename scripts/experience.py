#!/usr/bin/env python3
"""Luz System experience library: search before research, reuse fresh evidence, harvest after delivery.

experience/sources.json   verified frontend references (LuzCrawl captures and official specification pages)
experience/patterns.json  reusable knowledge: 功能, 交互流程, 组件, 色彩, 字阶, 前端规则, 设计理念, 调研经验
experience/notes.json     what every call learned: preference / lesson / fact, one entry per key (upsert, bounded)
experience/catalog.md     readable catalog generated from the three files; read it before starting a new project

Notes (same file, fields and commands in Luz-System, Luz-Design, Luz-Dev and Luz-Writing):
  experience.py note --kind preference|lesson|fact --key K --text "…" [--why "…"]
  experience.py list [--kind K]      experience.py search <words> [--kind K]
  experience.py prune                experience.py check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

from new_session import OUTPUT_ROOT
from validate_session import ARCHITECTURE_PATH, final_html, parse_research, strip_html_comments, work_dir

SKILL_ROOT = Path(__file__).resolve().parents[1]
EXP = SKILL_ROOT / "experience"
SOURCES = EXP / "sources.json"
PATTERNS = EXP / "patterns.json"
CATALOG = EXP / "catalog.md"
NOTES = EXP / "notes.json"
KINDS = ["功能", "交互流程", "组件", "色彩", "字阶", "前端规则", "设计理念", "调研经验"]
CATEGORIES = ["页面结构", "交互流程", "组件状态", "前端规则"]
STALE_DAYS = 180
PATTERN_CAP = 300
SOURCE_CAP = 200


def load(path: Path, key: str) -> dict:
    if not path.is_file():
        return {"schema_version": "1.0", key: []}
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_id(items: list[dict], prefix: str) -> str:
    numbers = [int(i["id"].split("-")[1]) for i in items if re.fullmatch(prefix + r"-\d+", i.get("id", ""))]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def age_days(day: str | None) -> int | None:
    try:
        return (date.today() - date.fromisoformat(day)).days
    except (TypeError, ValueError):
        return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- search

def matches(entry: dict, args) -> bool:
    blob = json.dumps(entry, ensure_ascii=False)
    if args.kind and entry.get("kind") != args.kind and entry.get("category") != args.kind:
        return False
    if args.industry and not any(args.industry in x or x == "通用" for x in entry.get("industries", ["通用"])):
        return False
    if args.surface and not any(args.surface in x or x == "通用" for x in entry.get("surfaces", ["通用"])):
        return False
    return all(term in blob for term in args.words)


def cmd_search(args) -> int:
    """Notes first (filtered by a note kind), then patterns and sources (filtered by a pattern kind, industry or surface)."""
    note_kind = args.kind if args.kind in NOTE_KINDS else None
    notes = [] if (args.kind and not note_kind) or args.industry or args.surface else search_notes(load_notes(NOTES), args.words, note_kind)
    for n in notes:
        print(format_note(n))
    library = not note_kind
    patterns = [p for p in load(PATTERNS, "patterns")["patterns"] if library and matches(p, args)]
    sources = [s for s in load(SOURCES, "sources")["sources"] if library and matches(s, args)]
    for p in patterns:
        print(f"{p['id']} [{p['kind']}] {p['title']}  ({'、'.join(p.get('surfaces', []))} · {'、'.join(p.get('industries', []))})")
        print(f"    {p.get('summary', '')}")
    for s in sources:
        age = age_days(s.get("captured_at"))
        flag = "可复用" if s.get("snapshot") and age is not None and age <= STALE_DAYS else ("仅作知识" if not s.get("snapshot") else "已过期，需重新采集")
        print(f"{s['id']} [{s['category']}] {s['title']}  {s['url']}  {s.get('captured_at')} {flag}")
    print(f"共 {len(notes)} 条沉淀，{len(patterns)} 条模式，{len(sources)} 条来源")
    return 0


# ---------------------------------------------------------------- notes store (identical in Luz-System, Luz-Design, Luz-Dev, Luz-Writing)
# experience/notes.json = {"schema_version": "1.0", "caps": {...}, "notes": [{key, kind, text, why?, uses, first_seen,
# last_confirmed, previous?}]}. A note on an existing key replaces its text (one `previous` kept); the same statement
# under another key confirms that note; over a cap the fewest uses, then the oldest confirmation, are dropped.
NOTES_SCHEMA_VERSION = "1.0"
NOTE_KINDS = {"preference": "偏好", "lesson": "教训", "fact": "有效信息"}
NOTE_CAPS = {"preference": 60, "lesson": 120, "fact": 120}
NOTE_FIELDS = ("key", "kind", "text", "why", "uses", "first_seen", "last_confirmed", "previous")
NOTE_REQUIRED = ("key", "kind", "text", "uses", "first_seen", "last_confirmed")
NOTE_STALE_DAYS = 180
NOTE_TEXT_MAX = 400
NOTE_KEY_RE = re.compile(r"[\w一-鿿][\w一-鿿-]{0,47}")
NOTE_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
NOTE_PRIVATE_RES = (
    (re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"), "phone number"),
    (re.compile(r"[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?!(?:png|jpe?g|gif|svg|webp)\b)[A-Za-z]{2,}\b"), "email address"),
    (re.compile(r"(?i)\bwxid_\w+|(?:微信号?|wechat(?:\s*id)?|weixin|vx)\s*[:：]\s*[A-Za-z][\w-]{5,}"), "WeChat ID"),
    (re.compile(r"(?i)\b[A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]|(?<![\w.])/(?:Users|home)/\w"), "user-home path"),
    (re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\s*[:=：]\s*\S+"
                r"|(?:密码|口令|密钥)\s*[:=：]\s*\S+|\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,})"), "credential"),
)


def note_today() -> str:
    return date.today().isoformat()


def note_normalize(text: str) -> str:
    """Comparison form of a statement: NFKC, lower case, without whitespace, punctuation or symbols."""
    return "".join(c for c in unicodedata.normalize("NFKC", str(text or "")).lower()
                   if not c.isspace() and unicodedata.category(c)[0] not in "PS")


def note_private_hits(text: str) -> list[str]:
    return [label for pattern, label in NOTE_PRIVATE_RES if pattern.search(text or "")]


def new_notes_doc() -> dict:
    return {"schema_version": NOTES_SCHEMA_VERSION, "caps": dict(NOTE_CAPS), "notes": []}


def load_notes(path: Path) -> dict:
    if not path.is_file():
        return new_notes_doc()
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("notes"), list):
        raise ValueError(f"{path.name} must be an object with a notes array")
    return doc


def save_notes(path: Path, doc: dict) -> None:
    """Write atomically, notes ordered by kind then key, fields in the shared order."""
    order = list(NOTE_KINDS)
    notes = sorted(doc["notes"], key=lambda n: (order.index(n["kind"]) if n.get("kind") in order else len(order), str(n.get("key", ""))))
    doc.update(schema_version=NOTES_SCHEMA_VERSION, caps=dict(NOTE_CAPS))
    doc["notes"] = [{**{f: n[f] for f in NOTE_FIELDS if n.get(f) not in (None, "")},
                     **{k: v for k, v in n.items() if k not in NOTE_FIELDS}} for n in notes]
    payload = {"schema_version": doc["schema_version"], "caps": doc["caps"], "notes": doc["notes"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def prune_notes(doc: dict, keep: dict | None = None) -> list[dict]:
    """Enforce the caps: drop the fewest uses first, then the oldest confirmation; never the note just written."""
    removed: list[dict] = []
    for kind, cap in NOTE_CAPS.items():
        group = [n for n in doc["notes"] if n.get("kind") == kind]
        overflow = len(group) - cap
        if overflow <= 0:
            continue
        ranked = sorted((n for n in group if n is not keep), key=lambda n: (int(n.get("uses") or 0), str(n.get("last_confirmed", ""))))
        removed += ranked[:overflow]
    gone = {id(n) for n in removed}
    doc["notes"] = [n for n in doc["notes"] if id(n) not in gone]
    return removed


def upsert_note(doc: dict, kind: str, key: str, text: str, why: str = "", on: str | None = None,
                privacy: bool = True) -> tuple[str, dict, list[dict]]:
    """Insert or replace one note by key. Returns (added|replaced|confirmed, note, pruned notes); raises ValueError."""
    if kind not in NOTE_KINDS:
        raise ValueError(f"--kind must be one of {', '.join(NOTE_KINDS)}")
    key = (key or "").strip()
    if not NOTE_KEY_RE.fullmatch(key):
        raise ValueError("--key must be a short slug: letters, digits, Chinese, - or _, at most 48 characters, no spaces")
    text, why = " ".join((text or "").split()), " ".join((why or "").split())
    if not text:
        raise ValueError("--text is empty")
    if len(text) > NOTE_TEXT_MAX:
        raise ValueError(f"--text is longer than {NOTE_TEXT_MAX} characters; record the general principle, not task details")
    hits = note_private_hits(f"{text} {why}") if privacy else []
    if hits:
        raise ValueError(f"notes are public; remove the {', '.join(hits)} and write the general principle")
    on = on or note_today()
    notes = doc["notes"]
    norm = note_normalize(text)
    entry = next((n for n in notes if n.get("key") == key), None)
    twin = next((n for n in notes if n is not entry and note_normalize(n.get("text", "")) == norm), None)
    if entry is None and twin is not None:
        entry, action = twin, "confirmed"
        if why and not entry.get("why"):
            entry["why"] = why
    elif entry is None:
        entry, action = {"key": key, "kind": kind, "text": text, "why": why, "uses": 0, "first_seen": on}, "added"
        notes.append(entry)
    elif twin is not None:
        raise ValueError(f"the same statement is stored under {twin['key']}; update that key instead")
    else:
        action = "confirmed"
        if note_normalize(entry.get("text", "")) != norm:
            entry["previous"] = {"text": entry.get("text", ""), "replaced_at": on}
            action = "replaced"
        entry.update(kind=kind, text=text)
        if why:
            entry["why"] = why
    entry["uses"] = int(entry.get("uses") or 0) + 1
    entry["last_confirmed"] = on
    return action, entry, prune_notes(doc, keep=entry)


def stale_notes(doc: dict, now: date | None = None) -> list[dict]:
    """Notes not confirmed for NOTE_STALE_DAYS days: listed by prune and check, first to go when a cap is hit."""
    now = now or date.today()
    out = []
    for n in doc["notes"]:
        try:
            age = (now - date.fromisoformat(str(n.get("last_confirmed")))).days
        except ValueError:
            age = NOTE_STALE_DAYS + 1
        if age > NOTE_STALE_DAYS:
            out.append(n)
    return out


def check_notes(doc: dict, privacy: bool = True) -> list[str]:
    """Shape, fields, duplicate keys, duplicate statements, caps and private data."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["notes.json must be a JSON object"]
    if sorted(doc) != ["caps", "notes", "schema_version"]:
        errors.append(f"notes.json top-level fields must be schema_version, caps, notes (found {', '.join(sorted(doc))})")
    if doc.get("schema_version") != NOTES_SCHEMA_VERSION:
        errors.append(f"notes.json schema_version must be {NOTES_SCHEMA_VERSION}")
    if doc.get("caps") != NOTE_CAPS:
        errors.append(f"notes.json caps must be {json.dumps(NOTE_CAPS)}")
    notes = doc.get("notes")
    if not isinstance(notes, list):
        return errors + ["notes.json notes must be an array"]
    keys: dict[str, int] = {}
    texts: dict[str, str] = {}
    for n in notes:
        key = str(n.get("key", "")) if isinstance(n, dict) else ""
        if not isinstance(n, dict):
            errors.append("note is not an object")
            continue
        for field in NOTE_REQUIRED:
            if n.get(field) in (None, ""):
                errors.append(f"note {key or '?'} missing {field}")
        extra = sorted(set(n) - set(NOTE_FIELDS))
        if extra:
            errors.append(f"note {key} has unknown fields {', '.join(extra)}")
        if n.get("kind") not in NOTE_KINDS:
            errors.append(f"note {key} kind must be one of {', '.join(NOTE_KINDS)}")
        if key and not NOTE_KEY_RE.fullmatch(key):
            errors.append(f"note key is not a short slug: {key}")
        if not isinstance(n.get("uses"), int) or isinstance(n.get("uses"), bool) or n.get("uses", 0) < 1:
            errors.append(f"note {key} uses must be a positive integer")
        for field in ("first_seen", "last_confirmed"):
            if n.get(field) and not NOTE_DATE_RE.fullmatch(str(n[field])):
                errors.append(f"note {key} {field} must be YYYY-MM-DD")
        previous = n.get("previous")
        if previous is not None and (not isinstance(previous, dict) or sorted(previous) != ["replaced_at", "text"]
                                     or not NOTE_DATE_RE.fullmatch(str(previous.get("replaced_at")))):
            errors.append(f"note {key} previous must be {{text, replaced_at: YYYY-MM-DD}}")
        if len(str(n.get("text", ""))) > NOTE_TEXT_MAX:
            errors.append(f"note {key} text is longer than {NOTE_TEXT_MAX} characters")
        keys[key] = keys.get(key, 0) + 1
        norm = note_normalize(n.get("text", ""))
        if norm and norm in texts and texts[norm] != key:
            errors.append(f"note {key} repeats the statement of {texts[norm]}; keep one key")
        texts.setdefault(norm, key)
        if privacy:
            hits = note_private_hits(f"{n.get('text', '')} {n.get('why', '')} {(previous or {}).get('text', '') if isinstance(previous, dict) else ''}")
            if hits:
                errors.append(f"note {key} contains a {', '.join(hits)}; notes are public")
    errors += [f"duplicate note key {k} ({c} entries); a key is replaced, never repeated" for k, c in keys.items() if c > 1]
    for kind, cap in NOTE_CAPS.items():
        count = sum(1 for n in notes if isinstance(n, dict) and n.get("kind") == kind)
        if count > cap:
            errors.append(f"{count} {kind} notes exceed the cap {cap}; run prune")
    return errors


def search_notes(doc: dict, words: list[str], kind: str | None = None) -> list[dict]:
    terms = [t for t in (note_normalize(w) for w in words or []) if t]
    return [n for n in doc["notes"] if (not kind or n.get("kind") == kind)
            and all(t in note_normalize(f"{n.get('key', '')} {n.get('text', '')} {n.get('why', '')}") for t in terms)]


def format_note(n: dict) -> str:
    why = f"（{n['why']}）" if n.get("why") else ""
    return f"[{NOTE_KINDS.get(n.get('kind'), n.get('kind'))}] {n.get('key')}：{n.get('text')}{why}  （{n.get('uses', 1)} 次，最近 {n.get('last_confirmed')}）"


def note_counts(doc: dict) -> str:
    return "，".join(f"{NOTE_KINDS[k]} {sum(1 for n in doc['notes'] if n.get('kind') == k)}/{cap}" for k, cap in NOTE_CAPS.items())
# ---------------------------------------------------------------- end of notes store


def note(kind: str, key: str, text: str, why: str = "") -> tuple[str, dict]:
    """Upsert one note into experience/notes.json, re-render the catalog; returns (action, note)."""
    doc = load_notes(NOTES)
    try:
        action, entry, removed = upsert_note(doc, kind, key, text, why)
    except ValueError as exc:
        raise SystemExit(f"FAIL: {exc}")
    save_notes(NOTES, doc)
    render()
    for n in removed:
        print(f"pruned {n['kind']} {n['key']} (cap {NOTE_CAPS[n['kind']]})")
    return action, entry


def cmd_note(args) -> int:
    action, entry = note(args.kind, args.key, args.text, args.why or "")
    print(f"{action} {entry['kind']} {entry['key']}：{entry['text']}")
    return 0


def cmd_list(args) -> int:
    notes = [n for n in load_notes(NOTES)["notes"] if not args.kind or n.get("kind") == args.kind]
    for n in notes:
        print(format_note(n))
    print(f"共 {len(notes)} 条")
    return 0


def prune_patterns(patterns: list[dict]) -> list[dict]:
    if len(patterns) <= PATTERN_CAP:
        return []
    ranked = sorted(patterns, key=lambda p: (p.get("uses", 1), p.get("last_used", "")))
    removed = ranked[:len(patterns) - PATTERN_CAP]
    for p in removed:
        patterns.remove(p)
    return removed


def cmd_prune(_args) -> int:
    doc = load_notes(NOTES)
    removed = prune_notes(doc)
    save_notes(NOTES, doc)
    pdoc = load(PATTERNS, "patterns")
    removed_patterns = prune_patterns(pdoc["patterns"])
    save(PATTERNS, pdoc)
    render()
    for n in removed:
        print(f"pruned {n['kind']} {n['key']}")
    for p in removed_patterns:
        print(f"pruned pattern {p['id']} {p['title']}")
    stale = stale_notes(doc)
    if stale:
        print(f"not confirmed for {NOTE_STALE_DAYS} days (confirm or replace):", ", ".join(n["key"] for n in stale))
    print(f"pruned {len(removed)} notes, {len(removed_patterns)} patterns")
    return 0


# ---------------------------------------------------------------- reuse

def cmd_reuse(args) -> int:
    session = Path(args.session).resolve()
    research = work_dir(session) / "01-system" / "02-research.md"
    snaps = work_dir(session) / "01-system" / "crawl-snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    text = research.read_text(encoding="utf-8") if research.is_file() else "# Research\n"
    existing = {r.get("url") for r in parse_research(research)} if research.is_file() else set()
    numbers = [int(x) for x in re.findall(r"^### REF-(\d+)", strip_html_comments(text), re.M)]
    sources = {s["id"]: s for s in load(SOURCES, "sources")["sources"]}
    blocks = []
    for sid in args.ids:
        s = sources.get(sid)
        if not s:
            raise SystemExit(f"FAIL: unknown source {sid}")
        if s["url"] in existing:
            print(f"skip {sid}: already in this session")
            continue
        snap = s.get("snapshot")
        if not snap:
            raise SystemExit(f"FAIL: {sid} has no snapshot; it is knowledge only and cannot count as session research")
        age = age_days(s.get("captured_at"))
        if age is None or age > STALE_DAYS:
            raise SystemExit(f"FAIL: {sid} was captured {s.get('captured_at')}; older than {STALE_DAYS} days, crawl it again")
        origin = OUTPUT_ROOT / snap["session"] / "raw" / snap["path"]
        if not origin.is_file() or sha256(origin) != snap["sha256"]:
            raise SystemExit(f"FAIL: {sid} snapshot is missing or changed: {origin}")
        number = max(numbers, default=0) + 1
        numbers.append(number)
        ref = f"REF-{number:03d}"
        target = snaps / f"{ref}.json"
        shutil.copyfile(origin, target)
        blocks.append("\n".join([
            f"### {ref}", f"- Source name: {s['title']}", f"- URL: {s['url']}", f"- Registrable domain: {s['domain']}",
            f"- Access date: {s['captured_at']}", f"- HTTP status: {s.get('http_status', 200)}", f"- Page title: {s.get('page_title', s['title'])}",
            f"- LuzCrawl task ID: {s['luzcrawl_task']}", f"- LuzCrawl status: {s.get('luzcrawl_status', '成功')}",
            f"- Evidence category: {s['category']}", f"- Visible evidence: {s['evidence']}",
            f"- Supported functions: {args.functions or s.get('supports', '待在架构中关联')}",
            f"- Business flow or module: {args.module or '全部模块'}", f"- Borrowable: {s['borrowable']}", f"- Not copyable: {s['not_copyable']}",
            f"- Snapshot path: 01-system/crawl-snapshots/{ref}.json", f"- Snapshot sha256: {sha256(target)}",
            f"- Reused from: {sid}（{snap['session']} {snap['ref']}）", ""]))
        print(f"reused {sid} as {ref}")
    if blocks:
        research.write_text(text.rstrip("\n") + "\n\n" + "\n".join(blocks), encoding="utf-8")
    return 0


# ---------------------------------------------------------------- harvest

def upsert_pattern(patterns: list[dict], entry: dict, session: str) -> None:
    for p in patterns:
        if p["kind"] == entry["kind"] and p["title"] == entry["title"]:
            p.update({k: v for k, v in entry.items() if k not in {"id", "sessions", "first_seen", "uses"}})
            if session not in p.setdefault("sessions", []):
                p["sessions"].append(session)
                p["uses"] = p.get("uses", 0) + 1
            p["last_used"] = date.today().isoformat()
            return
    entry.update({"id": next_id(patterns, "PAT"), "sessions": [session], "first_seen": date.today().isoformat(),
                  "last_used": date.today().isoformat(), "uses": 1})
    patterns.append(entry)


def contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        h = h.lstrip("#")
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        out = []
        for i in (0, 2, 4):
            v = int(h[i:i + 2], 16) / 255
            out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return round((x + 0.05) / (y + 0.05), 1)


def cmd_harvest(args) -> int:
    session = Path(args.session).resolve()
    name = session.name
    work = work_dir(session)
    industries = [x for x in args.industry.split(",") if x]
    sources_doc = load(SOURCES, "sources")
    sources = sources_doc["sources"]
    by_url = {s["url"]: s for s in sources}
    research = parse_research(work / "01-system" / "02-research.md")
    for r in research:
        if r.get("reused from"):
            continue
        url = r["url"]
        entry = by_url.get(url) or {"id": next_id(sources, "SRC")}
        entry.update({
            "url": url, "title": r.get("source name"), "page_title": r.get("page title"), "domain": r.get("registrable domain"),
            "category": r.get("evidence category"), "evidence": r.get("visible evidence"), "borrowable": r.get("borrowable"),
            "not_copyable": r.get("not copyable"), "supports": r.get("supported functions"),
            "surfaces": entry.get("surfaces") or (["后台"] if any(k in (r.get("source name") or "") for k in ("后台", "桌面")) else ["小程序"] if "小程序" in (r.get("source name") or "") else ["通用"]),
            "industries": sorted(set(entry.get("industries", ["通用"])) | {i for i in industries if i[:2] in (r.get("source name", "") + r.get("visible evidence", ""))}),
            "captured_at": r.get("access date"), "http_status": r.get("http status"), "luzcrawl_task": r.get("luzcrawl task id"),
            "luzcrawl_status": r.get("luzcrawl status"), "method": "LuzCrawl",
            "snapshot": {"session": name, "ref": r["id"], "path": r.get("snapshot path"), "sha256": r.get("snapshot sha256")},
        })
        if url not in by_url:
            sources.append(entry)
            by_url[url] = entry
    save(SOURCES, sources_doc)

    patterns_doc = load(PATTERNS, "patterns")
    patterns = patterns_doc["patterns"]
    arch = work / ARCHITECTURE_PATH
    if arch.is_file():
        html = arch.read_text(encoding="utf-8")
        rows = re.findall(r'<tr data-function-id="(F-\d+)" data-module="([^"]+)"[^>]*><td>[^<]*</td><td>[^<]*</td><td>([^<]*)</td><td>([^<]*)</td>', html)
        modules: dict[str, list[str]] = {}
        for _fid, module, end, fname in rows:
            modules.setdefault(module, []).append(f"{end}：{fname}")
        states = dict(re.findall(r'<tr data-state-id="S-\d+" data-module="([^"]+)"[^>]*><td>[^<]*</td><td>[^<]*</td><td>([^<]*)</td>', html))
        for module, items in modules.items():
            upsert_pattern(patterns, {"kind": "功能", "title": f"{'、'.join(industries)}·{module}", "industries": industries,
                                      "surfaces": sorted({i.split('：')[0] for i in items}), "summary": "；".join(items),
                                      "details": {"界面状态": states.get(module, "")}, "sources": []}, name)
        for main, exc in re.findall(r'<tr data-flow-id="FL-\d+" data-exception="[^"]*"><td>[^<]*</td><td>([^<]*)</td><td>([^<]*)</td>', html):
            title = main.split("：")[0]
            upsert_pattern(patterns, {"kind": "交互流程", "title": f"{'、'.join(industries)}·{title}", "industries": industries,
                                      "surfaces": ["小程序", "后台"], "summary": main, "details": {"主流程": main, "异常与恢复": exc}, "sources": []}, name)
    final = final_html(session)
    if final.is_file():
        root = re.search(r":root\{(.*?)\}", final.read_text(encoding="utf-8"), re.S)
        if root:
            tokens = dict(re.findall(r"--([\w-]+):(#[0-9a-fA-F]{3,6})", root.group(1)))
            pairs = {}
            for fg, bg in (("primary", "surface"), ("surface", "primary"), ("ink", "canvas"), ("ink2", "surface"), ("accent", "accent-tint"),
                           ("success", "success-tint"), ("danger", "danger-tint")):
                if fg in tokens and bg in tokens:
                    pairs[f"{fg} 于 {bg}"] = contrast(tokens[fg], tokens[bg])
            upsert_pattern(patterns, {"kind": "色彩", "title": f"{'、'.join(industries)}·{name.split('-', 1)[1]}配色", "industries": industries,
                                      "surfaces": ["小程序", "后台"], "summary": "、".join(f"{k} {v}" for k, v in tokens.items() if k in ("primary", "accent", "canvas")),
                                      "details": {"令牌": tokens, "对比度": pairs}, "sources": []}, name)
    prune_patterns(patterns)
    save(PATTERNS, patterns_doc)
    render()
    print(f"harvested {name}: {len(sources)} sources, {len(patterns)} patterns")
    return 0


# ---------------------------------------------------------------- add, check, render

def cmd_add(args) -> int:
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    patterns_doc = load(PATTERNS, "patterns")
    sources_doc = load(SOURCES, "sources")
    for s in data.get("sources", []):
        if not any(x["url"] == s["url"] for x in sources_doc["sources"]):
            s["id"] = next_id(sources_doc["sources"], "SRC")
            sources_doc["sources"].append(s)
    save(SOURCES, sources_doc)
    for p in data.get("patterns", []):
        if p.get("kind") not in KINDS:
            raise SystemExit(f"FAIL: kind must be one of {KINDS}: {p.get('title')}")
        upsert_pattern(patterns_doc["patterns"], p, data.get("session", "manual"))
    prune_patterns(patterns_doc["patterns"])
    save(PATTERNS, patterns_doc)
    render()
    print(f"added {len(data.get('patterns', []))} patterns, {len(data.get('sources', []))} sources")
    return 0


def check() -> list[str]:
    errors = []
    sources = load(SOURCES, "sources")["sources"]
    patterns = load(PATTERNS, "patterns")["patterns"]
    ids = {s["id"] for s in sources}
    for s in sources:
        for key in ("id", "url", "title", "category", "evidence", "borrowable", "not_copyable", "captured_at"):
            if not s.get(key):
                errors.append(f"{s.get('id')} missing {key}")
        if s.get("category") not in CATEGORIES:
            errors.append(f"{s['id']} category must be one of {CATEGORIES}")
        if [x["url"] for x in sources].count(s["url"]) > 1:
            errors.append(f"{s['id']} duplicates {s['url']}")
    for p in patterns:
        for key in ("id", "kind", "title", "summary"):
            if not p.get(key):
                errors.append(f"{p.get('id')} missing {key}")
        if p.get("kind") not in KINDS:
            errors.append(f"{p['id']} kind must be one of {KINDS}")
        for ref in p.get("sources", []):
            if ref not in ids:
                errors.append(f"{p['id']} cites unknown source {ref}")
    seen_titles: dict[tuple, str] = {}
    for p in patterns:
        sig = (p.get("kind"), note_normalize(p.get("title", "")))
        if sig in seen_titles:
            errors.append(f"{p.get('id')} duplicates {seen_titles[sig]} ({p.get('kind')} {p.get('title')}); merge them")
        seen_titles.setdefault(sig, p.get("id"))
    if len(patterns) > PATTERN_CAP:
        errors.append(f"patterns exceed the cap {PATTERN_CAP}; run prune")
    if len(sources) > SOURCE_CAP:
        errors.append(f"sources exceed the cap {SOURCE_CAP}; retire stale knowledge sources")
    if not NOTES.is_file():
        errors.append("experience/notes.json is missing")
    else:
        try:
            errors.extend(check_notes(json.loads(NOTES.read_text(encoding="utf-8"))))
        except ValueError as exc:
            errors.append(f"notes.json is not valid JSON: {exc}")
    return errors


def cmd_check(_args) -> int:
    errors = check()
    sources = load(SOURCES, "sources")["sources"]
    notes = load_notes(NOTES)
    stale = [s["id"] for s in sources if s.get("snapshot") and (age_days(s.get("captured_at")) or 0) > STALE_DAYS]
    old_notes = [n["key"] for n in stale_notes(notes)]
    for e in errors:
        print("ERROR", e)
    if stale:
        print("STALE (crawl again before reuse):", ", ".join(stale))
    if old_notes:
        print(f"UNCONFIRMED over {STALE_DAYS} days (first to prune):", ", ".join(old_notes))
    print("FAIL" if errors else "PASS",
          f"experience: {len(sources)}/{SOURCE_CAP} sources, {len(load(PATTERNS, 'patterns')['patterns'])}/{PATTERN_CAP} patterns, notes {note_counts(notes)}")
    return 1 if errors else 0


def render() -> None:
    sources = load(SOURCES, "sources")["sources"]
    patterns = load(PATTERNS, "patterns")["patterns"]
    notes = load_notes(NOTES)["notes"]
    src = {s["id"]: s for s in sources}
    lines = ["# Luz System 经验库", "",
             "每次调用开始先读本页并运行 `py -X utf8 scripts/experience.py search`；能复用的来源用 `reuse` 复制进会话，只为缺口做新的调研。"
             "每次调用结束用 `note` 记下偏好、教训与有效信息（同一主题替换原条），交付后运行 `harvest` 与 `add` 沉淀新经验。本页由 `scripts/experience.py` 生成，修改请改 JSON。", ""]
    for kind, label in NOTE_KINDS.items():
        group = sorted((n for n in notes if n["kind"] == kind), key=lambda n: n["key"])
        if not group:
            continue
        lines += [f"## {label}（{len(group)}/{NOTE_CAPS[kind]}）", ""]
        for n in group:
            why = f"（{n['why']}）" if n.get("why") else ""
            lines.append(f"- **{n['key']}**：{n['text']}{why}　确认 {n.get('uses', 1)} 次，最近 {n.get('last_confirmed')}")
        lines.append("")
    for kind in KINDS:
        group = [p for p in patterns if p["kind"] == kind]
        if not group:
            continue
        lines += [f"## {kind}", ""]
        for p in group:
            lines.append(f"### {p['id']} {p['title']}")
            lines.append(f"- 适用：{'、'.join(p.get('surfaces', []))}；行业：{'、'.join(p.get('industries', []))}；使用 {p.get('uses', 1)} 次，最近 {p.get('last_used')}")
            lines.append(f"- 要点：{p['summary']}")
            for key, value in (p.get("details") or {}).items():
                if isinstance(value, list):
                    value = "；".join(map(str, value))
                elif isinstance(value, dict):
                    value = "；".join(f"{k} {v}" for k, v in value.items())
                lines.append(f"- {key}：{value}")
            refs = [src[r] for r in p.get("sources", []) if r in src]
            if refs:
                lines.append("- 依据：" + "；".join(f"[{r['title']}]({r['url']})" for r in refs))
            lines.append("")
    lines += ["## 来源", "", "| 编号 | 类别 | 来源 | 可借鉴 | 采集日期 | 复用 |", "|---|---|---|---|---|---|"]
    for s in sources:
        age = age_days(s.get("captured_at"))
        reuse = "可复用快照" if s.get("snapshot") and age is not None and age <= STALE_DAYS else ("知识，无快照" if not s.get("snapshot") else "已过期")
        lines.append(f"| {s['id']} | {s['category']} | [{s['title']}]({s['url']}) | {s['borrowable']} | {s['captured_at']} | {reuse} |")
    CATALOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="find notes, reusable patterns and sources; every word must match")
    s.add_argument("words", nargs="*", help="keywords, all must match")
    s.add_argument("--kind", choices=list(NOTE_KINDS) + KINDS + CATEGORIES, help="a note kind, or a pattern kind or source category")
    s.add_argument("--industry")
    s.add_argument("--surface", choices=["小程序", "后台", "移动应用", "网页", "通用"])
    r = sub.add_parser("reuse", help="copy fresh sources into a session's research")
    r.add_argument("session")
    r.add_argument("ids", nargs="+")
    r.add_argument("--module", help="approved module the evidence supports")
    r.add_argument("--functions", help="functions the evidence supports")
    h = sub.add_parser("harvest", help="sediment a delivered session into the library")
    h.add_argument("session")
    h.add_argument("--industry", required=True, help="comma-separated industry tags, e.g. 健身房")
    a = sub.add_parser("add", help="add curated patterns and knowledge sources from a JSON file")
    a.add_argument("file")
    n = sub.add_parser("note", help="upsert a preference, lesson or fact by key; the same key replaces")
    n.add_argument("--kind", required=True, choices=list(NOTE_KINDS))
    n.add_argument("--key", required=True, help="stable topic slug, e.g. 表头居中 or table-header-centred")
    n.add_argument("--text", required=True, help="the general principle in one sentence")
    n.add_argument("--why", default="", help="evidence or the correction that led to it")
    ls = sub.add_parser("list", help="list notes")
    ls.add_argument("--kind", choices=list(NOTE_KINDS))
    sub.add_parser("prune", help="enforce the caps and list notes not confirmed for 180 days")
    sub.add_parser("check", help="validate shape, duplicates, caps, private data and stale sources")
    sub.add_parser("render", help="regenerate catalog.md")
    args = parser.parse_args(argv)
    if args.cmd == "render":
        render()
        return 0
    return {"search": cmd_search, "reuse": cmd_reuse, "harvest": cmd_harvest, "add": cmd_add, "check": cmd_check,
            "note": cmd_note, "list": cmd_list, "prune": cmd_prune}[args.cmd](args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
