"""Interface detail checks on prototypes (validate_session.prototype_ui_findings)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from new_session import fill_icon_slots, read_template, tab_icon_href
from validate_session import parse_html, prototype_list_brand_findings, prototype_ui_findings, tab_icon_errors

PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>后台</title>
<style>{css}</style></head><body><main data-artifact="interactive-prototype"><h1>门店后台</h1>
<section><h2>原型</h2>{body}</section></main></body></html>"""


def findings(body: str = "", css: str = "") -> tuple[list[str], list[str]]:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "interactive-prototype.html"
        path.write_text(PAGE.format(css=css, body=body), encoding="utf-8")
        errors: list[str] = []
        root = parse_html(path, errors)
        assert root is not None, errors
        return prototype_ui_findings(root)


def rows(*values: str) -> str:
    return "".join(f"<tr><td>{name}</td><td>{value}</td></tr>" for name, value in values)


class TitleAndNavigationTests(unittest.TestCase):
    def test_title_equal_to_active_nav_item_is_an_error(self) -> None:
        errors, _ = findings('<nav><a class="active" href="#p1">会员管理</a><a href="#p2">订单</a></nav>'
                             '<div id="p1"><h2 class="page-title">会员管理</h2></div>')
        self.assertTrue(any("repeats the highlighted navigation item: 会员管理" in e for e in errors))

    def test_title_equal_to_nav_item_through_page_id_is_an_error(self) -> None:
        errors, _ = findings('<aside><nav><a data-page-id="P-001">线索 12</a></nav></aside>'
                             '<div data-page-id="P-001"><h3>线索</h3></div>')
        self.assertTrue(any("repeats the highlighted navigation item: 线索" in e for e in errors))

    def test_page_area_without_repeated_title_passes(self) -> None:
        errors, _ = findings('<nav><a aria-current="page" href="#p1">会员管理</a></nav>'
                             '<div id="p1"><div class="toolbar"><button>新建会员</button></div></div>')
        self.assertEqual([e for e in errors if "navigation" in e], [])

    def test_group_named_like_its_only_item_is_an_error(self) -> None:
        errors, _ = findings('<nav><div class="nav-group"><div class="group-title">概览</div><a href="#a">概览</a></div>'
                             '<div class="nav-group"><div class="group-title">交易</div><a href="#b">订单</a><a href="#c">退款</a></div></nav>')
        self.assertEqual([e for e in errors if "group" in e], ["interactive-prototype navigation group repeats its only item: 概览"])


class TableTests(unittest.TestCase):
    def table(self, body: str, header: str = "<tr><th>客户</th><th>备注</th></tr>", wrapper: str = "") -> str:
        return f"<div {wrapper}><table><thead>{header}</thead><tbody>{body}</tbody></table></div>"

    def test_column_empty_in_every_row_is_an_error(self) -> None:
        errors, _ = findings(self.table(rows(("甲", "—"), ("乙", "-"), ("丙", ""))))
        self.assertTrue(any("empty in every row" in e and "备注" in e for e in errors))

    def test_column_with_any_value_passes(self) -> None:
        errors, _ = findings(self.table(rows(("甲", "—"), ("乙", "加急"))))
        self.assertFalse(any("empty in every row" in e for e in errors))

    def test_loading_skeleton_table_is_ignored(self) -> None:
        errors, _ = findings(self.table(rows(("", ""), ("", "")), wrapper='data-state-kind="加载"'))
        self.assertFalse(any("empty in every row" in e for e in errors))

    def test_same_value_in_five_rows_is_a_warning(self) -> None:
        errors, warnings = findings(self.table(rows(*[(f"客户{i}", "已支付") for i in range(5)])))
        self.assertEqual([e for e in errors if "table" in e], [])
        self.assertTrue(any("same value in every row" in w and "备注" in w for w in warnings))

    def test_export_preview_with_field_names_is_an_error(self) -> None:
        errors, _ = findings(self.table(rows(("甲", "1")), header="<tr><th>order_no</th><th>金额（元）</th></tr>",
                                        wrapper='class="export-preview"'))
        self.assertTrue(any("field name" in e and "order_no" in e for e in errors))

    def test_narrow_cell_padding_is_a_warning(self) -> None:
        _, warnings = findings(css="td{padding:12px 8px}th{padding:12px 16px}")
        self.assertEqual([w for w in warnings if "padding" in w], ["interactive-prototype table cell side padding 8px below 16px: td"])


