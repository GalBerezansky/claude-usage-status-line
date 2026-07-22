#!/bin/bash

command -v jq >/dev/null || { printf "statusline: jq not found\n" >&2; exit 1; }

input=$(cat)
cur=$(echo "$input" | jq -r '.context_window.used_percentage // 0 | floor')
model=$(echo "$input" | jq -r '.model.display_name // .model.id // "?"')
effort=$(echo "$input" | jq -r '.effort // .effort_level // .effortLevel // .model.effort // .model.reasoningEffort // empty')
if [ -z "$effort" ]; then
  effort=$(jq -r '.effortLevel // .effort // .reasoningEffort // "auto"' ~/.claude/settings.json 2>/dev/null)
fi
[ -z "$effort" ] && effort="auto"
git_status=$(git -C "$PWD" status --porcelain=v2 --branch 2>/dev/null)
branch=$(printf '%s\n' "$git_status" | awk '/^# branch.head / {print $3; exit}')
[ -z "$branch" ] && branch='-'
added=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
removed=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
in_tok=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
out_tok=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
transcript=$(echo "$input" | jq -r '.transcript_path // ""')

# `/clear` starts a fresh transcript, but cost/lines-added/removed are
# process-lifetime cumulative counters, so a new transcript would still
# show the old session's totals. Snapshot a baseline the first time a
# transcript is seen and render the delta since then.
if [ -n "$transcript" ]; then
  state_dir="${TMPDIR:-/tmp}/claude-statusline"
  mkdir -p "$state_dir" 2>/dev/null
  state_file="$state_dir/$(printf '%s' "$transcript" | cksum | cut -d' ' -f1)"
  if [ ! -f "$state_file" ]; then
    printf '%s %s %s\n' "$added" "$removed" "$cost" > "$state_file"
  fi
  read -r base_added base_removed base_cost < "$state_file" 2>/dev/null
  added=$((added - ${base_added:-0}))
  removed=$((removed - ${base_removed:-0}))
  cost=$(awk -v c="$cost" -v b="${base_cost:-0}" 'BEGIN{printf "%.4f", c-b}')
fi
rate_5h=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty | floor')
rate_7d=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty | floor')
rate_5h_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
[ -n "$rate_5h_reset" ] && rate_5h_time=$(date -r "$rate_5h_reset" '+%H:%M' 2>/dev/null || date -d "@$rate_5h_reset" '+%H:%M' 2>/dev/null)
rate_7d_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')
[ -n "$rate_7d_reset" ] && rate_7d_time=$(date -r "$rate_7d_reset" '+%a %H:%M' 2>/dev/null || date -d "@$rate_7d_reset" '+%a %H:%M' 2>/dev/null)

GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
ORANGE=$'\033[38;2;255;140;0m'
CYAN=$'\033[36m'
BOLD_CYAN=$'\033[1;36m'
BRIGHT_WHITE=$'\033[97m'
CAVEMAN=$'\033[38;5;172m'
DIM=$'\033[2m'
RESET=$'\033[0m'

if [ "$cur" -lt 40 ]; then
  ctx_color=$GREEN
elif [ "$cur" -lt 60 ]; then
  ctx_color=$YELLOW
else
  ctx_color=$RED
fi

if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
  branch_color=$ORANGE
else
  branch_color=$CYAN
fi

caveman_badge=""
caveman_flag="$HOME/.claude/.caveman-active"
if [ -f "$caveman_flag" ]; then
  caveman_mode=$(cat "$caveman_flag" 2>/dev/null)
  if [ "$caveman_mode" = "full" ] || [ -z "$caveman_mode" ]; then
    caveman_badge="${CAVEMAN}[CAVEMAN]${RESET}"
  else
    caveman_suffix=$(echo "$caveman_mode" | tr '[:lower:]' '[:upper:]')
    caveman_badge="${CAVEMAN}[CAVEMAN:${caveman_suffix}]${RESET}"
  fi
fi

fmt_tok() { awk -v v="$1" 'BEGIN{if(v>=1000000) printf "%.1fM",v/1000000; else if(v>=1000) printf "%.1fk",v/1000; else printf "%d",v}'; }
in_fmt=$(fmt_tok "$in_tok")
out_fmt=$(fmt_tok "$out_tok")

