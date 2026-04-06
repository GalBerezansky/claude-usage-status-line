# claude-statusline

A rich, information-dense status line for [Claude Code](https://claude.ai/code) — zero runtime dependencies beyond `bash` and `jq`.

```
ctx: 12% │ ~/Code/myproject │ claude-sonnet-4-6 │ effort: auto │ main ● 3f │ tokens in: 42.1k out: 8.3k │ +127 -34 │ usage 5h window: 23% (reset at 18:30) 7d: 41%
  ✔ off-peak now (limits burn slower) │ peak: Mon–Fri 15:00–21:00 IL
```

## Features

| Segment | Description |
|---------|-------------|
| `ctx: N%` | Context window usage — green → yellow → red at 40% / 60% |
| Working directory | Current path with `~` abbreviation |
| Model | Active Claude model name |
| Effort | Reasoning effort level (`auto`, `low`, `medium`, `high`) |
| Branch | Git branch — orange on `main`/`master`, cyan otherwise |
| Dirty state | `✔` clean or `● Nf` (N modified files) |
| Tokens | Input and output token counts (formatted: `1.2k`, `3.4M`) |
| Lines changed | `+added -removed` across the session |
| 5h window | API rate-limit usage % for the rolling 5-hour block, with reset time |
| 7d window | API rate-limit usage % for the rolling 7-day window, with reset time |
| **Peak/off-peak** | Whether Anthropic's high-traffic window is active *right now* in your timezone — limits burn faster during peak (Mon–Fri 5–11am PT) |

The peak/off-peak indicator is the only feature not found in other Claude Code status line tools. Anthropic applies stricter rate limits during US business hours; knowing whether you're in that window helps you pace usage and avoid hitting limits unexpectedly.

## Platform support

| Platform | Status |
|----------|--------|
| macOS | Supported |
| Linux | Supported |
| Windows | Not supported |

## Requirements

- `bash` 3.2+
- [`jq`](https://stedolan.github.io/jq/) — JSON parsing

```sh
brew install jq        # macOS
sudo apt install jq    # Debian/Ubuntu
```

## Installation

```sh
git clone <your-repo-url>
cd claude-statusline
./install.py
```

The script:
1. Copies `statusline.sh` to `~/.claude/hooks/claude-usage-status-line.sh`
2. Adds `statusLine` in `~/.claude/settings.json` only when missing/matching
3. Refuses to replace an existing `statusLine` unless you pass `--force`

Restart Claude Code to activate.

Use `--force` only if you want to replace an existing custom status line:

```sh
./install.py --force
```

### Manual installation

If you prefer to wire it up yourself:

```sh
cp statusline.sh ~/.claude/hooks/claude-usage-status-line.sh
chmod +x ~/.claude/hooks/claude-usage-status-line.sh
```

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "/Users/you/.claude/hooks/claude-usage-status-line.sh"
  }
}
```

## Configuration

Open `statusline.sh` and adjust the variables at the top of the file:

**Color thresholds** — context window color changes:
```bash
# green below 40%, yellow below 60%, red at 60%+
if [ "$cur" -lt 40 ]; then ctx_color=$GREEN
elif [ "$cur" -lt 60 ]; then ctx_color=$YELLOW
else ctx_color=$RED
fi
```

**Timezone for peak detection** — change `Asia/Jerusalem` to your own timezone:
```bash
peak_start_il=$(TZ='Asia/Jerusalem' date ...)
peak_end_il=$(TZ='Asia/Jerusalem' date ...)
...
day_of_week=$(TZ='Asia/Jerusalem' date +%u)
hour_il=$(TZ='Asia/Jerusalem' date +%-H)
```

Replace `Asia/Jerusalem` with your local timezone identifier (e.g. `Europe/London`, `America/New_York`). The peak window itself is always Mon–Fri 5–11am PT — only the display timezone changes.

## How it works

Claude Code calls the status line script once per render, piping a JSON payload on stdin:

```json
{
  "model": { "display_name": "claude-sonnet-4-6" },
  "context_window": { "used_percentage": 12 },
  "cost": { "total_lines_added": 127, "total_lines_removed": 34 },
  "rate_limits": {
    "five_hour":  { "used_percentage": 23, "resets_at": 1712345678 },
    "seven_day":  { "used_percentage": 41, "resets_at": 1712901234 }
  }
}
```

The script parses this with `jq`, queries `git` for branch and dirty state, and prints two or three lines of ANSI-colored output to stdout.

## Alternatives

If you want a more full-featured, GUI-configured status line with 30+ widgets and powerline separators, see [ccstatusline](https://github.com/sirmalloc/ccstatusline) (TypeScript/npm).

`claude-statusline` is for users who want a single self-contained shell script with no npm/Node dependency and a specific focus on rate-limit visibility.

## License

MIT