class TextSizeTests(unittest.TestCase):
    def test_small_table_text_is_an_error(self) -> None:
        errors, _ = findings(css="td{font-size:12px}")
        self.assertTrue(any("12px below 14px" in e and ": td" in e for e in errors))

    def test_auxiliary_classes_may_use_12_and_13px(self) -> None:
        css = ".order-time{font-size:12px}.price-unit{font:13px/18px sans-serif}.meta,.hint{font-size:12px}.badge{font-size:12px}"
        errors, warnings = findings(css=css)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_other_small_text_is_a_warning(self) -> None:
        errors, warnings = findings(css=".summary{font-size:13px}")
        self.assertEqual(errors, [])
        self.assertTrue(any("13px below 14px" in w and ".summary" in w for w in warnings))

    def test_inline_small_paragraph_is_an_error(self) -> None:
        errors, _ = findings('<p style="font-size:12px">正文</p><span class="time" style="font-size:12px">10:00</span>')
        self.assertEqual(len([e for e in errors if "inline text" in e]), 1)

    def test_prototype_template_has_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "interactive-prototype.html"
            path.write_text(fill_icon_slots(read_template(ROOT, "interactive-prototype.html"), "健身房后台"), encoding="utf-8")
            root = parse_html(path, [])
            self.assertEqual(prototype_ui_findings(root), ([], []))
            self.assertEqual(prototype_list_brand_findings(root), [])
            self.assertEqual(tab_icon_errors(root, path.name), [])


def list_findings(body: str) -> list[str]:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "interactive-prototype.html"
        path.write_text(PAGE.format(css="", body=body), encoding="utf-8")
        root = parse_html(path, [])
        return prototype_list_brand_findings(root)


def icon_errors(head: str) -> list[str]:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "page.html"
        path.write_text(f"<!doctype html><html><head>{head}</head><body><h1>页</h1></body></html>", encoding="utf-8")
        return tab_icon_errors(parse_html(path, []), path.name)


PAGER = ('<div class="pagination"><span>共 86 条</span><select>{options}</select>'
         '<button type="button">1</button><button type="button">2</button></div>')
SIZES = '<option value="10"{a}>10 条/页</option><option value="20"{b}>20 条/页</option><option value="50">50 条/页</option>'


class PaginationAndBrandTests(unittest.TestCase):
    def test_marked_list_without_pagination_is_a_warning(self) -> None:
        warnings = list_findings('<table class="member-list"><tr><th>会员</th></tr><tr><td>甲</td></tr></table>')
        self.assertTrue(any("without pagination" in w for w in warnings))

    def test_ten_rows_without_pagination_is_a_warning_even_without_a_class(self) -> None:
        warnings = list_findings("<table>" + rows(*[(f"客户{i}", str(i)) for i in range(10)]) + "</table>")
        self.assertTrue(any("without pagination" in w for w in warnings))

    def test_short_plain_table_and_one_page_lists_are_exempt(self) -> None:
        self.assertEqual(list_findings("<table>" + rows(("甲", "1"), ("乙", "2")) + "</table>"), [])
        opted_out = '<table class="list" data-pagination="none">' + rows(*[(f"档位{i}", str(i)) for i in range(12)]) + "</table>"
        self.assertEqual(list_findings(opted_out), [])
        self.assertEqual(list_findings('<div class="modal"><table class="list">' + rows(("甲", "1")) + "</table></div>"), [])

    def test_pagination_defaulting_to_20_passes(self) -> None:
        body = '<table class="list"><tbody id="rows"></tbody></table>' + PAGER.format(options=SIZES.format(a="", b=" selected"))
        self.assertEqual(list_findings(body), [])

    def test_other_default_page_size_is_a_warning(self) -> None:
        body = '<table class="list"></table>' + PAGER.format(options=SIZES.format(a=" selected", b=""))
        self.assertTrue(any("defaults to 10" in w for w in list_findings(body)))
        text_only = '<table class="list"></table><div>共 86 条 · 50 条/页</div>'
        warnings = list_findings(text_only)
        self.assertFalse(any("without pagination" in w for w in warnings))
        self.assertTrue(any("defaults to 50" in w for w in warnings))
        self.assertTrue(any("defaults to 10" in w for w in list_findings('<div class="pager" data-page-size="10"></div>')))

    def test_admin_header_needs_a_graphic_brand_mark(self) -> None:
        self.assertTrue(any("brand mark" in w for w in list_findings('<header class="topbar"><strong>门店后台</strong></header>')))
        self.assertTrue(any("brand mark" in w for w in list_findings('<aside class="sidebar"><div class="logo">健</div></aside>')))
        mark = '<svg viewBox="0 0 32 32"><rect width="32" height="32" rx="8"/></svg>'
        self.assertEqual(list_findings(f'<header class="topbar"><div class="brand">{mark}<span>门店后台</span></div></header>'), [])
        self.assertEqual(list_findings(f'<aside class="sidebar"><div class="logo"><img src="logo.svg" alt="">门店后台</div></aside>'), [])

    def test_mini_program_frame_header_is_not_an_admin_shell(self) -> None:
        self.assertEqual(list_findings('<div class="phone"><header class="mp-nav">首页</header></div>'), [])


