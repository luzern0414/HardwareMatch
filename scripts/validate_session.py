#!/usr/bin/env python3
"""Validate a Luz System session workspace without third-party dependencies."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote, urlparse

SESSION_RE = re.compile(r"^(\d{3,})-(.+)$")
# A session folder holds exactly one final HTML named after the folder, plus raw/ with every working file:
# brief, research, crawl snapshots, architecture, stage artifacts, approvals and manifest.
RAW_DIR = "raw"
PUBLISHABLE_STAGES = ("system_design", "visual", "prototype", "hardware")


def work_dir(folder: Path) -> Path:
    return folder / RAW_DIR


def final_html(folder: Path) -> Path:
    return folder / f"{folder.name}.html"
SESSION_ID_RE = re.compile(r"^SES-(\d{3,})$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HTML_LINK_RE = re.compile(r'(?:href|src)="([^"]+)"')
DELIVERABLE_ID_RE = re.compile(r"^(?:PAGE|ACT|FLOW|VIS|REF|DOC|SYS|PROTO|ARCH)-[A-Z0-9-]+$")
ASSUMPTION_ID_RE = re.compile(r"^ASSUME-\d{3,}$")
VALID_STATUS = {"draft", "review", "approved", "superseded"}
# "document" is accepted only so sessions created before the split still validate; new_session.py no longer creates it.
VALID_MODES = {"system", "visual", "prototype", "hardware", "document"}
VALID_APPROVAL_STATUS = {"pending", "approved", "rejected", "not_requested"}
VALID_POSTER_STATUS = {"requested", "approved", "rejected", "not_requested"}
ADVICE_RE = re.compile(r"(下一步建议|建议增加|推荐模块|建议你|建议使用|可以考虑|可考虑|不妨|或许|也许)")
BAD_NEIGHBOR_CLASS_RE = re.compile(r"(?:^|[-_])(description|desc|note|tip|help|explain|advice|recommend|guidance)(?:$|[-_])", re.I)
POSTER_TASK_RE = re.compile(r"海报|poster", re.I)
DESCRIPTIVE_COPY_RE = re.compile(r"说明|解释|建议|提示|备注|详情|方法|流程|步骤|原因|帮助|推荐|指南", re.I)
LABEL_CLASS_RE = re.compile(r"(?:^|[-_])(label|value|legend|axis|pill|unit|number|category)(?:$|[-_])", re.I)
COMMON_MULTI_LABEL_SUFFIXES = frozenset({
    "com.cn", "org.cn", "net.cn", "gov.cn", "edu.cn",
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au",
    "co.jp", "co.nz", "com.hk", "com.tw",
})
NUMERIC_LABEL_RE = re.compile(r"^(?:[—–-]|[¥￥$€£]?\s*[-+]?\d+(?:\.\d+)?\s*(?:%|px|k|万|千|人|次|天|元)?|\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?)$", re.I)
PROSE_TAGS = {"p", "small", "em"}
ALLOWED_CONTENT_CLASSES = {"module-grid", "metrics", "chart", "design-grid", "module-content", "module-board", "table-wrap", "content"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
MODE_REQUIRED = {
    "system": ["01-system/01-module-intake.html", "01-system/02-research.md"],
    "visual": ["02-visual/visual-board.html"],
    "prototype": ["03-prototype/interactive-prototype.html"],
    "hardware": ["04-hardware/plan.json"],
    "document": ["03-documents/document.html"],
}
ARCHITECTURE_PATH = "01-system/03-system-architecture.html"
SYSTEM_DESIGN_PATH = "01-system/04-system-design.html"
LEGACY_SYSTEM_DESIGN_PATH = "01-system/03-system-design.html"
VISUAL_PATH = "02-visual/visual-board.html"
PROTOTYPE_PATH = "03-prototype/interactive-prototype.html"
APPROVAL_ARTIFACTS = {
    "module_scope": "01-system/01-module-intake.html",
    "architecture": ARCHITECTURE_PATH,
    "system_design": SYSTEM_DESIGN_PATH,
    "visual": VISUAL_PATH,
    "prototype": PROTOTYPE_PATH,
}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
DATA_ID_PATTERNS = {
    "data-function-id": re.compile(r"^F-\d{3,}$"),
    "data-page-id": re.compile(r"^P-\d{3,}$"),
    "data-navigation-id": re.compile(r"^N-\d{3,}$"),
    "data-component-id": re.compile(r"^C-\d{3,}$"),
    "data-action-id": re.compile(r"^A-\d{3,}$"),
    "data-entity-id": re.compile(r"^D-\d{3,}$"),
    "data-flow-id": re.compile(r"^FL-\d{3,}$"),
    "data-state-id": re.compile(r"^S-\d{3,}$"),
    "data-integration-id": re.compile(r"^I-\d{3,}$"),
    "data-role-id": re.compile(r"^R-\d{3,}$"),
}
RESEARCH_FIELDS = {
    "source name": "Source name",
    "url": "URL",
    "registrable domain": "Registrable domain",
    "access date": "Access date",
    "http status": "HTTP status",
    "page title": "Page title",
    "luzcrawl task id": "LuzCrawl task ID",
    "luzcrawl status": "LuzCrawl status",
    "evidence category": "Evidence category",
    "visible evidence": "Visible evidence",
    "supported functions": "Supported functions",
    "business flow or module": "Business flow or module",
    "borrowable": "Borrowable",
    "not copyable": "Not copyable",
    "snapshot path": "Snapshot path",
    "snapshot sha256": "Snapshot sha256",
}
# Luz System researches only the frontend: what pages look like, how users move through them, and how
# components show their states. Business rules, regulations and backend behavior belong to Luz Dev.
EVIDENCE_CATEGORIES = {
    "页面结构": "page_structure",
    "page structure": "page_structure",
    "交互流程": "interaction_flow",
    "interaction flow": "interaction_flow",
    "组件状态": "component_state",
    "component state": "component_state",
}
BACKEND_CATEGORIES = {"业务规则", "法规", "接口", "后端", "business rules", "business rule", "regulation", "backend"}
# Evidence reused from the skill's experience library (experience/sources.json) stays valid for this many days.
REUSE_MAX_DAYS = 180
SMALL_ELEMENT_TOKENS = (".mark", ".icon", ".avatar", ".badge", ".pill", ".status", ".chip", ".tag", ".logo", ".corner",
                        ".coin", ".dot", ".kk", ".steps", ".copy i", ".check", ".box", "::before", "::after", "button", "input", "svg",
                        # data marks: checkbox fills, check marks, progress and ranking bar fills, heat-map cells
                        ".cbox", "-mark", "bar i", ".bar-fill", ".rb i", ".heat i", ".progress i")
LUZ_CRAWL_PARTIAL = {"部分", "部分获取", "partial"}
LUZ_CRAWL_OK = {"成功", "完成", "已完成", "success", "succeeded", "complete", "completed", "ok"}
# Frontend architecture only: backend boundaries, interfaces and events belong to Luz Dev.
ARCHITECTURE_SECTIONS = (
    "范围与角色权限", "模块与功能", "页面与路由", "导航树", "组件与动作",
    "交互流程与异常", "界面状态", "页面数据", "追溯矩阵", "验收标准",
)


@dataclass
class Node:
    tag: str
    attrs: dict[str, str | None]
    parent: Node | None = None
    children: list[Node | str] = field(default_factory=list)

    def get(self, name: str, default: str = "") -> str:
        value = self.attrs.get(name)
        return value if value is not None else default


class TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.lower(), {key.lower(): value for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if node.tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.lower(), {key.lower(): value for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def parse_html(path: Path, errors: list[str]) -> Node | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"non-UTF-8 HTML in {path.name}: {exc}")
        return None
    if not re.search(r"<!doctype\s+html>", text, re.I):
        errors.append(f"HTML missing doctype: {path.name}")
    builder = TreeBuilder()
    try:
        builder.feed(text)
        builder.close()
    except Exception as exc:  # HTMLParser raises on malformed declarations.
        errors.append(f"invalid HTML in {path.name}: {exc}")
        return None
    return builder.root


def iter_nodes(node: Node) -> Iterable[Node]:
    for child in node.children:
        if isinstance(child, Node):
            yield child
            yield from iter_nodes(child)


def text_content(node: Node) -> str:
    if node.tag in {"script", "style"}:
        return ""
    parts = []
    for child in node.children:
        parts.append(child if isinstance(child, str) else text_content(child))
    return "".join(parts)


def normalized_visible_text(node: Node) -> str:
    return re.sub(r"\s+", " ", text_content(node)).strip()


def first(root: Node, tag: str, classes: set[str] | None = None) -> Node | None:
    for node in iter_nodes(root):
        classes_value = set(node.get("class").split())
        if node.tag == tag and (classes is None or classes & classes_value):
            return node
    return None


def load_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing {path.name}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path.name}: {exc}")
    return None


def local_links(text: str) -> list[str]:
    targets = LINK_RE.findall(text) + HTML_LINK_RE.findall(text)
    result = []
    for raw in targets:
        target = raw.strip()
        if target.startswith(("<", "'")):
            continue
        target = target.split()[0].strip("<>")
        parsed = urlparse(target)
        if parsed.scheme in {"http", "https", "mailto", "tel", "data"} or target.startswith("#"):
            continue
        result.append(unquote(target.split("#", 1)[0]))
    return [item for item in result if item]


def parse_iso_datetime(value, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty ISO-8601 timestamp")
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        errors.append(f"{label} must be a valid ISO-8601 timestamp")
        return False
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def session_artifact(session: Path, value: str | None, errors: list[str], label: str) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} artifact_path must be a non-empty relative path")
        return None
    path = Path(value)
    if path.is_absolute():
        errors.append(f"{label} artifact_path must stay inside the session")
        return None
    resolved = (session / path).resolve()
    try:
        resolved.relative_to(session.resolve())
    except ValueError:
        errors.append(f"{label} artifact_path escapes the session")
        return None
    if not resolved.is_file():
        errors.append(f"{label} artifact_path does not exist: {value}")
    return resolved


def validate_approval_record(
    session: Path,
    name: str,
    item: object,
    errors: list[str],
    *,
    allow_not_requested: bool = True,
    browser_acceptance: bool = False,
) -> None:
    if not isinstance(item, dict):
        errors.append(f"APPROVALS.json {name} must be an object")
        return
    statuses = VALID_APPROVAL_STATUS if allow_not_requested else VALID_POSTER_STATUS
    status = item.get("status")
    if status not in statuses:
        errors.append(f"APPROVALS.json {name}.status is invalid")
    for key in ("artifact_path", "artifact_sha256", "approved_at", "approved_by", "note"):
        if key not in item:
            errors.append(f"APPROVALS.json {name} missing {key}")
    if browser_acceptance:
        for key in ("browser_acceptance_path", "browser_acceptance_sha256"):
            if key not in item:
                errors.append(f"APPROVALS.json {name} missing {key}")
    if status != "approved":
        return
    approved_by = str(item.get("approved_by") or "").strip()
    if not approved_by:
        errors.append(f"APPROVALS.json {name} approval needs approved_by")
    elif approved_by.casefold() in {"auto", "model", "system", "validator", "script"}:
        errors.append(f"APPROVALS.json {name} cannot be approved by an automatic actor")
    parse_iso_datetime(item.get("approved_at"), f"APPROVALS.json {name}.approved_at", errors)
    artifact = session_artifact(session, item.get("artifact_path"), errors, name)
    approved_hash = str(item.get("artifact_sha256") or "")
    if not SHA256_RE.fullmatch(approved_hash):
        errors.append(f"APPROVALS.json {name}.artifact_sha256 must be a lowercase SHA-256 digest")
    elif artifact and artifact.is_file() and sha256_file(artifact) != approved_hash:
        errors.append(f"APPROVALS.json {name} artifact hash differs from the approved file; downstream work is blocked")
    if browser_acceptance:
        acceptance = session_artifact(session, item.get("browser_acceptance_path"), errors, f"{name} browser acceptance")
        acceptance_hash = str(item.get("browser_acceptance_sha256") or "")
        if not SHA256_RE.fullmatch(acceptance_hash):
            errors.append(f"APPROVALS.json {name}.browser_acceptance_sha256 must be a lowercase SHA-256 digest")
        elif acceptance and acceptance.is_file() and sha256_file(acceptance) != acceptance_hash:
            errors.append(f"APPROVALS.json {name} browser acceptance hash differs from the screenshot")


def validate_approvals(session: Path, errors: list[str]) -> dict | None:
    path = session / "99-delivery" / "APPROVALS.json"
    approvals = load_json(path, errors)
    if approvals is None:
        return None
    required = {"schema_version", "module_scope", "architecture", "system_design", "visual", "prototype", "standalone_poster"}
    missing = sorted(required - set(approvals))
    if missing:
        errors.append("APPROVALS.json missing: " + ", ".join(missing))
    if approvals.get("schema_version") != "2.0":
        errors.append("APPROVALS.json schema_version must be 2.0")

    module_scope = approvals.get("module_scope", {})
    for name in ("module_scope", "architecture", "system_design", "visual"):
        validate_approval_record(session, name, approvals.get(name), errors)
    validate_approval_record(session, "prototype", approvals.get("prototype"), errors, browser_acceptance=True)
    standalone = approvals.get("standalone_poster", {})
    if not isinstance(standalone, dict):
        errors.append("APPROVALS.json standalone_poster must be an object")
    else:
        if standalone.get("status") not in VALID_POSTER_STATUS:
            errors.append("APPROVALS.json standalone_poster.status is invalid")
        if standalone.get("status") == "approved":
            if not str(standalone.get("approved_by") or "").strip():
                errors.append("APPROVALS.json standalone_poster approval needs approved_by")
            parse_iso_datetime(standalone.get("approved_at"), "APPROVALS.json standalone_poster.approved_at", errors)

    if isinstance(module_scope, dict):
        requested = module_scope.get("requested_modules", [])
        selected = module_scope.get("selected_modules", [])
        if not isinstance(requested, list) or len(requested) != len(set(requested)) or not all(isinstance(x, str) and x.strip() for x in requested):
            errors.append("APPROVALS.json module_scope.requested_modules must be a unique string list")
            requested = []
        if not isinstance(selected, list) or len(selected) != len(set(selected)) or not all(isinstance(x, str) and x.strip() for x in selected):
            errors.append("APPROVALS.json module_scope.selected_modules must be a unique string list")
            selected = []
        if module_scope.get("status") == "approved" and not selected:
            errors.append("APPROVALS.json approved module scope needs selected_modules")
        extras = [item for item in selected if requested and item not in requested]
        if extras:
            errors.append("APPROVALS.json selected_modules contains modules absent from the requested form: " + ", ".join(extras))
    return approvals if isinstance(approvals, dict) else None

def css_text(root: Node) -> str:
    chunks = []
    for node in iter_nodes(root):
        if node.tag == "style":
            chunks.append(text_content_direct(node))
        style = node.get("style")
        if style:
            chunks.append(style)
    return "\n".join(chunks)


def text_content_direct(node: Node) -> str:
    return "".join(child for child in node.children if isinstance(child, str))


def css_variables(style: str) -> dict[str, str]:
    return {match.group(1): match.group(2).strip() for match in re.finditer(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;}{]+)", style)}


def resolve_css_value(value: str, variables: dict[str, str], seen: set[str] | None = None) -> str:
    seen = set() if seen is None else seen
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in seen or name not in variables:
            return ""
        seen.add(name)
        value = variables[name]
        value = re.sub(r"var\((--[A-Za-z0-9_-]+)(?:\s*,\s*([^\)]+))?\)", lambda inner: inner.group(2) if inner.group(1) not in variables and inner.group(2) else resolve_css_value("var(" + inner.group(1) + ")", variables, seen), value)
        return resolve_css_value(value, variables, seen.copy())
    return re.sub(r"var\((--[A-Za-z0-9_-]+)(?:\s*,\s*([^\)]+))?\)", replace, value)


def parse_color_tokens(value: str) -> list[tuple[int, int, int]]:
    colors: list[tuple[int, int, int]] = []
    for raw in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", value):
        raw = raw[1:]
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        colors.append(tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4)))
    for match in re.finditer(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*[,/]\s*([\d.]+)(%?))?", value, re.I):
        alpha = match.group(4)
        if alpha is not None:
            # Translucent scrims and shadows (alpha below 0.5) are overlays, not dark surfaces.
            opacity = float(alpha) / (100 if match.group(5) else 1)
            if opacity < 0.5:
                continue
        colors.append(tuple(max(0, min(255, int(match.group(i)))) for i in (1, 2, 3)))
    if re.search(r"\bwhite\b", value, re.I):
        colors.append((255, 255, 255))
    return colors


def relative_luminance(color: tuple[int, int, int]) -> float:
    values = [value / 255 for value in color]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def size_violations(style: str, min_px: float = 14.0) -> list[str]:
    variables = css_variables(style)
    findings = []
    declarations = []
    for match in re.finditer(r"(?:font-size|font)\s*:\s*([^;}{]+)", style, re.I):
        declarations.append(("declaration", match.group(1)))
    for match in re.finditer(r"""font-size\s*=\s*["']([^"']+)""", style, re.I):
        declarations.append(("attribute", match.group(1)))
    for kind, raw in declarations:
        value = resolve_css_value(raw, variables)
        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(px|rem|em|%)", value, re.I):
            number = float(match.group(1))
            unit = match.group(2).lower()
            minimum = min_px if unit == "px" else min_px / 16 if unit in {"rem", "em"} else min_px / 16 * 100
            if number < minimum:
                findings.append(f"font size {match.group(0)} is below {min_px:g}px in a {kind}")
    return findings


def validate_html_top_contract(root: Node, label: str, errors: list[str]) -> None:
    body = first(root, "body")
    if body is None:
        errors.append(f"{label} is missing body")
        return
    h1s = [node for node in iter_nodes(body) if node.tag == "h1"]
    if len(h1s) != 1:
        errors.append(f"{label} must contain exactly one visible h1")
        return
    h1 = h1s[0]

    def first_visible_content(container: Node) -> Node | str | None:
        for child in container.children:
            if isinstance(child, str):
                if child.strip():
                    return child
                continue
            if child.tag in {"script", "style", "template"}:
                continue
            if child.tag == "h1":
                return child
            direct_text = " ".join(part for part in child.children if isinstance(part, str)).strip()
            has_visible_descendant = any(
                node.tag not in {"script", "style", "template"} and normalized_visible_text(node)
                for node in iter_nodes(child)
            )
            if child.tag in {"main", "article", "div"} and not direct_text and has_visible_descendant:
                result = first_visible_content(child)
                if result is not None:
                    return result
            if normalized_visible_text(child) or child.tag in {"header", "aside", "nav", "section", "img", "button"}:
                return child
        return None

    first_content = first_visible_content(body)
    if first_content is not h1:
        tag = first_content.tag if isinstance(first_content, Node) else "text"
        errors.append(f"{label} has visible content before its unique h1: {tag}")
    parent = h1.parent
    if parent is None:
        errors.append(f"{label} h1 has no parent container")
        return
    siblings = meaningful_nodes(parent.children)
    try:
        index = next(i for i, item in enumerate(siblings) if item is h1)
    except StopIteration:
        errors.append(f"{label} h1 is not in normal document order")
        return
    if index != 0:
        errors.append(f"{label} h1 must be the first visible child of its content container")
    if index + 1 >= len(siblings) or not isinstance(siblings[index + 1], Node) or siblings[index + 1].tag != "section":
        errors.append(f"{label} h1 must be followed directly by the first section")
        return
    first_section = siblings[index + 1]
    section_first = first_visible_content(first_section)
    if not isinstance(section_first, Node) or section_first.tag != "h2":
        errors.append(f"{label} first section must begin with h2 and no title-adjacent copy")
    for node in iter_nodes(body):
        if node.tag != "h2":
            continue
        title = normalized_visible_text(node)
        if re.search(r"来源记录|数据来源|采集日期|证据状态", title):
            errors.append(f"{label} must keep source, capture date, and evidence status outside delivery HTML")


def validate_light_html(path: Path, errors: list[str], min_px: float = 14.0) -> Node | None:
    root = parse_html(path, errors)
    if root is None:
        return None
    validate_html_top_contract(root, path.name, errors)
    body = first(root, "body")
    if body is None:
        errors.append(f"{path.name} is missing body")
        return root
    style = css_text(root)
    if re.search(r"color-scheme\s*:\s*dark", style, re.I):
        errors.append(f"{path.name} must use a light color scheme")
    for finding in size_violations(style, min_px):
        errors.append(f"{path.name}: {finding}")
    variables = css_variables(style)
    for match in re.finditer(r"background(?:-color)?\s*:\s*([^;}{]+)", style, re.I):
        resolved = resolve_css_value(match.group(1), variables)
        dark = [color for color in parse_color_tokens(resolved) if relative_luminance(color) < 0.25]
        if dark:
            opening = style.rfind("{", 0, match.start())
            selector = style[style.rfind("}", 0, opening) + 1:opening].split("@media")[-1] if opening >= 0 else ""
            selector = selector.strip().casefold()
            # Solid colour is allowed on elements smaller than a line of text (Luz-Design visual-design.html, 配色): marks, icons,
            # avatars, badges, chips, tags, logos, corner labels, step pills, coins, pseudo-element bars and controls.
            small_control = any(token in selector for token in SMALL_ELEMENT_TOKENS)
            if not small_control:
                errors.append(f"{path.name} contains a dark background color: {match.group(1).strip()}")
    body_rules = []
    for match in re.finditer(r"(?:(?:html|body)(?:\s*,\s*(?:html|body))?)\s*\{([^{}]*)\}", style, re.I):
        body_rules.append(match.group(1))
    light_backgrounds = []
    for rule in body_rules:
        for match in re.finditer(r"background(?:-color)?\s*:\s*([^;}{]+)", rule, re.I):
            resolved = resolve_css_value(match.group(1), variables)
            light_backgrounds.extend(relative_luminance(color) for color in parse_color_tokens(resolved))
    if light_backgrounds and max(light_backgrounds) < 0.7:
        errors.append(f"{path.name} body background must be white or light")
    visible = normalized_visible_text(body)
    advice = ADVICE_RE.search(visible)
    if advice:
        errors.append(f"{path.name} contains unrequested advisory copy: {advice.group(0)}")
    return root


def parse_module_form(session: Path, approvals: dict | None, errors: list[str]) -> tuple[str | None, list[str]]:
    path = session / "01-system" / "01-module-intake.html"
    if not path.is_file():
        return None, []
    root = validate_light_html(path, errors)
    if root is None or root is None:
        return None, []
    main = first(root, "main")
    if main is None or main.get("data-artifact") != "module-intake":
        errors.append('module intake must declare data-artifact="module-intake"')
        return None, []
    system_name = main.get("data-system-name").strip()
    headings = [node for node in iter_nodes(root) if node.tag == "h1"]
    if len(headings) != 1:
        errors.append("module intake must have exactly one system-name h1")
    elif normalized_visible_text(headings[0]) != system_name:
        errors.append("module intake h1 must exactly match data-system-name")
    checkbox_values = []
    for node in iter_nodes(root):
        if node.tag == "input":
            if node.get("type").lower() != "checkbox":
                errors.append("module intake may contain only checkbox inputs")
            value = node.get("data-module").strip() or node.get("value").strip()
            if not value:
                errors.append("module intake checkbox is missing a module name")
            else:
                checkbox_values.append(value)
        if node.tag in {"button", "select", "textarea"}:
            errors.append(f"module intake must not contain <{node.tag}> controls")
    if len(checkbox_values) != len(set(checkbox_values)):
        errors.append("module intake has duplicate module checkboxes")
    if not checkbox_values:
        errors.append("module intake must list at least one requested module")
    expected_text = " ".join([system_name, "模块选择", *checkbox_values]).strip()
    actual_text = normalized_visible_text(main)
    remainder = actual_text
    for item in [system_name, "模块选择", *checkbox_values]:
        if item:
            remainder = remainder.replace(item, "", 1)
    if remainder.strip():
        errors.append("module intake contains visible text beyond the system name and requested module names")
    svg_nodes = [node for node in iter_nodes(root) if node.tag == "svg"]
    linear_svgs = [node for node in svg_nodes if node.get("fill").lower() == "none" or any(desc.get("fill").lower() == "none" for desc in iter_nodes(node))]
    if len(linear_svgs) < len(checkbox_values):
        errors.append("module intake needs one linear SVG icon per module")
    if approvals:
        requested = approvals.get("module_scope", {}).get("requested_modules", [])
        if requested != checkbox_values:
            errors.append("module intake checkbox order/list must exactly match APPROVALS requested_modules")
        selected = approvals.get("module_scope", {}).get("selected_modules", [])
        extra = [item for item in selected if item not in checkbox_values]
        if extra:
            errors.append("approved module list contains a module absent from the intake: " + ", ".join(extra))
    return system_name, checkbox_values


def sibling_items(node: Node) -> list[Node | str]:
    if node.parent is None:
        return []
    return node.parent.children


def direct_visible_text(node: Node) -> str:
    return re.sub(r"\s+", " ", text_content_direct(node)).strip()


def meaningful_nodes(children: list[Node | str]) -> list[Node | str]:
    return [
        child for child in children
        if isinstance(child, Node) or child.strip()
    ]


def visual_only(node: Node | str) -> bool:
    if not isinstance(node, Node) or normalized_visible_text(node):
        return False
    return any(desc.tag in {"svg", "img", "canvas"} for desc in iter_nodes(node))


def chart_label_is_allowed(text: str, classes: str) -> bool:
    if not text:
        return True
    if ADVICE_RE.search(text) or DESCRIPTIVE_COPY_RE.search(text):
        return False
    if len(text) > 32 or re.search(r"[。！？!?；;]", text):
        return False
    if NUMERIC_LABEL_RE.fullmatch(text):
        return True
    return bool(LABEL_CLASS_RE.search(classes))


def title_copy_failure(node: Node) -> str | None:
    for desc in [node, *iter_nodes(node)]:
        if desc.tag in {"script", "style", "svg"}:
            continue
        if any(parent.tag == "svg" for parent in ancestors(desc)):
            continue
        text = direct_visible_text(desc)
        if not text:
            continue
        classes = desc.get("class")
        if desc.tag in PROSE_TAGS:
            return f"<{desc.tag}> explanatory text"
        if BAD_NEIGHBOR_CLASS_RE.search(classes):
            return "description-like element"
        if desc.tag in {"span", "div", "strong", "th", "td", "li"}:
            if not chart_label_is_allowed(text, classes):
                return f"text-bearing <{desc.tag}>"
            continue
        return "free text"
    return None


def ancestors(node: Node) -> Iterable[Node]:
    current = node.parent
    while current is not None:
        yield current
        current = current.parent


def check_title_neighbors(heading: Node, errors: list[str]) -> None:
    parent = heading.parent
    if parent is None:
        return
    if "module-head" not in parent.get("class").split():
        errors.append("module title must be inside a module-head container")
        return
    siblings = parent.children
    index = siblings.index(heading)
    before = meaningful_nodes(siblings[:index])
    after = meaningful_nodes(siblings[index + 1:])
    if after:
        errors.append("module title has disallowed adjacent content inside module-head")
    for candidate in before:
        if not visual_only(candidate):
            errors.append("module title has disallowed adjacent text before the heading")
    if parent.parent is None:
        return
    parent_siblings = parent.parent.children
    parent_index = parent_siblings.index(parent)
    previous = meaningful_nodes(parent_siblings[:parent_index])
    following = meaningful_nodes(parent_siblings[parent_index + 1:])
    if previous:
        nearest = previous[-1]
        if isinstance(nearest, str) or normalized_visible_text(nearest):
            errors.append("module title has disallowed adjacent copy before its content region")
    if not following or not isinstance(following[0], Node):
        errors.append("module title must be followed directly by an explicit content region")
        return
    content = following[0]
    classes = set(content.get("class").split())
    if not classes & ALLOWED_CONTENT_CLASSES:
        errors.append("module title is followed by an unapproved content region")
        return
    reason = title_copy_failure(content)
    if reason:
        errors.append(f"module title content region contains disallowed adjacent {reason}")


def check_system_h1_neighbors(heading: Node, errors: list[str]) -> None:
    if heading.parent is None:
        return
    siblings = meaningful_nodes(heading.parent.children)
    seen_heading = False
    seen_section = False
    for candidate in siblings:
        if candidate is heading:
            seen_heading = True
            continue
        if not seen_heading:
            errors.append("system h1 must be the first visible content")
            continue
        if isinstance(candidate, Node) and candidate.tag == "section":
            seen_section = True
            continue
        reason = "free text" if isinstance(candidate, str) else title_copy_failure(candidate)
        if reason:
            errors.append(f"system h1 has disallowed accompanying {reason}")
    if not seen_section:
        errors.append("system h1 must be followed by a section")

def system_design_file(session: Path) -> Path | None:
    current = session / SYSTEM_DESIGN_PATH
    if current.is_file():
        return current
    legacy = session / LEGACY_SYSTEM_DESIGN_PATH
    return legacy if legacy.is_file() else None


def validate_system_design(
    session: Path,
    system_name: str | None,
    modules: list[str],
    errors: list[str],
    *,
    approved_ids: dict[str, set[str]] | None = None,
) -> None:
    path = system_design_file(session)
    if path is None:
        return
    root = validate_light_html(path, errors)
    if root is None:
        return
    main = first(root, "main")
    if main is None or main.get("data-artifact") not in {"system-design", ""}:
        errors.append('system-design must declare data-artifact="system-design"')
    h1s = [node for node in iter_nodes(root) if node.tag == "h1"]
    h2s = [node for node in iter_nodes(root) if node.tag == "h2"]
    h3s = [node for node in iter_nodes(root) if node.tag == "h3"]
    if system_name and (len(h1s) != 1 or normalized_visible_text(h1s[0]) != system_name):
        errors.append("system-design h1 must exactly match the requested system name")
    for heading in h1s:
        check_system_h1_neighbors(heading, errors)
    if h3s:
        errors.append("system-design h3 headings are not allowed")
    headings = []
    for heading in h2s:
        if "module-title" not in heading.get("class").split():
            errors.append("every system-design h2 must be an approved module-title")
            continue
        headings.append(heading)
    title_map = {}
    for heading in headings:
        module = heading.get("data-module").strip()
        actual = re.sub(r"\s+", " ", normalized_visible_text(heading))
        expected = f"{module}介绍，{module}设计"
        if actual != expected:
            errors.append(f"system-design module title must be exactly '{expected}', got '{actual}'")
        title_map[module] = title_map.get(module, 0) + 1
        check_title_neighbors(heading, errors)
    extras = sorted(set(title_map) - set(modules))
    missing = sorted(set(modules) - set(title_map))
    duplicates = sorted(module for module, count in title_map.items() if count != 1)
    if extras:
        errors.append("system-design includes unapproved module titles: " + ", ".join(extras))
    if missing:
        errors.append("system-design is missing module titles: " + ", ".join(missing))
    if duplicates:
        errors.append("system-design repeats module titles: " + ", ".join(duplicates))
    for node in iter_nodes(root):
        module = node.get("data-module").strip()
        if module and module not in modules:
            errors.append(f"system-design references unapproved module: {module}")
            break
    if approved_ids is not None:
        for attr, pattern in DATA_ID_PATTERNS.items():
            for node in iter_nodes(root):
                value = node.get(attr).strip()
                if not value:
                    continue
                if not pattern.fullmatch(value):
                    errors.append(f"system-design has invalid {attr}: {value}")
                elif value not in approved_ids.get(attr, set()):
                    errors.append(f"system-design references unapproved {attr}: {value}")
    body = first(root, "body")
    if body and ADVICE_RE.search(normalized_visible_text(body)):
        errors.append("system-design contains unrequested advisory copy")
    svg_nodes = [node for node in iter_nodes(root) if node.tag == "svg"]
    linear_svgs = [node for node in svg_nodes if node.get("fill").lower() == "none" or any(desc.get("fill").lower() == "none" for desc in iter_nodes(node))]
    if len(linear_svgs) < len(modules):
        errors.append("system-design needs multiple linear SVG icons")

def strip_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def parse_research(path: Path) -> list[dict[str, str]]:
    text = strip_html_comments(path.read_text(encoding="utf-8"))
    parts = re.split(r"^### (REF-\d{3,})\s*$", text, flags=re.M)
    records = []
    for index in range(1, len(parts), 2):
        record = {"id": parts[index]}
        for line in parts[index + 1].splitlines():
            match = re.match(r"^\s*-\s*([^:]+):\s*(.*)$", line)
            if match:
                record[match.group(1).strip().casefold()] = match.group(2).strip()
        records.append(record)
    return records


def fetch_source_status(url: str) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": "LuzSystemValidator/1.0"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return int(response.status)


def poster_brief_has_evidence(session: Path) -> bool:
    path = session / "BRIEF.md"
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    for line in text.splitlines():
        match = re.match(r"^\s*-\s*(Session|Request summary|Primary outcome|Task description):\s*(.+?)\s*$", line, re.I)
        if match and POSTER_TASK_RE.search(match.group(2)):
            return True
    return False


def _registrable_domain(hostname: str | None) -> str | None:
    host = (hostname or "").strip().strip(".").casefold()
    if not host or host == "localhost" or host == "invalid" or host.endswith(".invalid"):
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    labels = host.split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        return None
    suffix = ".".join(labels[-2:])
    if suffix in COMMON_MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:]) if len(labels) >= 3 else None
    return ".".join(labels[-2:])


