"""先读规则卡：py -X utf8 scripts/context.py hardware --session "<会话目录>"（规则、偏好、教训、工具与检查；本脚本只是骨架）

校验 raw/04-hardware/plan.json → 生成 raw/04-hardware/hardware-plan.html → 用 Luz-Design 文档检查脚本验收；
交付时用 publish.py <会话> hardware 发布为会话唯一的最终 HTML。

用法：
  py -X utf8 scripts/hw_build.py "<会话目录>"

会话根目录只放最终 HTML 和 raw/；校验与检查结果写入 raw/build-report.json。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hw_plan_lib as pl  # noqa: E402
import hw_render_plan as render_plan  # noqa: E402

LUZ_DESIGN = Path(r"D:\Codes\Luz-Design")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    session = Path(sys.argv[1]).resolve()
    # The hardware rule card decides the plan; this builder only renders and checks it.
    card = session / "raw" / "00-rules" / "hardware.md"
    print(f"rule card for this plan: py -X utf8 scripts/context.py hardware --session \"{session}\"  (read it before writing plan.json)", file=sys.stderr)
    if not card.is_file():
        print("  WARN  raw/00-rules/hardware.md is missing: run the command above; publish.py refuses a session without it", file=sys.stderr)
    raw = session / "raw" / "04-hardware"
    plan = pl.load(raw / "plan.json")
    errors, warnings = pl.validate(plan)
    for w in warnings:
        print("  WARN ", w)
    for e in errors:
        print("  ERROR", e)
    report = {"plan_errors": errors, "plan_warnings": warnings}
    if errors:
        (raw / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"方案校验 {len(errors)} 个错误，未生成。")
        return 1
    no_img = [d["name"] for d in plan["devices"] if d.get("purchase", True) and d["tier"] in ("field", "edge") and not render_plan.image_data(d)]
    for n in no_img:
        print(f"  WARN  缺实物图：{n}（用 scripts/hw_fetch_images.py 补图）")
    report["missing_images"] = no_img
    out = raw / "hardware-plan.html"
    out.write_text(render_plan.render(plan), encoding="utf-8")
    checker = LUZ_DESIGN / "scripts" / "check_document.py"
    if checker.exists():
        r = subprocess.run([sys.executable, "-X", "utf8", str(checker), str(out)], capture_output=True, text=True, encoding="utf-8")
        print(r.stdout.strip())
        report["luz_design_check"] = {"returncode": r.returncode, "output": r.stdout}
        ok = r.returncode == 0
    else:
        print("  WARN 未找到 Luz-Design check_document.py，跳过文档检查")
        ok = True
    b = pl.budget(plan)
    report.update({
        "html": out.name,
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "devices": len(plan["devices"]),
        "links": len(plan["links"]),
        "total_cny": b["total"],
        "unpriced": b["unpriced"],
        "poe": pl.poe_budget(plan),
        "ups_w": pl.ups_load(plan),
    })
    (raw / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'通过' if ok else '未通过'}：{out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
