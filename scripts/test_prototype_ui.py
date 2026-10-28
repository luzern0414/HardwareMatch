"""Interface detail checks on prototypes (validate_session.prototype_ui_findings)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from new_session import read_template
from validate_session import parse_html, prototype_ui_findings

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
            path.write_text(read_template(ROOT, "interactive-prototype.html"), encoding="utf-8")
            root = parse_html(path, [])
            self.assertEqual(prototype_ui_findings(root), ([], []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
