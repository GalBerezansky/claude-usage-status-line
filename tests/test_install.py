import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "install.py"
STATUSLINE_SRC = REPO_ROOT / "statusline.sh"
TARGET_NAME = "claude-usage-status-line.sh"


def run_installer(config_dir, *args, input_text="y\n"):
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, str(INSTALLER), *args]
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


class InstallerTests(unittest.TestCase):
    def test_fresh_install_creates_hook_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            result = run_installer(config_dir)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            target = config_dir / "hooks" / TARGET_NAME
            self.assertTrue(target.exists())
            self.assertTrue(os.access(target, os.X_OK))

            settings = json.loads((config_dir / "settings.json").read_text())
            self.assertEqual(
                settings["statusLine"],
                {"type": "command", "command": str(target)},
            )
            self.assertEqual(len(list(config_dir.glob("settings.json.bak.*"))), 0)

    def test_existing_status_line_requires_force_and_makes_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            settings_path = config_dir / "settings.json"
            original = {"statusLine": {"type": "command", "command": "/tmp/old.sh"}}
            settings_path.write_text(json.dumps(original) + "\n")

            result = run_installer(config_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("keep existing statusLine", result.stdout)
            self.assertIn("Cannot continue without --force.", result.stdout)
            self.assertFalse((config_dir / "hooks").exists())
            self.assertEqual(json.loads(settings_path.read_text()), original)
            self.assertEqual(len(list(config_dir.glob("settings.json.bak.*"))), 0)

    def test_force_replaces_existing_status_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            settings_path = config_dir / "settings.json"
            original = {"statusLine": {"type": "command", "command": "/tmp/old.sh"}}
            settings_path.write_text(json.dumps(original))

            result = run_installer(config_dir, "--force")
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            target = config_dir / "hooks" / TARGET_NAME
            settings = json.loads(settings_path.read_text())
            self.assertEqual(
                settings["statusLine"],
                {"type": "command", "command": str(target)},
            )
            backups = list(config_dir.glob("settings.json.bak.*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text()), original)

    def test_existing_settings_without_statusline_gets_backup_before_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            settings_path = config_dir / "settings.json"
            original = {"env": {"A": "1"}}
            settings_path.write_text(json.dumps(original) + "\n")

            result = run_installer(config_dir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            backups = list(config_dir.glob("settings.json.bak.*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text()), original)

    def test_invalid_json_settings_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            (config_dir / "settings.json").write_text("{invalid-json")

            result = run_installer(config_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("is not valid JSON", result.stderr)
            self.assertFalse((config_dir / "hooks").exists())

    def test_non_object_settings_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            (config_dir / "settings.json").write_text("[]")

            result = run_installer(config_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("must contain a JSON object", result.stderr)
            self.assertFalse((config_dir / "hooks").exists())

    def test_existing_target_requires_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            hooks_dir = config_dir / "hooks"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            target = hooks_dir / TARGET_NAME
            target.write_text("old-script\n")
            (config_dir / "settings.json").write_text("{}\n")

            result = run_installer(config_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("use --force to overwrite", result.stdout)
            self.assertIn("Cannot continue without --force.", result.stdout)
            self.assertEqual(target.read_text(), "old-script\n")

    def test_same_file_target_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            hooks_dir = config_dir / "hooks"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            target = hooks_dir / TARGET_NAME
            target.symlink_to(STATUSLINE_SRC)

            wanted = {"type": "command", "command": str(target)}
            (config_dir / "settings.json").write_text(json.dumps({"statusLine": wanted}) + "\n")

            result = run_installer(config_dir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("Already installed", result.stdout)
            self.assertIn("Unchanged", result.stdout)


if __name__ == "__main__":
    unittest.main()
