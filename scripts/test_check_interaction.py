"""Tests for check_interaction.py (interaction logic: entries, exits, duplicates, closed loops, states and feedback,
and the seven agent run states a prototype demonstrates).

Run:  py -X utf8 -m unittest test_check_interaction -v   (from scripts/)
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from check_interaction import (  # noqa: E402
    AGENT_RUN_STATES,
    architecture_interaction_findings,
    prototype_agent_state_findings,
    prototype_interaction_findings,
)
from validate_session import parse_html  # noqa: E402

FULL_STATES = "加载:骨架行;空:还没有订单·去点餐 A-002;错误:原因与重试;成功:列表;禁用:无权限时按钮置灰并写原因"


def parse(body: str):
    html = f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>架构</title></head><body><main data-artifact="system-architecture"><h1>系统</h1>{body}</main></body></html>'
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "a.html"
        path.write_text(html, encoding="utf-8")
        errors: list[str] = []
        root = parse_html(path, errors)
        assert root is not None, errors
        return root


def page(pid: str, name: str, route: str, **attrs: str) -> str:
    extra = "".join(f' data-{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<tr data-page-id="{pid}" data-route="{route}"{extra}><td>{pid}</td><td>{name}</td><td>{route}</td></tr>'


def nav(nid: str, target: str, label: str, source: str) -> str:
    return f'<tr data-navigation-id="{nid}" data-page-id="{target}"><td>{nid}</td><td>{label}</td><td>{source}</td><td>{target}</td></tr>'


def comp(cid: str, pid: str, name: str, *actions: str, display: str = "") -> str:
    disp = f' data-display="{display}"' if display else ""
    return f'<div class="node" data-component-id="{cid}" data-page-id="{pid}"{disp}><strong>{name}</strong>{"".join(actions)}</div>'


def act(aid: str, pid: str, cid: str, label: str, functions: str = "F-001", **attrs: str) -> str:
    extra = "".join(f' data-{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return (f'<button type="button" data-action-id="{aid}" data-page-id="{pid}" data-component-id="{cid}" '
            f'data-function-ids="{functions}"{extra}>{aid} {label}</button>')


def run(*parts: str, design: str | None = None):
    body = "<table><tbody>" + "".join(p for p in parts if p.startswith("<tr")) + "</tbody></table>"
    body += "".join(p for p in parts if not p.startswith("<tr"))
    return architecture_interaction_findings(parse(body), parse(design) if design else None)


BASE = (
    page("P-001", "订单", "/orders"),
    page("P-002", "订单详情", "/orders/:id"),
    nav("N-001", "P-001", "底部标签 · 订单", "底部标签栏"),
    nav("N-002", "P-002", "订单行 → 订单详情", "P-001"),
)


class DuplicateTests(unittest.TestCase):
    def test_same_text_twice_on_one_page_is_an_error(self) -> None:
        errors, _ = run(*BASE, comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "导出"),
                                    act("A-002", "P-001", "C-001", "导出")))
        self.assertTrue(any("same text “导出”" in e for e in errors))

    def test_two_navigation_entries_to_one_destination_is_an_error(self) -> None:
        errors, _ = run(*BASE, nav("N-003", "P-002", "顶栏 · 详情", "P-001"))
        self.assertTrue(any("two entries to P-002: N-002 and N-003" in e for e in errors))

    def test_action_and_navigation_to_the_same_target_need_a_link(self) -> None:
        unlinked = comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "查看", target_page_id="P-002"))
        errors, _ = run(*BASE, unlinked)
        self.assertTrue(any("both A-001 and N-002" in e for e in errors))
        linked = comp("C-001", "P-001", "订单列表",
                      act("A-001", "P-001", "C-001", "查看", target_page_id="P-002", navigation_id="N-002"))
        errors, _ = run(*BASE, linked)
        self.assertFalse(any("both A-001" in e for e in errors))

    def test_action_named_like_the_navigation_target_is_a_warning(self) -> None:
        _, warnings = run(*BASE, comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "打开订单详情")))
        self.assertTrue(any("A-001 “打开订单详情” and N-002 both lead to P-002" in w for w in warnings))

    def test_overlapping_purposes_on_one_page_are_a_warning(self) -> None:
        _, warnings = run(*BASE, comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "新建订单"),
                                      act("A-002", "P-001", "C-001", "扫码新建订单")))
        self.assertTrue(any("look like the same purpose" in w for w in warnings))

    def test_same_text_for_different_functions_across_pages_is_a_warning(self) -> None:
        _, warnings = run(*BASE, comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "重试", "F-001")),
                          comp("C-002", "P-002", "订单信息", act("A-002", "P-002", "C-002", "重试", "F-009")))
        self.assertTrue(any("share the text “重试”" in w for w in warnings))


class ContractTests(unittest.TestCase):
    def full(self, **override: str) -> tuple[list[str], list[str]]:
        attrs = dict(entry="N-001", goal="找到要处理的订单", primary_action="A-001", exit="切换:标签栏", states=FULL_STATES)
        attrs.update(override)
        attrs = {k: v for k, v in attrs.items() if v}
        detail = dict(entry="N-002", goal="处理一笔订单", primary_action="无", exit="返回:来源", states=FULL_STATES)
        return run(page("P-001", "订单", "/orders", **attrs), page("P-002", "订单详情", "/orders/:id", **detail),
                   *BASE[2:], comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "打开订单详情",
                                                                    target_page_id="P-002", navigation_id="N-002")))

    def test_complete_contract_passes(self) -> None:
        errors, warnings = self.full()
        self.assertEqual(errors, [])
        self.assertFalse(any("do not yet declare" in w for w in warnings))

    def test_opted_in_page_missing_fields_is_an_error(self) -> None:
        errors, _ = self.full(goal="", states="")
        self.assertTrue(any("P-001 订单 must declare data-goal, data-states" in e for e in errors))

    def test_entry_naming_navigation_to_another_page_is_an_error(self) -> None:
        errors, _ = self.full(entry="N-002")
        self.assertTrue(any("data-entry N-002 leads to P-002, not to this page" in e for e in errors))

    def test_primary_action_must_be_one_action_of_the_page(self) -> None:
        errors, _ = self.full(primary_action="A-001,A-009")
        self.assertTrue(any("2 primary actions" in e for e in errors))
        errors, _ = self.full(primary_action="A-404")
        self.assertTrue(any("unknown action A-404" in e for e in errors))

    def test_states_need_all_five_kinds_and_reasons(self) -> None:
        errors, _ = self.full(states="加载:骨架;错误:重试;成功:列表")
        self.assertTrue(any("lacks 空、禁用" in e for e in errors))
        errors, _ = self.full(states=FULL_STATES.replace("禁用:无权限时按钮置灰并写原因", "禁用:不适用"))
        self.assertTrue(any("禁用 is 不适用 without a reason" in e for e in errors))

    def test_reason_in_parentheses_counts(self) -> None:
        errors, _ = self.full(states=FULL_STATES.replace("禁用:无权限时按钮置灰并写原因", "禁用:不适用（本页没有受条件限制的按钮）"))
        self.assertFalse(any("不适用 without a reason" in e for e in errors))

    def test_empty_state_of_a_list_needs_a_next_step(self) -> None:
        _, warnings = self.full(states=FULL_STATES.replace("还没有订单·去点餐 A-002", "暂无数据"))
        self.assertTrue(any("empty state gives no next step" in w for w in warnings))

    def test_legacy_architecture_only_warns(self) -> None:
        errors, warnings = run(*BASE, comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "导出")))
        self.assertEqual(errors, [])
        self.assertTrue(any("do not yet declare the interaction contract" in w for w in warnings))
        self.assertTrue(any("have actions but declare no interface states" in w for w in warnings))


class NavigationTests(unittest.TestCase):
    def test_island_page_warns_in_legacy_and_fails_when_opted_in(self) -> None:
        island = page("P-003", "退款记录", "/refunds")
        _, warnings = run(*BASE, island)
        self.assertTrue(any("P-003 退款记录 is an island" in w for w in warnings))
        errors, _ = run(page("P-001", "订单", "/orders", entry="N-001", goal="g", primary_action="无", exit="切换:标签栏",
                             states=FULL_STATES), *BASE[1:], island)
        self.assertTrue(any("P-003 退款记录 is an island" in e for e in errors))

    def test_login_and_external_pages_are_not_islands(self) -> None:
        _, warnings = run(*BASE, page("P-009", "登录", "/login"))
        self.assertFalse(any("P-009" in w and "island" in w for w in warnings))

    def test_dead_end_page_warns(self) -> None:
        _, warnings = run(*BASE)
        self.assertTrue(any("declare no exit" in w and "P-002 订单详情" in w for w in warnings))
        _, warnings = run(*BASE, comp("C-002", "P-002", "订单信息", act("A-005", "P-002", "C-002", "返回")))
        self.assertFalse(any("declare no exit" in w for w in warnings))

    def test_navigation_must_use_the_target_page_name(self) -> None:
        _, warnings = run(*BASE, nav("N-003", "P-002", "消息 → 订单页", "P-001"))
        self.assertTrue(any("N-003 calls P-002 “订单页”" in w for w in warnings))


class LoopTests(unittest.TestCase):
    def state(self, transitions: str, terminal: str = "") -> str:
        term = f' data-terminal="{terminal}"' if terminal else ""
        return (f'<div class="node" data-state-id="S-001" data-state-subject="订单" data-transitions="{transitions}"{term}>'
                '<strong>订单</strong>：待付款、已支付、已完成、已取消</div>')

    def test_dead_and_unreachable_states_are_errors(self) -> None:
        errors, _ = run(*BASE, self.state("待付款>已支付@支付成功;已支付>已完成@核销", terminal="已完成"))
        self.assertTrue(any("已取消 has no entering event" in e for e in errors))
        self.assertTrue(any("已取消 is a dead state" in e for e in errors))

    def test_closed_state_machine_passes(self) -> None:
        errors, _ = run(*BASE, self.state("待付款>已支付@支付成功;已支付>已完成@核销;待付款>已取消@超时关单",
                                          terminal="已完成,已取消"))
        self.assertEqual([e for e in errors if "S-001" in e], [])

    def test_states_without_transitions_warn(self) -> None:
        _, warnings = run(*BASE, '<div class="node" data-state-id="S-002" data-state-subject="订单">待付款、已支付</div>')
        self.assertTrue(any("declare no transitions" in w and "S-002" in w for w in warnings))

    def test_creatable_entity_without_delete_or_edit_warns(self) -> None:
        entity = '<tr data-entity-id="D-001"><td>D-001</td><td>优惠券</td><td>面额、门槛</td></tr>'
        _, warnings = run(*BASE, entity, comp("C-001", "P-001", "优惠券列表", act("A-001", "P-001", "C-001", "新增优惠券")))
        self.assertTrue(any("D-001 优惠券 can be created (A-001) but has no 查看、编辑、删除或归档 path" in w for w in warnings))

    def test_declared_lifecycle_is_checked_strictly(self) -> None:
        entity = ('<tr data-entity-id="D-001" data-lifecycle="新建:A-001;查看:A-001;编辑:不提供"><td>D-001</td>'
                  '<td>优惠券</td></tr>')
        errors, _ = run(*BASE, entity, comp("C-001", "P-001", "优惠券列表", act("A-001", "P-001", "C-001", "新增优惠券")))
        self.assertTrue(any("编辑 is 不提供 without a reason" in e for e in errors))
        self.assertTrue(any("data-lifecycle lacks 删除" in e for e in errors))

    def test_lifecycle_reason_in_parentheses_counts(self) -> None:
        entity = ('<tr data-entity-id="D-001" data-lifecycle="新建:A-001;查看:A-001;编辑:不提供（由系统生成）;'
                  '删除:不提供（随上级对象删除）"><td>D-001</td><td>优惠券</td></tr>')
        errors, _ = run(*BASE, entity, comp("C-001", "P-001", "优惠券列表", act("A-001", "P-001", "C-001", "新增优惠券")))
        self.assertEqual([e for e in errors if "D-001" in e], [])

    def test_flow_success_end_and_missing_warning(self) -> None:
        errors, warnings = run(*BASE, '<div data-flow-id="FL-001" data-exception="失败重试" data-success="P-404">主流程</div>',
                               '<div data-flow-id="FL-002" data-exception="失败重试">次流程</div>')
        self.assertTrue(any("FL-001 data-success names unknown page P-404" in e for e in errors))
        self.assertTrue(any("declare no success end" in w and "FL-002" in w for w in warnings))


class FeedbackTests(unittest.TestCase):
    def test_declared_feedback_must_cover_progress_success_failure(self) -> None:
        errors, _ = run(*BASE, comp("C-001", "P-001", "订单列表",
                                    act("A-001", "P-001", "C-001", "导出", feedback="成功:轻提示")))
        self.assertTrue(any("A-001 data-feedback lacks 进行中、失败" in e for e in errors))

    def test_missing_feedback_and_confirmation_warn(self) -> None:
        _, warnings = run(*BASE, comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "删除订单")))
        self.assertTrue(any("declare no feedback" in w and "A-001" in w for w in warnings))
        self.assertTrue(any("no confirmation or undo" in w and "A-001 删除订单" in w for w in warnings))
        _, warnings = run(*BASE, comp("C-001", "P-001", "订单列表", act(
            "A-001", "P-001", "C-001", "删除订单", confirm="删除后不可恢复",
            feedback="进行中:按钮加载;成功:轻提示，留在 P-001;失败:原位提示原因与重试")))
        self.assertFalse(any("A-001" in w for w in warnings))

    def test_component_without_action_warns_unless_display(self) -> None:
        _, warnings = run(*BASE, comp("C-009", "P-001", "订单汇总"))
        self.assertTrue(any("C-009 订单汇总 has no action" in w for w in warnings))
        _, warnings = run(*BASE, comp("C-009", "P-001", "订单汇总", display="只读展示"))
        self.assertFalse(any("C-009" in w for w in warnings))

    def test_system_design_must_use_architecture_names(self) -> None:
        design = ('<table><tbody><tr><td><span data-page-id="P-002">P-002</span></td><td>订单页</td></tr>'
                  '<tr><td><span><span data-action-id="A-001">A-001</span> 看详情</span></td></tr></tbody></table>')
        _, warnings = run(*BASE, comp("C-001", "P-001", "订单列表", act("A-001", "P-001", "C-001", "打开订单详情")),
                          design=design)
        self.assertTrue(any("names P-002 “订单页” but the architecture calls it “订单详情”" in w for w in warnings))
        self.assertTrue(any("labels A-001 “看详情”" in w for w in warnings))


class PrototypeTests(unittest.TestCase):
    def proto(self, body: str):
        return prototype_interaction_findings(parse(body))

    def test_same_action_twice_on_one_page_is_an_error(self) -> None:
        errors, _ = self.proto('<button data-action-id="A-001" data-page-id="P-001">新建</button>'
                               '<button data-action-id="A-001" data-page-id="P-001">新建</button>')
        self.assertTrue(any("shows A-001 2 times on P-001" in e for e in errors))

    def test_list_rows_tabs_and_scenarios_are_exempt(self) -> None:
        rows = "".join(f'<tr><td><button data-action-id="A-002" data-page-id="P-001">详情</button></td></tr>' for _ in range(3))
        tabs = "".join(f'<button role="tab" data-arg="P-00{i}" data-action-id="A-003" data-page-id="P-001">标签{i}</button>'
                       for i in range(3))
        scenario = ('<button data-action-id="A-004" data-page-id="P-001">去点餐</button>'
                    '<div data-state-kind="空"><button data-action-id="A-004" data-page-id="P-001">去点餐</button></div>')
        errors, _ = self.proto(f"<table>{rows}</table>{tabs}{scenario}")
        self.assertEqual(errors, [])

    def test_same_text_for_two_actions_is_a_warning(self) -> None:
        _, warnings = self.proto('<button data-action-id="A-001" data-page-id="P-001">保存</button>'
                                 '<button data-action-id="A-002" data-page-id="P-001">保存</button>')
        self.assertTrue(any("same text “保存”" in w for w in warnings))


def parse_file(text: str):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "a.html"
        path.write_text(text, encoding="utf-8")
        root = parse_html(path, [])
    assert root is not None
    return root


def prototype_from_template(agent: bool) -> str:
    from new_session import fill_icon_slots, insert_agent_part, read_template
    text = fill_icon_slots(read_template(ROOT, "interactive-prototype.html"), "智能体助手")
    if agent:
        text = insert_agent_part(text, ROOT)
    return text.replace("{{ACTION_ID}}", "A-001").replace("{{PAGE_ID}}", "P-001")


class TemplateTests(unittest.TestCase):
    def test_skill_architecture_template_has_no_findings(self) -> None:
        from new_session import read_template
        root = parse_file(read_template(ROOT, "system-architecture.html"))
        errors, warnings = architecture_interaction_findings(root)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_prototype_template_has_one_entry_per_action(self) -> None:
        for agent in (False, True):
            errors, _ = prototype_interaction_findings(parse_file(prototype_from_template(agent)))
            self.assertEqual(errors, [], f"agent part: {agent}")

    def test_agent_part_demonstrates_every_run_state_without_warnings(self) -> None:
        root = parse_file(prototype_from_template(True))
        self.assertEqual(prototype_agent_state_findings(root, expected=True), [])
        plain = parse_file(prototype_from_template(False))
        self.assertEqual(prototype_agent_state_findings(plain), [])  # no agent marker, not an agent session: silent
        self.assertTrue(prototype_agent_state_findings(plain, expected=True))  # an agent session without the part warns


class AgentStateTests(unittest.TestCase):
    def blocks(self, *states: str, extra: str = "") -> str:
        return '<div data-surface="agent">' + "".join(f'<div data-state="{s}">{s}</div>' for s in states) + extra + "</div>"

    def test_missing_run_states_are_named(self) -> None:
        warnings = prototype_agent_state_findings(parse(self.blocks("排队", "执行中", "完成")))
        self.assertTrue(any("等待审批、失败可重试、断线重连、已停止" in w for w in warnings))

    def test_aliases_count_as_the_canonical_state(self) -> None:
        warnings = prototype_agent_state_findings(parse(self.blocks("排队中", "运行中", "待审批", "失败", "重连恢复", "已取消", "已完成")))
        self.assertFalse(any("does not demonstrate" in w for w in warnings))

    def test_running_state_needs_elapsed_time_and_stop(self) -> None:
        warnings = prototype_agent_state_findings(parse(self.blocks(*AGENT_RUN_STATES)))
        self.assertTrue(any("执行中 shows no elapsed time" in w for w in warnings))
        self.assertTrue(any("执行中 has no 停止 control" in w for w in warnings))
        running = ('<div data-surface="agent"><div data-state="执行中"><span data-elapsed="12">已用 12 秒</span>'
                   '<button type="button">停止</button></div></div>')
        warnings = prototype_agent_state_findings(parse(running))
        self.assertFalse(any("执行中" in w for w in warnings))

    def test_failure_needs_retry_and_request_number(self) -> None:
        failed = '<div data-surface="agent"><div data-state="失败可重试">查询失败</div></div>'
        warnings = prototype_agent_state_findings(parse(failed))
        self.assertTrue(any("失败可重试 has no retry control" in w for w in warnings))
        self.assertTrue(any("请求编号" in w for w in warnings))

    def test_buttons_repeated_across_run_states_are_not_duplicates(self) -> None:
        body = "".join(f'<div data-state="{s}"><button data-action-id="A-001" data-page-id="P-001">停止</button></div>'
                       for s in ("排队", "执行中"))
        errors, _ = prototype_interaction_findings(parse(body))
        self.assertEqual(errors, [])



class RuleAndCheckAgreementTests(unittest.TestCase):
    """The rule pages and the checks agree: values with spaces, read-only pages, navigation references, names ending in 详情."""

    def test_list_values_with_spaces_stay_whole(self) -> None:
        from check_interaction import split_list
        self.assertEqual(split_list("草稿,AI 已润色,已发布"), ["草稿", "AI 已润色", "已发布"])
        self.assertEqual(split_list("草稿、AI 已润色；已发布"), ["草稿", "AI 已润色", "已发布"])
        self.assertEqual(split_list("加载 空 失败"), ["加载", "空", "失败"])
        self.assertEqual(split_list(""), [])

    def test_state_value_with_a_space_is_one_value(self) -> None:
        state = ('<div class="node" data-state-id="S-001" data-values="草稿,AI 已润色,已发布" data-initial="草稿" '
                 'data-terminal="已发布" data-transitions="草稿>AI 已润色@润色;AI 已润色>已发布@发布">稿件状态</div>')
        errors, _ = run(*BASE, state)
        self.assertFalse(any("S-001" in e for e in errors), errors)

    def viewer(self, *actions: str):
        attrs = dict(entry="N-001", goal="查看产物", primary_action="无", exit="返回:来源", states=FULL_STATES)
        return run(page("P-001", "产物面板", "/artifact", **attrs), nav("N-001", "P-001", "侧栏 · 产物", "侧栏"),
                   comp("C-001", "P-001", "产物查看", *actions))

    def test_read_only_page_may_declare_no_primary_action(self) -> None:
        for actions in ((act("A-001", "P-001", "C-001", "切换版本"), act("A-002", "P-001", "C-001", "返回")),
                        (act("A-001", "P-001", "C-001", "全屏查看"), act("A-002", "P-001", "C-001", "下载")),
                        (act("A-001", "P-001", "C-001", "关闭"),)):
            with self.subTest(actions=len(actions)):
                errors, _ = self.viewer(*actions)
                self.assertFalse(any("declares no primary action" in e for e in errors), errors)
        errors, _ = self.viewer(act("A-001", "P-001", "C-001", "切换版本"), act("A-003", "P-001", "C-001", "保存修改"))
        self.assertTrue(any("declares no primary action" in e and "A-003" in e and "A-001" not in e.split(":")[-1] for e in errors), errors)

    def test_navigation_id_on_an_action_is_a_reference(self) -> None:
        from validate_session import collect_stable_ids
        defined = '<table><tbody>' + nav("N-001", "P-002", "订单行 → 订单详情", "P-001") + '</tbody></table>'
        button = '<button type="button" data-action-id="A-001" data-navigation-id="{nid}">打开订单详情</button>'
        errors: list[str] = []
        collect_stable_ids(parse(defined + button.format(nid="N-001")), errors, "architecture")
        self.assertEqual(errors, [])
        errors = []
        collect_stable_ids(parse(defined + button.format(nid="N-009")), errors, "architecture")
        self.assertTrue(any("undefined data-navigation-id: N-009" in e for e in errors), errors)
        errors = []
        collect_stable_ids(parse(defined + defined), errors, "architecture")
        self.assertTrue(any("repeats data-navigation-id: N-001" in e for e in errors), errors)

    def test_visual_board_and_prototype_share_the_interface_type_floor(self) -> None:
        from validate_session import interface_type_findings, parse_html, validate_light_html

        def board(css: str) -> tuple[list[str], list[str], list[str]]:
            html = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>视觉板</title>'
                    f'<style>body{{font-size:14px}}{css}</style></head><body><main data-artifact="visual-board"><h1>系统</h1>'
                    '<section><h2>会员</h2><table><tr><td>王一</td><td class="time">10:24</td></tr></table></section></main></body></html>')
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "visual-board.html"
                path.write_text(html, encoding="utf-8")
                floor: list[str] = []
                validate_light_html(path, floor, min_px=12.0)
                parse_errors: list[str] = []
                root = parse_html(path, parse_errors)
            errors, warnings = interface_type_findings(root, "visual-board")
            return floor, errors, warnings

        floor, errors, _ = board(".time{font-size:12px}")
        self.assertEqual((floor, errors), ([], []))
        _, errors, _ = board("td{font-size:12px}")
        self.assertTrue(any("visual-board interface text 12px below 14px" in e for e in errors), errors)
        floor, _, _ = board(".time{font-size:11px}")
        self.assertTrue(any("below 12px" in e for e in floor), floor)

    def test_names_ending_in_a_descriptive_word_are_labels(self) -> None:
        from validate_session import chart_label_is_allowed
        for name in ("会议详情", "Demo 详情", "AI 会议详情", "审批流程", "退款原因", "使用指南"):
            with self.subTest(name=name):
                self.assertTrue(chart_label_is_allowed(name, "label"))
        for copy in ("查看详情", "说明：请先登录", "详情见附件", "提示", "处理建议", "操作流程是先登记再审核"):
            with self.subTest(copy=copy):
                self.assertFalse(chart_label_is_allowed(copy, "label"))


if __name__ == "__main__":
    unittest.main()
