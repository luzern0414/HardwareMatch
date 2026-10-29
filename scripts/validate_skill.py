#!/usr/bin/env python3
"""Validate the flattened Luz System skill package and root-level sessions."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlparse

from new_session import OUTPUT_ROOT
from validate_session import (
    SESSION_RE,
    first,
    iter_nodes,
    meaningful_nodes,
    normalized_visible_text,
    parse_html,
    validate as validate_session,
    validate_html_top_contract,
)

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HTML_LINK_RE = re.compile(r'(?:href|src)="([^"]+)"')
REQUIRED = [
    ".gitignore",
    "README.md",
    "LICENSE",
    "NOTICE",
    "SKILL.md",
    "WORKFLOW.md",
    "agents/openai.yaml",
    "references/guidelines.css",
    "references/templates.txt",
    "scripts/new_session.py",
    "scripts/add_mode.py",
    "scripts/validate_session.py",
    "scripts/validate_skill.py",
    "scripts/publish.py",
    "scripts/experience.py",
    "scripts/test_session_flow.py",
    "scripts/test_experience.py",
    "experience/sources.json",
    "experience/patterns.json",
    "experience/notes.json",
    "experience/catalog.md",
    "references/ui-standards.html",
    "references/system-design.html",
    "references/admin-design.html",
    "references/miniprogram-design.html",
    "references/agent-design.html",
    "references/website-design.html",
    "references/function-list-design.html",
    "references/hardware-design.html",
    "references/handoff.md",
    "references/handoff.schema.json",
    "references/hardware/plan-schema.md",
    "scripts/hw_build.py",
    "scripts/hw_experience.py",
    "scripts/hw_plan_lib.py",
    "scripts/hw_render_plan.py",
    "scripts/hw_crawl_digest.py",
    "scripts/hw_fetch_images.py",
    "experience/hardware/catalog.json",
    "experience/hardware/suppliers.json",
    "examples/unmanned-gym.plan.json",
    "scripts/context.py",
    "scripts/test_context.py",
    "references/cards.json",
    "scripts/check_interaction.py",
    "scripts/test_check_interaction.py",
]
RULE_PAGES = [
    ("ui-standards.html", "ui", "界面通用规范"),
    ("system-design.html", "system", "系统设计规范"),
    ("admin-design.html", "admin", "网页管理后台设计规范"),
    ("miniprogram-design.html", "miniprogram", "小程序设计规范"),
    ("agent-design.html", "agent", "智能体设计规范"),
    ("website-design.html", "website", "网站设计规范"),
    ("function-list-design.html", "flist", "系统功能列表规范"),
    ("commerce-design.html", "commerce", "交易与营销界面规范"),
    ("ui-recipes.html", "recipes", "界面实现参考"),
    ("config-design.html", "config", "远程配置规范"),
    ("hardware-design.html", "hardware", "硬件设计规范"),
]
TEMPLATE_NAMES = ("brief.md", "research.md", "module-intake.html", "system-architecture.html", "system-design.html", "visual-board.html", "interactive-prototype.html", "approvals.json", "manifest.json",)
REFERENCE_SUBDIRS = {"hardware"}
# The skill keeps five folders (agents, references, scripts, experience, examples); sessions are outputs and live in OUTPUT_ROOT.
ALLOWED_TOP_LEVEL = {".git", ".gitignore", "LICENSE", "NOTICE", "README.md", "SKILL.md", "WORKFLOW.md", "agents", "references", "scripts", "experience", "examples"}
RULE_TITLES = {f: t for f, _, t in RULE_PAGES}
TITLE_SEPARATOR_RE = re.compile(r"[,，:：;；|｜/／·・、\\\-–—]")
RULE_SECTIONS = [
    "scope",
    "workflow",
    "rules",
    "platform-matrix",
    "examples",
    "output-contract",
    "quality-gates",
    "handoff",
]
INLINE_ICON_DRAWING_TAGS = {"path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}
HUMAN_TEXT_ATTRIBUTES = (
    "aria-label",
    "alt",
    "title",
    "placeholder",
    "aria-description",
    "aria-roledescription",
    "aria-valuetext",
)


def title_contains_punctuation(value: str) -> bool:
    """Treat every Unicode punctuation mark as a title separator."""
    return bool(TITLE_SEPARATOR_RE.search(value)) or any(
        unicodedata.category(char).startswith("P") for char in value
    )


def is_linear_icon(icon) -> bool:
    """Require a self-contained, visible inline outline icon."""
    viewbox = icon.get("viewbox").strip()
    stroke_width = icon.get("stroke-width").strip()
    style = icon.get("style").lower()
    drawing_tags = {
        node.tag for node in iter_nodes(icon)
        if node.tag in INLINE_ICON_DRAWING_TAGS
    }
    try:
        stroke_width_value = float(stroke_width.removesuffix("px"))
    except ValueError:
        return False
    return (
        icon.tag == "svg"
        and icon.get("fill").strip().lower() == "none"
        and icon.get("stroke").strip().lower() == "currentcolor"
        and icon.get("aria-hidden").strip().lower() == "true"
        and icon.get("focusable").strip().lower() == "false"
        and bool(re.fullmatch(r"[-.0-9 ]{7,}", viewbox))
        and 0 < stroke_width_value <= 4
        and bool(drawing_tags)
        and not any(node.tag in {"image", "foreignobject"} for node in iter_nodes(icon))
        and not any(name in style for name in ("fill:", "stroke:"))
    )


TOKEN_TAGS = {"code", "kbd"}


def prose_text(node) -> str:
    """Visible text with <code>/<kbd> tokens, scripts and styles removed."""
    parts = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag in TOKEN_TAGS:
            parts.append(" ")
        elif child.tag not in {"script", "style"}:
            parts.append(prose_text(child))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def local_targets(text: str, html: bool = False) -> list[str]:
    """Local link targets. In HTML only href and src attributes link; script and style bodies and comments are code, so
    a `](` in a prototype script is not a Markdown link. In Markdown, code spans and fences are skipped."""
    if html:
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        text = re.sub(r"(<(script|style)\b[^>]*>).*?(</\2\s*>)", r"\1\3", text, flags=re.S | re.I)
        found = HTML_LINK_RE.findall(text)
    else:
        text = re.sub(r"^(`{3,}|~{3,}).*?^\1", "", text, flags=re.S | re.M)
        text = re.sub(r"`[^`\n]+`", "", text)
        found = LINK_RE.findall(text) + HTML_LINK_RE.findall(text)
    targets = []
    for raw in found:
        target = raw.strip()
        if not target or target.startswith(("<", "'")):
            continue
        target = target.split()[0].strip("<>")
        parsed = urlparse(target)
        if parsed.scheme in {"http", "https", "mailto", "data"} or target.startswith("#"):
            continue
        clean = unquote(target.split("#", 1)[0])
        if clean:
            targets.append(clean)
    return targets


def validate_rule_page(
    path: Path,
    prefix: str,
    source_count: int,
    expected_h1: str,
    errors: list[str],
) -> None:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT)
    if "<!doctype html>" not in text.lower():
        errors.append(f"HTML missing doctype: {rel}")
    if not re.search(r'<link\s+rel="stylesheet"\s+href="guidelines\.css"', text, re.I):
        errors.append(f"rule page must use rules/guidelines.css: {rel}")
    if re.search(r"color-scheme\s*:\s*dark", text, re.I):
        errors.append(f"dark color scheme is not allowed: {rel}")

    root_node = parse_html(path, errors)
    if root_node is None:
        return
    validate_html_top_contract(root_node, str(rel), errors)
    body = first(root_node, "body")
    if body is None:
        errors.append(f"{rel} is missing body")
        return
    # Prose stays Chinese; technical tokens (99+, Esc, YYYY-MM-DD, API names) are allowed only inside <code> or <kbd>.
    visible = prose_text(body)
    latin = re.search(r"[A-Za-z]", visible)
    if latin:
        start = max(0, latin.start() - 18)
        end = min(len(visible), latin.end() + 34)
        errors.append(f"visible Latin letters outside <code>/<kbd> are not allowed in {rel}: {visible[start:end]!r}")

    for node in iter_nodes(body):
        for attr in HUMAN_TEXT_ATTRIBUTES:
            attr_text = (node.get(attr) or "").strip()
            if attr_text and re.search(r"[A-Za-z]", attr_text):
                errors.append(f"accessible text in {rel} contains Latin letters: {attr_text}")

    title_node = first(root_node, "title")
    browser_title = normalized_visible_text(title_node) if title_node is not None else ""
    if browser_title != expected_h1:
        errors.append(f"{rel} browser title must be exactly {expected_h1}")
    if title_contains_punctuation(browser_title):
        errors.append(f"{rel} browser title contains a separator or punctuation mark")

    h1s = [node for node in iter_nodes(body) if node.tag == "h1"]
    if len(h1s) != 1:
        errors.append(f"{rel} must have exactly one h1 outside the sidebar")
    elif normalized_visible_text(h1s[0]) != expected_h1:
        errors.append(f"{rel} h1 must be exactly {expected_h1}")
    elif title_contains_punctuation(normalized_visible_text(h1s[0])):
        errors.append(f"{rel} h1 contains a separator or punctuation mark")

    main = first(root_node, "main")
    if main is None:
        errors.append(f"{rel} is missing main")
    else:
        if main.get("aria-label").strip() != expected_h1:
            errors.append(f"{rel} main aria-label must exactly match the page title")
        children = meaningful_nodes(main.children)
        if len(children) < 2 or not hasattr(children[0], "tag") or children[0].tag != "h1":
            errors.append(f"{rel} main must begin directly with its unique h1")
        elif not hasattr(children[1], "tag") or children[1].tag != "section":
            errors.append(f"{rel} h1 must be followed directly by the first section")
        else:
            first_section_children = meaningful_nodes(children[1].children)
            if not first_section_children or not hasattr(first_section_children[0], "tag") or first_section_children[0].tag != "h2":
                errors.append(f"{rel} first section must begin directly with its h2")
            near_title_copy = normalized_visible_text(children[1])
            for banned in ("日期", "无需构建", "可直接编辑", "入口", "说明"):
                if banned in near_title_copy:
                    errors.append(f"{rel} first section contains title-adjacent copy: {banned}")

        all_section_nodes = [node for node in iter_nodes(main) if node.tag == "section"]
        for section_node in all_section_nodes:
            section_children = meaningful_nodes(section_node.children)
            section_label = section_node.get("id") or "without-id"
            if (not section_children
                    or not hasattr(section_children[0], "tag")
                    or section_children[0].tag != "h2"):
                errors.append(f"{rel} section {section_label} must begin directly with its h2")

        section_icon_count = 0
        formal_section_nodes = [
            node for node in all_section_nodes if node.get("id") in RULE_SECTIONS
        ]
        for section_node in formal_section_nodes:
            section_children = meaningful_nodes(section_node.children)
            if (not section_children
                    or not hasattr(section_children[0], "tag")
                    or section_children[0].tag != "h2"):
                continue
            section_h2 = section_children[0]
            h2_children = meaningful_nodes(section_h2.children)
            if (not h2_children
                    or not hasattr(h2_children[0], "tag")
                    or h2_children[0].tag != "svg"):
                errors.append(f"{rel} section {section_node.get('id')} h2 must begin with its linear SVG icon")
            icons = [node for node in iter_nodes(section_h2) if node.tag == "svg"]
            if len(icons) != 1:
                errors.append(
                    f"{rel} section {section_node.get('id')} h2 must contain exactly one inline linear SVG icon"
                )
            for icon in icons:
                if not is_linear_icon(icon):
                    errors.append(
                        f"{rel} section {section_node.get('id')} h2 needs a valid linear SVG icon"
                    )
                else:
                    section_icon_count += 1
        if len(formal_section_nodes) < len(RULE_SECTIONS):
            errors.append(f"{rel} must contain all eight formal sections")
        if section_icon_count < len(RULE_SECTIONS):
            errors.append(f"{rel} needs one linear icon for every formal section; found {section_icon_count}")

    ids = re.findall(r'\bid="([^"]+)"', text)
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"duplicate HTML ids in {rel}: {', '.join(duplicates)}")
    for section in RULE_SECTIONS:
        if f'<section id="{section}" data-rule-id="{prefix}-{section}"' not in text:
            errors.append(f"{rel} missing stable section contract: {section}")
        if f"<!-- SECTION:{section}:START" not in text or f"<!-- SECTION:{section}:END -->" not in text:
            errors.append(f"{rel} missing section edit boundaries: {section}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the flattened Luz System skill and root-level sessions.")
    parser.add_argument("--strict-production", action="store_true", help="Require strict session structure and live source verification")
    args = parser.parse_args(argv)
    errors: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            errors.append(f"missing required file: {rel}")
    for item in ROOT.iterdir():
        if item.name not in ALLOWED_TOP_LEVEL and item.name not in {"__pycache__", ".pytest_cache"}:
            errors.append(f"unexpected top-level item in the skill: {item.name} (the skill keeps only LICENSE, NOTICE, README.md, SKILL.md, WORKFLOW.md, agents, references, scripts, experience, examples)")
    for item in (ROOT / "references").iterdir() if (ROOT / "references").is_dir() else []:
        if item.is_dir() and item.name not in REFERENCE_SUBDIRS:
            errors.append(f"references must stay flat: {item.name}/")

    skill = ROOT / "SKILL.md"
    if skill.is_file():
        text = skill.read_text(encoding="utf-8")
        normalized = text.replace("\r\n", "\n")
        if not normalized.startswith("---\n"):
            errors.append("SKILL.md must start with YAML frontmatter")
        if "\nname: luz-system" not in normalized:
            errors.append("SKILL.md name must be luz-system")
        if "description:" not in text:
            errors.append("SKILL.md description is missing")
        if re.search(r"\b(?:TODO|TBD|FIXME)\b", text):
            errors.append("SKILL.md contains an unfinished marker")
        for expected in [f"references/{f}" for f, _, _ in RULE_PAGES]:
            if expected not in text:
                errors.append(f"SKILL.md missing route: {expected}")
        # The invocation protocol is the first section and starts from the rule card (scripts/context.py).
        sections = re.findall(r"(?m)^## (.+)$", normalized)
        if not sections or not sections[0].startswith("调用协议"):
            errors.append("SKILL.md must open with the section 调用协议 (invocation protocol) before any other section")
        protocol_text = normalized.split("\n## ", 2)[1] if "\n## " in normalized else ""
        if "scripts/context.py" not in protocol_text:
            errors.append("SKILL.md 调用协议 must start from scripts/context.py (the rule card)")
        # Agents choose skills from the parsed frontmatter; an unquoted ": " inside the description breaks it silently.
        try:
            import yaml
            front = yaml.safe_load(normalized.split("---", 2)[1])
            if not isinstance(front, dict) or not isinstance(front.get("description"), str):
                errors.append("SKILL.md frontmatter does not parse to a name and a description string")
        except ImportError:
            if re.search(r"(?m)^description: [^\n]*: ", normalized):
                errors.append("SKILL.md description contains ': ' which breaks YAML; use a dash instead")
        except Exception as exc:
            errors.append(f"SKILL.md frontmatter is not valid YAML: {exc}")
        description = re.search(r"(?m)^description: (.+)$", normalized)
        if not description or "context.py" not in description.group(1):
            errors.append("SKILL.md description must tell agents to start with scripts/context.py")
        if len(description.group(1) if description else "") > 1024:
            errors.append("SKILL.md description exceeds 1024 characters")

    json_files = ["references/handoff.schema.json", "examples/unmanned-gym.plan.json", "references/cards.json"]
    for rel in json_files:
        path = ROOT / rel
        if path.is_file():
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in {rel}: {exc}")

    for file_name, prefix, title in RULE_PAGES:
        validate_rule_page(ROOT / "references" / file_name, prefix, 0, title, errors)
    # Every rule card resolves to existing rule-page sections, so renaming a heading cannot silently empty a card.
    import context
    errors.extend(f"rule card: {e}" for e in context.check_cards())
    head = (ROOT / "references" / "templates.txt").read_text(encoding="utf-8").splitlines()[:4]
    if not any("context.py" in line for line in head):
        errors.append("references/templates.txt must say at the top that templates are skeletons and point to scripts/context.py")

    guidelines_css = ROOT / "references/guidelines.css"
    if guidelines_css.is_file():
        css_body = guidelines_css.read_text(encoding="utf-8")
        for value in re.findall(r"(?:font-size|font)\s*:\s*[^;{}]*?([0-9.]+)px", css_body):
            if float(value) < 14:
                errors.append(f"rule stylesheet contains a font size below 14px: {value}px")
        icon_style = re.search(r"\.icon-linear\s*\{([^}]*)\}", css_body, re.S)
        if not icon_style:
            errors.append("rule stylesheet is missing .icon-linear")
        else:
            icon_rules = icon_style.group(1)
            for token in ("width:", "height:", "fill:none", "stroke:currentcolor"):
                compact = re.sub(r"\s+", "", icon_rules).lower()
                if token not in compact:
                    errors.append(f"rule stylesheet icon style missing {token}")
        heading_style = re.search(r"h2\s*\{([^}]*)\}", css_body, re.S)
        heading_rules = heading_style.group(1) if heading_style else ""
        compact_heading = re.sub(r"\s+", "", heading_rules).lower()
        if "display:flex" not in compact_heading or "align-items:center" not in compact_heading:
            errors.append("rule stylesheet must align h2 icons and text vertically")

    for path in ROOT.rglob("*"):
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in {".md", ".html"}:
            text = path.read_text(encoding="utf-8")
            for target in local_targets(text, html=path.suffix.lower() == ".html"):
                if not (path.parent / target).resolve().exists():
                    errors.append(f"broken local link in {path.relative_to(ROOT)}: {target}")
            if path.suffix.lower() == ".html" and "<!doctype html>" not in text.lower():
                errors.append(f"HTML missing doctype: {path.relative_to(ROOT)}")
            if path.suffix.lower() == ".html" and re.search(r"color-scheme\s*:\s*dark", text, re.I):
                errors.append(f"dark color scheme is not allowed: {path.relative_to(ROOT)}")
            if path.suffix.lower() == ".html" and "{{" not in text:
                root = parse_html(path, errors)
                if root is not None:
                    validate_html_top_contract(root, str(path.relative_to(ROOT)), errors)

    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.suffix.lower() not in {".md", ".txt", ".json", ".py", ".html", ".yaml", ".yml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"(?<![A-Za-z0-9-])sk-(?:proj-)?[A-Za-z0-9_]{20,}", text):
            errors.append(f"possible API key in {path.relative_to(ROOT)}")

    sessions = [path for path in OUTPUT_ROOT.iterdir() if path.is_dir() and SESSION_RE.match(path.name)] if OUTPUT_ROOT.is_dir() else []
    warnings: list[str] = []
    for session in sorted(sessions):
        session_warnings: list[str] = []
        errors.extend(
            f"{session.name}: {error}"
            for error in validate_session(
                session, strict=args.strict_production, live_sources=args.strict_production, warnings=session_warnings
            )
        )
        warnings.extend(f"{session.name}: {warning}" for warning in dict.fromkeys(session_warnings))

    from new_session import read_template
    templates: dict[str, str] = {}
    for name in TEMPLATE_NAMES:
        try:
            templates[name] = read_template(ROOT, name)
        except (KeyError, OSError) as exc:
            errors.append(str(exc))
    for name in ("approvals.json", "manifest.json"):
        if name in templates:
            try:
                json.loads(templates[name])
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in template {name}: {exc}")
    for name in [n for n in ("module-intake.html", "system-design.html") if n in TEMPLATE_NAMES]:
        for value in re.findall(r"font-size:\s*([0-9.]+)px", templates.get(name, "")):
            if float(value) < 14:
                errors.append(f"{name} contains a font size below 14px")
    if "module-intake.html" in templates and "{{MODULE_ITEMS}}" not in templates["module-intake.html"]:
        errors.append("module-intake.html must contain a copyable module placeholder")
    if "visual-board.html" in templates and 'data-artifact="visual-board"' not in templates["visual-board.html"]:
        errors.append("visual-board.html must declare its artifact type")

    from experience import check as check_experience
    errors.extend(f"experience: {e}" for e in check_experience())

    for warning in warnings:
        print("WARN", warning)
    if errors:
        print(f"FAIL: {len(errors)} issue(s)")
        for error in errors:
            print("ERROR", error)
        return 1
    if not Path("D:/Codes/Imagegen/src/imagegen.py").is_file():
        print("WARN: Imagegen was not found at D:\\Codes\\Imagegen")
    session_label = f"{len(sessions)} production session(s)" if args.strict_production else f"{len(sessions)} session(s)"
    validation_label = "sessions production-validated" if args.strict_production else "sessions not production-validated"
    print(
        f"PASS: Luz System skill validated with {len(REQUIRED)} required files, "
        f"{session_label}, 3 rule entrances, and {validation_label}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
