#!/usr/bin/env python3
"""Install claude-statusline into ~/.claude/hooks/ and patch settings.json safely."""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
HOOKS_DIR = CLAUDE_DIR / "hooks"
SETTINGS = CLAUDE_DIR / "settings.json"
DEFAULT_TARGET_NAME = "claude-usage-status-line.sh"


def parse_args():
    parser = argparse.ArgumentParser(description="Install Claude Code status line script.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing target script and existing statusLine setting.",
    )
    return parser.parse_args()


def desired_status_line(target):
    return {"type": "command", "command": str(target)}


def confirm(prompt):
    answer = input(f"{prompt} [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        sys.exit(0)


def load_settings_object():
    try:
        config = json.loads(SETTINGS.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: {SETTINGS} is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(config, dict):
        print(f"Error: {SETTINGS} must contain a JSON object at the top level.", file=sys.stderr)
        sys.exit(1)
    return config


def is_same_file(path_a, path_b):
    try:
        return path_a.samefile(path_b)
    except OSError:
        return False


def plan_install_script(source, target, force):
    if target.exists():
        if is_same_file(source, target):
            print(f"  = keep existing {target} (already installed)")
        elif force:
            print(f"  ~ overwrite existing {target} (--force)")
        else:
            print(f"  ! keep existing {target} (use --force to overwrite)")
    else:
        if not HOOKS_DIR.exists():
            print(f"  + create directory {HOOKS_DIR}")
        print(f"  + would copy statusline.sh → {target}")


def plan_patch_settings(target, force):
    wanted = desired_status_line(target)
    if not SETTINGS.exists():
        print(f"  + create {SETTINGS} with statusLine entry")
        print(f"      {json.dumps(wanted)}")
        return

    config = load_settings_object()
    existing = config.get("statusLine")
    if not existing:
        print(f"  + backup existing {SETTINGS} before update")
        print(f"  + add statusLine entry to {SETTINGS}")
        print(f"      {json.dumps(wanted)}")
    elif existing == wanted:
        print(f"  = keep existing statusLine in {SETTINGS} (already set)")
    elif force:
        print(f"  + backup existing {SETTINGS} before update")
        print(f"  ~ replace existing statusLine in {SETTINGS} (--force):")
        print(f"      was: {json.dumps(existing)}")
        print(f"      now: {json.dumps(wanted)}")
    else:
        print(f"  ! keep existing statusLine in {SETTINGS} (use --force to replace):")
        print(f"      existing: {json.dumps(existing)}")
        print(f"      desired:  {json.dumps(wanted)}")


def has_blocking_conflicts(source, target, force):
    if force:
        return False

    if target.exists() and not is_same_file(source, target):
        return True

    if SETTINGS.exists():
        config = load_settings_object()
        existing = config.get("statusLine")
        wanted = desired_status_line(target)
        if existing and existing != wanted:
            return True

    return False


def backup_settings(raw_text):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = SETTINGS.with_name(f"{SETTINGS.name}.bak.{stamp}")
    suffix = 1
    while backup.exists():
        backup = SETTINGS.with_name(f"{SETTINGS.name}.bak.{stamp}.{suffix}")
        suffix += 1
    backup.write_text(raw_text)
    print(f"Backup:    {backup}")


def install_script(source, target, force):
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if is_same_file(source, target):
            target.chmod(target.stat().st_mode | 0o111)
            print(f"Already installed: {target}")
            return
        if not force:
            print(
                f"Error: target script exists at {target}. Re-run with --force to overwrite.",
                file=sys.stderr,
            )
            sys.exit(1)
    shutil.copy2(source, target)
    target.chmod(target.stat().st_mode | 0o111)
    print(f"Installed: {target}")


def patch_settings(target, force):
    wanted = desired_status_line(target)
    indent = 2
    if SETTINGS.exists():
        raw = SETTINGS.read_text()
        config = load_settings_object()
        existing = config.get("statusLine")
        if existing == wanted:
            print(f"Unchanged: {SETTINGS}")
            return
        if existing and not force:
            print(
                f"Error: {SETTINGS} already has statusLine. Re-run with --force to replace it.",
                file=sys.stderr,
            )
            sys.exit(1)
        for line in raw.splitlines():
            stripped = line.lstrip()
            if stripped and line != stripped:
                indent = len(line) - len(stripped)
                break
        backup_settings(raw)
    else:
        config = {}

    config["statusLine"] = wanted
    SETTINGS.write_text(json.dumps(config, indent=indent) + "\n")
    print(f"Updated:   {SETTINGS}")


if __name__ == "__main__":
    args = parse_args()
    source = SCRIPT_DIR / "statusline.sh"
    target = HOOKS_DIR / DEFAULT_TARGET_NAME

    print("claude-statusline installer\n")
    print("Planned actions:")
    plan_install_script(source, target, args.force)
    plan_patch_settings(target, args.force)
    if has_blocking_conflicts(source, target, args.force):
        print("\nCannot continue without --force.")
        sys.exit(1)
    print()
    confirm("Proceed?")
    print()
    install_script(source, target, args.force)
    patch_settings(target, args.force)
    print("\nDone. Restart Claude Code to see the status line.")
