#!/usr/bin/env python3
"""Install claude-statusline into ~/.claude/hooks/ and patch settings.json."""

import json
import os
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
HOOKS_DIR = CLAUDE_DIR / "hooks"
SETTINGS = CLAUDE_DIR / "settings.json"
TARGET = HOOKS_DIR / "statusline.sh"


def confirm(prompt):
    answer = input(f"{prompt} [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        sys.exit(0)


def plan_install_script():
    if TARGET.exists():
        print(f"  ~ overwrite existing {TARGET}")
    else:
        if not HOOKS_DIR.exists():
            print(f"  + create directory {HOOKS_DIR}")
        print(f"  + copy statusline.sh → {TARGET}")


def plan_patch_settings():
    if not SETTINGS.exists():
        print(f"  + create {SETTINGS} with statusLine entry")
        return

    config = json.loads(SETTINGS.read_text())
    existing = config.get("statusLine")
    if existing:
        print(f"  ~ replace existing statusLine in {SETTINGS}:")
        print(f"      was: {json.dumps(existing)}")
        print(f"      now: {json.dumps({'type': 'command', 'command': str(TARGET)})}")
    else:
        print(f"  + add statusLine entry to {SETTINGS}")
        print(f"      {json.dumps({'type': 'command', 'command': str(TARGET)})}")


def install_script():
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT_DIR / "statusline.sh", TARGET)
    TARGET.chmod(TARGET.stat().st_mode | 0o111)
    print(f"Installed: {TARGET}")


def patch_settings():
    indent = 2
    if SETTINGS.exists():
        raw = SETTINGS.read_text()
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: {SETTINGS} is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
        for line in raw.splitlines():
            stripped = line.lstrip()
            if stripped and line != stripped:
                indent = len(line) - len(stripped)
                break
    else:
        config = {}

    config["statusLine"] = {"type": "command", "command": str(TARGET)}
    SETTINGS.write_text(json.dumps(config, indent=indent) + "\n")
    print(f"Updated:   {SETTINGS}")


if __name__ == "__main__":
    print("claude-statusline installer\n")
    print("The following changes will be made:")
    plan_install_script()
    plan_patch_settings()
    print()
    confirm("Proceed?")
    print()
    install_script()
    patch_settings()
    print("\nDone. Restart Claude Code to see the status line.")
