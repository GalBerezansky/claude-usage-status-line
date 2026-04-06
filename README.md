# claude-statusline

A rich, information-dense status line for [Claude Code](https://claude.ai/code) — zero runtime dependencies beyond `bash`, `jq`, and `python3` (for installer).

```
ctx: 12% │ ~/Code/myproject │ claude-sonnet-4-6 │ effort: auto │ main ● 3f │ tokens in: 42.1k out: 8.3k │ +127 -34
  usage 5h window: 23% (reset at 18:30) 7d: 41%
  ✔ off-peak now (limits burn slower) │ peak: Mon–Fri 05:00–11:00 PT
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
| **Peak/off-peak** | Whether Anthropic's high-traffic window is active *right now* in PT — limits burn faster during peak (Mon–Fri 5–11am PT) |

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
- `python3` — installer (`install.py`)

```sh
brew install jq        # macOS
sudo apt install jq python3    # Debian/Ubuntu
```

## Installation

Quick install (one command):

```sh
git clone https://github.com/GalBerezansky/claude-usage-status-line && cd claude-usage-status-line && ./install.py
```

If `statusLine` already exists and you want to replace it:
```sh
git clone https://github.com/GalBerezansky/claude-usage-status-line && cd claude-usage-status-line && ./install.py --force
```

If you are already inside the cloned repo:
```sh
./install.py
```
If `./install.py` fails with `permission denied`, run:
```sh
python3 install.py
```

The script:
1. Copies `statusline.sh` to `~/.claude/hooks/claude-usage-status-line.sh`
2. Adds `statusLine` in `~/.claude/settings.json` only when missing/matching
3. Refuses to replace an existing `statusLine` unless you pass `--force`

Restart Claude Code to activate.

### Manual installation

If you prefer to wire it up yourself:

```sh
cp statusline.sh ~/.claude/hooks/claude-usage-status-line.sh
chmod +x ~/.claude/hooks/claude-usage-status-line.sh
```

Add to `~/.claude/settings.json` (replace `/Users/your-username` with your actual home directory — run `echo $HOME` to get it):

```json
{
  "statusLine": {
    "type": "command",
    "command": "/Users/your-username/.claude/hooks/claude-usage-status-line.sh"
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

**Peak window label/detection** — edit these lines if you want different wording or window:
```bash
day_pt=$(TZ='America/Los_Angeles' date +%u)   # 1=Mon, 7=Sun
hour_pt=$(TZ='America/Los_Angeles' date +%-H)
if [ "$day_pt" -ge 6 ] || [ "$hour_pt" -lt 5 ] || [ "$hour_pt" -ge 11 ]; then
  offpeak_now="..."
else
  offpeak_now="..."
fi
line3="  ${offpeak_now} │ peak: Mon–Fri 05:00–11:00 PT"
```

By default, the script uses PT (`America/Los_Angeles`) to match Anthropic's documented peak window.

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