def parse_brief_requirements(session: Path, errors: list[str]) -> list[dict[str, str]]:
    path = session / "BRIEF.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    header = None
    for index, line in enumerate(lines):
        if line.strip().startswith("|") and re.search(r"(Requirement ID|需求编号)", line, re.I):
            header = index
            break
    if header is None:
        errors.append("BRIEF.md needs a Requirement ID table before architecture work")
        return []
    columns = [cell.strip().casefold() for cell in lines[header].strip().strip("|").split("|")]
    aliases = {
        "id": ("requirement id", "需求编号"),
        "request": ("user request (verbatim)", "用户原文"),
        "module": ("module", "模块"),
        "signal": ("acceptance signal", "验收信号"),
    }
    positions: dict[str, int] = {}
    for key, names in aliases.items():
        for name in names:
            if name.casefold() in columns:
                positions[key] = columns.index(name.casefold())
                break
    missing_columns = [key for key in aliases if key not in positions]
    if missing_columns:
        errors.append("BRIEF.md requirement table is missing: " + ", ".join(missing_columns))
        return []
    requirements: list[dict[str, str]] = []
    seen = set()
    for line in lines[header + 2:]:
        if not line.strip().startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) <= max(positions.values()):
            errors.append("BRIEF.md requirement row has too few cells")
            continue
        item = {key: cells[index] for key, index in positions.items()}
        req_id = item["id"]
        if not re.fullmatch(r"REQ-\d{3,}", req_id):
            if req_id or any(item.values()):
                errors.append(f"BRIEF.md has invalid requirement ID: {req_id or 'empty'}")
            continue
        if req_id in seen:
            errors.append(f"BRIEF.md repeats requirement ID: {req_id}")
        seen.add(req_id)
        for key in ("request", "module", "signal"):
            if not item[key]:
                errors.append(f"BRIEF.md {req_id} missing {key}")
        requirements.append(item)
    if not requirements:
        errors.append("BRIEF.md requirement ledger must contain at least one completed REQ row")
    return requirements


