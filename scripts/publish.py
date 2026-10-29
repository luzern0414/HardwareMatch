#!/usr/bin/env python3
"""Publish one stage artifact as the session's single final HTML: <session>/<session-folder>.html."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_session import (
    PROTOTYPE_PATH,
    SYSTEM_DESIGN_PATH,
    VISUAL_PATH,
    final_html,
    rule_card_errors,
    sediment_errors,
    sha256_file,
    tab_icon_errors,
    validate_approval_record,
    validate_light_html,
    work_dir,
)

STAGE_PATHS = {
    "system_design": SYSTEM_DESIGN_PATH,
    "visual": VISUAL_PATH,
    "prototype": PROTOTYPE_PATH,
    "hardware": "04-hardware/hardware-plan.html",
}
# The rule card each stage is built from (references/cards.json), named in the refusal message.
STAGE_CARDS = {
    "system_design": "system-design",
    "visual": "admin-list | miniprogram | website | agent-ui",
    "prototype": "prototype",
    "hardware": "hardware",
}
# A stage belongs to a mode, and add_mode.py adds a mode only after the stages before it are approved by a person.
# Publishing checks the same chain, so a stage written without its approvals is never delivered.
STAGE_MODES = {"system_design": "system", "visual": "visual", "prototype": "prototype", "hardware": "hardware"}
UPSTREAM_APPROVALS = {
    "system_design": ("module_scope", "architecture"),
    "visual": ("module_scope", "architecture", "system_design"),
    "prototype": ("module_scope", "architecture", "system_design", "visual"),
    # The hardware list has no downstream stage, so its own approval by the person is the gate.
    "hardware": ("hardware",),
}


def approval_gate_errors(work: Path, stage: str) -> list[str]:
    """The stage's mode is declared and every upstream approval is a person's, on the file as it is now."""
    delivery = work / "99-delivery"
    manifest = json.loads((delivery / "MANIFEST.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    mode = STAGE_MODES[stage]
    if mode not in manifest.get("modes", []):
        errors.append(f"stage {stage} belongs to mode {mode}, which this session has not declared: add it with "
                      f"`py -X utf8 scripts/add_mode.py <会话> {mode}`, which checks the approvals before it")
    upstream = UPSTREAM_APPROVALS[stage]
    if stage == "visual" and manifest.get("session_kind") == "standalone_poster":
        upstream = ()
    if not upstream:
        return errors
    try:
        approvals = json.loads((delivery / "APPROVALS.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return errors + ["raw/99-delivery/APPROVALS.json is missing or unreadable"]
    for name in upstream:
        item = approvals.get(name)
        if not isinstance(item, dict) or item.get("status") != "approved":
            errors.append(f"{name} is not approved yet: show it to the person and record their approval in APPROVALS.json "
                          "(scripts and the model never approve)")
            continue
        validate_approval_record(work, name, item, errors)
    return errors


def publish(folder: Path, stage: str) -> Path:
    folder = folder.resolve()
    work = work_dir(folder)
    if stage not in STAGE_PATHS:
        raise ValueError(f"stage must be one of: {', '.join(STAGE_PATHS)}")
    source = work / STAGE_PATHS[stage]
    if not source.is_file():
        raise FileNotFoundError(f"missing stage artifact: raw/{STAGE_PATHS[stage]}")
    approval_errors = approval_gate_errors(work, stage)
    if approval_errors:
        raise PermissionError("publish refused, approval gate: " + "; ".join(approval_errors))
    # Work starts from a current rule card and the BRIEF names the rules it applied (scripts/context.py).
    rule_errors = rule_card_errors(work, require_adopted=True, check_current=True)
    if rule_errors:
        raise ValueError(f"publish refused, rule card gate (`py -X utf8 scripts/context.py {STAGE_CARDS[stage]} --session <会话>`, then fill BRIEF 采用的规则): " + "; ".join(rule_errors))
    # Every call leaves experience behind (SKILL.md 每次调用后沉淀): notes written or confirmed for this session.
    created = json.loads((work / "99-delivery" / "MANIFEST.json").read_text(encoding="utf-8")).get("created_at", "")
    note_errors = sediment_errors(work, str(created)[:10])
    if note_errors:
        raise ValueError("publish refused, sediment gate (`py -X utf8 scripts/experience.py note --kind preference|lesson|fact --key <主题> --text \"<一句话原则>\"`, then list the key in BRIEF 本次沉淀): " + "; ".join(note_errors))
    errors: list[str] = []
    # Visual boards and prototypes render real interfaces with a 12px floor for auxiliary text (Luz-Design
    # visual-design.html 字体与字号); a standalone poster and reading pages keep 14px.
    poster = json.loads((work / "99-delivery" / "MANIFEST.json").read_text(encoding="utf-8")).get("session_kind") == "standalone_poster"
    interface = stage == "prototype" or (stage == "visual" and not poster)
    root = validate_light_html(source, errors, min_px=12.0 if interface else 14.0)
    # Every published page carries its own browser-tab icon (Luz-Design visual-design.html 网页图标与品牌标识).
    if root is not None:
        errors.extend(tab_icon_errors(root, source.name))
    if errors:
        raise ValueError("stage artifact fails the HTML contract: " + "; ".join(errors))
    for item in folder.iterdir():
        if item.is_file() and item.suffix.lower() == ".html" and item != final_html(folder):
            raise ValueError(f"unexpected HTML at the session root: {item.name}")
    target = final_html(folder)
    shutil.copyfile(source, target)
    manifest_path = work / "99-delivery" / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["final"] = {
        "path": target.name,
        "stage": stage,
        "source": STAGE_PATHS[stage],
        "sha256": sha256_file(target),
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", help="Numbered session folder in the output root")
    parser.add_argument("stage", choices=sorted(STAGE_PATHS), help="Stage artifact to publish")
    args = parser.parse_args(argv)
    try:
        target = publish(Path(args.session), args.stage)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PUBLISHED: {target}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
