from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from add_mode import add_mode
from new_session import read_template, create_session, fill_icon_slots
from validate_session import parse_html, validate, validate_html_top_contract
from validate_skill import validate_rule_page

MODULES = ["订单", "支付", "预约", "履约", "库存", "优惠券"]
SYSTEM_NAME = "订餐系统"
REQUIREMENTS = [f"REQ-{index:03d}" for index in range(1, len(MODULES) + 1)]
DOMAINS = ["alpha.example", "beta.example", "gamma.example", "delta.example", "omega.example"]

def tool_root(temp: str) -> Path:
    root = Path(temp) / "sessions"
    root.mkdir()
    return root

def make_system(root: Path) -> Path:
    return create_session(
        root, "订餐系统", ["system"], skill_root=ROOT, session_kind="system",
        system_name=SYSTEM_NAME, modules=MODULES,
    )

def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def write_requirements(session: Path) -> None:
    rows = [
        "| Requirement ID | User request (verbatim) | Module | Acceptance signal |",
        "|---|---|---|---|",
    ]
    for req, module in zip(REQUIREMENTS, MODULES):
        rows.append(f"| {req} | 用户要求设计{module}功能 | {module} | 端到端验收通过 |")
    path = session / "raw" / "BRIEF.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\| Requirement ID \|[\s\S]*?(?=\n\n## Users)", "\n".join(rows), text, count=1)
    path.write_text(text, encoding="utf-8")

def approve_module(session: Path) -> None:
    path = session / "raw" / "01-system" / "01-module-intake.html"
    approvals_path = session / "raw" / "99-delivery" / "APPROVALS.json"
    data = read_json(approvals_path)
    data["module_scope"].update({
        "status": "approved", "selected_modules": MODULES,
        "artifact_sha256": digest(path), "approved_by": "测试用户",
        "approved_at": now(), "note": "模块范围确认",
    })
    write_json(approvals_path, data)

def approve_artifact(session: Path, name: str, relative: str, acceptance: str | None = None) -> None:
    path = session / "raw" / "99-delivery" / "APPROVALS.json"
    data = read_json(path)
    item = data[name]
    item.update({
        "status": "approved", "artifact_path": relative,
        "artifact_sha256": digest(session / "raw" / relative),
        "approved_by": "测试用户", "approved_at": now(), "note": "人工确认",
    })
    if acceptance:
        item.update({
            "browser_acceptance_path": acceptance,
            "browser_acceptance_sha256": digest(session / "raw" / acceptance),
        })
    write_json(path, data)

def write_research(session: Path, *, omit_tasks: bool = False) -> None:
    snaps = session / "raw" / "01-system" / "crawl-snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    categories = ["页面结构", "页面结构", "页面结构", "交互流程", "交互流程", "交互流程", "组件状态", "组件状态"]
    blocks = ["# Research", ""]
    for index in range(12):
        ref = f"REF-{index + 1:03d}"
        task = f"LC-TEST-{index + 1:03d}"
        snapshot = snaps / f"{task}.md"
        snapshot.write_text(f"# {ref}\n\n已实际读取的页面证据。\n", encoding="utf-8")
        domain = DOMAINS[index % len(DOMAINS)]
        module = MODULES[index % len(MODULES)]
        blocks.extend([
            f"### {ref}",
            f"- Source name: 来源{index + 1}",
            f"- URL: https://{domain}/source/{index + 1}",
            f"- Registrable domain: {domain}",
            f"- Access date: {date.today().isoformat()}",
            "- HTTP status: 200",
            f"- Page title: 页面标题{index + 1}",
            f"- LuzCrawl task ID: {'LC-TEST-MISSING' if omit_tasks else task}",
            "- LuzCrawl status: 成功",
            f"- Evidence category: {categories[index % len(categories)]}",
            "- Visible evidence: 可见的流程、状态和异常恢复证据",
            f"- Supported functions: F-{index + 1:03d}",
            f"- Business flow or module: {module}",
            "- Borrowable: 信息结构和状态组织",
            "- Not copyable: 品牌、文案、图像和独占布局",
            f"- Snapshot path: {snapshot.relative_to(session / "raw").as_posix()}",
            f"- Snapshot sha256: {digest(snapshot)}",
            "",
        ])
    (session / "raw" / "01-system" / "02-research.md").write_text("\n".join(blocks), encoding="utf-8")

def write_architecture(session: Path) -> None:
    text = read_template(ROOT, "system-architecture.html")
    text = fill_icon_slots(text, SYSTEM_NAME).replace("{{SYSTEM_NAME}}", SYSTEM_NAME).replace("{{MODULE}}", MODULES[0])
    extras = []
    for index, (req, module) in enumerate(zip(REQUIREMENTS[1:], MODULES[1:]), 2):
        extras.append(f'<div class="node" data-function-id="F-{index:03d}" data-module="{module}" data-source="用户要求" data-req-ids="{req}">{module}功能</div>')
    text = text.replace('</div></section>\n<section id="pages">', ''.join(extras) + '</div></section>\n<section id="pages">', 1)
    states = ''.join(f'<div class="node" data-state-id="S-{index:03d}" data-module="{module}" data-state-subject="{module}">{module}状态</div>' for index, module in enumerate(MODULES[1:], 2))
    text = text.replace('</div></div></section>\n<section id="data">', '</div>' + states + '</div></section>\n<section id="data">', 1)
    (session / "raw" / "01-system" / "03-system-architecture.html").write_text(text, encoding="utf-8")

