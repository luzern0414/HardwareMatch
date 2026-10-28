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
    sha256_file,
    validate_light_html,
    work_dir,
)

STAGE_PATHS = {
    "system_design": SYSTEM_DESIGN_PATH,
    "visual": VISUAL_PATH,
    "prototype": PROTOTYPE_PATH,
    "hardware": "04-hardware/hardware-plan.html",
}


def publish(folder: Path, stage: str) -> Path:
    folder = folder.resolve()
    work = work_dir(folder)
    if stage not in STAGE_PATHS:
        raise ValueError(f"stage must be one of: {', '.join(STAGE_PATHS)}")
    source = work / STAGE_PATHS[stage]
    if not source.is_file():
        raise FileNotFoundError(f"missing stage artifact: raw/{STAGE_PATHS[stage]}")
    errors: list[str] = []
    # Prototypes render real interfaces with a 12px floor (Luz-Design visual-design.html 字体与字号); reading pages keep 14px.
    validate_light_html(source, errors, min_px=12.0 if stage == "prototype" else 14.0)
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
