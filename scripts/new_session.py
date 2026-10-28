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
    return text.replace("{{SYSTEM_NAME}}", safe_system).replace("{{MODULE_ITEMS}}", module_items(modules))


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
        board = board.replace("{{PAGE_ID}}", page_id)
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
        manifest = json.loads((session / "99-delivery" / "MANIFEST.json").read_text(encoding="utf-8"))
        prototype = (prototype
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


def render_brief(skill_root: Path, title: str, session_kind: str) -> str:
    text = read_template(skill_root, "brief.md")
    if session_kind == "standalone_poster":
        text = text.replace("- Session:", f"- Session: {title}", 1)
        text = text.replace("- Request summary:", f"- Request summary: {title}", 1)
    return text


def validate_creation(modes: list[str], session_kind: str, system_name: str | None, modules: list[str]) -> None:
    if session_kind not in SESSION_KINDS:
        raise ValueError(f"unknown session kind: {session_kind}")
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
) -> Path:
    requested_modules = list(dict.fromkeys(modules or []))
    validate_creation(modes, session_kind, system_name, requested_modules)
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
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the next Luz System session folder.")
    parser.add_argument("--name", required=True, help="Readable session title")
    parser.add_argument("--modes", default="", help="system, hardware (system,hardware for both), or none; visual and prototype are added later with add_mode.py")
    parser.add_argument("--session-kind", choices=SESSION_KINDS, default="general")
    parser.add_argument("--system-name", help="Required in system mode; provide the exact system name supplied by the user")
    parser.add_argument("--modules", help="Comma-separated exact module names supplied by the user")
    parser.add_argument("--root", help="Output root override, primarily for tests")
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
        )
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(str(folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