def write_system_design(session: Path) -> None:
    icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true" focusable="false"><path d="M4 12h16M12 4v16"/></svg>'
    sections = []
    for index, module in enumerate(MODULES, 1):
        sections.append(f'''<section class="module" data-module="{module}" id="module-{index}">
<div class="module-head"><span class="module-icon">{icon}</span><h2 class="module-title" data-module="{module}">{module}介绍，{module}设计</h2></div>
<div class="module-grid"><article class="metric" data-module="{module}"><strong>—</strong></article></div>
</section>''')
    template = read_template(ROOT, "system-design.html")
    body = fill_icon_slots(template, SYSTEM_NAME).replace("{{SYSTEM_NAME}}", SYSTEM_NAME).replace("{{MODULE_SECTIONS}}", "\n".join(sections))
    body = body.replace("<main>", '<main data-artifact="system-design">', 1)
    (session / "raw" / "01-system" / "04-system-design.html").write_text(body, encoding="utf-8")

def prepare_approved_system(root: Path, *, live: bool = True) -> Path:
    session = make_system(root)
    write_requirements(session)
    approve_module(session)
    write_research(session)
    write_architecture(session)
    approve_artifact(session, "architecture", "01-system/03-system-architecture.html")
    write_system_design(session)
    approve_artifact(session, "system_design", "01-system/04-system-design.html")
    return session

def minimal_rule_page() -> str:
    sections = []
    titles = ["适用范围", "工作流程", "核心规则", "平台矩阵", "案例样本", "输出契约", "质量门禁", "交接规则"]
    ids = ["scope", "workflow", "rules", "platform-matrix", "examples", "output-contract", "quality-gates", "handoff"]
    for index, (section_id, heading) in enumerate(zip(ids, titles), 1):
        icon = f'<svg class="icon-linear" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true" focusable="false"><path d="M{index + 3} 4v16M4 {index + 3}h16"/></svg>'
        sections.append(f'<!-- SECTION:{section_id}:START id={section_id} data-rule-id=visual-{section_id} -->\n<section id="{section_id}" data-rule-id="visual-{section_id}" aria-labelledby="{section_id}-heading"><h2 id="{section_id}-heading" class="section-heading">{icon}<span>{heading}</span></h2><p>按标准执行并验收。</p></section>\n<!-- SECTION:{section_id}:END -->')
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>视觉设计规范</title><link rel="stylesheet" href="guidelines.css"></head><body><main id="main" aria-label="视觉设计规范"><h1>视觉设计规范</h1>{"".join(sections)}</main></body></html>'

