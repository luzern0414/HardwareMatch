#!/usr/bin/env python3
"""Create the next immutable-numbered Luz System session workspace."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
# The skill holds rules, templates and scripts; every session it creates is an output and lives here.
OUTPUT_ROOT = Path(r"D:\Codes\skill输出\Luz-System")
SESSION_RE = re.compile(r"^(\d{3,})-(.+)$")
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Luz-System owns system design, product visual, interactive prototype and hardware.
# Posters, brand visuals and document layout belong to Luz-Design (D:\Codes\Luz-Design).
MODE_NAMES = ("system", "visual", "prototype", "hardware")
OTHER_SKILL_MODES = {"document": "Luz-Design", "poster": "Luz-Design"}
HW_REQUIREMENTS = """# 硬件需求

| 编号 | 要点 | 验收信号 |
|---|---|---|
| HW-01 | 系统类型与规模（面积、门店数、入口数、灶位数） | |
| HW-02 | 运营模式（营业时间、付费方式、是否无人值守） | |
| HW-03 | 已有设备或指定品牌 | |
| HW-04 | 硬件预算区间 | |
| HW-05 | 后台系统（自研 / SaaS）与设备接入要求 | |
"""
POSTER_TASK_RE = re.compile(r"海报|poster", re.I)
SESSION_KINDS = ("general", "system")
# per_stage: a person approves each stage. authorization: a platform demo session; a person signs one authorization
# before generation and the platform records each stage under it (SKILL.md 调用协议 6).
APPROVAL_MODES = ("per_stage", "authorization")
# Rule cards written into raw/00-rules/ when a mode starts (scripts/context.py; references/cards.json).
# A stage card always comes with its mode; visual mode adds the surface cards named with --card, else these two.
MODE_CARDS = {"system": "system-design", "prototype": "prototype", "hardware": "hardware"}
# The closed-loop interaction rules (ui-standards.html 页面交互契约, 功能闭环, 操作反馈) come with the stages that write
# the architecture and build the prototype.
MODE_EXTRA_CARDS = {"system": ("interaction",), "prototype": ("interaction",)}
DEFAULT_SURFACE_CARDS = ("admin-list", "miniprogram")

# Tab icon and brand mark (Luz-Design references/visual-design.html 网页图标与品牌标识; ui-standards.html 页头):
# one flat line pictogram of the system's subject, primary-colour strokes on a rounded square in the theme's lightest
# tint, 32×32, at most three shapes, no text. The same icon is the browser-tab icon of every page and the header brand mark.
TAB_ICONS = {
    "dumbbell": '<path d="M9 11v10M23 11v10M6 14v4M26 14v4M9 16h14"/>',
    "megaphone": '<path d="M8 13v6h4l8 5V8l-8 5z"/><path d="M24 13a4 4 0 0 1 0 6"/>',
    "radar": '<circle cx="16" cy="16" r="8.5"/><path d="M16 16l5.5-5.5M16 11.5a4.5 4.5 0 1 0 4.5 4.5"/>',
    "chip": '<rect x="10" y="10" width="12" height="12" rx="2"/><path d="M13.5 7v3M18.5 7v3M13.5 22v3M18.5 22v3M7 13.5h3M7 18.5h3M22 13.5h3M22 18.5h3"/>',
    "ledger": '<rect x="9" y="7" width="14" height="18" rx="2"/><path d="M13 12h6M13 16h6M13 20h3"/>',
    "store": '<path d="M7.5 13l2-5h13l2 5zM9 13v11h14V13"/><path d="M14 24v-5h4v5"/>',
    "grid": '<path d="M9 9h5v5H9zM18 9h5v5h-5zM9 18h5v5H9zM18 18h5v5h-5z"/>',
}
# First match wins; the system name is matched case-insensitively.
ICON_KEYWORDS = (
    (("健身", "gym", "运动馆", "健身房"), "dumbbell"),
    (("采购", "招标", "投标", "公告"), "megaphone"),
    (("获客", "线索", "商机", "雷达"), "radar"),
    (("硬件", "芯片", "物联", "设备"), "chip"),
    (("财务", "账本", "账务", "记账", "会计", "发票"), "ledger"),
    (("门店", "零售", "店铺", "商城"), "store"),
)
THEME_KEYWORDS = ((("健身", "gym", "运动馆"), "fitness-gym"),)
THEMES_JSON = SKILL_ROOT.parent / "Luz-Design" / "references" / "themes.json"
# Ant Design blue-7 on blue-1: the neutral fallback when no industry theme matches.
FALLBACK_COLORS = ("#0958D9", "#E6F4FF")


def pick_icon(subject: str) -> str:
    lowered = subject.casefold()
    return next((icon for words, icon in ICON_KEYWORDS if any(w in lowered for w in words)), "grid")


def theme_colors(subject: str, theme: str | None = None, themes_json: Path = THEMES_JSON) -> tuple[str, str]:
    """(primary, lightest tint) of the theme named or matched from the subject; neutral blue when none matches."""
    try:
        themes = json.loads(themes_json.read_text(encoding="utf-8")).get("themes", {})
    except (OSError, ValueError):
        return FALLBACK_COLORS
    lowered = subject.casefold()
    key = theme or next((k for words, k in THEME_KEYWORDS if any(w in lowered for w in words)), None)
    if key is None:
        for name, data in themes.items():
            tokens = re.split(r"[\s/、，,]+", f"{data.get('label', '')}、{data.get('subtype', '')}")
            if any(len(t) >= 2 and t.casefold() in lowered for t in tokens):
                key = name
                break
    data = themes.get(key or "", {})
    if data.get("action") and data.get("actionTint"):
        return data["action"], data["actionTint"]
    return FALLBACK_COLORS


def tab_icon_svg(subject: str, *, icon: str | None = None, theme: str | None = None, attrs: str = "") -> str:
    primary, tint = theme_colors(subject, theme)
    shapes = TAB_ICONS[icon or pick_icon(subject)]
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"{attrs}>'
    return (head + f'<rect width="32" height="32" rx="8" fill="{tint}"/>'
            f'<g fill="none" stroke="{primary}" stroke-width="2.75" stroke-linecap="round" stroke-linejoin="round">{shapes}</g></svg>')


def tab_icon_href(subject: str, **options) -> str:
    from urllib.parse import quote
    return "data:image/svg+xml," + quote(tab_icon_svg(subject, **options).replace('"', "'"), safe=" =:/,;'.-")


def brand_mark_svg(subject: str, **options) -> str:
    return tab_icon_svg(subject, attrs=' class="brand-mark" width="28" height="28" aria-hidden="true" focusable="false"', **options)


def fill_icon_slots(text: str, subject: str, **options) -> str:
    """Fill {{TAB_ICON}} (the href of <link rel="icon">) and {{BRAND_MARK}} (the inline header mark) in a template."""
    return text.replace("{{TAB_ICON}}", tab_icon_href(subject, **options)).replace("{{BRAND_MARK}}", brand_mark_svg(subject, **options))

_ICONS = [
    '<path d="M12 3l8 4v10l-8 4-8-4V7l8-4z"/><path d="M8 12h8M12 8v8"/>',
    '<path d="M6 3h12v18H6z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0116 0"/>',
    '<path d="M4 6h16v14H4z"/><path d="M8 3v6M16 3v6M4 11h16"/>',
    '<path d="M4 7h16v12H4z"/><path d="M4 10h16M8 15h3M15 15h1"/>',
    '<path d="M5 20V9l7-5 7 5v11"/><path d="M9 20v-6h6v6"/>',
    '<path d="M12 3l8 4v10l-8 4-8-4V7l8-4z"/><path d="M8 12l3 3 5-6"/>',
    '<path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5M8 17h8"/>',
]


def clean_title(value: str) -> str:
    value = unicodedata.normalize("NFC", value).strip()
    value = re.sub(r"^\d{3,}[-_\s]+", "", value)
    value = INVALID.sub("-", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"-{2,}", "-", value).strip(" .-")
    value = value[:60].rstrip(" .")
    return value or "未命名会话"


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    result: list[str] = []
    for item in re.split(r"[,，]", value):
        item = item.strip()
        if item and item not in result:
            result.append(item)
    return result


def parse_modes(value: str | None) -> list[str]:
    if not value or value == "none":
        return []
    if value == "all":
        modes = list(MODE_NAMES)
    else:
        modes = [item.strip() for item in value.split(",") if item.strip()]
    elsewhere = [m for m in modes if m in OTHER_SKILL_MODES]
    if elsewhere:
        raise ValueError(f"{', '.join(elsewhere)} belongs to {OTHER_SKILL_MODES[elsewhere[0]]}, not Luz-System; use that skill")
    unknown = sorted(set(modes) - set(MODE_NAMES))
    if unknown:
        raise ValueError(f"unknown modes: {', '.join(unknown)}")
    return [mode for mode in MODE_NAMES if mode in modes]


def read_template(skill_root: Path, name: str) -> str:
    """Return one block of references/templates.txt (all session templates live in that single file)."""
    text = (skill_root / "references" / "templates.txt").read_text(encoding="utf-8")
    start = f"=== template: {name} ===\n"
    if start not in text:
        raise KeyError(f"template not found in references/templates.txt: {name}")
    body = text.split(start, 1)[1].split("\n=== end ===", 1)[0]
    return body + "\n"


AGENT_PART_MARK = "<!-- AGENT_PART -->"
AGENT_CARD_KINDS = ("agent-ui", "agent-runtime-ui")


def insert_agent_part(prototype: str, skill_root: Path = SKILL_ROOT) -> str:
    """Put the agent run-state skeleton (templates.txt agent-run-states.html: 排队, 执行中, 等待审批, 失败可重试, 断线重连,
    已停止, 完成) where the prototype template marks it; agent-design.html 运行状态 decides what each state shows."""
    if AGENT_PART_MARK not in prototype:
        return prototype
    part = read_template(skill_root, "agent-run-states.html").strip()
    return prototype.replace(AGENT_PART_MARK, part, 1)


def write_if_missing(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def module_items(modules: list[str]) -> str:
    rows = []
    for index, module in enumerate(modules):
        safe = html.escape(module, quote=True)
        icon = _ICONS[index % len(_ICONS)]
        rows.append(
            '      <li data-module="' + safe + '">\n'
            '        <label>\n'
            f'          <input type="checkbox" name="selected_modules" value="{safe}" data-module="{safe}">\n'
            f'          <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none">{icon}</svg></span>\n'
            f'          <span class="name">{html.escape(module)}</span>\n'
            '          <span class="mark" aria-hidden="true"></span>\n'
            '        </label>\n'
            '      </li>'
        )
    return "\n".join(rows)


def render_module_intake(skill_root: Path, system_name: str, modules: list[str]) -> str:
    text = read_template(skill_root, "module-intake.html")
    safe_system = html.escape(system_name)
    text = fill_icon_slots(text, system_name)
    return text.replace("{{SYSTEM_NAME}}", safe_system).replace("{{MODULE_ITEMS}}", module_items(modules))


def session_subject(session: Path) -> str:
    """The name the tab icon is chosen from: the manifest's system name, else the session title."""
    try:
        manifest = json.loads((session / "99-delivery" / "MANIFEST.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    return str(manifest.get("system_name") or manifest.get("title") or session.parent.name.split("-", 1)[-1])


def init_mode(skill_root: Path, session: Path, mode: str, *, system_name: str | None = None, modules: list[str] | None = None) -> None:
    if mode == "system":
        if not system_name or not modules:
            raise ValueError("system mode needs a system name and at least one requested module")
        base = session / "01-system"
        base.mkdir(parents=True, exist_ok=True)
        write_if_missing(base / "01-module-intake.html", render_module_intake(skill_root, system_name, modules))
        write_if_missing(base / "02-research.md", read_template(skill_root, "research.md"))
    elif mode == "visual":
        base = session / "02-visual"
        for child in ("prompts", "references", "generated"):
            (base / child).mkdir(parents=True, exist_ok=True)
        board = read_template(skill_root, "visual-board.html")
        page_id = "NOT_APPLICABLE"
        design = session / "01-system" / "04-system-design.html"
        if design.is_file():
            page_ids = re.findall(r'data-page-id="(P-\d{3,})"', design.read_text(encoding="utf-8"))
            if page_ids:
                page_id = page_ids[0]
        if page_id == "NOT_APPLICABLE":
            architecture = session / "01-system" / "03-system-architecture.html"
            if architecture.is_file():
                page_ids = re.findall(r'data-page-id="(P-\d{3,})"', architecture.read_text(encoding="utf-8"))
                if page_ids:
                    page_id = page_ids[0]
        board = fill_icon_slots(board.replace("{{PAGE_ID}}", page_id), session_subject(session))
        write_if_missing(base / "visual-board.html", board)
    elif mode == "prototype":
        base = session / "03-prototype"
        base.mkdir(parents=True, exist_ok=True)
        architecture = session / "01-system" / "03-system-architecture.html"
        if not architecture.is_file():
            raise PermissionError("prototype mode requires an approved architecture")
        architecture_text = architecture.read_text(encoding="utf-8")
        action_ids = re.findall(r'data-action-id="(A-\d{3,})"', architecture_text)
        page_ids = re.findall(r'data-page-id="(P-\d{3,})"', architecture_text)
        if not action_ids or not page_ids:
            raise PermissionError("prototype mode requires approved page and action IDs")
        architecture_hash = hashlib.sha256(architecture.read_bytes()).hexdigest()
        prototype = read_template(skill_root, "interactive-prototype.html")
        # An agent session (it works from the agent rule cards) gets the seven run states in its skeleton.
        if any((session / "00-rules" / f"{kind}.md").is_file() for kind in AGENT_CARD_KINDS):
            prototype = insert_agent_part(prototype, skill_root)
        else:
            prototype = "\n".join(line for line in prototype.split("\n") if line.strip() != AGENT_PART_MARK)
        manifest = json.loads((session / "99-delivery" / "MANIFEST.json").read_text(encoding="utf-8"))
        prototype = (fill_icon_slots(prototype, session_subject(session))
            .replace("{{SYSTEM_NAME}}", html.escape(str(manifest.get("system_name", "交互原型"))))
            .replace("{{ARCHITECTURE_SHA256}}", architecture_hash)
            .replace("{{ACTION_ID}}", action_ids[0])
            .replace("{{PAGE_ID}}", page_ids[0]))
        write_if_missing(base / "interactive-prototype.html", prototype)
    elif mode == "hardware":
        # Hardware design lives beside the software design in the same session (references/hardware-design.html).
        base = session / "04-hardware"
        base.mkdir(parents=True, exist_ok=True)
        write_if_missing(base / "requirements.md", HW_REQUIREMENTS)
        title = (system_name or session.name.split("-", 1)[-1])
        write_if_missing(base / "plan.json", json.dumps({"title": title, "zones": [], "devices": [], "links": []}, ensure_ascii=False, indent=2) + "\n")
    else:
        raise ValueError(f"unknown mode: {mode}")


def rule_card_kinds(modes: list[str], cards: list[str] | None = None) -> list[str]:
    """The rule cards a session needs for these modes plus any named with --card; unknown kinds are refused."""
    import context
    kinds = [MODE_CARDS[mode] for mode in modes if mode in MODE_CARDS]
    kinds.extend(extra for mode in modes for extra in MODE_EXTRA_CARDS.get(mode, ()))
    if "visual" in modes and not cards:
        kinds.extend(DEFAULT_SURFACE_CARDS)
    kinds.extend(cards or [])
    unknown = sorted(set(kinds) - set(context.card_kinds()))
    if unknown:
        raise ValueError(f"unknown rule card: {', '.join(unknown)}; see py -X utf8 scripts/context.py list")
    return list(dict.fromkeys(kinds))


def save_rule_cards(work: Path, kinds: list[str]) -> list[Path]:
    """Save each card not yet in raw/00-rules/; an existing card is kept so its date and hash still show staleness."""
    import context
    saved = []
    for kind in kinds:
        if not (work / "00-rules" / f"{kind}.md").is_file():
            saved.append(context.save_card(work, kind))
    return saved


def print_card_hint(folder: Path) -> None:
    cards = sorted((folder / "raw" / "00-rules").glob("*.md"))
    if cards:
        print("NEXT: read the rule card(s) before producing anything, then fill BRIEF 采用的规则 and 本次沉淀:", file=sys.stderr)
        for card in cards:
            print(f"  {card}", file=sys.stderr)


def render_brief(skill_root: Path, title: str, session_kind: str) -> str:
    text = read_template(skill_root, "brief.md")
    if session_kind == "standalone_poster":
        text = text.replace("- Session:", f"- Session: {title}", 1)
        text = text.replace("- Request summary:", f"- Request summary: {title}", 1)
    return text


def validate_creation(modes: list[str], session_kind: str, system_name: str | None, modules: list[str],
                      approval_mode: str = "per_stage") -> None:
    if session_kind not in SESSION_KINDS:
        raise ValueError(f"unknown session kind: {session_kind}")
    if approval_mode not in APPROVAL_MODES:
        raise ValueError(f"unknown approval mode: {approval_mode}")
    if approval_mode == "authorization" and (session_kind != "system" or "hardware" in modes):
        raise ValueError("approval mode authorization is for software demo sessions: --session-kind system --modes system")
    if "system" in modes and session_kind != "system":
        raise ValueError("system mode requires session kind 'system'")
    if session_kind == "system" and "system" not in modes:
        raise ValueError("a system session must start with system mode")
    if "system" in modes and not modules:
        raise ValueError("system sessions require the exact user-requested modules via --modules")
    if not system_name and "system" in modes:
        raise ValueError("system sessions require --system-name")
    if "visual" in modes:
        raise ValueError("product visual starts only after system-design approval; use add_mode.py (posters and brand visuals belong to Luz-Design)")
    if "system" in modes and ("visual" in modes or "prototype" in modes):
        raise ValueError("system mode cannot start with downstream visual or prototype modes")
    if "prototype" in modes and "visual" not in modes:
        raise ValueError("prototype mode is activated only after visual approval")


def create_session(
    root: Path,
    title: str,
    modes: list[str],
    *,
    skill_root: Path = SKILL_ROOT,
    session_kind: str = "general",
    system_name: str | None = None,
    modules: list[str] | None = None,
    cards: list[str] | None = None,
    approval_mode: str = "per_stage",
) -> Path:
    requested_modules = list(dict.fromkeys(modules or []))
    validate_creation(modes, session_kind, system_name, requested_modules, approval_mode)
    kinds = rule_card_kinds(modes, cards)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    clean = clean_title(title)
    if session_kind == "standalone_poster" and not POSTER_TASK_RE.search(clean):
        raise ValueError("standalone poster session title must explicitly describe a poster task")
    sequences = []
    for item in root.iterdir():
        match = SESSION_RE.match(item.name)
        if item.is_dir() and match:
            sequences.append(int(match.group(1)))
    next_sequence = max(sequences, default=0) + 1

    while True:
        folder = root / f"{next_sequence:03d}-{clean}"
        try:
            folder.mkdir()
            break
        except FileExistsError:
            next_sequence += 1

    try:
        created = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        session_id = f"SES-{next_sequence:03d}"
        work = folder / "raw"
        work.mkdir()
        (work / "BRIEF.md").write_text(render_brief(skill_root, clean, session_kind), encoding="utf-8")

        delivery = work / "99-delivery"
        delivery.mkdir()
        approvals = json.loads(read_template(skill_root, "approvals.json"))
        if session_kind == "system":
            approvals["module_scope"]["requested_modules"] = requested_modules
        if session_kind == "standalone_poster":
            approvals["module_scope"]["status"] = "not_requested"
            approvals["system_design"]["status"] = "not_requested"
            approvals["standalone_poster"]["status"] = "requested"
        if approval_mode == "authorization":
            # Filled when the person signs, before generation (SKILL.md 调用协议 6, 一次授权).
            approvals["authorizations"] = []
        (delivery / "APPROVALS.json").write_text(
            json.dumps(approvals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        manifest = json.loads(read_template(skill_root, "manifest.json"))
        manifest.update({
            "session_id": session_id,
            "sequence": next_sequence,
            "folder": folder.name,
            "title": clean,
            "created_at": created,
            "session_kind": session_kind,
            "modes": modes,
        })
        if session_kind == "system":
            manifest["system_name"] = system_name
            manifest["requested_modules"] = requested_modules
        if approval_mode == "authorization":
            manifest["approval_mode"] = approval_mode
        (delivery / "MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for mode in modes:
            init_mode(
                skill_root,
                work,
                mode,
                system_name=system_name if mode == "system" else None,
                modules=requested_modules if mode == "system" else None,
            )
        # The rules, preferences, lessons, tools and checks for this task, cut from the rule pages (read before producing).
        save_rule_cards(work, kinds)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder


def print_icon(argv: list[str]) -> int:
    """`new_session.py icon NAME [--icon KEY] [--theme KEY]`: print the tab-icon link and the header brand mark."""
    parser = argparse.ArgumentParser(prog="new_session.py icon", description="Print the tab icon and brand mark for a system name.")
    parser.add_argument("name", help="System name; the pictogram and theme colour are chosen from its keywords")
    parser.add_argument("--icon", choices=sorted(TAB_ICONS), help="Override the pictogram")
    parser.add_argument("--theme", help="Override the theme key in Luz-Design references/themes.json")
    args = parser.parse_args(argv)
    options = {"icon": args.icon, "theme": args.theme}
    print(f'<link rel="icon" href="{tab_icon_href(args.name, **options)}">')
    print(brand_mark_svg(args.name, **options))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["icon"]:
        return print_icon(argv[1:])
    parser = argparse.ArgumentParser(description="Create the next Luz System session folder; `icon NAME` prints the tab icon and brand mark.")
    parser.add_argument("--name", required=True, help="Readable session title")
    parser.add_argument("--modes", default="", help="system, hardware (system,hardware for both), or none; visual and prototype are added later with add_mode.py")
    parser.add_argument("--session-kind", choices=SESSION_KINDS, default="general")
    parser.add_argument("--system-name", help="Required in system mode; provide the exact system name supplied by the user")
    parser.add_argument("--modules", help="Comma-separated exact module names supplied by the user")
    parser.add_argument("--root", help="Output root override, primarily for tests")
    parser.add_argument("--card", action="append", help="Extra rule card for this task (repeatable): system-design, function-list, admin-list, admin-dashboard, admin-form, miniprogram, agent-ui, agent-runtime-ui, website, prototype, hardware, interaction; each mode adds its own card (system and prototype also add interaction)")
    parser.add_argument("--approval-mode", choices=APPROVAL_MODES, default="per_stage",
                        help="per_stage (default): a person approves each stage; authorization: a platform demo session where a "
                             "person signs one authorization before generation (APPROVALS.json authorizations)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else OUTPUT_ROOT
    kind = args.session_kind
    if args.modes == "system" and kind == "general":
        kind = "system"
    try:
        folder = create_session(
            root,
            args.name,
            parse_modes(args.modes),
            session_kind=kind,
            system_name=args.system_name,
            modules=parse_csv(args.modules),
            cards=args.card,
            approval_mode=args.approval_mode,
        )
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(str(folder))
    print_card_hint(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
