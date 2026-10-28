"""Experience stores: notes upsert by key, caps prune the least valuable, check finds duplicates; hardware merges replace."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experience  # noqa: E402
import hw_experience  # noqa: E402


class NotesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(experience, name, root / file) for name, file in (
            ("NOTES", "notes.json"), ("PATTERNS", "patterns.json"), ("SOURCES", "sources.json"), ("CATALOG", "catalog.md"))]
        for p in self.patches:
            p.start()
        self.out = redirect_stdout(StringIO())
        self.out.__enter__()

    def tearDown(self) -> None:
        self.out.__exit__(None, None, None)
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def notes(self) -> list[dict]:
        return experience.load_notes(experience.NOTES)["notes"]

    def test_same_key_replaces_and_keeps_one_previous(self) -> None:
        self.assertEqual(experience.note("preference", "表头对齐", "表头左对齐")[0], "added")
        self.assertEqual(experience.note("preference", "表头对齐", "表头与数据居中")[0], "replaced")
        experience.note("preference", "表头对齐", "表头与短数据居中，长文本左对齐")
        notes = self.notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["text"], "表头与短数据居中，长文本左对齐")
        self.assertEqual(notes[0]["previous"], {"text": "表头与数据居中", "replaced_at": notes[0]["last_confirmed"]})
        self.assertEqual(notes[0]["uses"], 3)
        self.assertIn("表头与短数据居中", experience.CATALOG.read_text(encoding="utf-8"))

    def test_same_statement_under_new_key_confirms_instead_of_adding(self) -> None:
        experience.note("lesson", "drawer", "详情用居中悬浮面板。")
        action, entry = experience.note("lesson", "panel", "详情用居中悬浮面板")
        self.assertEqual((action, entry["key"], entry["uses"]), ("confirmed", "drawer", 2))
        self.assertEqual(len(self.notes()), 1)

    def test_cap_drops_fewest_uses_then_oldest(self) -> None:
        with mock.patch.dict(experience.NOTE_CAPS, {"preference": 3}):
            for i in range(3):
                experience.note("preference", f"p{i}", f"偏好 {i}")
            doc = experience.load_notes(experience.NOTES)
            for n in doc["notes"]:
                n["last_confirmed"] = {"p0": "2026-01-02", "p1": "2026-01-01", "p2": "2026-01-03"}[n["key"]]
            doc["notes"][2]["uses"] = 5
            experience.save_notes(experience.NOTES, doc)
            experience.note("preference", "p3", "偏好 3")
            keys = sorted(n["key"] for n in self.notes())
        self.assertEqual(keys, ["p0", "p2", "p3"])

    def test_check_finds_duplicates_overflow_bad_shape_and_private_data(self) -> None:
        base = {"kind": "fact", "first_seen": "2026-01-01", "last_confirmed": "2026-01-01", "uses": 1}
        doc = {**experience.new_notes_doc(), "notes": [
            {**base, "key": "a", "text": "一条事实"}, {**base, "key": "a", "text": "另一条"},
            {**base, "key": "b", "text": "一条 事实！"}, {**base, "key": "c", "text": "电话 13812345678"},
            {**base, "key": "d", "text": "路径", "id": "X-1", "created": "2026-01-01T00:00:00"}]}
        errors = "\n".join(experience.check_notes(doc))
        self.assertIn("duplicate note key a", errors)
        self.assertIn("repeats the statement of a", errors)
        self.assertIn("phone number", errors)
        self.assertIn("unknown fields created, id", errors)
        with mock.patch.dict(experience.NOTE_CAPS, {"fact": 2}):
            self.assertTrue(any("exceed the cap" in e for e in experience.check_notes(doc)))

    def test_note_refuses_private_data(self) -> None:
        for text in ("联系人微信号: abc_12345", "发到 someone@example.com", r"方案在 C:\Users\me\plan.html", "token: abc123"):
            with self.assertRaises(SystemExit, msg=text):
                experience.note("fact", "contact", text)
        self.assertEqual(self.notes(), [])


class SharedNotesSpecTest(unittest.TestCase):
    """experience/notes.json has the shape shared by Luz-System, Luz-Design, Luz-Dev and Luz-Writing."""

    def test_committed_notes_file_matches_shared_spec(self) -> None:
        path = Path(__file__).resolve().parents[1] / "experience" / "notes.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(list(doc), ["schema_version", "caps", "notes"])
        self.assertEqual(doc["schema_version"], "1.0")
        self.assertEqual(doc["caps"], {"preference": 60, "lesson": 120, "fact": 120})
        allowed = {"key", "kind", "text", "why", "uses", "first_seen", "last_confirmed", "previous"}
        for n in doc["notes"]:
            self.assertLessEqual({"key", "kind", "text", "uses", "first_seen", "last_confirmed"}, set(n), n.get("key"))
            self.assertLessEqual(set(n), allowed, n.get("key"))
            self.assertIn(n["kind"], ("preference", "lesson", "fact"))
            self.assertRegex(n["first_seen"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertRegex(n["last_confirmed"], r"^\d{4}-\d{2}-\d{2}$")
            if "previous" in n:
                self.assertEqual(set(n["previous"]), {"text", "replaced_at"})
        self.assertEqual(len({n["key"] for n in doc["notes"]}), len(doc["notes"]))
        self.assertEqual(experience.check_notes(doc), [])
        self.assertFalse((path.parent / "preferences.json").exists() or (path.parent / "lessons.json").exists()
                         or (path.parent / "experience.json").exists())


class HardwareMergeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(hw_experience, "ROOT", Path(self.tmp.name))
        self.patch.start()
        self.out = redirect_stdout(StringIO())
        self.out.__enter__()

    def tearDown(self) -> None:
        self.out.__exit__(None, None, None)
        self.patch.stop()
        self.tmp.cleanup()

    def product(self, pid: str, prices: list[tuple[str, str, int]]) -> dict:
        return {"id": pid, "category": "门禁通行", "subsystem": "无人自助", "brand": "示例", "model": "AB-100",
                "verdict": "可用", "specs": {"供电": "12V"},
                "prices": [{"url": u, "date": d, "cny": c} for u, d, c in prices]}

    def test_product_merges_by_model_and_keeps_latest_prices(self) -> None:
        old = self.product("ab-100", [(f"https://x/{i}", f"2026-0{i}-01", 100 + i) for i in range(1, 5)])
        new = self.product("other-id", [("https://x/1", "2026-09-01", 99), ("https://x/9", "2026-08-01", 120),
                                        ("https://x/8", "2026-07-01", 130)])
        merged = hw_experience.merge_items("products", [old], [new])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "ab-100")
        prices = merged[0]["prices"]
        self.assertEqual(len(prices), hw_experience.PRICE_KEEP)
        self.assertEqual(prices[0], {"url": "https://x/1", "date": "2026-09-01", "cny": 99})
        self.assertEqual(len({p["url"] for p in prices}), len(prices))

    def test_queries_merge_by_text_and_compat_is_symmetric(self) -> None:
        q = hw_experience.merge_items("queries", [{"platform": "1688", "query": "人脸 门禁", "useful": False}],
                                      [{"platform": "1688", "query": "人脸门禁", "useful": True, "date": "2026-10-01"}])
        self.assertEqual(len(q), 1)
        self.assertTrue(q[0]["useful"])
        c = hw_experience.merge_items("compat", [{"a": "读头", "b": "控制器", "ok": True}],
                                      [{"a": "控制器", "b": "读头", "ok": False}])
        self.assertEqual(len(c), 1)
        self.assertFalse(c[0]["ok"])

    def test_cap_drops_oldest_query_and_check_flags_duplicates(self) -> None:
        with mock.patch.dict(hw_experience.CAPS, {"queries": 2}):
            cur = [{"platform": "web", "query": f"q{i}", "useful": True, "date": f"2026-0{i}-01"} for i in range(1, 3)]
            cur = hw_experience.merge_items("queries", cur, [{"platform": "web", "query": "q3", "useful": True, "date": "2026-09-01"}])
        self.assertEqual([x["query"] for x in cur], ["q2", "q3"])
        dup = [self.product("a", []), self.product("b", [])]
        (Path(self.tmp.name) / "catalog.json").write_text(json.dumps(dup, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(any("重复的产品" in e for e in hw_experience.duplicate_errors()))


class RulePageLatinTest(unittest.TestCase):
    def test_latin_only_allowed_in_code_and_kbd(self) -> None:
        from validate_session import TreeBuilder
        from validate_skill import prose_text

        def prose(html: str) -> str:
            builder = TreeBuilder()
            builder.feed(html)
            return prose_text(builder.root)

        self.assertNotRegex(prose("<p>徽标显示 <code>99+</code>，按 <kbd>Esc</kbd> 关闭，日期 <code>YYYY-MM-DD</code></p>"), "[A-Za-z]")
        self.assertRegex(prose("<p>按 Esc 关闭</p>"), "[A-Za-z]")


if __name__ == "__main__":
    unittest.main()