def split_ids(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，;；\s]+", value or "") if item.strip()]


def validate_research(
    session: Path,
    selected_modules: list[str],
    errors: list[str],
    live_check: bool = False,
    source_checker: Callable[[str], int] | None = None,
    checked_on: date | None = None,
    allow_live_crawl_offline: bool = False,
) -> list[dict[str, str]]:
    path = session / "01-system" / "02-research.md"
    if not path.is_file():
        return []
    records = parse_research(path)
    domains: set[str] = set()
    urls: set[str] = set()
    task_ids: set[str] = set()
    categories: dict[str, int] = {"page_structure": 0, "interaction_flow": 0, "component_state": 0}
    for record in records:
        ref = record.get("id", "REF")
        for key, label in RESEARCH_FIELDS.items():
            if not record.get(key, "").strip():
                errors.append(f"research {ref} missing {label}")
        url = record.get("url", "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"research {ref} URL must be an absolute HTTP(S) URL")
            registrable = None
        else:
            # Hash-routed documentation sites (#/route) serve different pages per fragment; plain anchors do not.
            route_fragment = parsed.fragment if parsed.fragment.startswith(("/", "!/")) else ""
            normalized = parsed._replace(fragment=route_fragment).geturl().rstrip("/")
            if normalized in urls:
                errors.append(f"research {ref} repeats an earlier URL")
            urls.add(normalized)
            registrable = _registrable_domain(parsed.hostname)
            if registrable is None:
                errors.append(f"research {ref} URL must use an identifiable public registrable domain")
            else:
                domains.add(registrable)
                recorded_domain = record.get("registrable domain", "").strip().casefold()
                if recorded_domain != registrable:
                    errors.append(f"research {ref} registrable domain must be {registrable}")
        access = record.get("access date", "").strip()
        try:
            access_day = date.fromisoformat(access)
            if access_day > date.today():
                errors.append(f"research {ref} Access date cannot be in the future")
            if record.get("reused from", "").strip() and (date.today() - access_day).days > REUSE_MAX_DAYS:
                errors.append(f"research {ref} reuses evidence older than {REUSE_MAX_DAYS} days; crawl it again")
        except ValueError:
            errors.append(f"research {ref} Access date must be YYYY-MM-DD")
        status = record.get("http status", "").strip()
        if not re.fullmatch(r"[23]\d{2}", status):
            errors.append(f"research {ref} HTTP status must record a 2xx or 3xx response")
        task_id = record.get("luzcrawl task id", "").strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{5,}", task_id):
            errors.append(f"research {ref} needs a real LuzCrawl task ID")
        elif task_id.casefold() in task_ids:
            errors.append(f"research {ref} repeats LuzCrawl task ID {task_id}")
        else:
            task_ids.add(task_id.casefold())
        crawl_status = record.get("luzcrawl status", "").strip().casefold()
        partial_ok = False
        if crawl_status in LUZ_CRAWL_PARTIAL:
            # A partial crawl counts only when its own LuzCrawl record confirms the target content was read.
            snapshot_file = session / record.get("snapshot path", "").strip()
            try:
                captured = json.loads(snapshot_file.read_text(encoding="utf-8"))
                partial_ok = bool(captured.get("url_check", {}).get("valid_content"))
            except (OSError, ValueError, AttributeError):
                partial_ok = False
            if not partial_ok:
                errors.append(f"research {ref} partial crawl needs its LuzCrawl content.json snapshot with valid_content true")
        elif crawl_status not in LUZ_CRAWL_OK:
            errors.append(f"research {ref} LuzCrawl status must record a successful crawl")
        raw_category = record.get("evidence category", "").strip().casefold()
        category = EVIDENCE_CATEGORIES.get(raw_category)
        if raw_category in BACKEND_CATEGORIES:
            errors.append(f"research {ref} is backend or regulatory evidence; it belongs to Luz Dev, not Luz System")
        elif category is None:
            errors.append(f"research {ref} evidence category must be 页面结构, 交互流程, or 组件状态")
        else:
            categories[category] += 1
        applicable = record.get("business flow or module", "").strip()
        if applicable and applicable not in {"全部模块", "all"}:
            if selected_modules and not any(module in applicable for module in selected_modules):
                errors.append(f"research {ref} does not identify an approved module or business flow")
        snapshot_value = record.get("snapshot path", "").strip()
        snapshot = session_artifact(session, snapshot_value, errors, f"research {ref} snapshot")
        snapshot_hash = record.get("snapshot sha256", "").strip().casefold()
        if not SHA256_RE.fullmatch(snapshot_hash):
            errors.append(f"research {ref} snapshot sha256 must be a lowercase SHA-256 digest")
        elif snapshot and snapshot.is_file() and sha256_file(snapshot) != snapshot_hash:
            errors.append(f"research {ref} snapshot hash differs from the captured evidence")
    if len(urls) < 12:
        errors.append(f"research needs at least 12 unique sources; found {len(urls)}")
    if len(domains) < 5:
        errors.append(f"research needs at least 5 different registrable domains; found {len(domains)}")
    if categories["page_structure"] < 3:
        errors.append("research needs at least 3 page-structure sources")
    if categories["interaction_flow"] < 3:
        errors.append("research needs at least 3 interaction-flow sources")
    if categories["component_state"] < 2:
        errors.append("research needs at least 2 component-state sources")
    if live_check and not allow_live_crawl_offline:
        checker = source_checker or fetch_source_status
        verification_day = (checked_on or date.today()).isoformat()
        for record in records:
            ref = record.get("id", "REF")
            url = record.get("url", "").strip()
            if not url:
                continue
            hostname = (urlparse(url).hostname or "").casefold()
            if hostname == "invalid" or hostname.endswith(".invalid"):
                errors.append(f"research {ref} URL uses the non-resolvable .invalid domain")
                continue
            try:
                actual_status = int(checker(url))
            except Exception as exc:
                errors.append(f"research {ref} URL is not accessible: {exc}")
                continue
            if not 200 <= actual_status < 400:
                errors.append(f"research {ref} URL is not accessible: HTTP {actual_status}")
                continue
            recorded_status = record.get("http status", "").strip()
            if recorded_status != str(actual_status):
                errors.append(f"research {ref} HTTP status record {recorded_status or 'missing'} differs from live HTTP {actual_status}")
            recorded_day = record.get("access date", "").strip()
            if recorded_day != verification_day and not record.get("reused from", "").strip():
                errors.append(f"research {ref} access date {recorded_day or 'missing'} differs from live check date {verification_day}")
    return records


def collect_stable_ids(root: Node, errors: list[str], label: str) -> dict[str, set[str]]:
    ids = {attr: set() for attr in DATA_ID_PATTERNS}
    for node in iter_nodes(root):
        for attr, pattern in DATA_ID_PATTERNS.items():
            value = node.get(attr).strip()
            if not value:
                continue
            if not pattern.fullmatch(value):
                errors.append(f"{label} has invalid {attr}: {value}")
                continue
            if value in ids[attr] and attr not in {"data-page-id", "data-component-id"}:
                errors.append(f"{label} repeats {attr}: {value}")
            ids[attr].add(value)
    return ids


def validate_architecture(
    session: Path,
    system_name: str | None,
    modules: list[str],
    requirements: list[dict[str, str]],
    research: list[dict[str, str]],
    errors: list[str],
    *,
    approved: bool = False,
) -> dict[str, set[str]]:
    empty = {attr: set() for attr in DATA_ID_PATTERNS}
    path = session / ARCHITECTURE_PATH
    if not path.is_file():
        return empty
    root = validate_light_html(path, errors)
    if root is None:
        return empty
    main = first(root, "main")
    if main is None or main.get("data-artifact") != "system-architecture":
        errors.append('system-architecture must declare data-artifact="system-architecture"')
    h1s = [node for node in iter_nodes(root) if node.tag == "h1"]
    if system_name and (len(h1s) != 1 or normalized_visible_text(h1s[0]) != system_name):
        errors.append("system-architecture h1 must exactly match the requested system name")
    headings = [normalized_visible_text(node) for node in iter_nodes(root) if node.tag == "h2"]
    for section in ARCHITECTURE_SECTIONS:
        if not any(section in heading for heading in headings):
            errors.append(f"system-architecture missing section: {section}")
    ids = collect_stable_ids(root, errors, "system-architecture")
    for required in ("data-function-id", "data-page-id", "data-navigation-id", "data-component-id", "data-action-id", "data-entity-id", "data-flow-id", "data-state-id"):
        if not ids[required]:
            errors.append(f"system-architecture needs at least one {required}")
    if len(ids["data-function-id"]) < max(1, len(modules)):
        errors.append("system-architecture needs at least one function per approved module")
    requirement_ids = {item["id"] for item in requirements}
    research_ids = {record.get("id", "") for record in research}
    covered_requirements: set[str] = set()
    covered_modules: set[str] = set()
    for node in iter_nodes(root):
        function_id = node.get("data-function-id").strip()
        if not function_id:
            continue
        module = node.get("data-module").strip()
        if module not in modules:
            errors.append(f"architecture function {function_id} references unapproved module: {module or 'missing'}")
        else:
            covered_modules.add(module)
        source = node.get("data-source").strip()
        if source == "用户要求":
            reqs = set(split_ids(node.get("data-req-ids")))
            if not reqs:
                errors.append(f"architecture function {function_id} needs REQ-IDs")
            missing_req = sorted(reqs - requirement_ids)
            if missing_req:
                errors.append(f"architecture function {function_id} references unknown requirements: {', '.join(missing_req)}")
            covered_requirements.update(reqs)
        elif source == "调研推断待确认":
            refs = set(split_ids(node.get("data-ref-ids")))
            if len(refs) < 2:
                errors.append(f"research-inferred function {function_id} needs at least two REF-IDs")
            missing_refs = sorted(refs - research_ids)
            if missing_refs:
                errors.append(f"research-inferred function {function_id} references unknown research: {', '.join(missing_refs)}")
            if approved:
                errors.append(f"approved architecture still contains unconfirmed function {function_id}")
        else:
            errors.append(f"architecture function {function_id} needs data-source 用户要求 or 调研推断待确认")
    missing_modules = sorted(set(modules) - covered_modules)
    if missing_modules:
        errors.append("architecture has no function for approved modules: " + ", ".join(missing_modules))
    missing_requirements = sorted(requirement_ids - covered_requirements)
    if missing_requirements:
        errors.append("architecture does not trace user requirements: " + ", ".join(missing_requirements))
    for node in iter_nodes(root):
        module = node.get("data-module").strip()
        if module and module not in modules:
            errors.append(f"system-architecture references unapproved module: {module}")
            break
    for node in iter_nodes(root):
        page_id = node.get("data-page-id").strip()
        if node.get("data-navigation-id") and page_id not in ids["data-page-id"]:
            errors.append(f"architecture navigation references unknown page: {page_id or 'missing'}")
        if node.get("data-component-id") and page_id not in ids["data-page-id"]:
            errors.append(f"architecture component references unknown page: {page_id or 'missing'}")
        action_id = node.get("data-action-id").strip()
        if action_id:
            component_id = node.get("data-component-id").strip()
            if component_id not in ids["data-component-id"]:
                errors.append(f"architecture action {action_id} references unknown component")
            functions = set(split_ids(node.get("data-function-ids")))
            if not functions or functions - ids["data-function-id"]:
                errors.append(f"architecture action {action_id} references unknown function")
        flow_id = node.get("data-flow-id").strip()
        if flow_id and not node.get("data-exception").strip():
            errors.append(f"architecture flow {flow_id} needs an exception and recovery rule")
    # Every approved module shows at least one interface state; the subjects come from the project, not a fixed list.
    state_nodes = [node for node in iter_nodes(root) if node.get("data-state-id")]
    for node in state_nodes:
        if not node.get("data-state-subject").strip():
            errors.append(f"architecture state {node.get('data-state-id')} needs data-state-subject")
    for module in modules:
        if not any(module in (node.get("data-module"), node.get("data-state-subject")) or module in node.get("data-state-subject") for node in state_nodes):
            errors.append(f"system-architecture needs an interface state for module {module}")
    return ids


def validate_visual(
    path: Path,
    modules: list[str],
    approved_ids: dict[str, set[str]],
    errors: list[str],
) -> None:
    root = validate_light_html(path, errors)
    if root is None:
        return
    main = first(root, "main")
    if main is None or main.get("data-artifact") != "visual-board":
        errors.append('visual-board must declare data-artifact="visual-board"')
    for node in iter_nodes(root):
        module = node.get("data-module").strip()
        if module and module not in modules:
            errors.append(f"visual board adds unapproved module: {module}")
        for attr in DATA_ID_PATTERNS:
            value = node.get(attr).strip()
            if value and value not in approved_ids.get(attr, set()):
                errors.append(f"visual board references unapproved {attr}: {value}")


# Interface detail rules (references/ui-standards.html and admin-design.html): a page title must not repeat the
# highlighted navigation item, a navigation group must not repeat its only item, a table column that is empty in the
# current data is hidden, and interface body text is at least 14px. 12–13px is allowed only on elements whose selector
# or class marks them as auxiliary; this is the naming convention prototypes follow.
AUXILIARY_TEXT_RE = re.compile(
    r"(?:^|[-_.#\s])(meta|hint|time|date|unit|badge|tag|chip|pill|axis|legend|tick|caption|aux|corner|dot|count|kbd)(?:$|[-_\s:.\[>+~)])",
    re.I,
)
# Selectors whose text is read as content. A bare element selector (table cells, paragraphs, form labels and
# controls, list items, body) below 14px is an error; any other non-auxiliary selector below 14px is a warning.
BODY_TEXT_TAG_RE = re.compile(r"^(?:td|th|p|label|li|body|html|table|input|textarea|select|dd|dt)(?![\w-])", re.I)
ACTIVE_CLASS_RE = re.compile(r"(?:^|[-_\s])(active|current|selected|is-active|on)(?:$|[-_\s])", re.I)
GROUP_CLASS_RE = re.compile(r"group", re.I)
GROUP_LABEL_CLASS_RE = re.compile(r"title|label|head|name", re.I)
EMPTY_CELL_VALUES = {"", "—", "–", "-", "--", "——", "/"}
SNAKE_OR_LATIN_HEADER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$|[a-z0-9]+_[a-z0-9_]+")


def _is_inside(node: Node, tags: set[str]) -> bool:
    return any(parent.tag in tags or parent.get("role") == "navigation" for parent in ancestors(node))


def _classes(node: Node) -> str:
    return node.get("class")


def _label_text(node: Node) -> str:
    # Navigation and title comparison ignores whitespace and trailing counts ("订单 12").
    return re.sub(r"\d+$", "", re.sub(r"\s+", "", normalized_visible_text(node)))


def _css_rules(style: str) -> list[tuple[str, str, bool]]:
    """Innermost (selector, declarations, inside an at-rule such as @media) triples."""
    rules = []
    clean = re.sub(r"/\*.*?\*/", "", style, flags=re.S)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean):
        selector = match.group(1).strip()
        if selector.startswith("@"):
            continue
        before = clean[:match.start()]
        rules.append((selector, match.group(2), before.count("{") > before.count("}")))
    return rules