class TabIconTests(unittest.TestCase):
    def test_missing_empty_and_placeholder_icons_are_errors(self) -> None:
        self.assertTrue(any("no browser-tab icon" in e for e in icon_errors("<title>页</title>")))
        for href in ("", "#", "{{TAB_ICON}}", "data:image/svg+xml,", "data:image/svg+xml,%3Csvg%3E%3C/svg%3E"):
            with self.subTest(href=href):
                self.assertTrue(any("empty or an unfilled placeholder" in e for e in icon_errors(f'<link rel="icon" href="{href}">')))

    def test_inline_theme_icon_passes(self) -> None:
        self.assertEqual(icon_errors(f'<link rel="icon" href="{tab_icon_href("健身房后台")}">'), [])
        self.assertEqual(icon_errors('<link rel="shortcut icon" href="favicon.ico">'), [])



class IconSetTests(unittest.TestCase):
    def test_keywords_pick_the_pictogram_and_theme_colour(self) -> None:
        from new_session import FALLBACK_COLORS, pick_icon, theme_colors
        cases = {"健身房后台": "dumbbell", "政府采购招标": "megaphone", "商机雷达获客系统": "radar", "门禁硬件选型": "chip",
                 "珠宝财务智能化": "ledger", "零售门店管理": "store", "Demo一键生成": "grid"}
        for name, icon in cases.items():
            with self.subTest(name=name):
                self.assertEqual(pick_icon(name), icon)
        self.assertEqual(theme_colors("Demo一键生成", themes_json=Path("missing.json")), FALLBACK_COLORS)
        self.assertEqual(theme_colors("某系统", themes_json=Path("missing.json")), FALLBACK_COLORS)

    def test_every_icon_is_flat_line_with_at_most_three_shapes_and_no_text(self) -> None:
        import re
        from new_session import TAB_ICONS, tab_icon_svg
        for key in TAB_ICONS:
            with self.subTest(icon=key):
                svg = tab_icon_svg("某系统", icon=key)
                self.assertIn('viewBox="0 0 32 32"', svg)
                self.assertIn('rx="8"', svg)
                self.assertNotIn("<text", svg)
                self.assertNotIn("Gradient", svg)
                self.assertLessEqual(len(re.findall(r"<(?:path|rect|circle|line|polyline|polygon|ellipse)\b", svg)), 3)
                self.assertRegex(svg, r'stroke-width="2\.\d+"')

    def test_same_system_gets_the_same_icon_on_every_page(self) -> None:
        text = '<link rel="icon" href="{{TAB_ICON}}"><h1>{{BRAND_MARK}}</h1>'
        a, b = fill_icon_slots(text, "健身房后台"), fill_icon_slots(text, "健身房后台")
        self.assertEqual(a, b)
        self.assertNotIn("{{", a)
        self.assertIn('class="brand-mark"', a)


if __name__ == "__main__":
    unittest.main(verbosity=2)