class SessionFlowTests(unittest.TestCase):
    def test_minimal_system_session_is_valid_and_does_not_prebuild_downstream(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            session = make_system(tool_root(temp))
            self.assertEqual(validate(session), [])
            self.assertFalse((session / "raw" / "01-system/03-system-architecture.html").exists())
            self.assertFalse((session / "raw" / "01-system/04-system-design.html").exists())
            self.assertFalse((session / "raw" / "02-visual").exists())
            approvals = read_json(session / "raw" / "99-delivery/APPROVALS.json")
            for name in ("module_scope", "architecture", "system_design", "visual", "prototype"):
                self.assertIn(name, approvals)
                self.assertNotEqual(approvals[name]["status"], "approved")

    def test_full_hash_bound_chain_passes(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root = tool_root(temp)
            session = prepare_approved_system(root)
            add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)
            approve_artifact(session, "visual", "02-visual/visual-board.html")
            add_mode(root, session, "prototype", skill_root=ROOT, allow_live_crawl_offline=True)
            screenshot = session / "raw" / "99-delivery" / "browser-acceptance.png"
            screenshot.write_bytes(b"\x89PNG\r\n\x1a\nacceptance")
            approve_artifact(session, "prototype", "03-prototype/interactive-prototype.html", "99-delivery/browser-acceptance.png")
            self.assertEqual(validate(session, allow_live_crawl_offline=True), [])

    def test_session_root_holds_only_the_published_final_html_and_raw(self) -> None:
        from publish import publish
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root = tool_root(temp)
            session = prepare_approved_system(root)
            add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)
            approve_artifact(session, "visual", "02-visual/visual-board.html")
            add_mode(root, session, "prototype", skill_root=ROOT, allow_live_crawl_offline=True)
            final = publish(session, "prototype")
            self.assertEqual(final.name, session.name + ".html")
            self.assertEqual(sorted(p.name for p in session.iterdir()), sorted(["raw", final.name]))
            self.assertFalse(any("final" in e or "may only contain" in e for e in validate(session, allow_live_crawl_offline=True)))
            final.write_text(final.read_text(encoding="utf-8") + "<!-- edited -->", encoding="utf-8")
            self.assertTrue(any("differs from its published hash" in e for e in validate(session, allow_live_crawl_offline=True)))
            (session / "notes.md").write_text("x", encoding="utf-8")
            self.assertTrue(any("may only contain" in e for e in validate(session, allow_live_crawl_offline=True)))

    def test_modified_architecture_hash_blocks_downstream(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root = tool_root(temp)
            session = prepare_approved_system(root)
            path = session / "raw" / "01-system/03-system-architecture.html"
            path.write_text(path.read_text(encoding="utf-8") + "\n<!-- changed -->\n", encoding="utf-8")
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertTrue(any("artifact hash differs" in error for error in errors), errors)
            with self.assertRaises(PermissionError):
                add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)

    def test_research_without_task_or_snapshot_fails(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            session = make_system(tool_root(temp))
            write_requirements(session)
            approve_module(session)
            write_research(session, omit_tasks=True)
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertTrue(any("LuzCrawl task ID" in error for error in errors), errors)
            (session / "raw" / "01-system/02-research.md").write_text("# Research\n", encoding="utf-8")
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertTrue(any("at least 12 unique sources" in error for error in errors), errors)

    def test_architecture_cannot_exist_before_module_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            session = make_system(tool_root(temp))
            write_requirements(session)
            write_research(session)
            write_architecture(session)
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertTrue(any("before module_scope approval" in error for error in errors), errors)

    def test_system_design_requires_architecture_approval(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            session = make_system(tool_root(temp))
            write_requirements(session); approve_module(session); write_research(session)
            write_architecture(session); write_system_design(session)
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertTrue(any("before architecture approval" in error for error in errors), errors)

    def test_visual_cannot_start_without_both_approvals(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root = tool_root(temp)
            session = make_system(root)
            with self.assertRaises(PermissionError):
                add_mode(root, session, "visual", skill_root=ROOT)

    def test_hardware_session_and_mode_routing(self) -> None:
        from new_session import parse_modes
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root = tool_root(temp)
            session = create_session(root, "无人健身房硬件选型清单", ["hardware"], skill_root=ROOT)
            self.assertTrue((session / "raw" / "04-hardware" / "plan.json").is_file())
            self.assertTrue((session / "raw" / "04-hardware" / "requirements.md").is_file())
            self.assertEqual(validate(session), [])
        for other in ("document", "poster"):
            with self.assertRaises(ValueError) as caught:
                parse_modes(other)
            self.assertIn("Luz-Design", str(caught.exception))

    def test_h1_first_contract_accepts_only_title_then_section(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            page = Path(temp) / "visual-design.html"
            page.write_text(minimal_rule_page(), encoding="utf-8")
            errors: list[str] = []
            validate_rule_page(page, "visual", 0, "视觉设计规范", errors)
            self.assertEqual(errors, [])

            for bad in (
                minimal_rule_page().replace('<main id="main"', '<header><p>采集日期</p></header><main id="main"'),
                minimal_rule_page().replace('<h1>视觉设计规范</h1>', '<h1>视觉设计规范</h1><p>摘要</p>'),
                minimal_rule_page().replace('id="scope"', 'id="scope"><p>来源与证据状态</p>'),
            ):
                page.write_text(bad, encoding="utf-8")
                errors = []
                validate_rule_page(page, "visual", 0, "视觉设计规范", errors)
                self.assertTrue(errors)

    def test_actual_rules_are_title_first_chinese_and_source_free(self) -> None:
        cases = [("ui-standards.html", "ui", "界面通用规范"), ("system-design.html", "system", "系统设计规范"),
                 ("admin-design.html", "admin", "网页管理后台设计规范"), ("miniprogram-design.html", "miniprogram", "小程序设计规范"),
                 ("agent-design.html", "agent", "智能体设计规范"), ("website-design.html", "website", "网站设计规范"),
                 ("function-list-design.html", "flist", "系统功能列表规范"), ("hardware-design.html", "hardware", "硬件设计规范")]
        for filename, prefix, title in cases:
            with self.subTest(filename=filename):
                path = ROOT / "references" / filename
                errors: list[str] = []
                validate_rule_page(path, prefix, 0, title, errors)
                self.assertEqual(errors, [])
                text = path.read_text(encoding="utf-8")
                for forbidden in ("source-card", "<aside", 'id="sources"', "rule-date"):
                    self.assertNotIn(forbidden, text)

    def test_rule_content_covers_ordering_visual_and_spreadsheet_contracts(self) -> None:
        system = (ROOT / "references/ui-standards.html").read_text(encoding="utf-8")
        visual = (ROOT / "references/ui-standards.html").read_text(encoding="utf-8")
        for token in ("订单", "支付", "预约", "履约", "库存", "优惠券", "取餐码"):
            self.assertIn(token, system)
        for token in ("底部导航", "菜品卡", "套餐选择", "购物车", "结算", "浏览器"):
            self.assertIn(token, visual)

if __name__ == "__main__":
    unittest.main(verbosity=2)