def _font_px(declarations: str, variables: dict[str, str]) -> float | None:
    size = None
    for match in re.finditer(r"(font-size|font)\s*:\s*([^;}{]+)", declarations, re.I):
        value = resolve_css_value(match.group(2), variables)
        if match.group(1).lower() == "font":
            value = value.split("/", 1)[0]
        number = re.search(r"(\d+(?:\.\d+)?)\s*(px|rem)\b", value, re.I)
        if number:
            size = float(number.group(1)) * (16 if number.group(2).lower() == "rem" else 1)
    return size


def _horizontal_padding_px(declarations: str, variables: dict[str, str]) -> float | None:
    """Smallest left/right padding in px; values in other units are not judged."""
    def px(token: str) -> float | None:
        if token == "0":
            return 0.0
        return float(token[:-2]) if re.fullmatch(r"\d+(?:\.\d+)?px", token) else None

    smallest = None
    for match in re.finditer(r"padding(-left|-right|-inline)?\s*:\s*([^;}{]+)", declarations, re.I):
        parts = resolve_css_value(match.group(2), variables).replace("!important", "").split()
        if not parts:
            continue
        if match.group(1) in {"-left", "-right"}:
            horizontal = parts[:1]
        elif match.group(1) == "-inline":
            horizontal = parts[:2]
        else:
            horizontal = [parts[0]] if len(parts) == 1 else [parts[1]] if len(parts) < 4 else [parts[1], parts[3]]
        for value in (px(token) for token in horizontal):
            if value is not None:
                smallest = value if smallest is None else min(smallest, value)
    return smallest


