#!/usr/bin/env python3
"""Safely activate another mode in an existing Luz Design session."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable

from new_session import MODE_NAMES, OUTPUT_ROOT, SESSION_RE, SKILL_ROOT, init_mode

LOCK_TIMEOUT_SECONDS = 5.0


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain an object")
    return data


def atomic_json(path: Path, data: dict) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing to replace symlink: {path}")
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def acquire_lock(lock: Path) -> None:
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock.mkdir()
            return
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for manifest lock: {lock}")
            time.sleep(0.05)


def checked_session(root: Path, session: Path) -> Path:
    root = root.resolve()
    candidate = session.resolve()
    if candidate.parent != root or not SESSION_RE.match(candidate.name) or not candidate.is_dir():
        raise ValueError("session must be an existing numbered directory directly under the output root")
    return candidate


def add_mode(root: Path, session: Path, mode: str, *, standalone_poster: bool = False, skill_root: Path = SKILL_ROOT, source_checker: Callable[[str], int] | None = None, allow_live_crawl_offline: bool = False) -> dict:
    if mode not in {"visual", "prototype", "document"}:
        raise ValueError("add_mode supports visual, prototype, or document; system scope is created only by the intake workflow")
    session = checked_session(root, session)
    work = session / "raw"
    manifest_path = work / "99-delivery" / "MANIFEST.json"
    approvals_path = work / "99-delivery" / "APPROVALS.json"
    manifest = load_json(manifest_path)
    approvals = load_json(approvals_path)
    modes = list(manifest.get("modes", []))
    kind = manifest.get("session_kind")
    if mode == "visual":
        from validate_session import validate
        system_approved = approvals.get("system_design", {}).get("status") == "approved"
        architecture_approved = approvals.get("architecture", {}).get("status") == "approved"
        poster_requested = (
            standalone_poster
            and kind == "standalone_poster"
            and approvals.get("standalone_poster", {}).get("status") in {"requested", "approved"}
        )
        architecture = work / "01-system" / "03-system-architecture.html"
        design = work / "01-system" / "04-system-design.html"
        legacy_design = work / "01-system" / "03-system-design.html"
        if system_approved and architecture_approved:
            if not architecture.is_file():
                raise PermissionError("visual mode requires an existing 01-system/03-system-architecture.html")
            if not design.is_file() and not legacy_design.is_file():
                raise PermissionError("visual mode requires an existing approved system design HTML")
            errors = validate(
                session,
                live_sources=True,
                source_checker=source_checker,
                allow_live_crawl_offline=allow_live_crawl_offline,
            )
            if errors:
                raise PermissionError("visual gate failed: " + "; ".join(errors))
        elif poster_requested:
            errors = validate(session)
            if errors:
                raise PermissionError("standalone poster gate failed: " + "; ".join(errors))
        else:
            raise PermissionError("visual mode requires approved architecture and system design; standalone posters must be declared when the session is created")
    elif mode == "prototype":
        from validate_session import validate
        visual_approved = approvals.get("visual", {}).get("status") == "approved"
        visual = work / "02-visual" / "visual-board.html"
        if not visual_approved or not visual.is_file():
            raise PermissionError("prototype mode requires an approved 02-visual/visual-board.html")
        errors = validate(
            session,
            live_sources=True,
            source_checker=source_checker,
            allow_live_crawl_offline=allow_live_crawl_offline,
        )
        if errors:
            raise PermissionError("prototype gate failed: " + "; ".join(errors))

    if mode in modes:
        return manifest

    init_mode(skill_root, work, mode)
    updated_modes = [item for item in MODE_NAMES if item in set(modes + [mode])]
    lock = manifest_path.with_name(".MANIFEST.lock")
    acquire_lock(lock)
    try:
        current = load_json(manifest_path)
        if current.get("session_id") != manifest.get("session_id"):
            raise ValueError("manifest changed during update")
        current_modes = list(current.get("modes", []))
        if mode not in current_modes:
            current_modes.append(mode)
        current["modes"] = [item for item in MODE_NAMES if item in set(current_modes)]
        atomic_json(manifest_path, current)
        return current
    finally:
        try:
            lock.rmdir()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Activate a Luz Design mode after its approval gate.")
    parser.add_argument("session", help="Numbered session folder")
    parser.add_argument("mode", choices=["visual", "prototype", "document"])
    parser.add_argument("--standalone-poster", action="store_true")
    parser.add_argument("--root", help="Session root override, primarily for tests")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else OUTPUT_ROOT
    try:
        manifest = add_mode(root, Path(args.session), args.mode, standalone_poster=args.standalone_poster)
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("PASS: active modes: " + ", ".join(manifest.get("modes", [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