rate_color() {
  if [ -z "$1" ]; then
    echo "$DIM"
  elif [ "$1" -lt 50 ]; then
    echo "$GREEN"
  elif [ "$1" -lt 80 ]; then
    echo "$YELLOW"
  else
    echo "$RED"
  fi
}
rate_text=""
if [ -n "$rate_5h" ]; then
  r5_color=$(rate_color "$rate_5h")
  if [ -n "$rate_7d" ]; then
    r7_color=$(rate_color "$rate_7d")
    rate_7d_display="${rate_7d}%"
  else
    r7_color="$DIM"
    rate_7d_display="n/a"
  fi
  tz_abbr=$(date '+%Z')
  reset_str=""
  [ -n "$rate_5h_time" ] && reset_str=" ${RESET}${DIM}(reset at ${YELLOW}${rate_5h_time} ${tz_abbr}${RESET}${DIM})${RESET}"
  reset_7d_str=""
  [ -n "$rate_7d_time" ] && reset_7d_str=" ${RESET}${DIM}(reset at ${YELLOW}${rate_7d_time} ${tz_abbr}${RESET}${DIM})${RESET}"
  rate_text="${BRIGHT_WHITE}usage 5h window: ${RESET}${r5_color}${rate_5h}%${reset_str} ${BRIGHT_WHITE}7d: ${RESET}${r7_color}${rate_7d_display}${reset_7d_str}${RESET}"
fi

section_msgs=""
if [ -f "$transcript" ]; then
  msgs=$(grep -c '"type":"last-prompt"' "$transcript" 2>/dev/null)
  [ -n "$msgs" ] && [ "$msgs" -gt 0 ] && section_msgs=" │ ${BRIGHT_WHITE}msgs:${RESET} ${YELLOW}${msgs}${RESET}"
fi

section_cost=""
if awk "BEGIN{exit !($cost>0)}" 2>/dev/null; then
  cost_fmt=$(awk -v c="$cost" 'BEGIN{printf "%.2f", c}')
  if awk -v c="$cost" 'BEGIN{exit !(c>=5)}'; then
    cost_color=$RED
  elif awk -v c="$cost" 'BEGIN{exit !(c>=1)}'; then
    cost_color=$YELLOW
  else
    cost_color=$GREEN
  fi
  section_cost=" ${DIM}│ ${RESET}${BRIGHT_WHITE}\$${RESET}${cost_color}${cost_fmt}${RESET}"
fi

ab_str=""
ab=$(printf '%s\n' "$git_status" | awk '/^# branch.ab / {print $3, $4; exit}')
ahead=$(printf '%s\n' "$ab" | awk '{print $1}' | tr -d '+')
behind=$(printf '%s\n' "$ab" | awk '{print $2}' | tr -d '-')
[ -n "$ahead" ] && [ "$ahead" != "0" ] && ab_str="${ab_str} ${GREEN}↑${ahead}${RESET}"
[ -n "$behind" ] && [ "$behind" != "0" ] && ab_str="${ab_str} ${RED}↓${behind}${RESET}"

conflicts=$(printf '%s\n' "$git_status" | grep -c '^u ')
conflict_str=""
[ "$conflicts" -gt 0 ] 2>/dev/null && conflict_str=" ${RED}⚠ ${conflicts}c${RESET}"

dirty_files=$(printf '%s\n' "$git_status" | grep -c '^[12u?]')
if [ -n "$git_status" ] && [ "$dirty_files" -gt 0 ]; then
  git_dirty=" ${YELLOW}● ${dirty_files}f${RESET}${ab_str}${conflict_str}"
else
  git_dirty=" ${GREEN}✔${RESET}${ab_str}${conflict_str}"
fi

# Peak detection in Israel time (IDT): Mon-Fri 15:00-21:00
day_idt=$(TZ='Asia/Jerusalem' date +%u)   # 1=Mon, 7=Sun
hour_idt=$(TZ='Asia/Jerusalem' date +%-H)
if [ "$day_idt" -ge 6 ] || [ "$hour_idt" -lt 15 ] || [ "$hour_idt" -ge 21 ]; then
  offpeak_now="${GREEN}✔ off-peak now (limits burn slower)${RESET}"
else
  offpeak_now="${RED}✘ peak now (limits burn faster)${RESET}"
fi

line1="${ctx_color}ctx: ${cur}%${RESET} │ ${BOLD_CYAN}${PWD/#$HOME/~}${RESET} │ ${BRIGHT_WHITE}${model}${RESET} │ ${BRIGHT_WHITE}effort:${RESET} ${YELLOW}${effort}${RESET}${section_msgs} │ ${branch_color}${branch}${git_dirty}${RESET} │ ${BRIGHT_WHITE}tokens in: ${RESET}${YELLOW}${in_fmt}${RESET} ${BRIGHT_WHITE}out: ${RESET}${YELLOW}${out_fmt}${RESET}"
line2="${DIM}  ${GREEN}+${added}${RESET} ${RED}-${removed}${RESET}${section_cost}"
[ -n "$rate_text" ] && line2="${line2} ${DIM}│ ${RESET}${rate_text}"
line3="${DIM}  ${offpeak_now} ${DIM}│ peak: Mon–Fri 15:00–21:00 IDT${RESET}"
[ -n "$caveman_badge" ] && line3="${line3} ${DIM}│ ${RESET}${caveman_badge}"
printf '%s\n' "$line1"
printf '%s\n' "$line2"
printf '%s\n' "$line3"
