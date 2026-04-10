import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STATUSLINE = REPO_ROOT / "statusline.sh"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text):
    return ANSI_RE.sub("", text)


def run_cmd(cmd, cwd):
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def init_repo(repo_dir):
    run_cmd(["git", "init"], repo_dir)
    run_cmd(["git", "config", "user.email", "test@example.com"], repo_dir)
    run_cmd(["git", "config", "user.name", "Statusline Test"], repo_dir)
    (repo_dir / "tracked.txt").write_text("base\n")
    run_cmd(["git", "add", "tracked.txt"], repo_dir)
    run_cmd(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], repo_dir)
    run_cmd(["git", "branch", "-M", "main"], repo_dir)


class StatuslineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("jq") is None:
            raise unittest.SkipTest("jq is required for statusline tests")

    def setUp(self):
        self.repo_tmp = tempfile.TemporaryDirectory()
        self.home_tmp = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.repo_tmp.name)
        self.home_dir = Path(self.home_tmp.name)
        init_repo(self.repo_dir)

    def tearDown(self):
        self.repo_tmp.cleanup()
        self.home_tmp.cleanup()

    def run_statusline(self, payload):
        env = os.environ.copy()
        env["HOME"] = str(self.home_dir)
        return subprocess.run(
            [str(STATUSLINE)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=str(self.repo_dir),
            env=env,
        )

    def write_caveman_flag(self, value):
        claude_dir = self.home_dir / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / ".caveman-active").write_text(value)

    def test_full_payload_renders_usage_and_peak_lines(self):
        payload = {
            "context_window": {"used_percentage": 12, "total_input_tokens": 1000, "total_output_tokens": 2000},
            "model": {"display_name": "sonnet"},
            "effort": "high",
            "cost": {"total_lines_added": 5, "total_lines_removed": 2},
            "rate_limits": {
                "five_hour": {"used_percentage": 23, "resets_at": 1712345678},
                "seven_day": {"used_percentage": 41, "resets_at": 1712901234},
            },
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        lines = strip_ansi(result.stdout).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("ctx: 12%", lines[0])
        self.assertIn("effort: high", lines[0])
        self.assertIn("+5 -2", lines[1])
        self.assertIn("usage 5h window: 23%", lines[1])
        self.assertIn("7d: 41%", lines[1])
        self.assertIn("peak: Mon", lines[2])

    def test_missing_seven_day_is_rendered_as_na(self):
        payload = {
            "context_window": {"used_percentage": 12},
            "model": {"display_name": "sonnet"},
            "cost": {"total_lines_added": 1, "total_lines_removed": 2},
            "rate_limits": {"five_hour": {"used_percentage": 23, "resets_at": 1712345678}},
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("integer expression expected", result.stderr)
        self.assertIn("7d: n/a", strip_ansi(result.stdout))

    def test_no_rate_limits_omits_usage_line(self):
        payload = {
            "context_window": {"used_percentage": 12},
            "model": {"display_name": "sonnet"},
            "cost": {"total_lines_added": 1, "total_lines_removed": 2},
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        lines = strip_ansi(result.stdout).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("+1 -2", lines[1])
        self.assertNotIn("usage 5h window", strip_ansi(result.stdout))

    def test_dirty_repo_shows_modified_file_count(self):
        (self.repo_dir / "tracked.txt").write_text("changed\n")
        payload = {
            "context_window": {"used_percentage": 8},
            "model": {"display_name": "sonnet"},
            "cost": {"total_lines_added": 0, "total_lines_removed": 0},
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("● 1f", strip_ansi(result.stdout))

    def test_clean_repo_shows_checkmark(self):
        payload = {
            "context_window": {"used_percentage": 8},
            "model": {"display_name": "sonnet"},
            "cost": {"total_lines_added": 0, "total_lines_removed": 0},
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("✔", strip_ansi(result.stdout))

    def test_effort_defaults_to_auto_without_settings(self):
        payload = {
            "context_window": {"used_percentage": 8},
            "model": {"display_name": "sonnet"},
            "cost": {"total_lines_added": 0, "total_lines_removed": 0},
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("effort: auto", strip_ansi(result.stdout))

    def test_model_id_is_used_when_display_name_missing(self):
        payload = {
            "context_window": {"used_percentage": 8},
            "model": {"id": "claude-model-id"},
            "cost": {"total_lines_added": 0, "total_lines_removed": 0},
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("claude-model-id", strip_ansi(result.stdout))

    def test_caveman_full_badge_when_flag_is_full(self):
        self.write_caveman_flag("full")
        payload = {
            "context_window": {"used_percentage": 8},
            "model": {"display_name": "sonnet"},
            "cost": {"total_lines_added": 0, "total_lines_removed": 0},
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        lines = strip_ansi(result.stdout).splitlines()
        self.assertIn("[CAVEMAN]", lines[2])
        self.assertNotIn("[CAVEMAN]", lines[0])

    def test_caveman_mode_badge_is_uppercased(self):
        self.write_caveman_flag("wenyan-lite")
        payload = {
            "context_window": {"used_percentage": 8},
            "model": {"display_name": "sonnet"},
            "cost": {"total_lines_added": 0, "total_lines_removed": 0},
        }
        result = self.run_statusline(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        lines = strip_ansi(result.stdout).splitlines()
        self.assertIn("[CAVEMAN:WENYAN-LITE]", lines[2])
        self.assertNotIn("[CAVEMAN:WENYAN-LITE]", lines[0])


if __name__ == "__main__":
    unittest.main()
