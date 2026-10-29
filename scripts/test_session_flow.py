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

def adopt_rules(session: Path, rule: str = "界面通用规范 › 核心规则 › 五、组件 › 分页与加载更多", how: str = "列表默认 20 条/页") -> None:
    """Fill BRIEF 采用的规则 and 本次沉淀 the way an agent does after reading the rule card and writing a note."""
    import validate_session
    brief = session / "raw" / "BRIEF.md"
    text = brief.read_text(encoding="utf-8")
    head, tail = text.split("## 本次沉淀", 1)
    head = head.rstrip("\n") + f"\n| {rule} | {how} |\n\n"
    tail = tail.rstrip("\n") + "\n| test-session-note | lesson | 测试会话写入的经验 |\n"
    brief.write_text(head + "## 本次沉淀" + tail, encoding="utf-8")
    notes = session.parent / "notes.json"
    today = date.today().isoformat()
    notes.write_text(json.dumps({"schema_version": "1.0", "notes": [{"key": "test-session-note", "kind": "lesson", "text": "测试会话写入的经验", "uses": 1, "first_seen": today, "last_confirmed": today}]}, ensure_ascii=False), encoding="utf-8")
    validate_session.NOTES_FILE = notes

def prepare_prototype(root: Path) -> Path:
    session = prepare_approved_system(root)
    add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)
    approve_artifact(session, "visual", "02-visual/visual-board.html")
    add_mode(root, session, "prototype", skill_root=ROOT, allow_live_crawl_offline=True)
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
    def tearDown(self) -> None:
        import validate_session
        validate_session.NOTES_FILE = ROOT / "experience" / "notes.json"  # adopt_rules points it at a temporary store

    def test_minimal_system_session_is_valid_and_does_not_prebuild_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
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
        with tempfile.TemporaryDirectory() as temp:
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
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = prepare_approved_system(root)
            add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)
            approve_artifact(session, "visual", "02-visual/visual-board.html")
            add_mode(root, session, "prototype", skill_root=ROOT, allow_live_crawl_offline=True)
            adopt_rules(session)
            final = publish(session, "prototype")
            self.assertEqual(final.name, session.name + ".html")
            self.assertEqual(sorted(p.name for p in session.iterdir()), sorted(["raw", final.name]))
            self.assertFalse(any("final" in e or "may only contain" in e for e in validate(session, allow_live_crawl_offline=True)))
            final.write_text(final.read_text(encoding="utf-8") + "<!-- edited -->", encoding="utf-8")
            self.assertTrue(any("differs from its published hash" in e for e in validate(session, allow_live_crawl_offline=True)))
            (session / "notes.md").write_text("x", encoding="utf-8")
            self.assertTrue(any("may only contain" in e for e in validate(session, allow_live_crawl_offline=True)))

    def test_sessions_and_modes_save_their_rule_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = prepare_approved_system(root)
            rules = session / "raw" / "00-rules"
            self.assertEqual(sorted(p.name for p in rules.glob("*.md")), ["interaction.md", "remote-config.md", "system-design.md"])
            add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)
            self.assertEqual(sorted(p.name for p in rules.glob("*.md")), ["admin-list.md", "interaction.md", "miniprogram.md", "remote-config.md", "system-design.md"])
            approve_artifact(session, "visual", "02-visual/visual-board.html")
            add_mode(root, session, "prototype", skill_root=ROOT, allow_live_crawl_offline=True, cards=["admin-dashboard"])
            self.assertEqual(sorted(p.name for p in rules.glob("*.md")),
                             ["admin-dashboard.md", "admin-list.md", "interaction.md", "miniprogram.md", "prototype.md", "remote-config.md", "system-design.md"])
            self.assertTrue((rules / "prototype.md").read_text(encoding="utf-8").startswith("<!-- rules-sha256: "))
            # Named surface cards replace the visual defaults; the stage card always comes with its mode.
            other = create_session(root, "官网", ["system"], skill_root=ROOT, session_kind="system", system_name="官网",
                                   modules=["首页"], cards=["website"])
            self.assertEqual(sorted(p.name for p in (other / "raw" / "00-rules").glob("*.md")), ["interaction.md", "remote-config.md", "system-design.md", "website.md"])
            hardware = create_session(root, "门店硬件选型清单", ["hardware"], skill_root=ROOT)
            self.assertTrue((hardware / "raw" / "00-rules" / "hardware.md").is_file())
            with self.assertRaises(ValueError) as caught:
                create_session(root, "未知卡", ["hardware"], skill_root=ROOT, cards=["poster"])
            self.assertIn("unknown rule card", str(caught.exception))
            self.assertFalse(any("未知卡" in p.name for p in root.iterdir()))

    def test_agent_session_prototype_shows_the_seven_run_states(self) -> None:
        # agent-design.html 运行状态: an agent session's prototype skeleton carries one data-state block per run state;
        # removing them leaves a warning, never an error, so older sessions keep validating.
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = prepare_approved_system(root)
            add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True, cards=["agent-ui", "agent-runtime-ui"])
            approve_artifact(session, "visual", "02-visual/visual-board.html")
            add_mode(root, session, "prototype", skill_root=ROOT, allow_live_crawl_offline=True)
            prototype = session / "raw" / "03-prototype" / "interactive-prototype.html"
            text = prototype.read_text(encoding="utf-8")
            for state in ("排队", "执行中", "等待审批", "失败可重试", "断线重连", "已停止", "完成"):
                self.assertIn(f'data-state="{state}"', text)
            self.assertNotIn("<!-- AGENT_PART -->", text)
            warnings: list[str] = []
            self.assertEqual(validate(session, allow_live_crawl_offline=True, warnings=warnings), [])
            self.assertFalse(any("agent" in w for w in warnings), warnings)
            stripped = re.sub(r'<section id="agent-run".*?</section>', "", text, flags=re.S)
            prototype.write_text(stripped, encoding="utf-8")
            warnings = []
            validate(session, allow_live_crawl_offline=True, warnings=warnings)
            self.assertTrue(any("does not demonstrate the run states" in w for w in warnings))
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = prepare_prototype(root)
            text = (session / "raw" / "03-prototype" / "interactive-prototype.html").read_text(encoding="utf-8")
            self.assertNotIn('data-state="排队"', text)  # not an agent session: no agent part
            self.assertNotIn("AGENT_PART", text)  # and no leftover marker

    def test_publish_needs_the_mode_and_every_upstream_approval(self) -> None:
        # A prototype written straight after the architecture, without system design, visual approval or the
        # prototype mode, must not be published (publish.py approval gate mirrors add_mode.py).
        from publish import publish
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = prepare_approved_system(root)
            adopt_rules(session)
            prototype = session / "raw" / "03-prototype" / "interactive-prototype.html"
            prototype.parent.mkdir(parents=True, exist_ok=True)
            prototype.write_text((session / "raw" / "01-system" / "04-system-design.html").read_text(encoding="utf-8"), encoding="utf-8")
            with self.assertRaises(PermissionError) as caught:
                publish(session, "prototype")
            self.assertIn("has not declared", str(caught.exception))
            self.assertIn("visual is not approved", str(caught.exception))
            self.assertFalse((session / f"{session.name}.html").exists())
            prototype.unlink()
            prototype.parent.rmdir()
            add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)
            approve_artifact(session, "visual", "02-visual/visual-board.html")
            add_mode(root, session, "prototype", skill_root=ROOT, allow_live_crawl_offline=True)
            adopt_rules(session)
            # An approved upstream file edited afterwards blocks publishing until it is approved again.
            board = session / "raw" / "02-visual" / "visual-board.html"
            original = board.read_text(encoding="utf-8")
            board.write_text(original + "<!-- edited -->", encoding="utf-8")
            with self.assertRaises(PermissionError) as caught:
                publish(session, "prototype")
            self.assertIn("visual artifact hash differs", str(caught.exception))
            board.write_text(original, encoding="utf-8")
            self.assertTrue(publish(session, "prototype").is_file())

    def test_publish_needs_rule_card_adopted_rules_and_sediment(self) -> None:
        from publish import publish
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = prepare_prototype(root)
            brief = session / "raw" / "BRIEF.md"
            with self.assertRaises(ValueError) as caught:
                publish(session, "prototype")
            self.assertIn("采用的规则", str(caught.exception))
            self.assertFalse((session / f"{session.name}.html").exists())
            text = brief.read_text(encoding="utf-8")
            brief.write_text(text.replace("|---|---|\n\n## 本次沉淀", "|---|---|\n| 界面通用规范 › 核心规则 › 五、组件 › 筛选 | 外露 4 个筛选 |\n\n## 本次沉淀"), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                publish(session, "prototype")
            self.assertIn("本次沉淀", str(caught.exception))
            brief.write_text(text, encoding="utf-8")
            adopt_rules(session)
            # A card cut from rule pages that have changed since is stale and blocks publishing.
            card = session / "raw" / "00-rules" / "prototype.md"
            original = card.read_text(encoding="utf-8")
            first, rest = original.split("\n", 1)
            card.write_text(first.replace(first[first.index(":") + 2:first.index(":") + 14], "000000000000") + "\n" + rest, encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                publish(session, "prototype")
            self.assertIn("out of date", str(caught.exception))
            card.write_text(original, encoding="utf-8")
            final = publish(session, "prototype")
            self.assertTrue(final.is_file())
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertFalse(any("00-rules" in e or "采用的规则" in e or "本次沉淀" in e for e in errors), errors)
            # A published session that loses its notes or cards is reported by validation.
            for path in (session / "raw" / "00-rules").glob("*.md"):
                path.unlink()
            brief.write_text(text, encoding="utf-8")
            errors = validate(session, allow_live_crawl_offline=True)
            for marker in ("00-rules", "采用的规则 is empty", "本次沉淀 is empty"):
                self.assertTrue(any(marker in e for e in errors), (marker, errors))

    def test_sessions_created_before_rule_cards_are_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            session = make_system(tool_root(temp))
            for path in (session / "raw" / "00-rules").glob("*.md"):
                path.unlink()
            self.assertTrue(any("00-rules" in e for e in validate(session)))
            manifest_path = session / "raw" / "99-delivery" / "MANIFEST.json"
            manifest = read_json(manifest_path)
            manifest["created_at"] = "2026-10-28T15:33:59+08:00"
            write_json(manifest_path, manifest)
            self.assertEqual(validate(session), [])

    def test_modified_architecture_hash_blocks_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = prepare_approved_system(root)
            path = session / "raw" / "01-system/03-system-architecture.html"
            path.write_text(path.read_text(encoding="utf-8") + "\n<!-- changed -->\n", encoding="utf-8")
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertTrue(any("artifact hash differs" in error for error in errors), errors)
            with self.assertRaises(PermissionError):
                add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)

    def test_research_without_task_or_snapshot_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
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
        with tempfile.TemporaryDirectory() as temp:
            session = make_system(tool_root(temp))
            write_requirements(session)
            write_research(session)
            write_architecture(session)
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertTrue(any("before module_scope approval" in error for error in errors), errors)

    def test_system_design_requires_architecture_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            session = make_system(tool_root(temp))
            write_requirements(session); approve_module(session); write_research(session)
            write_architecture(session); write_system_design(session)
            errors = validate(session, allow_live_crawl_offline=True)
            self.assertTrue(any("before architecture approval" in error for error in errors), errors)

    def test_visual_cannot_start_without_both_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = make_system(root)
            with self.assertRaises(PermissionError):
                add_mode(root, session, "visual", skill_root=ROOT)

    def test_hardware_session_and_mode_routing(self) -> None:
        from new_session import parse_modes
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = create_session(root, "无人健身房硬件选型清单", ["hardware"], skill_root=ROOT)
            self.assertTrue((session / "raw" / "04-hardware" / "plan.json").is_file())
            self.assertTrue((session / "raw" / "04-hardware" / "requirements.md").is_file())
            self.assertEqual(validate(session), [])
        for other in ("document", "poster"):
            with self.assertRaises(ValueError) as caught:
                parse_modes(other)
            self.assertIn("Luz-Design", str(caught.exception))

    def test_hardware_list_needs_the_persons_approval_before_publishing(self) -> None:
        from publish import publish
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = create_session(root, "无人健身房硬件选型清单", ["hardware"], skill_root=ROOT)
            approvals = read_json(session / "raw" / "99-delivery" / "APPROVALS.json")
            self.assertEqual(approvals["hardware"]["status"], "pending")
            (session / "raw" / "04-hardware" / "hardware-plan.html").write_text("<!doctype html><title>清单</title>", encoding="utf-8")
            with self.assertRaises(PermissionError) as caught:
                publish(session, "hardware")
            self.assertIn("hardware is not approved", str(caught.exception))

    def test_validate_skill_prints_the_package_result_first(self) -> None:
        import contextlib
        import io
        import validate_skill
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = validate_skill.main(["--package-only"])
        lines = buffer.getvalue().splitlines()
        self.assertTrue(lines[0].startswith("PACKAGE PASS" if code == 0 else "PACKAGE FAIL"), lines[:2])
        self.assertTrue(lines[-1].startswith("PASS:") if code == 0 else any(l.startswith("FAIL:") for l in lines))
        if code == 0:
            self.assertIn("--package-only", lines[-1])

    def test_add_mode_refuses_document_and_poster_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = make_system(root)
            for mode, poster in (("document", False), ("visual", True)):
                with self.assertRaises(ValueError) as caught:
                    add_mode(root, session, mode, standalone_poster=poster, skill_root=ROOT)
                self.assertIn("Luz-Design", str(caught.exception))

    def test_h1_first_contract_accepts_only_title_then_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
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

DEMO_SIGNER = "销售甲"
STAGES = ("module_scope", "architecture", "system_design", "visual", "prototype")


def make_demo(root: Path) -> Path:
    return create_session(
        root, "订餐系统", ["system"], skill_root=ROOT, session_kind="system",
        system_name=SYSTEM_NAME, modules=MODULES, approval_mode="authorization",
    )


def sign_authorization(session: Path, aid: str = "AUTH-001", *, signer: str = DEMO_SIGNER, scope=STAGES,
                       at: str | None = None, statement: str = "背景没问题，生成吧") -> Path:
    """What the platform writes when the person confirms the background and presses 生成."""
    context = session / "raw" / "00-intake" / f"{aid}-context.md"
    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_text("# 背景\n\n连锁餐饮门店，演示点餐、支付与会员。\n", encoding="utf-8")
    path = session / "raw" / "99-delivery" / "APPROVALS.json"
    data = read_json(path)
    data.setdefault("authorizations", []).append({
        "id": aid, "authorized_by": signer, "authorized_at": at or now(), "scope": list(scope),
        "statement": statement, "context_path": f"00-intake/{aid}-context.md", "context_sha256": digest(context),
    })
    write_json(path, data)
    return context


def record_under(session: Path, name: str, relative: str, aid: str = "AUTH-001", *, by: str = DEMO_SIGNER,
                 at: str | None = None) -> None:
    """What the platform writes for a stage after its checks pass."""
    path = session / "raw" / "99-delivery" / "APPROVALS.json"
    data = read_json(path)
    data[name].update({
        "status": "approved", "approval_basis": "authorization", "authorization_id": aid,
        "artifact_path": relative, "artifact_sha256": digest(session / "raw" / relative),
        "approved_by": by, "approved_at": at or now(), "note": "按授权通过：页面、交互与来源校验通过",
    })
    if name == "module_scope":
        data[name]["selected_modules"] = MODULES
    write_json(path, data)


class AuthorizationTests(unittest.TestCase):
    """approval_mode authorization (SKILL.md 调用协议 6): one signed authorization carries a platform demo through every
    stage and its checks; everything else about approvals stays."""

    def test_one_signed_authorization_carries_the_demo_to_publish(self) -> None:
        from publish import publish
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = make_demo(root)
            self.assertEqual(read_json(session / "raw" / "99-delivery" / "MANIFEST.json")["approval_mode"], "authorization")
            write_requirements(session)
            sign_authorization(session)
            record_under(session, "module_scope", "01-system/01-module-intake.html")
            write_research(session)
            write_architecture(session)
            record_under(session, "architecture", "01-system/03-system-architecture.html")
            write_system_design(session)
            record_under(session, "system_design", "01-system/04-system-design.html")
            add_mode(root, session, "visual", skill_root=ROOT, allow_live_crawl_offline=True)
            record_under(session, "visual", "02-visual/visual-board.html")
            add_mode(root, session, "prototype", skill_root=ROOT, allow_live_crawl_offline=True)
            adopt_rules(session)
            self.assertTrue(publish(session, "prototype").is_file())

    def module_errors(self, *, per_stage: bool = False, sign: dict | None = None, record: dict | None = None,
                      after=None) -> list[str]:
        from validate_session import validate_approval_record
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            session = make_system(root) if per_stage else make_demo(root)
            sign_authorization(session, **(sign or {}))
            record_under(session, "module_scope", "01-system/01-module-intake.html", **(record or {}))
            if after:
                after(session)
            work = session / "raw"
            errors: list[str] = []
            validate_approval_record(work, "module_scope", read_json(work / "99-delivery" / "APPROVALS.json")["module_scope"], errors)
            return errors

    def test_a_valid_record_passes(self) -> None:
        self.assertEqual(self.module_errors(), [])
        # A record written before a re-authorization stays valid under the authorization it cites.
        early = dict(at="2026-10-29T09:00:00+08:00")
        self.assertEqual(self.module_errors(sign=early, record=dict(at="2026-10-29T09:30:00+08:00"),
                                            after=lambda s: sign_authorization(s, "AUTH-002", at="2026-10-29T10:00:00+08:00")), [])

    def test_what_an_authorization_cannot_cover(self) -> None:
        def changed_background(session: Path) -> None:
            (session / "raw" / "00-intake" / "AUTH-001-context.md").write_text("# 背景\n\n改成健身房。\n", encoding="utf-8")

        cases = {
            "approves stage by stage": dict(per_stage=True),
            "automatic actor": dict(sign=dict(signer="platform"), record=dict(by="platform")),
            "outside the scope of AUTH-001": dict(sign=dict(scope=("architecture", "system_design"))),
            "must be the person who signed AUTH-001": dict(record=dict(by="销售乙")),
            "context file differs": dict(after=changed_background),
            "recorded before AUTH-001 was signed": dict(record=dict(at="2026-01-01T00:00:00+08:00")),
            "needs statement": dict(sign=dict(statement=" ")),
            "AUTH-002 was in force": dict(sign=dict(at="2026-10-29T09:00:00+08:00"), record=dict(at="2026-10-29T11:00:00+08:00"),
                                          after=lambda s: sign_authorization(s, "AUTH-002", at="2026-10-29T10:00:00+08:00")),
        }
        for expected, options in cases.items():
            with self.subTest(expected=expected):
                errors = self.module_errors(**options)
                self.assertTrue(any(expected in e for e in errors), errors)

    def test_authorization_is_for_software_demo_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = tool_root(temp)
            with self.assertRaises(ValueError):
                create_session(root, "无人健身房", ["system", "hardware"], skill_root=ROOT, session_kind="system",
                               system_name="无人健身房", modules=["门禁"], approval_mode="authorization")
            with self.assertRaises(ValueError):
                create_session(root, "活动海报", [], skill_root=ROOT, approval_mode="authorization")
            session = make_system(root)
            self.assertNotIn("approval_mode", read_json(session / "raw" / "99-delivery" / "MANIFEST.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