def prototype_ui_findings(root: Node) -> tuple[list[str], list[str]]:
    """Interface detail checks on a prototype; returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    body = first(root, "body") or root
    nodes = list(iter_nodes(body))

    # 1. Page title repeats the highlighted navigation item.
    nav_items = [
        node for node in nodes
        if node.tag in {"a", "button", "li"} and _is_inside(node, {"nav", "aside"}) and _label_text(node)
    ]
    headings = [
        node for node in nodes
        if (node.tag in {"h1", "h2"} or re.search(r"page-title", _classes(node)))
        and not _is_inside(node, {"nav", "aside"})
    ]
    for item in nav_items:
        text = _label_text(item)
        active = (item.get("aria-current") not in {"", "false"}) or bool(ACTIVE_CLASS_RE.search(_classes(item)))
        target = item.get("data-page-id").strip() or item.get("href").lstrip("#")
        repeated = None
        if target:
            for container in nodes:
                if container.tag in {"a", "button"} or _is_inside(container, {"nav", "aside"}):
                    continue
                if target not in {container.get("data-page-id"), container.get("id")}:
                    continue
                inner = next((n for n in iter_nodes(container)
                              if n.tag in {"h1", "h2", "h3"} or re.search(r"page-title", _classes(n))), None)
                if inner is not None and _label_text(inner) == text:
                    repeated = text
                    break
        if active and repeated is None:
            repeated = next((text for heading in headings if _label_text(heading) == text), None)
        if repeated:
            errors.append(f"interactive-prototype page title repeats the highlighted navigation item: {repeated}")

    # 2. A navigation group named the same as its only item.
    for group in nodes:
        if not _is_inside(group, {"nav", "aside"}):
            continue
        if not (group.get("role") == "group" or GROUP_CLASS_RE.search(_classes(group)) or group.tag == "details"):
            continue
        label_node = next((n for n in iter_nodes(group)
                           if n.tag in {"h3", "h4", "h5", "h6", "dt", "summary", "strong"}
                           or (GROUP_LABEL_CLASS_RE.search(_classes(n)) and n.tag not in {"a", "button"})), None)
        label = re.sub(r"\s+", "", group.get("aria-label")) or (_label_text(label_node) if label_node is not None else "")
        items = [n for n in iter_nodes(group) if n.tag in {"a", "button"}
                 and (label_node is None or n is not label_node and label_node not in ancestors(n))]
        if label and len(items) == 1 and _label_text(items[0]) == label:
            errors.append(f"interactive-prototype navigation group repeats its only item: {label}")

    # 3. Table columns: all empty is an error, all identical (5+ rows) is a warning.
    for table in (n for n in nodes if n.tag == "table"):
        if any(p.get("data-state-kind") or re.search(r"skeleton|loading", _classes(p)) for p in [table, *ancestors(table)]):
            continue
        headers = [normalized_visible_text(th) for th in iter_nodes(table) if th.tag == "th"]
        rows = []
        for tr in (n for n in iter_nodes(table) if n.tag == "tr"):
            cells = [c for c in tr.children if isinstance(c, Node) and c.tag == "td"]
            if cells and not any(c.get("colspan") for c in cells):
                rows.append(cells)
        if not rows:
            continue
        width = max(len(r) for r in rows)
        rows = [r for r in rows if len(r) == width]
        for col in range(width):
            cells = [r[col] for r in rows]
            values = [normalized_visible_text(c) for c in cells]
            rich = any(any(d.tag in {"img", "svg", "input", "button", "select", "a", "textarea"} for d in iter_nodes(c)) for c in cells)
            name = headers[col] if col < len(headers) else str(col + 1)
            if len(rows) >= 2 and not rich and all(v in EMPTY_CELL_VALUES for v in values):
                errors.append(f"interactive-prototype table column is empty in every row (hide it in column settings): {name}")
            elif len(rows) >= 5 and not rich and "操作" not in name and len(set(values)) == 1 and values[0] not in EMPTY_CELL_VALUES:
                warnings.append(f"interactive-prototype table column has the same value in every row (state it once in the filter summary): {name}")
        # Export previews show cleaned Chinese headers, never field names.
        if any("data-export-preview" in p.attrs or re.search(r"export", _classes(p)) for p in [table, *ancestors(table)]):
            for header in headers:
                if SNAKE_OR_LATIN_HEADER_RE.search(header):
                    errors.append(f"interactive-prototype export preview header is a field name, not Chinese business wording: {header}")

    # 4. Interface text below 14px outside auxiliary elements; 5. table cell side padding below 16px.
    style = css_text(root)
    variables = css_variables(style)
    for selector, declarations, in_at_rule in _css_rules(style):
        size = _font_px(declarations, variables)
        for part in (s.strip() for s in selector.split(",")):
            if not part:
                continue
            last = re.split(r"\s*[>+~]\s*|\s+", part)[-1]
            # Pseudo-elements (mobile card column names, markers) and chart/SVG text follow their own rules.
            decorative = "::" in last or any(token in part.lower() for token in ("svg", "chart"))
            if size is not None and 12 <= size < 14 and not decorative and not AUXILIARY_TEXT_RE.search(part):
                message = f"interactive-prototype interface text {size:g}px below 14px on a non-auxiliary selector: {part}"
                (errors if BODY_TEXT_TAG_RE.match(last) else warnings).append(message)
            selection_cell = re.search(r"\.(?:ck|chk|check|sel|select)", last, re.I)
            # Responsive overrides (narrow-screen card rows) are not judged for cell padding.
            if re.match(r"(?:td|th)(?![\w-])", last, re.I) and "::" not in last and not selection_cell and not in_at_rule:
                padding = _horizontal_padding_px(declarations, variables)
                if padding is not None and padding < 16:
                    warnings.append(f"interactive-prototype table cell side padding {padding:g}px below 16px: {part}")
    for node in nodes:
        inline = node.get("style")
        if not inline:
            continue
        size = _font_px(inline, variables)
        if size is not None and 12 <= size < 14 and not AUXILIARY_TEXT_RE.search(" " + _classes(node)):
            message = f"interactive-prototype inline text {size:g}px below 14px on <{node.tag}> without an auxiliary class"
            (errors if node.tag in {"td", "th", "p", "label", "li"} else warnings).append(message)
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


# List pagination (admin-design.html 分页), the browser-tab icon and the header brand mark (ui-standards.html 页头;
# Luz-Design visual-design.html 网页图标与品牌标识). The same checks run in Luz-Design check_document.py --allow interface.
PAGER_CLASS_RE = re.compile(r"pagination|pager", re.I)
LIST_CLASS_RE = re.compile(r"list|table", re.I)
PAGE_SIZE_TEXT_RE = re.compile(r"(\d+)\s*条\s*/\s*页")
TOTAL_TEXT_RE = re.compile(r"共\s*[\d,]+\s*条")
SKIP_TABLE_RE = re.compile(r"skeleton|loading|export|modal|dialog|detail|popover|tooltip|legend", re.I)
SHELL_CLASS_RE = re.compile(r"(?:^|[-_\s])(?:header|topbar|top-bar|navbar|nav-bar|appbar|app-bar|masthead|sidebar|side-bar|"
                            r"site-head|site-header|admin|console)(?:$|[-_\s])", re.I)
PHONE_CLASS_RE = re.compile(r"(?:^|[-_\s])(?:mp|phone|mobile|miniprogram|mini-program|wx|device|screen-phone)(?:$|[-_\s])", re.I)
BRAND_CLASS_RE = re.compile(r"logo|brand", re.I)
ICON_DRAWING_RE = re.compile(r"<(?:path|rect|circle|line|polyline|polygon|ellipse)\b", re.I)
DEFAULT_PAGE_SIZE = 20


def tab_icon_errors(root: Node, label: str) -> list[str]:
    """Every delivered HTML carries an inline browser-tab icon; missing, empty or an unfilled placeholder is an error."""
    from base64 import b64decode
    from urllib.parse import unquote
    hint = ('add <link rel="icon" href="data:image/svg+xml,..."> (py -X utf8 scripts/new_session.py icon <system name>; '
            "Luz-Design visual-design.html 网页图标与品牌标识)")
    links = [n.get("href").strip() for n in iter_nodes(root) if n.tag == "link" and "icon" in n.get("rel").lower()]
    if not links:
        return [f"{label} has no browser-tab icon: {hint}"]
    for href in links:
        if not href or href in {"#", "about:blank"} or "{{" in href or re.fullmatch(r"data:[^,]*,\s*", href, re.I):
            continue
        if href.lower().startswith("data:") and "svg" in href.split(",", 1)[0].lower():
            meta, payload = href[5:].split(",", 1)
            try:
                svg = b64decode(payload).decode("utf-8", "replace") if ";base64" in meta.lower() else unquote(payload)
            except ValueError:
                svg = ""
            if not ICON_DRAWING_RE.search(svg):
                continue
        return []
    return [f"{label} browser-tab icon is empty or an unfilled placeholder: {hint}"]


def _default_page_size(scope: Node) -> int | None:
    for node in [scope, *iter_nodes(scope)]:
        for attr in ("data-page-size", "data-default-size", "data-size"):
            if node.get(attr).strip().isdigit():
                return int(node.get(attr).strip())
    for select in (n for n in iter_nodes(scope) if n.tag == "select"):
        options = [o for o in iter_nodes(select) if o.tag == "option"]
        sized = [o for o in options if PAGE_SIZE_TEXT_RE.search(text_content(o)) or o.get("value").strip() in {"10", "20", "50", "100"}]
        if not sized:
            continue
        chosen = next((o for o in sized if "selected" in o.attrs), sized[0])
        if chosen.get("value").strip().isdigit():
            return int(chosen.get("value").strip())
        match = PAGE_SIZE_TEXT_RE.search(text_content(chosen))
        if match:
            return int(match.group(1))
    match = PAGE_SIZE_TEXT_RE.search(text_content(scope))
    return int(match.group(1)) if match else None


def prototype_list_brand_findings(root: Node) -> list[str]:
    """Warnings: a list table without pagination, a default page size other than 20, an admin or website header without a
    graphic brand mark. Only the static DOM is seen; a list that can never exceed one page carries data-pagination="none"."""
    warnings: list[str] = []
    body = first(root, "body") or root
    nodes = [n for n in iter_nodes(body) if not any(a.tag in {"template", "script"} for a in ancestors(n))]

    def chain(node: Node) -> list[Node]:
        return [node, *ancestors(node)]

    def data_rows(table: Node) -> int:
        return sum(1 for tr in iter_nodes(table) if tr.tag == "tr"
                   and next((a for a in ancestors(tr) if a.tag == "table"), None) is table
                   and not any(a.tag == "thead" for a in ancestors(tr))
                   and any(isinstance(c, Node) and c.tag == "td" for c in tr.children))

    lists = []
    for table in (n for n in nodes if n.tag == "table"):
        if any(a.get("data-pagination").lower() in {"none", "off", "false"} or "data-state-kind" in a.attrs
               or "data-export-preview" in a.attrs or "hidden" in a.attrs or SKIP_TABLE_RE.search(_classes(a)) for a in chain(table)):
            continue
        parent_class = _classes(table.parent) if table.parent is not None else ""
        if LIST_CLASS_RE.search(_classes(table)) or LIST_CLASS_RE.search(parent_class) or data_rows(table) >= 10:
            lists.append(table)
    pagers = [n for n in nodes if PAGER_CLASS_RE.search(_classes(n))]
    page_text = text_content(body)
    text_pager = bool(TOTAL_TEXT_RE.search(page_text) and PAGE_SIZE_TEXT_RE.search(page_text))
    if lists and not pagers and not text_pager:
        sample = _classes(lists[0]) or (_classes(lists[0].parent) if lists[0].parent is not None else "")
        warnings.append(f"interactive-prototype list table without pagination ({len(lists)} list table(s)"
                        f"{', e.g. class ' + repr(sample) if sample else ''}): add 共 N 条, a 10/20/50/100 条/页 selector and page "
                        'numbers below the table, default 20; mark a list that can never exceed one page with data-pagination="none"')
    sizes = {_default_page_size(p) for p in pagers} if pagers else ({_default_page_size(body)} if text_pager else set())
    for size in sorted(s for s in sizes if s is not None and s != DEFAULT_PAGE_SIZE):
        warnings.append(f"interactive-prototype pagination defaults to {size} 条/页: default to {DEFAULT_PAGE_SIZE} "
                        "(options 10/20/50/100) and remember the user's choice")
    shells = [n for n in nodes if (n.tag in {"header", "aside"} or SHELL_CLASS_RE.search(_classes(n)))
              and not any(PHONE_CLASS_RE.search(_classes(a)) for a in chain(n))]
    if shells:
        holders = [n for n in nodes if n.tag == "header" or BRAND_CLASS_RE.search(_classes(n))]
        if not any(h.tag in {"svg", "img"} or any(d.tag in {"svg", "img"} for d in iter_nodes(h)) for h in holders):
            warnings.append("interactive-prototype admin or website header without a graphic brand mark: put the tab-icon "
                            "pictogram (svg or img) beside the system name in a header, logo or brand element, never a letter tile")
    return warnings


def validate_prototype(
    session: Path,
    modules: list[str],
    approved_ids: dict[str, set[str]],
    architecture_hash: str | None,
    errors: list[str],
    warnings: list[str] | None = None,
) -> None:
    path = session / PROTOTYPE_PATH
    if not path.is_file():
        return
    # Prototypes render real interfaces; nothing below 12px (Luz-Design visual-design.html 字体与字号).
    root = validate_light_html(path, errors, min_px=12.0)
    if root is None:
        return
    main = first(root, "main")
    if main is None or main.get("data-artifact") != "interactive-prototype":
        errors.append('interactive-prototype must declare data-artifact="interactive-prototype"')
    if architecture_hash and main and main.get("data-architecture-sha256") != architecture_hash:
        errors.append("interactive-prototype is not bound to the approved architecture hash")
    buttons = [node for node in iter_nodes(root) if node.tag == "button"]
    if not buttons:
        errors.append("interactive-prototype needs at least one button")
    for index, node in enumerate(buttons, 1):
        action_id = node.get("data-action-id").strip()
        if not action_id:
            errors.append(f"interactive-prototype button {index} is missing data-action-id")
        elif action_id not in approved_ids.get("data-action-id", set()):
            errors.append(f"interactive-prototype button {index} references unapproved action: {action_id}")
        page_id = node.get("data-page-id").strip()
        if not page_id or page_id not in approved_ids.get("data-page-id", set()):
            errors.append(f"interactive-prototype button {index} references an unapproved page")
    states = {node.get("data-state-kind").strip().casefold() for node in iter_nodes(root) if node.get("data-state-kind").strip()}
    for state in ("加载", "空", "错误", "成功", "禁用"):
        if state.casefold() not in states and state == "空":
            if "empty" not in states:
                errors.append(f"interactive-prototype missing {state} state")
        elif state.casefold() not in states:
            errors.append(f"interactive-prototype missing {state} state")
    if not any(node.get("data-fixture-id") or node.get("data-demo-data") for node in iter_nodes(root)):
        errors.append("interactive-prototype needs explicit simulated data")
    for node in iter_nodes(root):
        module = node.get("data-module").strip()
        if module and module not in modules:
            errors.append(f"interactive-prototype adds unapproved module: {module}")
        for attr in DATA_ID_PATTERNS:
            value = node.get(attr).strip()
            if value and value not in approved_ids.get(attr, set()):
                errors.append(f"interactive-prototype references unapproved {attr}: {value}")
    svg_nodes = [node for node in iter_nodes(root) if node.tag == "svg"]
    if not any(node.get("fill").lower() == "none" or any(desc.get("fill").lower() == "none" for desc in iter_nodes(node)) for node in svg_nodes):
        errors.append("interactive-prototype needs a linear SVG icon")
    ui_errors, ui_warnings = prototype_ui_findings(root)
    errors.extend(ui_errors)
    if warnings is not None:
        warnings.extend(ui_warnings)
        warnings.extend(prototype_list_brand_findings(root))

def validate(
    session: Path,
    strict: bool = False,
    live_sources: bool = False,
    source_checker: Callable[[str], int] | None = None,
    checked_on: date | None = None,
    allow_live_crawl_offline: bool = False,
    warnings: list[str] | None = None,
) -> list[str]:
    """Return blocking errors; non-blocking findings are appended to ``warnings`` when a list is given."""
    errors: list[str] = []
    if not session.is_dir():
        return [f"session folder does not exist: {session}"]
    folder = session
    session = work_dir(folder)
    for item in folder.iterdir():
        if item.name not in {RAW_DIR, final_html(folder).name}:
            errors.append(f"session folder may only contain {final_html(folder).name} and {RAW_DIR}/; found {item.name}")
    if not session.is_dir():
        return errors + [f"missing {RAW_DIR}/ working folder"]
    match = SESSION_RE.match(folder.name)
    if not match:
        errors.append("session folder must start with a zero-padded number and a title")
    if not (session / "BRIEF.md").is_file():
        errors.append("missing BRIEF.md")
    if not (session / "99-delivery").is_dir():
        errors.append("missing 99-delivery/")
    if not (session / "01-system" / "01-module-intake.html").is_file() and (session / "01-system").exists():
        errors.append("system mode requires 01-system/01-module-intake.html")

    manifest = load_json(session / "99-delivery" / "MANIFEST.json", errors)
    approvals = validate_approvals(session, errors)
    if not (session / "99-delivery" / "APPROVALS.json").is_file():
        errors.append("missing APPROVALS.json")

    if manifest:
        required = {"schema_version", "session_id", "sequence", "folder", "title", "created_at", "session_kind", "status", "modes", "approvals_file", "stages", "deliverables", "assumptions", "verification", "notes"}
        missing = sorted(required - set(manifest))
        if missing:
            errors.append("MANIFEST.json missing: " + ", ".join(missing))
        if manifest.get("schema_version") != "2.0":
            errors.append("MANIFEST.json schema_version must be 2.0")
        if manifest.get("status") not in VALID_STATUS:
            errors.append("MANIFEST.json has an invalid status")
        if manifest.get("session_kind") not in {"general", "system", "standalone_poster"}:
            errors.append("MANIFEST.json has an invalid session_kind")
        if manifest.get("folder") != folder.name:
            errors.append("MANIFEST.json folder does not match directory name")
        final = final_html(folder)
        record = manifest.get("final") or {}
        if final.is_file():
            source = session / str(record.get("source", ""))
            actual = sha256_file(final)
            if not record:
                errors.append(f"{final.name} exists but MANIFEST.json has no final record; publish it with scripts/publish.py")
            elif record.get("sha256") != actual:
                errors.append(f"{final.name} differs from its published hash; republish it with scripts/publish.py")
            elif not source.is_file() or sha256_file(source) != actual:
                errors.append(f"{final.name} no longer matches its source {record.get('source')}; republish it")
            final_root = parse_html(final, errors)
            if final_root is not None:
                errors.extend(tab_icon_errors(final_root, final.name))
        elif record:
            errors.append(f"MANIFEST.json records a final HTML but {final.name} is missing")
        expected_title = folder.name.split("-", 1)[1] if "-" in folder.name else ""
        if expected_title and manifest.get("title") != expected_title:
            errors.append("MANIFEST.json title differs from the folder title")
        sid = SESSION_ID_RE.match(str(manifest.get("session_id", "")))
        if not sid:
            errors.append("MANIFEST.json session_id must match SES-NNN")
        elif match:
            expected_sequence = int(match.group(1))
            if int(sid.group(1)) != expected_sequence:
                errors.append("MANIFEST.json session_id sequence differs from folder sequence")
            if manifest.get("sequence") != expected_sequence:
                errors.append("MANIFEST.json sequence differs from folder sequence")
        try:
            datetime.fromisoformat(str(manifest.get("created_at", "")))
        except ValueError:
            errors.append("MANIFEST.json created_at must be ISO-8601")
        requested_modules = manifest.get("requested_modules", [])
        if not isinstance(requested_modules, list) or len(requested_modules) != len(set(requested_modules)) or not all(isinstance(item, str) and item.strip() for item in requested_modules):
            errors.append("MANIFEST.json requested_modules must be a unique string list")
            requested_modules = []
        system_name = manifest.get("system_name") if isinstance(manifest.get("system_name"), str) else None
        if manifest.get("session_kind") == "system" and (not isinstance(system_name, str) or not system_name.strip()):
            errors.append("system session MANIFEST.json needs system_name")
        if manifest.get("approvals_file") != "99-delivery/APPROVALS.json":
            errors.append("MANIFEST.json approvals_file must be 99-delivery/APPROVALS.json")
        modes = manifest.get("modes", [])
        if not isinstance(modes, list) or len(modes) != len(set(modes)):
            errors.append("MANIFEST.json modes must be a unique list")
            modes = []
        unknown = set(modes) - VALID_MODES
        if unknown:
            errors.append("unknown modes: " + ", ".join(sorted(unknown)))
        if manifest.get("session_kind") == "system" and "system" not in modes:
            errors.append("a system session must declare system mode")
        if manifest.get("session_kind") == "standalone_poster" and "system" in modes:
            errors.append("a standalone poster session cannot declare system mode")

        stages = manifest.get("stages", {})
        expected_stages = {"module_scope", "research", "architecture", "system_design", "visual", "prototype"}
        if not isinstance(stages, dict):
            errors.append("MANIFEST.json stages must be an object")
            stages = {}
        else:
            missing_stages = sorted(expected_stages - set(stages))
            if missing_stages:
                errors.append("MANIFEST.json stages missing: " + ", ".join(missing_stages))
            expected_paths = {
                "module_scope": "01-system/01-module-intake.html",
                "research": "01-system/02-research.md",
                "architecture": ARCHITECTURE_PATH,
                "system_design": SYSTEM_DESIGN_PATH,
                "visual": VISUAL_PATH,
                "prototype": PROTOTYPE_PATH,
            }
            for name, expected_path in expected_paths.items():
                item = stages.get(name)
                if not isinstance(item, dict):
                    if name in stages:
                        errors.append(f"MANIFEST.json stages.{name} must be an object")
                    continue
                if item.get("path") != expected_path:
                    errors.append(f"MANIFEST.json stages.{name}.path must be {expected_path}")
                if "sha256" not in item or "approval" not in item:
                    errors.append(f"MANIFEST.json stages.{name} needs sha256 and approval")
                staged_hash = item.get("sha256")
                if staged_hash not in {None, ""}:
                    if not SHA256_RE.fullmatch(str(staged_hash)):
                        errors.append(f"MANIFEST.json stages.{name}.sha256 is invalid")
                    else:
                        artifact = session / expected_path
                        if artifact.is_file() and sha256_file(artifact) != staged_hash:
                            errors.append(f"MANIFEST.json stages.{name} hash differs from the artifact")

        mode_dirs = {"system": "01-system", "visual": "02-visual", "prototype": "03-prototype", "hardware": "04-hardware", "document": "03-documents"}
        for mode in modes:
            folder = mode_dirs.get(mode)
            if folder and not (session / folder).is_dir():
                errors.append(f"{mode} mode is declared but {folder}/ is missing")
            for rel in MODE_REQUIRED.get(mode, []):
                if not (session / rel).is_file():
                    errors.append(f"{mode} mode missing required file: {rel}")

        deliverables = manifest.get("deliverables", [])
        if not isinstance(deliverables, list):
            errors.append("MANIFEST.json deliverables must be a list")
            deliverables = []
        ids = set()
        per_mode = {mode: 0 for mode in VALID_MODES}
        for index, item in enumerate(deliverables, 1):
            if not isinstance(item, dict):
                errors.append(f"deliverable {index} must be an object")
                continue
            required_item = {"id", "title", "mode", "path", "format", "status"}
            missing_item = sorted(required_item - set(item))
            if missing_item:
                errors.append(f"deliverable {index} missing: {', '.join(missing_item)}")
                continue
            if not DELIVERABLE_ID_RE.match(str(item["id"])):
                errors.append(f"deliverable {index} has invalid id")
            if item["id"] in ids:
                errors.append(f"duplicate deliverable id: {item['id']}")
            ids.add(item["id"])
            if item.get("mode") not in VALID_MODES:
                errors.append(f"deliverable {index} has invalid mode")
            else:
                per_mode[item["mode"]] += 1
            if item.get("status") not in VALID_STATUS:
                errors.append(f"deliverable {index} has invalid status")
            rel = Path(str(item.get("path", "")))
            if rel.is_absolute():
                errors.append(f"deliverable {index} path must be relative: {rel}")
            else:
                resolved = (session / rel).resolve()
                try:
                    resolved.relative_to(session.resolve())
                except ValueError:
                    errors.append(f"deliverable {index} path escapes session: {rel}")
                else:
                    if not resolved.exists():
                        errors.append(f"deliverable {index} path does not exist: {rel}")

        assumptions = manifest.get("assumptions", [])
        if not isinstance(assumptions, list):
            errors.append("MANIFEST.json assumptions must be a list")
            assumptions = []
        assume_ids = set()
        for index, item in enumerate(assumptions, 1):
            if not isinstance(item, dict):
                errors.append(f"assumption {index} must be an object")
                continue
            if not ASSUMPTION_ID_RE.match(str(item.get("id", ""))):
                errors.append(f"assumption {index} has invalid id")
            if item.get("id") in assume_ids:
                errors.append(f"duplicate assumption id: {item.get('id')}")
            assume_ids.add(item.get("id"))
            if item.get("status") not in {"open", "resolved", "accepted"}:
                errors.append(f"assumption {index} has invalid status")
            if not str(item.get("text", "")).strip():
                errors.append(f"assumption {index} has empty text")
        verification = manifest.get("verification", [])
        if not isinstance(verification, list):
            errors.append("MANIFEST.json verification must be a list")
            verification = []
        for index, item in enumerate(verification, 1):
            if not isinstance(item, dict):
                errors.append(f"verification {index} must be an object")
                continue
            if item.get("result") not in {"pass", "fail", "pending"}:
                errors.append(f"verification {index} has invalid result")
            if not str(item.get("check", "")).strip():
                errors.append(f"verification {index} has empty check")

        form_system, form_modules = parse_module_form(session, approvals, errors)
        if system_name and form_system and system_name != form_system:
            errors.append("MANIFEST.json system_name differs from the module intake")
        selected = approvals.get("module_scope", {}).get("selected_modules", []) if approvals else []
        if not isinstance(selected, list):
            selected = []
        module_approved = bool(approvals and approvals.get("module_scope", {}).get("status") == "approved")
        architecture_approved = bool(approvals and approvals.get("architecture", {}).get("status") == "approved")
        system_approved = bool(approvals and approvals.get("system_design", {}).get("status") == "approved")
        visual_approved = bool(approvals and approvals.get("visual", {}).get("status") == "approved")
        prototype_approved = bool(approvals and approvals.get("prototype", {}).get("status") == "approved")
        poster_session = manifest.get("session_kind") == "standalone_poster"
        architecture_path = session / ARCHITECTURE_PATH
        design_path = system_design_file(session)

        if architecture_approved and not module_approved:
            errors.append("architecture cannot be approved before module_scope approval")
        if system_approved and not architecture_approved:
            errors.append("system_design cannot be approved before architecture approval")
        if visual_approved and not system_approved:
            errors.append("visual cannot be approved before system_design approval")
        if prototype_approved and not visual_approved:
            errors.append("prototype cannot be approved before visual approval")
        if architecture_approved and not architecture_path.is_file():
            errors.append(f"approved architecture requires {ARCHITECTURE_PATH}")
        if system_approved and design_path is None:
            errors.append("approved system_design requires a system design HTML")
        if visual_approved and not (session / VISUAL_PATH).is_file():
            errors.append(f"approved visual requires {VISUAL_PATH}")
        if prototype_approved and not (session / PROTOTYPE_PATH).is_file():
            errors.append(f"approved prototype requires {PROTOTYPE_PATH}")

        requirements: list[dict[str, str]] = []
        research: list[dict[str, str]] = []
        approved_ids = {attr: set() for attr in DATA_ID_PATTERNS}
        if module_approved:
            requirements = parse_brief_requirements(session, errors)
            extras = [item["id"] for item in requirements if item.get("module") not in selected]
            if extras:
                errors.append("BRIEF requirements name modules outside the approved scope: " + ", ".join(extras))
            missing_module_reqs = sorted(set(selected) - {item.get("module") for item in requirements})
            if missing_module_reqs:
                errors.append("BRIEF has no REQ row for approved modules: " + ", ".join(missing_module_reqs))
            research = validate_research(session, selected, errors, live_sources, source_checker, checked_on, allow_live_crawl_offline)
        if architecture_path.is_file():
            if not module_approved:
                errors.append("system-architecture HTML exists before module_scope approval")
            if not requirements:
                requirements = parse_brief_requirements(session, errors)
            if not research:
                research = parse_research(session / "01-system" / "02-research.md")
            approved_ids = validate_architecture(session, system_name, selected, requirements, research, errors, approved=architecture_approved)
        if design_path is not None:
            if not architecture_approved:
                errors.append("system-design HTML exists before architecture approval")
            validate_system_design(session, system_name, selected, errors, approved_ids=approved_ids)
        if (session / VISUAL_PATH).is_file() and not poster_session:
            validate_visual(session / VISUAL_PATH, selected, approved_ids, errors)
        if (session / PROTOTYPE_PATH).is_file():
            architecture_hash = approvals.get("architecture", {}).get("artifact_sha256") if approvals else None
            validate_prototype(session, selected, approved_ids, architecture_hash, errors, warnings)

        if (session / "02-visual").exists() and not poster_session:
            if not architecture_approved or not system_approved:
                errors.append("visual artifacts require approved architecture and system design")
        if poster_session and not poster_brief_has_evidence(session):
            errors.append("standalone poster BRIEF must record an explicit user poster task")
        if (session / "02-visual").exists() and "visual" not in modes and not poster_session:
            errors.append("visual artifacts exist but visual mode is not declared")
        if (session / "03-prototype").exists() and "prototype" not in modes:
            errors.append("prototype artifacts exist but prototype mode is not declared")

        if strict:
            if manifest.get("status") == "draft":
                errors.append("strict: draft session cannot be handed off or published")
            if not verification:
                errors.append("strict: at least one verification record is required")
            for mode in modes:
                if per_mode.get(mode, 0) == 0:
                    errors.append(f"strict: no deliverable is recorded for {mode} mode")
            if any(item.get("result") != "pass" for item in verification if isinstance(item, dict)):
                errors.append("strict: every verification result must be pass")
            for name in ("module_scope", "architecture", "system_design", "visual", "prototype"):
                item = stages.get(name) if isinstance(stages, dict) else None
                if isinstance(item, dict) and not item.get("sha256"):
                    errors.append(f"strict: MANIFEST.json stages.{name}.sha256 is required")
            if manifest.get("status") == "approved":
                open_items = [item for item in assumptions if isinstance(item, dict) and item.get("status") == "open"]
                if open_items:
                    errors.append("strict: approved session still has open assumptions")
                if any(item.get("status") != "approved" for item in deliverables if isinstance(item, dict)):
                    errors.append("strict: approved session contains non-approved deliverables")
                if modes and not poster_session and not system_approved:
                    errors.append("strict: approved system session lacks system_design approval")

    for path in session.rglob("*.html"):
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        # Prototypes render interfaces (12px annotations allowed); every other page keeps the 14px floor.
        validate_light_html(path, errors, min_px=12.0 if "03-prototype" in path.parts else 14.0)
    for path in session.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".html"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"non-UTF-8 text file: {path.relative_to(session)}")
            continue
        for target in local_links(text):
            if not (path.parent / target).resolve().exists():
                errors.append(f"broken local link in {path.relative_to(session)}: {target}")
    if strict:
        brief = session / "BRIEF.md"
        if brief.is_file() and len(brief.read_text(encoding="utf-8").strip()) < 200:
            errors.append("strict: BRIEF.md is not sufficiently completed")
        for path in session.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"\b(?:TODO|TBD|FIXME)\b", text):
                errors.append(f"strict: unresolved marker in {path.relative_to(session)}")
    return list(dict.fromkeys(errors))

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Luz System session.")
    parser.add_argument("session", help="Path to the numbered session folder")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--check-sources", action="store_true", help="Fetch every recorded research URL")
    parser.add_argument("--strict-production", action="store_true", help="Enforce strict structure and live source verification")
    args = parser.parse_args(argv)
    strict = args.strict or args.strict_production
    live_sources = args.check_sources or args.strict_production
    session = Path(args.session).resolve()
    warnings: list[str] = []
    errors = validate(session, strict=strict, live_sources=live_sources, warnings=warnings)
    for warning in dict.fromkeys(warnings):
        print("WARN", warning)
    if errors:
        print(f"FAIL: {len(errors)} issue(s)")
        for error in errors:
            print("ERROR", error)
        return 1
    mode = "production" if args.strict_production else "session"
    print(f"PASS ({mode}): session is valid: {session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
